"""Export `.env` / `.env.local` into os.environ for third-party SDKs.

pydantic-settings reads these files for our own Settings but does not export them, while
LangChain, the OpenAI SDK and LangSmith read os.environ directly. Precedence matches
Settings: real environment variables win, then `.env.local`, then `.env`.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

from grounded_agent.config.settings import REPO_ROOT


def load_environment(root: Path = REPO_ROOT) -> list[str]:
    """Return the names (never values) of variables that were exported."""
    merged: dict[str, str] = {}
    for name in (".env", ".env.local"):
        path = root / name
        if path.exists():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    exported = [k for k in merged if k not in os.environ]
    for k in exported:
        os.environ[k] = merged[k]
    return sorted(exported)
