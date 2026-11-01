"""Number extraction for grounding checks.

Normalises Indian digit grouping ("1,50,000" == "150000"), percentages ("3.5%" == "3.5"),
multipliers ("1.25x") and small number words ("two reversals"), so a number the model
states can be matched against the sources it cites.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
}  # fmt: skip
_WORD = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.IGNORECASE)


def _norm(token: str) -> str:
    token = token.replace(",", "")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token.lstrip("0") or "0"


def numbers_in(text: str) -> set[str]:
    found = {_norm(m.group()) for m in _NUMBER.finditer(text)}
    found |= {_WORDS[m.group().lower()] for m in _WORD.finditer(text)}
    return found
