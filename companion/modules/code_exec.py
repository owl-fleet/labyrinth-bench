"""CodeExecModule — execute code and return stdout/stderr.

Stub. Future: sandbox execution via toolbox container.
"""
from companion.module import CompanionModule, CompanionContext, CompanionResponse


class CodeExecModule(CompanionModule):
    name = "code execution"
    description = "run code snippets and return output"
    active = False

    def can_handle(self, intent: str, query: str) -> float:
        return 0.0

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        return CompanionResponse(text="[COMPANION]: Code execution module not yet active.")
