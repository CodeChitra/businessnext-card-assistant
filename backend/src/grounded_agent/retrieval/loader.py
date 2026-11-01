from __future__ import annotations

import re
from pathlib import Path

from grounded_agent.domain.policy import PolicyDocument
from grounded_agent.retrieval.sanitizer import classify_trust, strip_instructions

# "Document ID: POL-CRD-001 | Version 4.2 | Effective 01-Apr-2026 | Owner: Credit Policy"
_META_LINE = re.compile(
    r"^Document ID:\s*(?P<doc_id>POL-[A-Z]+-\d+)\s*\|(?P<rest>.*)$", re.MULTILINE
)


def _meta_field(rest: str, key: str) -> str | None:
    m = re.search(rf"{key}:?\s+([^|]+)", rest)
    return m.group(1).strip() if m else None


def parse_document(text: str, source_file: str) -> PolicyDocument:
    lines = text.strip().splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"{source_file}: expected a '# Title' first line")
    title = lines[0][2:].strip()
    meta = _META_LINE.search(text)
    if meta is None:
        raise ValueError(f"{source_file}: missing 'Document ID:' metadata line")
    rest = meta["rest"]
    raw_body = text[meta.end() :].strip()
    version = _meta_field(rest, "Version") or "unknown"
    body, removed = strip_instructions(raw_body)
    return PolicyDocument(
        doc_id=meta["doc_id"],
        title=title,
        version=version,
        effective_date=_meta_field(rest, "Effective"),
        owner=_meta_field(rest, "Owner"),
        trust=classify_trust(version, raw_body),
        body=body.strip(),
        source_file=source_file,
        quarantined_lines=removed,
    )


def load_corpus(corpus_dir: Path) -> list[PolicyDocument]:
    files = sorted(corpus_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No policy documents found in {corpus_dir}")
    return [parse_document(f.read_text(encoding="utf-8"), f.name) for f in files]
