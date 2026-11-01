"""CI gate for the retriever (deterministic; no API keys).

    uv run --project backend deepeval test run evals/component/retrieval
    uv run --project backend pytest evals/component/retrieval   # same, plain pytest

Per case: every expected chunk is retrieved and the miss flag is right (expanded config).
Aggregate: the thresholds in gates.py.
"""

from __future__ import annotations

import statistics

import pytest
from deepeval import assert_test

from evals.common.datasets import load_retrieval_goldens
from evals.component.retrieval.cases import build_case, make_retriever
from evals.component.retrieval.gates import GATED_CONFIG, GATES
from evals.component.retrieval.metrics import (
    ChunkRecallMetric,
    MissDetectionMetric,
    ReciprocalRankMetric,
)
from grounded_agent.config.settings import get_settings
from grounded_agent.retrieval.base import Retriever

GOLDENS = load_retrieval_goldens()


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return make_retriever(get_settings())


@pytest.mark.parametrize("golden", GOLDENS, ids=[g.id for g in GOLDENS])
def test_case_meets_retrieval_contract(retriever: Retriever, golden) -> None:  # type: ignore[no-untyped-def]
    case = build_case(golden, GATED_CONFIG, retriever)
    metrics = [MissDetectionMetric(threshold=1.0)]
    if golden.answerable:
        metrics.append(ChunkRecallMetric(threshold=1.0))
    assert_test(case, metrics, run_async=False)


def test_aggregate_gates(retriever: Retriever) -> None:
    cases = [(g, build_case(g, GATED_CONFIG, retriever)) for g in GOLDENS]
    answerable = [c for g, c in cases if g.answerable]
    actual = {
        "mean Chunk Recall@k": statistics.fmean(ChunkRecallMetric().measure(c) for c in answerable),
        "mean Reciprocal Rank": statistics.fmean(
            ReciprocalRankMetric().measure(c) for c in answerable
        ),
        "mean Miss Detection": statistics.fmean(MissDetectionMetric().measure(c) for _, c in cases),
    }
    failed = {k: (round(v, 4), GATES[k]) for k, v in actual.items() if v < GATES[k]}
    assert not failed, f"retrieval gates failed (actual, threshold): {failed}"
