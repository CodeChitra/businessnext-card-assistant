"""Provider-agnostic chat-model construction.

Models are named with LangChain provider strings ("openai:gpt-4o-mini", "anthropic:..."),
so switching provider is configuration only. Credentials and optional OpenAI-compatible
base URLs come from the standard provider environment variables (OPENAI_API_KEY,
OPENAI_BASE_URL, ANTHROPIC_API_KEY); nothing gateway-specific lives in code.
"""

from __future__ import annotations

import re
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

# Reasoning models take `reasoning_effort` and only support the default temperature.
_REASONING_MODEL = re.compile(r"(^|:)(gpt-5|o\d)", re.IGNORECASE)


def is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_MODEL.search(model))


def build_chat_model(
    model: str,
    *,
    temperature: float = 0.0,
    timeout_s: float = 60.0,
    max_retries: int = 1,
    reasoning_effort: str | None = None,
) -> BaseChatModel:
    kwargs: dict[str, Any] = {"timeout": timeout_s, "max_retries": max_retries}
    if is_reasoning_model(model):
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
    else:
        kwargs["temperature"] = temperature
    chat: BaseChatModel = init_chat_model(model, **kwargs)
    return chat
