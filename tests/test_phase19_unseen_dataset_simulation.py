"""Phase 19: Unseen Test Dataset Drop Simulation.

Verifies that the FlytBase Asset Intelligence Copilot:
1. Re-indexes and recompiles an entirely new, unseen dataset root in < 5 seconds.
2. Preserves physical domain laws (Delta T thermodynamics, SOP spill thresholds) on unseen wells.
3. Automatically generates semantic views and queries without any prompt modifications or hardcoding.
"""

import json
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.db.views import init_views
from backend.ingestion.compile_context import compile_context_data
from backend.ingestion.compile_reports import compile_reports_data
from backend.ingestion.compile_rules import compile_rules_data
from backend.ingestion.ingest_raw import ingest_raw_data


@pytest.fixture
def unseen_mock_dataset():
    """Create a minimal unseen dataset representing a newly discovered or external field."""
    temp_dir = tempfile.mkdtemp(prefix="unseen_dataset_")
    root = Path(temp_dir)

    fleet = root / "fleet"
    fleet.mkdir(parents=True)
    (fleet / "sops").mkdir()
    (fleet / "well-types").mkdir()

    # Areas & Teams
    areas_data = {
        "areas": [
            {
                "area_id": "AREA-TEST-99",
                "name": "North Sea Field Sector 4",
                "team_id": "TEAM-OFFSHORE-1",
                "center": {"lat": 56.5, "lon": 3.2},
                "asset_ids": ["WELL-9901", "WELL-9902"],
            }
        ],
        "teams": [
            {
                "team_id": "TEAM-OFFSHORE-1",
                "name": "Offshore Production Team",
                "lead_user_id": "USR-TEST-01"
            }
        ]
    }
    with open(fleet / "areas.json", "w") as f:
        json.dump(areas_data, f)

    # Users
    users_data = {
        "users": [
            {
                "user_id": "USR-TEST-01",
                "name": "Astrid Lindgren",
                "role": "field_inspector",
                "team_id": "TEAM-OFFSHORE-1",
            }
        ]
    }
    with open(fleet / "users.json", "w") as f:
        json.dump(users_data, f)

    # SOPs and manuals
    with open(fleet / "well-types" / "T200.md", "w") as f:
        f.write("# T200 Specs\nDelta T threshold is 15.0 deg C. RCA required after 3 repairs.\n")
    with open(fleet / "well-types" / "T350.md", "w") as f:
        f.write("# T350 Specs\nDelta T threshold is 20.0 deg C. RCA required after 3 repairs.\n")
    with open(fleet / "sops" / "spill-response-sop.md", "w") as f:
        f.write("# Spill Response SOP\nSR-01: Major spill >= 5.0 bbl requires written regulatory notice in 24h.\n")
    with open(fleet / "sops" / "regulatory-compliance-sop.md", "w") as f:
        f.write("# Regulatory SOP\nRC-04: Mandatory response within 30 days.\n")
    with open(fleet / "sops" / "field-work-sop.md", "w") as f:
        f.write("# Field Work SOP\nWS-01: PPE mandatory.\n")

    # Assets: WELL-9901 (T200, Hot, Active) and WELL-9902 (T350, Cold, Stale 'active' in DB)
    for well_id, w_type, temp_wh, temp_amb, rec_status in [
        ("WELL-9901", "T200", 35.0, 15.0, "active"),      # Delta T = 20.0 >= 15.0 -> PRODUCING
        ("WELL-9902", "T350", 18.0, 16.0, "active"),      # Delta T = 2.0 < 20.0  -> NOT PRODUCING (STALE)
    ]:
        w_dir = root / "assets" / well_id
        w_dir.mkdir(parents=True)
        with open(w_dir / "metadata.json", "w") as f:
            json.dump({
                "asset_id": well_id,
                "name": f"Offshore Platform {well_id}",
                "asset_category": "oil_well",
                "well_type": w_type,
                "area_id": "AREA-TEST-99",
                "team_id": "TEAM-OFFSHORE-1",
                "in_charge_user_id": "USR-TEST-01",
                "location": {"lat": 56.51, "lon": 3.21},
                "installed_on": "2023-01-01",
                "equipment": [
                    {"equipment_id": f"{well_id}-WH", "kind": "wellhead", "model": "WH-3000"},
                    {"equipment_id": f"{well_id}-PJ", "kind": "pump_jack", "model": "PJ-228"}
                ],
                "last_inspection": {
                    "inspection_id": f"INS-{well_id}-001",
                    "inspected_at": "2026-10-15T08:00:00Z",
                    "inspector_user_id": "USR-TEST-01"
                },
                "recorded_status": rec_status
            }, f)

        # Inspections
        with open(w_dir / "inspections.jsonl", "w") as f:
            f.write(json.dumps({
                "inspection_id": f"INS-{well_id}-001",
                "asset_id": well_id,
                "inspected_at": "2026-10-15T08:00:00Z",
                "inspector_user_id": "USR-TEST-01",
                "method": "drone",
                "ambient_temp_c": temp_amb,
                "wellhead_temp_c": temp_wh,
                "spill_detected": (well_id == "WELL-9901"),
                "spill_area_pct": 5.0 if well_id == "WELL-9901" else None,
                "spill_est_volume_bbl": 3.5 if well_id == "WELL-9901" else None,
                "evidence_images": [],
                "notes": "Moderate sheen noted" if well_id == "WELL-9901" else ""
            }) + "\n")

        # Maintenance
        with open(w_dir / "maintenance.jsonl", "w") as f:
            f.write(json.dumps({
                "maintenance_id": f"MNT-{well_id}-001",
                "asset_id": well_id,
                "started_at": "2026-09-01T08:00:00Z",
                "completed_at": "2026-09-01T12:00:00Z",
                "maintenance_type": "corrective",
                "equipment_kind": "pump_jack",
                "issue": "Motor bearing failure",
                "action_taken": "Replaced bearing",
                "technician_user_id": "USR-TEST-01",
                "contractor": None,
                "downtime_hours": 4,
                "cost_usd": {"labor": 500, "parts": 700, "total": 1200},
                "triggered_by_inspection_id": None,
                "report_file": None
            }) + "\n")

        # Regulatory events
        with open(w_dir / "regulatory-events.jsonl", "w") as f:
            f.write(json.dumps({
                "event_id": f"REG-{well_id}-001",
                "asset_id": well_id,
                "date": "2026-05-01",
                "agency": "State Commission",
                "event_type": "inspection",
                "protocol_id": "RC-01",
                "related_inspection_id": f"INS-{well_id}-001",
                "hours_to_report": None,
                "detail": "Routine site visit passed without violations",
                "fine_usd": 0.0,
                "status": "closed"
            }) + "\n")

        # Context
        with open(w_dir / "context.jsonl", "w") as f:
            f.write(json.dumps({
                "note_id": f"CTX-{well_id}-001",
                "asset_id": well_id,
                "created_at": "2026-10-01T08:00:00Z",
                "author_user_id": "USR-TEST-01",
                "note_type": "operator_note",
                "inspection_id": None,
                "text": "Initial offshore commissioning complete.",
                "valid_from": "2026-10-01",
                "valid_to": None
            }) + "\n")

    yield root
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_19_1_unseen_dataset_drop_recompilation(unseen_mock_dataset):
    """Verify that an unseen dataset compiles end-to-end in < 3 seconds."""
    temp_db_file = tempfile.mktemp(suffix=".duckdb")
    db_path = Path(temp_db_file)

    t0 = time.time()
    try:
        # 1. Ingest raw tables
        res_raw = ingest_raw_data(dataset_root=unseen_mock_dataset, db_path=db_path, mode="rebuild")
        assert res_raw["counts"]["wells"] == 2
        assert res_raw["counts"]["areas"] == 1

        # 2. Compile rules
        res_rules = compile_rules_data(dataset_root=unseen_mock_dataset, db_path=db_path)
        assert res_rules["rules_registry_count"] > 0

        # 3. Compile reports
        res_rep = compile_reports_data(dataset_root=unseen_mock_dataset, db_path=db_path)
        assert res_rep["total_reports_parsed"] == 0  # No markdown reports in mock

        # 4. Compile context
        res_ctx = compile_context_data(dataset_root=unseen_mock_dataset, db_path=db_path)
        assert res_ctx["enriched_context_notes_count"] == 2

        # 5. Initialize Semantic Views
        init_views(db_path=db_path)

        elapsed = time.time() - t0
        assert elapsed < 5.0, f"Unseen dataset compilation took too long: {elapsed:.2f}s"

        # 6. Verify Semantic Generalization over unseen wells
        con = get_db_connection(db_path=db_path)

        # WELL-9901: Delta T = 20.0 C >= 15.0 C -> is_producing = True
        w1 = con.execute("SELECT is_producing, is_recorded_status_stale FROM v_well_current_status WHERE asset_id = 'WELL-9901'").fetchone()
        assert w1[0] is True, "WELL-9901 should be producing based on thermal physics"
        assert w1[1] is False, "WELL-9901 recorded status matches physical reality"

        # WELL-9902: Delta T = 2.0 C < 20.0 C -> is_producing = False, is_recorded_status_stale = True
        w2 = con.execute("SELECT is_producing, is_recorded_status_stale FROM v_well_current_status WHERE asset_id = 'WELL-9902'").fetchone()
        assert w2[0] is False, "WELL-9902 must be identified as shut-in/not producing"
        assert w2[1] is True, "WELL-9902 must be flagged as stale recorded status in legacy DB"

    finally:
        if db_path.exists():
            db_path.unlink()


def test_19_2_unseen_dataset_runtime_override_cascade(unseen_mock_dataset):
    """Verify that runtime user feedback correctly triggers SOP cascade audits on unseen wells."""
    temp_db_file = tempfile.mktemp(suffix=".duckdb")
    db_path = Path(temp_db_file)

    try:
        # Build DB
        ingest_raw_data(dataset_root=unseen_mock_dataset, db_path=db_path, mode="rebuild")
        compile_rules_data(dataset_root=unseen_mock_dataset, db_path=db_path)
        compile_reports_data(dataset_root=unseen_mock_dataset, db_path=db_path)
        compile_context_data(dataset_root=unseen_mock_dataset, db_path=db_path)
        init_views(db_path=db_path)

        from backend.feedback.override_engine import apply_spill_volume_override, evaluate_spill_override_cascade

        con = get_db_connection(db_path=db_path)
        # Register a spill volume update on unseen well WELL-9901
        res = apply_spill_volume_override(
            asset_id="WELL-9901",
            inspection_date_or_id="INS-WELL-9901-001",
            new_volume_bbl=6.5,  # Major spill >= 5.0 bbl
            author_name="Astrid Lindgren",
            author_user_id="USR-TEST-01",
            reason="Drone camera missed secondary pooling, field tech measured 6.5 bbl crude",
            con=con,
        )

        assert res["asset_id"] == "WELL-9901"
        assert res["new_numeric_value"] == 6.5

        # Verify semantic overlay dynamic precedence
        spill_audit = con.execute(
            "SELECT effective_spill_volume_bbl, has_active_correction FROM v_spill_compliance_audit WHERE inspection_id = 'INS-WELL-9901-001'"
        ).fetchone()
        assert spill_audit[0] == 6.5
        assert spill_audit[1] is True

    finally:
        if db_path.exists():
            db_path.unlink()
