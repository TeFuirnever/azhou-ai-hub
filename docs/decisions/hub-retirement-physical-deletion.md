# HUB-RET-001: Retire three surfaces by physical deletion while freezing installed-state identifiers

- **Status:** Accepted — the cut lands as the squash of the `codex/decommission-20261111` branch (spec [#442](https://github.com/TeFuirnever/azhou-ai-hub/issues/442), tickets #443–#448); reversal requires Git history surgery, not a revert-friendly diff
- **Decision date:** 2026-11-11 (cut authorized); record filed 2026-11-12
- **Identifier:** `HUB-RET-001` — scoped to the Hub retirement cut (`RET`). Like `AS-E2E-001`, this directory deliberately avoids bare `ADR-NNNN` numbers, which belong to the lazily created domain-modeling [`docs/adr/`](../agents/domain.md) numbering space, so the two namespaces can never collide on one ID.
- **Scope:** the three objects retired by spec #442 — `packages/agent-orchestration-kit/` (the model router), `packages/codex-startup-animation/` (the legacy source root), and agent-skin's ZCode host layer.

## Context and constraints

Every repository change was still paying gates, docs, review surface and acceptance work for three surfaces the maintainer no longer intended to support:

- The **model router** (Agent Orchestration Kit) was an unreleased Codex profile installer whose main live coupling was a coexistence verdict that the pstack adapter loaded from the Kit's installer — dead code constraining a living package.
- The **legacy startup-animation root** had already been absorbed and de-derived by agent-skin; what remained unique was the Codex Pet toolchain and receipt ownership for installed App/Pet state.
- agent-skin's **ZCode host layer** chased ZCode desktop auto-updates through hard-coded version pins and failed closed whenever the installed desktop drifted from the pin — recurring maintenance with no planned support behind it.

Two hard constraints shaped the cut. First, installed state exists in the wild: Codex and DSH `0.9.0` installations migrate their persisted settings and installed-state ownership onto every new build, and those migrations key on identifiers that carry ZCode-era names (the `zcodeAttributes` wallpaper baseline keys, the `agent-skin-zcode-contract/v0.1` storage namespace, the `azhou.codex-startup-animation` owner/project id). Second, repository policy keeps evidence and CHANGELOG history immutable: retirement is recorded by new entries, never by rewriting old ones.

## Decision

1. **Retire by physical deletion, not by a frozen archive.** The package directories, the ZCode driver/runtime/page adapter, their tests, docs, CI legs and every Hub-side integration surface (model-router adapter, Kit coexistence verdict, legacy blocking/event rules) are removed in one cut with no detection stubs. Traceability moves to Git history, the historical provenance rows and the retained old releases; THIRD_PARTY_NOTICES rows become historical statements rather than deletions.
2. **Freeze installed-state identifiers under their historical names.** Persisted/protocol identifiers stay byte-for-byte unchanged, each with a one-line provenance comment at its site. No rename, no compatibility alias.
3. **Keep the cut legible as records:** this ADR, the dual-language README exit statement (last supported versions and uninstall guidance), the support-matrix historical rows, the CHANGELOG entry, and a permanent reverse-scan gate that fails if retired references resurrect (registered with the cut's final ticket, #448, with exemptions limited to the frozen identifiers and the historical evidence/CHANGELOG original text). Release cadence: the gate is the cut's last repository-side act — the version cut and the maintainer-machine uninstall of the retired installs execute after the branch merges, per the release process, so the uninstall run can double as machine-verified evidence for the exit statement instead of blocking the cut.

## Alternatives weighed

| Option | Benefits | Costs and failure modes |
|---|---|---|
| **A. Physical deletion + frozen identifiers — selected** | Dead code, gates, docs and review surface disappear at once; the surviving surface is exactly the supported surface; no stub code to drift | Hard to reverse: restoring any object means recovering bytes from Git history, not flipping a flag. Counterintuitive residue survives by design: a future reader of the living package meets ZCode-named keys and a `codex-startup-animation` owner id with no ZCode host in sight — the provenance comments and this record are the explanation |
| **B. Frozen archive: keep the trees, marked `unsupported`** | Zero recovery cost; old references keep resolving in-tree | The maintenance bill survives: every gate, doc and review still carries the dead surface; an in-tree "unsupported" directory invites both accidental dependence and slow rot; provenance-by-presence blurs the line between supported and unsupported claims |
| **C. Rename identifiers with compatibility aliases** | Names would match the post-cut shape | Aliases double the identifier surface forever and make every migration touch two names; a partial alias rollout splits installed state into two populations; the spec explicitly excluded alias migrations |
| **D. Staggered soft deprecation (warn, then freeze, then delete)** | Gentler for any external consumer | The retired objects were personal-scope surfaces with no external distribution authorization; a transition period would keep paying the exact maintenance burden being retired while promising support that did not exist |

**Why A:** for a maintainer-owned repository whose retired surfaces never had a public support contract, the honest boundary is the one the repository actually enforces. The irreversibility cost is real but bounded — Git history plus the provenance rows carry the exact bytes and their licenses — while the frozen-identifier residue is not optional at any option: installed-state migrations depend on those names regardless of how the source retires.

## Consequences

**Positive:** the surviving packages (pstack, agent-skin with its Codex and DSH hosts) carry only the gates and docs for surfaces that are actually supported; the Pet toolchain survives in agent-skin after a maintainer-reviewed receipt-ownership handoff; `pstack` loses its coupling to a dead installer (its coexistence install, owned exit and read-only transition review remain its own capabilities).

**Negative:** nothing retired can be re-enabled incrementally; the ZCode-named frozen identifiers will look wrong to a cold reader until the site comments and this record are read; installed ZCode skins are frozen installs that receive no further builds, and their retirement (restore the launcher retained by the install transaction, or remove the entry) is manual by design.

**Revisit when:** a genuine external support need emerges for a retired object (requires a new decision reversing this one, with the license and redistribution constraints re-examined first), or an installed-state migration format bump makes a frozen identifier renegotiable — at which point the rename-with-alias question returns with a real migration budget, not before.

**Traceability:** spec [#442](https://github.com/TeFuirnever/azhou-ai-hub/issues/442) · tickets #443 (Pet toolchain migration and handoff), #444 (ZCode host layer removal), #445 (model-router deletion), #446 (legacy root deletion), #447 (this record, the exit statement and the CHANGELOG entry), #448 (the permanent reverse-scan gate, `scripts/check_retired_surfaces.py`) · frozen-identifier sites annotated in `packages/agent-skin/` (`wallpaper/renderer.js`, `image-settings.js`, `install-macos.py`, `Native/InstallRegistryCore.swift`, `Native/Wallpaper.swift`, `extension/renderer.mjs`, `renderer.js`, `verify-artifacts.py`, `tools/manage-codex-pet.py`).
