"""The LLM-judged DeepEval metrics shared by the generation and pipeline layers.

Thresholds are reported against, never gated on: judges are noisy and drift (evals/README.md).
"""

from __future__ import annotations

from typing import Any

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)

from evals.common.llm_runner import MetricFactory

FAITHFULNESS = "Faithfulness"
ANSWER_RELEVANCY = "Answer Relevancy"
CONTEXTUAL_RELEVANCY = "Contextual Relevancy"

THRESHOLDS: dict[str, float] = {
    FAITHFULNESS: 0.8,
    ANSWER_RELEVANCY: 0.7,
    CONTEXTUAL_RELEVANCY: 0.7,
}


def _common(judge: Any, name: str) -> dict[str, Any]:
    return {
        "threshold": THRESHOLDS[name],
        "model": judge,
        "include_reason": True,
        "async_mode": True,
    }


def faithfulness(judge: Any) -> MetricFactory:
    return lambda: FaithfulnessMetric(**_common(judge, FAITHFULNESS))


def answer_relevancy(judge: Any) -> MetricFactory:
    return lambda: AnswerRelevancyMetric(**_common(judge, ANSWER_RELEVANCY))


def contextual_relevancy(judge: Any) -> MetricFactory:
    return lambda: ContextualRelevancyMetric(**_common(judge, CONTEXTUAL_RELEVANCY))
