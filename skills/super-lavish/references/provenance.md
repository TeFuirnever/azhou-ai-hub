# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Lavish-AXI-MIT.txt](../../../LICENSES/Lavish-AXI-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Audited source | configured user skill root, `lavish/SKILL.md` |
| Upstream source SHA-256 | `7c730b29baab6b29dd4c11f02783190f78e215604993a80228e3784423b5e857` |
| Upstream | `https://github.com/kunchenguid/lavish-axi` |
| Immutable commit | `232972beba9e0e4e75682c98f2aeb2cf01532122` |
| Upstream path | `skills/lavish/SKILL.md` |
| CLI baseline | `lavish-axi@0.1.83` |
| npm integrity | `sha512-cs6hfWReEPrGjySrEsPWm/Qg0ESKfRpH3t0dFRpsQiC0WSatkTA85LwRZngAwbJEDVSA2AmCf2p4+NlcVerzZA==` |
| License | MIT, copyright 2026 Kun Chen |

The recorded hash identifies the unmodified upstream skill baseline at the locked commit. The upstream repository generates its installable skill from its own source; this package imports that generated behavior rather than the Lavish application code. The package is not byte-identical to that baseline: the documented local layer turns the review artifact into a portable relay packet when the request needs one, while preserving the upstream review runtime.

## Azhou-maintained adaptation

Azhou AI Hub keeps the upstream workflow, visual guidance, playbooks, polling rules, editable-whiteboard behavior, export/share commands, design-source priority, and session-end semantics. The local layer:

- narrows frontmatter to the neutral `name` and `description` contract;
- pins npm execution to `0.1.83` for reproducibility;
- adds the Spec Relay relay mode: source/revision metadata, stable `data-review-id`s, an embedded `spec-relay.html-state.v1` block, complete comment and annotation records, feedback disposition updates, next-owner handoff, optimistic revision guards, a responsive visible ledger, and a relay-specific receipt ([Spec Relay contract](spec-relay.md));
- keeps Azhou identity, emoji, and stage language in the agent interaction layer while the transferable HTML remains brand-neutral;
- adds setup, provenance, capability mapping, authorization checkpoints, and stable Azhou receipts;
- forbids implicit publication, global installation, hook installation, and unrequested session reopening.

No Lavish application code, browser bundle, logos, screenshots, or runtime assets are vendored. `npx` downloads the external CLI at execution time; `skills/lavish/` contains the Azhou-authored orchestration and relay contract.

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/lavish-axi/232972beba9e0e4e75682c98f2aeb2cf01532122/skills/lavish/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `7c730b29baab6b29dd4c11f02783190f78e215604993a80228e3784423b5e857`.

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/lavish-axi/232972beba9e0e4e75682c98f2aeb2cf01532122/skills/lavish/SKILL.md \
  | python -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
```

## Update path

- 2026-10-07 — CLI baseline `0.1.47` → `0.1.83` (npm releases 0.1.48–0.1.83, 36 versions, zero `BREAKING CHANGES` markers per the upstream changelog scan in `docs/research/2026-10-07-upstream-freshness-scan.md`). Upstream skill source and immutable commit are unchanged (`232972be`, SHA-256 unchanged). Evidence recorded before the pin moved:
  - Relay contract regression on the local layer: `python tests/test_super_lavish_relay_state.py` (9 tests, includes the optimistic `state_revision` stale-write rejection, visible-ledger tampering rejection, exact visible-ledger projection, and the responsive-layout CSS assertions), `python tests/test_super_lavish_relay_fuzz_regressions.py` (4 tests), `python tests/test_fuzz_relay_state.py`, `python tests/test_super_lavish_entry_budget.py` — all pass.
  - Isolated install without global changes: `npm install lavish-axi@0.1.83 --prefix /tmp/lavish-083 --ignore-scripts` (plus the same for `0.1.47` as the comparison baseline); `npm view lavish-axi@0.1.83 dist.integrity` returned the integrity recorded above; the vendored `LICENSE` file is byte-identical between 0.1.47 and 0.1.83.
  - Real artifact-mode smoke on a `relay_state.py init` packet, identical steps on both versions: `open --no-open` (exit 0, session URL served HTTP 200), bounded 8s foreground `poll` (long-poll stayed alive until the bounded stop), `export --out` (exit 0, portable HTML, `unresolved_local_assets: 0`; export bodies identical across versions except the per-packet packet ID and timestamp), `end` (exit 0), and `relay_state.py validate` after the full lifecycle (`spec-relay.html-state.v1` valid, state block byte-identical to the pre-CLI copy). No browser annotation round-trip was exercised (no human in the loop), matching the disclosed boundary of the 2026-09-02 receipts.
  - Command-surface deltas at 0.1.83, none breaking the documented loop: additive `reply` command, `explanation` playbook added (7→8), `self_paint_warning` advisory emitted at open, poll may return `browser_disconnected` after the reconnect grace period, `share` adds `--private`/`--site`/`--unpublish` while keeping `--password`/`--token`, and diagram guidance now defaults to hand-authored inline SVG with Mermaid as the opt-in editable whiteboard (documented in artifact-mode.md).

## Fidelity classification

Classification: `adapted` — boundary case, decided by cited evidence: the upstream workflow is preserved (pinned commit `232972beba9e0e4e75682c98f2aeb2cf01532122`, source SHA-256 `7c730b29baab6b29dd4c11f02783190f78e215604993a80228e3784423b5e857`), and the local layer adds the entire Spec Relay mode (relay packets, `data-review-id`s, disposition updates, optimistic revision guards, relay receipt) — a new capability route on top of the original's flow, which is a capability extension, not packaging. Precedent: preserving the upstream workflow while adding a new mode decides `adapted`. The canonical name is `super-lavish` (renamed from `lavish` in #181 under the audit's rename milestone #176); the old name survives only as a compatibility trigger in the entry description. Skill-standard §2.3.
