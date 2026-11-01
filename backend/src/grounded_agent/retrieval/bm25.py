from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

from grounded_agent.domain.policy import PolicyChunk
from grounded_agent.retrieval.base import Vector

_STOPWORDS = frozenset(
    (
        "a an and are as at be by can do does for from has have how i if in is it its me my "
        "of on or our please the this to was what when where which who why will with you your"
    ).split()
)
_TOKEN = re.compile(r"pol-[a-z]+-\d+|\d+(?:\.\d+)?%?|[a-z]+")


def tokenize(text: str) -> list[str]:
    # Indian digit grouping ("1,50,000") collapses to "150000" so amounts match either way.
    text = re.sub(r"(?<=\d),(?=\d)", "", text.lower())
    return [t for t in _TOKEN.findall(text) if len(t) > 1 and t not in _STOPWORDS]


class BM25Index:
    def __init__(self, chunks: list[PolicyChunk]) -> None:
        self._bm25 = BM25Okapi([tokenize(c.embedding_text()) for c in chunks])

    def score_all(self, query: str) -> Vector:
        tokens = tokenize(query)
        if not tokens:
            return np.zeros(self._bm25.corpus_size, dtype=np.float32)
        return np.asarray(self._bm25.get_scores(tokens), dtype=np.float32)
