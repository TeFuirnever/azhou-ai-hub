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

Verdict.

- Claimed: the ZCode plugin's command surface is user-invocable from a real GUI session — command recognized and body executed — at plugin `0.15.36` enabled, observed 2026-11-14.
- Not claimed: end-to-end pstack workflow invocation (the command's referenced skills are absent from every machine skill root, so the chain fails at the skill step exactly as the probe shows), SessionStart hook trust, `0.15.37` currency on ZCode, and any statement about other hosts.
- Restoring the 68 skills to a skill root is a pstack reconfiguration and requires its own explicit task under the pstack source and generation contract; until then the command surface resolves but each command's skill step fails as observed.
