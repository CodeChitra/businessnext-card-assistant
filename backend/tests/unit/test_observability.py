from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from grounded_agent.config.settings import Settings
from grounded_agent.observability import tracing
from grounded_agent.observability.env import load_environment
from grounded_agent.observability.tracing import TracedRetriever, _as_documents, configure_tracing
from grounded_agent.retrieval.factory import build_retriever


def test_env_local_overrides_env_but_real_env_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("A_ONLY=from_env\nSHARED=from_env\nREAL=from_env\n")
    (tmp_path / ".env.local").write_text("SHARED=from_local\n")
    for key in ("A_ONLY", "SHARED"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("REAL", "from_shell")
    exported = load_environment(tmp_path)
    import os

    assert os.environ["SHARED"] == "from_local"
    assert os.environ["REAL"] == "from_shell"
    assert exported == ["A_ONLY", "SHARED"]


def test_tracing_off_without_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    assert configure_tracing().enabled is False


def test_flag_without_key_disables_instead_of_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    status = configure_tracing()
    assert status.enabled is False and "missing" in status.reason
    import os

    assert os.environ["LANGSMITH_TRACING"] == "false"


def test_flag_and_key_enable_with_default_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "x")
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    status = configure_tracing()
    assert status.enabled and status.project == tracing.DEFAULT_PROJECT


def test_traced_retriever_is_transparent_and_emits_langsmith_documents(
    settings: Settings, hashing_embedder: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    inner = build_retriever(settings, embedder=hashing_embedder)
    traced = TracedRetriever(inner)
    result = traced.retrieve(["foreign currency markup"])
    assert result.chunk_ids == inner.retrieve(["foreign currency markup"]).chunk_ids
    assert traced.chunks == inner.chunks  # attribute passthrough

    docs = _as_documents(result)
    assert docs and all(d["type"] == "Document" and d["page_content"] for d in docs)
    assert {"chunk_id", "trust", "via", "rrf_score", "dense_score"} <= set(docs[0]["metadata"])
