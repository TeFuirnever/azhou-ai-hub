# Three-face surface audit receipt (2026-11-04)

Scope: one cross-host check of the three distribution faces — skills, named subagents, hooks — over the pstack-azhouzhou program targets, measured on the maintainer's Mac at head `ab21b14`. The finding: only Claude Code carries all three faces. Every gap below is a contract boundary with a recorded revisit trigger, not an implementation omission. This feeds the "You see" surfaces of AZ1, AZ3, and AZ4 in `docs/design/pstack-plugin-fabric/plan.md` and ticks no plan box.

Face matrix, each cell from a command line in this session or a linked receipt.

| Face | Claude Code | ZCode | DeepSeek Harness |
|---|---|---|---|
| Skills | 68, plugin namespace | 68, shared root `~/.agents/skills` | 68, shared root |
| Named subagents | 4, registered | none — outside the manifest contract | none — no carrier field |
| Hooks | 1 SessionStart | none from the plugin — declaration unproven | none — no contract field |

Claude Code, all three faces live.

- `claude plugin details pstack-azhouzhou@pstack-claude` reports 68 Skills, 4 Agents — poteto-agent, comment-sicko, thermo-nuclear-review-subagent, thermo-nuclear-code-quality-review-subagent — and 1 Hook, SessionStart, harness-only, with 0 MCP and 0 LSP servers.
- The plugin cache at `~/.claude/plugins/cache/pstack-claude/` holds only `pstack-azhouzhou/`.
- The operator's live Claude session shows the same three faces working, stated in the audit request: its delegation roster is the four registered agents, and the SessionStart mandate block is that session's opening injection.

ZCode, one proven face, two bounded.

- The fabricated bundle at `packages/pstack-agent-harness/harness/pstack/zcode-plugin` declares exactly one capability pointer, `"commands": "commands"` in `.zcode-plugin/plugin.json`, with 41 command files in a flat layout.
- The registration is live: `~/.zcode/cli/plugins/installed_plugins.json` carries `pstack-azhouzhou@azhou-hub` 0.15.36 with its cache path, and `cache/azhou-hub/pstack-azhouzhou/0.15.36/commands` holds 41 files. `/architect` resolution through `commands list` is CLI-proven in the [fabric receipt](zcode-plugin-fabric-2026-11-03.md).
- Skills ship as 0 by design: ZCode serves the 68 pstack skills from the shared root, 164 entries at audit time, so the plugin adds no second source.
- The hooks omission is deliberate and recorded in the fabric receipt: no plugin-manifest `hooks` sample exists in the official cache. The boundary is narrower than "zcode has no hooks" — zcode itself has a proven host-config hooks surface where SessionStart fires in the GUI host at user scope ([hook surface receipt](zcode-hook-surface-2026-09-04.md)). What is unproven is the plugin-manifest declaration, and a config-level hook would live outside the plugin's lifecycle. The revisit trigger stays: an official sample reopens the emitter.

DeepSeek Harness, one face, no plugin carrier.

- Skills arrive through shared-root discovery only, 68 of 68 resolvable ([discovery receipt](deepseek-skill-discovery-2026-11-02.md)).
- The bundle contract decodes to cordis patch layers with icon and locale metadata and carries no field for skills, slash commands, or hooks — the command face does not exist there. The emitter is parked with that measured reason ([decoded-contract receipt](dsh-plugin-fabric-2026-11-03.md)); the contract growing a registration field reopens AZ4.

Boundary notes.

- The hooks face, for this program, means automatic SessionStart injection of the poteto mandate. Without it, skills still fire by explicit invocation; the mandate does not ride automatically.
- The subagent face as named-agent registration is a Claude plugin form. The ChatGPT desktop Codex plugin form ships skills, hooks, and prompts, 41 prompt files beside a 68-skill tree, and no agent registration ([install receipt](chatgpt-desktop-native-plugin-install-2026-11-04.md)). Delegation on other hosts is skill-level guidance over the host's own spawn mechanism, not a registration capability, so subagent adaptation off Claude is skill-layer guidance, not a missing registry entry.

Not claimed. No ZCode GUI session was driven in this audit — its command surface is CLI- and registry-verified only, and GUI invocation stays with AZ3's live lanes. No DSH session was driven. The Codex hooks face is shipped but its delivery awaits the host's `/hooks` trust decision per the install receipt. No plan checkbox moved: each stage keeps its own boxes. The Claude inventory was measured once, on this machine, on 2026-11-04.
