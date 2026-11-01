"""Structured-output LLM port with primary -> fallback failover and usage accounting.

Nodes depend on the `StructuredLLM` protocol, not on LangChain, so tests inject a scripted
fake and providers can change without touching the graph.

Failover is explicit rather than `.with_fallbacks()` so every call records which model
answered and why the primary was skipped. A schema-parse failure counts as a failure and
also falls over. If every model fails, `LLMUnavailable` is raised and the agent serves a
static safe response (no LLM involved).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LLMCall:
    """Accounting for one logical structured call (after any failover)."""

    purpose: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    fallback_used: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class StructuredResult(Generic[T]):
    value: T
    call: LLMCall


_primary_down: ContextVar[bool] = ContextVar("primary_down", default=False)


@contextmanager
def force_primary_down() -> Iterator[None]:
    """Demo/eval fault: make the primary model fail for calls in this context only."""
    token = _primary_down.set(True)
    try:
        yield
    finally:
        _primary_down.reset(token)


class LLMUnavailable(Exception):
    def __init__(self, errors: Sequence[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = tuple(errors)


class StructuredLLM(Protocol):
    async def generate(
        self, purpose: str, messages: Sequence[BaseMessage], schema: type[T]
    ) -> StructuredResult[T]: ...


@dataclass(frozen=True)
class NamedModel:
    name: str
    model: BaseChatModel


def _usage(raw: Any) -> tuple[int, int]:
    usage = getattr(raw, "usage_metadata", None) or {}
    return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))


class LangChainStructuredLLM:
    def __init__(self, models: Sequence[NamedModel]) -> None:
        if not models:
            raise ValueError("at least one model is required")
        self._models = list(models)

    async def generate(
        self, purpose: str, messages: Sequence[BaseMessage], schema: type[T]
    ) -> StructuredResult[T]:
        errors: list[str] = []
        for i, named in enumerate(self._models):
            started = time.perf_counter()
            try:
                if i == 0 and _primary_down.get():
                    raise ConnectionError("simulated primary model outage")
                runnable = named.model.with_structured_output(schema, include_raw=True)
                out = await runnable.ainvoke(
                    list(messages), config={"run_name": f"{purpose}:{named.name}"}
                )
                if not isinstance(out, dict):  # include_raw=True always returns a dict
                    raise TypeError(f"unexpected structured output type {type(out).__name__}")
                if out.get("parsing_error") is not None or out.get("parsed") is None:
                    raise ValueError(f"schema parse failed: {out.get('parsing_error')}")
                value = out["parsed"]
                if not isinstance(value, schema):
                    value = schema.model_validate(value)
                tokens_in, tokens_out = _usage(out.get("raw"))
                return StructuredResult(
                    value=value,
                    call=LLMCall(
                        purpose=purpose,
                        model=named.name,
                        input_tokens=tokens_in,
                        output_tokens=tokens_out,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        fallback_used=i > 0,
                        errors=tuple(errors),
                    ),
                )
            except Exception as exc:  # any provider failure moves to the next model
                msg = f"{named.name}: {type(exc).__name__}: {str(exc)[:160]}"
                log.warning("LLM %s failed for %s; %s", named.name, purpose, msg)
                errors.append(msg)
        raise LLMUnavailable(errors)
