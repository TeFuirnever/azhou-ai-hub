# Support matrix

“Portable package” does not mean every harness exposes identical lifecycle hooks or memory APIs. This matrix separates the shared skill from host integrations.

| Capability | Codex | Claude Code | zcode | Other compatible harnesses |
|---|---|---|---|---|
| Neutral package availability (repository surface) | ten canonical packages present and independently installable | same neutral package set | same repository package set | package availability is a repository fact; host install is not implied |
| Load canonical <code>SKILL.md</code> package | supported by a configured skill root | supported by a configured skill root | host-dependent; verify installation | host-dependent |
| Azhou Info / Doctor / Setup / Verify Agent Skills | package available; Codex discovery/invocation is locally smoke-tested | package available; Claude discovery/invocation requires a fresh host receipt | package available; discovery/invocation not evidenced here | expected only for Agent Skills-compatible hosts with Python and checkout access; verify locally |
| Foundation `info` / `version` / `doctor` / `setup` / public `verify` CLI | supported from a checkout with Python 3.11+ and an explicit skill root for setup | same neutral checkout CLI | same neutral checkout CLI when Python and a writable skill root exist | public verify needs no private evidence but still replays the approved exact diff; `--promotion-evidence` additionally authenticates two Git-external records |
| Managed checkout `repair` / same-target `migrate` / `uninstall` | supported only for a single artifact installed with an explicit Foundation receipt | same neutral checkout lifecycle | same when Python and the explicit target are available | harness-neutral filesystem contract; activation is not claimed |
| Azhou runtime-state namespace | project state uses <code>.azhou/&lt;skill-name&gt;/</code>; hub receipts use <code>.azhou/hub/</code> | same neutral filesystem contract | same when local execution is permitted | host-owned state and user deliverables remain outside this namespace |
| Managed receipt namespace migration | explicit dry-run, reviewed plan id, identity validation, atomic publish and source preservation | same neutral checkout CLI | same when Python and the explicit target are available | no fallback read, dual-write or automatic cleanup |
| Repo Pedant manual invocation | supported | supported | supported when the host loads the package | expected when Agent Skills are supported |
| Repo Pedant runtime state | <code>.azhou/repo-pedant/</code> for inventory, execution, closeout and evolution | same neutral core | same when local execution is permitted | explicit migration preserves the prior source |
| Repo Pedant history collection | Codex JSONL parser implemented | Claude session parser implemented | zcode session parser implemented | not claimed |
| Stop/PreCompact integration | advisory only; no hard-block claim | optional explicit gate with recursion/progress caps | no proven hook contract | no claim without a tested adapter |
| Project memory reconciliation | only for a path/resource proven to belong to the project | only for a path/resource proven to belong to the project | only for a path/resource proven to belong to the project | host discovery required |
| Excalidraw local file generation | supported with filesystem tools | supported with filesystem tools | supported with filesystem tools | requires local file access |
| Excalidraw offline render/export | supported after package dependencies | supported after package dependencies | supported after package dependencies | Python/Node/Chromium required |
| Interactive MCP preview | optional, host/tool-specific | optional, host/tool-specific | not claimed | not claimed |
| LLM Wiki manual operations | supported with Python 3.11+ and local file access | supported with Python 3.11+ and local file access | supported when the host loads the skill and permits local execution | Python 3.11+ and local file access required |
| LLM Wiki canonical <code>.azhou/llm-wiki/</code> store | supported | supported | supported when local execution is permitted | Python 3.11+ and local file access required |
| LLM Wiki stdio MCP | bundled server; explicit host configuration required | bundled server; explicit host configuration required | MCP transport must be verified | compatible MCP host and local Python execution required |
| LLM Wiki lifecycle adapter | three-event adapter implemented; explicit wiring required | three-event adapter implemented; explicit wiring required | event contract must be verified | no claim without a tested adapter |
| LLM Wiki project context refresh | reviewed local context file supported | reviewed local context file supported | host-independent filesystem behavior | no implicit host-memory claim |
| LLM Wiki session metadata capture | opt-in; disabled by default | opt-in; disabled by default | host-dependent | no transcript capture claim |
| LLM Wiki store migration | dry-run, atomic publish, source preservation and conflict rejection | same neutral core | same neutral core | local filesystem required |
| LLM Wiki branded interaction | fixed Azhou anchors and receipt v2; machine output stays emoji-free | same portable contract | same portable contract | Unicode hosts may remove emoji without changing fields |
| Super Caveman complete pinned ADHD-friendly response behavior, commit, review and help routes | current 19/19-case and 44/44-criterion behavior run plus 3/3 independent paired-judge candidate result and zero high-risk regressions; harness/model-specific | contract defined; equivalent behavior and promotion evidence required | host-dependent; no behavior evidence | host-dependent; no behavior evidence |
| Super Caveman lifecycle adapter (Claude Code) | Codex side: one-event SessionStart adapter implemented and smoke-tested; UserPromptSubmit state machine and persistent defaults require the separate reviewed decision in `docs/research/2026-08-31-codex-lifecycle-adapter-feasibility.md` before any build; no cross-host parity | Claude Code: opt-in adapter implemented inside the canonical package; deterministic 19-case lifecycle contract plus benchmark lifecycle fixtures pass; real-host smoke receipt `benchmarks/super-caveman/results/claude-smoke-receipt-attempt-1.json` recorded 2026-08-31; no full-parity claim and no fail-closed behavior | zcode: not claimed | not claimed |
| Super Caveman compact delegation | supported through available collaboration tools | supported through available subagents | host-dependent; named presets not claimed | host-dependent |
| Super Caveman guarded file compression | supported with Python 3.10+ and local file access | supported with Python 3.10+ and local file access | same neutral core | Python 3.10+ and local file access required |
| Super Caveman exact session statistics | host counters only; no bundled log scanner | host counters or separately reviewed compatible adapter | not claimed | unavailable without audited counters or parser |
| Spec Relay HTML packet | supported with Python 3.11+, stable review IDs, embedded `spec-relay.html-state.v1`, optimistic revision guards and relay receipts; Azhou branding stays outside HTML | same neutral package | supported when the host loads the skill and permits local execution | file carries embedded comments after polling persists them; one writer per packet revision |
| Spec Relay browser review and foreground polling | supported with Node.js 22+, a local browser and attached command execution | supported with Node.js 22+, a local browser and attached command execution | host-dependent; verify browser and foreground command lifecycle | host-dependent |
| Spec Relay standalone export | supported through locked Lavish CLI after dependency resolution | same neutral package | host-dependent | Node.js 22+ and local file access required |
| Spec Relay third-party share | available only after explicit publication authorization and network verification | same boundary | same boundary | share transfers embedded comments; no claim without receipt |
| Lavish rich-HTML artifact review loop | supported with Node.js 22+, the locked <code>lavish-axi@0.1.47</code> baseline and a local browser; artifacts and session state stay local until explicit publication | same neutral package | supported when the host loads the skill and permits local execution | host-dependent; the <code>ht-ml.app</code> share is a third-party publication action, not a bundled service |

## Meaning of “supported”

- **Supported**: implemented in the repository and covered by deterministic checks or a documented real adapter.
- **Host-dependent**: the runtime package is neutral, but the harness installation or tool surface must be verified.
- **Not claimed**: no audited implementation exists. It is not silently treated as equivalent.

Model quality is not a support claim. Benchmark comparisons must freeze the prompt, runtime package digest, time limit and tool permissions, then record attempt-1 evidence.

Open a [bug report](https://github.com/TeFuirnever/azhou-ai-hub/issues/new?template=bug.yml) when an entry is stale. Include the harness version, skill commit and a redacted reproduction.
