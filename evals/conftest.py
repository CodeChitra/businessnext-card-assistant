"""Pytest setup for eval gates.

DeepEval auto-loads dotenv files from the working directory, which would switch LangSmith
tracing on for every CI gate run. Gates trace only when EVAL_TRACE=1; the report runners
(`python -m evals...run`) trace normally into the eval project.
"""

from __future__ import annotations

import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
if os.environ.get("EVAL_TRACE") != "1":
    os.environ["LANGSMITH_TRACING"] = "false"
