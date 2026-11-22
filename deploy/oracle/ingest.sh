#!/bin/sh
# Loads new monitor-state snapshots into the self-hosted database on the Oracle server.
# Run every 15 minutes by stockwatch-ingest.timer; it does the work only once per finished
# scrape run on GitHub (checked through the public API, no token), like ingest.yml used to.
#   sh deploy/oracle/ingest.sh --now    # run regardless
set -eu
cd "$(dirname "$0")/../.."
STATE="$HOME/.stockwatch-last-scrape"
API='https://api.github.com/repos/fafo-0847/brands-monitor/actions/workflows/brands.yml/runs?status=completed&per_page=1'

latest=$(curl -fsS -m 30 "$API" | python3 -c 'import json, sys; runs = json.load(sys.stdin)["workflow_runs"]; print(runs[0]["id"] if runs else "")') || latest=""
if [ "${1:-}" != "--now" ] && [ -n "$latest" ] && [ "$latest" = "$(cat "$STATE" 2>/dev/null || true)" ]; then
  exit 0
fi
echo "scrape run ${latest:-unknown}: loading"

git fetch -q --no-tags --filter=blob:none origin '+refs/heads/monitor-state:refs/remotes/origin/monitor-state'
set -a
. ./.db.env                          # DATABASE_URL (local pooler), written at setup, not in git
[ -f ./.push.env ] && . ./.push.env  # optional EXPO_ACCESS_TOKEN
set +a
export INGEST_MAX_DB_MB="${INGEST_MAX_DB_MB:-60000}"

.venv/bin/pip install -q -r pipeline/requirements.txt
.venv/bin/python -m pipeline.migrate
.venv/bin/python -m pipeline.maintain
.venv/bin/python -m pipeline.ingest
if [ -n "$latest" ]; then echo "$latest" > "$STATE"; fi
