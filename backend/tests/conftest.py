from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pytest

from grounded_agent.config.settings import REPO_ROOT, Settings
from grounded_agent.retrieval.base import Vector

DATA_DIR = REPO_ROOT / "data"


class HashingEmbedder:
    """Deterministic bag-of-words embedder: no model download, good enough to test fusion logic."""

    model_name = "test-hashing-64"

    def _vec(self, text: str) -> Vector:
        v = np.zeros(64, dtype=np.float32)
        for tok in re.findall(r"[a-z]+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 64] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts: list[str]) -> Vector:
        return np.stack([self._vec(t) for t in texts])

    def embed_query(self, text: str) -> Vector:
        return self._vec(text)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=DATA_DIR, cache_dir=tmp_path / "cache", tool_latency_ms=0)


@pytest.fixture
def hashing_embedder() -> HashingEmbedder:
    return HashingEmbedder()
