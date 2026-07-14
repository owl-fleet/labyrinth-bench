"""SessionStateModule — answers questions about catalogued session observations.

The companion has NO map knowledge. It only knows what has been observed:
  - Confirmed dead nodes (outcomes recorded by the session API)
  - Gate solutions (answers that were accepted this session)
  - Node descriptions (text the navigator literally saw)
  - The navigator's saved note

It cannot predict whether an unexplored path leads somewhere useful.
It cannot compute distances or shortest paths.
It reports facts. The navigator reasons.
"""
from __future__ import annotations
from companion.module import CompanionModule, CompanionContext, CompanionResponse

_DEAD_KW  = {"dead", "exhausted", "safe", "visited", "been", "explored", "stuck", "confirmed"}
_GATE_KW  = {"gate", "answer", "code", "solution", "combination", "password", "key", "unlock"}
_DESC_KW  = {"description", "describe", "see", "saw", "text", "what was", "looked like", "identifier", "tag", "identifier"}
_NOTES_KW = {"note", "notes", "noted", "recorded", "saved", "written", "remember", "reminder"}

_ALL_KW = _DEAD_KW | _GATE_KW | _DESC_KW | _NOTES_KW

_REDIRECT = (
    "[COMPANION]: I can answer specific questions about: "
    "confirmed dead end nodes, gate answers from this session, "
    "visited node descriptions, or your saved note. Ask me something specific."
)


class SessionStateModule(CompanionModule):
    name = "session state"
    description = "confirmed dead ends, gate answers, visited node descriptions, saved note"
    active = True

    def can_handle(self, intent: str, query: str) -> float:
        combined = (intent + " " + query).lower()
        if any(kw in combined for kw in _ALL_KW):
            return 0.9
        return 0.0  # don't handle vague/open queries

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        q = query.lower()
        confirmed_dead = set(context.session_state.get("confirmed_dead_ends", []))
        answers: list[str] = []

        # Notes — most specific, check first
        if any(kw in q for kw in _NOTES_KW):
            ans = self._answer_notes(context)
            if ans:
                answers.append(ans)

        # Confirmed dead ends (observed outcomes only)
        if any(kw in q for kw in _DEAD_KW):
            ans = self._answer_dead(query, context, confirmed_dead)
            if ans:
                answers.append(ans)

        # Gate answers
        if any(kw in q for kw in _GATE_KW):
            ans = self._answer_gates(query, context, confirmed_dead)
            if ans:
                answers.append(ans)

        # Node descriptions
        if any(kw in q for kw in _DESC_KW):
            ans = self._answer_desc(query, context)
            if ans:
                answers.append(ans)

        if answers:
            return CompanionResponse(text="[COMPANION]: " + "\n".join(answers))

        return CompanionResponse(text=_REDIRECT)

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _answer_notes(self, context: CompanionContext) -> str | None:
        note = context.session_state.get("note", "").strip()
        if note:
            return f"Your saved note: {note}"
        return "No note saved yet this session."

    # ── Confirmed dead ends ───────────────────────────────────────────────────

    def _answer_dead(self, query: str, context: CompanionContext, confirmed_dead: set) -> str | None:
        # Check if a specific node is mentioned
        node_id = _extract_node_id(query, context.deg)
        if node_id:
            if node_id in confirmed_dead:
                return f"Node {node_id}: confirmed dead end (visited and exhausted this session)."
            return f"Node {node_id}: not in confirmed dead list — unexplored paths may remain."

        # Check if a specific path is mentioned (check its direct destination only)
        path_id = _extract_path_id(query, context)
        if path_id:
            current = context.session_state.get("current_node_id")
            node = context.deg.nodes.get(current) if current else None
            path_obj = node.get_path(path_id) if node else None
            if path_obj:
                dest_dead = path_obj.destination in confirmed_dead
                wrong_dead = (
                    path_obj.is_gated and path_obj.gate.wrong_destination in confirmed_dead
                )
                if dest_dead and wrong_dead:
                    return f'Path "{path_obj.label}": both direct destinations are confirmed dead ends.'
                if dest_dead:
                    return f'Path "{path_obj.label}": correct-answer destination is a confirmed dead end.'
                if wrong_dead:
                    return f'Path "{path_obj.label}": wrong-answer destination is a confirmed dead end. Correct destination unexplored.'
                return f'Path "{path_obj.label}": neither direct destination is a confirmed dead end.'

        # Return the full confirmed dead list
        if confirmed_dead:
            return "Confirmed dead end nodes this session: " + ", ".join(sorted(confirmed_dead))
        return "No confirmed dead ends recorded yet this session."

    # ── Gate answers ──────────────────────────────────────────────────────────

    def _answer_gates(self, query: str, context: CompanionContext, confirmed_dead: set) -> str | None:
        gate_results = context.session_state.get("gate_results", {})

        gate_id = _extract_gate_id(query, context.gate_index)
        if gate_id and gate_id in gate_results:
            gate = context.gate_index.get(gate_id)
            prob = gate.resolved_problem(gate_results) if gate else gate_id
            return f'Gate "{gate_id}": {gate_results[gate_id]}  (problem: {prob})'

        node_id = _extract_node_id(query, context.deg)
        if node_id:
            node = context.deg.nodes.get(node_id)
            if node:
                found = []
                for path in node.paths:
                    if path.is_gated and path.gate.gate_id:
                        gid = path.gate.gate_id
                        if gid in gate_results:
                            found.append(f'  path "{path.label}" ({gid}): {gate_results[gid]}')
                if found:
                    return "Gate answers for paths from " + node_id + ":\n" + "\n".join(found)

        # No direct gate answer — surface visited descriptions as context since
        # gate inputs are often codes or identifiers seen in prior node descriptions
        if gate_results:
            lines = ["Solved gates this session:"]
            for gid, ans in sorted(gate_results.items()):
                gate = context.gate_index.get(gid)
                prob = gate.resolved_problem(gate_results) if gate else gid
                lines.append(f"  {gid}: {ans}  (problem: {prob})")
            result = "\n".join(lines)
        else:
            result = "No gates have been solved in this session yet."

        if context.visited_descriptions:
            desc_lines = ["Visited node descriptions (may contain relevant codes or identifiers):"]
            for nid, desc in sorted(context.visited_descriptions.items()):
                desc_lines.append(f"  [{nid}] {desc.strip()}")
            result += "\n" + "\n".join(desc_lines)

        return result

    # ── Node descriptions ─────────────────────────────────────────────────────

    def _answer_desc(self, query: str, context: CompanionContext) -> str | None:
        node_id = _extract_node_id(query, context.deg)
        if node_id:
            if node_id in context.visited_descriptions:
                return f"Description at {node_id}: {context.visited_descriptions[node_id].strip()}"
            return f"No stored description for {node_id} — not yet visited or no description recorded."

        if context.visited_descriptions:
            lines = ["Descriptions at visited nodes:"]
            for nid, desc in sorted(context.visited_descriptions.items()):
                lines.append(f"  [{nid}] {desc.strip()}")
            return "\n".join(lines)

        return "No visited node descriptions recorded yet."


# ── Extraction helpers ─────────────────────────────────────────────────────────

def _extract_node_id(query: str, deg) -> str | None:
    for node_id in deg.nodes:
        if node_id.lower() in query.lower():
            return node_id
    return None


def _extract_gate_id(query: str, gate_index: dict) -> str | None:
    for gid in gate_index:
        if gid.lower() in query.lower():
            return gid
    return None


def _extract_path_id(query: str, context: CompanionContext) -> str | None:
    current = context.session_state.get("current_node_id")
    if not current:
        return None
    node = context.deg.nodes.get(current)
    if not node:
        return None
    for path in node.paths:
        if path.id.lower() in query.lower() or path.label.lower() in query.lower():
            return path.id
    return None
