"""Reference implementation of the renderer spec — INSTRUMENT ONLY.

Exists to prove the frozen spec is implementable and the frozen checker awards
full credit to a correct solution (renderer_selftest.py), and to produce the
hand-eyeball golden (expected.svg). NEVER enters the contributor model's
workspace, context, or image — showing it would void the attribution claim.
Stdlib-only, deterministic, spec-exact.
"""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def layout(deg: dict) -> dict[str, tuple[int, int]]:
    adj: dict[str, list[str]] = {n["id"]: [] for n in deg["nodes"]}
    for e in deg["edges"]:
        adj[e["src"]].append(e["dst"])
    dist = {"start": 0}
    q = deque(["start"])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    max_reach = max(dist.values())
    depth = {n["id"]: dist.get(n["id"], max_reach + 1) for n in deg["nodes"]}
    cols: dict[int, list[str]] = {}
    for nid, d in depth.items():
        cols.setdefault(d, []).append(nid)
    pos = {}
    for d in sorted(cols):
        for row, nid in enumerate(sorted(cols[d])):
            pos[nid] = (80 + d * 170, 70 + row * 90)
    return pos


STYLE = """
    .edge { stroke: #888; stroke-width: 1.5; }
    .edge.gated { stroke-dasharray: 6 3; }
    .edge.wrong { stroke: #c0392b; opacity: 0.45; }
    .route { fill: none; stroke: #2a78d6; stroke-width: 3.5; opacity: 0.85;
             stroke-linejoin: round; }
    .node { fill: #f4f4f4; stroke: #888; stroke-width: 1.5; }
    .node.start { fill: #2a78d6; stroke: #1b4e8a; }
    .node.exit { fill: #008300; stroke: #005200; }
    .node.deadend { fill: #efd8d4; stroke: #c0392b; }
    .step { font: bold 13px sans-serif; fill: #2a78d6; text-anchor: middle; }
"""


def main() -> None:
    journal = json.loads(Path(sys.argv[1]).read_text())
    deg = json.loads(Path(sys.argv[2]).read_text())
    out_path = Path(sys.argv[3])

    pos = layout(deg)
    depths = {(x - 80) // 170 for x, _ in pos.values()}
    col_sizes: dict[int, int] = {}
    for x, _ in pos.values():
        col_sizes[x] = col_sizes.get(x, 0) + 1
    W = 160 + max(depths) * 170
    H = 140 + (max(col_sizes.values()) - 1) * 90

    commits = [e for e in journal["events"] if e["action"] == "commit"]
    has_out = {e["src"] for e in deg["edges"]}

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">',
             f'  <title>LabyrinthBench run — {esc(deg["id"])} — '
             f'{esc(journal["model"])}</title>',
             f'  <style>{STYLE}  </style>']

    for e in deg["edges"]:
        (x1, y1), (x2, y2) = pos[e["src"]], pos[e["dst"]]
        cls = "edge" + (" gated" if e["gated"] else "") + (" wrong" if e["wrong"] else "")
        parts.append(f'  <line class="{cls}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')

    pts = [pos["start"]] + [pos[c["node_id"]] for c in commits]
    parts.append('  <polyline class="route" points="'
                 + " ".join(f"{x},{y}" for x, y in pts) + '"/>')

    for n in deg["nodes"]:
        x, y = pos[n["id"]]
        cls = "node"
        if n["id"] == "start":
            cls += " start"
        if n["terminal"]:
            cls += " exit"
        if n["id"] not in has_out and not n["terminal"]:
            cls += " deadend"
        parts.append(f'  <circle class="{cls}" data-id="{esc(n["id"])}" '
                     f'cx="{x}" cy="{y}" r="18"/>')

    seen: dict[str, int] = {}
    for c in commits:
        k = seen.get(c["node_id"], 0)
        seen[c["node_id"]] = k + 1
        x, y = pos[c["node_id"]]
        parts.append(f'  <text class="step" data-step="{c["steps_used"]}" '
                     f'x="{x}" y="{y - 26 - 14 * k}">{c["steps_used"]}</text>')

    parts.append("</svg>")
    out_path.write_text("\n".join(parts) + "\n")


if __name__ == "__main__":
    main()
