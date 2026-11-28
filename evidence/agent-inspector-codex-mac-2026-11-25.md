# Azhou Agent Inspector on Codex for Mac

This historical record reproduces the 0.1.0 handoff, not the current installation. During the 2026-11-28 reconciliation, the five recorded file hashes matched the cited Git revision; the original raw host-install logs were not found in the retained worktree, so the historical installation observations were not independently repeated. Later releases and native acceptance are recorded in the [support matrix](../docs/support-matrix.md#azhou-agent-workbench).

Observed on the maintainer's Apple silicon Mac on 2026-11-25 (Asia/Shanghai). ChatGPT Desktop reported `26.1120.50957` (build `30866`). Its bundled Codex CLI was `0.171.0-alpha.13.2` and used the default `~/.codex` home.

## Native update

- The maintainer checkout fast-forwarded to `857b779132ee80ea616f1bb9a0ee034d837ec212` with tree `690ac30b50981b1d24618d2d299d2aa606720b0f`. The Codex installation plan computed runtime fingerprint `887c737ef9713a64076f9ede38cb95f66f47b1c9d212a9845c8421fb272e3d07`. [Merged sidebar change](https://github.com/TeFuirnever/azhou-ai-hub/pull/583)
- The CLI rejected adding the same marketplace name from a different path. Its native manager removed the prior registration, added `<repo>/packages/azhou-agent-inspector` as `azhou-agent-tools` and added `azhou-agent-inspector@azhou-agent-tools` at `0.1.0`. The plugin is enabled in `~/.codex/config.toml`. The before and after marketplace listings show only the Inspector source path changed.
- Codex installed into `~/.codex/plugins/cache/azhou-agent-tools/azhou-agent-inspector/0.1.0`. The following SHA-256 digests matched the checkout. The previous local marketplace source was retained for rollback.

| Installed file | SHA-256 |
|---|---|
| `panel.html` | `f859bf0a33e954760fa3dca8d1238b596524c55ff8b9e1f34822bd585c91028a` |
| `server.py` | `0629c293f9c965114efc9a9f185211b91338b49074c5f54274314cc6faa10975` |
| `azhou.webp` | `144eb9abe568a3d8fa1f2d582db7f44bd42ace8ca37a135ced436ab887ff33c2` |
| `wallpaper.webp` | `4b9766e1bc8d9dbfd9fdca02bbd46db260d2a5e2f0481bc20b5b707dc38eb58d` |
| `.codex-plugin/plugin.json` | `51ad38b7868d4496bedad53020abcd5cbcf64d134e52a76d31d0f5fc8d7e85d6` |

The rollback path was recorded for this 0.1.0 update. Later installations have their own native-manager receipts and retained cache payloads; use the receipt for the version being restored rather than replaying this historical procedure.

## Acceptance

| Surface | Observation |
|---|---|
| Installed MCP App resource | The installed server returned 92,100 bytes with the portrait and wallpaper embedded as WebP. Both resource placeholders were resolved. |
| Desktop plugin discovery | The maintainer's screenshot shows 阿舟 Agent 透视台 in Sources → Use plugins. |
| Active Codex session | The mounted `session_performance` tool returned `running` for the handoff session. This establishes live tool invocation. The graphical panel and its loaded page revision still need observation. |
| Real completed turns | The installed MCP handler matched two real local sessions in A, B and A order. An independent reading of the completed turns matched duration, whole-turn throughput, first-token wait, cache hit, output tokens and response count. The observations used read-only local records and kept raw data out of the receipt. |
| Isolated Mac App Server | The bundled CLI used a disposable home and routed synthetic counters to A, B and A without model calls. |
| Chrome with simulated bridges | Both views passed. The Codex view exercised portrait and wallpaper loading, refresh success and failure, rejection of a stale refresh response after a session change, missing and zero values, and overflow checks at 240, 280, 320 and 684 pixels at 100% and 200% root font sizes. |
| Package tests | 43 Node tests and 4 Python tests passed. |
| Real Codex sidebar | Pending. Desktop automation denied access to the ChatGPT window. The two artwork assets, completed and empty turns, refresh, session switching, width, theme, font size, and close/reopen need direct observation. |

The original handoff stated that raw install and verification outputs stayed in ignored local evidence; their location was not confirmed during reconciliation.
