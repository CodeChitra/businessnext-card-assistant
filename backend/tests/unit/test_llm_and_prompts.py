from __future__ import annotations

from typing import Any, ClassVar

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from grounded_agent.llm.structured import (
    LangChainStructuredLLM,
    LLMUnavailable,
    NamedModel,
    force_primary_down,
)
from grounded_agent.observability.metrics import PriceTable, summarise_calls
from grounded_agent.prompts.registry import PromptRegistry


class Out(BaseModel):
    answer: str


class _Raw:
    usage_metadata: ClassVar[dict[str, int]] = {"input_tokens": 11, "output_tokens": 7}


class _Runnable:
    def __init__(self, behaviour: Any) -> None:
        self._behaviour = behaviour

    async def ainvoke(self, *_: Any, **__: Any) -> dict[str, Any]:
        if isinstance(self._behaviour, Exception):
            raise self._behaviour
        return self._behaviour


class StubModel:
    """Duck-typed chat model: only with_structured_output is used by the port."""

    def __init__(self, behaviour: Any) -> None:
        self.behaviour = behaviour

    def with_structured_output(self, schema: type, include_raw: bool = False) -> _Runnable:
        return _Runnable(self.behaviour)


OK = {"raw": _Raw(), "parsed": Out(answer="hi"), "parsing_error": None}
MSGS = [HumanMessage("q")]


async def test_primary_answers_without_fallback() -> None:
    llm = LangChainStructuredLLM([NamedModel("openai:gpt-4o-mini", StubModel(OK))])  # type: ignore[arg-type]
    result = await llm.generate("generate", MSGS, Out)
    assert result.value.answer == "hi"
    assert (result.call.input_tokens, result.call.output_tokens, result.call.fallback_used) == (
        11,
        7,
        False,
    )


async def test_fails_over_on_provider_error_and_records_why() -> None:
    llm = LangChainStructuredLLM(
        [
            NamedModel("primary", StubModel(ConnectionError("503"))),  # type: ignore[arg-type]
            NamedModel("fallback", StubModel(OK)),  # type: ignore[arg-type]
        ]
    )
    result = await llm.generate("generate", MSGS, Out)
    assert result.call.model == "fallback" and result.call.fallback_used
    assert "primary" in result.call.errors[0]


async def test_schema_parse_failure_also_fails_over() -> None:
    bad = {"raw": _Raw(), "parsed": None, "parsing_error": ValueError("bad json")}
    llm = LangChainStructuredLLM(
        [NamedModel("p", StubModel(bad)), NamedModel("f", StubModel(OK))]  # type: ignore[arg-type]
    )
    assert (await llm.generate("x", MSGS, Out)).call.model == "f"


async def test_all_models_down_raises_llm_unavailable() -> None:
    llm = LangChainStructuredLLM([NamedModel("p", StubModel(TimeoutError()))])  # type: ignore[arg-type]
    with pytest.raises(LLMUnavailable):
        await llm.generate("x", MSGS, Out)


async def test_simulated_primary_outage_uses_fallback() -> None:
    llm = LangChainStructuredLLM(
        [NamedModel("p", StubModel(OK)), NamedModel("f", StubModel(OK))]  # type: ignore[arg-type]
    )
    with force_primary_down():
        assert (await llm.generate("x", MSGS, Out)).call.model == "f"
    assert (await llm.generate("x", MSGS, Out)).call.model == "p"


async def test_cost_accounting_uses_price_table() -> None:
    llm = LangChainStructuredLLM([NamedModel("openai:gpt-4o-mini", StubModel(OK))])  # type: ignore[arg-type]
    call = (await llm.generate("x", MSGS, Out)).call
    summary = summarise_calls([call], PriceTable())
    assert summary["cost_usd"] == pytest.approx((11 * 0.15 + 7 * 0.60) / 1e6, abs=1e-6)
    unknown = summarise_calls(
        [call.__class__(**{**call.__dict__, "model": "x:unknown"})], PriceTable()
    )
    assert unknown["unpriced_models"] == ["x:unknown"]


def test_prompt_registry_versions_and_strict_rendering() -> None:
    reg = PromptRegistry()
    assert set(reg.versions()) == {"classify", "generate", "repair"}
    assert reg.get("generate").label.startswith("generate@5+")
    with pytest.raises(KeyError):
        reg.get("classify").render_user()  # missing $message
    assert "Singapore" in reg.get("classify").render_user(
        message="Singapore markup?", history="(none)"
    )
