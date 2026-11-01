"""The runner's whole point is coverage: every (case, metric) yields a score or an error."""

from __future__ import annotations

import asyncio
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from evals.common.llm_runner import _judge_all, judge_groups


class _Metric(BaseMetric):
    def __init__(self, behaviour: str) -> None:
        self.behaviour, self.threshold = behaviour, 0.5
        self.score: float | None = None
        self.reason: str | None = None
        self.error: str | None = None

    async def a_measure(self, test_case: LLMTestCase, *_: Any, **__: Any) -> float:
        if self.behaviour == "raise":
            raise RuntimeError("Error code: 429")
        if self.behaviour == "hang":
            await asyncio.sleep(10)
        self.score, self.reason = 0.9, "fine"
        return 0.9

    def measure(self, test_case: LLMTestCase, *_: Any, **__: Any) -> float:
        raise NotImplementedError

    def is_successful(self) -> bool:
        return True

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return f"m-{self.behaviour}"


async def test_every_case_and_metric_has_an_entry() -> None:
    cases = [LLMTestCase(input=f"q{i}", name=f"c{i}") for i in range(3)]
    factories = [lambda: _Metric("ok"), lambda: _Metric("raise"), lambda: _Metric("hang")]
    out = await _judge_all(cases, factories, max_concurrent=2, throttle_s=0.0, timeout_s=0.05)
    assert set(out) == {"c0", "c1", "c2"}
    for results in out.values():
        assert results["m-ok"]["score"] == 0.9
        assert results["m-raise"]["score"] is None and "429" in results["m-raise"]["error"]
        assert results["m-hang"]["score"] is None and "Timeout" in results["m-hang"]["error"]


def test_groups_share_one_event_loop_and_merge_per_case() -> None:
    # Regression: two separate judge_cases() calls each used asyncio.run(), so the judge's async
    # client (bound to the first loop) failed on the second with "Event loop is closed".
    cases = [LLMTestCase(input="q", name="c0")]
    out = judge_groups(
        [(cases, [lambda: _Metric("ok")]), (cases, [lambda: _Metric("raise")])],
        max_concurrent=2,
        throttle_s=0.0,
        timeout_s=1.0,
    )
    assert set(out["c0"]) == {"m-ok", "m-raise"}
    assert out["c0"]["m-ok"]["score"] == 0.9
