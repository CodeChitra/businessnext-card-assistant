#!/usr/bin/env python3
# ruff: noqa: E501  (the edge table and SVG strings are layout data, not logic)
"""Draw the agent's workflow as docs/workflow.svg, straight from the compiled LangGraph.

The layout is hand-placed (so it reads well); the *edges* are checked against the real graph.
`render()` raises if the drawing and the graph disagree, and a test fails if the committed SVG
is stale, so the picture cannot silently drift from the code.

    PYTHONPATH=backend/src uv run --project backend python scripts/workflow_diagram.py
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "workflow.svg"

W, H = 1780, 718
BOX_W, BOX_H = 150, 58
X0, STEP = 45, 190
ROW1, ROW2 = 130, 310

# name: (column or x, row y, title, what it does, kind)
#   kind: ai = a model call, code = plain code, tool = a supplied tool, exit = early exit / fallback
NODES: dict[str, tuple[int, int, str, str]] = {
    "input_guard": (X0 + STEP * 0, ROW1, "door guard", "code"),
    "classify": (X0 + STEP * 1, ROW1, "scope + intent", "ai"),
    "load_account": (X0 + STEP * 2, ROW1, "fetch the account", "tool"),
    "retrieve": (X0 + STEP * 3, ROW1, "find policy pages", "code"),
    "policy": (X0 + STEP * 4, ROW1, "rules engine", "code"),
    "generate": (X0 + STEP * 5, ROW1, "write the reply", "ai"),
    "validate": (X0 + STEP * 6, ROW1, "citations + guards", "code"),
    "act": (X0 + STEP * 7, ROW1, "raise the request", "tool"),
    "finalize": (X0 + STEP * 8, ROW1, "package + receipt", "code"),
    "short_circuit": (X0 + STEP * 1, ROW2, "fixed reply, no AI", "exit"),
    "uncovered": (X0 + STEP * 3, ROW2, "refuse + route", "exit"),
    "repair": (1110, ROW2, "fix it, once", "ai"),
    "safe_fallback": (1290, ROW2, "safe message", "exit"),
}
START_X, END_X, PILL_Y = 120, 1640, 66

STYLE = {  # fill, stroke, dash
    "ai": ("#FBF1DC", "#9A6200", ""),
    "code": ("#E3F1EF", "#0B6E69", ""),
    "tool": ("#E9EFF5", "#17324D", ""),
    "exit": ("#FFFFFF", "#60717E", "6 4"),
}
INK, MUTED = "#15202B", "#60717E"


def _box(name: str) -> tuple[int, int]:
    x, y, *_ = NODES[name]
    return x, y


def _pt(name: str, side: str, dx: int = 0) -> tuple[int, int]:
    x, y = _box(name)
    return {
        "l": (x, y + BOX_H // 2),
        "r": (x + BOX_W, y + BOX_H // 2),
        "t": (x + BOX_W // 2 + dx, y),
        "b": (x + BOX_W // 2 + dx, y + BOX_H),
    }[side]


# (source, target): (points, dashed, label, label x, label y, anchor)
def _edges() -> dict[tuple[str, str], tuple[list[tuple[int, int]], bool, str, int, int, str]]:
    sc_top = lambda dx: (_box("short_circuit")[0] + BOX_W // 2 + dx, ROW2)  # noqa: E731
    return {
        ("__start__", "input_guard"): (
            [(START_X, PILL_Y + 24), _pt("input_guard", "t")],
            False,
            "",
            0,
            0,
            "start",
        ),
        ("input_guard", "classify"): (
            [_pt("input_guard", "r"), _pt("classify", "l")],
            True,
            "",
            0,
            0,
            "start",
        ),
        ("input_guard", "short_circuit"): (
            [_pt("input_guard", "b", -20), sc_top(-55)],
            True,
            "",
            0,
            0,
            "start",
        ),
        ("classify", "load_account"): (
            [_pt("classify", "r"), _pt("load_account", "l")],
            True,
            "",
            0,
            0,
            "start",
        ),
        ("classify", "short_circuit"): ([_pt("classify", "b"), sc_top(0)], True, "", 0, 0, "start"),
        ("load_account", "retrieve"): (
            [_pt("load_account", "r"), _pt("retrieve", "l")],
            True,
            "",
            0,
            0,
            "start",
        ),
        ("load_account", "short_circuit"): (
            [_pt("load_account", "b", -10), sc_top(55)],
            True,
            "",
            0,
            0,
            "start",
        ),
        ("retrieve", "policy"): (
            [_pt("retrieve", "r"), _pt("policy", "l")],
            True,
            "",
            0,
            0,
            "start",
        ),
        ("retrieve", "uncovered"): (
            [_pt("retrieve", "b"), _pt("uncovered", "t")],
            True,
            "banking question, nothing relevant",
            698,
            262,
            "start",
        ),
        ("policy", "generate"): (
            [_pt("policy", "r"), _pt("generate", "l")],
            False,
            "",
            0,
            0,
            "start",
        ),
        ("generate", "validate"): (
            [_pt("generate", "r"), _pt("validate", "l")],
            False,
            "",
            0,
            0,
            "start",
        ),
        ("validate", "act"): (
            [_pt("validate", "r"), _pt("act", "l")],
            True,
            "pass",
            1355,
            147,
            "middle",
        ),
        ("validate", "repair"): (
            [_pt("validate", "b", -30), _pt("repair", "t", 30)],
            True,
            "send back once",
            1204,
            262,
            "end",
        ),
        ("repair", "validate"): (
            [_pt("repair", "t", 60), _pt("validate", "b", 0)],
            False,
            "re-check",
            1262,
            262,
            "start",
        ),
        ("validate", "safe_fallback"): (
            [_pt("validate", "b", 30), _pt("safe_fallback", "t", 0)],
            True,
            "fails again",
            1344,
            230,
            "start",
        ),
        ("safe_fallback", "act"): (
            [_pt("safe_fallback", "r"), (1470, _pt("safe_fallback", "r")[1]), (1470, ROW1 + BOX_H)],
            False,
            "",
            0,
            0,
            "start",
        ),
        ("uncovered", "act"): (
            [
                _pt("uncovered", "b"),
                (_pt("uncovered", "b")[0], 440),
                (1500, 440),
                (1500, ROW1 + BOX_H),
            ],
            False,
            "hand to a person: a request is raised",
            1090,
            432,
            "middle",
        ),
        ("short_circuit", "finalize"): (
            [
                _pt("short_circuit", "b"),
                (_pt("short_circuit", "b")[0], 530),
                (END_X, 530),
                (END_X, ROW1 + BOX_H),
            ],
            False,
            "reply goes out as is",
            1000,
            522,
            "middle",
        ),
        ("act", "finalize"): ([_pt("act", "r"), _pt("finalize", "l")], False, "", 0, 0, "start"),
        ("finalize", "__end__"): (
            [_pt("finalize", "t"), (END_X, PILL_Y + 24)],
            False,
            "",
            0,
            0,
            "start",
        ),
    }


def render(graph_edges: set[tuple[str, str]]) -> str:
    """The SVG, or a ValueError naming every edge the drawing and the real graph disagree on."""
    edges = _edges()
    drawn = set(edges)
    if drawn != graph_edges:
        raise ValueError(
            f"diagram and graph disagree. In the graph but not drawn: {sorted(graph_edges - drawn)}; "
            f"drawn but not in the graph: {sorted(drawn - graph_edges)}"
        )
    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif" role="img" '
        'aria-label="The agent workflow, drawn from the compiled graph">',
        f'<rect width="{W}" height="{H}" fill="#F4F7F8"/>',
        "<defs>"
        f'<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>',
        f'<text x="45" y="36" font-size="22" font-weight="600" fill="{INK}">How one question travels through the agent</text>',
    ]
    for label, cx in (("message in", START_X), ("reply out", END_X)):
        out.append(
            f'<rect x="{cx - 52}" y="{PILL_Y - 4}" width="104" height="28" rx="14" fill="#fff" stroke="{MUTED}"/>'
            f'<text x="{cx}" y="{PILL_Y + 15}" font-size="13" text-anchor="middle" fill="{INK}">{label}</text>'
        )
    for (_src, _dst), (pts, dashed, label, lx, ly, anchor) in edges.items():
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        out.append(
            f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="1.6"{dash} marker-end="url(#a)"/>'
        )
        if label:
            out.append(
                f'<text x="{lx}" y="{ly}" font-size="12" font-style="italic" text-anchor="{anchor}" '
                f'fill="{MUTED}">{escape(label)}</text>'
            )
    for name, (x, y, what, kind) in NODES.items():
        fill, stroke, dash = STYLE[kind]
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(
            f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.8"{da}/>'
            f'<text x="{x + BOX_W // 2}" y="{y + 25}" font-size="15" font-weight="600" text-anchor="middle" fill="{INK}">{escape(name)}</text>'
            f'<text x="{x + BOX_W // 2}" y="{y + 44}" font-size="12" text-anchor="middle" fill="{MUTED}">{escape(what)}</text>'
        )
    # legend and notes
    ly = 590
    out.append(f'<text x="45" y="{ly}" font-size="13" font-weight="600" fill="{INK}">Key</text>')
    for i, (kind, label) in enumerate(
        (
            ("ai", "a model call"),
            ("code", "plain code, no model"),
            ("tool", "a supplied tool"),
            ("exit", "early exit or fallback"),
        )
    ):
        fill, stroke, dash = STYLE[kind]
        da = f' stroke-dasharray="{dash}"' if dash else ""
        x = 45 + i * 230
        out.append(
            f'<rect x="{x}" y="{ly + 14}" width="28" height="18" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{da}/>'
            f'<text x="{x + 38}" y="{ly + 28}" font-size="13" fill="{INK}">{label}</text>'
        )
    out.append(
        f'<path d="M980,{ly + 23} L1030,{ly + 23}" stroke="{INK}" stroke-width="1.6" marker-end="url(#a)"/>'
        f'<text x="1040" y="{ly + 28}" font-size="13" fill="{INK}">always</text>'
        f'<path d="M1110,{ly + 23} L1160,{ly + 23}" stroke="{INK}" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#a)"/>'
        f'<text x="1170" y="{ly + 28}" font-size="13" fill="{INK}">decided by a check</text>'
    )
    out.append(
        f'<text x="45" y="{ly + 62}" font-size="13" fill="{MUTED}">Early exits skip everything after them: a pure greeting or another '
        f"customer's data (door guard), a greeting or off-topic question (scope + intent), an unknown customer (fetch the account).</text>"
        f'<text x="45" y="{ly + 82}" font-size="13" fill="{MUTED}">The model writes the reply but never decides: the rules engine decides, '
        f"and plain code checks the model's work before anything reaches the customer.</text>"
    )
    out.append(
        f'<text x="45" y="{ly + 112}" font-size="12" fill="{MUTED}">Drawn from the compiled LangGraph by '
        f"scripts/workflow_diagram.py; a test fails if this picture and the real graph ever disagree.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def graph_edges_of(compiled_graph: object) -> set[tuple[str, str]]:
    g = compiled_graph.get_graph()  # type: ignore[attr-defined]
    return {(e.source, e.target) for e in g.edges}


def main() -> int:
    from datetime import date

    from grounded_agent.bootstrap import build_runtime
    from grounded_agent.config.settings import Settings
    from grounded_agent.llm.fake import FakeStructuredLLM

    rt = build_runtime(
        Settings(as_of_date=date(2026, 8, 25), tool_latency_ms=0),
        llm=FakeStructuredLLM(),
        load_env=False,
    )
    svg = render(graph_edges_of(rt.agent._graph))
    OUT.write_text(svg)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(svg):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
