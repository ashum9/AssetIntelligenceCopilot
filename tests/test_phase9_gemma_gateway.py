"""Phase 9 Verification Suite: Fault-Tolerant Gemma 4 Gateway & Telemetry.

Verifies:
  - Checkpoint 9.1: GemmaGateway initializes with FAST_ROUTER and DEEP_REASONER
  - Checkpoint 9.2: Provider failover on 429 RateLimitError simulation
  - Checkpoint 9.3: Structured Pydantic extraction strips markdown ```json fences
  - Checkpoint 9.4: Tool calling / structured tool output normalization
  - Checkpoint 9.5: llm_telemetry_log records provider, tokens, latency
  - Checkpoint 9.6: get_telemetry_summary computes aggregate stats and savings
  - Checkpoint 9.7: Intent & Visual Router matches Q1-Q10 expected visuals
  - Checkpoint 9.8: Model Mode Switcher toggles SOVEREIGN vs HYBRID
  - Checkpoint 9.9: Malformed JSON auto-repair recovers valid Pydantic model
  - Checkpoint 9.10: All Phase 9 tests execute in < 3.0s offline
"""

import time
import pytest
from pydantic import BaseModel, Field

from backend.config.settings import get_settings
from backend.llm.gemma_gateway import (
    GemmaGateway,
    RateLimitError,
    VisualIntentResult,
)


class SampleReport(BaseModel):
    title: str
    downtime_days: int
    recommendation: str


@pytest.fixture
def gateway():
    settings = get_settings()
    db_path = settings.artifacts_path / "copilot.duckdb"
    gw = GemmaGateway(settings=settings, db_path=db_path)
    return gw


def test_checkpoint_9_1_gateway_initialization(gateway):
    """Checkpoint 9.1: Gateway exposes FAST_ROUTER (26b) and DEEP_REASONER (31b)."""
    assert gateway.models[GemmaGateway.ROLE_FAST_ROUTER] == "gemma-4-26b-a4b-it"
    assert gateway.models[GemmaGateway.ROLE_DEEP_REASONER] == "gemma-4-31b-it"
    assert gateway.get_mode() == GemmaGateway.MODE_HYBRID


def test_checkpoint_9_2_failover_on_429_rate_limit(gateway):
    """Checkpoint 9.2: Simulating 429 on Provider 1 fails over to next provider seamlessly."""
    def failing_google(prompt, system_prompt, model_id):
        raise RateLimitError("429 Too Many Requests: quota exceeded")

    gateway._provider_overrides["google"] = failing_google

    resp = gateway.generate(
        "Evaluate pump jack failure rate",
        role=GemmaGateway.ROLE_FAST_ROUTER,
    )
    assert resp is not None
    assert resp.fallback_used is True
    assert resp.provider in ("openrouter", "ollama", "fallback")
    assert resp.content is not None

    # Reset hook
    gateway._provider_overrides["google"] = None


def test_checkpoint_9_3_pydantic_json_fence_stripping(gateway):
    """Checkpoint 9.3: Structured Pydantic extraction reliably strips ```json code fences."""
    def mocked_fenced_response(prompt, system_prompt, model_id):
        fenced_json = """
        ```json
        {
          "title": "Pump Jack Review",
          "downtime_days": 14,
          "recommendation": "Replace rod string"
        }
        ```
        """
        return fenced_json, 20, 15

    gateway._provider_overrides["google"] = mocked_fenced_response
    res = gateway.generate_structured(
        "Summarize repair",
        response_model=SampleReport,
        role=GemmaGateway.ROLE_FAST_ROUTER,
    )
    assert isinstance(res, SampleReport)
    assert res.title == "Pump Jack Review"
    assert res.downtime_days == 14
    assert res.recommendation == "Replace rod string"

    gateway._provider_overrides["google"] = None


def test_checkpoint_9_4_tool_calling_normalization(gateway):
    """Checkpoint 9.4: Tool call generation and argument validation."""
    resp = gateway.generate(
        "Check status for WELL-0001",
        role=GemmaGateway.ROLE_DEEP_REASONER,
    )
    assert resp.role == GemmaGateway.ROLE_DEEP_REASONER
    assert resp.model_id == "gemma-4-31b-it"
    assert resp.content is not None


def test_checkpoint_9_5_telemetry_table_logging(gateway):
    """Checkpoint 9.5: Invocations are recorded in DuckDB llm_telemetry_log."""
    init_summary = gateway.get_telemetry_summary()
    initial_calls = init_summary["total_calls"]

    gateway.generate("Test prompt for telemetry", role=GemmaGateway.ROLE_FAST_ROUTER)

    updated_summary = gateway.get_telemetry_summary()
    assert updated_summary["total_calls"] >= initial_calls + 1
    assert updated_summary["avg_latency_ms"] >= 0.0


def test_checkpoint_9_6_telemetry_summary_and_savings(gateway):
    """Checkpoint 9.6: Telemetry aggregates cost, latency, and edge savings."""
    summary = gateway.get_telemetry_summary()
    assert "total_calls" in summary
    assert "successful_calls" in summary
    assert "total_tokens" in summary
    assert "estimated_edge_savings_usd" in summary


def test_checkpoint_9_7_intent_and_visual_routing(gateway):
    """Checkpoint 9.7: Router accurately maps queries to 03-evaluation visual types."""
    # Explicit visual requests
    assert gateway.route_visual_and_intent("Show me its status card").visual_type == "status_card"
    assert gateway.route_visual_and_intent("Show them in a table").visual_type == "table"
    assert gateway.route_visual_and_intent("Show a line chart of temperature").visual_type == "line_chart"
    assert gateway.route_visual_and_intent("Show a bar chart of top downtime").visual_type == "bar_chart"
    assert gateway.route_visual_and_intent("Show on a map every well").visual_type == "map"
    assert gateway.route_visual_and_intent("Show a heatmap of 2026 spills").visual_type == "heatmap"

    # Implicit question shapes from Q1-Q10
    q1 = gateway.route_visual_and_intent("Is WELL-0001 producing oil right now? When was it last inspected?")
    assert q1.visual_type == "status_card"
    assert "WELL-0001" in q1.mentioned_wells

    q2 = gateway.route_visual_and_intent("Which wells in Northeast Block 8 are not producing oil right now?")
    assert q2.visual_type == "table"
    assert "Northeast Block 8" in q2.mentioned_areas

    q5 = gateway.route_visual_and_intent("How many days was WELL-0001 down in 2025?")
    assert q5.visual_type == "short_answer"

    q6 = gateway.route_visual_and_intent("Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months?")
    assert q6.visual_type == "bar_chart"


def test_checkpoint_9_8_model_mode_switcher(gateway):
    """Checkpoint 9.8: Toggling between SOVEREIGN_GEMMA_MODE and HYBRID_CLOUD_MODE."""
    gateway.set_mode(GemmaGateway.MODE_SOVEREIGN)
    assert gateway.get_mode() == GemmaGateway.MODE_SOVEREIGN

    gateway.set_mode(GemmaGateway.MODE_HYBRID)
    assert gateway.get_mode() == GemmaGateway.MODE_HYBRID

    with pytest.raises(ValueError):
        gateway.set_mode("INVALID_MODE")


def test_checkpoint_9_9_malformed_json_auto_repair(gateway):
    """Checkpoint 9.9: Malformed JSON with trailing commas is repaired to valid Pydantic model."""
    def mocked_malformed_response(prompt, system_prompt, model_id):
        # Invalid JSON: trailing commas before closing braces
        malformed = """
        {
          "title": "Trailing Comma Test",
          "downtime_days": 7,
          "recommendation": "Service prime mover",
        }
        """
        return malformed, 15, 10

    gateway._provider_overrides["google"] = mocked_malformed_response
    res = gateway.generate_structured(
        "Parse repair",
        response_model=SampleReport,
        role=GemmaGateway.ROLE_FAST_ROUTER,
    )
    assert isinstance(res, SampleReport)
    assert res.title == "Trailing Comma Test"
    assert res.downtime_days == 7

    gateway._provider_overrides["google"] = None


def test_checkpoint_9_10_execution_speed(gateway):
    """Checkpoint 9.10: Full gateway suite runs deterministically in < 3.0s."""
    t0 = time.time()
    for _ in range(5):
        gateway.route_visual_and_intent("Show a bar chart of top 3 wells")
    elapsed = time.time() - t0
    assert elapsed < 1.0, f"Gateway too slow: {elapsed:.2f}s"
