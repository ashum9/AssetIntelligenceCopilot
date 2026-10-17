"""Phase 12 Verification Suite: Automated Contradiction & Conflict Detection Engine.

Tests:
  12.1: ConflictRecord Pydantic model structure and fields.
  12.2: Q12 CORRECTION_VS_INSPECTOR_REMARK on WELL-0164 (41.0 C vs 'Pump jack not moving.').
  12.3: Q15 Jessica Reed gets active conflict on WELL-0164.
  12.4: Q17 Step 1 Michael Turner's shut-in on WELL-0175 confirmed with INS-0175-0204 (0.4 C delta).
  12.5: Q17 Step 2 Tyler Hughes's 'running fine' flagged as CLAIM_VS_TELEMETRY_AND_PEER_NOTE.
  12.6: enriched_context_notes for WELL-0175 contains both Turner's CONFIRMED and Hughes's UNCONFIRMED_CLAIM notes.
  12.7: Q17 Step 3 Jake Morales on WELL-0001 flagged as CLAIM_VS_TELEMETRY_AND_SCHEDULE (INS-0001-0203 + CTX-0001-003).
  12.8: Q18 WELL-0101 spill detection stands despite CTX-0101-002 vs CTX-0101-003 peer disagreement.
  12.9: All conflict records include structured citations for UI badge rendering.
  12.10: reset_runtime_state clears all unconfirmed claims and restores clean baseline.
"""

import pytest
import duckdb

from backend.db.connection import get_db_connection
from backend.feedback.override_engine import apply_raw_sensor_override, reset_runtime_state
from backend.conflicts.conflict_engine import (
    ConflictRecord,
    ConflictPartyClaim,
    ConflictEngine,
    check_correction_conflict,
    evaluate_operational_claim,
    get_active_conflicts_for_well,
    audit_inspection_conflicts,
)


@pytest.fixture(autouse=True)
def clean_runtime_state():
    """Ensure clean runtime state before and after each test."""
    con = get_db_connection()
    reset_runtime_state(con)
    yield
    reset_runtime_state(con)


def test_12_1_conflict_record_pydantic_schema():
    """Checkpoint 12.1: ConflictRecord model schema validation."""
    record = ConflictRecord(
        conflict_type="CORRECTION_VS_INSPECTOR_REMARK",
        asset_id="WELL-0164",
        inspection_id="INS-0164-0205",
        winning_truth_summary="41.0 C remeasurement indicates producing, but inspector noted pump jack not moving.",
        claim_a=ConflictPartyClaim(
            author_name="Michael Turner",
            source_type="user_chat_claim",
            claim_text="Remeasured at 41.0 C"
        ),
        claim_b=ConflictPartyClaim(
            author_name="Tyler Hughes",
            source_type="sensor_inspection",
            claim_text="Pump jack not moving."
        ),
        citations=["INS-0164-0205"],
        verification_status="UNCONFIRMED_CLAIM",
        requires_user_confirmation=True,
    )

    assert record.conflict_type == "CORRECTION_VS_INSPECTOR_REMARK"
    assert record.asset_id == "WELL-0164"
    assert record.inspection_id == "INS-0164-0205"
    assert record.claim_a.author_name == "Michael Turner"
    assert record.claim_b.claim_text == "Pump jack not moving."
    assert record.citations == ["INS-0164-0205"]
    assert record.requires_user_confirmation is True


def test_12_2_q12_correction_vs_inspector_remark():
    """Checkpoint 12.2: ConflictEngine detects CORRECTION_VS_INSPECTOR_REMARK on WELL-0164."""
    con = get_db_connection()
    conflict = check_correction_conflict(
        asset_id="WELL-0164",
        inspection_id="INS-0164-0205",
        new_temp=41.0,
        author_name="Michael Turner",
        con=con,
    )

    assert conflict is not None
    assert conflict.conflict_type == "CORRECTION_VS_INSPECTOR_REMARK"
    assert conflict.asset_id == "WELL-0164"
    assert conflict.inspection_id == "INS-0164-0205"
    assert conflict.requires_user_confirmation is True
    assert "Pump jack not moving" in conflict.claim_b.claim_text
    assert conflict.claim_b.author_name == "Tyler Hughes"


def test_12_3_q15_active_conflicts_for_well_0164():
    """Checkpoint 12.3: get_active_conflicts_for_well('WELL-0164') returns active conflict for Jessica Reed."""
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

    conflicts = get_active_conflicts_for_well("WELL-0164", con=con)
    assert len(conflicts) >= 1
    c = conflicts[0]
    assert c.conflict_type == "CORRECTION_VS_INSPECTOR_REMARK"
    assert c.asset_id == "WELL-0164"
    assert c.claim_a.author_name == "Michael Turner"
    assert "Tyler Hughes" in c.claim_b.author_name
    assert "Pump jack not moving" in c.claim_b.claim_text


def test_12_4_q17_step1_turner_shutin_confirmed():
    """Checkpoint 12.4: Turner's shut-in on WELL-0175 matches INS-0175-0204 (0.4 C delta), logged CONFIRMED."""
    con = get_db_connection()
    res = evaluate_operational_claim(
        asset_id="WELL-0175",
        statement="WELL-0175 has been shut in for planned work since 14 Oct.",
        author_name="Michael Turner",
        con=con,
    )

    assert res["verification_status"] == "CONFIRMED"
    assert res["contradicts_sensor_data"] is False
    assert res["conflict"] is None
    assert res["note_id"] is not None

    # Check database
    row = con.execute(
        "SELECT verification_status, contradicts_sensor_data, is_planned_shutin FROM enriched_context_notes WHERE note_id = ?",
        [res["note_id"]]
    ).fetchone()
    assert row[0] == "CONFIRMED"
    assert row[1] is False
    assert row[2] is True


def test_12_5_q17_step2_hughes_claim_vs_telemetry_and_peer():
    """Checkpoint 12.5: Hughes's 'running fine' flagged as CLAIM_VS_TELEMETRY_AND_PEER_NOTE."""
    con = get_db_connection()
    # First apply Turner's note
    evaluate_operational_claim(
        asset_id="WELL-0175",
        statement="WELL-0175 has been shut in for planned work since 14 Oct.",
        author_name="Michael Turner",
        con=con,
    )

    # Now Hughes claims it's running fine
    res = evaluate_operational_claim(
        asset_id="WELL-0175",
        statement="WELL-0175 is running fine.",
        author_name="Tyler Hughes",
        con=con,
    )

    assert res["verification_status"] == "UNCONFIRMED_CLAIM"
    assert res["contradicts_sensor_data"] is True
    assert res["has_peer_disagreement"] is True
    assert res["conflict"] is not None

    conflict = res["conflict"]
    assert conflict.conflict_type == "CLAIM_VS_TELEMETRY_AND_PEER_NOTE"
    assert conflict.asset_id == "WELL-0175"
    assert conflict.requires_user_confirmation is True
    assert "INS-0175-0204" in conflict.citations
    assert any("CTX-" in c for c in conflict.citations)


def test_12_6_context_notes_preserves_both_turner_and_hughes():
    """Checkpoint 12.6: enriched_context_notes has both Turner's CONFIRMED and Hughes's UNCONFIRMED_CLAIM."""
    con = get_db_connection()
    evaluate_operational_claim(
        asset_id="WELL-0175",
        statement="WELL-0175 has been shut in for planned work since 14 Oct.",
        author_name="Michael Turner",
        con=con,
    )
    evaluate_operational_claim(
        asset_id="WELL-0175",
        statement="WELL-0175 is running fine.",
        author_name="Tyler Hughes",
        con=con,
    )

    notes = con.execute(
        """
        SELECT author_name, verification_status, contradicts_sensor_data, note_text
        FROM enriched_context_notes
        WHERE asset_id = 'WELL-0175' AND source_origin = 'runtime_user_chat'
        ORDER BY created_at ASC
        """
    ).fetchall()

    assert len(notes) == 2
    assert notes[0][0] == "Michael Turner"
    assert notes[0][1] == "CONFIRMED"
    assert notes[0][2] is False

    assert notes[1][0] == "Tyler Hughes"
    assert notes[1][1] == "UNCONFIRMED_CLAIM"
    assert notes[1][2] is True


def test_12_7_q17_step3_morales_claim_vs_schedule():
    """Checkpoint 12.7: Morales's claim on WELL-0001 flagged as CLAIM_VS_TELEMETRY_AND_SCHEDULE."""
    con = get_db_connection()
    res = evaluate_operational_claim(
        asset_id="WELL-0001",
        statement="WELL-0001 is back online since 14 Oct.",
        author_name="Jake Morales",
        con=con,
    )

    assert res["verification_status"] == "UNCONFIRMED_CLAIM"
    assert res["contradicts_sensor_data"] is True
    assert res["conflict"] is not None

    conflict = res["conflict"]
    assert conflict.conflict_type == "CLAIM_VS_TELEMETRY_AND_SCHEDULE"
    assert conflict.asset_id == "WELL-0001"
    assert conflict.requires_user_confirmation is True
    assert "INS-0001-0203" in conflict.citations
    assert "CTX-0001-003" in conflict.citations

    # Check status of WELL-0001 in view is still not producing
    status = con.execute("SELECT is_producing FROM v_well_current_status WHERE asset_id = 'WELL-0001'").fetchone()[0]
    assert status is False


def test_12_8_q18_peer_disagreement_on_spill():
    """Checkpoint 12.8: Q18 WELL-0101 spill detection stands; CTX-0101-002 vs CTX-0101-003 and MNT-0101-029 cited."""
    con = get_db_connection()
    conflict = audit_inspection_conflicts("WELL-0101", "2026-08-20", con=con)

    assert conflict is not None
    assert conflict.conflict_type == "PEER_NOTES_DISAGREEMENT"
    assert conflict.asset_id == "WELL-0101"
    assert conflict.inspection_id == "INS-0101-0197"
    assert "stands as real oil" in conflict.winning_truth_summary
    assert conflict.claim_a.author_name == "Ryan Brooks"
    assert conflict.claim_b.author_name == "Chris Dalton"
    assert "INS-0101-0197" in conflict.citations
    assert "CTX-0101-002" in conflict.citations
    assert "CTX-0101-003" in conflict.citations
    assert "MNT-0101-029" in conflict.citations


def test_12_9_conflict_records_carry_structured_citations():
    """Checkpoint 12.9: All conflict records carry citations ready for UI badge rendering."""
    con = get_db_connection()
    # Check 1: Correction conflict
    c1 = check_correction_conflict("WELL-0164", "INS-0164-0205", 41.0, "Michael Turner", con=con)
    assert len(c1.citations) >= 1
    assert c1.citations[0].startswith("INS-")

    # Check 2: Spill conflict
    c2 = audit_inspection_conflicts("WELL-0101", "INS-0101-0197", con=con)
    assert len(c2.citations) == 4
    for cit in c2.citations:
        assert any(cit.startswith(prefix) for prefix in ["INS-", "CTX-", "MNT-"])


def test_12_10_reset_runtime_state_clears_unconfirmed_claims():
    """Checkpoint 12.10: reset_runtime_state clears unconfirmed claims."""
    con = get_db_connection()
    evaluate_operational_claim("WELL-0175", "WELL-0175 is running fine.", "Tyler Hughes", con=con)
    evaluate_operational_claim("WELL-0001", "WELL-0001 is back online since 14 Oct.", "Jake Morales", con=con)

    # Before reset, there are runtime notes
    count_before = con.execute("SELECT COUNT(*) FROM enriched_context_notes WHERE source_origin = 'runtime_user_chat'").fetchone()[0]
    assert count_before >= 2

    # Reset
    reset_runtime_state(con)

    # After reset, zero runtime notes
    count_after = con.execute("SELECT COUNT(*) FROM enriched_context_notes WHERE source_origin = 'runtime_user_chat'").fetchone()[0]
    assert count_after == 0

    conflicts_175 = get_active_conflicts_for_well("WELL-0175", con=con)
    assert len(conflicts_175) == 0
