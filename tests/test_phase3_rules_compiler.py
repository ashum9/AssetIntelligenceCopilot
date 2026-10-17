"""Phase 3 Verification Gate: Manual & SOP Rule Compiler.

Asserts all 10 checkpoints defined in the Phase 3 PRD:
  - Checkpoint 3.1: Delta T thresholds for T200 (15 C) and T350 (20 C)
  - Checkpoint 3.2: Production evaluation parity on Q1, Q5, Q2
  - Checkpoint 3.3: Downtime computation parity for Q6 top 4 wells in NE-07
  - Checkpoint 3.4: RCA threshold = 3.0 repairs per 365 days for T200 & T350
  - Checkpoint 3.5: SR-01, SR-02, SR-03 deadlines and thresholds populated
  - Checkpoint 3.6: Spill severity classification bounds (moderate vs reportable)
  - Checkpoint 3.7: RC-01 through RC-05 populated
  - Checkpoint 3.8: WS-01 through WS-07 populated
  - Checkpoint 3.9: Planned shut-in maintenance log rule captured
  - Checkpoint 3.10: Full citations and raw excerpts present on all rows
"""

from pathlib import Path
import pytest

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.ingestion.compile_rules import compile_rules_data
from backend.ingestion.ingest_raw import ingest_raw_data


@pytest.fixture(scope="session")
def db_conn():
    """Ensure database has raw data and compiled rules."""
    settings = get_settings()
    db_file = settings.artifacts_path / "copilot.duckdb"
    ingest_raw_data(dataset_root=settings.dataset_path, db_path=db_file, mode="rebuild")
    compile_rules_data(dataset_root=settings.dataset_path, db_path=db_file)
    con = get_db_connection(db_path=db_file)
    yield con
    con.close()


def test_checkpoint_3_1_delta_t_thresholds(db_conn):
    """Checkpoint 3.1: MIN_PRODUCING_TEMP_DELTA_C exists for T200 (15 C) and T350 (20 C)."""
    rows = db_conn.execute("""
        SELECT scope_value, threshold_value, comparison_operator, protocol_or_section
        FROM rules_registry
        WHERE rule_code = 'MIN_PRODUCING_TEMP_DELTA_C'
    """).fetchall()
    assert len(rows) == 2
    rule_map = {r[0]: r[1] for r in rows}
    assert rule_map["T200"] == 15.0
    assert rule_map["T350"] == 20.0


def test_checkpoint_3_2_production_evaluation_parity(db_conn):
    """Checkpoint 3.2: WELL-0001 (Q1, Q5) and NE-08 wells (Q2) evaluate to not producing."""
    # Q1: WELL-0001 on 2026-10-15 (delta = 3.2 C)
    q1_insp = db_conn.execute("""
        SELECT i.raw_temp_delta_c, r.threshold_value, (i.raw_temp_delta_c >= r.threshold_value) AS is_producing
        FROM raw_inspections i
        JOIN wells w ON i.asset_id = w.asset_id
        JOIN rules_registry r ON r.rule_code = 'MIN_PRODUCING_TEMP_DELTA_C' AND r.scope_value = w.well_type
        WHERE i.inspection_id = 'INS-0001-0203'
    """).fetchone()
    assert q1_insp[0] == 3.2
    assert q1_insp[2] is False  # Not producing

    # Q5: WELL-0001 hot-day 2025-07-24 (delta = 8.5 C)
    q5_insp = db_conn.execute("""
        SELECT i.raw_temp_delta_c, r.threshold_value, (i.raw_temp_delta_c >= r.threshold_value) AS is_producing
        FROM raw_inspections i
        JOIN wells w ON i.asset_id = w.asset_id
        JOIN rules_registry r ON r.rule_code = 'MIN_PRODUCING_TEMP_DELTA_C' AND r.scope_value = w.well_type
        WHERE i.asset_id = 'WELL-0001' AND i.inspection_date = '2025-07-24'
    """).fetchone()
    assert q5_insp[0] == 8.5
    assert q5_insp[2] is False  # Not producing

    # Q2: Northeast Block 8 on 2026-10-15 has 4 non-producing wells
    q2_non_prod = db_conn.execute("""
        SELECT w.asset_id, i.raw_temp_delta_c
        FROM raw_inspections i
        JOIN wells w ON i.asset_id = w.asset_id
        JOIN rules_registry r ON r.rule_code = 'MIN_PRODUCING_TEMP_DELTA_C' AND r.scope_value = w.well_type
        WHERE w.area_id = 'NE-08'
          AND i.inspection_date = '2026-10-15'
          AND i.raw_temp_delta_c < r.threshold_value
        ORDER BY w.asset_id
    """).fetchall()
    assert len(q2_non_prod) == 4
    non_prod_ids = [row[0] for row in q2_non_prod]
    assert non_prod_ids == ["WELL-0164", "WELL-0170", "WELL-0172", "WELL-0175"]


def test_checkpoint_3_3_q6_downtime_parity(db_conn):
    """Checkpoint 3.3: NE-07 downtime in last 4 months yields exact Q6 top 4 wells."""
    results = db_conn.execute("""
        SELECT 
            w.asset_id,
            w.well_type,
            count(*) * 7 AS downtime_days
        FROM raw_inspections i
        JOIN wells w ON i.asset_id = w.asset_id
        JOIN rules_registry r ON r.rule_code = 'MIN_PRODUCING_TEMP_DELTA_C' AND r.scope_value = w.well_type
        WHERE w.area_id = 'NE-07'
          AND i.inspection_date >= '2026-06-16'
          AND i.inspection_date <= '2026-10-16'
          AND i.raw_temp_delta_c < r.threshold_value
        GROUP BY w.asset_id, w.well_type
        ORDER BY downtime_days DESC, w.asset_id
        LIMIT 4
    """).fetchall()

    assert len(results) == 4
    # Expected: WELL-0121 (49 days), WELL-0107 (42 days), WELL-0138 (42 days), WELL-0119 (28 days)
    wells_days = {r[0]: (r[1], r[2]) for r in results}
    assert wells_days["WELL-0121"] == ("T200", 49)
    assert wells_days["WELL-0107"] == ("T350", 42)
    assert wells_days["WELL-0138"] == ("T350", 42)
    assert wells_days["WELL-0119"] == ("T200", 28)


def test_checkpoint_3_4_rca_thresholds(db_conn):
    """Checkpoint 3.4: CORRECTIVE_REPAIRS_RCA_THRESHOLD populated for T200 and T350 (=3.0)."""
    rca_rules = db_conn.execute("""
        SELECT scope_value, threshold_value, rolling_window_days, protocol_or_section
        FROM rules_registry
        WHERE rule_code = 'CORRECTIVE_REPAIRS_RCA_THRESHOLD'
    """).fetchall()
    assert len(rca_rules) == 2
    for r in rca_rules:
        assert r[1] == 3.0
        assert r[2] == 365
        assert "T200.md" in r[3]


def test_checkpoint_3_5_spill_response_protocols(db_conn):
    """Checkpoint 3.5: SR-01, SR-02, SR-03 populated in rules_registry and sop_protocols."""
    rules = {r[0]: r[1] for r in db_conn.execute("""
        SELECT rule_code, threshold_value FROM rules_registry WHERE rule_code LIKE 'SPILL_%'
    """).fetchall()}

    assert rules["SPILL_REPORTABLE_MIN_BBL"] == 5.0
    assert rules["SPILL_REPORTING_DEADLINE_HOURS"] == 24.0
    assert rules["SPILL_CONTAINMENT_LIMIT_HOURS"] == 4.0
    assert rules["SPILL_CLEANUP_VERIFICATION_DAYS"] == 60.0

    sop_sr = {r[0]: r for r in db_conn.execute("""
        SELECT protocol_id, deadline_hours, deadline_days FROM sop_protocols WHERE protocol_id LIKE 'SR-%'
    """).fetchall()}
    assert "SR-01" in sop_sr
    assert sop_sr["SR-01"][1] == 24.0
    assert "SR-02" in sop_sr
    assert sop_sr["SR-02"][1] == 4.0
    assert "SR-03" in sop_sr
    assert sop_sr["SR-03"][2] == 60.0


def test_checkpoint_3_6_spill_classes_mapping(db_conn):
    """Checkpoint 3.6: Spill severity classification bounds: 4.5 bbl is moderate, 5.4 bbl is reportable."""
    classes = db_conn.execute("""
        SELECT spill_class_name, min_volume_bbl, max_volume_bbl
        FROM sop_protocols
        WHERE spill_class_name IS NOT NULL
        ORDER BY min_volume_bbl
    """).fetchall()
    assert len(classes) >= 4

    # Test 4.5 bbl mapping (should be moderate)
    class_4_5 = db_conn.execute("""
        SELECT spill_class_name FROM sop_protocols
        WHERE spill_class_name IS NOT NULL
          AND 4.5 >= min_volume_bbl AND (max_volume_bbl IS NULL OR 4.5 < max_volume_bbl)
    """).fetchone()[0]
    assert class_4_5 == "moderate"

    # Test 5.4 bbl mapping (should be reportable)
    class_5_4 = db_conn.execute("""
        SELECT spill_class_name FROM sop_protocols
        WHERE spill_class_name IS NOT NULL
          AND 5.4 >= min_volume_bbl AND (max_volume_bbl IS NULL OR 5.4 < max_volume_bbl)
    """).fetchone()[0]
    assert class_5_4 == "reportable"


def test_checkpoint_3_7_regulatory_compliance_protocols(db_conn):
    """Checkpoint 3.7: RC-01 through RC-05 populated in sop_protocols and rules_registry."""
    rc_protocols = {r[0] for r in db_conn.execute("""
        SELECT protocol_id FROM sop_protocols WHERE protocol_id LIKE 'RC-%'
    """).fetchall()}
    assert {"RC-01", "RC-02", "RC-03", "RC-04", "RC-05"}.issubset(rc_protocols)

    rc_rules = {r[0]: r[1] for r in db_conn.execute("""
        SELECT rule_code, threshold_value FROM rules_registry WHERE rule_code IN ('ANNUAL_FLOWLINE_TEST_MAX_DAYS', 'NOV_RESPONSE_DEADLINE_DAYS')
    """).fetchall()}
    assert rc_rules["ANNUAL_FLOWLINE_TEST_MAX_DAYS"] == 365.0
    assert rc_rules["NOV_RESPONSE_DEADLINE_DAYS"] == 30.0


def test_checkpoint_3_8_field_work_safety_protocols(db_conn):
    """Checkpoint 3.8: WS-01 through WS-07 populated in sop_protocols."""
    ws_protocols = {r[0] for r in db_conn.execute("""
        SELECT protocol_id FROM sop_protocols WHERE protocol_id LIKE 'WS-%'
    """).fetchall()}
    assert {"WS-01", "WS-02", "WS-03", "WS-04", "WS-05", "WS-06", "WS-07"}.issubset(ws_protocols)


def test_checkpoint_3_9_planned_shutin_rule_captured(db_conn):
    """Checkpoint 3.9: PLANNED_SHUTIN_MAINT_LOG_REQUIRED rule captured for T200 and T350."""
    shutin_rules = db_conn.execute("""
        SELECT scope_value, threshold_value, protocol_or_section
        FROM rules_registry
        WHERE rule_code = 'PLANNED_SHUTIN_MAINT_LOG_REQUIRED'
    """).fetchall()
    assert len(shutin_rules) == 2
    for r in shutin_rules:
        assert r[1] == 1.0


def test_checkpoint_3_10_citations_and_excerpts_present(db_conn):
    """Checkpoint 3.10: Every row in rules_registry and sop_protocols has non-empty citation & excerpt."""
    empty_rules = db_conn.execute("""
        SELECT count(*) FROM rules_registry
        WHERE source_file IS NULL OR length(source_file) = 0
           OR protocol_or_section IS NULL OR length(protocol_or_section) = 0
           OR raw_excerpt IS NULL OR length(raw_excerpt) = 0
    """).fetchone()[0]
    assert empty_rules == 0

    empty_sops = db_conn.execute("""
        SELECT count(*) FROM sop_protocols
        WHERE source_file IS NULL OR length(source_file) = 0
           OR section_heading IS NULL OR length(section_heading) = 0
           OR full_section_markdown IS NULL OR length(full_section_markdown) = 0
    """).fetchone()[0]
    assert empty_sops == 0
