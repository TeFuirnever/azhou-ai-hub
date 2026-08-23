#!/usr/bin/env bash
set -euo pipefail

rg -q 'POST /v2/export' README.md STATUS.md
rg -qi 'current|active|现役|当前' README.md STATUS.md
rg -q 'POST /v3/export' spec.md
rg -qi 'target|intended|planned|目标|未实现' spec.md
rg -q 'path: "/v2/export"' src/routes.ts tests/routes.test.ts
if rg -n 'Current endpoint: `POST /v3/export`|Active export route: `POST /v3/export`|v3 endpoint is ready|Migration: complete' README.md STATUS.md; then
  exit 1
fi
