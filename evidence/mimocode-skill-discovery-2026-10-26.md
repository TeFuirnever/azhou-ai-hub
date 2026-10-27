# MiMo Code local Skill discovery — 2026-10-26

Scope: one maintainer Mac, MiMo Code CLI `mimo` 0.1.15. This is a read-only Skill discovery check, not a model invocation or acceptance of lifecycle hooks, MCP transport, session parsing, or every Skill workflow.

- `command -v mimo` resolved to `$HOME/.mimocode/bin/mimo`; `mimo --version` returned `0.1.15`. The distinct command `mino` was absent. The user confirmed that MiMo Code is the intended fourth harness.
- In the existing user environment, `mimo debug skill` listed nine of the Hub's fourteen canonical Skill names: `super-arch-doc`, `super-archify`, `super-asd-ste100`, `super-eli5`, `super-excalidraw-diagram`, `super-lavish`, `super-llm-wiki`, `super-repo-pedant`, and `super-session-insights`. The other five were not installed in the scanned user roots, so this does not measure their compatibility.
- A temporary project installed only the remaining five as links under `.mimocode/skills/`: `super-ask-azhou`, `super-azhou-doctor`, `super-azhou-info`, `super-azhou-setup`, and `super-azhou-verify`. With a fresh `MIMOCODE_HOME`, built-in and `.agents` scanning disabled, and `--pure`, `mimo debug skill` exited `0` and returned all five names. The temporary project and MiMo home were removed after the check.
- The CLI printed malformed JSON when all fourteen packages plus the user's broad Skill catalog were scanned in one debug call; the cause was not established. The two bounded checks above establish discovery of each canonical name; they do not establish a complete single-session load or invocation.

MiMo Code's [official configuration reference](https://github.com/XiaomiMiMo/MiMo-Code/blob/main/packages/opencode/src/skill/builtin/.bundle/mimocode-docs/reference/config.md) documents `.mimocode/skills/` and `.agents/skills/` as discovery roots. No permanent MiMo configuration, installed Skill, or user session was changed.
