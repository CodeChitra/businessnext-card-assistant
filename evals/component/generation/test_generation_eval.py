from __future__ import annotations

from evals.common import scoring
from evals.common.datasets import GenerationGolden
from evals.common.fixtures import fake_run
from evals.common.llm_metrics import ANSWER_RELEVANCY, FAITHFULNESS, THRESHOLDS
from evals.component.generation.run import METRICS, build_case, build_row, render_markdown

GOLDEN = GenerationGolden(
    id="EV-009",
    customer_id="CUST-2007",
    question="What is the markup in Singapore?",
    gold_chunks=["POL-FEE-007#body"],
    expected_output="The foreign currency markup is 3.5%.",
)


def test_the_judge_sees_everything_the_generator_saw() -> None:
    case = build_case(GOLDEN, fake_run())
    ctx = "\n".join(case.retrieval_context or [])
    assert "POL-FEE-007#body" in ctx and "ACCOUNT FACTS" in ctx and "RULE OUTCOMES" in ctx
    assert "POL-OPS-012" not in ctx  # untrusted notes are not grounding
    assert case.actual_output == "The foreign currency markup is 3.5%."


def test_metrics_are_faithfulness_and_answer_relevancy() -> None:
    assert METRICS == [FAITHFULNESS, ANSWER_RELEVANCY]


def test_report_lists_scores_flags_and_answers() -> None:
    scores = scoring.to_scores(
        {
            FAITHFULNESS: {"score": 0.5, "reason": "added a claim", "error": None},
            ANSWER_RELEVANCY: {"score": 1.0, "reason": "on topic", "error": None},
        },
        THRESHOLDS,
    )
    row = build_row(GOLDEN, fake_run(), scores)
    report = {
        "generated_at": "now",
        "settings": {"agent_model": "m", "prompt_versions": {"generate": "generate@4+x"}},
        "judge": {"model": "j", "available": True, "reason": "ok"},
        "summary": scoring.summarise([row], METRICS),
        "cases": [row],
    }
    md = render_markdown(report)
    assert "0.50 ❌" in md and "added a claim" in md
    assert "The foreign currency markup is 3.5%." in md
    assert "retrieval held fixed" in md.lower()
