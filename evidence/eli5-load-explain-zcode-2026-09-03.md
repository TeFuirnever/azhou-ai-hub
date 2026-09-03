# Eli5 package load and explain task receipt — zcode — 2026-09-03

This receipt records a redacted real-host check that the zcode host loads the linked `eli5` package and completes one documented explain task with a self-contained HTML artifact. It contains no user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `cb8a26efe8cee76eea850a256599c6d2bd2b0bf4` (the linked user-scope package resolves to this content)
- Host: macOS (Apple Silicon), zcode GUI app session (interactive; the ZCode desktop host, user-scope Agent Skills root)
- Mode: interactive GUI session run through the host's native Skill surface, attempt-1

## Install step

~~~bash
python3 scripts/azhou_hub.py setup --skill autoresearch --skill azhou-doctor --skill azhou-info --skill azhou-setup --skill azhou-verify --skill eli5 --skill excalidraw-diagram --skill lavish --skill llm-wiki --skill repo-pedant --skill super-caveman \
  --target ~/.agents/skills --mode link --apply --plan-id 8d64ab4ad4a26f348e9e1c767d771f8dcb32bd5cad0a15de6cb600149273d7fd --json
~~~

- Dry-run `planId` recorded above; apply exit `0`; the prior stale `eli5` copy (pre-0.5.0 snapshot without `references/`) was moved Git-external to a backup directory before linking, disclosed here.

## Results

| Check | Result | Evidence |
|---|---|---|
| Package load through the native Skill surface | `PASS` | The interactive session loaded `eli5` from the linked user-scope path; the returned package body is the current canonical SKILL.md including the `🦊 阿舟 · Eli5` identity block, brand protocol and references. |
| Startup protocol | `PASS` | `🦊 阿舟 · Eli5 启动｜mode=explain｜scope=Git commit` emitted once. |
| One documented explain task | `PASS` | Topic "什么是 Git 的 commit" produced exactly one HTML artifact written to a Git-external temp path (user-visible, disclosed). |
| Artifact read-back and self-containment | `PASS` | Read-back: DOCTYPE present, three promised sections plus summary present; `grep` for external resource references (`src="http…"`, `href="http…"`, `@import`, `url(http…)`) returned 0; 5588 bytes. |

## Claim boundary

This proves the zcode GUI host loads the linked `eli5` package and that one real explain task completes with a read-back-verified self-contained artifact on this machine, attempt-1. It does not prove model quality (no benchmark claim), headless CLI behavior, or cross-host parity. Raw artifacts stay Git-external; nothing private is committed.
