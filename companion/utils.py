from __future__ import annotations
from engine.graph import DEG


def is_dead_branch(
    node_id: str,
    deg: DEG,
    confirmed_dead: set[str],
    _seen: frozenset = frozenset(),
) -> bool:
    """True if every forward path from node_id leads only to confirmed dead ends."""
    if node_id in confirmed_dead:
        return True
    if node_id in _seen:
        return True  # cycle — treat as exhausted
    node = deg.nodes.get(node_id)
    if not node or not node.paths:
        return node_id in confirmed_dead
    _seen = _seen | {node_id}
    for path in node.paths:
        dests = [path.destination]
        if path.is_gated:
            dests.append(path.gate.wrong_destination)
        if not all(is_dead_branch(d, deg, confirmed_dead, _seen) for d in dests):
            return False
    return True
