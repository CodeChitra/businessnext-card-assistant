"""DeepEval judge backed by the same provider-agnostic LangChain factory as the agent.

Any `init_chat_model` provider string works, including OpenAI-compatible gateways via
OPENAI_BASE_URL. Structured outputs use `with_structured_output`, so metric JSON is
schema-constrained instead of parsed from free text (DeepEval "JSON confinement").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deepeval.models.base_model import DeepEvalBaseLLM
from pydantic import BaseModel

from grounded_agent.llm.factory import build_chat_model


class LangChainJudge(DeepEvalBaseLLM):
    def __init__(
        self, model: str, timeout_s: float = 90.0, reasoning_effort: str | None = None
    ) -> None:
        self._model_string = model
        self._chat = build_chat_model(
            model,
            temperature=0.0,
            timeout_s=timeout_s,
            max_retries=6,  # SDK backs off on 429 using retry-after
            reasoning_effort=reasoning_effort,
        )
        super().__init__(model)

    def load_model(self) -> Any:
        return self._chat

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        if schema is not None:
            return self._chat.with_structured_output(schema).invoke(prompt)
        return self._chat.invoke(prompt).content

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        if schema is not None:
            return await self._chat.with_structured_output(schema).ainvoke(prompt)
        return (await self._chat.ainvoke(prompt)).content

    def get_model_name(self) -> str:
        return self._model_string


@dataclass(frozen=True)
class JudgeStatus:
    available: bool
    model: str
    reason: str


def preflight(
    model: str, reasoning_effort: str | None = None
) -> tuple[LangChainJudge | None, JudgeStatus]:
    """One tiny call so a bad key or gateway fails fast with a readable reason."""
    try:
        judge = LangChainJudge(model, reasoning_effort=reasoning_effort)
        judge.generate("Reply with the single word OK.")
    except Exception as exc:  # report, never crash the deterministic part of a run
        reason = getattr(getattr(exc, "response", None), "text", None) or str(exc)
        return None, JudgeStatus(False, model, f"{type(exc).__name__}: {reason[:200]}")
    return judge, JudgeStatus(True, model, "ok")
