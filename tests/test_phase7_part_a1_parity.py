"""Phase 7 Verification Suite: Part A1 Ground-Truth Parity Gate (Q1 through Q10).

Verifies 100% mathematical, factual, and visual parity against the official evaluation
answers in `03-evaluation-queries.md`.
"""

import json
from pathlib import Path
import pytest
import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.evaluation.part_a1_queries import (
    query_q1,
    query_q2,
    query_q3,
    query_q4,
    query_q5,
    query_q6,
    query_q7,
    query_q8,
    query_q9,
    query_q10,
    run_all_part_a1_queries,
)


@pytest.fixture(scope="module")
def db_conn():
    settings = get_settings()
    db_path = settings.artifacts_path / "copilot.duckdb"
    conn = get_db_connection(db_path, read_only=True)
    yield conn
    conn.close()


def test_q1_parity(db_conn):
    """Q1: WELL-0001 status card verification."""
    res = query_q1(db_conn)
    assert res["visual"] == "status_card"
    assert res["asset_id"] == "WELL-0001"
    assert res["is_producing"] is False
    assert res["inspection_id"] == "INS-0001-0203"
    assert str(res["inspection_date"]) == "2026-10-15"
    assert res["method"] == "drone"
    assert res["inspector_name"] == "Ryan Brooks"
    assert res["temp_delta_c"] == 3.2
    assert res["required_temp_delta_c"] == 15.0
    assert "T200" in res["temp_rule_citation"]
    assert res["active_shutin_note_id"] == "CTX-0001-003"
    assert res["active_shutin_author_name"] == "Jake Morales"
    assert str(res["valid_from"]) == "2026-10-07"
    assert str(res["valid_to"]) == "2026-10-20"
    assert res["is_shutin_logged_in_maintenance"] is False
    assert res["recorded_status"] == "active"
    assert res["is_recorded_status_stale"] is True
    assert res["recorded_status_display"] == "active (out of date)"


def test_q2_parity(db_conn):
    """Q2: Northeast Block 8 non-producing wells table verification."""
    res = query_q2(db_conn)
    assert res["visual"] == "table"
    assert res["count"] == 4
    wells = {w["asset_id"]: w for w in res["wells"]}
    assert set(wells.keys()) == {"WELL-0164", "WELL-0170", "WELL-0172", "WELL-0175"}

    # All T200, inspected 15 Oct 2026
    for w in wells.values():
        assert w["well_type"] == "T200"
        assert str(w["inspection_date"]) == "2026-10-15"

    assert wells["WELL-0164"]["temp_delta_c"] == 4.1
    assert wells["WELL-0164"]["recorded_status_display"] == "active (out of date)"
    assert wells["WELL-0164"]["stop_reason_type"] == "NO_RECORDED_REASON"
    assert 'Pump jack not moving.' in wells["WELL-0164"]["stop_reason_summary"]

    assert wells["WELL-0170"]["temp_delta_c"] == 2.9
    assert wells["WELL-0170"]["recorded_status_display"] == "down"
    assert wells["WELL-0170"]["stop_reason_type"] == "OPEN_REPAIR"
    assert "MNT-0170-031" in wells["WELL-0170"]["stop_reason_summary"]

    assert wells["WELL-0172"]["temp_delta_c"] == 5.7
    assert wells["WELL-0172"]["recorded_status_display"] == "active (out of date)"
    assert wells["WELL-0172"]["stop_reason_type"] == "OPEN_REPAIR"
    assert "MNT-0172-028" in wells["WELL-0172"]["stop_reason_summary"]

    assert wells["WELL-0175"]["temp_delta_c"] == 0.4
    assert wells["WELL-0175"]["recorded_status_display"] == "active (out of date)"
    assert wells["WELL-0175"]["stop_reason_type"] == "NO_RECORDED_REASON"


def test_q3_parity(db_conn):
    """Q3: WELL-0001 13-week temperature line chart."""
    res = query_q3(db_conn)
    assert res["visual"] == "line_chart"
    assert res["reading_count"] == 13
    assert [str(d) for d in res["non_producing_dates"]] == ["2026-10-08", "2026-10-15"]


def test_q4_parity(db_conn):
    """Q4: WELL-0001 4-year spills table verification."""
    res = query_q4(db_conn)
    assert res["visual"] == "table"
    assert res["total_detections"] == 7
    assert res["effective_spill_count"] == 6
    assert res["total_volume_bbl"] == 15.1
    assert len(res["rainwater_detection"]) == 1
    assert res["rainwater_detection"][0]["inspection_id"] == "INS-0001-0070"
    assert "CTX-0001-001" in res["rainwater_detection"][0]["applied_correction_note_ids"]

    spill_dates = [str(s["inspection_date"]) for s in res["spills"]]
    spill_vols = [s["effective_volume_bbl"] for s in res["spills"]]
    assert spill_dates == [
        "2023-03-16",
        "2023-04-27",
        "2023-09-28",
        "2023-10-19",
        "2026-06-11",
        "2026-10-01",
    ]
    assert spill_vols == [0.5, 2.6, 3.3, 0.3, 6.8, 1.6]


def test_q5_parity(db_conn):
    """Q5: WELL-0001 downtime in 2025."""
    res = query_q5(db_conn)
    assert res["total_downtime_days"] == 21
    assert res["down_inspections_count"] == 3
    dates = [str(e["inspection_date"]) for e in res["evidence"]]
    assert dates == ["2025-07-24", "2025-10-16", "2025-10-23"]
    # 24 Jul 2025: delta 8.5C (<15C), repair MNT-0001-021
    assert res["evidence"][0]["temp_delta_c"] == 8.5
    assert res["evidence"][0]["maintenance_id"] == "MNT-0001-021"


def test_q6_parity(db_conn):
    """Q6: Northeast Block 7 top 3 downtime wells bar chart."""
    res = query_q6(db_conn)
    assert res["visual"] == "bar_chart"
    top_3 = res["top_3"]
    assert len(top_3) == 3
    assert top_3[0]["asset_id"] == "WELL-0121"
    assert top_3[0]["well_type"] == "T200"
    assert top_3[0]["total_downtime_days"] == 49

    tied_assets = {top_3[1]["asset_id"], top_3[2]["asset_id"]}
    assert tied_assets == {"WELL-0107", "WELL-0138"}
    assert top_3[1]["total_downtime_days"] == 42
    assert top_3[2]["total_downtime_days"] == 42

    assert res["runner_up"]["asset_id"] == "WELL-0119"
    assert res["runner_up"]["total_downtime_days"] == 28


def test_q7_parity(db_conn):
    """Q7: Northeast Block 8 90-day spills map verification."""
    res = query_q7(db_conn)
    assert res["visual"] == "map"
    assert res["pin_count"] == 4
    pin_wells = {p["asset_id"]: p for p in res["pins"]}
    assert set(pin_wells.keys()) == {"WELL-0151", "WELL-0165", "WELL-0175", "WELL-0186"}

    w151 = pin_wells["WELL-0151"]
    assert str(w151["inspection_date"]) == "2026-09-24"
    assert w151["volume_bbl"] == 4.5
    assert round(w151["lat"], 5) == 32.12246
    assert round(w151["lon"], 5) == -102.18445

    w165 = pin_wells["WELL-0165"]
    assert str(w165["inspection_date"]) == "2026-07-30"
    assert w165["volume_bbl"] == 1.2
    assert round(w165["lat"], 5) == 32.15665
    assert round(w165["lon"], 5) == -102.14522

    w175 = pin_wells["WELL-0175"]
    assert str(w175["inspection_date"]) == "2026-07-30"
    assert w175["volume_bbl"] == 3.9
    assert round(w175["lat"], 5) == 32.18020
    assert round(w175["lon"], 5) == -102.14790

    w186 = pin_wells["WELL-0186"]
    assert str(w186["inspection_date"]) == "2026-07-23"
    assert w186["volume_bbl"] == 0.6
    assert round(w186["lat"], 5) == 32.17552
    assert round(w186["lon"], 5) == -102.17775


def test_q8_parity(db_conn):
    """Q8: 2026 spill heatmap matrix verification."""
    res = query_q8(db_conn)
    assert res["visual"] == "heatmap"
    assert res["total_2026_spills"] == 141
    matrix = {m["area_name"]: m for m in res["matrix"]}

    # Southwest Block 23: [4, 3, 3, 6, 3, 4, 4, 3, 3, 2] -> Total 35
    sw23 = matrix["Southwest Block 23"]
    assert [sw23[k] for k in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]] == [
        4, 3, 3, 6, 3, 4, 4, 3, 3, 2
    ]
    assert sw23["Total"] == 35

    # Southwest Block 24: [7, 4, 5, 6, 5, 5, 3, 1, 5, 2] -> Total 43
    sw24 = matrix["Southwest Block 24"]
    assert [sw24[k] for k in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]] == [
        7, 4, 5, 6, 5, 5, 3, 1, 5, 2
    ]
    assert sw24["Total"] == 43

    # Northeast Block 7: [5, 3, 2, 4, 6, 6, 2, 4, 4, 1] -> Total 37
    ne7 = matrix["Northeast Block 7"]
    assert [ne7[k] for k in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]] == [
        5, 3, 2, 4, 6, 6, 2, 4, 4, 1
    ]
    assert ne7["Total"] == 37

    # Northeast Block 8: [4, 4, 4, 3, 2, 4, 4, 0, 1, 0] -> Total 26
    ne8 = matrix["Northeast Block 8"]
    assert [ne8[k] for k in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]] == [
        4, 4, 4, 3, 2, 4, 4, 0, 1, 0
    ]
    assert ne8["Total"] == 26


def test_q9_parity(db_conn):
    """Q9: WELL-0001 12-month compliance breaches, open actions, and met rules."""
    res = query_q9(db_conn)
    assert res["visual"] == "table"
    assert res["total_breaches_12m"] == 4
    assert res["open_fines_usd"] == 5000.0

    # 4 Breaches
    assert res["sr01_breaches_cnt"] == 1
    assert "41" in res["sr01_detail"]
    assert res["sr02_breaches_cnt"] == 1
    assert "7" in res["sr02_detail"]
    assert res["sr03_breaches_cnt"] == 1
    assert "10 Aug 2026" in res["sr03_detail"]
    assert res["rc04_breaches_cnt"] == 1
    assert "30 Jul 2026" in res["rc04_detail"]

    # 2 Pending actions
    assert res["has_pending_rca"] is True
    assert "flowline" in res["pending_rca_equipment_list"]
    assert "Action required" in res["pending_rca_details"]

    assert res["has_unlogged_planned_shutin"] is True
    assert res["unlogged_shutin_note_id"] == "CTX-0001-003"

    # 1 Met rule
    assert str(res["last_annual_flowline_test_date"]) == "2026-03-07"
    assert res["is_annual_flowline_test_met"] is True


def test_q10_parity(db_conn):
    """Q10: Southwest Block 24 90-day containment breaches."""
    res = query_q10(db_conn)
    assert res["visual"] == "table"
    assert res["limit_hours"] == 4.0
    assert res["breach_count"] == 2

    breach_map = {b["asset_id"]: b for b in res["breaches"]}
    assert set(breach_map.keys()) == {"WELL-0082", "WELL-0100"}

    w82 = breach_map["WELL-0082"]
    assert w82["containment_hours"] == 7.1
    assert w82["inspection_id"] == "INS-0082-0198"
    assert w82["maintenance_id"] == "MNT-0082-028"

    w100 = breach_map["WELL-0100"]
    assert w100["containment_hours"] == 8.1
    assert w100["inspection_id"] == "INS-0100-0196"
    assert w100["maintenance_id"] == "MNT-0100-034"


def test_export_part_a1_baseline_artifact(db_conn):
    """Export artifacts/phase7_part_a1_baseline.json and verify structure."""
    settings = get_settings()
    artifact_path = settings.artifacts_path / "phase7_part_a1_baseline.json"
    results = run_all_part_a1_queries(conn=db_conn, export_path=artifact_path)

    assert artifact_path.exists()
    assert len(results.keys()) >= 11  # timestamp + q1-q10
    with open(artifact_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["q1"]["asset_id"] == "WELL-0001"
    assert data["q4"]["total_volume_bbl"] == 15.1
    assert data["q8"]["total_2026_spills"] == 141
