#!/usr/bin/env bash
# Gate 2 — does cross-run memory HELP? (no env-shift yet)
#
# A1 (naive accumulation) vs A0 (no memory) on the macguffin forge/direct fork. A1's run 1 has no
# memory so it forges K like A0; runs 2+ should recall K and take the direct approach, skipping the
# error-prone gauntlet -> fewer steps + higher exit-rate. A0 forges every run. The contrast is the
# learning curve: A1 improves over runs, A0 stays flat.
#
# Falsifier (Gate 2): if A1 does NOT beat A0 (no efficiency gain, no exit lift, no learning curve),
# either the task does not reward memory or the model cannot exploit memory for planning. Fix the task
# (gauntlet cost / briefing hint) before claiming the thesis.
#
# Usage:  bash design2/gate2.sh [N] [DEG] [MODEL] [BASE_URL]  [THINK=0|1]
set -euo pipefail

N="${1:-5}"
DEG="${2:-macguffin-acc-1}"
MODEL="${3:-qwen3:14b}"
BASE_URL="${4:-http://localhost:11434/v1}"
THINK="${THINK:-1}"                                  # 1 = let the model reason about route choice
NOTHINK=""; [ "$THINK" = "0" ] && NOTHINK="--no-think"
FAM="$(echo "$DEG" | sed -E 's/-[0-9]+$//')"         # macguffin-acc-1 -> macguffin-acc
SANDBOX="labyrinth-bench-sandbox"; DEVDB="dev-timescaledb"
A0_OUT="/results/g2_a0.jsonl"; A1_OUT="/results/g2_a1.jsonl"

echo "=== Gate 2 (does memory help): N=$N deg=$DEG model=$MODEL think=$THINK ==="
docker exec "$DEVDB" psql -U knowledge -d knowledge -c \
  "DELETE FROM knowledge_items WHERE collection LIKE 'labyrinth/A0/${FAM}%' OR collection LIKE 'labyrinth/A1/${FAM}%';" >/dev/null
docker exec "$SANDBOX" rm -f "$A0_OUT" "$A1_OUT"

for ARM_OUT in "A0:$A0_OUT" "A1:$A1_OUT"; do
  ARM="${ARM_OUT%%:*}"; OUT="${ARM_OUT##*:}"
  echo "--- $ARM x$N ---"
  docker exec "$SANDBOX" python3 /app/cli/run_eval.py \
    --model "$MODEL" --base-url "$BASE_URL" --maze-url http://localhost:8090 \
    --deg "$DEG" --runs "$N" --arm "$ARM" $NOTHINK \
    --output "$OUT" --label "g2-$ARM" 2>&1 | grep -E "^Run|EXIT|DNF|Exit rate|WRITE-BACK FAILED" || true
  # integrity: content-chunk count must equal N, or a silent write dropped (breaks the curve).
  CNT=$(docker exec "$DEVDB" psql -U knowledge -d knowledge -tA -c \
    "SELECT count(*) FROM knowledge_items WHERE collection='labyrinth/${ARM}/${FAM}' AND source_type='labyrinth_session';")
  echo "  [integrity] $ARM wrote $CNT/$N records"
done

echo "=== Gate 2 result (per-run; steps~=3 => direct/forge-skipped, ~=7+ => walked the gauntlet) ==="
docker exec "$SANDBOX" python3 -c "
import json
def rows(p):
    return [json.loads(l) for l in open(p)]
for arm,p in (('A0','$A0_OUT'),('A1','$A1_OUT')):
    rr=rows(p)
    print(f'--- {arm} ---')
    for i,r in enumerate(rr):
        md=r.get('memory_debug') or {}
        eff=r.get('normalized_efficiency')
        print(f'  run{i}: exit={r.get(\"found_exit\")} ramp={r.get(\"ramp_depth\")} steps={r.get(\"steps_to_exit\")} '
              f'eff={round(eff,2) if eff else None} retr={r.get(\"memory_retrievals\")} n={md.get(\"n_results\")}')
    ex=sum(1 for r in rr if r.get('found_exit'))
    effs=[r['normalized_efficiency'] for r in rr if r.get('normalized_efficiency')]
    me=sum(effs)/len(effs) if effs else float('nan')
    print(f'  {arm}: exits={ex}/{len(rr)}  mean_eff={me:.2f}')
print()
print('Read the learning curve: A1 later runs should show steps~3 (direct) while A0 stays ~7 (forge).')
"
