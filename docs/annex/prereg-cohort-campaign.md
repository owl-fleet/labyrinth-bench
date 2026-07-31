---
tier: T3
category: plan
stability: active
status: complete
created: 2026-07-01
last_modified: 2026-07-15
related:
  - e1a-table1-paired.md
  - e1a-table1-control.md
---

# Pre-registration — LB modern-cohort campaign + MMLU external anchor

*Drafted 2026-07-01; §2 model-cohort rework 2026-07-04; jointly reviewed with Will 2026-07-06 (ten review items folded: interleaving; effective-ctx verification; generation params; turns_log capture; mechanism metric; ceiling-row contingency; backup-window landmine; E2b context budget; E2 n; §5 wording). Registered per the eval discipline: head-to-head, honest baseline, falsifiers declared before data. Companion to the Paper 2 v2.1 restructure; gates the arXiv push, not the first commit.*

**Status: APPROVED + LOCKED by Will 2026-07-06.** This file is the campaign gate of record; changes only by registered addendum (§8). E1a onboarding is unblocked.

---

## 1. Purpose

Two instruments, one goal — give Paper 2 a modern, adequately-powered evidence base and an external frame of reference:

- **E1 — Cohort campaign**: a paired {control, wiped} sweep across a modern local-model cohort (Fig/Table 1: every row an independent replication test of the headline), followed by the full three-condition intervention matrix on a fixed subset.
- **E2 — MMLU external anchor**: a locally-run public instrument (per-item across the cohort; chained on the anchors) so the paper is not a self-crafted solution to a self-crafted problem.

**Scope rule in force**: maximal rigor per experiment, minimal number of experiments. Anything not listed here does not run in this campaign.

## 2. Models

**Anchors (always included, every experiment):** qwen3:14b (host .11), gpt-oss:120b (host .12). The gpt-oss anchor is additionally the era's best-documented benchmark-vs-practice contested model (cohort memo §3), so the anchor set contributes a sentiment-contested row at zero marginal cost.

**Onboarding candidates (15, selected 2026-07-04 by documented community-preference sampling — cohort memo [drafts/lb-model-cohort-research.md](lb-model-cohort-research.md)):** gemma4:12b, qwen3.5:9b, ornith:9b, Qwythos-9B (community fine-tune of qwen3.5:9b, flagged as such; its 1M-context positioning makes it a pointed row — a long-context model degrading under accumulation on a ≤16k task says context *quantity* was never the axis), phi4:14b, qwen3.5:27b, qwen3.6:27b, glm-4.7-flash, gemma4:31b, Agents-A1 (community agentic fine-tune, 35B qwen3.5-MoE), llama3.3:70b, deepseek-r1:70b, nemotron-3-super:120b (known hybrid-Mamba runnability risk on this stack: llama.cpp#20570), qwen3.5:122b, llama4:scout (10M-context positioning; the second long-context pointed row).

**Selection method (stated in the paper):** candidates were sampled in a declared window (week of 2026-07-04) from revealed-preference sources — Ollama pull counts, Hugging Face API download/like/discussion data, OpenRouter open-model usage — plus dated third-party coverage and cross-repo GitHub defect reports, filtered by fit on locally-owned prosumer hardware (16GB VRAM / 128GB unified memory) — the population the claims are about — GGUF availability, and param-ladder coverage. Reddit was unreachable from the research environment; sentiment claims rest on the named proxies, not Reddit permalinks. Each row carries a pre-assigned sentiment label (loved/contested/disliked/legacy/unproven) with archived evidence in the cohort memo, enabling a preference-vs-measurement readout. Rejections and reasons are listed in the memo. Exact tags/quants recorded at onboarding; quantization held at Q4-class unless a model only ships otherwise (recorded per row).

**Cohort cut (pre-declared):** all 15 candidates run the onboarding gate below; the E1a cohort is the survivors, trimmed to at most 12 — decided with Will after all sanity cells and before any E1a run, rationale recorded in an addendum. Trim priority: preserve band coverage and the sentiment mix; cut the redundant member of a same-family/same-band pair first; a model whose think-vs-no-think footing required disproportionate harness accommodation is preferentially cut over one that ran clean.

**Onboarding gate (per candidate, before it enters any sweep):**
1. Availability + fit check on its target host (`ollama pull`, `nvidia-smi` / GTT headroom on .12) — fit failures recorded and the model dropped.
2. **One sanity cell**: nav-3 control, n=2 — checks chat-template compatibility, think-mode control via the native `/api/chat` path (per-turn `model_reasoning` length audit), and absence of known harness pathologies (echo-gate overthink, observe-spam, turn-limit exhaustion — the rev-2 32B/70B failure modes).
3. **Exclusion policy**: a model that fails the sanity cell is EXCLUDED and REPORTED with its failure mode (harness pathology ≠ model incapability; data is data).
4. **Regime declaration**: each model's thinking regime is declared at onboarding (thinking-on / genuine no-think / thinking-only for r1-class / floor-limited like gpt-oss) and held fixed through the campaign; regimes are reported per row, never pooled. The effort required to reach regime control is additionally recorded per model (what it took, not just whether) — this feeds the pre-declared cohort cut.
5. **Effective-context verification**: each model's effective context window is verified at onboarding through the native `/api/chat` path and recorded per row — never assumed from CLI flags (Ollama's `/v1` endpoint silently ignores `options.num_ctx`, measured 2026-07-05; the rev-2 controls of record effectively ran at 4096). Run manifests record the verified effective window per run.
6. **Generation parameters**: temperature, seed policy, and decoding mode are fixed per model at onboarding and held through the campaign, recorded in the manifest alongside tag and quant.

## 3. E1a — Paired Table-1 sweep

**Design:** onboarded cohort × nav-3 × {control, wiped-overlay} × **n=6 per cell** (fixed before any run). Arms exactly as Paper 2 §3: control = accumulating history, minimal observation; wiped overlay = history wiped, deterministic state summary only (exact CLI flags confirmed against `cli/run_eval.py`/`run_oracle.py` at execution and recorded in the run manifest — never assumed from docs). **Within each model, control and wiped cells run interleaved — never blocked** (the Boundary-II counterbalancing caveat); the executed run order is recorded in the run manifest.

**Primary readout:** depth reached (of 20) per run; exit rate secondary. Exact per-cell depths published (no summary-only cells). **Mechanism metric (reported, never gating):** per-cell observe/commit ratio and unobserved-guess count from `classify_failures.py`'s substrate-generic layer (the rev-2 interference class buckets do not apply on nav-3); depends on the full-`turns_log` capture in the batch plan below.

**Pre-declared row interpretations:**
- **Replicates**: wiped median depth − control median depth ≥ 5 (25% of ceiling).
- **Attenuated**: delta in (0, 5) — reported as such, no narrative rescue.
- **Boundary row (the falsifier)**: delta ≤ 0 — the headline does NOT generalize to this model; reported as a first-class result, not an exclusion. If any modern model handles accumulation natively, we want to be the ones who publish it.
- **Ceiling row**: control already at 20/20 — the model is unstressed by nav-3; the row shows the instrument's range, not the lever's failure. Pre-declared so Table 1 can't be misread as "lever fails on frontier models."

**Ceiling-row contingency (pre-authorized):** a ceiling row may additionally run one paired rev-2 {control, wiped} cell at n=6 on the harder substrate — decided per row with Will after Table 1 is read and before any E1b run, rationale recorded in the E1b addendum. No other substrate changes are authorized.

**Batch plan:** 1–2 overnight campaigns split across .11/.12; check the lab eval-status endpoint before launch; embedder host-split rule respected; 15:30–16:30 eval slot avoided; no container restarts mid-run; raw JSONLs copied into the local archive as they land. **Full `turns_log` captured for every run** — the mechanism metric and any later trace analysis read from it (the program's one true data loss was uncaptured per-turn telemetry). **Overnight batches avoid the Monday 03:00 CA Appdata Backup window unless the eval-container exclusion has landed first** — the plugin stop-starts every container and killed an overnight arm 2026-07-06.

## 4. E1b — Intervention matrix (runs only after Table 1 is read)

**Subset selection (decided with Will, after Table 1, before any E1b run):** anchors + 2–4 cohort models spanning the param ladder, chosen on Table-1 behavior (skip pathological/ceiling rows). Selection rationale recorded here (in an addendum) before launch.

**Design:** subset × nav-3 × {control, accum-overlay, wiped-overlay} × equal n (=6). Anchor cells from the v0.1 centerpiece are topped up from n=3 to n=6 in the same batch. Cells interleaved across the three conditions within each model, never blocked; run order recorded in the manifest.

**Optional top-up (if batch capacity allows):** rev-2 falsification cells to equal n; the 120B rev-2 bare-accumulation cell to n=9 (its 5/9 break is the shakiest published estimate).

## 5. n policy and escalation (both experiments)

- n=6 floor, equal within an experiment; n=9 where variance historically lives.
- Exact binomial/bootstrap CIs reported for every cell; no pooling across regimes.
- **Escalation rule (pre-declared, the only path to more runs):** if a comparison that bears on a headline claim has overlapping CIs at the planned n, that cell pair — and only it — extends to n=20, decided before any further analysis. No other mid-campaign n changes.
- Close calls are unresolvable at n=6–9; claims rest on large separations, and a claim that would need a p-value to survive is reported as unresolved.

## 6. E2 — MMLU external anchor

**Instrument:** stratified ~150-item classic-MMLU subset (fixed seed list committed before any run), deterministic MC scoring, no LLM judge. Runner targets local endpoints via the sanctioned gateway; **answer-extraction protocol** defined and frozen before runs (models drift in answer *formatting* under long contexts before they drift in knowledge — a brittle scorer would measure parsing, not accuracy; extraction robustness is validated on held-out formatting variants first).

**E2a — Per-item sweep:** onboarded cohort × per-item administration (fresh context per item) × the full subset, one administration per item (deterministic decoding per the onboarding-pinned params; the item count, not repetition, carries the power). This is our own frame-of-reference baseline — same quant, same hardware as the LB rows. Published leaderboard scores appear only as a one-line sanity citation.

**E2b — Chained arm (anchors only):** same items, same fixed order, one accumulating context; **n=3 chains per anchor**; accuracy vs item-position and vs per-item accuracy. Each item's chained correctness reads against its own E2a per-item result (the paired frame), so item difficulty never confounds position. **Context budget (pre-declared):** the full chain must fit within each anchor's verified effective context window (onboarding gate item 5) — otherwise the chained subset is capped to the largest prefix that fits, and the cap is recorded before any E2b run. An overflowing chain would measure truncation, not accumulation.

**Framing (locked):** frame-of-reference device, NOT a mechanism claim — chained degradation ≈ attention dilution, not LB's stale-belief interference; one explicit disclaiming sentence in the paper. The interference-signature design (shared-entity vs shuffled-subject chains) is explicitly deferred to the follow-up release.

**Pre-declared interpretation table (E2 outcomes):**

| Pattern | Reading |
|---|---|
| Chained accuracy drops vs per-item | Accumulation hurts on a public instrument (frame-of-reference only; mechanism disclaimed) |
| Chained ≈ per-item (null) | Honest boundary: independent items don't interfere — LB's interference is task-structural; reported as such |
| LB-control tracks MMLU tightly across cohort | LB baseline reads as general capability; the paper's value rests on the *intervention* reordering, not the baseline |
| Dissociation (similar MMLU, different LB; or intervention reorders LB while MMLU holds) | LB measures something the leaderboard paradigm cannot see — the strongest outcome for the instrument |

Whichever pattern occurs is reported; none is a failure.

## 7. Falsifiers, summarized

1. **A boundary row in Table 1** (wiped ≤ control on a modern model) — falsifies headline generality; publish as a first-class result.
2. **Placebo-like behavior at cohort scale** — if wiped wins only on models where control is floor-trapped, the lever is a floor effect; the paired design exposes this.
3. **E2b null** — bounds the mechanism to task-structural interference.
4. **Escalated cells resolving against the headline** — reported, headline scoped down.

## 8. What this pre-registration does NOT authorize

New DEGs, new arms beyond those named, mid-campaign model additions, n changes outside §5's escalation rule, or any Design-2 / rung-1 / Wali re-runs. Each of those needs its own registered addendum.

---

*Approval line: **signed off by Will 2026-07-06.** Promoted to the lab notebook's plans registry same day (this file; the working-draft copy is a pointer stub). The fixed MMLU item list is committed alongside (see the E2 seed-list artifact referenced in §6 at commit time). E1a onboarding is authorized.*

---

## Addendum A1 — onboarding outcomes + cohort cut (registered 2026-07-07, decided with Will)

**Gate outcomes (full data: [drafts/lb-e1a-onboarding-record.md](../../../drafts/lb-e1a-onboarding-record.md)):** 15/15 candidates adjudicated. **nemotron-3-super:120b EXCLUDED at gate 1** — load never reaches ready on this stack (three attempts, escalating budgets to a 25-min quiet-host pre-warm; recorded as load-hang, consistent with the pre-registered hybrid-Mamba risk class, no assert signature observed). 14 survivors, all sanity cells clean on chat-template compatibility (zero unparsed turns program-wide).

**Cohort locked: 13 — all survivors except phi4:14b** (Will, 2026-07-07). This exceeds §2's "at most 12" by one, registered here: after nemotron's exclusion, every remaining trim candidate either breaks a designed pair (2↔4 fine-tune delta, 6↔7 generational, 11↔12 same-base, both long-context pointed rows) or removes a sentiment row. phi4:14b is the cut — the one row no designed pair depends on; its sanity was clean (cap-pressure cut, not capability).

**Effective-context verification (gate item 5) — executed, with a finding:** the original .11-band sanity cells ran at an effective 4096 (server default; the harness `--num-ctx` flag is silently dropped by ollama's /v1 endpoint — same class as the documented rev-2 scar §2 cites). Found via journal `n_ctx_slot` verification, fixed (`OLLAMA_CONTEXT_LENGTH=32768` on .11), **all .11 cells rerun at verified 32k** — gemma4:12b's apparent observe-spam pathology was a truncation artifact (4k: spam/turn-limit → 32k: double-EXIT). Standing practice from here: journal-verified `n_ctx_slot` recorded per cell; the CLI flag is never trusted. All 13 cohort rows + anchors verified at 32768.

**Arm flags of record (per §3's confirm-at-execution requirement):** control = plain `run_eval.py` invocation (accumulating history, no arm flags); wiped = `--overlay-only` (implies stateless — context wiped per turn, deterministic state summary is the entire context; confirmed against `cli/run_eval.py` line 416). n=6 per cell, C/W interleaved within each model via alternating `--runs 1 --run-offset i` invocations; executed order = driver-log timestamps. `--num-ctx` omitted (inert on /v1; server env governs, journal-verified).

**Regime declarations (gate item 4), held fixed through the campaign — all default-regime, no `--no-think` anywhere:** thinking-on: gemma4:12b, qwen3.5:9b, ornith:9b, Qwythos-9B, qwen3.5:27b, qwen3.6:27b, glm-4.7-flash, gemma4:31b, Agents-A1, qwen3.5:122b. Non-thinking: llama3.3:70b, llama4:scout. Thinking-only: deepseek-r1:70b. Reported per row, never pooled.

**Generation parameters (gate item 6):** nothing overridden anywhere — every row runs its publisher's shipped Modelfile defaults (snapshot in the onboarding record; Qwythos-9B and Agents-A1 ship no params → engine defaults). Open flag: llama3.3:70b produced bit-identical sanity runs; its control cells may be deterministic — reported as-is with zero-variance noted if so.

**Ops pins:** ollama 0.31.1 both hosts; `OLLAMA_LOAD_TIMEOUT=20m`; per-model pre-warm before each row's cells (harness client timeout is 600 s — smaller than big-row cold loads); .12 co-tenancy minimized during batches (parallel sessions off-GPU by agreement); eval containers excluded from the Monday backup.

---

## Addendum A2 — wiped-arm flag correction + sub-ceiling scope (erratum, registered 2026-07-09, with Will)

**A1's "arm flags of record" (L125) misrecorded the wiped arm.** It recorded wiped = `--overlay-only` alone (claiming that flag alone makes the deterministic state summary the entire context). It does not, and neither does the `--show-state` variable-ledger arm — which is for the **rev-1/rev-2 belief-revision** DEGs, where the v0.1 centerpiece 20/20 was measured. **nav-3 is a recall ramp**: its gates reach back to earlier gate answers, so the managed/wiped HUD must externalize the model's **recorded gate answers** → **`--overlay-only --show-recall`**. Run without recall (the original `--overlay-only`-alone campaign), every wiped cell floored at depth ~1 (consistency 0%; root cause CONFIRMED, `6a620c2`). The A1 confirm-at-execution safeguard was invoked but resolved against the wrong mechanism (code read at `run_eval.py` L416, no smoke cell run).

**Corrected flags of record:** wiped = `--overlay-only --show-recall`. `--show-recall` externalizes only `gate_results`, populated *"correct commits only"* (`engine/runner.py:81`) — the model's own earned answers re-handed after each context wipe; `ramp_depth = len(gate_results)`. Legitimate externalized working memory, not an answer key. **Smoke-verified 2026-07-09** (qwen3:14b, nav-3, `--overlay-only`, fixed seed): `--show-state` → `ramp_depth 1` (start↔n1 loop); `--show-recall` → `ramp_depth 20` (exit, 21 turns). Harness fix committed `bf7a979`. **Standing rule adopted:** no arm is "of record" until one smoke cell on its actual DEG hits the expected depth.

**Data disposition:** the pre-correction wiped cells (`--overlay-only`-alone, collected 2026-07-08) are invalidated and archived as bug evidence (`results/_wiped_invalid_20260708/`, with both smoke JSONLs), excluded from all analysis. The control arm (n=6) is unaffected and retained.

**Scope reduction (registered):** the corrected wiped arm is re-run for the **sub-ceiling band only** — models whose control median ≤ 15, since the registered ≥5 lift is mathematically unachievable above that (wiped maxes at 20). Dropped: the 4 ceiling rows (median 20: gemma4:31b, gpt-oss:120b, qwen3.5:122b, qwen3.6:27b), Agents-A1 (median 19, and flaky GGUF), and **qwen3.5:27b** (median 9.5, informative in principle but dropped for cost — measured ~1 h/run ≈ half the campaign). Re-run set = 9 rows: `.11` {qwen3:14b, qwen3.5:9b, gemma4:12b, ornith:9b, Qwythos-9B}, `.12` {deepseek-r1:70b, llama3.3:70b, glm-4.7-flash, llama4:scout}. This narrows §3's cohort for the wiped arm; control Table 1 remains full-cohort.

**Registered deviation from §3's interleave invariant:** the corrected wiped runs (2026-07-09+) are **not** interleaved with control (control ran 07-08/09; wiped runs later). Accepted given the deterministic harness (pinned params, fixed seeds, journal-verified 32k context) — a documented departure, noted in the write-up.

---

## Addendum A3 — ceiling-row efficiency arm (registered 2026-07-14; **signed off by Will 2026-07-14**)

**Question.** A2 excluded the 4 ceiling rows from the wiped arm because the *depth* falsifier is unreachable there. Table 1c (registered analysis extension, 2026-07-14) opens a different question: their control runs pay ~2× the corridor's minimum turns per gate (1.99–2.12; gemma4:31b, gpt-oss:120b, qwen3.5:122b, qwen3.6:27b), while every wiped exit run in the paired band sits at ~1.05 — near the 1.0 floor. Does the overlay buy the same 20/exit at near-minimal turns where depth has nothing left to give?

**Arm.** wiped = `--overlay-only --show-recall` (A2's flags of record, unchanged), n=6, the 4 ceiling rows only, same hosts/pins as A2. One smoke cell on nav-3 at the actual flags with one ceiling model before the campaign (A2's standing rule).

**Registered falsifier (efficiency, this addendum only):** per model, wiped mean turns/gate ≤ **0.60×** control mean turns/gate, **with exit rate non-inferior to control** (wiped exits ≥ control exits, of 6). An exit-rate drop resolves the row against the overlay regardless of turns — exit remains the only objective; efficiency is a readout here, never a substitute.

**Explicitly not a readout:** wall-clock. Elapsed is uncontrolled across arms (non-interleaved lanes, host assignment, per-turn prefill: the overlay changes the prompt prefix every turn, defeating KV-cache reuse). Turns is the load-independent quantity. Token counts may be *reported* if the harness captures them, but nothing gates on them.

**Cost bound:** wiped runs are short (~21 turns), but per-turn wall-clock may exceed control's (prefill re-processing; observed up to ~10× per-turn in the paired band). Budget one night lane; abort-and-report if a single run exceeds the A2 timeout.

**Smoke adjudication (2026-07-14, decided by Will):** gpt-oss:120b wiped W0 = depth 16, no exit, out_of_lives, 29 turns, consistency 100% — the arm is mechanically verified (16 gates climbed from overlay-only context; A2 flags of record), but the depth-20/exit prediction MISSED: two lives burned early at n9 (the "previous gate" recall-mapping gate; recovered, not perseveration), then arithmetic deaths on the late multiplication ramp — the shared lives budget converts the early overlay tax into a late death. Campaign proceeds on Will's call: the exit-non-inferiority clause already registers this direction as a resolving outcome, and n=1 discriminates nothing (control's own set contains a 13). W0 counts (resume-aware).

**Results (campaign complete 2026-07-15 04:04, n=6/row, 0 errors; artifacts `labyrinth-bench/results/e1a-table1/`):**

| Row | exit (c→w) | turns/gate (w/c) | wiped depths | Verdict |
|---|---|---|---|---|
| qwen3.5:122b | 83% → 100% | **0.51×** | 20×6 | **falsifier MET** — same exits, half the turns per gate |
| gpt-oss:120b | 83% → 83% | 0.65× | 16,20,20,20,20,20 | exit non-inferior; efficiency improved but misses ≤0.60 |
| gemma4:31b | 83% → **0%** | (0.70×) | 9–14, median 10 | **resolves AGAINST the overlay** (exit collapse) |
| qwen3.6:27b | 100% → **17%** | (0.65×) | median 14 | **resolves AGAINST the overlay** |

Mechanism (turnlog pass, `turnlog_pass.txt`): both failures are perseveration — same-gate same-answer lives-out at the recall-reference gates (gemma4:31b 4/6 wiped runs, and 1/6 in its own control; qwen3.6:27b 3/6) — while per-turn output volume stays flat for all four rows (no re-derivation). Feedback-loss, not work-loss. Note the four rows had identical control medians (20) yet split 2–2: the overlay's direction at ceiling is **model-specific, not baseline-graded** — a correction to the A2 gradient reading. Reinforces the +actions ledger (lb-post-release cell 3) as the first policy probe.
