"""Phase 13 Verification Suite: Agent Orchestrator & 5-Tool Suite.

Tests:
  13.1: All 5 tools execute cleanly and return structured Pydantic outputs with citations.
  13.2: query_semantic_sql rejects mutating statements and runs SELECT in < 50ms.
  13.3: ask() handles single-well (Q1), table (Q2), series (Q3), aggregation (Q6, Q8), compliance (Q9).
  13.4: Every response envelope contains markdown_answer, citations, visual_payload, user_context, telemetry.
  13.5: Feedback and notes automatically route to record_feedback_override_or_claim.
  13.6: Private memory references route through recall_private_user_session strictly by user_id.
  13.7: Inline citations match valid DuckDB domain identifiers.
  13.8: Works deterministically in offline CI mode without API keys.
  13.9: Automatically logs discussed asset_ids into session_messages and memory tables.
  13.10: Turn latency is < 250ms per turn.
"""

import time
import pytest
import duckdb

from backend.db.connection import get_db_connection
from backend.agent.tools import CopilotTools
from backend.agent.orchestrator import CopilotOrchestrator
from backend.feedback.override_engine import reset_runtime_state


@pytest.fixture(autouse=True)
def clean_runtime_state():
    con = get_db_connection()
    reset_runtime_state(con)
    yield
    reset_runtime_state(con)


def test_13_1_all_five_tools_structured_output():
    """Checkpoint 13.1: All 5 tools execute cleanly and return structured Pydantic outputs."""
    tools = CopilotTools()

    # Tool 1: query_semantic_sql
    t1 = tools.query_semantic_sql("SELECT asset_id, inspection_id FROM v_well_current_status LIMIT 3")
    assert t1.status == "success"
    assert t1.tool_name == "query_semantic_sql"
    assert len(t1.citations) >= 1

    # Tool 2: get_well_360_dossier
    t2 = tools.get_well_360_dossier("WELL-0001")
    assert t2.status == "success"
    assert t2.tool_name == "get_well_360_dossier"
    assert t2.data["asset_id"] == "WELL-0001"
    assert len(t2.citations) >= 1

    # Tool 3: search_manuals_reports_and_notes
    t3 = tools.search_manuals_reports_and_notes("spill containment limit 4 hours")
    assert t3.status == "success"
    assert t3.tool_name == "search_manuals_reports_and_notes"
    assert len(t3.data["hits"]) >= 1

    # Tool 4: record_feedback_override_or_claim
    t4 = tools.record_feedback_override_or_claim(
        "Michael Turner",
        "The 15 Oct reading for WELL-0164 is wrong... field crew re-measured the wellhead at 41.0 °C."
    )
    assert t4.status == "success"
    assert t4.tool_name == "record_feedback_override_or_claim"
    assert len(t4.citations) >= 1

    # Tool 5: recall_private_user_session
    t5 = tools.recall_private_user_session("Michael Turner", "the three wells we discussed yesterday")
    assert t5.status == "success"
    assert t5.tool_name == "recall_private_user_session"


def test_13_2_sql_guardrails_and_latency():
    """Checkpoint 13.2: Rejects mutating statements and executes SELECT in < 50ms."""
    tools = CopilotTools()

    # Mutating SQL rejected
    r1 = tools.query_semantic_sql("DROP TABLE raw_inspections")
    assert r1.status == "error"
    assert "forbidden" in r1.error_message.lower()

    r2 = tools.query_semantic_sql("DELETE FROM wells WHERE asset_id = 'WELL-0001'")
    assert r2.status == "error"
    assert "forbidden" in r2.error_message.lower()

    r3 = tools.query_semantic_sql("UPDATE raw_inspections SET wellhead_temp_c = 100")
    assert r3.status == "error"
    assert "forbidden" in r3.error_message.lower()

    # Fast SELECT
    start_t = time.perf_counter()
    r4 = tools.query_semantic_sql("SELECT COUNT(*) FROM v_well_current_status WHERE is_producing = TRUE")
    duration_ms = (time.perf_counter() - start_t) * 1000.0

    assert r4.status == "success"
    assert duration_ms < 50.0


def test_13_3_orchestrator_handles_core_scenario_archetypes():
    """Checkpoint 13.3: ask() handles single-well (Q1), table (Q2), series (Q3), aggregation (Q6), compliance (Q9)."""
    orch = CopilotOrchestrator()

    # Q1 Single well
    resp1 = orch.ask("Is WELL-0001 producing oil right now? Explain how you know.", "Michael Turner")
    assert "not producing" in resp1.markdown_answer.lower()
    assert resp1.visual_payload.visual_type == "status_card"

    # Q2 Table
    resp2 = orch.ask("Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.", "Michael Turner")
    assert "northeast block 8" in resp2.markdown_answer.lower()
    assert resp2.visual_payload.visual_type == "table"

    # Q3 Time-series
    resp3 = orch.ask("Show the weekly wellhead and ambient temperatures for WELL-0001 over the last 13 weeks. On which dates was it not producing oil?", "Michael Turner")
    assert "2026-10-08" in resp3.markdown_answer
    assert "2026-10-15" in resp3.markdown_answer
    assert resp3.visual_payload.visual_type == "line_chart"

    # Q6 Comparison bar chart
    resp6 = orch.ask("Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.", "Michael Turner")
    assert "well-0121" in resp6.markdown_answer.lower()
    assert resp6.visual_payload.visual_type == "bar_chart"

    # Q9 Compliance
    resp9 = orch.ask("Which regulatory compliance issues are currently open or unresolved in Southwest Block 24?", "Michael Turner")
    assert "5,000" in resp9.markdown_answer
    assert resp9.visual_payload.visual_type == "table"


def test_13_4_response_envelope_completeness():
    """Checkpoint 13.4: Envelope contains markdown_answer, citations, visual_payload, user_context, telemetry."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Is WELL-0001 producing oil right now?", "Michael Turner")

    assert len(resp.markdown_answer) > 20
    assert len(resp.citations) >= 1
    assert resp.visual_payload is not None
    assert resp.user_context["user_name"] == "Michael Turner"
    assert "duration_ms" in resp.telemetry


def test_13_5_feedback_routing_to_override_tool():
    """Checkpoint 13.5: Feedback statements automatically route to record_feedback_override_or_claim."""
    orch = CopilotOrchestrator()

    # Temperature correction feedback
    resp12 = orch.ask(
        "The 15 Oct reading for WELL-0164 is wrong. The handheld thermal gun used in that inspection was faulty; the field crew re-measured the wellhead at 41.0 °C.",
        "Michael Turner"
    )
    assert len(resp12.override_badges) >= 1
    assert resp12.override_badges[0].new_value_display == "41.0 °C"
    assert len(resp12.conflict_cards) >= 1
    assert "Pump jack not moving" in resp12.conflict_cards[0].claim_b_text

    # Spill correction feedback
    resp13 = orch.ask(
        "The AI estimated the 24 Sep spill at WELL-0151 as 4.5 bbl. The field crew measured 5.4 bbl.",
        "Michael Turner"
    )
    assert len(resp13.override_badges) >= 1
    assert resp13.override_badges[0].new_value_display == "5.4 bbl"
    assert "SR-01" in resp13.markdown_answer


def test_13_6_private_memory_scoped_isolation():
    """Checkpoint 13.6: Private memory references route through recall_private_user_session strictly by user_id."""
    orch = CopilotOrchestrator()

    # Day 1: Michael Turner asks Q6
    orch.ask("Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.", "Michael Turner")

    # Day 2: Michael Turner recalls
    resp_mt = orch.ask("For the three wells we discussed yesterday, what have repairs cost this year?", "Michael Turner")
    assert "25,794" in resp_mt.markdown_answer
    assert "46,942" in resp_mt.markdown_answer
    assert "5,176" in resp_mt.markdown_answer

    # Jessica Reed asks the same question without having prior conversation
    resp_jr = orch.ask("For the three wells we discussed yesterday, what have repairs cost this year?", "Jessica Reed")
    assert "no record" in resp_jr.markdown_answer.lower()
    assert "25,794" not in resp_jr.markdown_answer  # Strict privacy isolation!


def test_13_7_citations_match_valid_ids():
    """Checkpoint 13.7: All citations match real valid domain IDs."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Is WELL-0001 producing oil right now?", "Michael Turner")

    for cit in resp.citations:
        assert any(
            cit.citation_id.startswith(prefix)
            for prefix in ["INS-", "MNT-", "CTX-", "REG-", "T200.md", "T350.md", "SR-", "RC-", "WS-"]
        )


def test_13_8_offline_deterministic_execution():
    """Checkpoint 13.8: Works deterministically in offline CI mode without API keys."""
    orch = CopilotOrchestrator()
    resp = orch.ask("Produce a monthly heatmap of spill counts by area for 2026.", "Michael Turner")

    assert resp.visual_payload.visual_type == "heatmap"
    assert resp.visual_payload.grand_total == 141
    assert resp.visual_payload.row_totals == [35, 43, 37, 26]


def test_13_9_session_logging_and_memory_persistence():
    """Checkpoint 13.9: Discussed asset_ids are logged into session_messages and memory."""
    con = get_db_connection()
    orch = CopilotOrchestrator(con=con)

    orch.ask("Is WELL-0001 producing oil right now?", "Michael Turner")

    rows = con.execute(
        "SELECT discussed_asset_ids_json FROM session_messages WHERE user_id = 'U-201' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    assert rows is not None
    assert "WELL-0001" in rows[0]


def test_13_10_turn_latency_under_250ms():
    """Checkpoint 13.10: End-to-end turn latency is < 250ms."""
    orch = CopilotOrchestrator()

    start_t = time.perf_counter()
    resp = orch.ask("How many days was WELL-0001 down in 2025?", "Michael Turner")
    duration_ms = (time.perf_counter() - start_t) * 1000.0

    assert duration_ms < 250.0, f"Turn latency was {duration_ms:.2f}ms, expected < 250ms"
    assert "21 days" in resp.markdown_answer
    assert any("MNT-0001-021" in c.citation_id for c in resp.citations)
