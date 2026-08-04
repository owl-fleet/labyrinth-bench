# A3 — ceiling-row efficiency arm (nav-3): results brief

*Companion to the paired brief (`e1a-table1-paired.md`) — the registered follow-up its Discussion §3 picks out. Registered spec: `prereg-cohort-campaign.md` Addendum A3 (registered + signed off 2026-07-14; campaign complete 2026-07-15). Every number traces to `results/e1a-table1/e1a_table1.{md,json}` (Table 1c) and `turnlog_pass.txt`.*

## Abstract

Four models ran nav-3's control arm at the instrument ceiling — a median of 20 of 20 gates: gemma4:31b, gpt-oss:120b, qwen3.5:122b, qwen3.6:27b — so the paired campaign's depth falsifier (a ≥5-gate median gain) was unreachable for them by construction, and Addendum A2 deferred their wiped arms.
A3 registered the question the ceiling leaves open: their control runs paid roughly twice the corridor's minimum turns per gate (1.99–2.12×), while every wiped exit run in the paired band sat near the 1.0 floor. Does the wiped overlay buy the same exits at near-minimal turns where depth has nothing left to give?
The registered falsifier: wiped mean turns/gate ≤ 0.60× control, **with exit rate non-inferior to control** — an exit-rate drop resolves the row against the overlay regardless of turns.
Outcome, n=6 per row: **one met, one near-miss, two against.** qwen3.5:122b met the falsifier — exits 83% → 100%, turns/gate 0.51×, all six wiped runs at 20. gpt-oss:120b held exits (83% → 83%) and improved to 0.65×, missing the 0.60 bar. gemma4:31b collapsed from 83% exits to **0%** (wiped depths 9–14, median 10) and qwen3.6:27b from 100% to **17%** (median 14) — both resolve against the overlay outright.
The turn-log pass gives the mechanism: both failures are perseveration — same gate, same wrong answer, lives out at the recall-reference gates (gemma4:31b in 4 of 6 wiped runs, and once in its own control; qwen3.6:27b in 3 of 6) — while per-turn output volume stayed flat in all four rows. Feedback-loss, not work-loss.
The four rows entered with identical control medians and split 2–2, so the overlay's direction at the ceiling is model-specific, not baseline-graded — a correction to the paired table's gradient reading, which the ceiling band cannot see by construction.

## Design (registered)

- **Arm:** wiped = `--overlay-only --show-recall` (A2's corrected flags of record, unchanged), n=6, the four ceiling rows only; same hosts, ollama pin (0.31.1), shipped default generation parameters, and journal-verified effective context as A2.
- **Falsifier (efficiency, this addendum only):** per model, wiped mean turns/gate ≤ 0.60× control mean turns/gate, with wiped exits ≥ control exits (of 6). Exit remains the only objective; efficiency is a readout here, never a substitute.
- **Not a readout:** wall-clock. Elapsed is uncontrolled across arms (non-interleaved lanes, host assignment, per-turn prefill — the overlay changes the prompt prefix every turn, defeating KV-cache reuse). Turns is the load-independent quantity.
- **Deviation carried from A2:** wiped runs are not interleaved with control (control ran 2026-07-08/09; A3 ran 07-14/15). Same acceptance rationale: deterministic harness, pinned params, verified context.
- **Smoke adjudication (2026-07-14, decided by Will):** the pre-campaign smoke cell (gpt-oss:120b, W0) verified the arm mechanically — 16 gates climbed from overlay-only context — but missed the depth-20/exit prediction: two lives burned early at n9, the recall-mapping gate (recovered, not perseveration), then arithmetic deaths on the late multiplication ramp; the shared lives budget converts an early overlay tax into a late death. The campaign proceeded on the registered ground that exit non-inferiority already scores this direction as a resolving outcome, and n=1 discriminates nothing. W0 counts (resume-aware).

## Results

| Row | exit (c→w) | turns/gate (w/c) | wiped depths | Verdict |
|---|---|---|---|---|
| qwen3.5:122b | 83% → 100% | **0.51×** | 20,20,20,20,20,20 | **falsifier MET** — same-or-better exits at half the turns per gate |
| gpt-oss:120b | 83% → 83% | 0.65× | 16,20,20,20,20,20 | exit non-inferior; efficiency improved, misses ≤0.60 |
| gemma4:31b | 83% → **0%** | (0.70×) | 9–14, median 10 | **against the overlay** — exit collapse |
| qwen3.6:27b | 100% → **17%** | (0.65×) | median 14 | **against the overlay** — exit collapse |

Parenthesized ratios follow Table 1c's joint-read rule: a lower turns/gate at lower depth is a fast stall, not a win.

## Mechanism (turn-log pass)

Both failing rows die by perseveration at recall-reference gates: the wiped overlay re-hands the model its earned answers but carries no record of what already *failed*, and the model re-submits the identical wrong answer until its lives run out — gemma4:31b in 4 of 6 wiped runs (and 1 of 6 in its own control), qwen3.6:27b in 3 of 6.
Per-turn output volume stays flat across all four rows — none re-derives its chain from the notes the way qwen3.5:9b does in the paired band.
The failure class at ceiling is therefore feedback-loss, not work-loss: the same mechanism as llama3.3:70b's paired-band reversal, appearing in models whose unaided depth is perfect.

## What this constrains

1. **At the ceiling, the overlay's direction is model-specific, not baseline-graded.** Four rows with identical control medians (20) split two-for, two-against: identical baselines, opposite directions, so baseline cannot determine the overlay's direction in this band. The paired table's observable gradient — reversal risk rises with unaided baseline — cannot be evaluated where baseline has no variance; the split is what A3 adds.
2. **The efficiency win exists where the overlay holds.** qwen3.5:122b's 0.51× at 6/6 exits is the registered efficiency claim, met in full; gpt-oss:120b's 0.65× at unchanged exits bounds it. Neither licenses any claim about rows where exits collapsed.
3. **Feedback-loss is the recurring failure of the answers-only overlay.** Perseveration now accounts for the wiped failures in both bands (llama3.3:70b; gemma4:31b, qwen3.6:27b). Whether re-handing the missing piece — the action→outcome ledger (the registered +actions probe) — recovers these rows is the follow-up this result picks out, not a result of this table.

## Sources

- Aggregates + per-run depths: `results/e1a-table1/e1a_table1.{md,json}` (Table 1c, regenerated 2026-07-15 with the A3 rows).
- Mechanism: `results/e1a-table1/turnlog_pass.txt` (`cli/e1a_turnlog_pass.py`).
- Registered design + falsifier + smoke adjudication: `prereg-cohort-campaign.md` Addendum A3 (registered 2026-07-14, lock visible).
- Raw per-run JSONL: the annex raw-data bundle (`/data`, `wiped/` folder — the four ceiling files).
