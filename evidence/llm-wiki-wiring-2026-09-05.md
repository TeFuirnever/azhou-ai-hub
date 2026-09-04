# LLM Wiki codex wiring and live session-start receipt — 2026-09-05

This receipt records a redacted real-host check that the Codex CLI host, after an explicit host-local wiring of the three-event `llm-wiki` lifecycle adapter, fires the wired SessionStart hook live and delivers the wiki context injection into the model session. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Adapter: canonical `skills/llm-wiki/scripts/llm_wiki_adapter.py` at local default-branch commit `8bb83c9` (includes the matcher-validity fix from #121 and the session-end budget fix from #122)
- Host: macOS arm64, Codex CLI `codex-cli 0.152.0`; user-scope hook registration in `~/.codex/hooks.json` produced by the adapter's documented `render-hooks` output merged explicitly by the workspace owner (the adapter never mutates host config by design), with the three owned definitions confirmed through the host's `/hooks` per-definition trust flow
- Probe store: a disposable Git-initialized project directory with a freshly initialized private wiki store under the project's `.azhou/llm-wiki/` namespace and one reference page carrying a unique probe marker

## Results

| Check | Result | Evidence |
|---|---|---|
| Wiring loads cleanly | `PASS` | After correcting two renderer defects (below), the host loads the source with no hook-loading issue at startup. Before the fixes it reported a loading issue caused by an invalid `"*"` matcher and logged a clamp for the out-of-budget SessionEnd timeout; both were fixed in #121 and #122 and the symptoms disappeared on the host. |
| SessionStart fires live with context injection | `PASS` | In a real headless session, the model quoted the injected wiki context verbatim — the first line `[LLM Wiki: 1 pages at .azhou/llm-wiki/]` and the page's unique probe marker — proving the wired hook ran, resolved the project store, and delivered the injection. |
| PreCompact / SessionEnd command contract | `PASS` | Each wired command was exercised at the wired-command contract with a bounded event payload: exit 0 and valid hook-output JSON for both (no-op on an empty store, as designed). Real-host firing of these two events additionally requires a context compaction / session archival to occur naturally and remains unclaimed. |
| Empty-store behavior | `PASS` | With no wiki store in the project, the SessionStart command exits 0 and emits a silent no-op hook output (fail-open), matching the adapter's neutral-core contract. |

## Renderer defects fixed on the way (PRs #121, #122)

1. `render-hooks` emitted `"matcher": "*"` — invalid as a regular expression; the host reported `1 issue loading hooks for this source`. Fixed to `".*"` with a regression test pinning all three matchers as compilable regular expressions.
2. `render-hooks` requested a 30-second SessionEnd timeout — beyond the ~3-second session-end budget hosts enforce; the host logged a clamp at load time. Fixed to 3 seconds with a regression test pinning the budget.

## Claim boundary

This proves the Codex CLI 0.152.0 host fires the wired llm-wiki SessionStart hook live on this machine, with end-to-end context injection verified by verbatim model recall, and that the three wired commands satisfy their contract. It does not claim real-host firing of PreCompact or SessionEnd (their triggers did not occur naturally during the receipt window), behavior on other Codex versions or surfaces, or cross-host parity. The wiring stays host-local by design; raw probe artifacts stay Git-external; nothing private is committed.
