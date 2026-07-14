#!/usr/bin/env bash
# Gate-hardened — the publishable Gate 4 (poison -> dam recovery) with the A-8 thermal/order guard.
#
# Identical SCIENCE to gate4.sh (epoch-1 accumulate -> SHIFT canon -> epoch-2 A0/A1/A2 contrast), but:
#   • INTERLEAVED arm execution — instead of "all A0, then all A1, then all A2" (which confounds arm
#     identity with run-slot if the model/GPU drifts thermally over the run), it loops outer over the
#     run-index k and inner over the arms, ROTATING the arm order each k so every arm occupies every
#     time-slot equally. Any thermal/temporal drift now spreads evenly across arms.
#   • LARGER N is just a bigger M.
#   • Run-offset: each arm's learning curve is continued across interleaved `--runs 1` calls via
#     `--run-offset k` (the cross-run store is stateful in dev-timescaledb; run_index keeps counting).
#   • PARAMETERISED DEG family + canon, so the SAME driver runs the shift headline (default) OR the
#     no-rote `macguffin-drift` variant (different K *and* a different seal offset).
#
# The canon flip stays a HARD BARRIER between epochs — interleaving is WITHIN an epoch only, so the
# env-shift semantics are preserved exactly.
#
# Usage:   bash design2/gate_hardened.sh [N_PRE] [M] [MODEL] [BASE_URL]
# Env:     THINK=0|1                  (0 = --no-think, the maximal-poison default; 1 = thinking on)
#          DEG1 DEG2 CANON1 CANON2    (epoch-1 deg / epoch-2 deg / epoch-1 canon / epoch-2 canon)
#          FAM TAG SLOT
# Shift headline (default):   bash design2/gate_hardened.sh 16 16
# No-rote drift variant:      DEG1=macguffin-drift-1 DEG2=macguffin-drift-2 CANON1=5561 CANON2=5544 \
#                             FAM=macguffin-drift TAG=gh_drift bash design2/gate_hardened.sh 16 16
# Thinking-mode replication:  THINK=1 TAG=gh_shift_think bash design2/gate_hardened.sh 16 16
set -euo pipefail

N_PRE="${1:-16}"   # epoch-1 accumulation runs per accumulating arm (A1, A2)
M="${2:-16}"       # epoch-2 runs per arm (the poison/recovery contrast)
MODEL="${3:-qwen3:14b}"
BASE_URL="${4:-http://localhost:11434/v1}"
THINK="${THINK:-0}"; NOTHINK=""; [ "$THINK" = "0" ] && NOTHINK="--no-think"

DEG1="${DEG1:-macguffin-shift-1}"; DEG2="${DEG2:-macguffin-shift-2}"
CANON1="${CANON1:-5056}";          CANON2="${CANON2:-4970}"
FAM="${FAM:-macguffin-shift}";     TAG="${TAG:-gh_shift}"
SLOT="${SLOT:-fact://lab/macguffin/k}"

SANDBOX="labyrinth-bench-sandbox"; DEVDB="dev-timescaledb"; DEVW="dev-ingestion-worker"
A1E1="/results/${TAG}_a1_e1.jsonl"; A2E1="/results/${TAG}_a2_e1.jsonl"
A0E2="/results/${TAG}_a0_e2.jsonl"; A1E2="/results/${TAG}_a1_e2.jsonl"; A2E2="/results/${TAG}_a2_e2.jsonl"

set_canon() {  # flip the oathd ground-truth canon (the value layer's view of "the shift")
  docker exec "$DEVW" python3 -c "import os,httpx; httpx.put(f\"{os.environ['OATHD_URL']}/facts/${SLOT}\", headers={'X-Oath-Token':os.environ.get('OATHD_TOKEN','')}, json={'value':'$1'}); print('canon -> $1')"
}
run() {  # arm deg run_index outfile
  docker exec "$SANDBOX" python3 /app/cli/run_eval.py \
    --model "$MODEL" --base-url "$BASE_URL" --maze-url http://localhost:8090 \
    --deg "$2" --runs 1 --run-offset "$3" --arm "$1" $NOTHINK --macguffin-slot "$SLOT" \
    --output "$4" --label "${TAG}-$1" 2>&1 | grep -E "^Run|EXIT|DNF|WRITE-BACK FAILED" || true
}

echo "=== Gate-hardened (interleaved poison/recovery): N_PRE=$N_PRE M=$M model=$MODEL think=$THINK ==="
echo "    DEG1=$DEG1 DEG2=$DEG2 canon $CANON1 -> $CANON2  family=$FAM  tag=$TAG"
docker exec "$DEVDB" psql -U knowledge -d knowledge -c \
  "DELETE FROM knowledge_items WHERE collection LIKE 'labyrinth/A%/${FAM}%';" >/dev/null
docker exec "$SANDBOX" rm -f "$A1E1" "$A2E1" "$A0E2" "$A1E2" "$A2E2"

echo "--- EPOCH 1 (canon=$CANON1): A1 + A2 accumulate K=$CANON1, INTERLEAVED over $N_PRE runs ---"
set_canon "$CANON1"
for ((k=0; k<N_PRE; k++)); do
  if (( k % 2 == 0 )); then order=(A1 A2); else order=(A2 A1); fi   # alternate slot order
  for arm in "${order[@]}"; do
    [ "$arm" = "A1" ] && out="$A1E1" || out="$A2E1"
    echo "  [e1 k=$k] $arm"; run "$arm" "$DEG1" "$k" "$out"
  done
done

echo "--- THE SHIFT -> $DEG2, canon -> $CANON2 ---"
set_canon "$CANON2"

echo "--- EPOCH 2 (canon=$CANON2): A0 / A1 / A2 INTERLEAVED over $M runs, arm-order rotated ---"
for ((k=0; k<M; k++)); do
  case $(( k % 3 )) in                                             # rotate so each arm hits each slot
    0) order=(A0 A1 A2) ;;
    1) order=(A1 A2 A0) ;;
    2) order=(A2 A0 A1) ;;
  esac
  for arm in "${order[@]}"; do
    case "$arm" in A0) out="$A0E2";; A1) out="$A1E2";; A2) out="$A2E2";; esac
    echo "  [e2 k=$k] $arm"; run "$arm" "$DEG2" "$k" "$out"
  done
done

echo "=== Gate-hardened result ($TAG) ==="
echo "--- A2 epoch-2 per run (retrieved_k = what was surfaced; dam_dropped = stale records the dam removed) ---"
docker exec "$SANDBOX" python3 -c "
import json
for i,l in enumerate(open('$A2E2')):
    r=json.loads(l); md=r.get('memory_debug') or {}
    eff=r.get('normalized_efficiency')
    print(f'  A2-e2 run{i}: exit={r.get(\"found_exit\")} steps={r.get(\"steps_to_exit\")} eff={round(eff,2) if eff else None} '
          f'retrieved_k={md.get(\"retrieved_k\")} dam_dropped={md.get(\"dam_dropped\")} dammed_k={md.get(\"dammed_k\")}')
"
echo "--- the recovery contrast (epoch-2: A0 baseline vs A1 poisoned vs A2 dam), bootstrap CIs ---"
docker exec "$SANDBOX" python3 /app/design2/analyze.py --metric normalized_efficiency \
  --baseline A0 A0=$A0E2 A1=$A1E2 A2=$A2E2
echo
echo "WIN if A2 epoch-2 exit-rate >> A1 (poisoned) and ~ A0, with A2-A0 eff CI separated from 0."
echo "The dam carried it iff dam_dropped>0 on A2's stale-retrieval runs."
