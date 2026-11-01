"""HTTP contract tests: real FastAPI app, scripted LLM, hashing embedder (no network)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from grounded_agent.api.app import UNEXPECTED, create_app
from grounded_agent.bootstrap import build_runtime
from grounded_agent.config.settings import REPO_ROOT, Settings
from grounded_agent.domain.response import AgentResponse, DraftClaim, DraftResponse, IntentResult
from grounded_agent.llm.fake import FakeStructuredLLM

MARKUP = DraftResponse(
    behaviour="answer",
    message="The foreign currency markup is 3.5%.",
    claims=[DraftClaim(text="Markup is 3.5%", citations=["POL-FEE-007#body"])],
)


def scripted() -> FakeStructuredLLM:
    fake = FakeStructuredLLM()
    fake.default(
        "classify",
        IntentResult(intent="fee", search_query="foreign currency markup", explicit_request=False),
    )
    fake.default("generate", MARKUP)
    return fake


@pytest.fixture
def make_client(tmp_path: Path, hashing_embedder: Any) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(fake: FakeStructuredLLM | None = None, demo_faults: bool = False) -> TestClient:
        settings = Settings(
            data_dir=REPO_ROOT / "data",
            cache_dir=tmp_path / "cache",
            as_of_date=date(2026, 8, 25),
            tool_latency_ms=0,
            tool_timeout_rate=0.0,
            demo_faults=demo_faults,
        )
        llm = fake or scripted()
        app = create_app(
            settings,
            runtime_factory=lambda: build_runtime(
                settings, llm=llm, embedder=hashing_embedder, load_env=False
            ),
        )
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()  # runs the lifespan
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


def sse_events(text: str) -> list[tuple[str, Any]]:
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields.get("data", "null"))))
    return events


def test_health_reports_index_models_and_prompts(make_client) -> None:  # type: ignore[no-untyped-def]
    body = make_client().get("/health").json()
    assert body["status"] == "ok" and body["chunks_indexed"] == 17
    assert body["as_of_date"] == "2026-08-25"
    assert set(body["prompt_versions"]) == {"classify", "generate", "repair"}
    assert body["demo_faults"] is False


def test_customers_list_for_the_picker(make_client) -> None:  # type: ignore[no-untyped-def]
    rows = make_client().get("/api/customers").json()
    assert len(rows) == 10 and set(rows[0]) == {"customer_id", "name", "card_product"}


def test_policy_chunk_lookup_for_citation_chips(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client()
    fee = client.get("/api/policies/POL-FEE-007/body").json()
    assert fee["trust"] == "policy" and "3.5%" in fee["text"]
    assert client.get("/api/policies/POL-OPS-012/body").json()["trust"] == "non_policy"
    assert client.get("/api/policies/POL-XXX-000/body").status_code == 404


def test_chat_returns_validated_response_with_thread_id(make_client) -> None:  # type: ignore[no-untyped-def]
    res = make_client().post(
        "/api/chat", json={"customer_id": "CUST-2007", "message": "Markup in Singapore?"}
    )
    assert res.status_code == 200
    body = AgentResponse.model_validate(res.json())
    assert body.behaviour == "answer" and body.meta.thread_id


def test_stream_emits_progress_then_one_final(make_client) -> None:  # type: ignore[no-untyped-def]
    res = make_client().post(
        "/api/chat/stream", json={"customer_id": "CUST-2007", "message": "Markup in Singapore?"}
    )
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    events = sse_events(res.text)
    kinds = [k for k, _ in events]
    assert kinds[-1] == "final" and kinds.count("final") == 1
    steps = [d["step"] for k, d in events if k == "progress"]
    assert steps[:4] == ["input_guard", "classify", "load_account", "retrieve"]
    assert "validate" in steps
    final = AgentResponse.model_validate(events[-1][1])
    assert final.message == MARKUP.message
    assert "behavioural_score" not in res.text  # nothing internal leaks into the stream


def test_simulate_requires_demo_faults(make_client) -> None:  # type: ignore[no-untyped-def]
    req = {"customer_id": "CUST-2007", "message": "Markup?", "simulate": "timeout"}
    assert make_client().post("/api/chat", json=req).status_code == 400
    assert make_client().post("/api/chat/stream", json=req).status_code == 400
    res = make_client(demo_faults=True).post("/api/chat", json=req)
    assert res.status_code == 200 and res.json()["degraded"] is True


def test_request_validation(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client()
    assert client.post("/api/chat", json={"customer_id": "bob", "message": "hi"}).status_code == 422
    assert (
        client.post("/api/chat", json={"customer_id": "CUST-2007", "message": ""}).status_code
        == 422
    )


def test_unexpected_fault_is_generic_never_a_stack_trace(make_client) -> None:  # type: ignore[no-untyped-def]
    fake = FakeStructuredLLM().default("classify", RuntimeError("boom: internal detail"))
    client = make_client(fake)
    req = {"customer_id": "CUST-2007", "message": "Markup?"}
    res = client.post("/api/chat", json=req)
    assert res.status_code == 500 and res.json() == {"error": UNEXPECTED, "detail": None}
    stream = client.post("/api/chat/stream", json=req)
    assert sse_events(stream.text)[-1] == ("error", {"error": UNEXPECTED, "detail": None})
    assert "internal detail" not in res.text + stream.text


def test_rewind_needs_a_thread_and_forks_it(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client()
    body = {"customer_id": "CUST-2007", "message": "markup?"}
    assert client.post("/api/chat", json={**body, "rewind_to": 0}).status_code == 400
    first = client.post("/api/chat", json=body).json()
    again = client.post(
        "/api/chat", json={**body, "thread_id": first["meta"]["thread_id"], "rewind_to": 0}
    )
    assert again.status_code == 200
    assert again.json()["meta"]["thread_id"] != first["meta"]["thread_id"]
    assert (
        client.post("/api/chat", json={**body, "thread_id": "x", "rewind_to": -1}).status_code
        == 422
    )
