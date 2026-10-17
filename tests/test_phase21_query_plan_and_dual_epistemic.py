"""Phase 21.4: Typed QueryPlan and Dual Epistemic Model Verification Suite.

Tests:
1. Typed QueryPlan: Confirms metric validation and explicit echo interpretation for sliding windows.
2. Dual Epistemic Model (Record vs. Belief): Confirms transparent handling of Q12 (Turner's override vs inspector note).
"""

import pytest

from backend.schemas.query_plan import (
    QueryMetric,
    TemporalWindow,
    QueryPlan,
    BeliefState,
    RecordOfReference,
    DualEpistemicDuo,
)


def test_query_plan_echo_interpretation():
    """Verify that a temporal window produces an auditable echo interpretation."""
    window = TemporalWindow(
        natural_language_expression="last 4 months",
        start_date="2026-06-16",
        end_date="2026-10-17",
        echo_interpretation="Computed as 120 days preceding reference today (17 Oct 2026): 16 Jun to 17 Oct 2026.",
    )

    plan = QueryPlan(
        plan_id="QP-001",
        target_metric=QueryMetric.REPAIR_COST,
        target_areas=["Southwest Block 23"],
        temporal_window=window,
        limit=3,
    )

    assert plan.target_metric == QueryMetric.REPAIR_COST
    assert plan.temporal_window.echo_interpretation.startswith("Computed as 120 days")
    assert plan.validated_against_schema is True


def test_dual_epistemic_synthesis_q12_well0164():
    """Verify Q12 synthesis separating normative record from probabilistic belief."""
    record = RecordOfReference(
        asset_id="WELL-0164",
        official_status="producing",
        governing_sop_rule="Domain Law 4 (Dynamic Technician Override)",
        has_active_user_override=True,
        authoritative_citation="Michael Turner remeasurement (41.0 C, delta 21.1 C >= 20.0 C)",
        as_of_recorded_date="2026-10-15",
    )

    belief = BeliefState(
        asset_id="WELL-0164",
        latent_producing_prob=0.52,  # Near coin-flip
        epistemic_confidence=0.55,
        evidence_sources_evaluated=["INS-0164-0205_telemetry", "Michael_Turner_override", "Ryan_Brooks_note"],
    )

    duo = DualEpistemicDuo(
        asset_id="WELL-0164",
        record_of_reference=record,
        belief_state=belief,
        divergence_detected=True,
        divergence_reason="Ryan Brooks's inspection note logged 'Pump jack not moving' on same date",
        suggested_probe_action="Dispatch acoustic vibration probe or check SCADA motor ammeter",
    )

    synthesis = duo.render_synthesis()
    assert "The record of reference shows WELL-0164 as 'producing'" in synthesis
    assert "p_producing = 52.0%" in synthesis
    assert "Ryan Brooks's inspection note logged 'Pump jack not moving'" in synthesis
    assert "acoustic vibration probe" in synthesis
