"""Deterministic scope checks that need no model.

A message that is only a greeting, thanks or goodbye gets a fixed reply before any LLM call,
account lookup or retrieval. Everything else is scoped by the classifier (`out_of_scope`,
`greeting` for variants like "how are you") and routed in the graph.

Matching is deliberately strict (the whole message must be social): "hi, what is my limit?"
is a real question and must go through the normal path.
"""

from __future__ import annotations

import re
from typing import Literal

GreetingKind = Literal["hello", "thanks", "bye", "about"]

_END = r"\s*[!.?,]*$"
_PATTERNS: tuple[tuple[GreetingKind, re.Pattern[str]], ...] = (
    (
        "thanks",
        re.compile(
            r"^(?:(?:ok(?:ay)?|great|cool|perfect|awesome|got it)[ ,]+)?"
            r"(?:thanks?(?: a lot| so much| again)?|thank you(?: so much| very much| again)?|"
            r"thx|ty|cheers|many thanks|much appreciated)" + _END,
            re.I,
        ),
    ),
    (
        "bye",
        re.compile(
            r"^(?:bye(?:[ -]?bye)?|good ?bye|see (?:you|ya)(?: later| soon)?|take care|"
            r"that'?s (?:all|it)|that is (?:all|it)|nothing else|no(?:thing)? more|"
            r"i'?m done|all done)" + _END,
            re.I,
        ),
    ),
    (
        "about",
        re.compile(
            r"^(?:who are you|what are you|what can you do|what do you do|"
            r"how can you help(?: me)?|what can i ask(?: you)?|can you help(?: me)?|help)" + _END,
            re.I,
        ),
    ),
    (
        "hello",
        re.compile(
            r"^(?:(?:hi+|hello+|hey+|hiya|howdy|hola|namaste|namaskar|greetings|"
            r"good (?:morning|afternoon|evening|day))"
            r"(?:[ ,]+(?:there|team|assistant|bot|everyone|all|again))?"
            r"(?:[ ,]+how are you(?: doing)?(?: today)?)?|"
            r"how are you(?: doing)?(?: today)?)" + _END,
            re.I,
        ),
    ),
)
_MAX_CHARS = 60


def greeting_kind(message: str) -> GreetingKind | None:
    text = " ".join(message.split())
    if not text or len(text) > _MAX_CHARS:
        return None
    for kind, pattern in _PATTERNS:
        if pattern.match(text):
            return kind
    return None
