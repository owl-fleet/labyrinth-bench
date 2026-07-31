# lb-target-py — hermetic CODEGEN sandbox for the renderer rung.
#
# Same contract as lb-target (offline at run time, ephemeral, model has root in
# a throwaway layer) plus python3, with the frozen instrument BAKED at /lb/
# (rung0's /vendor pattern): fixtures + pristine renderer_check.py. The rung's
# per-turn state reader and final verdict always run /lb/renderer_check.py, so
# the model editing its /work copy changes nothing.
#
# Build from the REPO ROOT (paths below are repo-relative):
#   docker build -t lb-target-py:latest -f sandbox-target-py/Dockerfile .
# Rebuild whenever the frozen checker/fixtures change (they shouldn't — frozen).
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/* \
 && python3 --version

COPY sandbox/rungs/renderer_fixtures/journal.json \
     sandbox/rungs/renderer_fixtures/deg.json \
     sandbox/rungs/renderer_check.py \
     /lb/

# Commands from Target.exec land in /work (docker exec inherits WORKDIR).
WORKDIR /work

CMD ["sleep", "infinity"]
