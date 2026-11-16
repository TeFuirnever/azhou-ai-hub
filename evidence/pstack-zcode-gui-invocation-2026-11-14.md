# ZCode GUI command invocation receipt (2026-11-14)

Scope: the GUI-session invocation verdict left unclaimed by the [2026-11-03 plugin-fabric receipt](zcode-plugin-fabric-2026-11-03.md) ("Not claimed: GUI-session invocation of a command") and the read-only live run called for by the [2026-11-11 host inventory](pstack-host-readonly-inventory-2026-11-11.md). Everything below was observed on this host against the installed `pstack-azhouzhou@azhou-hub` plugin.

Machine state at receipt time.

- `~/.zcode/cli/plugins/installed_plugins.json` records `pstack-azhouzhou@azhou-hub` version `0.15.36`, user scope, installed 2026-11-03, install path `~/.zcode/cli/plugins/cache/azhou-hub/pstack-azhouzhou/0.15.36`; `~/.zcode/cli/config.json` marks the plugin enabled (`"pstack-azhouzhou@azhou-hub": true`).
- The cache holds 41 command markdown files (43 files total), matching the 2026-11-03 fabric receipt's count.
- `0.15.37` is not installed on ZCode; the candidate-currency question stays where the 2026-11-11 inventory left it.

GUI invocation probe.

- A fresh ZCode GUI session (session `sess_e1ef392a-915e-4146-bbc8-c717ed02e78d`, workspace `~/Desktop/oh-my-ai/azhou-ai-hub`) received exactly `/architect` as its first input on 2026-11-14; the session was archived after the reply was captured, before any further tool use.
- The command resolved and its body executed. The session's reply, verbatim: 「`/architect` 命令存在，但找不到名为 `architect` 的技能。让我检查一下该命令是在哪里定义的：」
- This is the first GUI-session evidence that the plugin's command surface resolves and runs in a real ZCode GUI workflow; the 2026-11-03 registration was CLI-verified only.

Skill-chain boundary (why the run stops at the command step).

- `commands/architect.md` reads "Invoke the `architect` skill and follow it." The 2026-11-03 receipt shipped the plugin with `skills: 0` because "ZCode already serves the 68 pstack skills from the shared user root"; the Hub source still holds those 68 skills at `packages/pstack-agent-harness/harness/pstack/skills-root/skills/` (re-counted 2026-11-14, `architect` among them).
- The shared root no longer carries them on this machine: `~/.agents/skills` holds no pstack skill directory (its 14 top-level symlinks are the super-*/novel-* families; no `architect`, `poteto-mode`, `babysit` or sibling names), `~/.zcode/skills` holds none, and no `architect` skill directory exists under `~/.agents` or `~/.zcode/skills`. The 2026-11-11 inventory had already marked "68 Skills discoverable at current installed bytes" UNVERIFIED with only HISTORICAL shared-root discovery behind it; this receipt upgrades that to a measured absence on 2026-11-14.
- The drift window is 2026-11-03 → 2026-11-11; the cause is not established by this receipt.

Restoration and post-restore probe (2026-11-14, same day).

- The [2026-11-04 retirement receipt](pstack-azhouzhou-retirement-2026-11-04.md) records the original install shape in its skills-root invariant: `~/.agents/skills` then held 164 entries with "the 68 skills-root-tree pstack skills all present" as plain-name links ("The links stay: they carry no plugin name"). The restoration reproduces exactly that shape.
- 66 of the 68 skill names were restored as top-level symlinks in `~/.agents/skills` pointing at the Hub source tree `packages/pstack-agent-harness/harness/pstack/skills-root/skills/<name>` in the maintainer checkout; all 66 resolve a `SKILL.md` (verified per link). Two names, `tdd` and `teach`, are occupied by other current installs and were ceded to them rather than overwritten.
- Tooling note for the record: a first `ln -s` pass hit the two occupied names and, because `ln -s` with an existing directory destination nests the link inside it, briefly created stray `tdd/tdd` and `teach/teach` entries; both were removed immediately after target verification and the two host skill directories were left with their pre-run contents.
- Post-restore probe: a fresh ZCode GUI session (`sess_0d4853e2-4a0b-4aac-9211-afd6d6f66260`, archived after capture) received exactly `/architect`, and this time the full chain engaged — command recognized, the `architect` skill loaded from the restored link, and the session answered inside the skill's own five-phase methodology (Ground→Sketch→Agree→Implement→Scrap), declining to start an exercise without a design target.

Verdict (after restoration).

- Claimed: the ZCode plugin command surface and its skill chain are user-invocable from a real GUI session at plugin `0.15.36` enabled — command recognized, referenced skill discovered through the shared root, and the skill's methodology driving the session — observed 2026-11-14.
- Not claimed: a complete read-only pstack task run in the GUI (the probe deliberately stopped before any exercise; the 2026-11-11 inventory's item-64 capture list remains the bar), SessionStart hook trust, `0.15.37` currency on ZCode, and any statement about other hosts.
- The links live in the maintainer checkout's canonical tree and carry no plugin name; they are the pstack skills install, not cleanup residue — the 2026-11-03 → 2026-11-11 disappearance recorded above is the cautionary precedent.
