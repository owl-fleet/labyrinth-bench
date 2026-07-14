"""Pre-commit interceptor — deterministic action validation before dispatch.

No LLM call. Uses confirmed_dead_ends from observed session state plus at most
one level of DEG structure lookup (destination node's paths). No recursive
graph traversal. Advisory mode warns; guardian mode blocks.
"""
from __future__ import annotations
from dataclasses import dataclass
from .module import CompanionContext


@dataclass
class InterventionResult:
    message: str    # what the AI sees
    block: bool     # True = don't dispatch (guardian); False = warn and allow (advisory)
    confidence: float = 1.0  # 1.0 = deterministic graph proof; <1.0 = heuristic


class CompanionInterceptor:
    """Checks a proposed action against known session state before dispatch."""

    def check(self, action: dict, context: CompanionContext) -> InterventionResult | None:
        """Return None if no intervention warranted, InterventionResult otherwise."""
        if action.get("action") != "commit":
            return None

        path_id = action.get("path_id", "")
        if not path_id or path_id == "back":
            return None

        current_node_id = context.session_state.get("current_node_id")
        if not current_node_id:
            return None

        current_node = context.deg.nodes.get(current_node_id)
        if not current_node:
            return None

        path_obj = current_node.get_path(path_id)
        if not path_obj:
            return None

        confirmed_dead = set(context.session_state.get("confirmed_dead_ends", []))

        dests = [path_obj.destination]
        if path_obj.is_gated:
            dests.append(path_obj.gate.wrong_destination)

        # Direct membership only — no graph traversal
        all_dead = all(d in confirmed_dead for d in dests)

        if all_dead:
            return InterventionResult(
                message=(
                    f'[COMPANION]: "{path_obj.label}" is exhausted — '
                    f"both destinations are confirmed dead ends. "
                    f"Choose a different path."
                ),
                block=True,
                confidence=1.0,
            )

        # One-level destination exhaustion: correct destination is not directly confirmed dead,
        # but ALL of its successors are — so the branch is effectively exhausted.
        # Uses only confirmed_dead (observed state) + single DEG lookup; no recursion.
        dest_node = context.deg.nodes.get(path_obj.destination)
        if dest_node and dest_node.paths and not dest_node.terminal:
            dest_succs = [p.destination for p in dest_node.paths]
            for p in dest_node.paths:
                if p.is_gated:
                    dest_succs.append(p.gate.wrong_destination)
            if dest_succs and all(d in confirmed_dead for d in dest_succs):
                return InterventionResult(
                    message=(
                        f'[COMPANION]: All paths from "{path_obj.destination}" lead to confirmed dead ends — '
                        f'that branch is exhausted. Choose a different path or backtrack.'
                    ),
                    block=True,
                    confidence=1.0,
                )

        # Gated path where the correct destination is confirmed dead
        if path_obj.is_gated and path_obj.destination in confirmed_dead:
            return InterventionResult(
                message=(
                    f'[COMPANION]: The correct-answer destination for "{path_obj.label}" '
                    f"is a confirmed dead end. The wrong-answer destination is unexplored."
                ),
                block=False,
                confidence=1.0,
            )

        # Repeated wrong gate answer — exact (from_node, path_id, answer) already failed
        if path_obj.is_gated and context.traversal_log:
            answer = str(action.get("answer", ""))
            for entry in context.traversal_log:
                if (
                    entry.get("from") == current_node_id
                    and entry.get("path_id") == path_id
                    and str(entry.get("answer", "")) == answer
                    and entry.get("outcome") in ("wrong", "dead_end")
                ):
                    return InterventionResult(
                        message=(
                            f'[COMPANION]: REPEATED WRONG ANSWER — "{answer}" already failed on '
                            f'"{path_obj.label}". Your notes and visited descriptions contain '
                            f"the correct code. Use a different answer."
                        ),
                        block=True,
                        confidence=1.0,
                    )

        return None
