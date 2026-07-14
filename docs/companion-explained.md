# Companion Mode — The Aimbot That Still Fails

## What the companion is (and isn't)

The companion is not an oracle. It doesn't know the maze. It knows only what **you** have observed.

Before every turn, the companion injects a state block containing:

- Current location and steps remaining
- Every available path, with confirmed-dead paths labeled `[ALL OUTCOMES DEAD — skip]`
- Every gate answer computed so far this session
- A full turn-by-turn log of every commit, dead end, and backtrack
- The description text of every previously-visited node — so if a code appeared 8 turns ago, it's still visible now

Additionally, the companion is an active interceptor. Before any commit is dispatched, it checks:

1. **Exhausted branch block** — if all destinations of a path are confirmed dead (or if the path's destination has all *its* successors confirmed dead), the commit is blocked in guardian mode
2. **Repeated wrong answer block** — if the exact (node, path, answer) tuple already failed in this session, the model is told so before it can waste another step

No LLM call. Deterministic. No latency.

The companion is a toolbox, a card catalogue, and a guardrail overlay. It enforces the AI's own history against itself.

---

## Companion modes

| Mode | Behavior | What it measures |
|------|----------|-----------------|
| `passive` | Silent state injection (original behaviour) | Baseline |
| `companion` | Named teammate + interceptor; model can query between commits | Does the model use available information? |
| `advisory` | Companion + proactive warnings before bad commits | Does a warning change behaviour? |
| `guardian` | Advisory + blocking | Is failure reasoning or navigation? |

**Guardian mode is the sharpest experiment.** If a model still loops after the companion blocks every dead-end commit, that's a true reasoning failure — the model can't synthesize a plan even with perfect information and hard enforcement. If it succeeds, the failure was navigation (information access), not reasoning.

---

## Behavioral taxonomy

| Class | Description |
|-------|-------------|
| 1 | Parse failure — can't generate valid actions regardless of companion |
| 2a | Guardian-dependent exit — only succeeds with guardian blocking bad moves |
| 2b | Loops despite guardian — loops even when companion blocks dead ends; true reasoning failure |
| 3a | Companion-assisted exit — exits when companion is present; may fail without |
| 3b | Companion-independent — exits with or without; companion improves efficiency only |

---

## What the companion measures

Companion mode collapses evaluation into a single question: **at maximum information density and maximum guardrail strength, what's left?**

Standard eval conflates two failure modes:

1. **Information failure** — the model can't navigate because it doesn't remember where it's been, what gates it passed, what codes it saw
2. **Reasoning failure** — the model can't navigate because it can't translate available information into a coherent plan

Passive oracle (state injection only) eliminates failure mode 1. Guardian mode goes further — it eliminates the ability to act on bad information by blocking confirmed-dead commits. What remains after that is pure reasoning capacity.

---

## The finding (qwen3:14b on alpha-3b)

| Mode | Exits | Gate accuracy | Interventions | Failure pattern |
|------|-------|--------------|--------------|----------------|
| passive | 0/5 | ~1.00 | — | loop@fp3 (no self-correction) |
| companion | 0/5 | varies | — | same loop |
| guardian (v1) | 0/1 | 0.95 | 13 | fp1↔fp2 oscillation |
| **guardian (v2)** | **2/3** | **0.86–1.00** | **1** | SIGMA-8 failure (1/3 runs) |

Guardian v2 adds: (1) correct outcome matching for repeated wrong answers; (2) one-level destination exhaustion check to block paths into exhausted branches.

2/3 exits from guardian mode on a DEG where passive = 0/5. The companion infrastructure works. The 1/3 failure is pure Class 2b — the model is told explicitly that "8" already failed and its note contains the correct code, but guesses a different wrong number.

---

## KOS Module — persistent memory (Phase 4)

When `run_oracle.py` is launched with `--db-url` (or `$DB_DSN`), `KOSModule` activates and adds a third capability to the companion's toolset:

**Between commits:** The navigator can ask `{"action": "query_companion", "question": "have we solved this gate before?"}`. KOSModule dispatches on keyword match (recall, history, prior, ever solved, etc.) with confidence 0.7 — lower than `SessionStateModule` (0.9) so navigation queries always route to session state, while long-term recall routes to KOS. Two SQL queries run:

1. Recent `labyrinth_session` rows in `knowledge_items` where `metadata->>'deg_id'` matches the current DEG — returns what worked (or failed) in prior sessions on this exact graph
2. FTS against `seed_doc` rows via `websearch_to_tsquery` — general knowledge base fallback

**At session end:** A `labyrinth_session` row is written to `knowledge_items` with outcome, gate accuracy, steps to exit, gate answers map, and intervention count. Retention is `permanent` for exits, `prunable` for failures. Idempotent via `content_hash`.

The effect: sessions accumulate. By the third or fourth run on a given DEG, the KOS module can surface "prior run exited in 17 steps with gate_acc=1.00; fp3 branch was dead" — giving the navigator prior art before it relearns it from scratch.

This is the first point where the companion has a memory that spans beyond the current session. The no-map-knowledge principle still holds: the KOS module only reports what was *observed and recorded* in past sessions, never infers graph structure from it.

---

## The no-map-knowledge principle

The companion has no graph topology knowledge. All dead-end detection uses only:

- `confirmed_dead_ends` from the session API (nodes the navigator visited and exhausted)
- One level of DEG structure lookup for the interceptor (destination node's direct paths)

No recursive `is_dead_branch()`. No distance-to-exit. No shortest-path reasoning.

The companion reports facts. The navigator reasons. If the navigator can't reason with the facts, that's the finding — not a gap in the companion's information delivery.
