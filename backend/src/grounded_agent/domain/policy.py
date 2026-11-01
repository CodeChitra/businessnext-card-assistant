from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Trust(StrEnum):
    """Whether a document may ground a policy claim."""

    POLICY = "policy"
    NON_POLICY = "non_policy"


class PolicyDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    title: str
    version: str
    effective_date: str | None
    owner: str | None
    trust: Trust
    body: str
    source_file: str
    # Lines removed by the sanitizer because they read as instructions to the model.
    quarantined_lines: tuple[str, ...] = ()


class PolicyChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str  # e.g. "POL-CRD-001#3"
    doc_id: str
    title: str
    section: str  # section number or slug; "body" when the doc has no headings
    heading: str | None
    text: str
    trust: Trust
    version: str
    effective_date: str | None
    references: tuple[str, ...] = ()  # other doc ids mentioned in this chunk

    def embedding_text(self) -> str:
        """Text used for indexing: a contextual header keeps short sections retrievable."""
        heading = f" — {self.heading}" if self.heading else ""
        return f"{self.title}{heading}\n{self.text}"
