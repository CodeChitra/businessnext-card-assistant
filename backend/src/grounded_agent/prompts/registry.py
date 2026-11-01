"""Versioned prompt templates.

Each template is a YAML file: id, version, description, system, user. The system part is
static (so provider-side prompt caching can reuse it); the user part is filled with
`$placeholders` via string.Template, which is strict and does not collide with JSON braces.
A content hash is recorded next to the version so an edit without a version bump is visible
in traces and eval reports.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from string import Template

import yaml

TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: str
    system: str
    user: str
    sha: str

    @property
    def label(self) -> str:
        return f"{self.id}@{self.version}+{self.sha}"

    def render_user(self, **values: str) -> str:
        return Template(self.user).substitute(**values)


class PromptRegistry:
    def __init__(self, directory: Path = TEMPLATES_DIR) -> None:
        self._prompts: dict[str, PromptTemplate] = {}
        for path in sorted(directory.glob("*.yaml")):
            raw = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            prompt = PromptTemplate(
                id=data["id"],
                version=str(data["version"]),
                system=data["system"].strip(),
                user=data["user"].strip(),
                sha=hashlib.sha256(raw.encode()).hexdigest()[:8],
            )
            if prompt.id in self._prompts:
                raise ValueError(f"duplicate prompt id {prompt.id} in {path.name}")
            self._prompts[prompt.id] = prompt

    def get(self, prompt_id: str) -> PromptTemplate:
        return self._prompts[prompt_id]

    def versions(self) -> dict[str, str]:
        return {p.id: p.label for p in self._prompts.values()}
