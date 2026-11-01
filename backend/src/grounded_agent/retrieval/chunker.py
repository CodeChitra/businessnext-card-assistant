"""Section-level chunking: one chunk per '## ' section, or one per document without headings.

Policies are short and already structured by section, so section ids make citations
meaningful (POL-CRD-001#3) and never split a rule list mid-way.
"""

from __future__ import annotations

import re

from grounded_agent.domain.policy import PolicyChunk, PolicyDocument

_HEADING = re.compile(r"^##\s+(?P<heading>.+)$", re.MULTILINE)
_NUMBERED = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\.?\s")
_DOC_REF = re.compile(r"\bPOL-[A-Z]+-\d+\b")


def _section_id(heading: str) -> str:
    m = _NUMBERED.match(heading)
    if m:
        return m["num"]
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def _references(text: str, own_id: str) -> tuple[str, ...]:
    return tuple(sorted({r for r in _DOC_REF.findall(text) if r != own_id}))


def chunk_document(doc: PolicyDocument) -> list[PolicyChunk]:
    def make(section: str, heading: str | None, text: str) -> PolicyChunk:
        return PolicyChunk(
            chunk_id=f"{doc.doc_id}#{section}",
            doc_id=doc.doc_id,
            title=doc.title,
            section=section,
            heading=heading,
            text=text.strip(),
            trust=doc.trust,
            version=doc.version,
            effective_date=doc.effective_date,
            references=_references(text, doc.doc_id),
        )

    matches = list(_HEADING.finditer(doc.body))
    if not matches:
        return [make("body", None, doc.body)]

    chunks: list[PolicyChunk] = []
    preamble = doc.body[: matches[0].start()].strip()
    if preamble:
        chunks.append(make("intro", None, preamble))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc.body)
        heading = m["heading"].strip()
        chunks.append(make(_section_id(heading), heading, doc.body[m.end() : end]))
    return chunks


def chunk_corpus(docs: list[PolicyDocument]) -> list[PolicyChunk]:
    return [chunk for doc in docs for chunk in chunk_document(doc)]
