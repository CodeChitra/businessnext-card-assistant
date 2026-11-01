"""Fusion, expansion, miss and caching logic, using a deterministic hashing embedder."""

from __future__ import annotations

from typing import Any

import pytest

from grounded_agent.config.settings import Settings
from grounded_agent.retrieval.bm25 import tokenize
from grounded_agent.retrieval.factory import build_retriever
from grounded_agent.retrieval.hybrid import HybridRetriever


@pytest.fixture
def retriever(settings: Settings, hashing_embedder: Any) -> HybridRetriever:
    return build_retriever(settings, embedder=hashing_embedder)


def test_tokenizer_normalises_indian_amounts_and_keeps_doc_ids() -> None:
    assert "150000" in tokenize("Waived on spend of 1,50,000")
    assert "pol-crd-001" in tokenize("See POL-CRD-001 for details")
    assert "3.5%" in tokenize("Foreign currency markup 3.5%")


def test_exact_term_query_ranks_the_fee_schedule_first(retriever: HybridRetriever) -> None:
    result = retriever.retrieve("foreign currency markup")
    assert not result.miss
    assert result.hits[0].chunk.chunk_id == "POL-FEE-007#body"


def test_cross_reference_pulls_in_the_referenced_policy(retriever: HybridRetriever) -> None:
    result = retriever.retrieve("mandatory declines limit increase unresolved dispute", top_k=1)
    assert result.hits[0].chunk.chunk_id == "POL-CRD-001#3"
    xrefs = [h.chunk.doc_id for h in result.hits if h.via == "xref"]
    assert xrefs == ["POL-CON-004"]


def test_off_domain_query_is_a_miss(retriever: HybridRetriever) -> None:
    result = retriever.retrieve("zzz qqq xyzzy")
    assert result.miss and result.hits == ()


def test_multi_query_fusion_recovers_vocabulary_mismatch(retriever: HybridRetriever) -> None:
    raw = "Someone used my card at a shop I have never been to."
    expanded = retriever.retrieve([raw, "transaction dispute provisional credit"])
    assert "POL-SVC-005" in {h.chunk.doc_id for h in expanded.hits}


def test_non_policy_chunks_are_retrievable_but_flagged(retriever: HybridRetriever) -> None:
    result = retriever.retrieve("agent desktop working notes")
    ops = [h for h in result.hits if h.chunk.doc_id == "POL-OPS-012"]
    assert ops and ops[0].chunk.trust.value == "non_policy"


def test_results_are_cached_by_normalised_query(retriever: HybridRetriever) -> None:
    first = retriever.retrieve("Annual  fee waiver")
    assert retriever.retrieve("annual fee WAIVER") is first


def test_empty_query_is_rejected(retriever: HybridRetriever) -> None:
    with pytest.raises(ValueError):
        retriever.retrieve(["  "])


def test_index_is_persisted_and_reused(settings: Settings, hashing_embedder: Any) -> None:
    build_retriever(settings, embedder=hashing_embedder)
    index_dirs = list((settings.cache_dir / "index").iterdir())
    assert len(index_dirs) == 1 and (index_dirs[0] / "vectors.npy").exists()
    build_retriever(settings, embedder=hashing_embedder)
    assert len(list((settings.cache_dir / "index").iterdir())) == 1
