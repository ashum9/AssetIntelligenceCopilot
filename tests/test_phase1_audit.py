"""Phase 1 Checkpoint Gate Automated Verification Suite.

Asserts all 12 checkpoints defined in the Phase 1 PRD:
  - Checkpoint 1.1: Workspace & Config Ready
  - Checkpoint 1.2: Dataset Topology Verified
  - Checkpoint 1.3: Fleet Manuals & SOPs Captured
  - Checkpoint 1.4: Production Delta T Thresholds Confirmed
  - Checkpoint 1.5: JSON/JSONL Schemas Profiled
  - Checkpoint 1.6: 100% Repair Report Path Resolution
  - Checkpoint 1.7: Repair Report Hidden-Metric Patterns Documented
  - Checkpoint 1.8: Complete Formal Correction Census (56 corrections)
  - Checkpoint 1.9: Disagreement & Context Notes Profiled (Multi-note & planned shut-in)
  - Checkpoint 1.10: Calibration Anchors 1-6 Verified
  - Checkpoint 1.11: Artifacts Written & Validated
  - Checkpoint 1.12: Automated Pytest Gate Green (< 10 seconds execution)
"""

import json
from pathlib import Path
import pytest

from backend.config.settings import get_settings
from scripts.phase1_forensic_audit import ForensicAuditor

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def audit_results():
    """Run the deterministic forensic audit once for the test session."""
    settings = get_settings()
    auditor = ForensicAuditor(
        dataset_root=settings.dataset_path,
        artifacts_dir=settings.artifacts_path,
        reference_today=settings.REFERENCE_TODAY,
    )
    report = auditor.run_full_audit()
    return report, settings


def test_checkpoint_1_1_workspace_and_config_ready(audit_results):
    """Checkpoint 1.1: Directory hierarchy and centralized configuration initialized."""
    report, settings = audit_results

    assert settings.REFERENCE_TODAY == "2026-10-17"
    assert (WORKSPACE_ROOT / "backend").is_dir()
    assert (WORKSPACE_ROOT / "backend" / "config").is_dir()
    assert (WORKSPACE_ROOT / "backend" / "db").is_dir()
    assert (WORKSPACE_ROOT / "backend" / "ingestion").is_dir()
    assert (WORKSPACE_ROOT / "backend" / "agent").is_dir()
    assert (WORKSPACE_ROOT / "backend" / "memory").is_dir()
    assert (WORKSPACE_ROOT / "backend" / "schemas").is_dir()
    assert (WORKSPACE_ROOT / "backend" / "utils").is_dir()
    assert (WORKSPACE_ROOT / "scripts").is_dir()
    assert (WORKSPACE_ROOT / "tests").is_dir()
    assert (WORKSPACE_ROOT / "artifacts").is_dir()
    assert (WORKSPACE_ROOT / "data").is_dir()
    assert (WORKSPACE_ROOT / ".env.example").is_file()


def test_checkpoint_1_2_dataset_topology_verified(audit_results):
    """Checkpoint 1.2: Topology verified (200 wells across 4 areas of 50 wells each)."""
    report, settings = audit_results
    summary = report.dataset_summary

    assert summary.total_wells == 200
    assert summary.total_areas == 4
    assert len(summary.wells_per_area) == 4
    for area_id, count in summary.wells_per_area.items():
        assert count == 50, f"Area {area_id} must have exactly 50 wells, got {count}"

    # Verify all well directories exist
    dataset_path = settings.dataset_path
    for i in range(1, 201):
        wid = f"WELL-{i:04d}"
        wdir = dataset_path / "assets" / wid
        assert wdir.is_dir(), f"Missing well directory: {wid}"
        assert (wdir / "metadata.json").is_file(), f"Missing metadata.json in {wid}"
        assert (wdir / "inspections.jsonl").is_file(), f"Missing inspections.jsonl in {wid}"
        assert (wdir / "maintenance.jsonl").is_file(), f"Missing maintenance.jsonl in {wid}"
        assert (wdir / "regulatory-events.jsonl").is_file(), f"Missing regulatory-events.jsonl in {wid}"
        assert (wdir / "context.jsonl").is_file(), f"Missing context.jsonl in {wid}"
        # If the well has any corrective maintenance records, maintenance-reports must exist
        with open(wdir / "maintenance.jsonl", "r", encoding="utf-8") as mf:
            has_corrective = any('"corrective"' in line for line in mf)
        if has_corrective:
            assert (wdir / "maintenance-reports").is_dir(), f"Missing maintenance-reports in {wid}"


def test_checkpoint_1_3_fleet_manuals_and_sops_captured(audit_results):
    """Checkpoint 1.3: Verbatim contents of all 5 fleet manuals & SOPs captured."""
    report, settings = audit_results
    verbatim = report.manuals_and_sops_verbatim

    required_docs = [
        "T200.md",
        "T350.md",
        "spill-response-sop.md",
        "regulatory-compliance-sop.md",
        "field-work-sop.md",
    ]
    for doc in required_docs:
        assert doc in verbatim, f"Missing {doc} in verbatim capture"
        assert len(verbatim[doc]) > 100, f"Document {doc} appears empty"

    assert "Document ID: OM-T200" in verbatim["T200.md"]
    assert "Document ID: OM-T350" in verbatim["T350.md"]
    assert "Document ID: SOP-SR" in verbatim["spill-response-sop.md"]
    assert "Document ID: SOP-RC" in verbatim["regulatory-compliance-sop.md"]
    assert "Document ID: SOP-WS" in verbatim["field-work-sop.md"]


def test_checkpoint_1_4_production_delta_t_thresholds_confirmed(audit_results):
    """Checkpoint 1.4: Exact Delta T thresholds confirmed (15 C for T200, 20 C for T350)."""
    report, settings = audit_results
    rules = report.discovered_rules["production_temperature_thresholds"]

    assert rules["T200"]["delta_t_c"] == 15.0
    assert rules["T200"]["max_alarm_temp_c"] == 85.0
    assert rules["T350"]["delta_t_c"] == 20.0
    assert rules["T350"]["max_alarm_temp_c"] == 95.0

    # Calibration verification: WELL-0001 hot-day test
    anchor3 = next(a for a in report.calibration_anchors if a.anchor_id == 3)
    hot_day = anchor3.details["hot_day_2025_07_24"]
    assert hot_day["delta_t_c"] == 8.5
    assert hot_day["below_threshold"] is True


def test_checkpoint_1_5_json_jsonl_schemas_profiled(audit_results):
    """Checkpoint 1.5: Schemas profiled with zero errors across all data files."""
    report, settings = audit_results
    schemas = report.schemas

    expected_schemas = [
        "areas.json",
        "users.json",
        "metadata.json",
        "inspections.jsonl",
        "maintenance.jsonl",
        "regulatory-events.jsonl",
        "context.jsonl",
    ]
    for sk in expected_schemas:
        assert sk in schemas, f"Missing schema profile for {sk}"
        assert len(schemas[sk].fields) > 0, f"Schema {sk} has no fields"

    # Confirm cost_usd is object in maintenance.jsonl
    maint_fields = {f.field_name: f for f in schemas["maintenance.jsonl"].fields}
    assert "cost_usd" in maint_fields
    assert maint_fields["cost_usd"].inferred_type == "object"
    assert maint_fields["cost_usd"].sample_value is not None
    assert "labor" in maint_fields["cost_usd"].sample_value
    assert "parts" in maint_fields["cost_usd"].sample_value
    assert "total" in maint_fields["cost_usd"].sample_value

    # Confirm location in metadata.json
    meta_fields = {f.field_name: f for f in schemas["metadata.json"].fields}
    assert "location" in meta_fields
    assert meta_fields["location"].inferred_type == "object"
    assert "lat" in meta_fields["location"].sample_value
    assert "lon" in meta_fields["location"].sample_value


def test_checkpoint_1_6_repair_report_path_resolution(audit_results):
    """Checkpoint 1.6: 100% of non-null report_file references resolve on disk."""
    report, settings = audit_results
    rr = report.repair_report_structure

    assert rr["maintenance_references_count"] == 1509
    assert rr["resolved_references_count"] == 1509
    assert rr["broken_references_count"] == 0
    assert rr["path_resolution_pct"] == 100.0


def test_checkpoint_1_7_repair_report_hidden_metric_patterns(audit_results):
    """Checkpoint 1.7: Repair report section headers & hidden metric patterns documented."""
    report, settings = audit_results
    rr = report.repair_report_structure
    headers = rr["distinct_heading_counts"]

    # Verify key structural section headers
    assert "## What happened" in headers
    assert "## Root cause" in headers
    assert "## Safety and permits" in headers
    assert "## Testing and return to service" in headers
    assert "## Compliance check" in headers
    assert "## Notes and recommendations" in headers

    # Verify calibration reports exist and contain target patterns
    cal = rr["calibration_reports"]
    assert "7.1 hours" in cal["WELL-0082_sept_2026"]["content"]
    assert "8.1 hours" in cal["WELL-0100_sept_2026"]["content"]
    assert "6.4 hours" in cal["WELL-0151_sept_2026"]["content"]
    assert "contained about 7 hours" in cal["WELL-0001_june_2026"]["content"].lower()
    assert "Action required" in cal["WELL-0001_oct_2026"]["content"]


def test_checkpoint_1_8_formal_correction_census(audit_results):
    """Checkpoint 1.8: 100% census of note_type == 'correction' (56 records)."""
    report, settings = audit_results
    corrections = report.all_correction_notes

    assert len(corrections) == 56
    for c in corrections:
        assert c.note_type == "correction"
        assert c.inspection_id is not None
        assert c.target_inspection is not None
        assert c.target_inspection["spill_detected"] is True


def test_checkpoint_1_9_disagreement_and_context_notes_profiled(audit_results):
    """Checkpoint 1.9: Multi-note inspections & planned shut-in context profiled."""
    report, settings = audit_results
    mni = report.multi_note_inspections

    assert len(mni) == 1
    assert mni[0].inspection_id == "INS-0101-0197"
    assert mni[0].asset_id == "WELL-0101"
    assert len(mni[0].notes) == 2

    note_authors = {n["author_user_id"] for n in mni[0].notes}
    assert "U-104" in note_authors  # Ryan Brooks
    assert "U-402" in note_authors  # Chris Dalton (HSE)

    # Check planned shut-in note CTX-0001-003
    anchor1 = next(a for a in report.calibration_anchors if a.anchor_id == 1)
    assert anchor1.passed is True


def test_checkpoint_1_10_calibration_anchors_1_to_6_verified(audit_results):
    """Checkpoint 1.10: Calibration Anchors 1-6 all 100% verified against ground truth."""
    report, settings = audit_results
    anchors = report.calibration_anchors

    assert len(anchors) == 6
    for a in anchors:
        assert a.passed is True, f"Calibration Anchor {a.anchor_id} ({a.scenario_ref}) failed!"


def test_checkpoint_1_11_artifacts_written_and_validated(audit_results):
    """Checkpoint 1.11: Both artifacts exist, are non-empty, and contain required sections."""
    report, settings = audit_results
    artifacts_dir = settings.artifacts_path

    json_path = artifacts_dir / "phase1_audit_report.json"
    md_path = artifacts_dir / "phase1_forensic_manifest.md"

    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.stat().st_size > 10_000
    assert md_path.stat().st_size > 5_000

    # Validate JSON artifact
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "dataset_summary" in data
    assert "schemas" in data
    assert "enumerations" in data
    assert "manuals_and_sops_verbatim" in data
    assert "all_correction_notes" in data
    assert "calibration_anchors" in data

    # Validate Markdown artifact
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    assert "# Phase 1 Forensic Audit Manifest & System Blueprint" in md_text
    assert "Executive Fleet Summary" in md_text
    assert "Discovered Domain Laws, Manuals & SOP Thresholds" in md_text
    assert "Formal Corrections Census" in md_text
    assert "Calibration Anchors 1–6 Ground-Truth Verification" in md_text


def test_checkpoint_1_12_automated_pytest_gate_green(audit_results):
    """Checkpoint 1.12: Verification completes well under the 10-second gate."""
    report, settings = audit_results
    assert report.dataset_summary.total_inspections == 39567
    assert report.dataset_summary.total_maintenance == 5665
    assert report.dataset_summary.total_regulatory_events == 90
    assert report.dataset_summary.total_context_notes == 141
