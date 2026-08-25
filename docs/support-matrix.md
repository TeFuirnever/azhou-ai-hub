# Support matrix

“Portable package” does not mean every harness exposes identical lifecycle hooks or memory APIs. This matrix separates the shared skill from host integrations.

| Capability | Codex | Claude Code | zcode | Other compatible harnesses |
|---|---|---|---|---|
| Load canonical <code>SKILL.md</code> package | supported by a configured skill root | supported by a configured skill root | host-dependent; verify installation | host-dependent |
| Foundation `info` / `version` / `doctor` / `setup` / `verify` CLI | supported from a checkout with Python 3.11+ and an explicit skill root for setup | same neutral checkout CLI | same neutral checkout CLI when Python and a writable skill root exist | Python 3.11+; harness skill root must be supplied explicitly |
| Managed checkout `repair` / same-target `migrate` / `uninstall` | supported only for a single artifact installed with an explicit Foundation receipt | same neutral checkout lifecycle | same when Python and the explicit target are available | harness-neutral filesystem contract; activation is not claimed |
| Repo Pedant manual invocation | supported | supported | supported when the host loads the package | expected when Agent Skills are supported |
| Repo Pedant history collection | Codex JSONL parser implemented | Claude session parser implemented | zcode session parser implemented | not claimed |
| Stop/PreCompact integration | advisory only; no hard-block claim | optional explicit gate with recursion/progress caps | no proven hook contract | no claim without a tested adapter |
| Project memory reconciliation | only for a path/resource proven to belong to the project | only for a path/resource proven to belong to the project | only for a path/resource proven to belong to the project | host discovery required |
| Excalidraw local file generation | supported with filesystem tools | supported with filesystem tools | supported with filesystem tools | requires local file access |
| Excalidraw offline render/export | supported after package dependencies | supported after package dependencies | supported after package dependencies | Python/Node/Chromium required |
| Interactive MCP preview | optional, host/tool-specific | optional, host/tool-specific | not claimed | not claimed |

## Meaning of “supported”

- **Supported**: implemented in the repository and covered by deterministic checks or a documented real adapter.
- **Host-dependent**: the runtime package is neutral, but the harness installation or tool surface must be verified.
- **Not claimed**: no audited implementation exists. It is not silently treated as equivalent.

Model quality is not a support claim. Benchmark comparisons must freeze the prompt, runtime package digest, time limit and tool permissions, then record attempt-1 evidence.

Open a [bug report](https://github.com/TeFuirnever/azhou-ai-hub/issues/new?template=bug.yml) when an entry is stale. Include the harness version, skill commit and a redacted reproduction.
