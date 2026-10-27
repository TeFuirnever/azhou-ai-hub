#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
# Always build current sources, consolidate the installed entry, then launch it.
exec bash tools/install-macos.sh --open
