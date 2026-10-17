"""Phase 11 Verification Suite: Scoped Runtime Feedback & Live Override Engine.

Tests:
  11.1: Raw sensor temp override inserts row in corrections_ledger targeting INS-0164-0205, keeping old=24.0.
  11.2: v_well_current_status for WELL-0164 shows effective temp=41.0, delta=21.1, producing=True, conflict=True.
  11.3: Non-producing wells in Northeast Block 8 reduced from 4 to 3 (WELL-0170, WELL-0172, WELL-0175).
  11.4: Spill volume override inserts row targeting INS-0151-0201, keeping old=4.5.
  11.5: Cascading SOP audit on INS-0151-0201 evaluates SR-01, SR-02 (6.4h), outdated class, SR-03 due 2026-11-23.
  11.6: Northeast Block 8 90-day reportable spills returns exclusively WELL-0151.
  11.7: Baseline Northeast Block 7 pump_jack RCAs returns exclusively 3 wells (WELL-0108, WELL-0121, WELL-0138).
  11.8: Rule override updates rules_registry scoped strictly to T350 and pump_jack.
  11.9: Post-override Northeast Block 7 pump_jack RCAs returns 4 wells (+WELL-0120, excluding WELL-0102).
  11.10: reset_runtime_state cleanly restores baseline state in < 50ms.
"""

import time
import pytest
import duckdb

from backend.db.connection import get_db_connection
from backend.feedback.override_engine import (
    apply_raw_sensor_override,
    apply_spill_volume_override,
    evaluate_spill_override_cascade,
    apply_well_type_rule_override,
    get_non_producing_wells_with_override_context,
    reset_runtime_state,
)


@pytest.fixture(autouse=True)
def clean_runtime_state():
    """Ensure baseline state before and after each test."""
    con = get_db_connection()
    reset_runtime_state(con)
    yield
    reset_runtime_state(con)


def test_11_1_raw_temp_override_persists_old_and_new():
    """Checkpoint 11.1: Q12 temperature override persists old=24.0, new=41.0 on INS-0164-0205."""
    con = get_db_connection()
    result = apply_raw_sensor_override(
        asset_id="WELL-0164",
        inspection_date_or_id="2026-10-15",
        target_field="wellhead_temp_c",
        new_value=41.0,
        author_name="Michael Turner",
        author_user_id="U-201",
        reason="The handheld thermal gun used in that inspection was faulty; the field crew re-measured the wellhead at 41.0 °C.",
        con=con,
    )

    assert result["asset_id"] == "WELL-0164"
    assert result["inspection_id"] == "INS-0164-0205"
    assert result["old_numeric_value"] == 24.0
    assert result["new_numeric_value"] == 41.0
    assert result["author_name"] == "Michael Turner"

    # Verify directly in DuckDB corrections_ledger
    row = con.execute(
        """
        SELECT old_numeric_value, new_numeric_value, author_name, is_active, source_origin
        FROM corrections_ledger
        WHERE inspection_id = 'INS-0164-0205' AND target_field = 'wellhead_temp_c' AND is_active = TRUE
        """
    ).fetchone()
    assert row is not None
    assert row[0] == 24.0
    assert row[1] == 41.0
    assert row[2] == "Michael Turner"
    assert row[3] is True
    assert row[4] == "runtime_user_chat"


def test_11_2_v_well_current_status_reflects_q12_override():
    """Checkpoint 11.2: Status shows 41.0 °C, 21.1 °C delta, is_producing=True, conflict=True."""
    con = get_db_connection()
    apply_raw_sensor_override(
        asset_id="WELL-0164",
        inspection_date_or_id="2026-10-15",
        target_field="wellhead_temp_c",
        new_value=41.0,
        author_name="Michael Turner",
        reason="Faulty gun re-measured 41.0 C",
        con=con,
    )

    status = con.execute(
        """
        SELECT effective_wellhead_temp_c, effective_temp_delta_c, is_producing, downtime_days,
               has_inspector_note_conflict, conflicting_inspector_note
        FROM v_well_current_status
        WHERE asset_id = 'WELL-0164'
        """
    ).fetchone()

    assert status is not None
    assert status[0] == 41.0
    assert round(status[1], 1) == 21.1
    assert status[2] is True
    assert status[3] == 0
    assert status[4] is True
    assert "Pump jack not moving" in status[5]


def test_11_3_q2_table_reduced_from_4_to_3_wells():
    """Checkpoint 11.3: Non-producing wells in Block 8 returns 3 wells (170, 172, 175) and explains 164."""
    con = get_db_connection()
    apply_raw_sensor_override(
        asset_id="WELL-0164",
        inspection_date_or_id="2026-10-15",
        target_field="wellhead_temp_c",
        new_value=41.0,
        author_name="Michael Turner",
        reason="Remeasured 41.0 C",
        con=con,
    )

    res = get_non_producing_wells_with_override_context("Northeast Block 8", con=con)
    non_producing_ids = [w["asset_id"] for w in res["non_producing_wells"]]
    assert non_producing_ids == ["WELL-0170", "WELL-0172", "WELL-0175"]
    assert len(non_producing_ids) == 3

    overridden_ids = [w["asset_id"] for w in res["overridden_producing_wells"]]
    assert "WELL-0164" in overridden_ids
    assert res["overridden_producing_wells"][0]["effective_wellhead_temp_c"] == 41.0


def test_11_4_spill_volume_override_persists_old_and_new():
    """Checkpoint 11.4: Q13 spill volume override persists old=4.5, new=5.4 on INS-0151-0201."""
    con = get_db_connection()
    result = apply_spill_volume_override(
        asset_id="WELL-0151",
        inspection_date_or_id="2026-09-24",
        new_volume_bbl=5.4,
        author_name="Michael Turner",
        author_user_id="U-201",
        reason="Field crew measured 5.4 bbl (correcting AI estimate of 4.5 bbl).",
        con=con,
    )

    assert result["asset_id"] == "WELL-0151"
    assert result["inspection_id"] == "INS-0151-0201"
    assert result["old_numeric_value"] == 4.5
    assert result["new_numeric_value"] == 5.4

    row = con.execute(
        """
        SELECT old_numeric_value, new_numeric_value, author_name, is_active
        FROM corrections_ledger
        WHERE inspection_id = 'INS-0151-0201' AND is_active = TRUE
        """
    ).fetchone()
    assert row is not None
    assert row[0] == 4.5
    assert row[1] == 5.4


def test_11_5_cascading_sop_audit_evaluates_all_4_impacts():
    """Checkpoint 11.5: Cascading audit evaluates SR-01, outdated class, SR-02 (6.4h), SR-03 due 2026-11-23."""
    con = get_db_connection()
    apply_spill_volume_override(
        asset_id="WELL-0151",
        inspection_date_or_id="2026-09-24",
        new_volume_bbl=5.4,
        author_name="Michael Turner",
        con=con,
    )

    cascade = evaluate_spill_override_cascade("INS-0151-0201", con=con)
    assert cascade["is_reportable_spill"] is True
    assert cascade["is_sr01_breach"] is True
    assert cascade["is_report_class_outdated"] is True
    assert cascade["reported_spill_class"] == "moderate"
    assert cascade["effective_spill_class"] == "reportable"
    assert cascade["is_sr02_breach"] is True
    assert cascade["containment_hours"] == 6.4
    assert cascade["sr02_limit_hours"] == 4.0
    assert str(cascade["sr03_cleanup_due_date"])[:10] == "2026-11-23"
    assert len(cascade["impact_summary"]) == 4


def test_11_6_spill_compliance_view_filtered_returns_well_0151():
    """Checkpoint 11.6: Querying v_spill_compliance_audit in Block 8 last 90 days returns exclusively WELL-0151."""
    con = get_db_connection()
    apply_spill_volume_override(
        asset_id="WELL-0151",
        inspection_date_or_id="2026-09-24",
        new_volume_bbl=5.4,
        author_name="Michael Turner",
        con=con,
    )

    rows = con.execute(
        """
        SELECT asset_id, effective_spill_volume_bbl, is_reportable_spill, is_sr01_breach
        FROM v_spill_compliance_audit
        WHERE area_name = 'Northeast Block 8'
          AND is_reportable_spill = TRUE
          AND inspection_date >= DATE '2026-10-17' - INTERVAL 90 DAY
        ORDER BY asset_id
        """
    ).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "WELL-0151"
    assert rows[0][1] == 5.4
    assert rows[0][2] is True
    assert rows[0][3] is True


def test_11_7_baseline_pump_jack_rca_in_block_7():
    """Checkpoint 11.7: Before Q14 override, Block 7 pump_jack RCAs returns exclusively 3 wells."""
    con = get_db_connection()
    rows = con.execute(
        """
        SELECT asset_id, well_name, corrective_repairs_12m, required_rca_threshold
        FROM v_equipment_rca_tracker
        WHERE area_name = 'Northeast Block 7'
          AND equipment_kind = 'pump_jack'
          AND needs_rca = TRUE
        ORDER BY asset_id
        """
    ).fetchall()

    wells = [r[0] for r in rows]
    assert wells == ["WELL-0108", "WELL-0121", "WELL-0138"]
    assert len(wells) == 3


def test_11_8_rule_override_updates_registry_scoped_to_t350():
    """Checkpoint 11.8: Michael Turner's rule override updates rules_registry scoped strictly to T350."""
    con = get_db_connection()
    override = apply_well_type_rule_override(
        well_type="T350",
        equipment_kind="pump_jack",
        new_threshold=2.0,
        author_name="Michael Turner",
        author_user_id="U-201",
        reason="Note for all T350 wells: our team now wants a pump jack root-cause analysis after 2 repairs, not 3.",
        con=con,
    )

    assert override["scope_value"] == "T350"
    assert override["equipment_kind"] == "pump_jack"
    assert override["threshold_value"] == 2.0
    assert override["is_user_override"] is True

    # Check database
    rule_row = con.execute(
        """
        SELECT scope_value, equipment_kind, threshold_value, is_user_override, overridden_by_user_name
        FROM rules_registry
        WHERE rule_code = 'CORRECTIVE_REPAIRS_RCA_THRESHOLD' AND is_user_override = TRUE AND is_active = TRUE
        """
    ).fetchone()
    assert rule_row is not None
    assert rule_row[0] == "T350"
    assert rule_row[1] == "pump_jack"
    assert rule_row[2] == 2.0
    assert rule_row[3] is True
    assert rule_row[4] == "Michael Turner"


def test_11_9_post_override_rca_tracker_includes_120_excludes_102():
    """Checkpoint 11.9: Block 7 pump_jack RCAs returns 4 wells: 108, 120 (T350), 121, 138; excludes 102 (T200)."""
    con = get_db_connection()
    apply_well_type_rule_override(
        well_type="T350",
        equipment_kind="pump_jack",
        new_threshold=2.0,
        author_name="Michael Turner",
        reason="T350 pump jack 2 repairs",
        con=con,
    )

    rows = con.execute(
        """
        SELECT asset_id, well_type, corrective_repairs_12m, required_rca_threshold, needs_rca
        FROM v_equipment_rca_tracker
        WHERE area_name = 'Northeast Block 7'
          AND equipment_kind = 'pump_jack'
          AND needs_rca = TRUE
        ORDER BY asset_id
        """
    ).fetchall()

    wells = [r[0] for r in rows]
    assert wells == ["WELL-0108", "WELL-0120", "WELL-0121", "WELL-0138"]
    assert "WELL-0102" not in wells  # T200 well with 2 repairs must remain needs_rca = False

    well_102 = con.execute(
        """
        SELECT corrective_repairs_12m, required_rca_threshold, needs_rca
        FROM v_equipment_rca_tracker
        WHERE asset_id = 'WELL-0102' AND equipment_kind = 'pump_jack'
        """
    ).fetchone()
    assert well_102 is not None
    assert well_102[0] == 2
    assert well_102[1] == 3  # T200 manual baseline threshold unchanged!
    assert well_102[2] is False


def test_11_10_reset_runtime_state_speed_and_cleanliness():
    """Checkpoint 11.10: reset_runtime_state removes all overrides and restores baseline in < 50ms."""
    con = get_db_connection()
    # Add overrides across all three types
    apply_raw_sensor_override("WELL-0164", "2026-10-15", "wellhead_temp_c", 41.0, "Michael Turner", con=con)
    apply_spill_volume_override("WELL-0151", "2026-09-24", 5.4, "Michael Turner", con=con)
    apply_well_type_rule_override("T350", "pump_jack", 2.0, "Michael Turner", con=con)

    start_t = time.perf_counter()
    res = reset_runtime_state(con)
    duration_ms = (time.perf_counter() - start_t) * 1000.0

    assert duration_ms < 50.0, f"Reset took {duration_ms:.2f}ms, expected < 50ms"

    # Verify DuckDB tables have 0 active user overrides
    corr_count = con.execute(
        "SELECT COUNT(*) FROM corrections_ledger WHERE source_origin = 'runtime_user_chat'"
    ).fetchone()[0]
    rules_count = con.execute(
        "SELECT COUNT(*) FROM rules_registry WHERE is_user_override = TRUE"
    ).fetchone()[0]

    assert corr_count == 0
    assert rules_count == 0

    # Verify WELL-0164 is back to non-producing
    status = con.execute(
        "SELECT is_producing FROM v_well_current_status WHERE asset_id = 'WELL-0164'"
    ).fetchone()[0]
    assert status is False
