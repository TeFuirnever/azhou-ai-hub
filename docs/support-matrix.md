# Support matrix

“Portable package” does not mean every harness exposes identical lifecycle hooks or memory APIs. This matrix separates the shared skill from host integrations.

| Capability | Codex | Claude Code | zcode | Other compatible harnesses |
|---|---|---|---|---|
| Load canonical <code>SKILL.md</code> package | supported by a configured skill root | supported by a configured skill root | host-dependent; verify installation | host-dependent |
| Azhou Info / Doctor / Setup / Verify Agent Skills | supported from a configured skill root with an explicit checkout; Codex invocation uses its native Skill surface | same neutral packages from a configured skill root; Claude invocation uses its native Skill surface | host-dependent; verify discovery, invocation and tools | expected only for Agent Skills-compatible hosts with Python and checkout access |
| Foundation `info` / `version` / `doctor` / `setup` / `verify` CLI | supported from a checkout with Python 3.11+ and an explicit skill root for setup | same neutral checkout CLI | same neutral checkout CLI when Python and a writable skill root exist | Python 3.11+; harness skill root must be supplied explicitly |
| Managed checkout `repair` / same-target `migrate` / `uninstall` | supported only for a single artifact installed with an explicit Foundation receipt | same neutral checkout lifecycle | same when Python and the explicit target are available | harness-neutral filesystem contract; activation is not claimed |
| Repo Pedant manual invocation | supported | supported | supported when the host loads the package | expected when Agent Skills are supported |
| Repo Pedant history collection | Codex JSONL parser implemented | Claude session parser implemented | zcode session parser implemented | not claimed |
| Stop/PreCompact integration | advisory only; no hard-block claim | optional explicit gate with recursion/progress caps | no proven hook contract | no claim without a tested adapter |
| Project memory reconciliation | only for a path/resource proven to belong to the project | only for a path/resource proven to belong to the project | only for a path/resource proven to belong to the project | host discovery required |
| Excalidraw local file generation | supported with filesystem tools | supported with filesystem tools | supported with filesystem tools | requires local file access |
| Excalidraw offline render/export | supported after package dependencies | supported after package dependencies | supported after package dependencies | Python/Node/Chromium required |
| Interactive MCP preview | optional, host/tool-specific | optional, host/tool-specific | not claimed | not claimed |
| Lavish local HTML generation | supported with filesystem tools | supported with filesystem tools | supported with filesystem tools | requires local file access |
| Lavish browser review and foreground polling | supported with Node.js 22+, a local browser and attached command execution | supported with Node.js 22+, a local browser and attached command execution | host-dependent; verify browser and foreground command lifecycle | host-dependent |
| Lavish standalone export | supported through locked CLI after dependency resolution | supported through locked CLI after dependency resolution | host-dependent | Node.js 22+ and local file access required |
| Lavish third-party share | available only after explicit publication authorization and network verification | same boundary | same boundary | no claim without tested network and receipt |
| LLM Wiki manual operations | supported with Python 3.11+ and local file access | supported with Python 3.11+ and local file access | supported when the host loads the skill and permits local execution | Python 3.11+ and local file access required |
| LLM Wiki legacy <code>.omc/wiki/</code> store | supported through explicit <code>--store</code> selection | supported through explicit <code>--store</code> selection | same neutral core; host lifecycle not implied | same neutral core |
| LLM Wiki lifecycle adapter | neutral stdin/stdout adapter implemented; host wiring not claimed | neutral adapter implemented; hook configuration remains explicit | no proven hook contract | no claim without a tested adapter |
| LLM Wiki session metadata capture | opt-in; disabled by default | opt-in; disabled by default | host-dependent | no transcript capture claim |
| Super Caveman complete pinned ADHD-friendly response behavior, commit, review and help routes | current 19/19-case and 44/44-criterion behavior run plus 3/3 independent paired-judge candidate result and zero high-risk regressions; harness/model-specific | contract defined; equivalent behavior and promotion evidence required | host-dependent; no behavior evidence | host-dependent; no behavior evidence |
| Super Caveman compact delegation | supported through available collaboration tools | supported through available subagents | host-dependent; named presets not claimed | host-dependent |
| Super Caveman guarded file compression | supported with Python 3.10+ and local file access | supported with Python 3.10+ and local file access | same neutral core | Python 3.10+ and local file access required |
| Super Caveman lifecycle adapter | explicit local setup required. One bounded full-mode `SessionStart` adapter has deterministic configuration and JSON-protocol coverage; Codex trust review and real-host smoke remain separate gates | roadmap only; no shipped adapter | not claimed | no claim without a tested adapter |
| Super Caveman exact session statistics | host counters only; no bundled log scanner | host counters or separately reviewed compatible adapter | not claimed | unavailable without audited counters or parser |

## Meaning of “supported”

- **Supported**: implemented in the repository and covered by deterministic checks or a documented real adapter.
- **Host-dependent**: the runtime package is neutral, but the harness installation or tool surface must be verified.
- **Not claimed**: no audited implementation exists. It is not silently treated as equivalent.

Model quality is not a support claim. Benchmark comparisons must freeze the prompt, runtime package digest, time limit and tool permissions, then record attempt-1 evidence.

Open a [bug report](https://github.com/TeFuirnever/azhou-ai-hub/issues/new?template=bug.yml) when an entry is stale. Include the harness version, skill commit and a redacted reproduction.
