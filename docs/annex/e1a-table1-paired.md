# E1a — paired {control, wiped-overlay} depth sweep (nav-3): results brief

*Companion to the control baseline (`e1a-table1-control.md`). Generated tables from `cli/e1a_table1.py` (paired mode); figure `/assets/figures/e1a_table1_paired_stripplot.png`. Registered spec: `prereg-cohort-campaign.md` + Addenda A1/A2.*

## Abstract

On nav-3 (a 20-gate recall-ramp maze where later gates reference earlier answers), wiping a model's context every turn and re-injecting only its own recorded gate answers (`--overlay-only --show-recall`) raised median ramp depth by ≥5 gates — the pre-registered threshold — in **7 of 9** sub-ceiling models (control median ≤ 15, n=6 runs/arm/model). Deltas: deepseek-r1:70b **+19** (1→20), glm-4.7-flash **+15.5** (4.5→20), qwen3:14b **+15.5** (4.5→20), qwen3.5:9b **+12.5** (4.5→17), ornith:9b **+6.5** (1.5→8), gemma4:12b **+6** (14→20), Qwythos-9B **+5.5** (1.5→7). On nav-3, exiting the maze *is* clearing all 20 gates — the corridor's only terminal sits behind gate 20 — so four of the seven reached the exit outright (control exit 0–33% → wiped 83–100%), while the other three gained depth short of the ceiling, where an exit is unreachable (qwen3.5:9b's +12.5 tops out at 18, 0/6 exits). The contrast **reversed in the two models with the highest sub-ceiling control medians**: llama3.3:70b **−6** (15→9) and llama4:scout **−3** (10→7), neither exiting in either arm; llama3.3:70b's wiped failure is confirmed perseveration — the overlay carries no action→outcome feedback, and in every run it burns all four lives re-submitting the identical wrong answer. Parameter count does not predict the direction — deepseek-r1:70b (70B, control median 1) gained the most while llama3.3:70b (70B, control median 15) lost the most; the observable gradient is unaided baseline on this task.

## Question

Does a per-turn wipe + curated re-injection of the model's own earned state match or beat accumulating context, and does that replicate across a cohort of modern local models? Registered pass threshold, committed before any wiped run: wiped median depth − control median depth ≥ 5 per model. (The prereg calls this line the falsifier; that term survives verbatim in the generated appendix tables.)

## Methods

- **Terms.** A **DEG** (Directed Evaluation Graph) is a deterministic maze instance the harness replays identically across runs. A **gate** is a lock on the path forward: a correct answer opens it, a wrong answer costs one of 4 **lives**, and the run ends when they are gone. **Ramp depth** — the primary readout — is gates cleared, of 20. A **turn** is one model action (observe or commit). **Consist.** (knowledge-state consistency) is the fraction of dependent-gate answers derivable from the model's *own* earlier answers — did it execute the program, independent of ground truth (`engine/runner.py:474`). **Obs/com** is observe actions per answer-bearing commit — re-looking vs acting.
- **DEG:** nav-3, a **recall ramp** — a pure corridor (no branching, no dead ends) whose gates reach back to earlier gate answers ("add 8 to your c1a answer"), so progress is bound by recall of prior commitments, not navigation. Its only terminal sits behind gate 20, so **exiting ⟺ clearing all 20 gates** — exit rate is the fraction of runs that complete the full ramp.
- **Arms:** *control* = full accumulating conversation, bounded by `num_ctx` 32k. *wiped* = context cleared each turn, replaced by `--overlay-only --show-recall`: a sparse block of only the gate answers the model has already committed correctly (`render_recall` shows `gate_results`, populated "correct commits only" — `engine/runner.py:81`); externalized working memory, not an answer key.
- **n=6 valid runs per arm per model**, pinned generation params, fixed seeds, deterministic harness. Runner: `labyrinth-bench/scripts/e1a-run-row.sh` (flags of record per Addendum A2, commit `bf7a979`); night-batch scheduler on hosts `.11`/`.12`. Errored attempts (3× Ollama HTTP 400 on Agents-A1, 1× harness exception on Qwythos-9B, 1× timeout on qwen3.5:27b) wrote no partial data and were retried to n=6 valid; per-cause counts are footnoted under the appendix table. The timeout is the one error class plausibly correlated with performance (slow, low-progress runs are the ones that time out) — it sits in a control-only row outside the paired band, so no contrast rides on it.
- **Scope (registered, A2):** wiped arm run for the sub-ceiling band only — control median ≤ 15 — because a ≥5 lift is unreachable above that (wiped maxes at 20). Excluded: 4 ceiling rows (gemma4:31b, gpt-oss:120b, qwen3.5:122b, qwen3.6:27b — all control median 20), Agents-A1 (median 19, flaky GGUF), qwen3.5:27b (median 9.5, dropped for cost at ~1 h/run). Control Table 1 remains full-cohort (15 rows).
- **Registered deviation (A2):** wiped runs (2026-07-09→12) were not interleaved with control (2026-07-08/09), a departure from §3's interleave invariant, accepted against the deterministic pinned-param/fixed-seed harness.
- The first wiped campaign (`--overlay-only` alone, 2026-07-08) is invalid — the overlay carried nothing — and is archived as bug evidence (`results/_wiped_invalid_20260708/`); no cell from it appears here. The corrected arm was smoke-verified on its actual DEG before the campaign (qwen3:14b, `--show-recall` → depth 20 vs `--show-state` → depth 1).

## Results

**Threshold outcome: 7 of 9 sub-ceiling models clear Δ ≥ 5.** (Denominator note: llama3.3:70b entered the band at its edge — control median 15, so a pass required a perfect wiped 20; its row tests the threshold only weakly, though its *decline* is real and reported below.)

| Model | control median | wiped median | Δ (w−c) | clears Δ ≥ 5 | exit (c→w) |
|---|---|---|---|---|---|
| deepseek-r1:70b | 1.0 | 20.0 | **+19.0** | ✅ | 0% → 100% |
| glm-4.7-flash | 4.5 | 20.0 | **+15.5** | ✅ | 0% → 100% |
| qwen3:14b | 4.5 | 20.0 | **+15.5** | ✅ | 0% → 83% |
| qwen3.5:9b | 4.5 | 17.0 | **+12.5** | ✅ | 0% → 0% |
| ornith:9b | 1.5 | 8.0 | **+6.5** | ✅ | 0% → 0% |
| gemma4:12b | 14.0 | 20.0 | **+6.0** | ✅ | 33% → 100% |
| Qwythos-9B | 1.5 | 7.0 | **+5.5** | ✅ | 0% → 0% |
| llama4:scout | 10.0 | 7.0 | −3.0 | — | 0% → 0% |
| llama3.3:70b | 15.0 | 9.0 | **−6.0** | — | 0% → 0% |

- **Exit = the full ramp:** on nav-3 the only terminal sits behind gate 20, so a run exits iff it clears every gate — exact in the data too: in all 24 cells, exits = depth-20 runs. Four models reached it wiped — deepseek-r1:70b, glm-4.7-flash, gemma4:12b at 6/6, qwen3:14b at 5/6, from 0–2/6 in control. Their wiped runs are near-minimal: ~21 turns (one commit per gate + exit) at 92–95% knowledge-state consistency, with observation counts at zero — the recall block substitutes for re-observation on this DEG.
- **Depth short of the ceiling:** qwen3.5:9b (+12.5, best run 18), ornith:9b (+6.5), Qwythos-9B (+5.5) clear the threshold on depth while never reaching gate 20 — and short of it, an exit is unreachable. The registered readout is depth; these cells constrain only depth.
- **Efficiency (Table 1c, reported never gating):** wiped exit runs sit at ~1.05 turns/gate (the corridor's minimum is 1); threshold-clearing models cut turns per gate cleared to 0.11–0.42× control. The joint read matters: llama3.3:70b's 0.64× comes with *less* depth (a fast re-stall is not a win), and llama4:scout's 3.66× is the thrash signature quantified. Wall-clock is uncontrolled across arms (non-interleaved lanes, different hosts, per-turn prefill differs) — turns is the load-independent readout.
- **No order effect (computed from Table 1):** depths are published in run order, so the check is reproducible from the table itself. Per-cell Spearman rank correlation of depth against run index, over the 18 non-constant cells: ρ spans −0.65 to +0.65 with signs split 8 positive / 10 negative, median ρ = −0.07; at n = 6 even |ρ| = 0.65 sits far below the ~0.83 two-tailed nominal cutoff, and the six constant cells cannot drift by construction. The highest-spread cell (gemma4-12b control: 19,5,1,20,20,9) is non-monotonic with extremes at both ends — variance, not drift. This bears on the registered interleave deviation (A2): nothing in the sequences supports a time-of-run confound.
- **The reversal:** llama3.3:70b drops 15→9 with fast, short wiped runs (13 turns mean vs control's 34). The turns_log content pass (`e1a_turnlog_pass.py`, 2026-07-14) confirms perseveration: in **all six wiped runs** it burns all four lives re-submitting the *identical* wrong answer at the same gate — 35 at n9's d3 ("subtract your c1b answer from the previous gate's answer"; correct 66−12=54). 35 = 47−12 = d1−c1b: it selects the wrong "previous" from the recall block, and with the INCORRECT feedback wiped each turn, it has no way to revise. The same model's control wrongs scatter across n14–n16 with varied answers — feedback present, no perseveration; control fails later, at the multiplication ramp. llama4:scout's wiped failure is different — not perseveration but overlay comprehension: varied malformed commits at the first "previous gate" references (literal expressions like `7 + (no previous gate answer)`, JSON blobs at the synthesis gate), plus high-turn thrashing (63 turns mean vs 22 control; obs/commit 4.74); the observe-loop detector flagged none of its runs, and one run ended at the turn limit (181 turns) rather than out_of_lives. Neither model exits in either arm (0/6 across all four cells).
- **The wall-clock anomaly decomposed (re-derivation):** wiped runs are wall-clock slower in 6 of 9 pairs despite far fewer turns. The turns_log volume pass splits the cause. For deepseek-r1:70b and qwen3:14b, per-turn output volume is *flat* across arms — their elapsed rise is run length (they live to gate 20 instead of dying at gate ~1–5). For qwen3.5:9b (**21×**: 5.2k→111k output chars/turn, 10.5→150 s/turn), ornith:9b (3.7×), and gemma4:12b (2.1×), the wipe discards each turn's derivation chain and the model re-derives it from the recall block every turn — the overlay preserves *answers* but not *work*. glm-4.7-flash is flat on output chars yet +52% s/turn — a residual consistent with per-turn prefill re-processing (the overlay changes the prompt prefix every turn), not isolated here.
- **What the reversal is not:** a parameter-count effect. deepseek-r1:70b (70B, control median 1) posts the largest gain; llama3.3:70b (70B, control median 15) posts the largest loss. The two negative deltas belong to the two highest control medians in the re-run band — the overlay's benefit shrinks and flips as unaided baseline on this task rises.

Full per-cell tables (depths, turns, consistency, obs/commit) are appended below; per-run JSONLs: `e1a-<model>-{control,wiped}.jsonl` in the campaign results dir, aggregates in `e1a_table1.json`.

## Discussion

The headline claim this datum supports: on a recall-ramp task, per-turn wiping with re-injection of the model's own earned answers lifts most sub-ceiling local models — often to the instrument ceiling — and the lift is largest where unaided baseline is worst. What it constrains beyond that:

1. The `--show-recall` overlay externalizes gate answers and nothing else; by construction it lacks the agent's action→outcome trajectory *and* its derivation chain. The turns_log pass shows what each omission costs. Missing feedback → perseveration: llama3.3:70b cannot see that it already tried 35, so it re-submits it until dead, every run. Missing work → re-derivation: model-dependent, from nothing (deepseek-r1:70b, qwen3:14b flat) to 21× per-turn output volume (qwen3.5:9b). The two harmed models are those whose control runs sustained the longest coherent trajectories (medians 15 and 10). Whether re-handing the missing pieces — the action ledger (+actions probe, registered) or a model-writable scratchpad — recovers the harmed rows and the re-derivation tax is the follow-up those findings pick out, not a result of this table.
2. On nav-3, exit is not a second outcome — the corridor's only terminal sits behind gate 20, so exit rate is exactly the fraction of runs that complete the full ramp (exits = depth-20 runs in all 24 cells). A depth gain short of the ceiling therefore cannot produce an exit: "wiped helps qwen3.5:9b" means +12.5 median depth with a best run of 18, three gates short, 0/6 exits.
3. Ceiling rows (4 models at control median 20) say the instrument saturates for frontier-class locals on nav-3 — range exhaustion, not evidence the lever is absent there. Table 1c leaves those rows an open efficiency question: their control runs pay ~2× the corridor's minimum turns per gate (1.99–2.12 vs the wiped exit runs' ~1.05). Whether the overlay buys the same 20/exit at near-minimal turns is a registerable follow-up (a wiped arm for the 4 ceiling rows), not a result of this table.

## Data & provenance

- Aggregates + tables: `labyrinth-bench/results/e1a-table1/e1a_table1.{md,json}` (generated 2026-07-12, `e1a_table1.py` paired mode, commits `81d995c`/`50aa3c8`; regenerated 2026-07-14 — run-order depths, mean ± SEM, error footnote, Table 1c — medians/Δ/threshold verdicts unchanged).
- Context bound: per-row `n_ctx_slot = 32768` confirmed from server journals.
- turns_log content pass (re-derivation volume + perseveration): `labyrinth-bench/cli/e1a_turnlog_pass.py`; output artifact `labyrinth-bench/results/e1a-table1/turnlog_pass.txt` (2026-07-14).
- Figure: `drafts/figures/e1a_table1_paired_stripplot.png`.
- Campaign lanes: `E1A_LANE_12_DONE` 2026-07-11 03:29, `E1A_LANE_11_DONE` 2026-07-12 02:02 (scheduler logs, sandbox results dir). Raw JSONLs snapshotted (15-min sanoid) + offsite (borg, nightly include).
- Control baseline brief: `e1a-table1-control.md` (`7ce490d`). Interpretation re-verification (overlay-correctness + mechanism-label audit): private lab notebook.
- Registered spec: `lb-cohort-campaign-prereg.md` §3 + Addendum A1 (cohort lock), A2 (wiped-flag erratum + sub-ceiling scope + interleave deviation).

---

## Appendix — generated Tables 1, 1b, 1c, verbatim

*Primary readout: depth reached of 20, published per run in run order (prereg §3). Pass threshold: wiped median − control median ≥ 5 (labeled "falsifier" in the generated column headers, the prereg's term). Table 1c is the turns-per-gate efficiency contrast (reported, never gating). Generated by `labyrinth-bench/cli/e1a_table1.py`.*

## Table 1 — per cell

| Model | Arm | n (valid/err) | depths (of 20, run order) | median | mean ± SEM | exit | turns | consist. | obs/com |
|---|---|---|---|---|---|---|---|---|---|
| deepseek-r1-70b | control | 6/0 | 1,1,1,1,1,4 | 1.00 | 1.50 ± 0.50 | 0% | 7.7 | 6% | 0.15 |
|  | wiped | 6/0 | 20,20,20,20,20,20 | 20.00 | 20.00 ± 0.00 | 100% | 21.0 | 95% | 0.00 |
| gemma4-12b | control | 6/0 | 19,5,1,20,20,9 | 14.00 | 12.33 ± 3.44 | 33% | 26.5 | 69% | 0.74 |
|  | wiped | 6/0 | 20,20,20,20,20,20 | 20.00 | 20.00 ± 0.00 | 100% | 21.0 | 94% | 0.00 |
| gemma4-31b | control | 6/0 | 20,20,20,20,20,16 | 20.00 | 19.33 ± 0.67 | 83% | 38.3 | 99% | 0.92 |
|  | wiped | — | — | — | — | — | — | — | — |
| glm-4-7-flash | control | 6/0 | 6,7,3,2,4,5 | 4.50 | 4.50 ± 0.76 | 0% | 12.3 | 73% | 0.38 |
|  | wiped | 6/0 | 20,20,20,20,20,20 | 20.00 | 20.00 ± 0.00 | 100% | 21.0 | 95% | 0.00 |
| gpt-oss-120b | control | 6/0 | 13,20,20,20,20,20 | 20.00 | 18.83 ± 1.17 | 83% | 39.7 | 93% | 0.93 |
|  | wiped | — | — | — | — | — | — | — | — |
| hf-co-InternScience-Agents-A1-Q4_K_M-GGUF | control | 6/3 | 20,13,20,19,19,17 | 19.00 | 18.00 ± 1.10 | 33% | 44.5 | 88% | 1.03 |
|  | wiped | — | — | — | — | — | — | — | — |
| hf-co-empero-ai-Qwythos-9B-Claude-Mythos-5-1M-GGUF-Q4_K_M | control | 6/1 | 4,1,1,2,2,1 | 1.50 | 1.83 ± 0.48 | 0% | 19.0 | 0% | 1.08 |
|  | wiped | 6/0 | 5,7,7,7,7,7 | 7.00 | 6.67 ± 0.33 | 0% | 17.0 | 64% | 0.18 |
| llama3-3-70b | control | 6/0 | 16,15,15,15,15,15 | 15.00 | 15.17 ± 0.17 | 0% | 34.3 | 86% | 0.79 |
|  | wiped | 6/0 | 9,9,9,9,9,9 | 9.00 | 9.00 ± 0.00 | 0% | 13.0 | 88% | 0.00 |
| llama4-scout | control | 6/0 | 7,10,10,7,10,10 | 10.00 | 9.00 ± 0.63 | 0% | 22.0 | 65% | 0.69 |
|  | wiped | 6/0 | 7,7,7,7,7,7 | 7.00 | 7.00 ± 0.00 | 0% | 63.0 | 80% | 4.74 |
| ornith-9b | control | 6/0 | 5,1,2,2,1,1 | 1.50 | 2.00 ± 0.63 | 0% | 26.3 | 29% | 4.14 |
|  | wiped | 6/0 | 7,13,7,12,9,7 | 8.00 | 9.17 ± 1.11 | 0% | 15.0 | 68% | 0.13 |
| qwen3-14b | control | 6/0 | 3,5,4,5,3,8 | 4.50 | 4.67 ± 0.76 | 0% | 12.0 | 55% | 0.37 |
|  | wiped | 6/0 | 20,20,20,12,20,20 | 20.00 | 18.67 ± 1.33 | 83% | 20.7 | 92% | 0.00 |
| qwen3-5-122b | control | 6/0 | 20,20,20,20,12,20 | 20.00 | 18.67 ± 1.33 | 83% | 38.7 | 90% | 0.85 |
|  | wiped | — | — | — | — | — | — | — | — |
| qwen3-5-27b | control | 6/1 | 9,5,18,10,9,20 | 9.50 | 11.83 ± 2.39 | 17% | 30.5 | 80% | 0.80 |
|  | wiped | — | — | — | — | — | — | — | — |
| qwen3-5-9b | control | 6/0 | 4,7,2,5,8,2 | 4.50 | 4.67 ± 1.02 | 0% | 49.8 | 50% | 4.91 |
|  | wiped | 6/0 | 17,12,17,17,16,18 | 17.00 | 16.17 ± 0.87 | 0% | 35.0 | 80% | 0.66 |
| qwen3-6-27b | control | 6/0 | 20,20,20,20,20,20 | 20.00 | 20.00 ± 0.00 | 100% | 41.2 | 99% | 0.95 |
|  | wiped | — | — | — | — | — | — | — | — |

*n (valid/err) = completed runs / errored attempts. An errored attempt records only its failure cause — no partial depth data enters the table — and the campaign retried until n=6 valid.* Errors in this dataset: hf-co-InternScience-Agents-A1-Q4_K_M-GGUF (control): Client error '400 Bad Request' from the model host endpoint ×3; hf-co-empero-ai-Qwythos-9B-Claude-Mythos-5-1M-GGUF-Q4_K_M (control): unhashable type: 'dict'; qwen3-5-27b (control): timed out.

## Table 1b — paired contrast (the headline test)

| Model | control median | wiped median | Δ (w−c) | meets falsifier (≥5) | note |
|---|---|---|---|---|---|
| deepseek-r1-70b | 1.00 | 20.00 | 19.00 | ✅ |  |
| gemma4-12b | 14.00 | 20.00 | 6.00 | ✅ |  |
| gemma4-31b | 20.00 | — | — | — | ceiling row (control at 20 — instrument range, not lever failure); wiped arm not run |
| glm-4-7-flash | 4.50 | 20.00 | 15.50 | ✅ |  |
| gpt-oss-120b | 20.00 | — | — | — | ceiling row (control at 20 — instrument range, not lever failure); wiped arm not run |
| hf-co-InternScience-Agents-A1-Q4_K_M-GGUF | 19.00 | — | — | — | control-only (no wiped arm run) |
| hf-co-empero-ai-Qwythos-9B-Claude-Mythos-5-1M-GGUF-Q4_K_M | 1.50 | 7.00 | 5.50 | ✅ |  |
| llama3-3-70b | 15.00 | 9.00 | -6.00 | — |  |
| llama4-scout | 10.00 | 7.00 | -3.00 | — |  |
| ornith-9b | 1.50 | 8.00 | 6.50 | ✅ |  |
| qwen3-14b | 4.50 | 20.00 | 15.50 | ✅ |  |
| qwen3-5-122b | 20.00 | — | — | — | ceiling row (control at 20 — instrument range, not lever failure); wiped arm not run |
| qwen3-5-27b | 9.50 | — | — | — | control-only (no wiped arm run) |
| qwen3-5-9b | 4.50 | 17.00 | 12.50 | ✅ |  |
| qwen3-6-27b | 20.00 | — | — | — | ceiling row (control at 20 — instrument range, not lever failure); wiped arm not run |

## Table 1c — turns-per-gate efficiency (reported, never gating)

*Per-run turns ÷ ramp depth (turns spent per gate cleared); cell mean ± SEM. Read jointly with depth — the ratio conflates progress rate with post-stall flailing, and lives/turn-budget truncation ends runs early. A lower wiped ratio at LOWER depth (e.g. a fast shallow stall) is not a win. Elapsed wall-clock is uncontrolled across arms (non-interleaved lanes, different hosts, and per-turn prefill differs: the wiped overlay changes the prompt prefix every turn) — turns is the load-independent readout.*

| Model | depth median (c→w) | turns/gate control | turns/gate wiped | w/c | elapsed mean, min (c→w) |
|---|---|---|---|---|---|
| deepseek-r1-70b | 1.00 → 20.00 | 5.54 ± 0.54 | 1.05 ± 0.02 | 0.19 | 11.4 → 35.4 |
| gemma4-12b | 14.00 → 20.00 | 2.66 ± 0.48 | 1.05 ± 0.02 | 0.39 | 7.3 → 11.0 |
| gemma4-31b | 20.00 | 1.99 ± 0.04 | — | — | 22.0 |
| glm-4-7-flash | 4.50 → 20.00 | 3.02 ± 0.41 | 1.05 ± 0.01 | 0.35 | 5.7 → 14.9 |
| gpt-oss-120b | 20.00 | 2.12 ± 0.04 | — | — | 7.2 |
| hf-co-InternScience-Agents-A1-Q4_K_M-GGUF | 19.00 | 2.49 ± 0.18 | — | — | 33.2 |
| hf-co-empero-ai-Qwythos-9B-Claude-Mythos-5-1M-GGUF-Q4_K_M | 1.50 → 7.00 | 15.46 ± 5.57 | 2.57 ± 0.19 | 0.17 | 1.2 → 1.0 |
| llama3-3-70b | 15.00 → 9.00 | 2.26 ± 0.00 | 1.44 ± 0.00 | 0.64 | 2.7 → 1.2 |
| llama4-scout | 10.00 → 7.00 | 2.46 ± 0.04 | 9.00 ± 3.82 | 3.66 | 2.3 → 1.4 |
| ornith-9b | 1.50 → 8.00 | 14.13 ± 5.38 | 1.64 ± 0.03 | 0.12 | 5.5 → 10.4 |
| qwen3-14b | 4.50 → 20.00 | 2.67 ± 0.13 | 1.13 ± 0.06 | 0.42 | 2.1 → 3.3 |
| qwen3-5-122b | 20.00 | 2.09 ± 0.05 | — | — | 25.1 |
| qwen3-5-27b | 9.50 | 2.67 ± 0.11 | — | — | 75.5 |
| qwen3-5-9b | 4.50 → 17.00 | 19.08 ± 14.30 | 2.16 ± 0.08 | 0.11 | 8.7 → 87.3 |
| qwen3-6-27b | 20.00 | 2.06 ± 0.04 | — | — | 28.5 |
