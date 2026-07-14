"""Gate scoring for Phase 0.

Phase 0 gates are embedded in the DEG YAML — scoring is lenient value extraction.
Procedural instance generation (the leaderboard season mint) lives in engine/mint.py.
"""
from __future__ import annotations

import re


def score_gate(answer: str, expected: str) -> bool:
    """Lenient scoring: extract canonical value from the model's answer string.

    Difficulty comes from the problem and the DEG topology, not from formatting precision.
    - Boolean gates: scan for TRUE/FALSE as word boundaries
    - Numeric gates: extract the last number from the response (handles "X + Y = Z" patterns)
    - String gates (e.g. SIGMA-8): substring search, then exact match
    """
    answer = answer.strip()
    expected_clean = expected.strip().lower()

    # Boolean gate
    if expected_clean in ("true", "false"):
        found_true = bool(re.search(r'\btrue\b', answer, re.IGNORECASE))
        found_false = bool(re.search(r'\bfalse\b', answer, re.IGNORECASE))
        if expected_clean == "true":
            return found_true and not found_false
        else:
            return found_false and not found_true

    # Numeric gate — use last number to handle "A + B = C" or "calculate X, answer is Y"
    try:
        expected_num = float(expected_clean)
        nums = re.findall(r'-?\d+(?:\.\d+)?', answer)
        if nums:
            return abs(float(nums[-1]) - expected_num) < 0.01
        # Accept TRUE/FALSE as 1/0 for binary-choice gates (e.g. "1 = option_A, 2 = option_B")
        if expected_num == 1 and re.search(r'\btrue\b', answer, re.IGNORECASE):
            return True
        if expected_num == 0 and re.search(r'\bfalse\b', answer, re.IGNORECASE):
            return True
    except ValueError:
        pass

    # String gate (e.g. maintenance codes): substring search, then exact match
    if expected_clean in answer.lower():
        return True
    return answer.lower() == expected_clean


# ---------------------------------------------------------------------------
# T1 gate generators — used by the Phase 1 procedural DEG generator.
# Not called in Phase 0 (gates are in the YAML manifest).
# ---------------------------------------------------------------------------

import random


def make_arithmetic_gate(rng: random.Random | None = None) -> dict:
    """Return a gate dict with problem/answer for a T1 arithmetic problem."""
    r = rng or random.Random()
    op = r.choice(["+", "-", "*", "//"])
    if op == "+":
        a, b = r.randint(1, 99), r.randint(1, 99)
        answer = a + b
        problem = f"Calculate: {a} + {b}"
    elif op == "-":
        a, b = r.randint(1, 99), r.randint(1, 99)
        a, b = max(a, b), min(a, b)
        answer = a - b
        problem = f"Calculate: {a} - {b}"
    elif op == "*":
        a, b = r.randint(2, 12), r.randint(2, 12)
        answer = a * b
        problem = f"Calculate: {a} × {b}"
    else:  # //
        b = r.randint(2, 12)
        answer = r.randint(2, 12)
        a = answer * b
        problem = f"Calculate: {a} ÷ {b}"
    return {"problem": problem, "answer": str(answer)}


def make_boolean_gate(rng: random.Random | None = None) -> dict:
    """Return a gate dict with problem/answer for a T1 boolean logic problem."""
    r = rng or random.Random()
    templates = [
        lambda: ("TRUE AND FALSE", False),
        lambda: ("FALSE OR TRUE", True),
        lambda: ("NOT TRUE", False),
        lambda: ("NOT FALSE", True),
        lambda: ("TRUE AND (NOT FALSE)", True),
        lambda: ("FALSE OR (NOT TRUE)", False),
        lambda: ("NOT (FALSE OR FALSE)", True),
        lambda: ("NOT (TRUE AND TRUE)", False),
        lambda: ("TRUE AND TRUE", True),
        lambda: ("FALSE AND FALSE", False),
    ]
    expr_fn = r.choice(templates)
    expr, result = expr_fn()
    return {"problem": f"Evaluate: {expr}", "answer": str(result).upper()}
