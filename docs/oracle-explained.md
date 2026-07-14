# Oracle Mode — The Aimbot That Still Fails

## Yes, it's an aimbot

Oracle mode provides maximum navigational assistance. Before every turn, the model receives:

- Its current location and steps remaining
- Every path available, with dead branches labeled `[ALL OUTCOMES DEAD — skip]`
- Every gate answer it has computed so far
- A full turn-by-turn log of every commit, dead end, and backtrack
- The description text of every node it has already visited — so if a code appeared in a room description 8 turns ago, it's right there in the state block now

This is not subtle assistance. The system is actively pointing the model away from confirmed dead ends on every turn. That's the point.

---

## What the aimbot measures

Oracle mode collapses the evaluation into a single question: **at maximum information density, what's left?**

Two failure modes exist in a maze eval:

1. **Information failure** — the model can't navigate because it doesn't remember where it's been, what gates it passed, what codes it saw
2. **Execution failure** — the model can't navigate because it can't translate available information into a coherent plan and follow it

Standard eval conflates these. A model that fails under standard conditions might be failing for either reason, or both. Oracle mode eliminates failure mode 1 entirely. What remains is failure mode 2.

---

## The finding

| Model | Standard exits | Oracle exits | Oracle GA | Oracle failure mode |
|-------|---------------|-------------|-----------|---------------------|
| gpt-oss:120b | 1/3 | 6/6 | 1.00 | — |
| qwen3:32b | 0/1 | 3/3 | 1.00 | — |
| phi4-reasoning:14b | 0/4 | 2/3 | 1.00 | budget_exhausted (1) |
| **qwen3:14b** | **0/6** | **0/6** | **1.00** | **loop_trapped (all)** |

qwen3:14b under oracle: 100% gate accuracy. Full state block every turn. Dead ends labeled explicitly. It commits to the same confirmed dead end anyway — twice — which triggers the loop trap.

The aimbot does not help it. The bottleneck is not information.

---

## What the split tells you

The comparison between phi4-reasoning:14b and qwen3:14b under oracle is the core finding.

Same parameter count. Same information environment. Oracle GA = 1.00 for both. phi4-reasoning exits at optimal efficiency. qwen3:14b loop-traps on every run.

This is not a scale effect. Both are 14B models. The difference is execution capacity — the ability to maintain a navigation strategy across turns, integrate a structured state block into action selection, and not drift back into confirmed-dead branches.

The oracle removes the memory excuse. What's left is the model itself.

---

## The implications for information environments

The oracle experiment was originally motivated by a thesis: **models fail because of information availability, not intelligence.** The experiment partially confirms that — and partially refutes it.

The confirmation: phi4-reasoning:14b exits under oracle and never exits without it. Turn the lights on; the model navigates. That's the thesis working.

The partial refutation: qwen3:14b has the same lights and cannot navigate. Information availability is necessary but not sufficient. Some failure is information failure. Some is execution failure. Oracle mode tells you which is which.

This is more useful than a clean confirmation. A benchmark that only shows "better information = better outcomes" isn't a benchmark — it's a demonstration. The oracle reveals that the relationship is model-dependent, which is the interesting result.
