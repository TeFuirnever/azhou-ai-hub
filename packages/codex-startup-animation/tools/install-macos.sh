#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  --check|--help|-h) exec python3 tools/install-macos.py "$@" ;;
esac
bash tools/build-macos.sh
exec python3 tools/install-macos.py "$@"
