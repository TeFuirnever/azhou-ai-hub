# DeepSeek Harness shared-root skill discovery receipt (2026-11-02)

Scope: stage-1 experimental receipt for DeepSeek Harness desktop (`com.deepseek.dsh` 0.2.1-rc.5, Electron) discovering pstack skills from the shared user root `~/.agents/skills`. One real desktop session ran the receipt prompt (session model glm-5.3-flash, shell available). The probe session was read-only and modified nothing under `~/.dsh`, `~/.agents`, or the repository.

Findings:

- Discovery. 164 visible entries at `~/.agents/skills` (77 symlinks, 86 directories, 1 file), matching the expected count. 68 pstack skills detected by the deterministic criterion (link target contains `harness/pstack/skills-root/skills`); all 68 resolve with a readable `SKILL.md`, zero broken links.
- Source attribution. All 68 pstack skills resolve through the user root, `user-agents` in DSH's provider ranking (rank 500, per the 2026-11-02 asar source reading of `@deepseek-ai/dsh-skill-filesystem`). The repository checkout's git-ignored project `.agents/skills` contributed 0 pstack hits.
- Adapter pointer. poteto-mode `SKILL.md` line 11 carries the injected adapter line verbatim; the relative link resolves to `harness/pstack/skills-root/docs/harness/skills-root.md` (74 lines) and was read in-session.
- Capability probe. Engine 0.2.1-rc.5; shell available (`Darwin arm64`); `DSH_HOME=/Users/guanxueliang/.dsh` set with `DSH_PROFILE=desktop`; `DSH_AGENTS_HOME` unset and defaulting to `~/.agents` (runtime plus adapter-doc evidence; source-level confirmation inside the probe skipped because DSH ships as one `app.asar`). Dispatch surfaces present: `subagent`, `subagent_fork`, `spawn_teammate`, `workflow`. No model-list surface exposed in-session.
- Cross-checks. Total 164 and pstack 68 match independent measurements taken by the preparing Claude Code session before the probe ran.

Not claimed: host-level explicit skill invocation was not exercised (the receipt read the SKILL.md as a file; no invocation surface ran). Hook surface, session-store parsing, and model quality remain unclaimed. pstack skills carrying `disable-model-invocation: true` were absent from the session's model-invocable directory, consistent with the flag; user-invocation visibility is unverified.

Open follow-up: the stale `~/.agents/skills/SOURCES.md` manifest (self-recorded 161 entries, 65 pstack links, dated 2026-10-25) belongs to the azhou installer flow and was left untouched by the read-only probe.
