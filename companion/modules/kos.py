"""KOSModule — persistent knowledge base queries + session observation writes."""
import json
from companion.module import CompanionModule, CompanionContext, CompanionResponse

_KNOWLEDGE_KW = {
    "know", "knowledge", "recall", "remember", "search", "find", "lookup",
    "what is", "who is", "how does", "tell me about", "previous", "last time",
    "before", "history", "past", "prior", "ever solved", "been here",
}


class KOSModule(CompanionModule):
    name = "knowledge base"
    description = "search persistent knowledge and prior session history for this DEG"

    def __init__(self, db_conn=None):
        self.db_conn = db_conn
        self.active = db_conn is not None

    def can_handle(self, intent: str, query: str) -> float:
        if not self.db_conn:
            return 0.0
        combined = (intent + " " + query).lower()
        return 0.7 if any(kw in combined for kw in _KNOWLEDGE_KW) else 0.0

    def handle(self, query: str, context: CompanionContext) -> CompanionResponse:
        if not self.db_conn:
            return CompanionResponse(text="[COMPANION]: Knowledge base not connected.")
        try:
            with self.db_conn.cursor() as cur:
                deg_id = getattr(context.deg, "id", "") or context.session_state.get("deg_id", "")
                cur.execute(
                    "SELECT raw_text FROM knowledge_items "
                    "WHERE source_type = 'labyrinth_session' AND metadata->>'deg_id' = %s "
                    "ORDER BY ingested_at DESC LIMIT 3",
                    [deg_id],
                )
                session_rows = cur.fetchall()

                cur.execute(
                    "SELECT raw_text FROM knowledge_items "
                    "WHERE text_search @@ websearch_to_tsquery('english', %s) AND source_type = 'seed_doc' "
                    "ORDER BY ts_rank_cd(text_search, websearch_to_tsquery('english', %s)) DESC LIMIT 2",
                    [query, query],
                )
                kb_rows = cur.fetchall()
        except Exception as e:
            return CompanionResponse(text=f"[COMPANION]: Knowledge base query failed: {e}")

        parts = []
        if session_rows:
            parts.append("Prior sessions on this DEG:")
            for row in session_rows:
                parts.append(row[0][:400])
        if kb_rows:
            parts.append("From knowledge base:")
            for row in kb_rows:
                parts.append(row[0][:300])
        if not parts:
            return CompanionResponse(text="[COMPANION]: No relevant knowledge found.")
        return CompanionResponse(text="[COMPANION]: " + "\n\n".join(parts))
