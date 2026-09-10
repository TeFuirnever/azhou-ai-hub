# session-insights benchmark

Wiring-integrity suite for the session-insights aggregate/report pipeline, registered in the repository verify gate. At check time it builds synthetic Claude Code/Codex/zcode session stores inside a temporary directory — hand-written JSONL with deliberate noise (interruptions, an error-retry loop, a sidechain-only subagent session, meta/injected lines, a >200-char first prompt, secret-shaped seeds, absolute-home-path-shaped strings) — runs the CLI as a subprocess, and requires:

- the claude-code aggregate section matches the pinned golden exactly (counts, rankings, distributions, skip behavior), with the mtime-dependent composite digest checked separately;
- the default 30-day window trims the stale session, `--days 60` restores it, and `--max-sessions 2` keeps only the two most recent — all anchored to the newest observed session timestamp, never wall-clock now;
- the receipt input digest is stable across two runs on untouched files and changes after a fixture file content change;
- privacy negative controls: the report artifact contains no absolute home path, no seeded secret-shaped string, and — with excerpts off — no transcript text;
- fail-closed negative controls: detectable Codex/zcode stores yield `unsupported` holds and no speculative report sections.

Fixtures prove wiring only; they are never benchmark evidence about model behavior. No behavior benchmark yet.
