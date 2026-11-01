"""The harness, run offline with a scripted LLM: pinning, grounding capture, cache, faults."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from evals.common import agent_runs
from evals.common.agent_runs import (
    AgentRun,
    EvalHarness,
    PinnedRetriever,
    RunRequest,
    generator_text,
    load_runs,
    run_all,
    save_runs,
)
from grounded_agent.domain.response import (
    AgentResponse,
    DraftClaim,
    DraftResponse,
    IntentResult,
    ServiceRequestRef,
)
from grounded_agent.llm.fake import FakeStructuredLLM


def _fake() -> FakeStructuredLLM:
    fake = FakeStructuredLLM()
    fake.default(
        "classify",
        IntentResult(intent="fee", search_query="foreign currency markup", explicit_request=False),
    )
    msg = "The foreign currency markup is 3.5%."
    fake.default(
        "generate",
        DraftResponse(
            behaviour="answer",
            message=msg,
            claims=[DraftClaim(text=msg, citations=["POL-FEE-007#body"])],
        ),
    )
    return fake


@pytest.fixture(scope="module")
def harness() -> Iterator[EvalHarness]:
    yield EvalHarness(llm=_fake())


def test_clock_is_pinned_and_random_timeouts_are_off(harness: EvalHarness) -> None:
    assert harness.settings.as_of_date == agent_runs.EVAL_AS_OF
    assert harness.settings.tool_timeout_rate == 0.0


async def test_pinned_retrieval_replaces_live_retrieval(harness: EvalHarness) -> None:
    run = await harness.run_one(
        "T-1",
        "CUST-2007",
        "What is the markup in Singapore?",
        pinned_chunks=["POL-FEE-007#body"],
    )
    assert run.ok, run.error
    assert [c.chunk_id for c in run.grounding.retrieved] == ["POL-FEE-007#body"]  # type: ignore[union-attr]
    assert run.response.behaviour == "answer"  # type: ignore[union-attr]
    assert run.grounding.miss is False  # type: ignore[union-attr]


async def test_grounding_is_what_the_generator_was_shown(harness: EvalHarness) -> None:
    run = await harness.run_one("T-2", "CUST-2007", "Markup?", pinned_chunks=["POL-FEE-007#body"])
    ctx = run.grounding.faithfulness_context()  # type: ignore[union-attr]
    assert ctx[0].startswith("[POL-FEE-007#body]")
    assert any(c.startswith("ACCOUNT FACTS:") and "CUST-2007" in c for c in ctx)
    assert any(c.startswith("RULE OUTCOMES:") for c in ctx)
    # The internal score must never reach the generator, and so never reaches the judge's context.
    assert "behavioural_score" not in "\n".join(ctx)
    # Retrieval-side context is just what the retriever returned, tagged with trust.
    assert run.grounding.retrieval_context()[0].startswith("[POL-FEE-007#body | trust=policy]")  # type: ignore[union-attr]


async def test_live_retrieval_is_used_when_nothing_is_pinned(harness: EvalHarness) -> None:
    run = await harness.run_one("T-3", "CUST-2007", "What is the markup in Singapore?")
    assert run.ok, run.error
    assert "POL-FEE-007#body" in [c.chunk_id for c in run.grounding.retrieved]  # type: ignore[union-attr]


async def test_forced_timeout_degrades_instead_of_failing(harness: EvalHarness) -> None:
    run = await harness.run_one(
        "T-4",
        "CUST-2000",
        "Is my fee waived?",
        simulate="timeout",
        pinned_chunks=["POL-FEE-007#body"],
    )
    assert run.ok, run.error
    assert run.response.degraded is True  # type: ignore[union-attr]
    assert "UNAVAILABLE" in run.grounding.account_facts  # type: ignore[union-attr]


async def test_a_bad_gold_chunk_is_a_recorded_failure_not_a_crash(harness: EvalHarness) -> None:
    run = await harness.run_one("T-5", "CUST-2007", "q", pinned_chunks=["POL-NOPE#body"])
    assert not run.ok
    assert run.error is not None and "KeyError" in run.error


@pytest.mark.parametrize("pinned", [None, ["POL-FEE-007#body"]], ids=["live", "pinned"])
async def test_grounding_capture_survives_strict_msgpack(
    monkeypatch: pytest.MonkeyPatch, pinned: list[str] | None
) -> None:
    # LangGraph will block unregistered checkpoint types by default in a future version; the
    # allow-list in bootstrap keeps the snapshot typed so the judges still get their context.
    monkeypatch.setenv("LANGGRAPH_STRICT_MSGPACK", "true")
    strict = EvalHarness(llm=_fake())
    run = await strict.run_one("T-6", "CUST-2007", "What is the markup?", pinned_chunks=pinned)
    assert run.ok, run.error
    assert run.grounding.policy_context[0].startswith("[POL-FEE-007#body]")  # type: ignore[union-attr]


def test_pinned_retriever_with_no_chunks_is_a_miss(harness: EvalHarness) -> None:
    retriever = PinnedRetriever([], harness.deps.chunk_index.get_chunk)
    result = retriever.retrieve(["anything", "else"])
    assert result.miss and not result.hits


def test_run_all_keeps_order_and_reports_progress(harness: EvalHarness) -> None:
    seen: list[str] = []
    reqs = [
        RunRequest("A", "CUST-2007", "markup?", pinned_chunks=("POL-FEE-007#body",)),
        RunRequest("B", "CUST-2007", "markup again?", pinned_chunks=("POL-FEE-007#body",)),
    ]
    runs = run_all(harness, reqs, max_concurrent=2, on_done=lambda r, _d, _t: seen.append(r.id))
    assert [r.id for r in runs] == ["A", "B"]
    assert sorted(seen) == ["A", "B"]


def test_runs_roundtrip_through_the_cache(
    harness: EvalHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_runs, "CACHE_DIR", tmp_path)
    runs = run_all(
        harness, [RunRequest("A", "CUST-2007", "markup?", pinned_chunks=("POL-FEE-007#body",))]
    )
    save_runs("unit", runs)
    loaded = load_runs("unit")
    assert loaded["A"].response == runs[0].response
    assert loaded["A"].grounding == runs[0].grounding
    with pytest.raises(FileNotFoundError, match="--reuse-runs"):
        load_runs("never-run")


def test_generator_text_strips_only_what_the_system_appended() -> None:
    base = AgentResponse(behaviour="raise_request", message="We will look into the payment.")
    with_receipt = base.model_copy(
        update={
            "message": "We will look into the payment.\n\nI've raised request SR-1A2B3C4D "
            "(transaction dispute). You can expect an update within 2 working days.",
            "service_request": ServiceRequestRef(
                request_id="SR-1A2B3C4D", queue="DISPUTES", sla_hours=16
            ),
        }
    )
    assert generator_text(with_receipt) == "We will look into the payment."
    degraded = AgentResponse(
        behaviour="answer",
        message=f"{agent_runs.DEGRADED_PREFIX} The markup is 3.5%.",
        degraded=True,
    )
    assert generator_text(degraded) == "The markup is 3.5%."
    assert generator_text(base) == "We will look into the payment."


def test_a_failed_run_is_not_ok() -> None:
    assert not AgentRun(id="x", customer_id="c", question="q", error="boom").ok
