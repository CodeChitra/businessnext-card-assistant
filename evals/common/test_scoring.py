from __future__ import annotations

from evals.common import scoring


def test_geval_names_are_cleaned_and_thresholds_applied() -> None:
    raw = {"Correctness [GEval]": {"score": 0.65, "reason": "r", "error": None}}
    out = scoring.to_scores(raw, {"Correctness": 0.7})
    assert out["Correctness"]["passed"] is False and out["Correctness"]["threshold"] == 0.7


def test_an_errored_metric_has_no_pass_flag() -> None:
    out = scoring.to_scores(
        {"Faithfulness": {"score": None, "error": "429"}}, {"Faithfulness": 0.8}
    )
    assert out["Faithfulness"]["passed"] is None
    assert scoring.fmt(out["Faithfulness"]) == "ERR"


def test_summary_counts_a_case_only_when_every_metric_was_scored() -> None:
    thresholds = {"A": 0.5, "B": 0.5}
    rows = [
        {
            "id": "1",
            "scores": scoring.to_scores({"A": {"score": 0.9}, "B": {"score": 0.9}}, thresholds),
        },
        {
            "id": "2",
            "scores": scoring.to_scores({"A": {"score": 0.9}, "B": {"score": 0.1}}, thresholds),
        },
        {
            "id": "3",
            "scores": scoring.to_scores(
                {"A": {"score": 0.9}, "B": {"score": None, "error": "x"}}, thresholds
            ),
        },
    ]
    s = scoring.summarise(rows, ["A", "B"])
    assert s["all_metrics_pass"] == "1/2"  # case 3 is unscored, not a pass and not a fail
    assert s["metrics"]["B"]["scored"] == "2/3"
    assert s["metrics"]["A"]["mean"] == 0.9
    assert scoring.coverage_warning(s)[0].startswith("> **PARTIAL RESULT")
    assert scoring.judge_errors(rows) == ["- **3** · B: x"]


def test_below_threshold_lists_reasons() -> None:
    rows = [
        {
            "id": "1",
            "scores": scoring.to_scores({"A": {"score": 0.2, "reason": "off topic"}}, {"A": 0.5}),
        }
    ]
    assert scoring.below_threshold(rows, ["A"]) == ["- **1** · A = 0.20: off topic"]
    assert scoring.below_threshold([], ["A"]) == ["None."]
