# Repo Pedant history parsers receipt — Claude + zcode — 2026-09-01

This receipt records a redacted real-host check that the implemented Claude and zcode session parsers (`skills/repo-pedant/scripts/collect_agent_history.py`) parse real local sessions of each host and produce their documented normalized, privacy-preserving output. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `85447284c8953e7f1797b46146ad80e247b1d518` (merged `main`; the two later `docs(evidence)` commits of this slice touch only `evidence/` files, so the parser code is identical)
- Host: macOS 26.6.2, arm64; Python 3.14.7
- Parser inputs: the hosts' real local session homes (`~/.claude/projects/` for Claude Code; the zcode session home for zcode), read-only
- Mode: attempt-1 parser runs against real local history, output saved Git-external

## Results

| Check | Host | Result | Evidence |
|---|---|---|---|
| Claude session parser on real local sessions | Claude Code | `PASS` | `collect_agent_history.py --runtime claude --limit 5 --format json`: `files_scanned: 161`, `parse_errors: 0`, `runs_found: 5` with hashed run/session/source/request digests, explicit-user invocation evidence, assistant/tool/mutation/destructive/failure counts, correction/abort/receipt signals and one conservative outcome label per run (`receipt_emitted` ×3, `insufficient_evidence` ×1, `tool_failure_signal` ×1). `raw_text_included: false`, `identifiers_hashed: true`. |
| zcode session parser on real local sessions | zcode | `PASS` | Same command with `--runtime zcode`: `files_scanned: 19`, `parse_errors: 0`, `recorded_run_count: 2` runs with the same normalized fields, including the `origin: claudeCode` import attribution on both runs. Outcomes: `receipt_emitted` ×1, `insufficient_evidence` ×1. |
| Privacy contract | both | `no raw text in default output` | Both outputs declare `raw_text_included: false`, `excerpts_redacted_and_truncated: false`, `identifiers_hashed: full digests only`, `transcripts_treated_as_untrusted: true`. Full parser JSON outputs are recorded Git-external for verification; only these summary figures enter Git. Git contains no raw session data. |

## Cross-checks

- File counts match the real local homes: 161 Claude session files and 19 zcode session files were scanned with zero parse errors, so the parse succeeded on the real local history shapes of both hosts rather than a fixture.
- The zcode runs' `origin: claudeCode` field matches the documented import-attribution behavior (imported sessions attributed to the runtime file that supplied them).
- A second run of each command reproduced the same `files_scanned`/`parse_errors`/`runs_found` figures at a new timestamp (parser deterministic on unchanged homes), matching the deterministic-recheck discipline of the earlier Foundation receipts; run-level identifiers are content digests and repeated identifiers across the two runs confirm the hashing is stable per session.

## Claim boundary

This proves the implemented Claude and zcode session parsers parse the real local session history of each host on this machine and emit the documented normalized privacy-preserving schema (`repo-pedant.history.v1`) with zero parse errors, including zcode import attribution. It does not prove Codex parser behavior (already recorded elsewhere), GUI-surface behavior, or that the conservative outcome labels are semantically complete — the reference documents these as heuristics with counted parse errors. Full parser outputs stay Git-external; nothing private is committed.