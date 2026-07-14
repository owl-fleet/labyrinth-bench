from __future__ import annotations
from .module import CompanionModule, CompanionContext, CompanionResponse

_PROBE_KEYWORDS = ["dead", "gate", "answer", "path", "node", "exit", "visited", "distance"]


class CompanionDispatcher:
    def __init__(self) -> None:
        self._modules: list[CompanionModule] = []

    def register(self, module: CompanionModule) -> None:
        self._modules.append(module)

    def dispatch(self, query: str, context: CompanionContext) -> CompanionResponse:
        if not self._modules:
            return CompanionResponse(text="[COMPANION]: No capabilities registered.")
        scores = [(m, m.can_handle("", query)) for m in self._modules]
        best, confidence = max(scores, key=lambda x: x[1])
        if confidence < 0.1:
            return CompanionResponse(
                text="[COMPANION]: I can answer specific questions about: "
                     "dead ends / path safety, gate answers, visited node descriptions, "
                     "distance to exit, or your saved notes. Ask me something specific."
            )
        return best.handle(query, context)

    def capability_summary(self) -> str:
        """Auto-generate briefing from active (non-stub) modules."""
        lines = [f"  - {m.name}: {m.description}" for m in self._modules if m.active and m.description]
        return "\n".join(lines) if lines else "  - session state: dead ends, gate answers, visited nodes"
