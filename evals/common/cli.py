"""Shared command-line and environment setup for the report runners."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from grounded_agent.observability.env import load_environment
from grounded_agent.observability.tracing import configure_tracing


def base_parser(description: str, *, default_out: Path) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--ids", help="comma list of golden ids to run, e.g. EV-001,EV-004")
    p.add_argument("--tag", help="only goldens carrying this tag (e.g. demo)")
    p.add_argument("--no-llm", action="store_true", help="skip LLM-judged metrics")
    p.add_argument(
        "--reuse-runs",
        action="store_true",
        help="re-judge the agent runs cached by the previous run instead of calling the agent",
    )
    p.add_argument("--max-concurrent-runs", type=int, default=3, help="concurrent agent runs")
    p.add_argument("--max-concurrent", type=int, default=3, help="concurrent judge cases")
    p.add_argument("--throttle", type=float, default=1.0, help="seconds between judge starts")
    p.add_argument("--trace", action="store_true", help="send LangSmith traces for this run")
    p.add_argument("--out", type=Path, default=default_out)
    return p


def prepare_environment(trace: bool) -> None:
    """Quiet by default: eval runs make many calls and must not depend on LangSmith access."""
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    if trace:
        os.environ["LANGSMITH_PROJECT"] = os.environ.get(
            "EVAL_LANGSMITH_PROJECT", "grounded-card-agent-evals"
        )
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
    load_environment()
    if trace:
        configure_tracing()
