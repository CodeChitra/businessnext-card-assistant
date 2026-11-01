"""Annual-fee waiver thresholds parsed from POL-FEE-007, like the queue catalogue."""

from __future__ import annotations

import re
from pathlib import Path

FEES_DOC_GLOB = "POL-FEE-007*.md"
# "| Annual card fee, Classic | Waived on spend of 1,50,000 in the card year |"
_WAIVER_ROW = re.compile(
    r"\|\s*Annual card fee,\s*(?P<product>\w+)\s*\|\s*Waived on spend of (?P<amount>[\d,]+)",
)


def parse_waiver_thresholds(text: str) -> dict[str, int]:
    thresholds = {
        m["product"]: int(m["amount"].replace(",", "")) for m in _WAIVER_ROW.finditer(text)
    }
    if not thresholds:
        raise ValueError("POL-FEE-007 could not be parsed into waiver thresholds")
    return thresholds


def load_waiver_thresholds(corpus_dir: Path) -> dict[str, int]:
    matches = sorted(corpus_dir.glob(FEES_DOC_GLOB))
    if not matches:
        raise FileNotFoundError(f"Fees policy {FEES_DOC_GLOB} not found in {corpus_dir}")
    return parse_waiver_thresholds(matches[0].read_text(encoding="utf-8"))


def format_inr(amount: int) -> str:
    """Indian digit grouping, as used throughout the corpus: 162000 -> '1,62,000'."""
    s = str(abs(amount))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head)
        s = f"{head},{tail}"
    return f"-{s}" if amount < 0 else s
