"""Frozen checker for the renderer rung — deterministic, stdlib-only, no LLM judge.

Runs in the task workspace (cwd must hold render_trace.py, journal.json,
deg.json). Recomputes the spec's layout formulas independently, runs the
model's script TWICE (determinism), then structurally verifies the SVG.

Prints one line per check:  "OK <name>"  or  "FAIL <name> -- <detail>",
then "PASSED <n>/<total>". Exit 0 iff all checks pass.

The model may read and run this file freely (tests-as-spec); the harness's
final verdict uses a pristine copy baked into the target image at /lb/, so
editing the workspace copy changes nothing.

Frozen 2026-07-18 BEFORE any contributor-model session (attribution protocol:
spec + checker are human/Claude-authored instrument; the model authors only
render_trace.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

TOL = 0.5
RENDER_TIMEOUT = 20

CHECK_NAMES = ["renders_ok", "deterministic", "valid_svg_viewbox", "title_present",
               "style_present", "nodes_complete", "node_positions", "node_classes",
               "edges_complete", "route_correct", "step_labels"]


# ---------- expected geometry (independent recompute of the spec) ----------

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
    for d, ids in cols.items():
        for row, nid in enumerate(sorted(ids)):
            pos[nid] = (80 + d * 170, 70 + row * 90)
    return pos


def expected_canvas(pos: dict[str, tuple[int, int]]) -> tuple[int, int]:
    depths = {(x - 80) // 170 for x, _ in pos.values()}
    col_sizes: dict[int, int] = {}
    for x, _ in pos.values():
        col_sizes[x] = col_sizes.get(x, 0) + 1
    return 160 + max(depths) * 170, 140 + (max(col_sizes.values()) - 1) * 90


# ---------- svg helpers ----------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

def _all(root, name: str) -> list:
    return [el for el in root.iter() if _local(el.tag) == name]

def _classes(el) -> set[str]:
    return set((el.get("class") or "").split())

def _f(el, attr: str) -> float | None:
    v = el.get(attr)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _near(a: float | None, b: float) -> bool:
    return a is not None and abs(a - b) <= TOL

def _text_of(el) -> str:
    return "".join(el.itertext()).strip()


# ---------- checks ----------

def main() -> None:
    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    def fail_rest(from_name: str, detail: str) -> None:
        started = False
        for n in CHECK_NAMES:
            if n == from_name:
                started = True
            if started and n not in {r[0] for r in results}:
                add(n, False, detail)

    journal = json.loads(Path("journal.json").read_text())
    deg = json.loads(Path("deg.json").read_text())
    pos = layout(deg)
    W, H = expected_canvas(pos)
    commits = [e for e in journal["events"] if e["action"] == "commit"]

    def render(out: str) -> tuple[bool, str]:
        try:
            p = subprocess.run([sys.executable, "render_trace.py",
                                "journal.json", "deg.json", out],
                               capture_output=True, text=True, timeout=RENDER_TIMEOUT)
        except subprocess.TimeoutExpired:
            return False, f"timeout after {RENDER_TIMEOUT}s"
        if p.returncode != 0:
            return False, f"exit={p.returncode} stderr: {(p.stderr or '')[-400:]}"
        if not Path(out).is_file():
            return False, "exit 0 but no output file written"
        return True, ""

    if not Path("render_trace.py").is_file():
        add("renders_ok", False, "render_trace.py not found")
        fail_rest("deterministic", "no render_trace.py")
    else:
        ok, why = render(".check_a.svg")
        add("renders_ok", ok, why)
        if not ok:
            fail_rest("deterministic", "render failed")
        else:
            ok2, why2 = render(".check_b.svg")
            same = ok2 and Path(".check_a.svg").read_bytes() == Path(".check_b.svg").read_bytes()
            add("deterministic", same,
                "" if same else (why2 or "two runs produced different bytes"))

    root = None
    if results[0][1]:  # renders_ok
        try:
            root = ET.parse(".check_a.svg").getroot()
        except ET.ParseError as e:
            add("valid_svg_viewbox", False, f"XML parse error: {e}")
            fail_rest("title_present", "unparseable SVG")

    if root is not None:
        vb_ok = False
        detail = ""
        if _local(root.tag) != "svg":
            detail = f"root element is <{_local(root.tag)}>, not <svg>"
        elif "http://www.w3.org/2000/svg" not in root.tag and \
                root.get("xmlns") != "http://www.w3.org/2000/svg":
            detail = "missing xmlns=http://www.w3.org/2000/svg"
        else:
            parts = (root.get("viewBox") or "").split()
            try:
                nums = [float(p) for p in parts]
            except ValueError:
                nums = []
            if len(nums) == 4 and nums[0] == 0 and nums[1] == 0 and \
                    _near(nums[2], W) and _near(nums[3], H):
                vb_ok = True
            else:
                detail = f"viewBox={root.get('viewBox')!r}, expected '0 0 {W} {H}'"
        add("valid_svg_viewbox", vb_ok, detail)

        titles = [_text_of(t) for t in _all(root, "title")]
        t_ok = any(journal["deg_id"] in t and journal["model"] in t for t in titles)
        add("title_present", t_ok,
            "" if t_ok else f"no <title> containing both {journal['deg_id']!r} "
                            f"and {journal['model']!r} (found: {titles!r})")

        styles = [_text_of(s) for s in _all(root, "style")]
        s_ok = any(s for s in styles)
        add("style_present", s_ok, "" if s_ok else "no non-empty <style> element")

        # nodes
        circles = {c.get("data-id"): c for c in _all(root, "circle")}
        missing = sorted(set(pos) - set(circles))
        extra = sorted(set(circles) - set(pos) - {None})
        bad_r = [i for i, c in circles.items() if i in pos and not _near(_f(c, "r"), 18)]
        n_ok = not missing and not extra and None not in circles and not bad_r
        add("nodes_complete", n_ok,
            "" if n_ok else f"missing={missing} extra={extra} "
                            f"no-data-id={None in circles} bad_r={bad_r}")

        bad_pos = [i for i, (x, y) in pos.items()
                   if i in circles and not (_near(_f(circles[i], "cx"), x)
                                            and _near(_f(circles[i], "cy"), y))]
        add("node_positions", n_ok and not bad_pos,
            f"wrong cx/cy: {sorted(bad_pos)[:8]}" if bad_pos
            else ("" if n_ok else "nodes_complete failed"))

        has_out = {e["src"] for e in deg["edges"]}
        want_cls = {}
        for n in deg["nodes"]:
            extra_tok = set()
            if n["id"] == "start":
                extra_tok.add("start")
            if n["terminal"]:
                extra_tok.add("exit")
            if n["id"] not in has_out and not n["terminal"]:
                extra_tok.add("deadend")
            want_cls[n["id"]] = {"node"} | extra_tok
        bad_cls = [i for i in pos if i in circles
                   and _classes(circles[i]) & ({"node", "start", "exit", "deadend"})
                   != want_cls[i]]
        add("node_classes", n_ok and not bad_cls,
            (f"wrong class tokens on {sorted(bad_cls)[:8]} "
             f"(e.g. {sorted(bad_cls)[0]}: got {sorted(_classes(circles[sorted(bad_cls)[0]]))}, "
             f"want {sorted(want_cls[sorted(bad_cls)[0]])})") if bad_cls
            else ("" if n_ok else "nodes_complete failed"))

        # edges
        lines = [(l, _classes(l)) for l in _all(root, "line") if "edge" in _classes(l)]
        unmatched_want = []
        pool = list(lines)
        for e in deg["edges"]:
            (x1, y1), (x2, y2) = pos[e["src"]], pos[e["dst"]]
            want_tok = {"edge"} | ({"gated"} if e["gated"] else set()) \
                                | ({"wrong"} if e["wrong"] else set())
            hit = next((i for i, (l, cl) in enumerate(pool)
                        if _near(_f(l, "x1"), x1) and _near(_f(l, "y1"), y1)
                        and _near(_f(l, "x2"), x2) and _near(_f(l, "y2"), y2)
                        and cl & {"edge", "gated", "wrong"} == want_tok), None)
            if hit is None:
                unmatched_want.append(f"{e['src']}->{e['dst']}")
            else:
                pool.pop(hit)
        e_ok = not unmatched_want and not pool
        add("edges_complete", e_ok,
            "" if e_ok else f"missing/wrong: {unmatched_want[:6]}  "
                            f"unexpected extra edge lines: {len(pool)}")

        # route
        want_pts = [pos["start"]] + [pos[c["node_id"]] for c in commits]
        routes = [p for p in _all(root, "polyline") if "route" in _classes(p)]
        r_ok, r_detail = False, "no <polyline class='route'>"
        if len(routes) == 1:
            try:
                raw = routes[0].get("points", "").replace(",", " ").split()
                got = [(float(raw[i]), float(raw[i + 1])) for i in range(0, len(raw), 2)]
            except (ValueError, IndexError):
                got = None
            if got is None:
                r_detail = "unparseable points attribute"
            elif len(got) != len(want_pts):
                r_detail = f"{len(got)} points, expected {len(want_pts)}"
            elif all(_near(gx, wx) and _near(gy, wy)
                     for (gx, gy), (wx, wy) in zip(got, want_pts)):
                r_ok, r_detail = True, ""
            else:
                bad = next(i for i, ((gx, gy), (wx, wy)) in
                           enumerate(zip(got, want_pts))
                           if not (_near(gx, wx) and _near(gy, wy)))
                r_detail = f"point {bad} is {got[bad]}, expected {want_pts[bad]}"
        elif len(routes) > 1:
            r_detail = f"{len(routes)} route polylines, expected exactly 1"
        add("route_correct", r_ok, r_detail)

        # step labels
        seen: dict[str, int] = {}
        want_steps = []
        for c in commits:
            k = seen.get(c["node_id"], 0)
            seen[c["node_id"]] = k + 1
            x, y = pos[c["node_id"]]
            want_steps.append((str(c["steps_used"]), x, y - 26 - 14 * k))
        texts = [t for t in _all(root, "text") if "step" in _classes(t)]
        by_step = {t.get("data-step"): t for t in texts}
        bad_steps = []
        for s, x, y in want_steps:
            t = by_step.get(s)
            if t is None or not _near(_f(t, "x"), x) or not _near(_f(t, "y"), y) \
                    or _text_of(t) != s:
                bad_steps.append(s)
        st_ok = not bad_steps and len(texts) == len(want_steps)
        add("step_labels", st_ok,
            "" if st_ok else f"bad/missing steps {bad_steps[:8]}; "
                             f"{len(texts)} step texts, expected {len(want_steps)}")

    for name, ok, detail in results:
        print(f"OK {name}" if ok else f"FAIL {name} -- {detail}")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"PASSED {passed}/{len(results)}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
