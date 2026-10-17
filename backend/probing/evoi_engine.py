"""Active Probing Engine: Expected Value of Information (EVOI) & Probe Dispatch.

Implements the Senior Researcher's Challenge Space 3 foundation:
- Optimizes Expected Value of Information (EVOI), NOT raw entropy.
- Analyzes critical decision boundaries (e.g., 5.0 bbl major spill threshold under SR-01).
- Calculates the probability that an AI computer vision estimate (e.g. 4.5 bbl) crosses the
  statutory compliance threshold under measurement uncertainty (CV error ~ 20%).
- Compares risk of regulatory notice-of-violation fine ($5,000) against probe dispatch cost ($150-$250).
- Emits a typed ProbeSpec recommendation card inside the 24-hour statutory response window.
"""

import math
from typing import Any, Dict, List, Optional


# Standard Probe Action Catalog with costs and turnaround times
PROBE_CATALOG: Dict[str, Dict[str, Any]] = {
    "OPERATOR_MANUAL_MEASURE": {
        "probe_type": "manual_site_visit",
        "label": "Dispatch Field Operator (Direct Physical Gauge)",
        "cost_usd": 150.0,
        "turnaround_hours": 3.0,
        "error_std": 0.05,  # 5% uncertainty
        "target_entity": "wellhead_cellar",
    },
    "DRONE_TARGETED_REFLY": {
        "probe_type": "drone_multispectral_reflight",
        "label": "Automated Drone Re-flight (Multi-angle Photogrammetry)",
        "cost_usd": 220.0,
        "turnaround_hours": 1.5,
        "error_std": 0.10,  # 10% uncertainty
        "target_entity": "spill_perimeter",
    },
    "LAB_SAMPLE_ASSAY": {
        "probe_type": "certified_lab_sample",
        "label": "Certified Hydrocarbon Testing (Rainwater vs Crude)",
        "cost_usd": 450.0,
        "turnaround_hours": 24.0,
        "error_std": 0.01,
        "target_entity": "fluid_sample",
    },
}


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def calculate_spill_boundary_evoi(
    asset_id: str,
    inspection_id: str,
    detected_volume_bbl: float,
    hours_since_detection: float,
    threshold_bbl: float = 5.0,
    drone_cv_error_cv: float = 0.20,  # 20% coefficient of variation
    potential_penalty_usd: float = 5000.0,  # RC-04 / SR-01 statutory fine
    selected_probe_id: str = "OPERATOR_MANUAL_MEASURE",
) -> Dict[str, Any]:
    """Calculate Expected Value of Information for resolving a spill near the 5 bbl boundary.
    
    Under a log-normal or Gaussian observation model:
    Std = detected_volume * 0.20 (e.g. 4.5 * 0.20 = 0.90 bbl).
    Z = (threshold_bbl - detected_volume) / Std = (5.0 - 4.5) / 0.90 = 0.555
    P(True >= 5.0) = 1 - CDF(0.555) ~ 0.289 (roughly 29% chance true volume >= 5.0).
    """
    if detected_volume_bbl <= 0.0:
        return {"evoi_usd": 0.0, "should_probe": False, "reason": "No spill detected"}

    # Measurement uncertainty standard deviation
    std_dev = max(0.1, detected_volume_bbl * drone_cv_error_cv)
    z_score = (threshold_bbl - detected_volume_bbl) / std_dev
    prob_exceeds_threshold = 1.0 - norm_cdf(z_score)

    probe_spec = PROBE_CATALOG.get(selected_probe_id, PROBE_CATALOG["OPERATOR_MANUAL_MEASURE"])
    probe_cost = probe_spec["cost_usd"]

    # Expected penalty under uncertainty if no probe is conducted and operator does not report
    expected_fine_unprobed = prob_exceeds_threshold * potential_penalty_usd

    # Expected Value of Information:
    # A probe resolves the uncertainty with high fidelity, saving the expected fine at probe cost
    evoi_usd = expected_fine_unprobed - probe_cost
    should_probe = (evoi_usd > 0.0) and (hours_since_detection < 24.0)

    # Calculate statutory deadline remaining
    hours_remaining = max(0.0, 24.0 - hours_since_detection)

    return {
        "asset_id": asset_id,
        "inspection_id": inspection_id,
        "detected_volume_bbl": detected_volume_bbl,
        "threshold_bbl": threshold_bbl,
        "prob_exceeds_threshold": round(prob_exceeds_threshold, 4),
        "uncertainty_sigma_bbl": round(std_dev, 2),
        "hours_since_detection": hours_since_detection,
        "hours_remaining_in_window": round(hours_remaining, 1),
        "expected_fine_without_probe_usd": round(expected_fine_unprobed, 2),
        "probe_cost_usd": probe_cost,
        "evoi_usd": round(evoi_usd, 2),
        "should_probe": should_probe,
        "recommended_action": (
            f"DISPATCH_PROBE: Positive EVOI (+${evoi_usd:.2f}). "
            f"{prob_exceeds_threshold*100:.1f}% risk of major spill (>= 5.0 bbl). "
            f"Dispatch probe within {hours_remaining:.1f} hours to avoid potential ${potential_penalty_usd:,.0f} fine."
            if should_probe
            else "NO_PROBE_RECOMMENDED: Negative EVOI or outside statutory window."
        ),
        "probe_spec": {
            "probe_id": selected_probe_id,
            "label": probe_spec["label"],
            "type": probe_spec["probe_type"],
            "turnaround_hours": probe_spec["turnaround_hours"],
            "cost_usd": probe_cost,
        } if should_probe else None,
    }
