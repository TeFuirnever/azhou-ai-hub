#!/usr/bin/env bash
set -euo pipefail

test "${1:-}" = "--service"
test "${2:-}" = "api"
test "${3:-}" = "--region"
test -n "${4:-}"
