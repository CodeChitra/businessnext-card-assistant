"""Deterministic retrieval metrics as DeepEval metrics.

They read ids from `test_case.metadata` (set by the runner), need no LLM, run in CI with no
keys, and complement the LLM-judged contextual metrics:

  - ChunkRecallMetric        share of expected chunks retrieved (search + xref hits)
  - ReciprocalRankMetric     1 / rank of the first expected chunk among search hits
  - ChunkPrecisionMetric     share of search hits that are expected (reported, not gated:
                             with top-k=5 and 1-2 relevant chunks it is bounded by design)
  - MissDetectionMetric      miss flag agrees with the golden (off-domain must be a miss,
                             in-domain must not)
"""

from __future__ import annotations

from typing import Any, ClassVar

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


class _IdMetric(BaseMetric):
    _required_params: ClassVar[list[Any]] = []
    metric_name = "id-metric"

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.include_reason = True
        self.strict_mode = False
        self.async_mode = False
        self.verbose_mode = False
        self.evaluation_model = None
        self.error = None

    @staticmethod
    def _meta(test_case: LLMTestCase) -> dict[str, Any]:
        meta = test_case.metadata or {}
        for key in (
            "expected_chunks",
            "search_chunks",
            "all_chunks",
            "miss",
            "expected_miss",
        ):
            if key not in meta:
                raise ValueError(f"test case {test_case.name} is missing metadata[{key!r}]")
        return meta

    def _score(self, meta: dict[str, Any]) -> tuple[float, str]:
        raise NotImplementedError

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        self.score, self.reason = self._score(self._meta(test_case))
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return self.metric_name


class ChunkRecallMetric(_IdMetric):
    metric_name = "Chunk Recall@k"

    def _score(self, meta: dict[str, Any]) -> tuple[float, str]:
        expected = set(meta["expected_chunks"])
        if not expected:
            return 1.0, "No chunks expected."
        found = expected & set(meta["all_chunks"])
        missing = sorted(expected - found)
        return len(found) / len(expected), f"missing: {missing}" if missing else "all retrieved"


class ReciprocalRankMetric(_IdMetric):
    metric_name = "Reciprocal Rank"

    def _score(self, meta: dict[str, Any]) -> tuple[float, str]:
        expected = set(meta["expected_chunks"])
        if not expected:
            return 1.0, "No chunks expected."
        for rank, cid in enumerate(meta["search_chunks"], start=1):
            if cid in expected:
                return 1.0 / rank, f"first relevant at rank {rank} ({cid})"
        return 0.0, "no expected chunk among search hits"


class ChunkPrecisionMetric(_IdMetric):
    metric_name = "Chunk Precision@k"

    def _score(self, meta: dict[str, Any]) -> tuple[float, str]:
        hits = meta["search_chunks"]
        expected = set(meta["expected_chunks"])
        if not hits:
            return (1.0, "no hits, none expected") if not expected else (0.0, "no hits")
        relevant = [c for c in hits if c in expected]
        return len(relevant) / len(hits), f"{len(relevant)}/{len(hits)} hits expected"


class MissDetectionMetric(_IdMetric):
    metric_name = "Miss Detection"

    def _score(self, meta: dict[str, Any]) -> tuple[float, str]:
        ok = bool(meta["miss"]) == bool(meta["expected_miss"])
        return (1.0 if ok else 0.0), f"miss={meta['miss']} expected={meta['expected_miss']}"


DETERMINISTIC_METRICS: list[type[_IdMetric]] = [
    ChunkRecallMetric,
    ReciprocalRankMetric,
    ChunkPrecisionMetric,
    MissDetectionMetric,
]
