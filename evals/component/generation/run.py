"""Component-level generation evaluation: the generator alone, retrieval held fixed.

    uv run --project backend python -m evals.component.generation.run [--no-llm] [--ids ...]

Each golden pins its gold chunks in place of live retrieval, so the generator is the only part
that varies. The tools, rules engine, classifier and citation validator still run for real.
Metrics (LLM-judged DeepEval): Faithfulness, Answer Relevancy. Faithfulness is judged against
everything the generator was shown (policy chunks, account facts, rule outcomes), and only the
model's own words are judged (the receipt the system appends is stripped).
Writes evals/reports/component/generation/report.{json,md}.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from deepeval.test_case import LLMTestCase

from evals.common import scoring
from evals.common.agent_runs import (
    AgentRun,
    EvalHarness,
    RunRequest,
    announce,
    generator_text,
    load_runs,
    run_all,
    save_runs,
)
from evals.common.cli import base_parser, prepare_environment
from evals.common.datasets import GenerationGolden, load_generation_goldens, select
from evals.common.judge import JudgeStatus, preflight
from evals.common.llm_metrics import (
    ANSWER_RELEVANCY,
    FAITHFULNESS,
    THRESHOLDS,
    answer_relevancy,
    faithfulness,
)
from evals.common.llm_runner import judge_cases
from evals.common.render import answers_section, flags, summary_table, tail
from evals.common.report import REPORTS_DIR, write_reports

SUITE = "component.generation"
OUT_DIR = REPORTS_DIR / "component" / "generation"
METRICS = [FAITHFULNESS, ANSWER_RELEVANCY]


def build_case(golden: GenerationGolden, run: AgentRun) -> LLMTestCase:
    assert run.response is not None and run.grounding is not None
    return LLMTestCase(
        name=golden.id,
        input=golden.question,
        actual_output=generator_text(run.response),
        expected_output=golden.expected_output,
        retrieval_context=run.grounding.faithfulness_context(),
        tags=golden.tags,
    )


def build_row(golden: GenerationGolden, run: AgentRun, scores: scoring.Scores) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": golden.id,
        "question": golden.question,
        "tags": golden.tags,
        "gold_chunks": golden.gold_chunks,
        "expected_output": golden.expected_output,
        "error": run.error,
        "scores": scores,
    }
    if run.response is not None and run.grounding is not None:
        r = run.response
        row |= {
            "answer": generator_text(r),
            "behaviour": r.behaviour,
            "generated": r.meta.model is not None,
            "repaired": r.meta.repaired,
            "safe_fallback": r.meta.safe_fallback,
            "degraded": r.degraded,
            "shown_to_generator": [
                c.split("]")[0].lstrip("[") for c in run.grounding.policy_context
            ],
        }
    return row


def render_markdown(r: dict[str, Any]) -> str:
    s, rows = r["summary"], r["cases"]
    lines = [
        "# Component eval: generation (retrieval held fixed)",
        "",
        f"Generated {r['generated_at']} · {len(rows)} goldens · agent model "
        f"`{r['settings']['agent_model']}` · prompts `{r['settings']['prompt_versions']}`",
        "",
        f"LLM judge: **{r['judge']['model']}**, "
        + ("available" if r["judge"]["available"] else f"skipped ({r['judge']['reason']})"),
        "",
        *scoring.coverage_warning(s),
        "## Summary",
        "",
        *summary_table(s),
        "",
        "## Cases",
        "",
        "| Case | Faithfulness | Answer relevancy | Behaviour | Notes |",
        "|---|---|---|---|---|",
    ]
    for c in rows:
        lines.append(
            f"| {c['id']} | {scoring.fmt(c['scores'].get(FAITHFULNESS))} | "
            f"{scoring.fmt(c['scores'].get(ANSWER_RELEVANCY))} | {c.get('behaviour', '—')} | "
            f"{flags(c)} |"
        )
    lines += [
        "",
        "## Below threshold (with reasons)",
        "",
        *scoring.below_threshold(rows, METRICS),
        "",
    ]
    lines += answers_section(rows)
    lines += tail(
        rows,
        s,
        [
            "- Retrieval is pinned to each golden's gold chunks, so these scores isolate the "
            "generator. Live retrieval is covered by the retrieval and pipeline evals.",
            "- Faithfulness is judged against everything the generator was shown: the policy "
            "chunks, the account facts and the rule outcomes. A claim about the customer's own "
            "account is grounded by the account facts, not by policy text.",
            "- Answer relevancy of a refusal or decline is judged against the question like any "
            "other reply, so deliberate refusals (EV-010, EV-011, EV-012) can score lower by "
            "design; read the reply, not just the score.",
            "- LLM-judged scores are reported against thresholds, not gated: judges are noisy.",
        ],
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = base_parser(__doc__ or "", default_out=OUT_DIR)
    args = parser.parse_args()
    prepare_environment(args.trace)

    goldens = select(load_generation_goldens(), args.ids, args.tag)
    started = time.perf_counter()
    harness = EvalHarness()
    settings = harness.settings

    if args.reuse_runs:
        cached = load_runs(SUITE)
        runs = [cached[g.id] for g in goldens]
    else:
        print(f"running {len(goldens)} goldens (generator only, retrieval pinned)...")
        requests = [
            RunRequest(g.id, g.customer_id, g.question, pinned_chunks=tuple(g.gold_chunks))
            for g in goldens
        ]
        runs = run_all(harness, requests, max_concurrent=args.max_concurrent_runs, on_done=announce)
        save_runs(SUITE, runs)

    judge, status = (None, JudgeStatus(False, settings.llm_judge_model, "--no-llm"))
    if not args.no_llm:
        judge, status = preflight(settings.llm_judge_model, settings.llm_reasoning_effort)

    scored: dict[str, dict[str, Any]] = {}
    if judge is not None:
        pairs = [(g, r) for g, r in zip(goldens, runs, strict=True) if r.ok]
        print(f"judging {len(pairs)} cases...")
        scored = judge_cases(
            [build_case(g, r) for g, r in pairs],
            [faithfulness(judge), answer_relevancy(judge)],
            max_concurrent=args.max_concurrent,
            throttle_s=args.throttle,
        )
    rows = [
        build_row(g, r, scoring.to_scores(scored.get(g.id, {}), THRESHOLDS))
        for g, r in zip(goldens, runs, strict=True)
    ]
    report = {
        "suite": SUITE,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_s": round(time.perf_counter() - started, 1),
        "settings": {
            "agent_model": settings.llm_primary_model,
            "as_of_date": settings.as_of_date.isoformat() if settings.as_of_date else None,
            "prompt_versions": harness.deps.prompts.versions(),
            "goldens": len(goldens),
        },
        "judge": status.__dict__,
        "thresholds": {k: THRESHOLDS[k] for k in METRICS},
        "summary": scoring.summarise(rows, METRICS),
        "cases": rows,
    }
    json_path, md_path = write_reports(report, args.out, render_markdown)
    print(f"judge: {status.reason}\nwrote {json_path} and {md_path}")


if __name__ == "__main__":
    main()
