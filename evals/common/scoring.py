"""Turn judge output into per-case scores, pass flags and honest summaries.

A case is only counted as passing when every metric was actually scored: a judge error never
reads as a pass, and a mean over 3 of 15 cases is labelled as such.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from evals.common.stats import mean

Scores = dict[str, dict[str, Any]]


def clean_name(name: str) -> str:
    """DeepEval names GEval metrics 'Correctness [GEval]'."""
    return name.removesuffix(" [GEval]")


def to_scores(raw: Mapping[str, Mapping[str, Any]], thresholds: Mapping[str, float]) -> Scores:
    out: Scores = {}
    for name, m in raw.items():
        key = clean_name(name)
        score = m.get("score")
        threshold = thresholds.get(key)
        out[key] = {
            "score": score,
            "reason": m.get("reason"),
            "error": m.get("error"),
            "threshold": threshold,
            "passed": None if score is None or threshold is None else score >= threshold,
        }
    return out


def merge(*parts: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for part in parts:
        merged.update({k: dict(v) for k, v in part.items()})
    return merged


def summarise(rows: Sequence[Mapping[str, Any]], names: Sequence[str]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for n in names:
        scored = [r["scores"][n] for r in rows if r["scores"].get(n, {}).get("score") is not None]
        passed = sum(1 for m in scored if m["passed"])
        metrics[n] = {
            "mean": mean([m["score"] for m in scored]),
            "pass_rate": round(passed / len(scored), 4) if scored else None,
            "scored": f"{len(scored)}/{len(rows)}",
            "threshold": next(
                (r["scores"][n]["threshold"] for r in rows if n in r["scores"]), None
            ),
        }
    complete = [
        r for r in rows if all(r["scores"].get(n, {}).get("score") is not None for n in names)
    ]
    all_pass = sum(1 for r in complete if all(r["scores"][n]["passed"] for n in names))
    return {
        "cases": len(rows),
        "metrics": metrics,
        "fully_scored": len(complete),
        "all_metrics_pass": f"{all_pass}/{len(complete)}",
    }


def fmt(m: Mapping[str, Any] | None) -> str:
    if not m:
        return "—"
    if m.get("score") is None:
        return "ERR"
    mark = "" if m.get("passed") in (None, True) else " ❌"
    return f"{m['score']:.2f}{mark}"


def below_threshold(rows: Sequence[Mapping[str, Any]], names: Sequence[str]) -> list[str]:
    lines = []
    for r in rows:
        for n in names:
            m = r["scores"].get(n)
            if m and m.get("passed") is False:
                lines.append(f"- **{r['id']}** · {n} = {m['score']:.2f}: {m.get('reason')}")
    return lines or ["None."]


def judge_errors(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        f"- **{r['id']}** · {n}: {str(m['error'])[:160]}"
        for r in rows
        for n, m in r["scores"].items()
        if m.get("score") is None and m.get("error")
    ]


def coverage_warning(summary: Mapping[str, Any]) -> list[str]:
    partial = {
        n: m["scored"]
        for n, m in summary["metrics"].items()
        if m["scored"].split("/")[0] != m["scored"].split("/")[1]
    }
    if not partial:
        return []
    detail = ", ".join(f"{k} {v}" for k, v in partial.items())
    return [
        f"> **PARTIAL RESULT: means cover only some cases ({detail}).** Errored cases are "
        "excluded from the means; see Judge errors below.",
        "",
    ]
