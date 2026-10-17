"""Phase 21.3: Active Probing & EVOI Engine Verification Suite.

Tests:
1. Critical boundary test (Q13 4.5 bbl vs 5.0 bbl threshold):
   - Confirms ~29% probability of exceeding major reporting threshold under 20% CV error.
   - Confirms positive EVOI (+>$1,200) against $5,000 potential fine.
   - Confirms probe recommendation card generated within 24h window.
2. Low-risk boundary test (0.8 bbl):
   - Confirms negligible exceedance probability, negative EVOI, zero probe dispatched.
3. Expired window test (> 24 hours):
   - Confirms probe is not recommended for statutory window that has already lapsed.
"""

import pytest

from backend.probing.evoi_engine import (
    calculate_spill_boundary_evoi,
    PROBE_CATALOG,
)


def test_evoi_1_critical_boundary_q13_well0151():
    """Verify EVOI calculation for WELL-0151 with 4.5 bbl detection at 6 hours post-discovery."""
    res = calculate_spill_boundary_evoi(
        asset_id="WELL-0151",
        inspection_id="INS-0151-0201",
        detected_volume_bbl=4.5,
        hours_since_detection=6.0,
        threshold_bbl=5.0,
        drone_cv_error_cv=0.20,
        potential_penalty_usd=5000.0,
        selected_probe_id="OPERATOR_MANUAL_MEASURE",
    )

    # 4.5 bbl with 0.90 sigma puts 5.0 bbl at z = 0.555 -> P(>=5.0) ~ 28.9%
    assert 0.25 <= res["prob_exceeds_threshold"] <= 0.32
    assert res["expected_fine_without_probe_usd"] > 1200.0
    assert res["evoi_usd"] > 1000.0
    assert res["should_probe"] is True
    assert res["hours_remaining_in_window"] == 18.0
    assert res["probe_spec"] is not None
    assert res["probe_spec"]["cost_usd"] == 150.0


def test_evoi_2_low_volume_negative_evoi():
    """Verify that a minor spill of 0.8 bbl results in negligible risk and no probe."""
    res = calculate_spill_boundary_evoi(
        asset_id="WELL-0020",
        inspection_id="INS-0020-0100",
        detected_volume_bbl=0.8,
        hours_since_detection=2.0,
        threshold_bbl=5.0,
    )

    assert res["prob_exceeds_threshold"] < 0.001
    assert res["evoi_usd"] < 0.0
    assert res["should_probe"] is False
    assert res["probe_spec"] is None


def test_evoi_3_expired_statutory_window():
    """Verify that an inspection discovered 30 hours ago cannot prevent SR-01 24h breach."""
    res = calculate_spill_boundary_evoi(
        asset_id="WELL-0151",
        inspection_id="INS-0151-0201",
        detected_volume_bbl=4.8,
        hours_since_detection=30.0,
    )

    assert res["hours_remaining_in_window"] == 0.0
    assert res["should_probe"] is False
