#!/usr/bin/env bash
set -euo pipefail

test -f HANDOFF.md
rg -i 'ready|complete|completed|已完成|可交接' STATUS.md HANDOFF.md >/dev/null
rg 'Tool B' HANDOFF.md >/dev/null
rg 'source-a' HANDOFF.md >/dev/null
test -f evidence/sources.md
test -f research/findings.md
test -f release/package.md
if rg -n 'research in progress|researching' STATUS.md ideas/backlog.md; then
  exit 1
fi
