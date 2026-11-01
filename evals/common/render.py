"""Markdown fragments shared by the generation, pipeline and application reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from evals.common.scoring import coverage_warning, judge_errors


def summary_table(summary: Mapping[str, Any]) -> list[str]:
    lines = [
        "| Metric | Threshold | Mean | Pass rate | Scored |",
        "|---|---|---|---|---|",
    ]
    for name, m in summary["metrics"].items():
        rate = "—" if m["pass_rate"] is None else f"{m['pass_rate']:.0%}"
        lines.append(f"| {name} | {m['threshold']} | {m['mean']} | {rate} | {m['scored']} |")
    lines += [
        "",
        f"Cases where every metric passed: **{summary['all_metrics_pass']}** "
        f"(of cases fully scored; {summary['cases']} cases in total).",
    ]
    return lines


def flags(row: Mapping[str, Any]) -> str:
    notes = []
    if row.get("error"):
        notes.append("run failed")
    elif not row.get("generated", True):
        notes.append("no generator call (deterministic reply)")
    if row.get("safe_fallback"):
        notes.append("safe fallback")
    if row.get("repaired"):
        notes.append("repaired once")
    if row.get("degraded"):
        notes.append("degraded")
    return ", ".join(notes) or "—"


def answers_section(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["## Answers", ""]
    for r in rows:
        lines += [
            f"<details><summary><b>{r['id']}</b> — {r['question']}</summary>",
            "",
            "**Reply**",
            "",
            *[
                f"> {line}" if line else ">"
                for line in (r.get("answer") or "(no reply)").splitlines()
            ],
            "",
            f"**Reference:** {r.get('expected_output', '—')}",
            "",
            "</details>",
            "",
        ]
    return lines


def tail(
    rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any], notes: Sequence[str]
) -> list[str]:
    lines: list[str] = []
    errors = judge_errors(rows)
    if errors:
        lines += ["", f"## Judge errors ({len(errors)}; excluded from means)", "", *errors]
    failed = [f"- **{r['id']}**: {r['error']}" for r in rows if r.get("error")]
    if failed:
        lines += ["", f"## Agent runs that failed ({len(failed)})", "", *failed]
    lines += ["", "## Reading this report", "", *notes]
    return lines


__all__ = ["answers_section", "coverage_warning", "flags", "summary_table", "tail"]
