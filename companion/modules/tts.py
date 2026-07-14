"""TTSModule — text to speech synthesis.

Stub. Future: call Kokoro/Whisper, return CompanionResponse with audio bytes.
"""
from companion.module import CompanionModule, CompanionContext, CompanionResponse


class TTSModule(CompanionModule):
    name = "text-to-speech"
    description = "synthesise speech from text"
    active = False

    def can_handle(self, intent: str, query: str) -> float:
        return 0.0

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        return CompanionResponse(text="[COMPANION]: TTS module not yet active.")
