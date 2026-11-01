"""Component-level retrieval evaluation (standalone retriever, no generator).

    uv run --project backend python -m evals.component.retrieval.run [--no-llm]

Deterministic metrics (DeepEval custom metrics) always run. LLM-judged DeepEval metrics
(Contextual Recall / Precision / Relevancy) run when the judge model is reachable; if not,
they are reported as skipped with the reason, never silently dropped.
Writes evals/reports/component/retrieval/report.{json,md}.
"""

from __future__ import annotations

import argparse
import os
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase

from evals.common.datasets import RetrievalGolden, load_retrieval_goldens
from evals.common.judge import JudgeStatus, preflight
from evals.common.llm_runner import MetricFactory, judge_cases
from evals.common.report import REPORTS_DIR, write_reports
from evals.component.retrieval.cases import (
    QUERY_CONFIGS,
    SUITE,
    build_case,
    make_retriever,
)
from evals.component.retrieval.gates import GATED_CONFIG, GATES, LLM_THRESHOLD
from evals.component.retrieval.metrics import DETERMINISTIC_METRICS
from grounded_agent.config.settings import get_settings
from grounded_agent.observability.env import load_environment
from grounded_agent.observability.tracing import configure_tracing
from grounded_agent.retrieval.chunker import chunk_corpus
from grounded_agent.retrieval.loader import load_corpus
from grounded_agent.retrieval.vector_store import corpus_fingerprint

OUT_DIR = REPORTS_DIR / "component" / "retrieval"


def _deterministic(case: LLMTestCase, golden: RetrievalGolden) -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for metric_cls in DETERMINISTIC_METRICS:
        metric = metric_cls()
        # Ranking metrics only apply where the corpus holds the answer.
        if metric.metric_name != "Miss Detection" and not golden.answerable:
            continue
        metric.measure(case)
        scores[metric.metric_name] = {
            "score": round(metric.score, 4),
            "reason": metric.reason,
        }
    return scores


def _llm_metrics(judge: Any) -> list[MetricFactory]:
    common = {
        "threshold": LLM_THRESHOLD,
        "model": judge,
        "include_reason": True,
        "async_mode": True,
    }
    return [
        lambda: ContextualRecallMetric(**common),
        lambda: ContextualPrecisionMetric(**common),
        lambda: ContextualRelevancyMetric(**common),
    ]


def _run_llm(
    cases: list[LLMTestCase], judge: Any, max_concurrent: int, throttle_s: float
) -> dict[str, dict[str, dict[str, Any]]]:
    # Every (case, metric) gets a score or an explicit error; see evals/common/llm_runner.py.
    return judge_cases(
        cases, _llm_metrics(judge), max_concurrent=max_concurrent, throttle_s=throttle_s
    )


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def _summarise(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_metric: dict[str, list[float]] = defaultdict(list)
    for c in cases:
        for name, m in {**c["deterministic"], **c.get("llm", {})}.items():
            if m.get("score") is not None:
                by_metric[name].append(m["score"])
    summary: dict[str, Any] = {f"mean {k}": _mean(v) for k, v in sorted(by_metric.items())}
    # Coverage of LLM-judged metrics: a mean over 3 of 24 cases must not read as complete.
    errors: dict[str, int] = defaultdict(int)
    for c in cases:
        for name, m in c.get("llm", {}).items():
            if m.get("score") is None:
                errors[name] += 1
    for name in sorted({n for c in cases for n in c.get("llm", {})}):
        summary[f"scored {name}"] = f"{len(by_metric[name])}/{len(by_metric[name]) + errors[name]}"
    recall = [c["deterministic"]["Chunk Recall@k"]["score"] for c in cases if c["answerable"]]
    summary["full recall rate"] = _mean([1.0 if r == 1.0 else 0.0 for r in recall])
    summary["cases"] = len(cases)
    return summary


def _by_tag(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cases:
        for tag in c["tags"]:
            grouped[tag].append(c)
    return {tag: _summarise(cs) for tag, cs in sorted(grouped.items())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-llm", action="store_true", help="skip LLM-judged metrics")
    parser.add_argument("--llm-configs", default=GATED_CONFIG, help="comma list, e.g. raw,expanded")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--max-concurrent", type=int, default=2, help="concurrent judge cases")
    parser.add_argument("--throttle", type=float, default=1.0, help="seconds between judge cases")
    args = parser.parse_args()

    load_environment()
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    # Keep eval traffic out of the application's LangSmith project.
    os.environ["LANGSMITH_PROJECT"] = os.environ.get(
        "EVAL_LANGSMITH_PROJECT", "grounded-card-agent-evals"
    )
    tracing = configure_tracing()
    settings = get_settings()

    goldens = load_retrieval_goldens()
    retriever = make_retriever(settings)
    chunks = chunk_corpus(load_corpus(settings.corpus_dir))

    judge, judge_status = (
        None,
        JudgeStatus(False, settings.llm_judge_model, "--no-llm"),
    )
    if not args.no_llm:
        judge, judge_status = preflight(settings.llm_judge_model, settings.llm_reasoning_effort)
    llm_configs = set(args.llm_configs.split(",")) if judge else set()

    started = time.perf_counter()
    configs: dict[str, Any] = {}
    for config in QUERY_CONFIGS:
        built = [(g, build_case(g, config, retriever)) for g in goldens]
        llm_scores: dict[str, dict[str, dict[str, Any]]] = {}
        if config in llm_configs:
            llm_cases = [case for g, case in built if g.answerable]
            llm_scores = _run_llm(llm_cases, judge, args.max_concurrent, args.throttle)
        rows = []
        for g, case in built:
            meta = case.metadata or {}
            rows.append(
                {
                    "id": g.id,
                    "question": g.question,
                    "queries": meta["queries"],
                    "tags": g.tags,
                    "answerable": g.answerable,
                    "expected_chunks": g.expected_chunks,
                    "retrieved": meta["all_chunks"],
                    "miss": meta["miss"],
                    "deterministic": _deterministic(case, g),
                    "llm": llm_scores.get(case.name or "", {}),
                }
            )
        configs[config] = {
            "summary": _summarise(rows),
            "by_tag": _by_tag(rows),
            "cases": rows,
        }

    gated = configs[GATED_CONFIG]["summary"]
    gates = {
        name: {
            "threshold": t,
            "actual": gated.get(name),
            "pass": (gated.get(name) or 0) >= t,
        }
        for name, t in GATES.items()
    }
    report = {
        "suite": SUITE,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_s": round(time.perf_counter() - started, 1),
        "settings": {
            "embedding_model": settings.embedding_model,
            "top_k": settings.retrieval_top_k,
            "rrf_k": settings.rrf_k,
            "dense_min_score": settings.dense_min_score,
            "bm25_min_score": settings.bm25_min_score,
            "corpus_fingerprint": corpus_fingerprint(chunks, settings.embedding_model),
            "goldens": len(goldens),
        },
        "judge": judge_status.__dict__,
        "tracing": tracing.__dict__,
        "gated_config": GATED_CONFIG,
        "gates": gates,
        "all_gates_pass": all(g["pass"] for g in gates.values()),
        "configs": configs,
    }
    json_path, md_path = write_reports(report, args.out, render_markdown)
    print(f"gates pass: {report['all_gates_pass']} | judge: {judge_status.reason}")
    print(f"wrote {json_path} and {md_path}")


def _coverage_warning(r: dict[str, Any]) -> list[str]:
    summary = r["configs"][r["gated_config"]]["summary"]
    partial = {
        k.removeprefix("scored "): v
        for k, v in summary.items()
        if k.startswith("scored ") and v.split("/")[0] != v.split("/")[1]
    }
    if not partial:
        return []
    detail = ", ".join(f"{k} {v}" for k, v in partial.items())
    return [
        f"> **PARTIAL RESULT: LLM-judged means cover only some cases ({detail}).** "
        "Errored cases are excluded from the means; see Judge errors below.",
        "",
    ]


def render_markdown(r: dict[str, Any]) -> str:
    lines = [
        "# Component eval: retrieval",
        "",
        f"Generated {r['generated_at']} · {r['settings']['goldens']} goldens · "
        f"corpus `{r['settings']['corpus_fingerprint']}` · `{r['settings']['embedding_model']}` "
        f"· top_k={r['settings']['top_k']}",
        "",
        f"LLM judge: **{r['judge']['model']}**, "
        + ("available" if r["judge"]["available"] else f"skipped ({r['judge']['reason']})"),
        "",
        *_coverage_warning(r),
        f"## Gates (`{r['gated_config']}` config): " + ("PASS" if r["all_gates_pass"] else "FAIL"),
        "",
        "| Gate | Threshold | Actual | |",
        "|---|---|---|---|",
    ]
    for name, g in r["gates"].items():
        lines.append(
            f"| {name} | {g['threshold']} | {g['actual']} | {'✅' if g['pass'] else '❌'} |"
        )

    metric_names = sorted({k for c in r["configs"].values() for k in c["summary"] if k != "cases"})
    lines += ["", "## Raw question vs. expanded (question + intent rewrite)", ""]
    lines.append("| Metric | " + " | ".join(r["configs"]) + " |")
    lines.append("|---|" + "---|" * len(r["configs"]))
    for m in metric_names:
        vals = [str(c["summary"].get(m, "—")) for c in r["configs"].values()]
        lines.append(f"| {m} | " + " | ".join(vals) + " |")

    exp = r["configs"][r["gated_config"]]
    llm_names = sorted({k for c in exp["cases"] for k in c["llm"]})
    header = ["Case", "Recall", "RR", "Prec", "Miss ok", *llm_names, "Retrieved"]
    lines += ["", f"## Cases (`{r['gated_config']}`)", ""]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))

    def cell(case: dict[str, Any], name: str, src: str = "deterministic") -> str:
        m = case[src].get(name)
        if not m:
            return "—"
        return "ERR" if m.get("score") is None else f"{m['score']:.2f}"

    for c in exp["cases"]:
        row = [
            c["id"],
            cell(c, "Chunk Recall@k"),
            cell(c, "Reciprocal Rank"),
            cell(c, "Chunk Precision@k"),
            cell(c, "Miss Detection"),
            *[cell(c, n, "llm") for n in llm_names],
            ", ".join(f"`{x}`" for x in c["retrieved"]) or "(miss)",
        ]
        lines.append("| " + " | ".join(row) + " |")

    failures = [
        (c["id"], n, m)
        for c in exp["cases"]
        for n, m in {**c["deterministic"], **c["llm"]}.items()
        if m.get("score") is not None
        and m["score"] < (LLM_THRESHOLD if n in llm_names else 1.0)
        and n != "Chunk Precision@k"
    ]
    lines += ["", "## Below threshold (with reasons)", ""]
    lines += [f"- **{cid}** · {n} = {m['score']:.2f}: {m['reason']}" for cid, n, m in failures]
    if not failures:
        lines.append("None.")
    errored = [
        (c["id"], n, m["error"])
        for c in exp["cases"]
        for n, m in c["llm"].items()
        if m.get("score") is None
    ]
    if errored:
        lines += ["", f"## Judge errors ({len(errored)}; excluded from means)", ""]
        lines += [f"- **{cid}** · {n}: {str(err)[:160]}" for cid, n, err in errored]
    lines += [
        "",
        "## Reading this report",
        "",
        "- Chunk Precision@k is bounded by design (top_k=5, usually 1-2 relevant chunks); "
        "it is reported, not gated.",
        "- `uncovered` cases (EV-010, RG-010) have no expected chunks: retrieval cannot detect "
        "them (they look in-domain); refusal is enforced at generation by the citation validator.",
        "- `rewrite` strings are hand-written stand-ins for the intent classifier until M2; "
        "re-run once the classifier produces them.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
