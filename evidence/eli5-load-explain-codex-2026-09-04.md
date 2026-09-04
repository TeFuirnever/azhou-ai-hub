# Eli5 package load and explain task receipt — Codex — 2026-09-04

This receipt records a redacted real-host check that the Codex CLI host loads the linked `eli5` package and completes one documented explain task with a self-contained HTML artifact. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `7d16d6da321745b0fec8657c85d8b226e7755e12` (the linked user-scope package resolves to this content)
- Host: macOS, arm64; Codex CLI `codex-cli 0.152.0`, model `gpt-5.6-sol` (reasoning effort `xhigh`)
- Mode: headless `codex exec` run in an empty disposable Git-initialized working directory (harness and cases stayed outside it), user-scope Agent Skills root, attempt-1

## Results

| Check | Result | Evidence |
|---|---|---|
| Package load through the host skill surface | `PASS` | The headless run resolved `eli5` from the user-scope linked root and followed its documented startup protocol, topic boundary and artifact contract. |
| Skill receipt emitted | `PASS` | The run closed with the skill's own `eli5.receipt.v1` stable receipt, `status: pass`. |
| One documented explain task | `PASS` | Topic "什么是 Git 的 commit" produced exactly one HTML artifact (`eli5-explain.html`, 10,175 bytes) in the run's working directory. |
| Artifact read-back and self-containment | `PASS` | Read-back: DOCTYPE present, `lang="zh-CN"`, six explained sections with four inline SVG illustrations; `grep` for external resource references (`src="http…"`, `href="http…"`, `@import`, `url(http…)`) returned 0 matches. |

## Claim boundary

This proves the Codex CLI host loads the linked `eli5` package and that one real explain task completes with a read-back-verified self-contained artifact on this machine, attempt-1. It does not prove model quality (no benchmark claim), interactive TUI behavior, or cross-host parity. Raw run artifacts stay Git-external; nothing private is committed.
