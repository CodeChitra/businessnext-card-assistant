"""Release gates for the retriever. Deterministic only, so CI can enforce them without keys.

Gated config is `expanded` (raw question + intent rewrite), which is what the agent runs.
`raw` is reported to show what query expansion buys, never gated.
"""

GATED_CONFIG = "expanded"

GATES: dict[str, float] = {
    "mean Chunk Recall@k": 0.90,
    "mean Reciprocal Rank": 0.70,
    "mean Miss Detection": 1.00,
}

# LLM-judged contextual metrics: reported against this threshold, not gated (judge noise).
LLM_THRESHOLD = 0.7
