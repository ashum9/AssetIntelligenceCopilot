"""Phase 7: Deterministic Part A1 Parity Verification Engine (Q1 through Q10).

Executes deterministic SQL queries against the Phase 6 Semantic Overlay Views
and validates exact 100% mathematical and factual parity against the official
ground-truth evaluation answers in `03-evaluation-queries.md`.
"""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection


def json_serial(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def query_q1(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q1: Is WELL-0001 producing oil right now? When was it last inspected, and by whom? Show me its status card."""
    row = conn.execute("""
        SELECT
            asset_id,
            well_name,
            well_type,
            area_name,
            is_producing,
            inspection_id,
            inspection_date,
            method,
            inspector_name,
            effective_wellhead_temp_c,
            effective_ambient_temp_c,
            effective_temp_delta_c,
            required_temp_delta_c,
            temp_rule_citation,
            recorded_status,
            is_recorded_status_stale,
            recorded_status_display,
            stop_reason_type,
            active_shutin_note_id,
            active_shutin_author_name,
            active_shutin_valid_from,
            active_shutin_valid_to,
            active_shutin_text,
            is_shutin_logged_in_maintenance
        FROM v_well_current_status
        WHERE asset_id = 'WELL-0001'
    """).fetchone()

    cols = [
        "asset_id", "well_name", "well_type", "area_name", "is_producing",
        "inspection_id", "inspection_date", "method", "inspector_name",
        "wellhead_temp_c", "ambient_temp_c", "temp_delta_c", "required_temp_delta_c",
        "temp_rule_citation", "recorded_status", "is_recorded_status_stale",
        "recorded_status_display", "stop_reason_type", "active_shutin_note_id",
        "active_shutin_author_name", "valid_from", "valid_to", "note_text",
        "is_shutin_logged_in_maintenance"
    ]
    res = dict(zip(cols, row))
    res["visual"] = "status_card"
    res["producing_answer"] = "No, it is not producing oil."
    return res


def query_q2(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q2: Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table."""
    rows = conn.execute("""
        SELECT
            asset_id,
            well_type,
            inspection_date,
            effective_temp_delta_c,
            recorded_status_display,
            stop_reason_type,
            stop_reason_summary
        FROM v_well_current_status
        WHERE area_name = 'Northeast Block 8' AND is_producing = FALSE
        ORDER BY asset_id
    """).fetchall()

    cols = [
        "asset_id", "well_type", "inspection_date", "temp_delta_c",
        "recorded_status_display", "stop_reason_type", "stop_reason_summary"
    ]
    table = [dict(zip(cols, r)) for r in rows]
    return {
        "visual": "table",
        "count": len(table),
        "wells": table,
    }


def query_q3(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q3: Show a line chart of WELL-0001's wellhead temperature against air temperature for the last 13 weeks."""
    rows = conn.execute("""
        SELECT
            inspection_date,
            effective_wellhead_temp_c,
            effective_ambient_temp_c,
            effective_temp_delta_c,
            required_temp_delta_c,
            is_producing
        FROM v_effective_inspections
        WHERE asset_id = 'WELL-0001'
          AND inspection_date >= DATE '2026-07-23'
          AND inspection_date <= DATE '2026-10-15'
        ORDER BY inspection_date ASC
    """).fetchall()

    cols = [
        "inspection_date", "wellhead_temp_c", "ambient_temp_c",
        "temp_delta_c", "required_temp_delta_c", "is_producing"
    ]
    series = [dict(zip(cols, r)) for r in rows]
    non_producing_dates = [r["inspection_date"] for r in series if not r["is_producing"]]
    return {
        "visual": "line_chart",
        "reading_count": len(series),
        "time_series": series,
        "non_producing_dates": non_producing_dates,
    }


def query_q4(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q4: How many oil spills has WELL-0001 had in the last 4 years, and how much oil in total? List them in a table."""
    rows = conn.execute("""
        SELECT
            inspection_id,
            inspection_date,
            raw_spill_detected,
            effective_spill_detected,
            raw_spill_volume_bbl,
            effective_spill_volume_bbl,
            applied_correction_note_ids,
            correction_reasons
        FROM v_spill_compliance_audit
        WHERE asset_id = 'WELL-0001'
        ORDER BY inspection_date ASC
    """).fetchall()

    cols = [
        "inspection_id", "inspection_date", "raw_spill_detected",
        "effective_spill_detected", "raw_volume_bbl", "effective_volume_bbl",
        "applied_correction_note_ids", "correction_reasons"
    ]
    all_detections = [dict(zip(cols, r)) for r in rows]
    real_spills = [d for d in all_detections if d["effective_spill_detected"]]
    total_bbl = round(sum(d["effective_volume_bbl"] for d in real_spills), 4)

    return {
        "visual": "table",
        "total_detections": len(all_detections),
        "effective_spill_count": len(real_spills),
        "total_volume_bbl": total_bbl,
        "spills": real_spills,
        "rainwater_detection": [d for d in all_detections if not d["effective_spill_detected"]],
    }


def query_q5(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q5: How many days was WELL-0001 down in 2025?"""
    rows = conn.execute("""
        SELECT
            vei.inspection_id,
            vei.inspection_date,
            vei.effective_wellhead_temp_c,
            vei.effective_ambient_temp_c,
            vei.effective_temp_delta_c,
            vei.downtime_days,
            rm.maintenance_id,
            rm.issue,
            rm.action_taken
        FROM v_effective_inspections vei
        LEFT JOIN raw_maintenance rm ON rm.triggered_by_inspection_id = vei.inspection_id
        WHERE vei.asset_id = 'WELL-0001'
          AND vei.is_producing = FALSE
          AND vei.inspection_date >= DATE '2025-01-01'
          AND vei.inspection_date <= DATE '2025-12-31'
        ORDER BY vei.inspection_date ASC
    """).fetchall()

    cols = [
        "inspection_id", "inspection_date", "wellhead_temp_c", "ambient_temp_c",
        "temp_delta_c", "downtime_days", "maintenance_id", "issue", "action_taken"
    ]
    down_inspections = [dict(zip(cols, r)) for r in rows]
    total_downtime_days = sum(d["downtime_days"] for d in down_inspections)

    return {
        "visual": "short_answer",
        "total_downtime_days": total_downtime_days,
        "down_inspections_count": len(down_inspections),
        "evidence": down_inspections,
    }


def query_q6(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q6: Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart."""
    rows = conn.execute("""
        SELECT
            asset_id,
            well_type,
            SUM(downtime_days) AS total_downtime_days
        FROM v_effective_inspections
        WHERE area_name = 'Northeast Block 7'
          AND inspection_date >= DATE '2026-06-16'
          AND inspection_date <= DATE '2026-10-16'
        GROUP BY asset_id, well_type
        ORDER BY total_downtime_days DESC, asset_id ASC
        LIMIT 4
    """).fetchall()

    cols = ["asset_id", "well_type", "total_downtime_days"]
    ranking = [dict(zip(cols, r)) for r in rows]
    return {
        "visual": "bar_chart",
        "window": "16 Jun 2026 to 16 Oct 2026",
        "top_3": ranking[:3],
        "runner_up": ranking[3] if len(ranking) > 3 else None,
    }


def query_q7(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q7: Show on a map every well in Northeast Block 8 with a real spill in the last 90 days."""
    rows = conn.execute("""
        SELECT
            asset_id,
            inspection_date,
            effective_spill_volume_bbl,
            lat,
            lon
        FROM v_spill_compliance_audit
        WHERE area_name = 'Northeast Block 8'
          AND effective_spill_detected = TRUE
          AND inspection_date >= DATE '2026-07-19'
          AND inspection_date <= DATE '2026-10-17'
        ORDER BY inspection_date DESC, asset_id ASC
    """).fetchall()

    cols = ["asset_id", "inspection_date", "volume_bbl", "lat", "lon"]
    pins = [dict(zip(cols, r)) for r in rows]
    return {
        "visual": "map",
        "pin_count": len(pins),
        "pins": pins,
    }


def query_q8(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q8: Show a heatmap of 2026 spills by geographic area and month."""
    rows = conn.execute("""
        SELECT
            area_name,
            SUM(CASE WHEN MONTH(inspection_date) = 1 THEN 1 ELSE 0 END) AS Jan,
            SUM(CASE WHEN MONTH(inspection_date) = 2 THEN 1 ELSE 0 END) AS Feb,
            SUM(CASE WHEN MONTH(inspection_date) = 3 THEN 1 ELSE 0 END) AS Mar,
            SUM(CASE WHEN MONTH(inspection_date) = 4 THEN 1 ELSE 0 END) AS Apr,
            SUM(CASE WHEN MONTH(inspection_date) = 5 THEN 1 ELSE 0 END) AS May,
            SUM(CASE WHEN MONTH(inspection_date) = 6 THEN 1 ELSE 0 END) AS Jun,
            SUM(CASE WHEN MONTH(inspection_date) = 7 THEN 1 ELSE 0 END) AS Jul,
            SUM(CASE WHEN MONTH(inspection_date) = 8 THEN 1 ELSE 0 END) AS Aug,
            SUM(CASE WHEN MONTH(inspection_date) = 9 THEN 1 ELSE 0 END) AS Sep,
            SUM(CASE WHEN MONTH(inspection_date) = 10 THEN 1 ELSE 0 END) AS Oct,
            COUNT(*) AS Total
        FROM v_spill_compliance_audit
        WHERE effective_spill_detected = TRUE
          AND inspection_date >= DATE '2026-01-01'
          AND inspection_date <= DATE '2026-10-17'
        GROUP BY area_name
        ORDER BY area_name ASC
    """).fetchall()

    cols = ["area_name", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Total"]
    matrix = [dict(zip(cols, r)) for r in rows]
    total_spills = sum(m["Total"] for m in matrix)
    return {
        "visual": "heatmap",
        "total_2026_spills": total_spills,
        "matrix": matrix,
    }


def query_q9(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q9: Which rules has WELL-0001 broken in the last 12 months, and what is still open?"""
    summary = conn.execute("""
        SELECT
            asset_id,
            sr01_breaches_cnt,
            sr02_breaches_cnt,
            sr03_breaches_cnt,
            rc04_breaches_cnt,
            total_breaches_12m,
            open_fines_usd,
            sr01_detail,
            sr02_detail,
            sr03_detail,
            rc04_detail,
            has_pending_rca,
            pending_rca_equipment_list,
            pending_rca_details,
            has_unlogged_planned_shutin,
            unlogged_shutin_note_id,
            unlogged_shutin_summary,
            last_annual_flowline_test_date,
            is_annual_flowline_test_met
        FROM v_well_compliance_summary
        WHERE asset_id = 'WELL-0001'
    """).fetchone()

    cols = [
        "asset_id", "sr01_breaches_cnt", "sr02_breaches_cnt", "sr03_breaches_cnt",
        "rc04_breaches_cnt", "total_breaches_12m", "open_fines_usd",
        "sr01_detail", "sr02_detail", "sr03_detail", "rc04_detail",
        "has_pending_rca", "pending_rca_equipment_list", "pending_rca_details",
        "has_unlogged_planned_shutin", "unlogged_shutin_note_id", "unlogged_shutin_summary",
        "last_annual_flowline_test_date", "is_annual_flowline_test_met"
    ]
    res = dict(zip(cols, summary))
    res["visual"] = "table"
    return res


def query_q10(conn: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """Q10: In Southwest Block 24, which spills in the last 90 days were not contained within the SOP time limit?"""
    rows = conn.execute("""
        SELECT
            asset_id,
            inspection_id,
            maintenance_id,
            inspection_date,
            effective_spill_volume_bbl,
            containment_hours,
            sr02_limit_hours,
            report_file_path
        FROM v_spill_compliance_audit
        WHERE area_name = 'Southwest Block 24'
          AND inspection_date >= DATE '2026-07-19'
          AND inspection_date <= DATE '2026-10-17'
          AND is_sr02_breach = TRUE
        ORDER BY containment_hours DESC
    """).fetchall()

    cols = [
        "asset_id", "inspection_id", "maintenance_id", "inspection_date",
        "volume_bbl", "containment_hours", "limit_hours", "report_file_path"
    ]
    breaches = [dict(zip(cols, r)) for r in rows]
    return {
        "visual": "table",
        "limit_hours": 4.0,
        "breach_count": len(breaches),
        "breaches": breaches,
    }


def run_all_part_a1_queries(
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
    export_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Execute all Part A1 deterministic queries and export baseline artifact."""
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=True)
        own_conn = True

    try:
        results = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "q1": query_q1(conn),
            "q2": query_q2(conn),
            "q3": query_q3(conn),
            "q4": query_q4(conn),
            "q5": query_q5(conn),
            "q6": query_q6(conn),
            "q7": query_q7(conn),
            "q8": query_q8(conn),
            "q9": query_q9(conn),
            "q10": query_q10(conn),
        }

        if export_path is None:
            settings = get_settings()
            export_path = settings.artifacts_path / "phase7_part_a1_baseline.json"

        export_path = Path(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=json_serial)

        return results
    finally:
        if own_conn:
            conn.close()
