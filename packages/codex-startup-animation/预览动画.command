#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
# Interactive browser preview always reads this project's current sources.
open "$PWD/index.html"
