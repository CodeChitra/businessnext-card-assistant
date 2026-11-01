from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def write_reports(
    report: dict[str, Any], out_dir: Path, render_md: Callable[[dict[str, Any]], str]
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    md_path.write_text(render_md(report))
    return json_path, md_path
