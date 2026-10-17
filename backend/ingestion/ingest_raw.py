import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.db.schema import init_database_schema


def ingest_raw_data(
    dataset_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    mode: str = "rebuild",
    reference_today: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest all raw JSON/JSONL files into normalized DuckDB tables."""
    settings = get_settings()
    d_root = (dataset_root or settings.dataset_path).resolve()
    today_str = reference_today or settings.REFERENCE_TODAY

    t0 = time.time()
    con = get_db_connection(db_path=db_path)

    try:
        # Initialize Phase 2 tables
        init_database_schema(con, drop_existing=(mode == "rebuild"), phases=[2])

        fleet_dir = d_root / "fleet"
        assets_pattern = str(d_root / "assets" / "*" / "*.json*")
        areas_file = str(fleet_dir / "areas.json")
        users_file = str(fleet_dir / "users.json")
        meta_pattern = str(d_root / "assets" / "*" / "metadata.json")
        insp_pattern = str(d_root / "assets" / "*" / "inspections.jsonl")
        maint_pattern = str(d_root / "assets" / "*" / "maintenance.jsonl")
        reg_pattern = str(d_root / "assets" / "*" / "regulatory-events.jsonl")
        ctx_pattern = str(d_root / "assets" / "*" / "context.jsonl")

        # 1. areas
        con.execute(f"""
        INSERT OR REPLACE INTO areas
        SELECT
            a.area_id,
            a.name AS area_name,
            a.team_id,
            CAST(a.center.lat AS DOUBLE) AS center_lat,
            CAST(a.center.lon AS DOUBLE) AS center_lon,
            len(a.asset_ids) AS expected_well_count
        FROM read_json_auto('{areas_file}') f,
             UNNEST(f.areas) AS t(a)
        """)

        # 2. teams
        con.execute(f"""
        INSERT OR REPLACE INTO teams
        SELECT
            t.team_id,
            t.name AS team_name,
            t.lead_user_id
        FROM read_json_auto('{areas_file}') f,
             UNNEST(f.teams) AS t(t)
        """)

        # 3. users
        con.execute(f"""
        INSERT OR REPLACE INTO users
        SELECT
            u.user_id,
            u.name AS user_name,
            u.role,
            u.team_id
        FROM read_json_auto('{users_file}') f,
             UNNEST(f.users) AS t(u)
        """)

        # 4. wells
        meta_cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_json_auto('{meta_pattern}', union_by_name=true)").fetchall()]
        status_col = "status" if "status" in meta_cols else "NULL AS status"
        decom_col = "CAST(decommissioned_on AS DATE) AS decommissioned_on" if "decommissioned_on" in meta_cols else "NULL AS decommissioned_on"
        con.execute(f"""
        INSERT OR REPLACE INTO wells
        SELECT
            asset_id,
            name AS well_name,
            asset_category,
            well_type,
            area_id,
            team_id,
            in_charge_user_id,
            CAST(location.lat AS DOUBLE) AS lat,
            CAST(location.lon AS DOUBLE) AS lon,
            CAST(installed_on AS DATE) AS installed_on,
            recorded_status,
            last_inspection.inspection_id AS meta_last_inspection_id,
            CAST(last_inspection.inspected_at AS TIMESTAMP) AS meta_last_inspected_at,
            last_inspection.inspector_user_id AS meta_last_inspector_user_id,
            {status_col},
            {decom_col}
        FROM read_json_auto('{meta_pattern}', union_by_name=true)
        """)

        # 5. well_equipment
        con.execute(f"""
        INSERT OR REPLACE INTO well_equipment
        SELECT
            eq.equipment_id,
            m.asset_id,
            eq.kind AS equipment_kind,
            eq.model
        FROM read_json_auto('{meta_pattern}', union_by_name=true) m,
             UNNEST(m.equipment) AS t(eq)
        """)

        # 6. raw_inspections
        con.execute(f"""
        INSERT OR REPLACE INTO raw_inspections
        SELECT
            inspection_id,
            asset_id,
            CAST(inspected_at AS TIMESTAMP) AS inspected_at,
            CAST(inspected_at AS DATE) AS inspection_date,
            inspector_user_id,
            method,
            ambient_temp_c,
            wellhead_temp_c,
            ROUND(wellhead_temp_c - ambient_temp_c, 4) AS raw_temp_delta_c,
            spill_detected,
            spill_area_pct,
            spill_est_volume_bbl,
            TO_JSON(evidence_images) AS evidence_images_json,
            notes AS inspector_notes
        FROM read_json_auto('{insp_pattern}', union_by_name=true)
        """)

        # 7. raw_maintenance
        con.execute(f"""
        INSERT OR REPLACE INTO raw_maintenance
        SELECT
            maintenance_id,
            asset_id,
            CAST(started_at AS TIMESTAMP) AS started_at,
            CAST(started_at AS DATE) AS started_date,
            CAST(completed_at AS TIMESTAMP) AS completed_at,
            CAST(completed_at AS DATE) AS completed_date,
            CASE 
                WHEN completed_at IS NULL OR CAST(completed_at AS DATE) >= DATE '{today_str}' THEN TRUE 
                ELSE FALSE 
            END AS is_open_as_of_today,
            maintenance_type,
            equipment_kind,
            issue,
            action_taken,
            technician_user_id,
            contractor,
            downtime_hours,
            CAST(cost_usd.labor AS DOUBLE) AS cost_labor_usd,
            CAST(cost_usd.parts AS DOUBLE) AS cost_parts_usd,
            CAST(cost_usd.total AS DOUBLE) AS cost_total_usd,
            triggered_by_inspection_id,
            report_file,
            CASE 
                WHEN report_file IS NOT NULL THEN CONCAT('assets/', asset_id, '/', report_file)
                ELSE NULL
            END AS resolved_report_path
        FROM read_json_auto('{maint_pattern}', union_by_name=true)
        """)

        # 8. raw_regulatory_events
        con.execute(f"""
        INSERT OR REPLACE INTO raw_regulatory_events
        SELECT
            event_id,
            asset_id,
            CAST(date AS DATE) AS event_date,
            agency,
            event_type,
            protocol_id,
            related_inspection_id,
            CAST(hours_to_report AS DOUBLE) AS hours_to_report,
            detail,
            CAST(fine_usd AS DOUBLE) AS fine_usd,
            status
        FROM read_json_auto('{reg_pattern}', union_by_name=true)
        """)

        # 9. raw_context_notes
        ctx_cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_json_auto('{ctx_pattern}', union_by_name=true)").fetchall()]
        field_col = "field" if "field" in ctx_cols else "NULL AS field"
        orig_val_col = "CAST(original_value AS DOUBLE) AS original_value" if "original_value" in ctx_cols else "NULL AS original_value"
        corr_val_col = "CAST(corrected_value AS DOUBLE) AS corrected_value" if "corrected_value" in ctx_cols else "NULL AS corrected_value"
        con.execute(f"""
        INSERT OR REPLACE INTO raw_context_notes
        SELECT
            note_id,
            asset_id,
            CAST(created_at AS TIMESTAMP) AS created_at,
            CAST(created_at AS DATE) AS created_date,
            author_user_id,
            note_type,
            inspection_id,
            text AS note_text,
            CAST(valid_from AS DATE) AS valid_from,
            CAST(valid_to AS DATE) AS valid_to,
            {field_col},
            {orig_val_col},
            {corr_val_col}
        FROM read_json_auto('{ctx_pattern}', union_by_name=true)
        """)

        # Calculate row counts
        counts = {}
        for tbl in [
            "areas",
            "teams",
            "users",
            "wells",
            "well_equipment",
            "raw_inspections",
            "raw_maintenance",
            "raw_regulatory_events",
            "raw_context_notes",
        ]:
            counts[tbl] = con.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]

        duration_ms = (time.time() - t0) * 1000.0

        # Record manifest
        manifest_id = f"MAN-{uuid.uuid4().hex[:8]}"
        con.execute(
            """
            INSERT INTO ingestion_manifest VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest_id,
                str(d_root),
                datetime.now(timezone.utc).isoformat(),
                today_str,
                "phase2_raw_ingestion",
                json.dumps(counts),
                duration_ms,
            ),
        )

        return {
            "status": "success",
            "mode": mode,
            "duration_ms": duration_ms,
            "dataset_root": str(d_root),
            "counts": counts,
        }
    finally:
        con.close()


if __name__ == "__main__":
    res = ingest_raw_data()
    print("Ingestion result:", res)
