# Lane-4 mandate copy fix receipt (2026-11-05)

Scope: the one open finding from the AZ1 verification lanes ([az1-verify receipt](az1-verify-2026-11-04.md)), fixed at head `caa51d9` in worktree `codex/pstack-mandate-copy-fix-20261105`. The rename reached the plugin identity but not the Hub-owned hook payload surfaces under `hub-runtime/hooks/`, which the build copies verbatim into all four trees (`build-harness.mjs`, `HOOKS`). No quilt patch: `hub-runtime` is Hub-owned hand-written surface; no patch in the queue touches it.

Fix surface, one sweep class, each file measured before and after.

- `session-start-context.md`: the identity line "You have pstack." and the seven invocation routes `pstack:X` renamed to `pstack-azhouzhou:X`.
- `session-start-muse.md`: the `plugin:pstack:X` forms renamed likewise.
- `session-start-copilot.md`, surfaced by the residual sweep during this fix: the "not `pstack:poteto-mode`" contrast example and the two agent prefixes `pstack:poteto-agent`, `pstack:comment-sicko` renamed. The `pstack-models.md` sheet path keeps its name, it is a file, not a namespace.
- `pre-tool-use.awk` `task_rule`, surfaced by the same sweep: its guard `index(type, "pstack:")` no longer matched the renamed agent types, so the model-sheet enforcement would have silently stopped applying to plugin agents. The guard now matches `pstack-azhouzhou:`.

Red-green.

- Red, before the fix at `caa51d9`: a fresh `claude -p` probe quotes the mandate routing as `pstack:poteto-mode`, `pstack:tdd` (az1-verify lane 4).
- Green, after the fix installed through a marketplace swap to this worktree's built tree: a fresh probe quotes `You have pstack-azhouzhou.` and `pstack-azhouzhou:poteto-mode`, `pstack-azhouzhou:tdd`, `pstack-azhouzhou:architect`, `pstack-azhouzhou:how`, `pstack-azhouzhou:why`, `pstack-azhouzhou:arena`, `pstack-azhouzhou:interrogate`.
- Measurement note: `claude plugin marketplace remove` uninstalls the plugin with its marketplace, learned during restore. The marketplace source is back on the maintainer folder; the installed copy returns from the rebuilt maintainer tree at landing closeout in the same session, byte-identical by the proven deterministic build.

Observed, recorded, not fixed here. The old namespace survives far beyond the hooks, measured by a package-wide sweep for `pstack:` minus `pstack-azhouzhou:`.

- Upstream files under `pstack/`, quilt territory: the README, the poteto-help SKILL, `docs/guide/01-setup.md`, the `docs/harness/claude-code.md` adapter table and its agent rows — including poteto-mode's `subagent_type: "pstack:poteto-agent"` defaults, which dispatch a nonexistent agent type under the renamed plugin.
- Hub-owned: the `hub-adapters/codex.md` and `hub-adapters/zcode.md` rows instructing users to write `/pstack:<name>`; `hub-skills/setup-pstack/copilot.md`; `hub-skills/poteto-mode/references/copilot-tools.md` agent lists.
- A full sweep is its own unit: quilt patches for the upstream files, direct edits for the hub files, rebuild, reinstall, re-lane. This receipt fixes the commissioned hook surface only.

Not claimed. The `task_rule` guard change is sweep-proven, not live-probed; a live probe needs a model-dispatched plugin agent with an explicit model. GUI mandate delivery stays with the operator's live session. The wider sweep above is measured, not remediated.
