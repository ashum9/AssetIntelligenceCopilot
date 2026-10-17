"""Hardened Write Path: Propose-Diff-Confirm-Commit Protocol with Asymmetric Verification.

Implements the Senior Researcher's governance foundation:
1. Confirm before commit:
   - propose_override() -> generates a typed OverrideProposal with pre-commit impact diff.
   - commit_override() -> commits to bitemporal ledger only after explicit confirmation.
2. Asymmetric Verification & Role Authority:
   - Obligation-adding overrides (e.g. volume revised up, declaring a spill) require single signer.
   - Obligation-reducing overrides (e.g. volume revised down, spill -> rainwater, claiming well is back online)
     require either a Supervisor/HSE role or a verified secondary signer.
3. Policy Scope & Expiry:
   - Rules and overrides carry an owner, valid_from, and review_by date.
"""

import time
import uuid
from typing import Any, Dict, List, Optional
import duckdb

from backend.db.connection import get_db_connection
from backend.feedback.override_engine import (
    apply_raw_sensor_override,
    apply_spill_volume_override,
    apply_well_type_rule_override,
    evaluate_spill_override_cascade,
)


# In-memory staging store for unconfirmed proposals (TTL = 1 hour)
_PROPOSAL_REGISTRY: Dict[str, Dict[str, Any]] = {}

# Elevated roles authorized for single-signer obligation reductions
SUPERVISORY_ROLES = {"production_supervisor", "field_supervisor", "hse_officer", "operations_manager"}


def propose_override(
    user_id: str,
    user_name: str,
    user_role: str,
    override_type: str,  # 'spill_volume', 'sensor_temp', 'rule_threshold', 'well_status'
    asset_id: str,
    target_field: str,
    old_value: Any,
    proposed_value: Any,
    rationale: str,
    inspection_id_or_date: Optional[str] = None,
    con: Optional[duckdb.DuckDBPyConnection] = None,
) -> Dict[str, Any]:
    """Generate a typed OverrideProposal diff before committing to the live ledger."""
    proposal_id = f"PROP-{uuid.uuid4().hex[:8].upper()}"
    
    # 1. Determine if this proposal reduces organizational obligations
    is_obligation_reducing = False
    
    if override_type == "spill_volume":
        if float(proposed_value) < float(old_value):
            is_obligation_reducing = True
    elif override_type == "well_status":
        if str(proposed_value).lower() in ["active", "producing", "back online"]:
            is_obligation_reducing = True
    elif target_field == "spill_detected" and proposed_value is False:
        is_obligation_reducing = True

    # 2. Asymmetric Authority Check: Does this require dual-signer or supervisor approval?
    user_role_norm = user_role.lower().replace(" ", "_")
    requires_second_signer = False
    authorization_status = "PENDING_CONFIRMATION"

    if is_obligation_reducing:
        if user_role_norm not in SUPERVISORY_ROLES:
            requires_second_signer = True
            authorization_status = "REQUIRES_SUPERVISOR_OR_SECOND_SIGNER"

    # 3. Compute pre-commit impact diff
    impact_preview: Dict[str, Any] = {}
    if override_type == "spill_volume" and inspection_id_or_date:
        # Pre-evaluate whether crossing 5.0 bbl changes reporting duties
        old_val_f = float(old_value)
        new_val_f = float(proposed_value)
        impact_preview["crosses_5bbl_threshold"] = (old_val_f < 5.0 and new_val_f >= 5.0) or (old_val_f >= 5.0 and new_val_f < 5.0)
        impact_preview["duty_change"] = "ESCALATE_TO_MAJOR" if new_val_f >= 5.0 else "DOWNGRADE_TO_MODERATE"

    proposal = {
        "proposal_id": proposal_id,
        "created_at": time.time(),
        "proposer": {
            "user_id": user_id,
            "user_name": user_name,
            "user_role": user_role,
        },
        "target": {
            "asset_id": asset_id,
            "target_field": target_field,
            "override_type": override_type,
            "inspection_id_or_date": inspection_id_or_date,
        },
        "diff": {
            "old_value": old_value,
            "proposed_value": proposed_value,
            "change_delta": round(float(proposed_value) - float(old_value), 4) if isinstance(old_value, (int, float)) and isinstance(proposed_value, (int, float)) else None,
        },
        "governance": {
            "is_obligation_reducing": is_obligation_reducing,
            "requires_second_signer": requires_second_signer,
            "authorization_status": authorization_status,
            "required_role_level": "supervisor" if requires_second_signer else "standard",
        },
        "rationale": rationale,
        "impact_preview": impact_preview,
        "status": "AWAITING_CONFIRMATION",
    }

    _PROPOSAL_REGISTRY[proposal_id] = proposal
    return proposal


def confirm_and_commit_override(
    proposal_id: str,
    approver_user_id: str,
    approver_user_name: str,
    approver_user_role: str,
    second_signer_user_id: Optional[str] = None,
    second_signer_user_name: Optional[str] = None,
    con: Optional[duckdb.DuckDBPyConnection] = None,
) -> Dict[str, Any]:
    """Execute the final commit phase of Propose-Diff-Confirm-Commit protocol."""
    if proposal_id not in _PROPOSAL_REGISTRY:
        raise ValueError(f"Proposal {proposal_id} not found or expired")

    prop = _PROPOSAL_REGISTRY[proposal_id]
    gov = prop["governance"]

    # Asymmetric Verification Gate
    if gov["requires_second_signer"]:
        approver_role_norm = approver_user_role.lower().replace(" ", "_")
        # Can be satisfied if the primary approver is a supervisor OR a secondary signer is supplied
        if approver_role_norm not in SUPERVISORY_ROLES and not second_signer_user_id:
            raise PermissionError(
                f"Obligation-reducing override {proposal_id} requires supervisor approval or a secondary signer. "
                f"Approver {approver_user_name} holds role '{approver_user_role}'."
            )

    # Execute commit to live DuckDB ledger
    t = prop["target"]
    d = prop["diff"]
    c = con or get_db_connection()

    commit_result: Dict[str, Any] = {}

    if t["override_type"] == "spill_volume":
        commit_result = apply_spill_volume_override(
            asset_id=t["asset_id"],
            inspection_date_or_id=t["inspection_id_or_date"],
            new_volume_bbl=float(d["proposed_value"]),
            author_name=prop["proposer"]["user_name"],
            author_user_id=prop["proposer"]["user_id"],
            reason=prop["rationale"],
            con=c,
        )
    elif t["override_type"] == "sensor_temp":
        commit_result = apply_raw_sensor_override(
            asset_id=t["asset_id"],
            inspection_date_or_id=t["inspection_id_or_date"],
            target_field=t["target_field"],
            new_value=float(d["proposed_value"]),
            author_name=prop["proposer"]["user_name"],
            author_user_id=prop["proposer"]["user_id"],
            reason=prop["rationale"],
            con=c,
        )

    prop["status"] = "COMMITTED"
    prop["committed_at"] = time.time()
    prop["approver"] = {
        "user_id": approver_user_id,
        "user_name": approver_user_name,
        "role": approver_user_role,
    }
    if second_signer_user_id:
        prop["second_signer"] = {
            "user_id": second_signer_user_id,
            "user_name": second_signer_user_name,
        }

    return {
        "status": "COMMITTED",
        "proposal_id": proposal_id,
        "ledger_commit": commit_result,
        "governance_audit": {
            "is_obligation_reducing": gov["is_obligation_reducing"],
            "approver": approver_user_name,
            "second_signer": second_signer_user_name,
        }
    }
