"""Phase 4 Verification Gate: Free-Text Maintenance Report Compiler.

Asserts all 10 checkpoints defined in the Phase 4 PRD:
  - Checkpoint 4.1: 100% of .md repair reports (1,509 files) parsed with zero errors
  - Checkpoint 4.2: Every parsed report links cleanly to valid maintenance_id
  - Checkpoint 4.3: Q9 June spill report has containment_hours = 7.0 and exceeds_sr02 = True
  - Checkpoint 4.4: Q9 Oct report MNT-0001-032 has rca_action_required = True
  - Checkpoint 4.5: Q9 RC-02 flowline test (7 Mar 2026) deterministically identified
  - Checkpoint 4.6: Q10 SW-24 containment breaches returns exclusively WELL-0082 & WELL-0100
  - Checkpoint 4.7: Q13 MNT-0151-025 has moderate class, 6.4h, and exceeds_sr02 = True
  - Checkpoint 4.8: Q18 MNT-0101-029 report present and confirms spill repair
  - Checkpoint 4.9: All 8 section text columns populated without dropping text
  - Checkpoint 4.10: Full compilation completes in under 5 seconds
"""

import time
from pathlib import Path
import pytest

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.ingestion.compile_reports import compile_reports_data
from backend.ingestion.ingest_raw import ingest_raw_data


@pytest.fixture(scope="session")
def db_conn():
    """Ensure database has raw data and compiled reports."""
    settings = get_settings()
    db_file = settings.artifacts_path / "copilot.duckdb"
    ingest_raw_data(dataset_root=settings.dataset_path, db_path=db_file, mode="rebuild")
    compile_reports_data(dataset_root=settings.dataset_path, db_path=db_file)
    con = get_db_connection(db_path=db_file)
    yield con
    con.close()


def test_checkpoint_4_1_total_reports_parsed(db_conn):
    """Checkpoint 4.1: 100% of .md reports (1,509 files) parsed into parsed_repair_reports."""
    cnt = db_conn.execute("SELECT count(*) FROM parsed_repair_reports").fetchone()[0]
    assert cnt == 1509


def test_checkpoint_4_2_foreign_key_link(db_conn):
    """Checkpoint 4.2: Every parsed report links cleanly to valid maintenance_id in raw_maintenance."""
    unmatched = db_conn.execute("""
        SELECT count(*)
        FROM parsed_repair_reports p
        LEFT JOIN raw_maintenance m ON p.maintenance_id = m.maintenance_id
        WHERE m.maintenance_id IS NULL
    """).fetchone()[0]
    assert unmatched == 0


def test_checkpoint_4_3_q9_june_spill_containment(db_conn):
    """Checkpoint 4.3: Q9 June spill report for WELL-0001 has containment_hours = 7.0 and exceeds SR-02."""
    row = db_conn.execute("""
        SELECT maintenance_id, asset_id, containment_hours, exceeds_sr02_limit, containment_excerpt
        FROM parsed_repair_reports
        WHERE asset_id = 'WELL-0001' AND containment_hours >= 7.0
    """).fetchone()
    assert row is not None
    assert row[0] == "MNT-0001-029"
    assert row[2] == 7.0
    assert row[3] is True
    assert "7 hours" in row[4].lower()


def test_checkpoint_4_4_q9_october_flowline_rca(db_conn):
    """Checkpoint 4.4: Q9 October report MNT-0001-032 has rca_action_required = True."""
    row = db_conn.execute("""
        SELECT maintenance_id, rca_action_required, rca_excerpt
        FROM parsed_repair_reports
        WHERE maintenance_id = 'MNT-0001-032'
    """).fetchone()
    assert row is not None
    assert row[1] is True
    assert "root-cause analysis" in row[2].lower() or "action required" in row[2].lower()


def test_checkpoint_4_5_q9_rc02_flowline_test(db_conn):
    """Checkpoint 4.5: Q9 yearly flowline test (7 Mar 2026) deterministically identified."""
    # Check in raw_maintenance
    test_maint = db_conn.execute("""
        SELECT maintenance_id, asset_id, started_date, issue, action_taken
        FROM raw_maintenance
        WHERE asset_id = 'WELL-0001' AND started_date = '2026-03-07'
    """).fetchone()
    assert test_maint is not None
    assert test_maint[0] == "MNT-0001-026"
    assert "Annual flowline integrity test" in test_maint[3]

    # Check mention in parsed_repair_reports
    flowline_reports = db_conn.execute("""
        SELECT maintenance_id, flowline_annual_test_performed
        FROM parsed_repair_reports
        WHERE asset_id = 'WELL-0001' AND flowline_annual_test_performed = TRUE
    """).fetchall()
    assert len(flowline_reports) >= 1


def test_checkpoint_4_6_q10_sw24_containment_breaches(db_conn):
    """Checkpoint 4.6: SW-24 breaches in last 90 days returns exclusively WELL-0082 and WELL-0100."""
    breaches = db_conn.execute("""
        SELECT p.asset_id, p.maintenance_id, p.triggered_by_inspection_id, p.containment_hours
        FROM parsed_repair_reports p
        JOIN wells w ON p.asset_id = w.asset_id
        WHERE w.area_id = 'SW-24'
          AND p.report_date >= '2026-07-19'
          AND p.report_date <= '2026-10-17'
          AND p.containment_hours > 4.0
        ORDER BY p.asset_id
    """).fetchall()

    assert len(breaches) == 2
    b_map = {b[0]: (b[1], b[2], b[3]) for b in breaches}
    assert "WELL-0082" in b_map
    assert b_map["WELL-0082"] == ("MNT-0082-028", "INS-0082-0198", 7.1)
    assert "WELL-0100" in b_map
    assert b_map["WELL-0100"] == ("MNT-0100-034", "INS-0100-0196", 8.1)


def test_checkpoint_4_7_q13_well0151_report(db_conn):
    """Checkpoint 4.7: Report MNT-0151-025 has moderate class, 6.4h containment, exceeds SR-02."""
    row = db_conn.execute("""
        SELECT maintenance_id, asset_id, reported_spill_class, containment_hours, exceeds_sr02_limit
        FROM parsed_repair_reports
        WHERE maintenance_id = 'MNT-0151-025'
    """).fetchone()
    assert row is not None
    assert row[1] == "WELL-0151"
    assert row[2] == "moderate"
    assert row[3] == 6.4
    assert row[4] is True


def test_checkpoint_4_8_q18_well0101_report(db_conn):
    """Checkpoint 4.8: Report MNT-0101-029 is present and confirms spill repair performed."""
    row = db_conn.execute("""
        SELECT maintenance_id, asset_id, triggered_by_inspection_id, section_what_happened
        FROM parsed_repair_reports
        WHERE maintenance_id = 'MNT-0101-029'
    """).fetchone()
    assert row is not None
    assert row[1] == "WELL-0101"
    assert row[2] == "INS-0101-0197"
    assert "crude oil" in row[3].lower() or "spill" in row[3].lower()


def test_checkpoint_4_9_section_text_populated(db_conn):
    """Checkpoint 4.9: Standard sections populated without dropping text."""
    sample = db_conn.execute("""
        SELECT 
            section_what_happened,
            section_root_cause,
            section_safety_steps,
            section_work_done,
            section_tests,
            section_cleanup,
            section_parts_and_cost,
            section_compliance_check
        FROM parsed_repair_reports
        WHERE maintenance_id = 'MNT-0001-032'
    """).fetchone()
    assert sample is not None
    for sec in sample:
        assert len(sec) > 0, "Expected non-empty section text"


def test_checkpoint_4_10_compilation_speed():
    """Checkpoint 4.10: Full compilation completes in under 5 seconds."""
    settings = get_settings()
    t0 = time.time()
    res = compile_reports_data(dataset_root=settings.dataset_path)
    elapsed = time.time() - t0
    assert res["status"] == "success"
    assert res["total_reports_parsed"] == 1509
    assert elapsed < 5.0
