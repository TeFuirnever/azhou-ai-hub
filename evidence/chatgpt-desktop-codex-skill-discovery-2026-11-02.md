# ChatGPT desktop Codex shared-root skill discovery receipt (2026-11-02)

Scope: shared-root discovery receipt for the ChatGPT desktop app's built-in Codex engine on this host (`/Applications/ChatGPT.app`, bundled `codex-cli` 0.166.0-alpha.5.1 measured in-process, reading the default `~/.codex`; the session self-identified as "Codex, based on GPT-6" without a finer version string). One real desktop session ran the receipt prompt read-only. Nothing under `~/.codex`, `~/.agents`, or the repository was modified.

Findings:

- Discovery. The session read the user root `~/.agents/skills` and found 163 skills with a readable `SKILL.md`: 68 pstack skills (deterministic criterion, resolved path contains `harness/pstack/skills-root/skills`) plus 95 user skills. The full 68-name pstack list matches the installed set exactly.
- Expectation correction, owned by the preparing session. The prompt expected "164 skills"; 164 is the entry count, not the skill count. A live recount settles the difference: 164 entries, of which 163 carry a `SKILL.md`; the 164th is the `SOURCES.md` manifest file. The DSH receipt of the same date had already reported this breakdown (77 symlinks + 86 directories + 1 file). Under the corrected criterion the discovery check passes; the receipt's "不过" marks the prompt's number, not a discovery failure.
- Link spot-checks. `poteto-mode` and `architect` are symlinks resolving into the skills-root tree with readable `SKILL.md`.
- Adapter pointer. The injected line in `poteto-mode/SKILL.md` was read first, and the document it names (`harness/pstack/skills-root/docs/harness/skills-root.md`) was reached and read.
- Capability probe. Shell ran read-only commands; `spawn_agent`, `apply_patch`, and web search are exposed in-session. None were exercised beyond the probe.

Not claimed: host-level skill invocation (the receipt read the SKILL.md as a file; no invocation surface ran), hook firing, and session-store parsing.
