from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompanionContext:
    session_state: dict
    deg: object          # engine.graph.DEG — avoid circular import at module level
    gate_index: dict     # gate_id → Gate
    visited_descriptions: dict  # node_id → description text
    history: list[dict]  # companion Q&A pairs this session: [{"q": ..., "a": ...}]
    session_id: str
    traversal_log: list[dict] = field(default_factory=list)
    db_conn: Any | None = field(default=None)   # psycopg2 connection


@dataclass
class CompanionResponse:
    text: str
    content_type: str = "text"
    data: bytes | None = None
    metadata: dict = field(default_factory=dict)


class CompanionModule:
    """Base class for all companion capability modules.

    active = True  → shown in capability briefing (module is implemented)
    active = False → stub; registered but excluded from briefing
    """
    name: str = "base"
    description: str = ""
    active: bool = False

    def can_handle(self, intent: str, query: str) -> float:
        """Return confidence 0.0–1.0. Highest-confidence module wins dispatch."""
        return 0.0

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        return CompanionResponse(text="[COMPANION]: I don't have a capability that covers that.")
