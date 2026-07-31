#!/bin/bash
# Local preview of the leaderboard site, containerized (no Node needed on the host).
# Usage:  bash dev.sh          # build + serve, rebuild on file changes
#         PORT=9000 bash dev.sh
#         bash dev.sh stop
set -euo pipefail

SITE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SITE_DIR")"          # site/ references ../entries and ../METHODOLOGY.md
PORT="${PORT:-8123}"
NAME=lb-site-dev
IMAGE=node:20-slim

if [[ "${1:-}" == "stop" ]]; then
  docker rm -f "$NAME" >/dev/null 2>&1 && echo "stopped $NAME" || echo "$NAME not running"
  exit 0
fi

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" \
  -p "${PORT}:8080" \
  -v "$REPO_DIR":/repo \
  -w /repo/site \
  "$IMAGE" \
  sh -c '[ -d node_modules ] || npm ci --no-fund --no-audit; npx eleventy --watch & exec node serve.js'

echo "building… first page load may take ~30s if npm ci has to run"
echo "  http://$(hostname -i 2>/dev/null | awk "{print \$1}" || echo localhost):${PORT}"
echo "edits under site/src, entries/, or METHODOLOGY.md rebuild automatically (refresh the page)"
echo "stop with:  bash dev.sh stop"
