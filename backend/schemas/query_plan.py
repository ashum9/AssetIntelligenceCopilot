"""Typed Query Plan & Epistemic Separation of Belief vs. Record of Reference.

Implements the Senior Researcher's core architectural move:
1. The LLM emits a strictly validated QueryPlan (metric, filters, window, grouping)
   rather than typing numbers or raw SQL.
2. Echoes the temporal interpretation ('last 4 months -> 16 Jun to 16 Oct 2026')
   to make ambiguous windows visible engineering assumptions.
3. Decouples:
   - Evidence Ledger: Raw bitemporal telemetry, observations, operator notes.
   - Belief State: Calibrated probability over latent operational facts.
   - Record of Reference: What the organization officially treats as true under policy.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryMetric(str, Enum):
    CURRENT_STATUS = "current_status"
    DOWNTIME_DAYS = "downtime_days"
    SPILL_COUNT = "spill_count"
    SPILL_VOLUME = "spill_volume"
    REPAIR_COST = "repair_cost"
    RCA_CANDIDATES = "rca_candidates"
    REGULATORY_BREACHES = "regulatory_breaches"
    CONTRADICTIONS = "contradictions"


class TemporalWindow(BaseModel):
    natural_language_expression: str = Field(..., description="User's expression, e.g. 'last 4 months'")
    start_date: str = Field(..., description="ISO 8601 start date, e.g. '2026-06-16'")
    end_date: str = Field(..., description="ISO 8601 end date, e.g. '2026-10-17'")
    echo_interpretation: str = Field(..., description="Human-auditable explanation of window derivation")


class QueryPlan(BaseModel):
    plan_id: str
    target_metric: QueryMetric
    target_asset_ids: List[str] = Field(default_factory=list)
    target_areas: List[str] = Field(default_factory=list)
    target_well_types: List[str] = Field(default_factory=list)
    temporal_window: Optional[TemporalWindow] = None
    group_by: List[str] = Field(default_factory=list)
    limit: Optional[int] = None
    validated_against_schema: bool = True


class BeliefState(BaseModel):
    """Epistemic probability distribution over latent reality."""
    asset_id: str
    latent_producing_prob: float = Field(..., ge=0.0, le=1.0)
    latent_spill_reality_prob: Optional[float] = Field(None, ge=0.0, le=1.0)
    expected_true_volume_bbl: Optional[float] = None
    epistemic_confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_sources_evaluated: List[str] = Field(default_factory=list)


class RecordOfReference(BaseModel):
    """Normative organizational truth under governing operating procedures."""
    asset_id: str
    official_status: str
    official_spill_volume_bbl: Optional[float] = None
    governing_sop_rule: str
    has_active_user_override: bool = False
    authoritative_citation: str
    as_of_recorded_date: str


class DualEpistemicDuo(BaseModel):
    """Surfaces the transparent gap between epistemic belief and normative record."""
    asset_id: str
    record_of_reference: RecordOfReference
    belief_state: BeliefState
    divergence_detected: bool = False
    divergence_reason: Optional[str] = None
    suggested_probe_action: Optional[str] = None

    def render_synthesis(self) -> str:
        """Render the exact transparent synthesis recommended by Senior Researcher."""
        if not self.divergence_detected:
            return f"Record shows {self.asset_id} is {self.record_of_reference.official_status}. Epistemic belief aligns ({self.belief_state.epistemic_confidence*100:.0f}% confidence)."
        
        return (
            f"The record of reference shows {self.asset_id} as '{self.record_of_reference.official_status}' "
            f"under {self.record_of_reference.authoritative_citation}. "
            f"However, epistemic belief state is uncertain (p_producing = {self.belief_state.latent_producing_prob*100:.1f}%) "
            f"due to: {self.divergence_reason}. "
            f"Suggested resolution: {self.suggested_probe_action}."
        )
