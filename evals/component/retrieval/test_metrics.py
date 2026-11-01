"""The metrics themselves are code; test them so a gate cannot pass by accident."""

from __future__ import annotations

from typing import Any

import pytest
from deepeval.test_case import LLMTestCase

from evals.component.retrieval.metrics import (
    ChunkPrecisionMetric,
    ChunkRecallMetric,
    MissDetectionMetric,
    ReciprocalRankMetric,
)


def case(**meta: Any) -> LLMTestCase:
    base = {"expected_chunks": [], "search_chunks": [], "all_chunks": [], "miss": False}
    base["expected_miss"] = False
    return LLMTestCase(input="q", name="t", metadata={**base, **meta})


def test_recall_counts_xref_hits() -> None:
    m = ChunkRecallMetric()
    tc = case(expected_chunks=["A", "B"], search_chunks=["A"], all_chunks=["A", "B"])
    assert m.measure(tc) == 1.0


def test_recall_partial_lists_missing() -> None:
    m = ChunkRecallMetric(threshold=1.0)
    assert m.measure(case(expected_chunks=["A", "B"], all_chunks=["A"])) == 0.5
    assert not m.is_successful() and "B" in m.reason


def test_reciprocal_rank_ignores_xref_hits() -> None:
    tc = case(expected_chunks=["B"], search_chunks=["A", "C"], all_chunks=["A", "C", "B"])
    assert ReciprocalRankMetric().measure(tc) == 0.0
    tc = case(expected_chunks=["B"], search_chunks=["A", "B"])
    assert ReciprocalRankMetric().measure(tc) == 0.5


def test_precision_is_share_of_search_hits() -> None:
    tc = case(expected_chunks=["A"], search_chunks=["A", "B", "C", "D"])
    assert ChunkPrecisionMetric().measure(tc) == 0.25


@pytest.mark.parametrize(("miss", "expected", "score"), [(True, True, 1.0), (False, True, 0.0)])
def test_miss_detection(miss: bool, expected: bool, score: float) -> None:
    assert MissDetectionMetric().measure(case(miss=miss, expected_miss=expected)) == score


def test_missing_metadata_is_an_error_not_a_pass() -> None:
    with pytest.raises(ValueError):
        ChunkRecallMetric().measure(LLMTestCase(input="q", name="t", metadata={}))
