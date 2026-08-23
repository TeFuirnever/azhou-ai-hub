#!/usr/bin/env bash
set -euo pipefail

test -f analysis/history-report.json
test -f analysis/HYPOTHESIS.md
test -f analysis/DECISION.md

python3 - <<'PY'
import json
from pathlib import Path

report = json.loads(Path("analysis/history-report.json").read_text())
assert report["runs_found"] == 3
assert {item["runtime"] for item in report["runs"]} == {"codex", "claude", "zcode"}
serialized = json.dumps(report)
assert "synthetic-codex-session" not in serialized
assert "synthetic-claude-session" not in serialized
assert "synthetic-zcode-session" not in serialized
assert "request_excerpt" not in serialized
PY

rg -q 'synthetic-codex-001' analysis/HYPOTHESIS.md
rg -q 'synthetic-claude-001' analysis/HYPOTHESIS.md
rg -q 'stale_agent_docs_after_code_change' analysis/HYPOTHESIS.md
rg -qi 'three|3|三' analysis/DECISION.md
rg -qi 'human|人类|用户确认|checkpoint' analysis/DECISION.md
