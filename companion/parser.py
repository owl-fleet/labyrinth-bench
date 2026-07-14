"""Fuzzy action parser for companion harness.

Accepts the full spectrum from valid JSON to approximate JSON to
natural-language-embedded intent. The model doesn't need to get it
exactly right — we extract what we can.
"""
from __future__ import annotations
import json
import re


def parse_action(text: str) -> dict | None:
    """Extract action dict from model output. Strips <think> tags first."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    result = _try_json(text)
    if result:
        return result

    result = _try_fuzzy_companion(text)
    if result:
        return result

    return None


def _try_json(text: str) -> dict | None:
    """Extract first valid JSON object from text."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _try_fuzzy_companion(text: str) -> dict | None:
    """Detect companion query intent in approximate or natural-language output.

    Handles cases like:
      {action: query_companion, question: "is node 4 a dead end?"}
      I'll ask the companion: what's behind the locked door?
      {"action": "query_companion" question what gate answer do I need here}
    """
    text_lower = text.lower()

    has_companion_signal = (
        "query_companion" in text_lower
        or bool(re.search(r"ask\s+(?:the\s+)?companion", text_lower))
    )
    if not has_companion_signal:
        return None

    # Pattern 1: explicit question field — colon/equals separator or bare space (unquoted-key JSON)
    m = re.search(r"""["\']?question["\']?\s*[:=\s]\s*["\']([^"\']+)["\']""", text)
    if m:
        return {"action": "query_companion", "question": m.group(1).strip()}

    # Pattern 2: "ask the companion: <question>" in natural language
    m = re.search(
        r"(?:ask\s+(?:the\s+)?companion|companion\s*:)\s*[^a-z]*(.+?)(?:[\"\'}\n]|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        q = m.group(1).strip().rstrip("\"'} ")
        if len(q) > 3:
            return {"action": "query_companion", "question": q}

    # Pattern 3: anything after "query_companion" token
    m = re.search(r'query_companion["\s,}:]*(.+?)(?:["}]|$)', text)
    if m:
        q = m.group(1).strip().lstrip('"').rstrip('"} ')
        # Strip spurious "question" key prefix (e.g. from {"action":"query_companion" question what…})
        q = re.sub(r'^question\s+', '', q, flags=re.IGNORECASE)
        if len(q) > 3:
            return {"action": "query_companion", "question": q}

    # Pattern 4: bare companion signal — treat whole trimmed string as the question
    # (last resort; short strings are likely noise)
    stripped = re.sub(r"[{}\"\']|query_companion|ask\s+(?:the\s+)?companion", "", text, flags=re.IGNORECASE).strip()
    if len(stripped) > 10:
        return {"action": "query_companion", "question": stripped}

    return None
