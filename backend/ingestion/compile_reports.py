"""Phase 4: Free-Text Maintenance Report Compiler (Markdown -> SQL)."""

import json
import re
import sys
import time
from datetime import datetime
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


CONTAINMENT_REGEX = re.compile(
    r"(?:contained|release was contained)\s+(?:about\s+)?(\d+(?:\.\d+)?)\s*hours",
    re.I,
)
CONTAINMENT_TABLE_REGEX = re.compile(
    r"\|\s*SR-02\s*\|\s*(?:\*\*)?(?:Not met|Met)(?:\*\*)?\s*\|\s*Contained\s+(?:about\s+)?(\d+(?:\.\d+)?)\s*hours",
    re.I,
)
SPILL_CLASS_REGEX = re.compile(
    r"\((minor|moderate|reportable|major)\s+class\)",
    re.I,
)
RCA_TABLE_REGEX = re.compile(
    r"\|\s*Manual\s*§10\s*\|\s*Action required\s*\|(.*?)\|",
    re.I,
)
PROTOCOLS_REGEX = re.compile(
    r"\b(SR-0[1-4]|RC-0[1-5]|WS-0[1-7])\b"
)


def extract_report_sections(markdown_text: str) -> Dict[str, str]:
    """Extract standard sections from maintenance report Markdown."""
    sections = {
        "what_happened": "",
        "root_cause": "",
        "safety_steps": "",
        "work_done": "",
        "tests": "",
        "cleanup": "",
        "parts_and_cost": "",
        "compliance_check": "",
        "notes": "",
    }

    # Split by level 2 headings
    raw_sections = re.split(r"^##\s+", markdown_text, flags=re.MULTILINE)
    for part in raw_sections[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        heading = lines[0].strip().lower()
        body = "\n".join(lines[1:]).strip()

        if "what happened" in heading:
            sections["what_happened"] = body
        elif "root cause" in heading:
            sections["root_cause"] = body
        elif "safety" in heading:
            sections["safety_steps"] = body
        elif "work done" in heading:
            sections["work_done"] = body
        elif "testing" in heading:
            sections["tests"] = body
        elif "clean-up" in heading or "waste" in heading:
            sections["cleanup"] = body
        elif "parts and cost" in heading:
            sections["parts_and_cost"] = body
        elif "compliance" in heading:
            sections["compliance_check"] = body
        elif "notes" in heading:
            sections["notes"] = body

    return sections


class ReportCompiler:
    """Compiles all ~1,500 free-text maintenance reports into SQL."""

    def __init__(self, dataset_root: Path, db_path: Optional[Path] = None):
        self.dataset_root = dataset_root.resolve()
        self.db_path = db_path

    def compile(self) -> Dict[str, Any]:
        """Compile all Markdown repair reports into parsed_repair_reports."""
        t0 = time.time()
        con = get_db_connection(db_path=self.db_path)

        try:
            init_database_schema(con, drop_existing=True, phases=[4])

            # Query maintenance mapping
            maint_rows = con.execute("""
                SELECT 
                    maintenance_id,
                    asset_id,
                    triggered_by_inspection_id,
                    started_date,
                    report_file,
                    resolved_report_path
                FROM raw_maintenance
                WHERE report_file IS NOT NULL
            """).fetchall()

            # Map relative path to maintenance record
            path_to_maint: Dict[str, Tuple] = {}
            for r in maint_rows:
                mid, aid, trig_id, sdate, rfile, rpath = r
                if rpath:
                    path_to_maint[rpath] = r

            # Find all reports on disk
            report_files = sorted(list(self.dataset_root.glob("assets/WELL-*/maintenance-reports/*.md")))
            parsed_rows: List[Tuple] = []

            for p in report_files:
                rel_path = str(p.relative_to(self.dataset_root))
                maint_rec = path_to_maint.get(rel_path)

                if maint_rec:
                    mid, aid, trig_id, sdate, rfile, rpath = maint_rec
                else:
                    # Fallback extraction from filename / header
                    mid_match = re.search(r"(MNT-\d+-\d+)", p.name)
                    mid = mid_match.group(1) if mid_match else p.stem
                    aid_match = re.search(r"(WELL-\d+)", rel_path)
                    aid = aid_match.group(1) if aid_match else "UNKNOWN"
                    trig_id = None
                    sdate = None

                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract sections
                secs = extract_report_sections(content)

                # Extract containment hours
                containment_hours: Optional[float] = None
                containment_excerpt: Optional[str] = None

                # Search what happened and compliance check
                m_contain = CONTAINMENT_REGEX.search(secs["what_happened"]) or CONTAINMENT_REGEX.search(content)
                if m_contain:
                    containment_hours = float(m_contain.group(1))
                    # Extract surrounding sentence
                    sentence_match = re.search(r"([^.\n]*?" + re.escape(m_contain.group(0)) + r"[^.\n]*?\.)", content)
                    containment_excerpt = sentence_match.group(1).strip() if sentence_match else m_contain.group(0)
                else:
                    m_table = CONTAINMENT_TABLE_REGEX.search(secs["compliance_check"]) or CONTAINMENT_TABLE_REGEX.search(content)
                    if m_table:
                        containment_hours = float(m_table.group(1))
                        containment_excerpt = m_table.group(0).strip()

                exceeds_sr02 = (containment_hours > 4.0) if containment_hours is not None else None

                # Extract spill class
                spill_class_match = SPILL_CLASS_REGEX.search(secs["compliance_check"]) or SPILL_CLASS_REGEX.search(content)
                reported_class = spill_class_match.group(1).lower() if spill_class_match else None

                # Extract reporting duty statement
                duty_statement: Optional[str] = None
                if "no reporting duty" in content.lower():
                    duty_statement = "No reporting duty based on moderate classification"
                elif "external report required" in content.lower() or "reported to the state" in content.lower():
                    duty_statement = "External report required per SR-01"

                # Extract RCA action required
                rca_match = RCA_TABLE_REGEX.search(secs["compliance_check"]) or RCA_TABLE_REGEX.search(content)
                rca_action = bool(rca_match) or ("action required" in secs["compliance_check"].lower() and "manual §10" in secs["compliance_check"].lower())
                rca_text = rca_match.group(1).strip() if rca_match else (
                    "Manual §10 Action required" if rca_action else None
                )

                # Extract annual flowline test
                flowline_annual_test = (
                    "flowline passed its annual integrity test" in content.lower()
                    or "annual flowline integrity test" in content.lower()
                )

                # Extract Parts installed
                m_parts = re.search(r"\*\*Parts installed:\*\*\s*(.*)", content)
                parts_model: Optional[str] = None
                parts_serial: Optional[str] = None
                parts_lot: Optional[str] = None
                if m_parts:
                    p_text = m_parts.group(1).strip()
                    m_mod = re.search(r"\b(Highline\s+[A-Z0-9-]+|ESP-[A-Z0-9-]+|RP-[A-Z0-9-]+)\b", p_text, re.I)
                    if m_mod:
                        parts_model = m_mod.group(1)
                    m_sn = re.search(r"\b(SN-[A-Z0-9-]+)\b", p_text, re.I)
                    if m_sn:
                        parts_serial = m_sn.group(1)
                    m_lot = re.search(r"\b(LOT-[A-Z0-9-]+)\b", p_text, re.I)
                    if m_lot:
                        parts_lot = m_lot.group(1)

                # Extract Follow-up
                m_fu = re.search(r"\*\*Follow-up:\*\*\s*(.*)", content)
                fu_days: Optional[int] = None
                fu_text: Optional[str] = None
                if m_fu:
                    fu_text = m_fu.group(1).strip()
                    m_fud = re.search(r"within\s+(\d+)\s+days", fu_text, re.I)
                    if m_fud:
                        fu_days = int(m_fud.group(1))

                # Referenced protocols
                found_protocols = sorted(list(set(PROTOCOLS_REGEX.findall(content))))
                protocols_json = json.dumps(found_protocols)

                parsed_rows.append((
                    mid,
                    aid,
                    trig_id,
                    rel_path,
                    str(sdate) if sdate else None,
                    secs["what_happened"],
                    secs["root_cause"],
                    secs["safety_steps"],
                    secs["work_done"],
                    secs["tests"],
                    secs["cleanup"],
                    secs["parts_and_cost"],
                    secs["compliance_check"],
                    containment_hours,
                    containment_excerpt,
                    exceeds_sr02,
                    reported_class,
                    duty_statement,
                    rca_action,
                    rca_text,
                    flowline_annual_test,
                    protocols_json,
                    parts_model,
                    parts_serial,
                    parts_lot,
                    fu_days,
                    fu_text,
                    content,
                ))

            if parsed_rows:
                con.executemany(
                    """
                    INSERT OR REPLACE INTO parsed_repair_reports VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    parsed_rows,
                )

            total_parsed = len(parsed_rows)
            duration_ms = (time.time() - t0) * 1000.0

            return {
                "status": "success",
                "total_reports_parsed": total_parsed,
                "duration_ms": duration_ms,
            }
        finally:
            con.close()


def compile_reports_data(
    dataset_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """CLI/API wrapper to compile all repair reports."""
    settings = get_settings()
    d_root = (dataset_root or settings.dataset_path).resolve()
    compiler = ReportCompiler(dataset_root=d_root, db_path=db_path)
    return compiler.compile()


if __name__ == "__main__":
    res = compile_reports_data()
    print("Report compilation result:", res)
