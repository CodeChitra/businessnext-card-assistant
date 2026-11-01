"""Scripted StructuredLLM for tests and offline demos: no network, deterministic.

Responses are scripted per purpose ("classify", "generate", "repair"), either as fixed
objects or as callables of the messages, so tests can also return deliberately bad output
(fake citations, approvals, leaks) to exercise the guards.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from grounded_agent.llm.structured import (
    LLMCall,
    LLMUnavailable,
    StructuredResult,
    T,
    _primary_down,
)

Script = BaseModel | Callable[[Sequence[BaseMessage]], BaseModel] | Exception


class FakeStructuredLLM:
    def __init__(self, model_name: str = "fake-model") -> None:
        self.model_name = model_name
        self._scripts: dict[str, deque[Script]] = defaultdict(deque)
        self._defaults: dict[str, Script] = {}
        self.calls: list[tuple[str, list[BaseMessage]]] = []

    def script(self, purpose: str, *responses: Script) -> FakeStructuredLLM:
        """Queue responses for a purpose; consumed in order."""
        self._scripts[purpose].extend(responses)
        return self

    def default(self, purpose: str, response: Script) -> FakeStructuredLLM:
        """Response used whenever the queue for `purpose` is empty."""
        self._defaults[purpose] = response
        return self

    def prompt_text(self, purpose: str, index: int = -1) -> str:
        """Concatenated message text of a recorded call, for prompt assertions."""
        calls = [m for p, m in self.calls if p == purpose]
        return "\n".join(str(m.content) for m in calls[index])

    async def generate(
        self, purpose: str, messages: Sequence[BaseMessage], schema: type[T]
    ) -> StructuredResult[T]:
        self.calls.append((purpose, list(messages)))
        queue = self._scripts[purpose]
        script: Any = queue.popleft() if queue else self._defaults.get(purpose)
        if script is None:
            raise LLMUnavailable([f"{self.model_name}: no scripted response for {purpose!r}"])
        if isinstance(script, Exception):
            raise script
        value = script(messages) if callable(script) else script
        if not isinstance(value, schema):
            value = schema.model_validate(value.model_dump())
        primary_down = _primary_down.get()  # mimic failover: the "fallback" answers
        return StructuredResult(
            value=value,
            call=LLMCall(
                purpose=purpose,
                model=f"{self.model_name}-fallback" if primary_down else self.model_name,
                input_tokens=100,
                output_tokens=50,
                latency_ms=1,
                fallback_used=primary_down,
                errors=("fake-model: simulated primary model outage",) if primary_down else (),
            ),
        )
