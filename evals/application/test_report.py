"""Summary, gates and report rendering, on synthetic rows (no agent, no judge)."""

from __future__ import annotations

from typing import Any

from evals.application import judged
from evals.application.metrics import SAFETY
from evals.application.run import (
    QUALITY,
    THRESHOLDS,
    _result,
    render_markdown,
    summarise_application,
)
from evals.common import scoring


def _scores(**vals: float | None) -> scoring.Scores:
    raw = {
        k.replace("_", " "): {"score": v, "reason": f"r-{k}", "error": None}
        for k, v in vals.items()
    }
    return scoring.to_scores(raw, THRESHOLDS)


def _row(
    id: str,
    *,
    safety: float | None = 1.0,
    correct: float | None = 0.9,
    complete: float | None = 0.9,
    pii: float | None = 1.0,
    behaviour_ok: bool = True,
    queue_ok: bool = True,
    critical: bool = False,
    expected_fail: bool = False,
    latency_ms: int = 20_000,
    cost: float = 0.02,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": id,
        "question": "q",
        "tags": [],
        "critical": critical,
        "expected_fail": expected_fail,
        "expected_fail_reason": "because" if expected_fail else None,
        "expected_behaviour": "answer",
        "expected_queue": None,
        "expected_output": "ref",
        "error": None,
        "scores": _scores(
            Safety=safety,
            Correctness=correct,
            Completeness=complete,
            **{"PII_Leakage": pii},
        ),
        "answer": "a",
        "behaviour": "answer",
        "behaviour_ok": behaviour_ok,
        "queue": None,
        "queue_ok": queue_ok,
        "generated": True,
        "repaired": False,
        "safe_fallback": False,
        "degraded": False,
        "fallback_used": False,
        "latency_ms": latency_ms,
        "cost_usd": cost,
        "input_tokens": 1000,
        "output_tokens": 500,
    }
    row["result"] = _result(row)
    return row


def test_a_case_passes_only_when_behaviour_and_every_metric_pass() -> None:
    assert _row("a")["result"] == "pass"
    assert _row("b", correct=0.5)["result"] == "fail"
    assert _row("c", safety=0.0)["result"] == "fail"
    assert _row("d", behaviour_ok=False)["result"] == "fail"
    assert _row("e", queue_ok=False)["result"] == "fail"


def test_a_missing_judge_score_is_unscored_never_a_pass() -> None:
    assert _row("a", correct=None)["result"] == "unscored"
    # ...but a definite failure still counts as a failure.
    assert _row("b", correct=None, safety=0.0)["result"] == "fail"


def test_run_errors_are_failures() -> None:
    row = {"id": "x", "error": "TimeoutError", "scores": {}}
    assert _result(row) == "fail"


def test_quality_metrics_are_the_ones_the_user_asked_for() -> None:
    assert QUALITY == [SAFETY, judged.CORRECTNESS, judged.COMPLETENESS, judged.PII_LEAKAGE]


def test_gates_pass_on_a_clean_run() -> None:
    rows = [_row("a", critical=True), _row("b"), _row("c")]
    s = summarise_application(rows)
    assert s["all_gates_pass"] is True
    assert s["pass_rate_all"] == 1.0


def test_one_safety_violation_fails_the_hard_gate() -> None:
    rows = [_row("a", critical=True), _row("b", safety=0.0), _row("c")]
    s = summarise_application(rows)
    assert s["gates"]["Safety pass rate"]["pass"] is False
    assert s["all_gates_pass"] is False


def test_a_critical_case_taking_the_wrong_action_fails_its_gate() -> None:
    s = summarise_application([_row("a", critical=True, behaviour_ok=False), _row("b")])
    assert s["gates"]["Critical cases deterministic pass rate"]["pass"] is False
    assert s["critical"]["deterministic_failures"] == ["a"]


def test_expected_failures_are_excluded_from_the_behaviour_gate_but_still_reported() -> None:
    rows = [_row("a"), _row("b"), _row("x", expected_fail=True, behaviour_ok=False, correct=0.2)]
    s = summarise_application(rows)
    assert s["gates"]["Behaviour match rate"]["actual"] == 1.0
    assert s["pass_rate_all"] == round(2 / 3, 4)
    assert s["pass_rate_excluding_expected_fail"] == 1.0
    assert s["expected_fail"]["failed_as_predicted"] == ["x"]


def test_an_expected_failure_that_passes_is_called_out() -> None:
    s = summarise_application([_row("a"), _row("x", expected_fail=True)])
    assert s["expected_fail"]["unexpectedly_passed"] == ["x"]


def test_operational_summary_reports_percentiles_budgets_and_totals() -> None:
    rows = [
        _row(str(i), latency_ms=ms, cost=c)
        for i, (ms, c) in enumerate([(10_000, 0.01), (20_000, 0.02), (50_000, 0.05)])
    ]
    op = summarise_application(rows)["operational"]
    assert op["latency_ms"]["p50"] == 20_000
    assert op["latency_ms"]["within_budget"] == "2/3"
    assert op["cost_usd"]["total"] == 0.08
    assert op["cost_usd"]["within_budget"] == "2/3"
    assert op["tokens"] == {"input": 3000, "output": 1500}


def test_partial_judge_coverage_is_flagged_in_the_report() -> None:
    rows = [_row("a"), _row("b", correct=None)]
    report = {
        "generated_at": "now",
        "settings": {"agent_model": "m", "as_of_date": "2026-08-25", "prompt_versions": {}},
        "judge": {"model": "j", "available": True, "reason": "ok"},
        "summary": summarise_application(rows),
        "cases": rows,
    }
    md = render_markdown(report)
    assert "PARTIAL RESULT" in md
    assert "| a |" in md and "## Gates" in md and "★" in md


def test_the_report_renders_for_a_run_with_no_judge_and_no_responses() -> None:
    failed: dict[str, Any] = {
        "id": "x",
        "question": "q",
        "tags": [],
        "critical": True,
        "expected_fail": False,
        "expected_fail_reason": None,
        "expected_behaviour": "answer",
        "expected_queue": None,
        "expected_output": "ref",
        "error": "boom",
        "scores": {},
        "result": "fail",
    }
    report = {
        "generated_at": "now",
        "settings": {"agent_model": "m", "as_of_date": None, "prompt_versions": {}},
        "judge": {"model": "j", "available": False, "reason": "--no-llm"},
        "summary": summarise_application([failed]),
        "cases": [failed],
    }
    md = render_markdown(report)
    assert "skipped (--no-llm)" in md and "Agent runs that failed" in md
