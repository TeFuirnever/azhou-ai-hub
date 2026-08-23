#!/usr/bin/env bash
set -euo pipefail

rg -l '/v2/jobs' README.md AGENTS.md spec.md HANDOFF.md docs/integration.md agent-memory/MEMORY.md >/dev/null
rg -l 'JOB_QUEUE_URL' README.md AGENTS.md spec.md HANDOFF.md docs/integration.md agent-memory/MEMORY.md >/dev/null
rg -l './deploy.sh --service api --region' README.md AGENTS.md HANDOFF.md docs/runbook.md agent-memory/MEMORY.md >/dev/null
if rg -n '/v1/jobs|\bQUEUE_URL\b|\./deploy\.sh prod' README.md AGENTS.md spec.md HANDOFF.md docs agent-memory; then
  exit 1
fi
