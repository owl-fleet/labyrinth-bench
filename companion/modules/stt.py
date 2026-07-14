"""STTModule — speech to text transcription.

Stub. Future: accept audio bytes, return transcript via Whisper.
"""
from companion.module import CompanionModule, CompanionContext, CompanionResponse


class STTModule(CompanionModule):
    name = "speech-to-text"
    description = "transcribe audio to text"
    active = False

    def can_handle(self, intent: str, query: str) -> float:
        return 0.0

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        return CompanionResponse(text="[COMPANION]: STT module not yet active.")
