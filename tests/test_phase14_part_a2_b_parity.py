"""Phase 14 Verification Suite: Stateful Multi-User Parity Gate (Q11–Q18).

Tests:
  14.1: Q11 memory recall with exact 2026 costs: WELL-0121 ($25,794), WELL-0138 ($46,942), WELL-0107 ($5,176).
  14.2: Q12 raw temp override on WELL-0164 (41.0 C) + conflict card + Q2 table reduction from 4 to 3 wells.
  14.3: Q13 spill override on WELL-0151 (5.4 bbl) + 4 cascading SOP impacts (SR-01, outdated class, SR-02 6.4h, SR-03 23 Nov).
  14.4: Q14 T350 pump jack rule override adds WELL-0120 (T350) and excludes WELL-0102 (T200).
  14.5: Q15 cross-user shared overrides (Jessica Reed on 164, Laura Simmons on 151).
  14.6: Q16 shared knowledge on WELL-0007 vs strict private isolation on Jessica Reed.
  14.7: Q17 contradictory status claims (Tyler Hughes on 175, Jake Morales on 0001).
  14.8: Q18 peer notes disagreement on WELL-0101 (stands as real oil, CTX-0101-002 vs CTX-0101-003, MNT-0101-029).
  14.9: Full 18-scenario evaluation report generated at artifacts/phase14_full_18_evaluation_report.json.
  14.10: Full 18-scenario evaluation suite runs in < 5.0 seconds.
"""

from pathlib import Path
import time
import pytest
import duckdb

from backend.db.connection import get_db_connection
from backend.feedback.override_engine import reset_runtime_state
from backend.evaluation.part_a2_b_runner import StatefulEvaluationRunner, run_full_18_evaluation


@pytest.fixture(autouse=True)
def clean_state():
    con = get_db_connection()
    reset_runtime_state(con)
    yield
    reset_runtime_state(con)


def test_14_1_q11_memory_recall():
    """Checkpoint 14.1: Q11 recalls 3 wells and exact costs: $25,794, $46,942, $5,176."""
    runner = StatefulEvaluationRunner()
    res = runner.run_q11()

    t2_resp = res["turn_2"]["response"]
    answer = t2_resp["markdown_answer"]

    assert "25,794" in answer
    assert "46,942" in answer
    assert "5,176" in answer
    assert "WELL-0121" in answer
    assert "WELL-0138" in answer
    assert "WELL-0107" in answer


def test_14_2_q12_raw_temp_override_and_q2_reask():
    """Checkpoint 14.2: Q12 Turn 1 (41.0 C override + conflict) & Turn 2 (Q2 table reduced to 3 wells)."""
    runner = StatefulEvaluationRunner()
    res = runner.run_q12()

    t1_resp = res["turn_1"]["response"]
    assert "41.0 °C" in t1_resp["override_badges"][0]["new_value_display"]
    assert len(t1_resp["conflict_cards"]) >= 1
    assert "Pump jack not moving" in t1_resp["conflict_cards"][0]["claim_b_text"]

    t2_resp = res["turn_2"]["response"]
    rows = t2_resp["visual_payload"]["rows"]
    row_ids = [r["asset_id"] for r in rows]
    assert row_ids == ["WELL-0170", "WELL-0172", "WELL-0175"]
    assert len(row_ids) == 3
    assert "WELL-0164" in t2_resp["markdown_answer"]
    assert "Michael Turner" in t2_resp["markdown_answer"]


def test_14_3_q13_ai_spill_override_cascade():
    """Checkpoint 14.3: Q13 evaluates all 4 cascading compliance impacts on WELL-0151."""
    runner = StatefulEvaluationRunner()
    res = runner.run_q13()

    t1_resp = res["turn_1"]["response"]
    answer = t1_resp["markdown_answer"]

    assert "5.4 bbl" in answer
    assert "SR-01" in answer
    assert "24 hours" in answer
    assert "MNT-0151-025" in answer
    assert "6.4 hours" in answer
    assert "SR-02" in answer
    assert "2026-11-23" in answer or "23 Nov" in answer


def test_14_4_q14_well_type_rule_override():
    """Checkpoint 14.4: Q14 baseline (3 wells) -> override -> post-override (4 wells, adds 120, excludes 102)."""
    runner = StatefulEvaluationRunner()
    res = runner.run_q14()

    t1_resp = res["turn_1"]["response"]
    t1_rows = [r["asset_id"] for r in t1_resp["visual_payload"]["rows"]]
    assert t1_rows == ["WELL-0108", "WELL-0121", "WELL-0138"]

    t3_resp = res["turn_3"]["response"]
    t3_rows = [r["asset_id"] for r in t3_resp["visual_payload"]["rows"]]
    assert t3_rows == ["WELL-0108", "WELL-0120", "WELL-0121", "WELL-0138"]
    assert "WELL-0102" not in t3_rows
    assert "T200" in t3_resp["markdown_answer"]


def test_14_5_q15_cross_user_shared_overrides():
    """Checkpoint 14.5: Q15 Part 1 (Jessica Reed on 164) and Part 2 (Laura Simmons on 151)."""
    runner = StatefulEvaluationRunner()
    # Apply Q12 and Q13 overrides first
    runner.run_q12()
    runner.run_q13()

    res = runner.run_q15()

    p1_resp = res["part_1"]["response"]
    assert "producing oil right now" in p1_resp["markdown_answer"].lower()
    assert "41.0 °C" in p1_resp["markdown_answer"]
    assert len(p1_resp["conflict_cards"]) >= 1

    p2_resp = res["part_2"]["response"]
    assert "WELL-0151" in p2_resp["markdown_answer"]
    assert "5.4 bbl" in p2_resp["markdown_answer"]
    assert "SR-01" in p2_resp["markdown_answer"]


def test_14_6_q16_shared_knowledge_vs_private_isolation():
    """Checkpoint 14.6: Q16 shared knowledge on WELL-0007 vs strict privacy isolation on Jessica Reed."""
    runner = StatefulEvaluationRunner()
    # Run Q11 Turn 1 first so Michael Turner has private history
    runner.orchestrator.ask("Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.", "Michael Turner")

    res = runner.run_q16()

    p2_resp = res["part_2"]["response"]
    assert "17 Oct" in p2_resp["markdown_answer"]
    assert "10 days" in p2_resp["markdown_answer"]
    assert "Jake Morales" in p2_resp["markdown_answer"]

    p3_resp = res["part_3"]["response"]
    assert "no record" in p3_resp["markdown_answer"].lower()
    assert "25,794" not in p3_resp["markdown_answer"]


def test_14_7_q17_contradictory_user_claims():
    """Checkpoint 14.7: Q17 Tyler Hughes on 175 and Jake Morales on 0001 flagged as unconfirmed."""
    runner = StatefulEvaluationRunner()
    res = runner.run_q17()

    p2_resp = res["part_2"]["response"]
    assert len(p2_resp["conflict_cards"]) >= 1
    assert p2_resp["conflict_cards"][0]["severity"] == "UNCONFIRMED_CLAIM"
    assert "INS-0175-0204" in p2_resp["markdown_answer"]

    p3_resp = res["part_3"]["response"]
    assert len(p3_resp["conflict_cards"]) >= 1
    assert p3_resp["conflict_cards"][0]["severity"] == "UNCONFIRMED_CLAIM"
    assert "INS-0001-0203" in p3_resp["markdown_answer"]
    assert "CTX-0001-003" in p3_resp["markdown_answer"]


def test_14_8_q18_peer_disagreement_on_ai_spill():
    """Checkpoint 14.8: Q18 WELL-0101 spill detection stands; CTX-0101-002 vs CTX-0101-003 and MNT-0101-029 cited."""
    runner = StatefulEvaluationRunner()
    res = runner.run_q18()

    resp = res["turn_1"]["response"]
    assert "real oil spill" in resp["markdown_answer"].lower() or "real oil" in resp["markdown_answer"].lower()
    assert len(resp["conflict_cards"]) >= 1
    assert "Ryan Brooks" in resp["markdown_answer"]
    assert "Chris Dalton" in resp["markdown_answer"]
    assert "MNT-0101-029" in resp["markdown_answer"]


def test_14_9_all_18_scenarios_report_generated():
    """Checkpoint 14.9: Generates artifacts/phase14_full_18_evaluation_report.json for all 18 scenarios."""
    report_file = "artifacts/phase14_full_18_evaluation_report.json"
    report = run_full_18_evaluation(report_file)

    assert Path(report_file).exists()
    assert report["summary"]["passed_scenarios"] == 18
    assert report["summary"]["parity_percentage"] == 100.0
    assert len(report["scenarios"]) == 18

    for i in range(1, 19):
        q_id = f"Q{i}"
        assert q_id in report["scenarios"]
        assert report["scenarios"][q_id]["status"] == "PASS"


def test_14_10_execution_duration_under_5_seconds():
    """Checkpoint 14.10: Full 18-scenario evaluation runs in < 5.0 seconds."""
    start_t = time.perf_counter()
    report = run_full_18_evaluation()
    duration = time.perf_counter() - start_t

    assert duration < 5.0, f"Full 18-scenario evaluation took {duration:.3f}s, expected < 5.0s"
