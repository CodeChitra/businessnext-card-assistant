from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"


class RetrievalGolden(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    question: str
    rewrite: str
    expected_chunks: list[str]
    expected_miss: bool
    expected_output: str | None = None
    tags: list[str] = []

    @model_validator(mode="after")
    def _consistent(self) -> RetrievalGolden:
        if self.expected_miss and self.expected_chunks:
            raise ValueError(f"{self.id}: a miss case cannot expect chunks")
        if self.expected_chunks and not self.expected_output:
            raise ValueError(f"{self.id}: answerable cases need a reference expected_output")
        return self

    @property
    def answerable(self) -> bool:
        return bool(self.expected_chunks)


def load_retrieval_goldens(
    path: Path = DATASETS_DIR / "retrieval_goldens.yaml",
) -> list[RetrievalGolden]:
    goldens = [RetrievalGolden.model_validate(row) for row in yaml.safe_load(path.read_text())]
    ids = [g.id for g in goldens]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate golden ids")
    return goldens


# --- Generation, pipeline and application goldens ------------------------------------------

Behaviour = Literal["answer", "decline_with_reason", "refuse", "raise_request"]


class _Golden(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    customer_id: str
    question: str
    expected_output: str
    tags: list[str] = []


class GenerationGolden(_Golden):
    """Generator under a fixed context: `gold_chunks` replace live retrieval."""

    gold_chunks: list[str]


class PipelineGolden(_Golden):
    """Retrieval + generation, nothing pinned."""


class ApplicationGolden(_Golden):
    expected_behaviour: Behaviour
    expected_queue: str | None = None
    no_request: bool = False  # the reply must NOT raise a service request (no human review)
    grounding_docs: list[str] = []
    must_not_mention: list[str] = []
    simulate: Literal["timeout", "primary_down"] | None = None
    critical: bool = False
    expected_fail: bool = False
    expected_fail_reason: str | None = None

    @model_validator(mode="after")
    def _expected_fail_needs_a_reason(self) -> ApplicationGolden:
        if self.expected_fail and not (self.expected_fail_reason or "").strip():
            raise ValueError(f"{self.id}: expected_fail needs an expected_fail_reason")
        return self


G = TypeVar("G", bound=_Golden)


def _load(path: Path, model: type[G]) -> list[G]:
    goldens = [model.model_validate(row) for row in yaml.safe_load(path.read_text())]
    ids = [g.id for g in goldens]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path.name}: duplicate golden ids")
    return goldens


def load_generation_goldens(
    path: Path = DATASETS_DIR / "generation_goldens.yaml",
) -> list[GenerationGolden]:
    return _load(path, GenerationGolden)


def load_pipeline_goldens(
    path: Path = DATASETS_DIR / "pipeline_goldens.yaml",
) -> list[PipelineGolden]:
    return _load(path, PipelineGolden)


def load_application_goldens(
    path: Path = DATASETS_DIR / "application_goldens.yaml",
) -> list[ApplicationGolden]:
    return _load(path, ApplicationGolden)


def select(goldens: Sequence[G], ids: str | None = None, tag: str | None = None) -> list[G]:
    """Narrow a run to some ids and/or a tag; unknown ids are an error, not a silent no-op."""
    chosen = list(goldens)
    if ids:
        wanted = [i.strip() for i in ids.split(",") if i.strip()]
        unknown = sorted(set(wanted) - {g.id for g in chosen})
        if unknown:
            raise ValueError(f"unknown golden ids: {', '.join(unknown)}")
        chosen = [g for g in chosen if g.id in wanted]
    if tag:
        chosen = [g for g in chosen if tag in g.tags]
    if not chosen:
        raise ValueError("selection matched no goldens")
    return chosen
