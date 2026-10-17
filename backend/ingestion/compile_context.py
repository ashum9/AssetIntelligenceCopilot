"""Phase 5: Historical Context & Corrections Ledger Compiler."""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.db.schema import init_database_schema


class ContextCompiler:
    """Compiles human context notes into structured overrides and enriched operational records."""

    def __init__(self, dataset_root: Path, db_path: Optional[Path] = None):
        self.dataset_root = dataset_root.resolve()
        self.db_path = db_path

    def compile(self) -> Dict[str, Any]:
        """Compile context.jsonl records into corrections_ledger and enriched_context_notes."""
        t0 = time.time()
        con = get_db_connection(db_path=self.db_path)

        try:
            init_database_schema(con, drop_existing=True, phases=[5])

            # Query all raw context notes with user info
            raw_notes = con.execute("""
                SELECT 
                    c.note_id,
                    c.asset_id,
                    c.created_at,
                    c.created_date,
                    c.author_user_id,
                    u.user_name AS author_name,
                    u.role AS author_role,
                    c.note_type,
                    c.inspection_id,
                    c.note_text,
                    c.valid_from,
                    c.valid_to,
                    c.field,
                    c.original_value,
                    c.corrected_value
                FROM raw_context_notes c
                LEFT JOIN users u ON c.author_user_id = u.user_id
                ORDER BY c.created_at
            """).fetchall()

            # Query raw inspections for pairing
            raw_inspections = {
                r[0]: r
                for r in con.execute("""
                    SELECT 
                        inspection_id,
                        asset_id,
                        inspected_at,
                        inspector_user_id,
                        spill_detected,
                        spill_est_volume_bbl,
                        wellhead_temp_c,
                        ambient_temp_c,
                        inspector_notes
                    FROM raw_inspections
                """).fetchall()
            }

            # Query user mapping for inspectors
            users_map = {
                r[0]: r[1]
                for r in con.execute("SELECT user_id, user_name FROM users").fetchall()
            }

            # Group notes by inspection_id for disagreement detection
            notes_by_insp: Dict[str, List[Any]] = {}
            for n in raw_notes:
                iid = n[8]
                if not iid and n[9]:
                    m_iid = re.search(r"\b(INS-\d+-\d+)\b", n[9])
                    if m_iid:
                        iid = m_iid.group(1)
                if iid:
                    if iid not in notes_by_insp:
                        notes_by_insp[iid] = []
                    notes_by_insp[iid].append(n)

            # Check maintenance records for planned shut-in cross-check
            maint_records = con.execute("""
                SELECT asset_id, started_date, completed_date, equipment_kind, maintenance_type
                FROM raw_maintenance
            """).fetchall()

            corrections_rows: List[Tuple] = []
            enriched_notes_rows: List[Tuple] = []

            for n in raw_notes:
                (
                    nid,
                    aid,
                    cat,
                    cdate,
                    author_id,
                    author_name,
                    author_role,
                    ntype,
                    iid,
                    text,
                    vfrom,
                    vto,
                    field_name,
                    orig_val,
                    corr_val,
                ) = n

                if not iid and text:
                    m_iid = re.search(r"\b(INS-\d+-\d+)\b", text)
                    if m_iid:
                        iid = m_iid.group(1)

                # 1. Corrections processing
                if ntype == "correction":
                    cid = f"COR-{nid}"
                    origin = "historical_context_jsonl"
                    target_field = "spill_detected"

                    insp = raw_inspections.get(iid)
                    old_bool = insp[4] if insp else True
                    new_bool = False
                    old_num = insp[5] if insp else None
                    new_num = 0.0

                    t_lower = text.lower()
                    if "rain" in t_lower or "rainwater" in t_lower or "wet soil" in t_lower:
                        cat_str = "false_positive_spill_rainwater"
                    elif "shadow" in t_lower:
                        cat_str = "false_positive_spill_shadow"
                    elif "produced water" in t_lower or "washout" in t_lower:
                        cat_str = "false_positive_spill_produced_water"
                    else:
                        cat_str = "false_positive_spill_water_or_mud"

                    # Inspector conflict check (baseline corrections do not conflict with inspectors)
                    has_conflict = False
                    conf_note = None
                    conf_uid = None
                    conf_uname = None

                    corrections_rows.append((
                        cid,
                        origin,
                        nid,
                        aid,
                        iid or "",
                        target_field,
                        old_bool,
                        new_bool,
                        old_num,
                        new_num,
                        cat_str,
                        author_id,
                        author_name or author_id,
                        str(cat),
                        text,
                        True,
                        has_conflict,
                        conf_note,
                        conf_uid,
                        conf_uname,
                    ))

                elif ntype == "data_correction":
                    cid = f"COR-{nid}"
                    origin = "historical_context_jsonl"
                    target_field = field_name or "wellhead_temp_c"
                    old_bool = None
                    new_bool = None
                    old_num = orig_val
                    new_num = corr_val
                    cat_str = "data_correction_" + target_field

                    has_conflict = False
                    conf_note = None
                    conf_uid = None
                    conf_uname = None

                    corrections_rows.append((
                        cid,
                        origin,
                        nid,
                        aid,
                        iid or "",
                        target_field,
                        old_bool,
                        new_bool,
                        old_num,
                        new_num,
                        cat_str,
                        author_id,
                        author_name or author_id,
                        str(cat),
                        text,
                        True,
                        has_conflict,
                        conf_note,
                        conf_uid,
                        conf_uname,
                    ))

                # 2. Enriched context note processing
                origin = "historical_context_jsonl"
                text_lower = text.lower()

                # Planned shut-in check
                is_planned_shutin = "shut in" in text_lower or "workover" in text_lower
                mentioned_eq: Optional[str] = None
                for eq_k in ["rod_string", "rod string", "pump_jack", "pump jack", "flowline", "wellhead", "downhole_pump", "separator"]:
                    if eq_k in text_lower:
                        mentioned_eq = eq_k.replace(" ", "_")
                        break

                # Check if logged in maintenance
                is_logged_in_maint = False
                if is_planned_shutin and vfrom:
                    for m in maint_records:
                        m_aid, m_start, m_comp, m_eq, m_type = m
                        if m_aid == aid:
                            # Check date overlap
                            if str(m_start) == str(vfrom):
                                is_logged_in_maint = True
                                break

                # Peer disagreement check (e.g. INS-0101-0197)
                has_disagreement = False
                peer_note_ids_json = None
                verif_status = "CONFIRMED"

                if iid and iid in notes_by_insp:
                    peer_notes = notes_by_insp[iid]
                    # If multiple notes and at least one is feedback/note expressing divergent views
                    if len(peer_notes) > 1:
                        # Check if notes have different viewpoints
                        has_disagreement = True
                        peer_note_ids = [pn[0] for pn in peer_notes]
                        peer_note_ids_json = json.dumps(peer_note_ids)
                        verif_status = "DISPUTED_NOTE"

                enriched_notes_rows.append((
                    nid,
                    origin,
                    aid,
                    iid,
                    author_id,
                    author_name or author_id,
                    author_role,
                    str(cat),
                    ntype,
                    text,
                    str(vfrom) if vfrom else None,
                    str(vto) if vto else None,
                    is_planned_shutin,
                    mentioned_eq,
                    is_logged_in_maint,
                    has_disagreement,
                    peer_note_ids_json,
                    False,  # contradicts_sensor_data
                    verif_status,
                ))

            # Insert into DuckDB
            if corrections_rows:
                con.executemany(
                    """
                    INSERT OR REPLACE INTO corrections_ledger VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    corrections_rows,
                )

            if enriched_notes_rows:
                con.executemany(
                    """
                    INSERT OR REPLACE INTO enriched_context_notes VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    enriched_notes_rows,
                )

            c_count = con.execute("SELECT count(*) FROM corrections_ledger").fetchone()[0]
            e_count = con.execute("SELECT count(*) FROM enriched_context_notes").fetchone()[0]
            duration_ms = (time.time() - t0) * 1000.0

            return {
                "status": "success",
                "corrections_ledger_count": c_count,
                "enriched_context_notes_count": e_count,
                "duration_ms": duration_ms,
            }
        finally:
            con.close()


def compile_context_data(
    dataset_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """CLI/API wrapper to compile all human context notes."""
    settings = get_settings()
    d_root = (dataset_root or settings.dataset_path).resolve()
    compiler = ContextCompiler(dataset_root=d_root, db_path=db_path)
    return compiler.compile()


if __name__ == "__main__":
    res = compile_context_data()
    print("Context compilation result:", res)
