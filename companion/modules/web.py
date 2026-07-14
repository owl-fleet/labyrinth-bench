"""WebModule — web search and page fetch.

Stub. Future: route to SearXNG for search, httpx for fetch.
"""
from companion.module import CompanionModule, CompanionContext, CompanionResponse


class WebModule(CompanionModule):
    name = "web"
    description = "web search and page retrieval"
    active = False

    def can_handle(self, intent: str, query: str) -> float:
        return 0.0

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        return CompanionResponse(text="[COMPANION]: Web module not yet active.")
