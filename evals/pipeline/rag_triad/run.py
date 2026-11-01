"""Pipeline evaluation: the RAG triad on live retrieval + generation.

    uv run --project backend python -m evals.pipeline.rag_triad.run [--no-llm] [--ids ...]

Nothing is pinned: the real retriever, tools, rules and generator run for each golden. Three
LLM-judged DeepEval metrics, each answering one question about the pipeline:

  Contextual Relevancy  did retrieval return context that is relevant to the question?
                        (judged against what the retriever returned)
  Faithfulness          is the reply grounded in what the generator was shown?
                        (policy chunks + account facts + rule outcomes; only the model's own
                        words are judged, not the receipt the system appends)
  Answer Relevancy      does the reply address the question that was asked?

Writes evals/reports/pipeline/rag_triad/report.{json,md}.
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
from evals.common.datasets import PipelineGolden, load_pipeline_goldens, select
from evals.common.judge import JudgeStatus, preflight
from evals.common.llm_metrics import (
    ANSWER_RELEVANCY,
    CONTEXTUAL_RELEVANCY,
    FAITHFULNESS,
    THRESHOLDS,
    answer_relevancy,
    contextual_relevancy,
    faithfulness,
)
from evals.common.llm_runner import judge_groups
from evals.common.render import answers_section, flags, summary_table, tail
from evals.common.report import REPORTS_DIR, write_reports

SUITE = "pipeline.rag_triad"
OUT_DIR = REPORTS_DIR / "pipeline" / "rag_triad"
METRICS = [CONTEXTUAL_RELEVANCY, FAITHFULNESS, ANSWER_RELEVANCY]


def build_cases(golden: PipelineGolden, run: AgentRun) -> tuple[LLMTestCase, LLMTestCase]:
    """(retrieval-side case, grounding-side case): same reply, different context."""
    assert run.response is not None and run.grounding is not None
    answer = generator_text(run.response)
    common: dict[str, Any] = {
        "name": golden.id,
        "input": golden.question,
        "actual_output": answer,
        "expected_output": golden.expected_output,
        "tags": golden.tags,
    }
    return (
        LLMTestCase(**common, retrieval_context=run.grounding.retrieval_context()),
        LLMTestCase(**common, retrieval_context=run.grounding.faithfulness_context()),
    )


def build_row(golden: PipelineGolden, run: AgentRun, scores: scoring.Scores) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": golden.id,
        "question": golden.question,
        "tags": golden.tags,
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
            "retrieved": [c.chunk_id for c in run.grounding.retrieved],
            "retrieval_miss": run.grounding.miss,
        }
    return row


def render_markdown(r: dict[str, Any]) -> str:
    s, rows = r["summary"], r["cases"]
    lines = [
        "# Pipeline eval: RAG triad (live retrieval + generation)",
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
        "| Case | Contextual relevancy | Faithfulness | Answer relevancy | Behaviour | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for c in rows:
        sc = c["scores"]
        lines.append(
            f"| {c['id']} | {scoring.fmt(sc.get(CONTEXTUAL_RELEVANCY))} | "
            f"{scoring.fmt(sc.get(FAITHFULNESS))} | {scoring.fmt(sc.get(ANSWER_RELEVANCY))} | "
            f"{c.get('behaviour', '—')} | {flags(c)} |"
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
            "- Contextual relevancy is judged on everything the retriever returned (top-k plus "
            "cross-referenced chunks), so it is bounded by design: only one or two chunks answer "
            "a given question. It is a signal for retrieval quality, not a target of 1.0.",
            "- Faithfulness is judged against what the generator was actually shown (policy "
            "chunks, account facts, rule outcomes), not just policy text.",
            "- Refusals and declines are judged against the question like any other reply, so "
            "deliberate refusals (EV-010, EV-011, EV-012) can score lower on answer relevancy by "
            "design; read the reply, not just the score.",
            "- LLM-judged scores are reported against thresholds, not gated: judges are noisy.",
        ],
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = base_parser(__doc__ or "", default_out=OUT_DIR)
    args = parser.parse_args()
    prepare_environment(args.trace)

    goldens = select(load_pipeline_goldens(), args.ids, args.tag)
    started = time.perf_counter()
    harness = EvalHarness()
    settings = harness.settings

    if args.reuse_runs:
        cached = load_runs(SUITE)
        runs = [cached[g.id] for g in goldens]
    else:
        print(f"running {len(goldens)} goldens (live retrieval + generation)...")
        requests = [RunRequest(g.id, g.customer_id, g.question) for g in goldens]
        runs = run_all(harness, requests, max_concurrent=args.max_concurrent_runs, on_done=announce)
        save_runs(SUITE, runs)

    judge, status = (None, JudgeStatus(False, settings.llm_judge_model, "--no-llm"))
    if not args.no_llm:
        judge, status = preflight(settings.llm_judge_model, settings.llm_reasoning_effort)

    scored: dict[str, dict[str, Any]] = {}
    if judge is not None:
        pairs = [(g, r) for g, r in zip(goldens, runs, strict=True) if r.ok]
        built = [build_cases(g, r) for g, r in pairs]
        print(f"judging {len(pairs)} cases...")
        scored = judge_groups(
            [
                (
                    [retrieval for retrieval, _ in built],
                    [contextual_relevancy(judge), answer_relevancy(judge)],
                ),
                ([grounding for _, grounding in built], [faithfulness(judge)]),
            ],
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
            "top_k": settings.retrieval_top_k,
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
