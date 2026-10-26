# Harness support and extension boundaries

Evidence checked on 2026-10-25 (Asia/Shanghai). Product identity and a documented native delegation mechanism are prerequisites for any future adapter; Skill, Markdown, or MCP support alone is insufficient.

2026-10-26 scope update: the user identified the previously unresolved “MiniCode” name as MiMo Code (`mimo`) and selected it as a maintained Hub Skill target. That does not add a native Agent Orchestration Kit adapter. The row below remains a dated record of what was known on 2026-10-25.

## Current support

| Harness | Identity / version evidence | Status in this kit |
|---|---|---|
| Codex | Local ChatGPT App bundle `com.openai.codex`, App 26.1021.31345; bundled CLI `0.164.0-alpha.11.1`. PATH CLI `0.160.1` is a separate installation. | Implemented and accepted on this Mac, using the bundled runtime. |
| ZCode | [`zai-org/ZCode`](https://github.com/zai-org/ZCode); the local `/Applications/ZCode.app/Contents/Info.plist` reports bundle `dev.zcode.app`, version 3.16.3 (build 3.16.3.8992); current public source [`package.json`](https://github.com/zai-org/ZCode/blob/main/package.json) says 3.16.2. The [GitHub Releases page](https://github.com/zai-org/ZCode/releases) separately marks v3.14.3 as Latest. | Future plan; no adapter or installed configuration in this round. Source version, release-page version, and local installed version are distinct facts. |
| Claude Code | Official [subagent documentation](https://code.claude.com/docs/en/sub-agents); official [release list](https://github.com/anthropics/claude-code/releases) showed v2.1.310 at final lookup (2026-10-23 release). | Future plan; no adapter or local runtime acceptance. |
| MiniCode | No exact official project/repository identified by the user. | Identity and mechanism unconfirmed. No assumed path, schema, or capability. |

## Native mechanisms that matter

**Codex.** Standalone TOML roles live in `CODEX_HOME/agents`; `name` determines identity. User model defaults and `[agents]` settings live in `config.toml`. Personal Skills are discovered under `~/.agents/skills`. Project/session overrides remain possible. Roles inherit parent permissions; role-local `sandbox_mode` does not establish isolation. Model identifiers and service-tier values in the balanced profile are Codex-specific. See [official subagents](https://developers.openai.com/codex/subagents) and [Skills](https://developers.openai.com/codex/skills).

**ZCode.** The official [subagent guide](https://zcode.z.ai/en/docs/subagents) documents native delegation through the Agent tool and user-level custom agents in Beta. Definitions use Markdown/frontmatter under `~/.zcode/agents`; the role can choose model, `thoughtLevel`, tools, and instructions. Changes generally need a new session. The documented restrictions include no child-of-child delegation and user-level-only creation in Settings. These live documentation claims do not demonstrate that the installed local version supports every field.

**Claude Code.** Its official guide defines Markdown/YAML roles with project/user scopes, `name`/`description`, model and tool settings, and permission-mode rules. Parent policy can override requested subagent permissions. File discovery, role precedence, invocation, and permissions differ from Codex. A future implementation must validate the chosen Claude Code release directly rather than translating Codex TOML mechanically.

## What can be reused

The reusable material is the human-readable role purpose, bounded task contract, concise handoff, explicit file ownership, escalation criteria, and requirement for independent execution evidence. The current Skill records these rules for Codex. This round does not extract a new configuration language or duplicate them into an abstract runtime.

A future integration needs only the following work when that harness is actually selected:

1. Confirm the exact product, installed version, and supported native delegation interface.
2. Map responsibilities into that version's role format, model/effort vocabulary, and native tool/permission controls.
3. Implement a scoped installer with its own target ownership and failure handling.
4. Prove discovery, role invocation, actual model selection, and permission behavior using that host's native records.

No plugin registry, unified scheduler, common process manager, automatic budget system, or cross-harness dispatch layer is included. The current `scripts/install_codex.py`, `scripts/codex_native.py`, and `profiles/*/codex/` explicitly belong to Codex. Retaining these names makes the boundary visible without introducing unused adapters.
