"""Phase 2 Verification Gate: Raw Structured Ingestion into DuckDB.

Asserts all 10 checkpoints defined in the Phase 2 PRD:
  - Checkpoint 2.1: Areas, Teams, Users populated with required personas
  - Checkpoint 2.2: Wells has 200 rows (50 per area) and clean foreign keys
  - Checkpoint 2.3: Well equipment unpacked with valid kinds
  - Checkpoint 2.4: Raw inspections has 39,567 rows with no NULLs in critical fields
  - Checkpoint 2.5: Raw maintenance has 5,665 rows and Q11 repair cost sums match
  - Checkpoint 2.6: Open repair detection works (MNT-0170-031 & MNT-0172-028)
  - Checkpoint 2.7: 100% path resolution for report_file
  - Checkpoint 2.8: Raw regulatory events has 90 rows with Q9 REG-0001 records
  - Checkpoint 2.9: Raw context notes has 141 rows with type and dates preserved
  - Checkpoint 2.10: Merge mode is idempotent (< 5s, identical row counts)
"""

from pathlib import Path
import pytest

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.ingestion.ingest_raw import ingest_raw_data


@pytest.fixture(scope="session")
def db_conn():
    """Ensure raw ingestion is executed and provide a DuckDB connection."""
    settings = get_settings()
    ingest_raw_data(
        dataset_root=settings.dataset_path,
        db_path=settings.artifacts_path / "copilot.duckdb",
        mode="rebuild",
        reference_today=settings.REFERENCE_TODAY,
    )
    con = get_db_connection(db_path=settings.artifacts_path / "copilot.duckdb")
    yield con
    con.close()


def test_checkpoint_2_1_areas_teams_users(db_conn):
    """Checkpoint 2.1: areas, teams, and users populated with required personas."""
    # Check areas
    areas = db_conn.execute("SELECT area_id, area_name, expected_well_count FROM areas ORDER BY area_id").fetchall()
    assert len(areas) == 4
    area_ids = {a[0] for a in areas}
    assert {"SW-23", "SW-24", "NE-07", "NE-08"}.issubset(area_ids)
    for a in areas:
        assert a[2] == 50

    # Check teams
    teams = db_conn.execute("SELECT team_id, team_name FROM teams").fetchall()
    assert len(teams) == 4
    team_ids = {t[0] for t in teams}
    assert {"TEAM-SW", "TEAM-NE", "TEAM-MX", "TEAM-HSE"}.issubset(team_ids)

    # Check users
    users = db_conn.execute("SELECT user_id, user_name, role FROM users").fetchall()
    assert len(users) >= 14
    user_names = {u[1] for u in users}
    required_personas = {
        "Michael Turner",
        "Tyler Hughes",
        "Jessica Reed",
        "Jake Morales",
        "Laura Simmons",
        "Ryan Brooks",
        "Chris Dalton",
    }
    assert required_personas.issubset(user_names)


def test_checkpoint_2_2_wells_and_fks(db_conn):
    """Checkpoint 2.2: wells has exactly 200 rows (50 per area) and clean foreign keys."""
    wells_count = db_conn.execute("SELECT count(*) FROM wells").fetchone()[0]
    assert wells_count == 200

    area_dist = db_conn.execute("SELECT area_id, count(*) FROM wells GROUP BY area_id").fetchall()
    assert len(area_dist) == 4
    for _, cnt in area_dist:
        assert cnt == 50

    # Foreign key integrity
    unmatched_areas = db_conn.execute(
        "SELECT count(*) FROM wells w LEFT JOIN areas a ON w.area_id = a.area_id WHERE a.area_id IS NULL"
    ).fetchone()[0]
    assert unmatched_areas == 0

    unmatched_teams = db_conn.execute(
        "SELECT count(*) FROM wells w LEFT JOIN teams t ON w.team_id = t.team_id WHERE t.team_id IS NULL"
    ).fetchone()[0]
    assert unmatched_teams == 0

    unmatched_users = db_conn.execute(
        "SELECT count(*) FROM wells w LEFT JOIN users u ON w.in_charge_user_id = u.user_id WHERE u.user_id IS NULL"
    ).fetchone()[0]
    assert unmatched_users == 0


def test_checkpoint_2_3_well_equipment(db_conn):
    """Checkpoint 2.3: well_equipment contains all items with valid equipment kinds."""
    eq_count = db_conn.execute("SELECT count(*) FROM well_equipment").fetchone()[0]
    assert eq_count == 1094

    valid_kinds = {"wellhead", "pump_jack", "rod_string", "downhole_pump", "flowline", "separator"}
    distinct_kinds = {row[0] for row in db_conn.execute("SELECT DISTINCT equipment_kind FROM well_equipment").fetchall()}
    assert distinct_kinds.issubset(valid_kinds)


def test_checkpoint_2_4_raw_inspections(db_conn):
    """Checkpoint 2.4: raw_inspections count matches Phase 1 with no nulls in key fields."""
    insp_count = db_conn.execute("SELECT count(*) FROM raw_inspections").fetchone()[0]
    assert insp_count == 39567

    null_check = db_conn.execute("""
        SELECT count(*) FROM raw_inspections
        WHERE inspection_id IS NULL 
           OR asset_id IS NULL 
           OR inspected_at IS NULL 
           OR ambient_temp_c IS NULL 
           OR wellhead_temp_c IS NULL 
           OR raw_temp_delta_c IS NULL
    """).fetchone()[0]
    assert null_check == 0


def test_checkpoint_2_5_raw_maintenance_and_q11(db_conn):
    """Checkpoint 2.5: raw_maintenance count matches and Q11 repair cost sums match."""
    maint_count = db_conn.execute("SELECT count(*) FROM raw_maintenance").fetchone()[0]
    assert maint_count == 5665

    # Check Q11 repair costs for 2026: WELL-0121 ($25,794), WELL-0138 ($46,942), WELL-0107 ($5,176)
    q11_cases = {
        "WELL-0121": 25794.0,
        "WELL-0138": 46942.0,
        "WELL-0107": 5176.0,
    }
    for wid, expected_cost in q11_cases.items():
        actual_cost = db_conn.execute(f"""
            SELECT SUM(cost_total_usd) 
            FROM raw_maintenance 
            WHERE asset_id = '{wid}' AND started_date >= '2026-01-01'
        """).fetchone()[0]
        assert actual_cost == expected_cost, f"Mismatch for {wid}: expected {expected_cost}, got {actual_cost}"


def test_checkpoint_2_6_open_repairs(db_conn):
    """Checkpoint 2.6: Open repair detection works (MNT-0170-031 and MNT-0172-028 are open)."""
    open_repairs = db_conn.execute("""
        SELECT maintenance_id, asset_id, started_date, completed_date, is_open_as_of_today
        FROM raw_maintenance
        WHERE maintenance_id IN ('MNT-0170-031', 'MNT-0172-028')
    """).fetchall()
    assert len(open_repairs) == 2
    for r in open_repairs:
        assert r[4] is True, f"Repair {r[0]} on {r[1]} should be open as of today"


def test_checkpoint_2_7_report_path_resolution(db_conn):
    """Checkpoint 2.7: 100% of non-null report_file rows have verified resolved_report_path."""
    settings = get_settings()
    d_root = settings.dataset_path

    reports = db_conn.execute("""
        SELECT maintenance_id, report_file, resolved_report_path
        FROM raw_maintenance
        WHERE report_file IS NOT NULL
    """).fetchall()
    assert len(reports) == 1509

    for mid, rf, rpath in reports:
        assert rpath is not None
        disk_path = d_root / rpath
        assert disk_path.exists(), f"Resolved report file not found on disk: {disk_path} for {mid}"


def test_checkpoint_2_8_raw_regulatory_events(db_conn):
    """Checkpoint 2.8: raw_regulatory_events has 90 rows including Q9 REG-0001 records."""
    reg_count = db_conn.execute("SELECT count(*) FROM raw_regulatory_events").fetchone()[0]
    assert reg_count == 90

    # Q9 regulatory records for WELL-0001
    w1_regs = db_conn.execute("""
        SELECT event_id, event_type, protocol_id, hours_to_report, fine_usd, status
        FROM raw_regulatory_events
        WHERE asset_id = 'WELL-0001'
        ORDER BY event_id
    """).fetchall()
    assert len(w1_regs) >= 3

    reg_map = {r[0]: r for r in w1_regs}
    assert reg_map["REG-0001-001"][3] == 41.0  # hours_to_report
    assert reg_map["REG-0001-001"][5] == "closed"
    assert reg_map["REG-0001-002"][4] == 5000.0  # fine_usd
    assert reg_map["REG-0001-002"][5] == "open"
    assert reg_map["REG-0001-003"][2] == "SR-03"  # protocol_id
    assert reg_map["REG-0001-003"][5] == "open"


def test_checkpoint_2_9_raw_context_notes(db_conn):
    """Checkpoint 2.9: raw_context_notes has 141 rows, preserving type and dates."""
    ctx_count = db_conn.execute("SELECT count(*) FROM raw_context_notes").fetchone()[0]
    assert ctx_count == 141

    # Check CTX-0001-001 (rainwater correction)
    c1 = db_conn.execute("""
        SELECT note_id, asset_id, note_type, inspection_id, valid_from
        FROM raw_context_notes
        WHERE note_id = 'CTX-0001-001'
    """).fetchone()
    assert c1 is not None
    assert c1[2] == "correction"
    assert c1[3] == "INS-0001-0070"

    # Check CTX-0001-003 (planned shut-in)
    c3 = db_conn.execute("""
        SELECT note_id, asset_id, note_type, valid_from, valid_to
        FROM raw_context_notes
        WHERE note_id = 'CTX-0001-003'
    """).fetchone()
    assert c3 is not None
    assert str(c3[3]) == "2026-10-07"
    assert str(c3[4]) == "2026-10-20"


def test_checkpoint_2_10_merge_mode_idempotency(db_conn):
    """Checkpoint 2.10: Running ingest_raw in merge mode is idempotent (< 5s, identical counts)."""
    settings = get_settings()
    res = ingest_raw_data(
        dataset_root=settings.dataset_path,
        db_path=settings.artifacts_path / "copilot.duckdb",
        mode="merge",
        reference_today=settings.REFERENCE_TODAY,
    )
    assert res["status"] == "success"
    assert res["duration_ms"] < 5000.0
    assert res["counts"]["wells"] == 200
    assert res["counts"]["raw_inspections"] == 39567
    assert res["counts"]["raw_maintenance"] == 5665
    assert res["counts"]["raw_regulatory_events"] == 90
    assert res["counts"]["raw_context_notes"] == 141
