#!/usr/bin/env bash
# Generalized interleaved poison/recovery driver — the multi-arm successor to gate_hardened.sh.
# Same science (epoch-1 accumulate -> SHIFT canon -> epoch-2 contrast) with the A-8 thermal/order
# guard: arms run INTERLEAVED, order rotated per run-index, --run-offset continues each arm's curve.
# The arm SETS are configurable so one driver serves the Design-2 follow-ons:
#   Exp 1 (recency):      E1_ARMS="A2 A2W A2R"   E2_ARMS="A0 A2 A2W A2R"   (defaults)
#   Exp 2 (trust-verify): E1_ARMS="A1 A2 A5"     E2_ARMS="A0 A1 A2 A5"
# The canon flip stays a HARD barrier between epochs (interleave is within-epoch only).
#
# Usage:  bash design2/gate_arms.sh [N_PRE] [M] [MODEL] [BASE_URL]
# Env:    THINK=0|1 ; DEG1 DEG2 CANON1 CANON2 FAM TAG SLOT ; E1_ARMS E2_ARMS
set -euo pipefail

N_PRE="${1:-16}"; M="${2:-16}"
MODEL="${3:-qwen3:14b}"; BASE_URL="${4:-http://localhost:11434/v1}"
THINK="${THINK:-0}"; NOTHINK=""; [ "$THINK" = "0" ] && NOTHINK="--no-think"

DEG1="${DEG1:-macguffin-shift-1}"; DEG2="${DEG2:-macguffin-shift-2}"
CANON1="${CANON1:-5056}";          CANON2="${CANON2:-4970}"
FAM="${FAM:-macguffin-shift}";     TAG="${TAG:-ga_recency}"
SLOT="${SLOT:-fact://lab/macguffin/k}"
read -r -a E1_ARMS <<< "${E1_ARMS:-A2 A2W A2R}"
read -r -a E2_ARMS <<< "${E2_ARMS:-A0 A2 A2W A2R}"

SANDBOX="labyrinth-bench-sandbox"; DEVDB="dev-timescaledb"; DEVW="dev-ingestion-worker"

outfile() { echo "/results/${TAG}_${1,,}_$2.jsonl"; }   # arm, epoch(e1|e2)

set_canon() {  # flip the oathd ground-truth canon (the value layer's view of "the shift")
  docker exec "$DEVW" python3 -c "import os,httpx; httpx.put(f\"{os.environ['OATHD_URL']}/facts/${SLOT}\", headers={'X-Oath-Token':os.environ.get('OATHD_TOKEN','')}, json={'value':'$1'}); print('canon -> $1')"
}
run() {  # arm deg run_index outfile
  docker exec "$SANDBOX" python3 /app/cli/run_eval.py \
    --model "$MODEL" --base-url "$BASE_URL" --maze-url http://localhost:8090 \
    --deg "$2" --runs 1 --run-offset "$3" --arm "$1" $NOTHINK --macguffin-slot "$SLOT" \
    --output "$4" --label "${TAG}-$1" 2>&1 | grep -E "^Run|EXIT|DNF|WRITE-BACK FAILED" || true
}
interleave() {  # deg  n  eptag  arms...
  local deg="$1" n="$2" eptag="$3"; shift 3; local arms=("$@"); local m=${#arms[@]}
  for ((k=0; k<n; k++)); do
    for ((j=0; j<m; j++)); do
      local arm="${arms[$(( (k + j) % m ))]}"   # rotate start by k so each arm hits each time-slot
      echo "  [$eptag k=$k] $arm"; run "$arm" "$deg" "$k" "$(outfile "$arm" "$eptag")"
    done
  done
}

echo "=== gate_arms (interleaved): N_PRE=$N_PRE M=$M model=$MODEL think=$THINK tag=$TAG ==="
echo "    DEG $DEG1 -> $DEG2  canon $CANON1 -> $CANON2  E1=[${E1_ARMS[*]}]  E2=[${E2_ARMS[*]}]"
docker exec "$DEVDB" psql -U knowledge -d knowledge -c \
  "DELETE FROM knowledge_items WHERE collection LIKE 'labyrinth/A%/${FAM}%';" >/dev/null
for arm in "${E1_ARMS[@]}" "${E2_ARMS[@]}"; do
  docker exec "$SANDBOX" rm -f "$(outfile "$arm" e1)" "$(outfile "$arm" e2)"
done

echo "--- EPOCH 1 (canon=$CANON1): [${E1_ARMS[*]}] accumulate, INTERLEAVED x$N_PRE ---"
set_canon "$CANON1"
interleave "$DEG1" "$N_PRE" e1 "${E1_ARMS[@]}"

echo "--- THE SHIFT -> $DEG2, canon -> $CANON2 ---"
set_canon "$CANON2"

echo "--- EPOCH 2 (canon=$CANON2): [${E2_ARMS[*]}] contrast, INTERLEAVED x$M ---"
interleave "$DEG2" "$M" e2 "${E2_ARMS[@]}"

echo "=== gate_arms result ($TAG) — epoch-2 contrast (bootstrap CIs) ==="
ANALYZE_ARGS=""
for arm in "${E2_ARMS[@]}"; do ANALYZE_ARGS="$ANALYZE_ARGS ${arm}=$(outfile "$arm" e2)"; done
ANALYZE_OUT=$(docker exec "$SANDBOX" python3 /app/design2/analyze.py --metric normalized_efficiency \
  --baseline A0 $ANALYZE_ARGS)
echo "$ANALYZE_OUT"
echo
# Honest verdict — COMPUTED from the bootstrap CIs above, never asserted. An arm "wins" only if its
# efficiency-delta vs A0 is SEPARATED from 0 (95% CI excludes 0); otherwise it is a null at this N.
WINS=""
for arm in "${E2_ARMS[@]}"; do
  [ "$arm" = "A0" ] && continue
  if echo "$ANALYZE_OUT" | grep -qE "^[[:space:]]*${arm} - A0:.*SEPARATED from 0"; then
    WINS="$WINS $arm"
  fi
done
if [ -n "$WINS" ]; then
  echo "VERDICT:${WINS} efficiency SEPARATED from A0 (95% CI excludes 0) — real effect at this N."
else
  echo "VERDICT: NULL — no arm's efficiency CI separated from A0 at this N (all overlap 0). Read the CIs above; do NOT claim a win."
fi
