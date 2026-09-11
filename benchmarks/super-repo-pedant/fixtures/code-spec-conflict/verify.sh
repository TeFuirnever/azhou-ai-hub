#!/usr/bin/env bash
set -euo pipefail

grep -Eq 'POST /v2/export' README.md STATUS.md
grep -Eiq 'current|active|现役|当前' README.md STATUS.md
grep -Eq 'POST /v3/export' spec.md
grep -Eiq 'target|intended|planned|目标|未实现' spec.md
grep -Eq 'path: "/v2/export"' src/routes.ts tests/routes.test.ts
if grep -En 'Current endpoint: `POST /v3/export`|Active export route: `POST /v3/export`|v3 endpoint is ready|Migration: complete' README.md STATUS.md; then
  exit 1
fi
