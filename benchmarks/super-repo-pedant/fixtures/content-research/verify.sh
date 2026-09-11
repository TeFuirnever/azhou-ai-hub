#!/usr/bin/env bash
set -euo pipefail

test -f HANDOFF.md
grep -Eiq 'ready|complete|completed|已完成|可交接' STATUS.md HANDOFF.md
grep -Eq 'Tool B' HANDOFF.md
grep -Eq 'source-a' HANDOFF.md
test -f evidence/sources.md
test -f research/findings.md
test -f release/package.md
if grep -En 'research in progress|researching' STATUS.md ideas/backlog.md; then
  exit 1
fi
