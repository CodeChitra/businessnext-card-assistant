"""The greeting matcher is strict on purpose: a false positive would swallow a real question."""

from __future__ import annotations

import pytest

from grounded_agent.guardrails.scope import greeting_kind


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Hi", "hello"),
        ("hello!", "hello"),
        ("Hey there", "hello"),
        ("Good morning", "hello"),
        ("Namaste", "hello"),
        ("hi, how are you?", "hello"),
        ("how are you", "hello"),
        ("Hello again", "hello"),
        ("Thanks", "thanks"),
        ("thank you so much!", "thanks"),
        ("ok thanks", "thanks"),
        ("Bye", "bye"),
        ("that's all", "bye"),
        ("What can you do?", "about"),
        ("who are you", "about"),
        ("help", "about"),
    ],
)
def test_pure_social_messages_are_recognised(text: str, kind: str) -> None:
    assert greeting_kind(text) == kind


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Hi, what is my credit limit?",
        "hello I lost my card",
        "thanks, but why was my fee charged?",
        "help me raise a dispute",
        "What can you do about a wrong charge on my card?",
        "bye bye the fee is wrong",
        "hi " * 40,  # long: never a bare greeting
        "Who is the Prime Minister of India?",
    ],
)
def test_anything_with_a_real_question_goes_through_the_normal_path(text: str) -> None:
    assert greeting_kind(text) is None
