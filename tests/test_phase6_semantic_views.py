"""Phase 6 Verification Suite: Semantic Overlay SQL Views.

Verifies:
  - Checkpoint 6.1: All 5 views exist and query latency < 200ms
  - Checkpoint 6.2: v_effective_inspections row count exactly matches raw_inspections (39,567)
  - Checkpoint 6.3: v_well_current_status has exactly 200 rows (1 per well)
  - Checkpoint 6.4: WELL-0001 current status reflects planned shut-in, delta T 3.2C, and stale active status
  - Checkpoint 6.5: NE-08 non-producing wells match Q2 exactly (WELL-0164, 0170, 0172, 0175)
  - Checkpoint 6.6: WELL-0001 11 Jun 2026 spill audit flags all 4 breaches (SR-01, SR-02, SR-03, RC-04)
  - Checkpoint 6.7: NE-07 pump jack RCA needs_rca=True baseline matches Q14 (WELL-0108, 0121, 0138)
  - Checkpoint 6.8: NE-07 WELL-0120 and WELL-0102 have 2 repairs and needs_rca=False under baseline
  - Checkpoint 6.9: WELL-0001 flowline has 3 repairs and report flags action required
  - Checkpoint 6.10: WELL-0001 compliance summary surfaces RC-02 flowline test and unlogged shut-in
"""

import time
from pathlib import Path
import pytest
import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.db.views import init_views


@pytest.fixture(scope="module")
def db_conn():
    settings = get_settings()
    db_path = settings.artifacts_path / "copilot.duckdb"
    conn = get_db_connection(db_path, read_only=True)
    yield conn
    conn.close()


def test_checkpoint_6_1_all_views_created_and_fast(db_conn):
    """Checkpoint 6.1: All 5 views exist and execute in under 200ms."""
    views = [
        "v_effective_inspections",
        "v_well_current_status",
        "v_spill_compliance_audit",
        "v_equipment_rca_tracker",
        "v_well_compliance_summary",
    ]
    existing = [
        row[0]
        for row in db_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_type = 'VIEW'"
        ).fetchall()
    ]
    for v in views:
        assert v in existing, f"View {v} not found in database"

    for v in views:
        t0 = time.time()
        db_conn.execute(f"SELECT * FROM {v} LIMIT 50").fetchall()
        latency_ms = (time.time() - t0) * 1000.0
        assert latency_ms < 200.0, f"View {v} exceeded 200ms threshold: {latency_ms:.2f}ms"


def test_checkpoint_6_2_effective_inspections_row_count(db_conn):
    """Checkpoint 6.2: v_effective_inspections row count matches raw_inspections (39,567)."""
    raw_cnt = db_conn.execute("SELECT count(*) FROM raw_inspections").fetchone()[0]
    eff_cnt = db_conn.execute("SELECT count(*) FROM v_effective_inspections").fetchone()[0]
    assert raw_cnt == 39567
    assert eff_cnt == raw_cnt, f"Row count mismatch: {eff_cnt} vs {raw_cnt}"


def test_checkpoint_6_3_well_current_status_one_per_well(db_conn):
    """Checkpoint 6.3: v_well_current_status has exactly 200 rows (1 per well)."""
    status_cnt = db_conn.execute("SELECT count(*) FROM v_well_current_status").fetchone()[0]
    distinct_wells = db_conn.execute(
        "SELECT count(DISTINCT asset_id) FROM v_well_current_status"
    ).fetchone()[0]
    assert status_cnt == 200
    assert distinct_wells == 200


def test_checkpoint_6_4_well0001_current_status(db_conn):
    """Checkpoint 6.4: WELL-0001 current status reflects planned shut-in note CTX-0001-003."""
    row = db_conn.execute("""
        SELECT
            asset_id,
            is_producing,
            effective_temp_delta_c,
            recorded_status,
            is_recorded_status_stale,
            recorded_status_display,
            stop_reason_type,
            active_shutin_note_id,
            is_shutin_logged_in_maintenance
        FROM v_well_current_status
        WHERE asset_id = 'WELL-0001'
    """).fetchone()

    assert row is not None
    aid, is_prod, delta_t, rec_stat, is_stale, rec_disp, stop_type, shutin_id, shutin_logged = row
    assert is_prod is False
    assert delta_t == 3.2
    assert rec_stat == "active"
    assert is_stale is True
    assert rec_disp == "active (out of date)"
    assert stop_type == "PLANNED_SHUTIN_NOTE"
    assert shutin_id == "CTX-0001-003"
    assert shutin_logged is False


def test_checkpoint_6_5_ne08_non_producing_wells_q2(db_conn):
    """Checkpoint 6.5: NE-08 non-producing wells match Q2 exactly (4 wells)."""
    rows = db_conn.execute("""
        SELECT asset_id, effective_temp_delta_c, recorded_status_display, stop_reason_type, stop_reason_summary
        FROM v_well_current_status
        WHERE area_name = 'Northeast Block 8' AND is_producing = FALSE
        ORDER BY asset_id
    """).fetchall()

    assert len(rows) == 4
    well_ids = [r[0] for r in rows]
    assert well_ids == ["WELL-0164", "WELL-0170", "WELL-0172", "WELL-0175"]

    # WELL-0164
    w164 = rows[0]
    assert w164[1] == 4.1
    assert w164[2] == "active (out of date)"
    assert w164[3] == "NO_RECORDED_REASON"
    assert "Pump jack not moving." in w164[4]

    # WELL-0170
    w170 = rows[1]
    assert w170[1] == 2.9
    assert w170[2] == "down"
    assert w170[3] == "OPEN_REPAIR"
    assert "MNT-0170-031" in w170[4]

    # WELL-0172
    w172 = rows[2]
    assert w172[1] == 5.7
    assert w172[2] == "active (out of date)"
    assert w172[3] == "OPEN_REPAIR"
    assert "MNT-0172-028" in w172[4]

    # WELL-0175
    w175 = rows[3]
    assert w175[1] == 0.4
    assert w175[2] == "active (out of date)"
    assert w175[3] == "NO_RECORDED_REASON"


def test_checkpoint_6_6_well0001_june_spill_four_breaches(db_conn):
    """Checkpoint 6.6: WELL-0001 11 Jun 2026 spill flags SR-01, SR-02, SR-03, and RC-04 breaches."""
    row = db_conn.execute("""
        SELECT
            inspection_id,
            inspection_date,
            effective_spill_volume_bbl,
            containment_hours,
            is_sr01_breach,
            hours_to_report,
            nov_event_id,
            nov_fine_usd,
            is_sr02_breach,
            is_sr03_breach,
            sr03_cleanup_due_date,
            is_rc04_breach,
            rc04_response_due_date
        FROM v_spill_compliance_audit
        WHERE asset_id = 'WELL-0001' AND inspection_date = DATE '2026-06-11'
    """).fetchone()

    assert row is not None
    (
        insp_id,
        insp_date,
        vol,
        contain_h,
        sr01_b,
        h_rep,
        nov_id,
        fine,
        sr02_b,
        sr03_b,
        clean_due,
        rc04_b,
        rc04_due,
    ) = row

    assert insp_id == "INS-0001-0185"
    assert vol == 6.8
    assert contain_h == 7.0
    assert sr01_b is True
    assert h_rep == 41.0
    assert nov_id == "REG-0001-002"
    assert fine == 5000.0
    assert sr02_b is True
    assert sr03_b is True
    assert str(clean_due) == "2026-08-10"
    assert rc04_b is True
    assert str(rc04_due) == "2026-07-30"


def test_checkpoint_6_7_ne07_pump_jack_rca_baseline_q14(db_conn):
    """Checkpoint 6.7: NE-07 pump jack RCA needs_rca=True baseline matches Q14 (WELL-0108, 0121, 0138)."""
    rows = db_conn.execute("""
        SELECT asset_id, well_type, corrective_repairs_12m, required_rca_threshold, needs_rca
        FROM v_equipment_rca_tracker
        WHERE area_name = 'Northeast Block 7' AND equipment_kind = 'pump_jack' AND needs_rca = TRUE
        ORDER BY asset_id
    """).fetchall()

    wells = [r[0] for r in rows]
    assert wells == ["WELL-0108", "WELL-0121", "WELL-0138"]
    for r in rows:
        assert r[2] == 3
        assert r[3] == 3
        assert r[4] is True


def test_checkpoint_6_8_ne07_two_repairs_wells_baseline(db_conn):
    """Checkpoint 6.8: NE-07 WELL-0120 (T350) and WELL-0102 (T200) have 2 repairs and needs_rca=False."""
    rows = db_conn.execute("""
        SELECT asset_id, well_type, corrective_repairs_12m, required_rca_threshold, needs_rca
        FROM v_equipment_rca_tracker
        WHERE area_name = 'Northeast Block 7' AND equipment_kind = 'pump_jack' AND asset_id IN ('WELL-0102', 'WELL-0120')
        ORDER BY asset_id
    """).fetchall()

    assert len(rows) == 2
    w102 = rows[0]
    assert w102[0] == "WELL-0102"
    assert w102[1] == "T200"
    assert w102[2] == 2
    assert w102[3] == 3
    assert w102[4] is False

    w120 = rows[1]
    assert w120[0] == "WELL-0120"
    assert w120[1] == "T350"
    assert w120[2] == 2
    assert w120[3] == 3
    assert w120[4] is False


def test_checkpoint_6_9_well0001_flowline_rca_flags(db_conn):
    """Checkpoint 6.9: WELL-0001 shows 3 corrective repairs on flowline with report action required flag."""
    row = db_conn.execute("""
        SELECT asset_id, equipment_kind, corrective_repairs_12m, maintenance_ids_list, any_report_flags_action_required, needs_rca
        FROM v_equipment_rca_tracker
        WHERE asset_id = 'WELL-0001' AND equipment_kind = 'flowline'
    """).fetchone()

    assert row is not None
    aid, eq_kind, cnt, ids, action_req, needs_rca = row
    assert eq_kind == "flowline"
    assert cnt == 3
    assert "MNT-0001-028" in ids
    assert "MNT-0001-029" in ids
    assert "MNT-0001-032" in ids
    assert action_req is True
    assert needs_rca is True


def test_checkpoint_6_10_well0001_compliance_summary(db_conn):
    """Checkpoint 6.10: WELL-0001 compliance summary surfaces RC-02 flowline test and unlogged shut-in."""
    row = db_conn.execute("""
        SELECT
            asset_id,
            total_breaches_12m,
            open_fines_usd,
            has_pending_rca,
            has_unlogged_planned_shutin,
            unlogged_shutin_note_id,
            last_annual_flowline_test_date,
            is_annual_flowline_test_met
        FROM v_well_compliance_summary
        WHERE asset_id = 'WELL-0001'
    """).fetchone()

    assert row is not None
    aid, breaches, fines, rca, unlogged_shutin, shutin_id, fl_date, fl_met = row
    assert breaches == 4
    assert fines == 5000.0
    assert rca is True
    assert unlogged_shutin is True
    assert shutin_id == "CTX-0001-003"
    assert str(fl_date) == "2026-03-07"
    assert fl_met is True
