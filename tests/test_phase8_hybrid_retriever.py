"""Phase 8 Verification Suite: Hybrid Unstructured Retriever (BM25 + Semantic N-gram RRF).

Verifies:
  - Checkpoint 8.1: Index builds in < 3.0s and indexes >= 1,700 items
  - Checkpoint 8.2: T200 production temperature rule retrieved in top 2
  - Checkpoint 8.3: T200 Section 10 RCA escalation retrieved in top 2
  - Checkpoint 8.4: SR-01 reporting deadline retrieved as #1
  - Checkpoint 8.5: SR-02 containment time limit (4h) retrieved in top 2
  - Checkpoint 8.6: CTX-0001-003 shut-in note retrieved as #1 for WELL-0001
  - Checkpoint 8.7: MNT-0082-028 (7.1h containment) retrieved as #1 for WELL-0082
  - Checkpoint 8.8: CTX-0101-002, CTX-0101-003, and MNT-0101-029 in top 5 for WELL-0101
  - Checkpoint 8.9: Incremental document addition executes in < 50ms
  - Checkpoint 8.10: Average search latency over 20 queries < 50ms
"""

import time
from pathlib import Path
import pytest

from backend.config.settings import get_settings
from backend.retrieval.hybrid_search import HybridRetriever, get_hybrid_retriever


@pytest.fixture(scope="module")
def retriever():
    settings = get_settings()
    db_path = settings.artifacts_path / "copilot.duckdb"
    r = HybridRetriever(db_path=db_path)
    t0 = time.time()
    count = r.build_index()
    t_build = time.time() - t0
    r._build_time = t_build
    r._build_count = count
    return r


def test_checkpoint_8_1_index_build_speed_and_count(retriever):
    """Checkpoint 8.1: Index builds in < 3.0s and indexes >= 1,700 items."""
    assert retriever._build_time < 3.0, f"Index build too slow: {retriever._build_time:.2f}s"
    assert retriever._build_count >= 1700, f"Indexed only {retriever._build_count} items"


def test_checkpoint_8_2_t200_production_temp_rule(retriever):
    """Checkpoint 8.2: T200 production temp rule in top 2 results."""
    res = retriever.search_documents(
        "minimum temperature above ambient producing oil",
        well_type="T200",
        top_k=2,
    )
    assert len(res) >= 1
    citations = [r.citation_id for r in res]
    assert any("T200.md §9.3" in c or "T200.md §9" in c or "Production temperature" in r.title for c, r in zip(citations, res))


def test_checkpoint_8_3_t200_rca_repairs_escalation(retriever):
    """Checkpoint 8.3: T200 Section 10 RCA escalation rule in top 2 results."""
    res = retriever.search_documents(
        "root cause analysis corrective repairs 12 months",
        top_k=2,
    )
    assert len(res) >= 1
    citations = [r.citation_id for r in res]
    assert any("T200.md §10" in c or "Maintenance escalation" in r.title for c, r in zip(citations, res))


def test_checkpoint_8_4_sr01_reporting_deadline(retriever):
    """Checkpoint 8.4: SR-01 24-hour reporting deadline is #1."""
    res = retriever.search_documents(
        "spill reporting deadline 24 hours 5 barrels",
        top_k=1,
    )
    assert len(res) == 1
    assert res[0].citation_id == "SR-01"


def test_checkpoint_8_5_sr02_containment_limit(retriever):
    """Checkpoint 8.5: SR-02 containment time limit (4 hours) in top 2 results."""
    res = retriever.search_documents(
        "spill containment time limit 4 hours",
        top_k=2,
    )
    assert len(res) >= 1
    citations = [r.citation_id for r in res]
    assert "SR-02" in citations


def test_checkpoint_8_6_well0001_rod_string_shutin(retriever):
    """Checkpoint 8.6: CTX-0001-003 shut-in note is #1 for WELL-0001."""
    res = retriever.search_documents(
        "rod string replacement planned shut-in",
        asset_id="WELL-0001",
        top_k=1,
    )
    assert len(res) == 1
    assert res[0].citation_id == "CTX-0001-003"
    assert "Jake Morales" in res[0].content


def test_checkpoint_8_7_well0082_containment_hours(retriever):
    """Checkpoint 8.7: MNT-0082-028 (7.1h containment) is #1 for WELL-0082."""
    res = retriever.search_documents(
        "containment clean-up hours",
        asset_id="WELL-0082",
        top_k=1,
    )
    assert len(res) == 1
    assert res[0].citation_id == "MNT-0082-028"
    assert "7.1" in res[0].content


def test_checkpoint_8_8_well0101_disagreement_and_report(retriever):
    """Checkpoint 8.8: CTX-0101-002, CTX-0101-003, and MNT-0101-029 in top 5 for WELL-0101."""
    res = retriever.search_documents(
        "produced water crude oil stain cellar",
        asset_id="WELL-0101",
        top_k=5,
    )
    citations = {r.citation_id for r in res}
    assert "CTX-0101-002" in citations
    assert "CTX-0101-003" in citations
    assert "MNT-0101-029" in citations


def test_checkpoint_8_9_incremental_indexing_speed(retriever):
    """Checkpoint 8.9: Newly inserted runtime context note adds incrementally in < 50ms."""
    t0 = time.time()
    added = retriever.add_document(
        citation_id="CTX-TEST-999",
        doc_type="context_note",
        title="Runtime Shared Note CTX-TEST-999",
        content="WELL-0007 will be shut in from 17 Oct for a 10-day planned workover per Jake Morales.",
        asset_id="WELL-0007",
        metadata={"author": "Jake Morales", "is_planned_shutin": True},
    )
    add_latency_ms = (time.time() - t0) * 1000.0
    assert add_latency_ms < 50.0, f"Incremental add took {add_latency_ms:.2f}ms"
    assert added.citation_id == "CTX-TEST-999"

    # Verify searchable immediately
    search_res = retriever.search_documents("10-day planned workover", asset_id="WELL-0007", top_k=1)
    assert len(search_res) == 1
    assert search_res[0].citation_id == "CTX-TEST-999"


def test_checkpoint_8_10_average_query_latency(retriever):
    """Checkpoint 8.10: Average query latency across 20 test queries is < 50ms."""
    queries = [
        ("spill reporting deadline", None),
        ("flowline pinhole leak", "WELL-0172"),
        ("walking beam bearing wear", "WELL-0170"),
        ("pump jack root cause analysis", None),
        ("produced water test", None),
        ("cleanup verification 60 days", None),
        ("drone inspection evidence", None),
        ("stuffing box packing leak", "WELL-0001"),
        ("prime mover tripped", "WELL-0001"),
        ("soil sampling TPH", None),
        ("wellhead temperature above ambient", None),
        ("notice of violation response deadline 30 days", None),
        ("waste manifest hazardous material", None),
        ("pressure test 1.25 maximum operating pressure", None),
        ("planned workover weather delay", None),
        ("containment hours limit 4 hours", None),
        ("flowline annual integrity test", None),
        ("rebalanced counterweights", None),
        ("corrosion inhibitor injection", None),
        ("emergency shutdown valve ESD", None),
    ]

    latencies = []
    for q, aid in queries:
        t0 = time.time()
        retriever.search_documents(q, asset_id=aid, top_k=5)
        latencies.append((time.time() - t0) * 1000.0)

    avg_ms = sum(latencies) / len(latencies)
    assert avg_ms < 50.0, f"Average query latency exceeded 50ms: {avg_ms:.2f}ms"
