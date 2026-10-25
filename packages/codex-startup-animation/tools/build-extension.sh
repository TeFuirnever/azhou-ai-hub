#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Compatibility build entry: both commands produce the same hidden install payload.
exec bash tools/build-macos.sh "$@"
