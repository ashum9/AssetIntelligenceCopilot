"""Phase 21.2: Hardened Write Path & Asymmetric Verification Test Suite.

Verifies:
1. Propose -> Diff: Proposals stage without modifying database until confirmed.
2. Obligation-adding overrides (e.g. volume 4.5 -> 5.4 bbl) commit with single signer.
3. Obligation-reducing overrides (e.g. volume 5.4 -> 2.1 bbl) are blocked if non-supervisor attempts commit without second signer.
4. Obligation-reducing overrides succeed when a Supervisor approves or a dual signer signs.
"""

import os
import shutil
import tempfile
import pytest
import duckdb

from backend.feedback.hardened_write_path import (
    propose_override,
    confirm_and_commit_override,
)


@pytest.fixture
def forked_db():
    """Create a cheap isolated forked snapshot of the database."""
    temp_db = tempfile.mktemp(suffix=".duckdb")
    shutil.copy2("artifacts/copilot.duckdb", temp_db)
    con = duckdb.connect(database=temp_db, read_only=False)
    yield con
    con.close()
    if os.path.exists(temp_db):
        os.unlink(temp_db)


def test_hardened_write_1_propose_diff_uncommitted(forked_db):
    """Verify that proposing an override generates a typed diff without mutating the database."""
    con = forked_db
    
    # Propose spill volume change from 4.5 to 5.4 bbl
    prop = propose_override(
        user_id="U-201",
        user_name="Michael Turner",
        user_role="production_supervisor",
        override_type="spill_volume",
        asset_id="WELL-0151",
        target_field="spill_est_volume_bbl",
        old_value=4.5,
        proposed_value=5.4,
        rationale="Field measurement indicated higher pooling",
        inspection_id_or_date="2026-09-24",
        con=con,
    )

    assert prop["proposal_id"].startswith("PROP-")
    assert prop["status"] == "AWAITING_CONFIRMATION"
    assert prop["diff"]["change_delta"] == 0.9
    assert prop["impact_preview"]["crosses_5bbl_threshold"] is True

    # Database must remain UNCHANGED before confirmation
    row = con.execute("SELECT effective_spill_volume_bbl FROM v_spill_compliance_audit WHERE inspection_id = 'INS-0151-0201'").fetchone()
    assert row[0] == 4.5, "Database was mutated before explicit confirmation!"


def test_hardened_write_2_obligation_adding_single_signer(forked_db):
    """Verify that obligation-adding overrides commit cleanly with single signer."""
    con = forked_db
    
    prop = propose_override(
        user_id="U-102",
        user_name="Jake Morales",
        user_role="field_operator",
        override_type="spill_volume",
        asset_id="WELL-0151",
        target_field="spill_est_volume_bbl",
        old_value=4.5,
        proposed_value=5.4,
        rationale="Operator measured 5.4 bbl crude",
        inspection_id_or_date="2026-09-24",
        con=con,
    )

    assert prop["governance"]["is_obligation_reducing"] is False
    assert prop["governance"]["requires_second_signer"] is False

    # Confirm and commit
    res = confirm_and_commit_override(
        proposal_id=prop["proposal_id"],
        approver_user_id="U-102",
        approver_user_name="Jake Morales",
        approver_user_role="field_operator",
        con=con,
    )

    assert res["status"] == "COMMITTED"
    row = con.execute("SELECT effective_spill_volume_bbl FROM v_spill_compliance_audit WHERE inspection_id = 'INS-0151-0201'").fetchone()
    assert row[0] == 5.4


def test_hardened_write_3_asymmetric_verification_blocks_unauthorized_reduction(forked_db):
    """Verify that obligation-reducing overrides are blocked if a non-supervisor attempts commit alone."""
    con = forked_db
    
    # Operator attempts to revise spill volume down from 5.4 to 1.2 bbl
    prop = propose_override(
        user_id="U-102",
        user_name="Jake Morales",
        user_role="field_operator",
        override_type="spill_volume",
        asset_id="WELL-0151",
        target_field="spill_est_volume_bbl",
        old_value=5.4,
        proposed_value=1.2,
        rationale="Looks much smaller now",
        inspection_id_or_date="2026-09-24",
        con=con,
    )

    assert prop["governance"]["is_obligation_reducing"] is True
    assert prop["governance"]["requires_second_signer"] is True

    # Operator attempts self-commit without second signer -> MUST FAIL
    with pytest.raises(PermissionError) as exc_info:
        confirm_and_commit_override(
            proposal_id=prop["proposal_id"],
            approver_user_id="U-102",
            approver_user_name="Jake Morales",
            approver_user_role="field_operator",
            second_signer_user_id=None,
            con=con,
        )

    assert "requires supervisor approval or a secondary signer" in str(exc_info.value)


def test_hardened_write_4_asymmetric_verification_succeeds_with_supervisor(forked_db):
    """Verify that obligation-reducing override succeeds when supervisor confirms."""
    con = forked_db
    
    prop = propose_override(
        user_id="U-102",
        user_name="Jake Morales",
        user_role="field_operator",
        override_type="spill_volume",
        asset_id="WELL-0151",
        target_field="spill_est_volume_bbl",
        old_value=5.4,
        proposed_value=1.2,
        rationale="Lab soil analysis confirms mostly brine",
        inspection_id_or_date="2026-09-24",
        con=con,
    )

    # Supervisor approves
    res = confirm_and_commit_override(
        proposal_id=prop["proposal_id"],
        approver_user_id="U-201",
        approver_user_name="Michael Turner",
        approver_user_role="production_supervisor",
        con=con,
    )

    assert res["status"] == "COMMITTED"
    assert res["governance_audit"]["approver"] == "Michael Turner"
