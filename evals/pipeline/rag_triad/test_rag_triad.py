from __future__ import annotations

from evals.common import scoring
from evals.common.datasets import PipelineGolden
from evals.common.fixtures import fake_run
from evals.common.llm_metrics import (
    ANSWER_RELEVANCY,
    CONTEXTUAL_RELEVANCY,
    FAITHFULNESS,
    THRESHOLDS,
)
from evals.pipeline.rag_triad.run import METRICS, build_cases, build_row, render_markdown

GOLDEN = PipelineGolden(
    id="EV-009",
    customer_id="CUST-2007",
    question="What is the markup in Singapore?",
    expected_output="The foreign currency markup is 3.5%.",
)


def test_the_triad_is_the_three_requested_metrics() -> None:
    assert METRICS == [CONTEXTUAL_RELEVANCY, FAITHFULNESS, ANSWER_RELEVANCY]


def test_relevancy_judges_what_was_retrieved_and_faithfulness_what_was_shown() -> None:
    retrieval_side, grounding_side = build_cases(GOLDEN, fake_run())
    retrieved = "\n".join(retrieval_side.retrieval_context or [])
    shown = "\n".join(grounding_side.retrieval_context or [])
    # Retrieval side: every retrieved chunk, with its trust tag (including the untrusted notes).
    assert "POL-OPS-012#body | trust=non_policy" in retrieved
    assert "ACCOUNT FACTS" not in retrieved
    # Grounding side: what the generator got: trusted policy plus account facts and rules.
    assert "ACCOUNT FACTS" in shown and "RULE OUTCOMES" in shown
    assert "POL-OPS-012" not in shown
    assert retrieval_side.actual_output == grounding_side.actual_output


def test_report_has_one_column_per_triad_metric() -> None:
    scores = scoring.to_scores(
        {
            CONTEXTUAL_RELEVANCY: {"score": 0.4, "reason": "noisy context", "error": None},
            FAITHFULNESS: {"score": 1.0, "reason": "ok", "error": None},
            ANSWER_RELEVANCY: {"score": 0.9, "reason": "ok", "error": None},
        },
        THRESHOLDS,
    )
    row = build_row(GOLDEN, fake_run(), scores)
    assert row["retrieved"] == ["POL-FEE-007#body", "POL-OPS-012#body"]
    report = {
        "generated_at": "now",
        "settings": {"agent_model": "m", "prompt_versions": {}},
        "judge": {"model": "j", "available": True, "reason": "ok"},
        "summary": scoring.summarise([row], METRICS),
        "cases": [row],
    }
    md = render_markdown(report)
    assert "| Case | Contextual relevancy | Faithfulness | Answer relevancy |" in md
    assert "0.40 ❌" in md and "noisy context" in md
