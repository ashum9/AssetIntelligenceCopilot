"""Phase 15 Verification Suite: Declarative Generative UI Schema & Visual Auto-Hydrator.

Tests:
  15.1: Q1 emits StatusCardSpec for WELL-0001 with delta=3.2, required=15.0, producing=False, stale=True.
  15.2: Q2, Q4, Q9, Q10 emit TableSpec with exact row counts (4, 6, 6, 2).
  15.3: Q3 emits LineChartSpec with 13 data points and markers on 2026-10-08, 2026-10-15.
  15.4: Q5 emits ShortAnswerSpec (visual_type == 'none') with MNT-0001-021 and MNT-0001-023 citations.
  15.5: Q6 emits BarChartSpec with bars for 121 (49), 138 (42), 107 (42), 119 (28).
  15.6: Q7 emits MapSpec with 4 pins for WELL-0151, WELL-0165, WELL-0175, WELL-0186.
  15.7: Q8 emits HeatmapSpec (4 areas x 10 months, 35, 43, 37, 26, total 141) + OverrideDiffBadge.
  15.8: Explicit visual override: 'Show it as a table' forces table; 'Show a bar chart' forces bar_chart.
  15.9: Q12, Q13, Q14, Q15 populate override_badges[] with exact diffs.
  15.10: Q12, Q15, Q17, Q18 populate conflict_cards[] with structured claims and citations.
"""

import pytest
import duckdb

from backend.db.connection import get_db_connection
from backend.feedback.override_engine import reset_runtime_state
from backend.agent.orchestrator import CopilotOrchestrator
from backend.schemas.generative_ui import (
    StatusCardSpec,
    TableSpec,
    LineChartSpec,
    BarChartSpec,
    MapSpec,
    HeatmapSpec,
    ShortAnswerSpec,
)


@pytest.fixture(autouse=True)
def clean_state():
    con = get_db_connection()
    reset_runtime_state(con)
    yield
    reset_runtime_state(con)


def test_15_1_q1_status_card_spec():
    """Checkpoint 15.1: Q1 emits StatusCardSpec with delta=3.2, required=15.0, producing=False, stale=True."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Is WELL-0001 producing oil right now? Explain how you know.", "Michael Turner")

    assert resp.visual_payload.visual_type == "status_card"
    card: StatusCardSpec = resp.visual_payload
    assert card.asset_id == "WELL-0001"
    assert card.temp_delta_c == 3.2
    assert card.required_temp_delta_c == 15.0
    assert card.is_producing is False
    assert card.is_recorded_status_stale is True
    assert card.status_badge_label == "SHUT-IN (PLANNED)"


def test_15_2_q2_q4_q9_q10_table_specs_row_counts():
    """Checkpoint 15.2: Q2 (4 rows), Q4 (6 rows), Q9 (6 rows), Q10 (2 rows) emit TableSpec."""
    orch = CopilotOrchestrator()

    # Q2: 4 non-producing wells before Q12
    resp2 = orch.ask("Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.", "Michael Turner")
    assert resp2.visual_payload.visual_type == "table"
    assert len(resp2.visual_payload.rows) == 4

    # Q4: 6 verified spills at WELL-0001
    resp4 = orch.ask("List all verified spills at WELL-0001 in 2026 with their dates and volumes.", "Michael Turner")
    assert resp4.visual_payload.visual_type == "table"
    assert len(resp4.visual_payload.rows) == 6

    # Q9: 4 breaches + 2 pending = 6 rows
    resp9 = orch.ask("Which regulatory compliance issues are currently open or unresolved in Southwest Block 24?", "Michael Turner")
    assert resp9.visual_payload.visual_type == "table"
    assert len(resp9.visual_payload.rows) == 6

    # Q10: 2 spills not contained within SOP limit
    resp10 = orch.ask("In Southwest Block 24, which spills in the last 90 days were not contained within the SOP time limit?", "Michael Turner")
    assert resp10.visual_payload.visual_type == "table"
    assert len(resp10.visual_payload.rows) == 2


def test_15_3_q3_line_chart_spec():
    """Checkpoint 15.3: Q3 emits LineChartSpec with 13 data points and markers on 2026-10-08 and 2026-10-15."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Show the weekly wellhead and ambient temperatures for WELL-0001 over the last 13 weeks. On which dates was it not producing oil?", "Michael Turner")

    assert resp.visual_payload.visual_type == "line_chart"
    chart: LineChartSpec = resp.visual_payload
    assert len(chart.data_points) == 13
    assert chart.threshold_line["value"] == 15.0
    assert "2026-10-08" in chart.non_producing_markers
    assert "2026-10-15" in chart.non_producing_markers


def test_15_4_q5_short_answer_spec():
    """Checkpoint 15.4: Q5 emits ShortAnswerSpec (visual_type == 'none') with MNT-0001-021 and MNT-0001-023 citations."""
    orch = CopilotOrchestrator()
    resp = orch.ask("How many days was WELL-0001 down in 2025?", "Michael Turner")

    assert resp.visual_payload.visual_type == "none"
    assert "21 days" in resp.markdown_answer
    cit_ids = [c.citation_id for c in resp.citations]
    assert any("MNT-0001-021" in cid for cid in cit_ids)
    assert any("MNT-0001-023" in cid for cid in cit_ids)


def test_15_5_q6_bar_chart_spec():
    """Checkpoint 15.5: Q6 emits BarChartSpec with bars for 121 (49), 138 (42), 107 (42), 119 (28)."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.", "Michael Turner")

    assert resp.visual_payload.visual_type == "bar_chart"
    chart: BarChartSpec = resp.visual_payload
    bar_map = {b.asset_id: int(b.value) for b in chart.bars}
    assert bar_map["WELL-0121"] == 49
    assert bar_map["WELL-0138"] == 42
    assert bar_map["WELL-0107"] == 42
    assert bar_map["WELL-0119"] == 28


def test_15_6_q7_map_spec():
    """Checkpoint 15.6: Q7 emits MapSpec with 4 pins for WELL-0151, WELL-0165, WELL-0175, WELL-0186."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Show all spills detected in Northeast Block 8 this year on a map.", "Michael Turner")

    assert resp.visual_payload.visual_type == "map"
    map_spec: MapSpec = resp.visual_payload
    assert len(map_spec.pins) == 4
    pin_wells = [p.asset_id for p in map_spec.pins]
    assert set(pin_wells) == {"WELL-0151", "WELL-0165", "WELL-0175", "WELL-0186"}
    for p in map_spec.pins:
        assert p.lat != 0.0
        assert p.lon != 0.0
        assert p.volume_bbl > 0.0


def test_15_7_q8_heatmap_spec_and_override_badge():
    """Checkpoint 15.7: Q8 emits HeatmapSpec summing to 35, 43, 37, 26 (141 total) + OverrideDiffBadge."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Produce a monthly heatmap of spill counts by area for 2026.", "Michael Turner")

    assert resp.visual_payload.visual_type == "heatmap"
    hm: HeatmapSpec = resp.visual_payload
    assert hm.grand_total == 141
    assert hm.row_totals == [35, 43, 37, 26]
    assert len(resp.override_badges) >= 1
    assert "CTX-0001-001" in resp.override_badges[0].citation_id


def test_15_8_explicit_visual_preference_override():
    """Checkpoint 15.8: User prompt specifying 'Show it as a table' forces table format."""
    orch = CopilotOrchestrator()

    # WELL-0001 defaults to status_card, but user asks for table
    resp_table = orch.ask("Is WELL-0001 producing oil right now? Show it as a table.", "Michael Turner")
    assert resp_table.visual_payload.visual_type == "table"

    # User asks for bar chart
    resp_bar = orch.ask("Is WELL-0001 producing oil right now? Show a bar chart.", "Michael Turner")
    assert resp_bar.visual_payload.visual_type == "bar_chart"


def test_15_9_override_diff_badges_populated():
    """Checkpoint 15.9: Q12, Q13, Q14, Q15 populate override_badges[] with exact diffs."""
    orch = CopilotOrchestrator()

    # Q12
    resp12 = orch.ask("The 15 Oct reading for WELL-0164 is wrong. The handheld thermal gun used in that inspection was faulty; the field crew re-measured the wellhead at 41.0 °C.", "Michael Turner")
    assert len(resp12.override_badges) == 1
    assert resp12.override_badges[0].old_value_display == "24.0 °C"
    assert resp12.override_badges[0].new_value_display == "41.0 °C"

    # Q13
    resp13 = orch.ask("The AI estimated the 24 Sep spill at WELL-0151 as 4.5 bbl. The field crew measured 5.4 bbl.", "Michael Turner")
    assert len(resp13.override_badges) == 1
    assert resp13.override_badges[0].old_value_display == "4.5 bbl"
    assert resp13.override_badges[0].new_value_display == "5.4 bbl"

    # Q14
    resp14 = orch.ask("Note for all T350 wells: our team now wants a pump jack root-cause analysis after 2 repairs, not 3.", "Michael Turner")
    assert len(resp14.override_badges) == 1
    assert resp14.override_badges[0].old_value_display == "3 repairs"
    assert resp14.override_badges[0].new_value_display == "2 repairs"

    # Q15 Part 2
    resp15 = orch.ask("Which spills in Northeast Block 8 in the last 90 days needed a report to the regulator?", "Laura Simmons")
    assert len(resp15.override_badges) == 1
    assert resp15.override_badges[0].new_value_display == "5.4 bbl"


def test_15_10_conflict_alert_cards_populated():
    """Checkpoint 15.10: Q12, Q15, Q17, Q18 populate conflict_cards[] with structured claims."""
    orch = CopilotOrchestrator()

    # Q12
    resp12 = orch.ask("The 15 Oct reading for WELL-0164 is wrong. The handheld thermal gun used in that inspection was faulty; the field crew re-measured the wellhead at 41.0 °C.", "Michael Turner")
    assert len(resp12.conflict_cards) == 1
    assert resp12.conflict_cards[0].severity == "WARNING"
    assert resp12.conflict_cards[0].requires_confirmation is True

    # Q15 Part 1
    resp15 = orch.ask("Is WELL-0164 producing oil right now?", "Jessica Reed")
    assert len(resp15.conflict_cards) == 1
    assert "Tyler Hughes" in resp15.conflict_cards[0].claim_b_source or "Tyler Hughes" in resp15.conflict_cards[0].claim_b_text

    # Q17 Tyler Hughes on WELL-0175
    orch.ask("WELL-0175 has been shut in for planned work since 14 Oct.", "Michael Turner")
    resp17 = orch.ask("WELL-0175 is running fine.", "Tyler Hughes")
    assert len(resp17.conflict_cards) == 1
    assert resp17.conflict_cards[0].severity == "UNCONFIRMED_CLAIM"
    assert resp17.conflict_cards[0].requires_confirmation is True

    # Q18 WELL-0101 spill
    resp18 = orch.ask("Was the 20 Aug spill at WELL-0101 real oil?", "Michael Turner")
    assert len(resp18.conflict_cards) == 1
    assert resp18.conflict_cards[0].severity == "DISPUTE"
