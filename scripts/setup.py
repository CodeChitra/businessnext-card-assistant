"""One-command setup for backend and frontend. Standard library only, so it runs on
Windows, macOS and Linux with any Python 3: `python scripts/setup.py`."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_NODE_MAJOR = 20


def fail(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    sys.exit(1)


def require(tool: str, hint: str) -> str:
    # which() resolves Windows shims such as npm.cmd, which bare subprocess names miss.
    path = shutil.which(tool)
    if path is None:
        fail(f"'{tool}' not found on PATH. {hint}")
    return str(path)


def run(step: str, cmd: list[str], cwd: Path) -> None:
    print(f"\n==> {step}  (in {cwd.name}/)")
    if subprocess.run(cmd, cwd=cwd).returncode != 0:
        fail(f"'{step}' failed (see output above).")


def check_node(node: str) -> None:
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    try:
        major = int(out.lstrip("v").split(".")[0])
    except ValueError:
        fail(f"Could not read the Node version from '{out}'.")
    if major < MIN_NODE_MAJOR:
        fail(f"Node {MIN_NODE_MAJOR}+ is required (CI uses 22); found {out}.")


def ensure_env_file() -> bool:
    target = ROOT / ".env.local"
    if target.exists():
        return False
    shutil.copyfile(ROOT / ".env.example", target)
    return True


def main() -> None:
    uv = require("uv", "Install it from https://docs.astral.sh/uv/getting-started/installation/")
    node = require("node", "Install Node 22 from https://nodejs.org/")
    npm = require("npm", "It ships with Node: https://nodejs.org/")
    check_node(node)

    run("Backend dependencies", [uv, "sync", "--all-groups"], ROOT / "backend")
    run("Frontend dependencies", [npm, "ci"], ROOT / "frontend")
    created = ensure_env_file()

    print("\nSetup complete.\n")
    if created:
        print("Created .env.local from .env.example. Edit it: set OPENAI_API_KEY and LLM_* models.")
    else:
        print(".env.local already exists and was left untouched.")
    print(
        "\nThen run, in two terminals:\n"
        "  1) cd backend  &&  uv run uvicorn grounded_agent.api.app:app --reload --port 8000\n"
        "  2) cd frontend &&  npm run dev\n"
        "Open http://localhost:5173"
    )


if __name__ == "__main__":
    main()