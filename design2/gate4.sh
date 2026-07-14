#!/usr/bin/env bash
# Gate 4 — does CURATION flip the poison? (the climax)
#
# A2 = the organism: same accumulation as A1, but with the REAL oath_adjudicate currency dam
# (currency="current") + the LB-layer outcome-demote, attributed separately. The dam re-derives the
# FRESH canon from oathd (fact://lab/macguffin/k) and flags any record asserting a stale value; A2
# drops the flagged records. So after the shift, A2 distrusts its stale "K=5056" notes (the dam knows
# canon is now 4970), falls back to forging the fresh K, exits, and re-learns to skip the forge with
# the fresh value — recovering where A1 (naive) sits at 0/8.
#
# Protocol mirrors Gate 3 with the oathd canon synchronised to the world:
#   epoch 1 (shift-1, canon=5056): A1 + A2 accumulate "K=5056" (tagged via --macguffin-slot)
#   THE SHIFT: DEG -> shift-2, oathd canon -> 4970
#   epoch 2 (shift-2): A0 (baseline) + A1 (poisoned) + A2 (dam recovers)
# Win: A2 epoch-2 exit-rate >> A1 (0/8) and ~ A0 (8/8). Attribution: the stale records have
# outcome=EXIT, so the outcome-demote can't catch them — only the dam can (dam_dropped in A2's debug).
#
# Usage:  bash design2/gate4.sh [N_PRE] [M] [MODEL] [BASE_URL]   [THINK=0|1]
set -euo pipefail

N_PRE="${1:-6}"; M="${2:-8}"
MODEL="${3:-qwen3:14b}"; BASE_URL="${4:-http://localhost:11434/v1}"
THINK="${THINK:-0}"; NOTHINK=""; [ "$THINK" = "0" ] && NOTHINK="--no-think"
SLOT="fact://lab/macguffin/k"; FAM="macguffin-shift"
SANDBOX="labyrinth-bench-sandbox"; DEVDB="dev-timescaledb"; DEVW="dev-ingestion-worker"
A0E2="/results/g4_a0_e2.jsonl"; A1E2="/results/g4_a1_e2.jsonl"; A2E2="/results/g4_a2_e2.jsonl"

set_canon() {  # flip the oathd ground-truth canon (the value layer's view of "the shift")
  docker exec "$DEVW" python3 -c "import os,httpx; httpx.put(f\"{os.environ['OATHD_URL']}/facts/${SLOT}\", headers={'X-Oath-Token':os.environ.get('OATHD_TOKEN','')}, json={'value':'$1'}); print('canon -> $1')"
}
run() {  # arm deg runs outfile
  docker exec "$SANDBOX" python3 /app/cli/run_eval.py \
    --model "$MODEL" --base-url "$BASE_URL" --maze-url http://localhost:8090 \
    --deg "$2" --runs "$3" --arm "$1" $NOTHINK --macguffin-slot "$SLOT" \
    --output "$4" --label "g4-$1" 2>&1 | grep -E "^Run|EXIT|DNF|Exit rate|WRITE-BACK FAILED" || true
}

echo "=== Gate 4 (does curation flip the poison): N_PRE=$N_PRE M=$M model=$MODEL think=$THINK ==="
docker exec "$DEVDB" psql -U knowledge -d knowledge -c \
  "DELETE FROM knowledge_items WHERE collection LIKE 'labyrinth/A%/${FAM}%';" >/dev/null
docker exec "$SANDBOX" rm -f "$A0E2" "$A1E2" "$A2E2"

echo "--- EPOCH 1 (canon=5056): A1 + A2 accumulate K=5056 ---"
set_canon 5056
run A1 macguffin-shift-1 "$N_PRE" /results/g4_a1_e1.jsonl
run A2 macguffin-shift-1 "$N_PRE" /results/g4_a2_e1.jsonl
echo "--- THE SHIFT -> macguffin-shift-2, canon -> 4970 ---"
set_canon 4970
echo "--- EPOCH 2: A0 baseline ---";  run A0 macguffin-shift-2 "$M" "$A0E2"
echo "--- EPOCH 2: A1 poisoned ---";  run A1 macguffin-shift-2 "$M" "$A1E2"
echo "--- EPOCH 2: A2 dam recovers ---"; run A2 macguffin-shift-2 "$M" "$A2E2"

echo "=== Gate 4 result ==="
echo "--- A2 epoch-2 per run (retrieved_k = what was retrieved; dam_dropped = stale records the dam removed) ---"
docker exec "$SANDBOX" python3 -c "
import json
for i,l in enumerate(open('$A2E2')):
    r=json.loads(l); md=r.get('memory_debug') or {}
    eff=r.get('normalized_efficiency')
    print(f'  A2-e2 run{i}: exit={r.get(\"found_exit\")} steps={r.get(\"steps_to_exit\")} eff={round(eff,2) if eff else None} '
          f'retrieved_k={md.get(\"retrieved_k\")} dam_dropped={md.get(\"dam_dropped\")} dammed_k={md.get(\"dammed_k\")}')
"
echo "--- the recovery contrast (epoch-2 exit-rate: A0 baseline vs A1 poisoned vs A2 dam) ---"
docker exec "$SANDBOX" python3 /app/design2/analyze.py --metric normalized_efficiency \
  --baseline A0 A0=$A0E2 A1=$A1E2 A2=$A2E2
echo
echo "WIN if A2 epoch-2 exit-rate >> A1 (poisoned 0/8) and ~ A0 (8/8). The dam carried it iff dam_dropped>0."
