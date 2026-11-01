"""Run LLM-judged DeepEval metrics with guaranteed coverage.

`deepeval.evaluate()` applies its own per-task time budget and can drop cancelled tasks from
the results, which with a slow reasoning judge behind a rate-limited gateway silently
removed most cases. Here every (case, metric) pair yields either a score or an explicit
error, under our own concurrency limit, throttle and timeout. The metrics themselves are
unchanged DeepEval metrics, driven through their public `a_measure`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

MetricFactory = Callable[[], BaseMetric]
Scores = dict[str, dict[str, dict[str, Any]]]  # case name -> metric name -> result


async def _judge_one(
    case: LLMTestCase, factories: Sequence[MetricFactory], timeout_s: float
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for factory in factories:
        metric = factory()  # metrics are stateful: fresh instance per case
        name = metric.__name__
        try:
            await asyncio.wait_for(metric.a_measure(case, _show_indicator=False), timeout_s)
            results[name] = {
                "score": None if metric.score is None else round(float(metric.score), 4),
                "reason": metric.reason,
                "error": metric.error,
            }
        except Exception as exc:  # recorded, never dropped
            results[name] = {
                "score": None,
                "reason": None,
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            }
    return results


async def _judge_all(
    cases: Sequence[LLMTestCase],
    factories: Sequence[MetricFactory],
    max_concurrent: int,
    throttle_s: float,
    timeout_s: float,
    semaphore: asyncio.Semaphore | None = None,
) -> Scores:
    semaphore = semaphore or asyncio.Semaphore(max_concurrent)

    async def guarded(i: int, case: LLMTestCase) -> tuple[str, dict[str, dict[str, Any]]]:
        await asyncio.sleep(i * throttle_s / max(max_concurrent, 1))  # stagger starts
        async with semaphore:
            return case.name or f"case-{i}", await _judge_one(case, factories, timeout_s)

    pairs = await asyncio.gather(*(guarded(i, c) for i, c in enumerate(cases)))
    return dict(pairs)


def judge_cases(
    cases: Sequence[LLMTestCase],
    factories: Sequence[MetricFactory],
    *,
    max_concurrent: int = 2,
    throttle_s: float = 1.0,
    timeout_s: float = 600.0,
) -> Scores:
    return asyncio.run(_judge_all(cases, factories, max_concurrent, throttle_s, timeout_s))


async def _judge_groups(
    groups: Sequence[tuple[Sequence[LLMTestCase], Sequence[MetricFactory]]],
    max_concurrent: int,
    throttle_s: float,
    timeout_s: float,
) -> Scores:
    shared = asyncio.Semaphore(max_concurrent)  # one limit across every group
    parts = await asyncio.gather(
        *(
            _judge_all(cases, factories, max_concurrent, throttle_s, timeout_s, shared)
            for cases, factories in groups
        )
    )
    merged: Scores = {}
    for part in parts:
        for name, metrics in part.items():
            merged.setdefault(name, {}).update(metrics)
    return merged


def judge_groups(
    groups: Sequence[tuple[Sequence[LLMTestCase], Sequence[MetricFactory]]],
    *,
    max_concurrent: int = 2,
    throttle_s: float = 1.0,
    timeout_s: float = 600.0,
) -> Scores:
    """Judge several (cases, metrics) groups in ONE event loop.

    The judge model's async HTTP client is bound to the loop it first runs in, so calling
    `judge_cases` twice (two `asyncio.run`s) fails the second time with "Event loop is closed".
    Cases that appear in more than one group get their metrics merged.
    """
    return asyncio.run(_judge_groups(groups, max_concurrent, throttle_s, timeout_s))
