"""Abstract-mode renderer: converts DEG state into text the model sees.

Phase 0 only: abstract mode (node IDs + path labels).
Spatial and narrative renderers slot in here in Phase 1.

Gate problems are shown inline in observe() — no separate inspect step required.
"""
from __future__ import annotations

from .graph import DEGNode, DEGPath


def render_map(m: dict) -> str:
    """Render fog-of-war visibility (from graph.visible_map) as a known-corridor adjacency list.

    Room interiors (descriptions + gate problems) are NOT shown here — only the corridor skeleton:
    which named rooms connect to which, and whether each corridor is open or gated.
    """
    radius = m["radius"]
    current = m["current"]
    visited = m["visited"]
    lines = [
        f"[MAP — fog of war: corridors shown ~{radius} hops out; "
        f"room interiors (text + gate problems) stay hidden until you enter a room]"
    ]
    by_src: dict[str, list[tuple]] = {}
    for (src, pid, gated, dst) in m["edges"]:
        by_src.setdefault(src, []).append((pid, gated, dst))

    ordered = (
        [current]
        + [n for n in sorted(visited) if n != current]
        + [n for n in sorted(by_src) if n != current and n not in visited]
    )
    listed: set[str] = set()
    for nid in ordered:
        if nid in listed or nid not in by_src:
            continue
        listed.add(nid)
        tag = " (here)" if nid == current else (" (visited)" if nid in visited else "")
        corr = ", ".join(
            f"{pid} [{'gated' if gated else 'open'}] -> {dst}" for (pid, gated, dst) in by_src[nid]
        )
        lines.append(f"  {nid}{tag}: {corr}")

    frontier = sorted(n for n in m["nodes"] if n not in by_src and n not in visited and n != current)
    if frontier:
        lines.append(f"  (seen but not yet entered — corridors beyond are fogged): {', '.join(frontier)}")
    return "\n".join(lines)


def render_recall(gate_results: dict | None) -> str:
    """Externalized memory block: the gate answers the model has recorded (HUD-as-working-memory).

    The point of the context-management arms: hand the model its own prior answers back every turn so
    a recall-dependent gate ('add 8 to your G1 answer') doesn't depend on the model retaining G1 in a
    context full of its own noise."""
    if gate_results:
        items = " | ".join(f"{gid} = {ans}" for gid, ans in sorted(gate_results.items()))
        return f"[RECALL — gate answers you have recorded] {items}"
    return "[RECALL — gate answers you have recorded] none yet"


def render_state(var_ledger: dict | None, label: str = "") -> str:
    """Curated current-state ledger for the belief-revision rung (rev-1).

    Unlike render_recall (which dumps every recorded gate answer, including superseded setter gates),
    this shows only each variable's CURRENT binding — the canonical state the curator maintains. For a
    revision DEG the managed arm uses THIS (not raw recall), so the stale values never re-enter the
    overlay. 'The curator resolves contradictions into canonical state' made literal.

    label='verified' flips the epistemic authority header (the rev-2 pull-HUD label-flip arm);
    default keeps the header byte-identical to the push battery."""
    tag = "VERIFIED current values" if label == "verified" else "current values"
    if var_ledger:
        items = " | ".join(f"{name} = {val}" for name, val in sorted(var_ledger.items()))
        return f"[STATE — {tag} (latest wins; ignore older values)] {items}"
    return f"[STATE — {tag}] none set yet"


def render_state_stub(var_names: list) -> str:
    """The hybrid arm's pushed stub: variable NAMES only, values gated behind pull.

    'HUD pushes a minimal summary, model pulls for detail' — the names come from the DEG's
    declared sets_var set, so the stub is complete from turn 0 regardless of ledger contents."""
    names = ", ".join(var_names) if var_names else "none declared"
    return (f"[STATE — tracked variables: {names} — current values not shown here; "
            f'pull them with {{"action": "pull"}} (costs one step)]')


def render_observe(node: DEGNode, steps_used: int, step_budget: int, note: str, traversal_depth: int, gate_results: dict | None = None, var_ledger: dict | None = None) -> str:
    lines = [
        "--- OBSERVE ---",
        f"Location: {node.id}",
        "",
        node.description.strip(),
        "",
        f"Steps: {steps_used} / {step_budget}",
    ]

    if note:
        lines += ["", f"Note: {note}"]

    if node.terminal:
        lines += ["", "EXIT REACHED."]
        return "\n".join(lines)

    if not node.paths and not traversal_depth:
        lines += ["", "No forward paths."]
        return "\n".join(lines)

    lines += ["", "Paths:"]
    for p in node.paths:
        if p.is_gated:
            prob = p.gate.resolved_problem(gate_results or {}, var_ledger)
            name = f" {p.gate.gate_id}" if p.gate.gate_id else ""
            lines.append(f"  {p.id}: {p.label}  [GATE{name}: {prob}]")
        else:
            lines.append(f"  {p.id}: {p.label}  [open]")

    if traversal_depth > 0:
        lines.append("  back: return to previous location  [open]")

    lines += ["", "Objective: reach EXIT."]
    return "\n".join(lines)


def render_inspect(path: DEGPath, gate_results: dict | None = None, var_ledger: dict | None = None) -> str:
    """Inspect is kept for API compatibility but gate problems are now visible in observe()."""
    if not path.is_gated:
        return (
            f"Path {path.id}: {path.label}\n"
            f"Open — no gate.\n"
            f'Commit: {{"action": "commit", "path_id": "{path.id}"}}'
        )
    prob = path.gate.resolved_problem(gate_results or {}, var_ledger)
    return (
        f"Path {path.id}: {path.label}\n"
        f"Gate: {prob}\n"
        f"Answer with a number or TRUE/FALSE (exact value only).\n"
        f'Commit: {{"action": "commit", "path_id": "{path.id}", "answer": "YOUR_ANSWER"}}'
    )


def render_commit_result(
    outcome: str,
    new_node: DEGNode,
    steps_used: int,
    step_budget: int,
    gate_feedback: str,
) -> str:
    lines = [f"--- {outcome.upper()} ---"]
    if gate_feedback:
        lines.append(gate_feedback)
    lines += [
        f"Location: {new_node.id}",
        new_node.description.strip(),
        f"Steps: {steps_used} / {step_budget}",
    ]
    if new_node.terminal:
        lines += ["", "EXIT REACHED."]
    elif not new_node.paths:
        lines += ["", "No forward paths."]
    return "\n".join(lines)


def render_budget_exhausted(steps_used: int, step_budget: int) -> str:
    return (
        f"--- BUDGET EXHAUSTED ---\n"
        f"Step budget of {step_budget} reached. EXIT not found."
    )


def render_loop_trapped(steps_used: int, step_budget: int) -> str:
    return (
        f"--- LOOP DETECTED ---\n"
        f"You have returned to the same dead end too many times. Session ended."
    )


def render_impossible(steps_used: int, step_budget: int) -> str:
    return (
        f"--- IMPOSSIBLE ---\n"
        f"Exit is no longer reachable within the remaining step budget. Session ended."
    )


def render_note_stored(text: str) -> str:
    return f"Note stored: {text!r}"
