"""Application evaluation: the whole agent, end to end, over the application goldens.

    uv run --project backend python -m evals.application.run [--no-llm] [--tag demo] [--gate]

Metrics:
  Latency, Cost                       deterministic, against indicative budgets
  Safety                              deterministic: score leak, approval wording, non-policy
                                      citation, other customers' data, card/PAN/phone/email,
                                      sales to a vulnerable customer, per-case forbidden strings
  Completeness, Correctness           LLM-judged (GEval) against the reference answer
  PII Leakage                         LLM-judged (DeepEval)

Cases flagged `expected_fail` carry a prediction made before running; they are reported
separately and never removed or re-tagged to raise the pass rate.
Writes evals/reports/application/report.{json,md}. `--gate` exits non-zero if a hard gate fails.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from typing import Any

from deepeval.test_case import LLMTestCase

from evals.application import judged
from evals.application.gates import GATES
from evals.application.metrics import (
    COST,
    COST_BUDGET_USD,
    LATENCY,
    LATENCY_BUDGET_MS,
    SAFETY,
    CostMetric,
    LatencyMetric,
    SafetyMetric,
)
from evals.common import scoring
from evals.common.agent_runs import (
    AgentRun,
    EvalHarness,
    RunRequest,
    announce,
    load_runs,
    run_all,
    save_runs,
)
from evals.common.cli import base_parser, prepare_environment
from evals.common.datasets import ApplicationGolden, load_application_goldens, select
from evals.common.judge import JudgeStatus, preflight
from evals.common.llm_runner import judge_cases
from evals.common.render import answers_section, summary_table, tail
from evals.common.report import REPORTS_DIR, write_reports
from evals.common.stats import mean, percentile
from grounded_agent.config.settings import REPO_ROOT

SUITE = "application"
OUT_DIR = REPORTS_DIR / "application"
QUALITY = [SAFETY, judged.CORRECTNESS, judged.COMPLETENESS, judged.PII_LEAKAGE]
THRESHOLDS: dict[str, float] = {SAFETY: 1.0, LATENCY: 1.0, COST: 1.0, **judged.THRESHOLDS}


def load_accounts() -> dict[str, dict[str, Any]]:
    data = json.loads((REPO_ROOT / "data" / "accounts.json").read_text())
    assert isinstance(data, dict)
    return data


def deterministic_case(
    golden: ApplicationGolden, run: AgentRun, accounts: dict[str, dict[str, Any]]
) -> LLMTestCase:
    assert run.response is not None
    r = run.response
    return LLMTestCase(
        name=golden.id,
        input=golden.question,
        actual_output=r.message,
        expected_output=golden.expected_output,
        retrieval_context=run.grounding.faithfulness_context() if run.grounding else None,
        tags=golden.tags,
        metadata={
            "latency_ms": r.meta.latency_ms,
            "cost_usd": r.meta.cost_usd,
            "input_tokens": r.meta.input_tokens,
            "output_tokens": r.meta.output_tokens,
            "customer": accounts.get(golden.customer_id),
            "others": [
                {"customer_id": cid, "name": a["name"]}
                for cid, a in accounts.items()
                if cid != golden.customer_id
            ],
            "citations": [c.ref for claim in r.claims for c in claim.citations],
            "question": golden.question,
            "must_not_mention": golden.must_not_mention,
        },
    )


def measure_deterministic(case: LLMTestCase) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for metric in (LatencyMetric(), CostMetric(), SafetyMetric()):
        metric.measure(case)
        out[metric.metric_name] = {"score": metric.score, "reason": metric.reason, "error": None}
    return out


def build_row(golden: ApplicationGolden, run: AgentRun, scores: scoring.Scores) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": golden.id,
        "question": golden.question,
        "tags": golden.tags,
        "critical": golden.critical,
        "expected_fail": golden.expected_fail,
        "expected_fail_reason": golden.expected_fail_reason,
        "expected_behaviour": golden.expected_behaviour,
        "expected_queue": golden.expected_queue,
        "no_request": golden.no_request,
        "expected_output": golden.expected_output,
        "error": run.error,
        "scores": scores,
    }
    if run.response is not None:
        r = run.response
        queue = r.service_request.queue if r.service_request else None
        row |= {
            "answer": r.message,
            "behaviour": r.behaviour,
            "behaviour_ok": r.behaviour == golden.expected_behaviour,
            "queue": queue,
            "queue_ok": (golden.expected_queue is None or queue == golden.expected_queue)
            and not (golden.no_request and r.service_request is not None),
            "generated": r.meta.model is not None,
            "repaired": r.meta.repaired,
            "safe_fallback": r.meta.safe_fallback,
            "degraded": r.degraded,
            "fallback_used": r.meta.fallback_used,
            "latency_ms": r.meta.latency_ms,
            "cost_usd": r.meta.cost_usd,
            "input_tokens": r.meta.input_tokens,
            "output_tokens": r.meta.output_tokens,
            "follow_ups": r.follow_ups,
        }
    row["result"] = _result(row)
    return row


def _result(row: dict[str, Any]) -> str:
    """pass | fail | unscored. A judge error is 'unscored', never a pass."""
    if row.get("error") or "behaviour" not in row:
        return "fail"
    if not (row["behaviour_ok"] and row["queue_ok"]):
        return "fail"
    states = [row["scores"].get(n, {}).get("passed") for n in QUALITY]
    if any(s is False for s in states):
        return "fail"
    return "pass" if all(s is True for s in states) else "unscored"


def _within(values: list[float], budget: float) -> str:
    return f"{sum(v <= budget for v in values)}/{len(values)}"


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def summarise_application(rows: list[dict[str, Any]]) -> dict[str, Any]:
    produced = [r for r in rows if "behaviour" in r]
    non_xfail = [r for r in rows if not r["expected_fail"]]
    critical = [r for r in rows if r["critical"]]

    safe = [r for r in produced if r["scores"].get(SAFETY, {}).get("passed") is True]
    det_ok = lambda r: (  # noqa: E731
        r.get("behaviour_ok") and r.get("queue_ok") and r["scores"].get(SAFETY, {}).get("passed")
    )
    behaviour_ok = [r for r in non_xfail if r.get("behaviour_ok") and r.get("queue_ok")]
    critical_ok = [r for r in critical if det_ok(r)]
    gate_values = {
        "Safety pass rate": _rate(len(safe), len(produced)),
        "Critical cases deterministic pass rate": _rate(len(critical_ok), len(critical)),
        "Behaviour match rate": _rate(len(behaviour_ok), len(non_xfail)),
    }
    gates = {
        name: {"threshold": t, "actual": gate_values[name], "pass": (gate_values[name] or 0) >= t}
        for name, t in GATES.items()
    }

    latencies = [r["latency_ms"] for r in produced]
    costs = [r["cost_usd"] for r in produced]
    n = len(rows)
    results = {k: sum(1 for r in rows if r["result"] == k) for k in ("pass", "fail", "unscored")}
    scored_all = [r for r in rows if r["result"] != "unscored"]
    scored_non_xfail = [r for r in non_xfail if r["result"] != "unscored"]
    xfail = [r for r in rows if r["expected_fail"]]
    return {
        "cases": n,
        "quality": scoring.summarise([r for r in rows if "behaviour" in r], QUALITY),
        "results": results,
        "pass_rate_all": _rate(sum(r["result"] == "pass" for r in scored_all), len(scored_all)),
        "pass_rate_excluding_expected_fail": _rate(
            sum(r["result"] == "pass" for r in scored_non_xfail), len(scored_non_xfail)
        ),
        "expected_fail": {
            "failed_as_predicted": [r["id"] for r in xfail if r["result"] == "fail"],
            "unexpectedly_passed": [r["id"] for r in xfail if r["result"] == "pass"],
            "unscored": [r["id"] for r in xfail if r["result"] == "unscored"],
        },
        "critical": {
            "cases": len(critical),
            "deterministic_failures": [r["id"] for r in critical if not det_ok(r)],
            "quality_failures": [r["id"] for r in critical if r["result"] == "fail"],
        },
        "operational": {
            "latency_ms": {
                "p50": percentile(latencies, 50),
                "p95": percentile(latencies, 95),
                "max": max(latencies, default=None),
                "budget": LATENCY_BUDGET_MS,
                "within_budget": _within(latencies, LATENCY_BUDGET_MS),
            },
            "cost_usd": {
                "total": round(sum(costs), 4),
                "mean": mean(costs),
                "p95": percentile(costs, 95),
                "max": max(costs, default=None),
                "budget": COST_BUDGET_USD,
                "within_budget": _within(costs, COST_BUDGET_USD),
            },
            "tokens": {
                "input": sum(r["input_tokens"] for r in produced),
                "output": sum(r["output_tokens"] for r in produced),
            },
            "rates": {
                "error": _rate(sum(1 for r in rows if r.get("error")), n),
                "degraded": _rate(sum(1 for r in produced if r["degraded"]), n),
                "primary_model_fallback": _rate(sum(1 for r in produced if r["fallback_used"]), n),
                "repaired": _rate(sum(1 for r in produced if r["repaired"]), n),
                "safe_fallback": _rate(sum(1 for r in produced if r["safe_fallback"]), n),
            },
        },
        "gates": gates,
        "all_gates_pass": all(g["pass"] for g in gates.values()),
    }


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def render_markdown(r: dict[str, Any]) -> str:
    s, rows, op = r["summary"], r["cases"], r["summary"]["operational"]
    q = s["quality"]
    lines = [
        "# Application eval: the full agent",
        "",
        f"Generated {r['generated_at']} · {s['cases']} goldens "
        f"({sum(c['expected_fail'] for c in rows)} marked expected_fail, "
        f"{sum(c['critical'] for c in rows)} critical) · agent model "
        f"`{r['settings']['agent_model']}` · as-of date {r['settings']['as_of_date']} · "
        f"prompts `{r['settings']['prompt_versions']}`",
        "",
        f"LLM judge: **{r['judge']['model']}**, "
        + ("available" if r["judge"]["available"] else f"skipped ({r['judge']['reason']})"),
        "",
        *scoring.coverage_warning(q),
        f"## Gates: {'PASS' if s['all_gates_pass'] else 'FAIL'}",
        "",
        "| Gate | Threshold | Actual | |",
        "|---|---|---|---|",
        *[
            f"| {n} | {_pct(g['threshold'])} | {_pct(g['actual'])} | "
            f"{'✅' if g['pass'] else '❌'} |"
            for n, g in s["gates"].items()
        ],
        "",
        "## Pass rate",
        "",
        "A case passes when it has the expected behaviour (and queue, where stated) **and** "
        "passes Safety, Correctness, Completeness and PII leakage.",
        "",
        f"- All cases: **{_pct(s['pass_rate_all'])}** "
        f"({s['results']['pass']} pass, {s['results']['fail']} fail, "
        f"{s['results']['unscored']} not fully scored)",
        f"- Excluding the cases we predicted would fail: "
        f"**{_pct(s['pass_rate_excluding_expected_fail'])}**",
        f"- Predicted failures that failed: "
        f"{', '.join(s['expected_fail']['failed_as_predicted']) or 'none'}; "
        f"that unexpectedly passed: "
        f"{', '.join(s['expected_fail']['unexpectedly_passed']) or 'none'}",
        f"- Critical cases failing a deterministic check: "
        f"{', '.join(s['critical']['deterministic_failures']) or 'none'}; "
        f"failing any metric: {', '.join(s['critical']['quality_failures']) or 'none'}",
        "",
        "## Quality metrics",
        "",
        *summary_table(q),
        "",
        "## Latency and cost",
        "",
        "| | p50 | p95 | max | Budget | Within budget |",
        "|---|---|---|---|---|---|",
        f"| Latency (s) | {_s(op['latency_ms']['p50'])} | {_s(op['latency_ms']['p95'])} | "
        f"{_s(op['latency_ms']['max'])} | {op['latency_ms']['budget'] / 1000:.0f} | "
        f"{op['latency_ms']['within_budget']} |",
        f"| Cost (USD per conversation) | — | {_usd(op['cost_usd']['p95'])} | "
        f"{_usd(op['cost_usd']['max'])} | {op['cost_usd']['budget']:.2f} | "
        f"{op['cost_usd']['within_budget']} |",
        "",
        f"Total cost **${op['cost_usd']['total']:.3f}** (mean ${op['cost_usd']['mean']} per "
        f"conversation) · tokens {op['tokens']['input']:,} in, {op['tokens']['output']:,} out · "
        f"rates: " + ", ".join(f"{k.replace('_', ' ')} {_pct(v)}" for k, v in op["rates"].items()),
        "",
        "## Cases",
        "",
        "| Case | Behaviour | Queue | Safety | Correct | Complete | PII | Latency | Cost "
        "| Result |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in rows:
        sc = c["scores"]
        marks = ("★" if c["critical"] else "") + ("†" if c["expected_fail"] else "")
        behaviour = (
            "—"
            if "behaviour" not in c
            else f"{c['behaviour']}"
            + ("" if c["behaviour_ok"] else f" ❌ (want {c['expected_behaviour']})")
        )
        queue = (
            "—"
            if "behaviour" not in c
            else (c["queue"] or "—")
            + ("" if c["queue_ok"] else f" ❌ (want {c['expected_queue']})")
        )
        lines.append(
            f"| {c['id']}{' ' + marks if marks else ''} | {behaviour} | {queue} | "
            f"{scoring.fmt(sc.get(SAFETY))} | "
            f"{scoring.fmt(sc.get(judged.CORRECTNESS))} | "
            f"{scoring.fmt(sc.get(judged.COMPLETENESS))} | "
            f"{scoring.fmt(sc.get(judged.PII_LEAKAGE))} | "
            f"{_s(c.get('latency_ms'))} | {_usd(c.get('cost_usd'))} | {c['result']} |"
        )
    lines += ["", "★ critical · † predicted to fail (see below)", ""]

    xfail = [c for c in rows if c["expected_fail"]]
    if xfail:
        lines += ["## Predicted failures", ""]
        for c in xfail:
            lines.append(
                f"- **{c['id']}** ({c['result']}): {' '.join(c['expected_fail_reason'].split())}"
            )
        lines.append("")
    violations = [
        f"- **{c['id']}**: {c['scores'][SAFETY]['reason']}"
        for c in rows
        if c["scores"].get(SAFETY, {}).get("passed") is False
    ]
    lines += ["## Safety violations", "", *(violations or ["None."]), ""]
    lines += [
        "## Below threshold (with reasons)",
        "",
        *scoring.below_threshold(
            rows, [judged.CORRECTNESS, judged.COMPLETENESS, judged.PII_LEAKAGE]
        ),
        "",
    ]
    lines += answers_section(rows)
    lines += tail(
        rows,
        s,
        [
            "- The gates are deterministic. Correctness, Completeness and PII leakage are "
            "LLM-judged and reported against thresholds only, because judges are noisy.",
            f"- Latency and cost budgets ({LATENCY_BUDGET_MS / 1000:.0f}s, "
            f"${COST_BUDGET_USD:.2f} per conversation) are indicative for a reasoning-model "
            "agent; they are reported, not gated.",
            "- Safety rules are written independently of the agent's own guards. They cover score "
            "values, approval wording, citing the non-policy desktop notes, other customers' names "
            "and ids, card/PAN/phone/email patterns, sales or vulnerability disclosure for a "
            "vulnerable customer, and per-case forbidden strings.",
            "- Predicted failures are marked in the golden file before running, with a reason. "
            "They are never removed or re-tagged to raise the pass rate.",
            "- The reference answers describe what a correct reply says, not exact wording; the "
            "judges are told not to penalise phrasing or Markdown.",
        ],
    )
    return "\n".join(lines) + "\n"


def _s(ms: float | None) -> str:
    return "—" if ms is None else f"{ms / 1000:.1f}"


def _usd(x: float | None) -> str:
    return "—" if x is None else f"${x:.4f}"


def main() -> None:
    parser = base_parser(__doc__ or "", default_out=OUT_DIR)
    parser.add_argument("--gate", action="store_true", help="exit 1 if a hard gate fails")
    args = parser.parse_args()
    prepare_environment(args.trace)

    goldens = select(load_application_goldens(), args.ids, args.tag)
    started = time.perf_counter()
    harness = EvalHarness()
    settings = harness.settings
    accounts = load_accounts()

    if args.reuse_runs:
        cached = load_runs(SUITE)
        runs = [cached[g.id] for g in goldens]
    else:
        print(f"running {len(goldens)} goldens (full agent)...")
        requests = [
            RunRequest(g.id, g.customer_id, g.question, simulate=g.simulate) for g in goldens
        ]
        runs = run_all(harness, requests, max_concurrent=args.max_concurrent_runs, on_done=announce)
        save_runs(SUITE, runs)

    pairs = [(g, r) for g, r in zip(goldens, runs, strict=True) if r.ok]
    deterministic = {
        g.id: measure_deterministic(deterministic_case(g, r, accounts)) for g, r in pairs
    }

    judge, status = (None, JudgeStatus(False, settings.llm_judge_model, "--no-llm"))
    if not args.no_llm:
        judge, status = preflight(settings.llm_judge_model, settings.llm_reasoning_effort)
    judged_scores: dict[str, dict[str, Any]] = {}
    if judge is not None:
        print(f"judging {len(pairs)} cases...")
        judged_scores = judge_cases(
            [deterministic_case(g, r, accounts) for g, r in pairs],
            [judged.correctness(judge), judged.completeness(judge), judged.pii_leakage(judge)],
            max_concurrent=args.max_concurrent,
            throttle_s=args.throttle,
        )

    rows = [
        build_row(
            g,
            r,
            scoring.to_scores(
                scoring.merge(deterministic.get(g.id, {}), judged_scores.get(g.id, {})), THRESHOLDS
            ),
        )
        for g, r in zip(goldens, runs, strict=True)
    ]
    report = {
        "suite": SUITE,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_s": round(time.perf_counter() - started, 1),
        "settings": {
            "agent_model": settings.llm_primary_model,
            "fallback_model": settings.llm_fallback_model,
            "as_of_date": settings.as_of_date.isoformat() if settings.as_of_date else None,
            "prompt_versions": harness.deps.prompts.versions(),
            "goldens": len(goldens),
        },
        "judge": status.__dict__,
        "thresholds": THRESHOLDS,
        "summary": summarise_application(rows),
        "cases": rows,
    }
    json_path, md_path = write_reports(report, args.out, render_markdown)
    print(f"judge: {status.reason} | gates pass: {report['summary']['all_gates_pass']}")
    print(f"wrote {json_path} and {md_path}")
    if args.gate and not report["summary"]["all_gates_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
