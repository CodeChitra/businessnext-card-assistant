"""Retrieval recall on the seed questions with the real local embedding model.

Raw questions alone are not enough for every case (EV-007 is a vocabulary mismatch), so the
agent adds an intent-guided rewrite; the pairs below stand in for that rewrite until M2.
Marked `model`: downloads ~130 MB on first run, then uses the cache.
"""

from __future__ import annotations

import pytest

from grounded_agent.config.settings import REPO_ROOT, Settings
from grounded_agent.retrieval.factory import build_retriever
from grounded_agent.retrieval.hybrid import HybridRetriever

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def retriever() -> HybridRetriever:
    return build_retriever(Settings(data_dir=REPO_ROOT / "data"))


CASES = [
    # (case, raw question, rewrite, doc that must be in the hits)
    (
        "EV-001",
        "My annual fee was charged, I thought it was waived.",
        "annual card fee waiver spend",
        "POL-FEE-007",
    ),
    (
        "EV-002",
        "I want my credit limit increased to 3 lakh.",
        "credit limit increase mandatory decline",
        "POL-CRD-001",
    ),
    (
        "EV-005",
        "Why can I only get a small increase?",
        "limit increase maximum cap thin file",
        "POL-CRD-003",
    ),
    # EV-006 is deliberately absent: nothing in the question points at KYC; only the account
    # state does. The rules engine pins POL-KYC-008 when that rule fires, not retrieval.
    (
        "EV-007",
        "Someone used my card at a shop I have never been to.",
        "unauthorised transaction dispute fraud",
        "POL-SVC-005",
    ),
    (
        "EV-008",
        "What is the interest rate if I do not pay in full?",
        "revolve rate interest",
        "POL-PRD-010",
    ),
    (
        "EV-009",
        "What is the markup if I use my card in Singapore?",
        "foreign currency markup",
        "POL-FEE-007",
    ),
    (
        "EV-011",
        "What is my exact CIBIL score?",
        "internal score disclosure adverse action reasons",
        "POL-GOV-009",
    ),
]


@pytest.mark.parametrize(("case", "raw", "rewrite", "doc"), CASES, ids=[c[0] for c in CASES])
def test_expected_doc_is_retrieved_with_rewrite(
    retriever: HybridRetriever, case: str, raw: str, rewrite: str, doc: str
) -> None:
    result = retriever.retrieve([raw, rewrite])
    assert doc in {h.chunk.doc_id for h in result.hits}, case


def test_rewrite_promotes_dispute_policy_to_top_for_ev007(retriever: HybridRetriever) -> None:
    # Raw wording shares almost no vocabulary with POL-SVC-005: it ranks below the fee table.
    raw = "Someone used my card at a shop I have never been to."
    raw_ids = [h.chunk.doc_id for h in retriever.retrieve(raw).hits]
    assert raw_ids[0] != "POL-SVC-005"
    rewritten = retriever.retrieve([raw, "unauthorised transaction dispute fraud"])
    assert rewritten.hits[0].chunk.doc_id == "POL-SVC-005"


@pytest.mark.parametrize(
    "q", ["What's the weather tomorrow?", "Who won the cricket match yesterday?"]
)
def test_off_domain_questions_are_misses(retriever: HybridRetriever, q: str) -> None:
    assert retriever.retrieve(q).miss


def test_uncovered_in_domain_question_is_not_a_retrieval_miss(retriever: HybridRetriever) -> None:
    # Documented limitation: refusal for this case must come from generation + citation checks.
    result = retriever.retrieve("Can I get travel insurance added to my card?")
    assert not result.miss
    assert "travel insurance" not in " ".join(h.chunk.text.lower() for h in result.hits)
