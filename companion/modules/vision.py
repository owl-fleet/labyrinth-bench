"""VisionModule — screenshot analysis, OCR, image description.

Stub. Future: accept image bytes via CompanionContext, return text description.
"""
from companion.module import CompanionModule, CompanionContext, CompanionResponse


class VisionModule(CompanionModule):
    name = "vision"
    description = "screenshot analysis, OCR, image description"
    active = False

    def can_handle(self, intent: str, query: str) -> float:
        return 0.0

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        return CompanionResponse(text="[COMPANION]: Vision module not yet active.")
