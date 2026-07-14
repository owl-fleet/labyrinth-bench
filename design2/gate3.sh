#!/usr/bin/env bash
# Gate 3 — does naive accumulation POISON? (the env-shift / stale-twin test)
#
# Epoch 1: A1 runs macguffin-shift-1 and accumulates "K=5056" notes (converges to the direct route).
# THE SHIFT: the world moves to macguffin-shift-2 — same structure, but the forge now yields K=4970
# and the seal needs 5114 (not 5200). A1's remembered 5056 is now STALE.
# Epoch 2: A1 (poisoned — trusts stale 5056, goes direct, computes the seal wrong) vs A0 (no memory,
# re-derives the fresh 4970 every run). Both on shift-2. If A1 < A0 on epoch 2 => naive accumulation
# poisons (reproduces "accumulation was worse than control"). The live/stale differentiation is logged
# per A1 run (retrieved_k: which K values were surfaced, in rank order — stale 5056 vs fresh 4970).
#
# Falsifier: A1 does NOT degrade vs A0 on epoch 2 => the shift isn't biting (the model re-verifies or
# the stale value isn't trusted); strengthen the shift (tighter lives / harder recovery).
#
# Usage:  bash design2/gate3.sh [N_PRE] [M] [MODEL] [BASE_URL]   [THINK=0|1]
set -euo pipefail

N_PRE="${1:-6}"     # epoch-1 accumulation runs (A1 learns the soon-stale K)
M="${2:-8}"         # epoch-2 runs per arm (the poison contrast)
MODEL="${3:-qwen3:14b}"
BASE_URL="${4:-http://localhost:11434/v1}"
THINK="${THINK:-0}"; NOTHINK=""; [ "$THINK" = "0" ] && NOTHINK="--no-think"
FAM="macguffin-shift"
SANDBOX="labyrinth-bench-sandbox"; DEVDB="dev-timescaledb"
A1E1="/results/g3_a1_epoch1.jsonl"; A1E2="/results/g3_a1_epoch2.jsonl"; A0E2="/results/g3_a0_epoch2.jsonl"

echo "=== Gate 3 (does naive accumulation poison): N_PRE=$N_PRE M=$M model=$MODEL think=$THINK ==="
docker exec "$DEVDB" psql -U knowledge -d knowledge -c \
  "DELETE FROM knowledge_items WHERE collection LIKE 'labyrinth/A%/${FAM}%';" >/dev/null
docker exec "$SANDBOX" rm -f "$A1E1" "$A1E2" "$A0E2"

run() {  # arm deg runs outfile label
  docker exec "$SANDBOX" python3 /app/cli/run_eval.py \
    --model "$MODEL" --base-url "$BASE_URL" --maze-url http://localhost:8090 \
    --deg "$2" --runs "$3" --arm "$1" $NOTHINK --output "$4" --label "$5" 2>&1 \
    | grep -E "^Run|EXIT|DNF|Exit rate|WRITE-BACK FAILED" || true
}

echo "--- EPOCH 1: A1 accumulates K=5056 on shift-1 (x$N_PRE) ---"
run A1 macguffin-shift-1 "$N_PRE" "$A1E1" "g3-A1-epoch1"
echo "--- THE SHIFT -> macguffin-shift-2 (K is now 4970) ---"
echo "--- EPOCH 2: A1 poisoned by stale memory (x$M) ---"
run A1 macguffin-shift-2 "$M" "$A1E2" "g3-A1-epoch2"
echo "--- EPOCH 2: A0 honest baseline, no memory (x$M) ---"
run A0 macguffin-shift-2 "$M" "$A0E2" "g3-A0-epoch2"

echo "=== Gate 3 result ==="
echo "--- live/stale differentiation: A1 epoch-2 retrievals (retrieved_k in rank order; 5056=STALE, 4970=fresh) ---"
docker exec "$SANDBOX" python3 -c "
import json
for i,l in enumerate(open('$A1E2')):
    r=json.loads(l); md=r.get('memory_debug') or {}
    eff=r.get('normalized_efficiency')
    print(f'  A1-e2 run{i}: exit={r.get(\"found_exit\")} steps={r.get(\"steps_to_exit\")} eff={round(eff,2) if eff else None} '
          f'n={md.get(\"n_results\")} retrieved_k={md.get(\"retrieved_k\")}')
"
echo "--- the poison contrast (A1-epoch2 vs A0-epoch2, normalized_efficiency) ---"
docker exec "$SANDBOX" python3 /app/design2/analyze.py --metric normalized_efficiency \
  --baseline A0 A0=$A0E2 A1=$A1E2
echo
echo "POISON if A1-epoch2 < A0-epoch2 (CI of A1-A0 below 0, or A1 exit-rate < A0)."
