# LLM Wiki stdio MCP transport receipt — Claude Code + zcode — 2026-09-01

This receipt records a redacted real-host check that the bundled `scripts/llm_wiki_mcp.py` stdio server is loaded by both available hosts and executes real store tool calls against the canonical `<project>/.azhou/llm-wiki/` store. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `85447284c8953e7f1797b46146ad80e247b1d518` (merged `main`; disposable Git worktree of that commit)
- Host: macOS 26.6.2, arm64; Python 3.14.7
- Host: Claude Code `2.1.239` local CLI (user-scope MCP registration)
- Host: zcode headless CLI `0.16.5` (run via the ZCode.app 3.10.2 bundle), Node.js 24.15.0
- Mode: real host MCP configuration outside Git + headless non-interactive model runs (`claude -p`, `zcode -p`), attempt-1 per run

## Host configuration (kept outside Git; host-local)

The adapter's `render-mcp` output was merged into each host's own MCP configuration outside the repository:

- Claude Code: `claude mcp add --scope user llm-wiki -- <python3.14> <checkout>/skills/llm-wiki/scripts/llm_wiki_mcp.py`. `claude mcp list` reported the server as connected before the run.
- zcode: the `llm-wiki` stdio entry (same `command` + `args` shape as the renderer output, plus `timeoutMs: 60000`) was added under `mcp.servers` in the zcode CLI configuration file at the CLI's config path (redacted in Git; before/after redacted diff recorded Git-external).
- A scratch project root outside Git was initialized with `llm_wiki.py --root <scratch> init`; the store contains only these receipt pages.

## Results

| Check | Host | Result | Evidence |
|---|---|---|---|
| MCP registration loads server | Claude Code | `PASS` | `claude mcp list` shows `llm-wiki: ... ✔ Connected`. |
| MCP registration loads server | zcode | `PASS` | Post-run model I/O rollout (Git-external) lists the seven `mcp__llm-wiki__wiki_*` tool definitions; `finishReason: "tool-calls"` on the first model response. |
| Real read tool call | Claude Code | `PASS` | Headless `claude -p` run (session recorded Git-external) called `wiki_list`; model reply quoted the rendered index header `0 pages`. Store was empty by design before the write check. |
| Real write tool call | Claude Code | `PASS` | Same run series called `wiki_ingest` (title `MCP transport receipt`, source `evidence-slice2`); tool receipt returned `created: [mcp-transport-receipt.md]`, `total_affected: 1`. |
| Real write tool call | zcode | `PASS` | Headless `zcode -p` run (model `glm-5.1`) called `wiki_ingest` (title `zcode MCP transport receipt`, source `evidence-slice2-zcode`); reply reported `Created: zcode-mcp-transport-receipt.md`, `Total affected: 1`. |
| Neutral CLI cross-check | both | `PASS` | `llm_wiki.py --root <scratch> list` (neutral CLI, no MCP) returns both pages `mcp-transport-receipt.md` and `zcode-mcp-transport-receipt.md`, status `pass`. The MCP writes are visible to the neutral core, so the transport runs did hit the canonical store. |

## zcode configuration-location finding

zcode CLI `0.16.5` does not read `~/.zcode/mcp.json` for its MCP servers (that file is read by a different surface). The CLI reads MCP servers from `mcp.servers` inside the CLI configuration (`~/.zcode/cli/config.json`). First attempt with an entry only in `~/.zcode/mcp.json` produced a run whose tool list contained no `llm-wiki` tools (rollout shows only unrelated MCP tool names); the run was voided and the entry moved to the CLI configuration. This location is recorded here so future receipts re-point at the working location; the redacted before/after diff is Git-external.

## Reproduction

1. Check out the recorded commit into a disposable worktree.
2. Initialize a scratch store: `python3 <checkout>/skills/llm-wiki/scripts/llm_wiki.py --root <scratch-project> init`.
3. Render the MCP fragment: `python3 <checkout>/skills/llm-wiki/scripts/llm_wiki_adapter.py render-mcp --skill-dir <checkout>/skills/llm-wiki --python <python3>`.
4. Register the emitted `llm-wiki` stdio entry in the Claude Code user scope (`claude mcp add --scope user`) and in the zcode CLI `mcp.servers` configuration.
5. Run `claude -p` and `zcode -p` prompts that call `wiki_list` and `wiki_ingest`; confirm `wiki_ingest` reports one created page.
6. Cross-check with the neutral CLI `list` that both receipt pages exist.

## Claim boundary

This proves the bundled stdio MCP server is transport-verified on Claude Code 2.1.239 and zcode 0.16.5 on this machine, with real store reads and writes confirmed by the neutral CLI. It does not prove GUI-surface MCP behavior, any other host, or cross-host parity. Raw transcripts and host configuration stay Git-external; nothing private is committed.