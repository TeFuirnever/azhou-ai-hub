#!/usr/bin/env bash
set -euo pipefail

grep -El '/v2/jobs' README.md AGENTS.md spec.md HANDOFF.md docs/integration.md agent-memory/MEMORY.md >/dev/null
grep -El 'JOB_QUEUE_URL' README.md AGENTS.md spec.md HANDOFF.md docs/integration.md agent-memory/MEMORY.md >/dev/null
grep -El './deploy.sh --service api --region' README.md AGENTS.md HANDOFF.md docs/runbook.md agent-memory/MEMORY.md >/dev/null
if grep -En '/v1/jobs|(^|[^[:alnum:]_])QUEUE_URL([^[:alnum:]_]|$)|\./deploy\.sh prod' README.md AGENTS.md spec.md HANDOFF.md docs/integration.md docs/runbook.md agent-memory/MEMORY.md; then
  exit 1
fi
