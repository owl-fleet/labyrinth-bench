#!/usr/bin/env bash
# Gate 1b — the positive control for the LB Design 2 accumulation eval.
#
# Falsifier under test: does a PERFECT injected memory (the answer key) lift the run vs no memory?
# If A1 (reads the key) does NOT beat A0 (no memory) on ramp_depth, the metric cannot see memory —
# the model ignores injected context, or the task can't reward it. Fix that before any thesis task.
#
# Method: inject one hand-crafted answer-key record into the A1 collection, then run the SAME model
# +DEG under --arm A0 (never reads) and --arm A1 (reads the key). Only the cross-run memory faculty
# differs; the within-run HUD config is identical. Reports ramp_depth distributions for the contrast.
#
# Usage:  bash design2/gate1b.sh [N] [MODEL] [BASE_URL]
set -euo pipefail

N="${1:-6}"
MODEL="${2:-qwen3:14b}"
BASE_URL="${3:-http://localhost:11434/v1}"      # points directly at an OpenAI-compatible endpoint
DEG="replay-pos-0"
SANDBOX="labyrinth-bench-sandbox"
DEVDB="dev-timescaledb"
RESULTS=/results
A0_OUT="$RESULTS/g1b_a0.jsonl"
A1_OUT="$RESULTS/g1b_a1.jsonl"

echo "=== Gate 1b positive control: N=$N model=$MODEL deg=$DEG ==="

# 1. clean slate for both arm collections, then inject the PERFECT answer key into A1's collection.
docker exec "$DEVDB" psql -U knowledge -d knowledge -c \
  "DELETE FROM knowledge_items WHERE collection IN ('labyrinth/A0/replay-pos','labyrinth/A1/replay-pos');" >/dev/null
docker exec "$SANDBOX" rm -f "$A0_OUT" "$A1_OUT"

docker exec "$SANDBOX" python3 -c "
import sys, time; sys.path.insert(0,'/app')
from cli import accum_mem
c = accum_mem.MemoryClient()
rec = {
  'source_uri': 'labyrinth://A1/replay-pos-0/PERFECT-KEY',
  'source_type': 'labyrinth_session',
  'collection': 'labyrinth/A1/replay-pos',
  'retention': 'prunable',
  'text': ('Answer key recovered from a verified past run of replay-pos-0 (every gate confirmed '
           'correct). Match each gate call-sign and commit the listed product: ALPHA=10063, '
           'BRAVO=27401, CHARLIE=11248, DELTA=23464, ECHO=17226, FOXTROT=29736, GOLF=22836.'),
  'metadata': {'arm':'A1','deg_id':'replay-pos-0','deg_family':'replay-pos','outcome':'exit',
               'found_exit': True, 'ts': time.time(), 'perfect_key': True},
}
print('inject:', c.ingest_record(rec))
"

# 2. A0 — control, never reads (writes benign self-records to its own collection).
echo "--- A0 (no memory) x$N ---"
docker exec "$SANDBOX" python3 /app/cli/run_eval.py \
  --model "$MODEL" --base-url "$BASE_URL" --maze-url http://localhost:8090 \
  --deg "$DEG" --runs "$N" --arm A0 --no-think \
  --output "$A0_OUT" --label "g1b-A0" 2>&1 | grep -E "^Run|ramp|EXIT|DNF|Summary|Exit rate" || true

# 3. A1 — reads the injected perfect key every run (self-records are benign, never contain answers).
echo "--- A1 (perfect key) x$N ---"
docker exec "$SANDBOX" python3 /app/cli/run_eval.py \
  --model "$MODEL" --base-url "$BASE_URL" --maze-url http://localhost:8090 \
  --deg "$DEG" --runs "$N" --arm A1 --no-think \
  --output "$A1_OUT" --label "g1b-A1" 2>&1 | grep -E "^Run|ramp|EXIT|DNF|Summary|Exit rate" || true

# 4. report ramp_depth distributions for the contrast.
echo "=== Gate 1b result ==="
docker exec "$SANDBOX" python3 -c "
import json
def load(p):
    out=[]
    for ln in open(p):
        r=json.loads(ln)
        out.append({'ramp_depth': r.get('ramp_depth'), 'found_exit': r.get('found_exit'),
                    'retr': r.get('memory_retrievals'), 'n': (r.get('memory_debug') or {}).get('n_results')})
    return out
for arm,p in (('A0','$A0_OUT'),('A1','$A1_OUT')):
    rows=load(p)
    rd=[x['ramp_depth'] for x in rows if x['ramp_depth'] is not None]
    ex=sum(1 for x in rows if x['found_exit'])
    mean=sum(rd)/len(rd) if rd else float('nan')
    print(f'{arm}: n={len(rows)} ramp_depth={rd} mean={mean:.2f} exits={ex}/{len(rows)} '
          f'retrievals={[x[\"retr\"] for x in rows]} n_results={[x[\"n\"] for x in rows]}')
print()
print('FALSIFIER: if A1 mean ramp_depth does NOT exceed A0, the metric cannot see memory.')
"
