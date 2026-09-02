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
| CLI baseline | `lavish-axi@0.1.47` |
| npm integrity | `sha512-zB1kEUSgyvi6sC3I/nBPCGZwO8Z5pt8I2/ltFcovC8R+PuzRwJUb5V4BWMWnaPdXVBPH07B7XoBKKBf28733kg==` |
| License | MIT, copyright 2026 Kun Chen |

The recorded hash identifies the unmodified upstream skill baseline at the locked commit. The upstream repository generates its installable skill from its own source; this package imports that generated behavior rather than the Lavish application code. The package is not byte-identical to that baseline: the documented local layer turns the review artifact into a portable relay packet when the request needs one, while preserving the upstream review runtime.

## Azhou-maintained adaptation

Azhou AI Hub keeps the upstream workflow, visual guidance, playbooks, polling rules, editable-whiteboard behavior, export/share commands, design-source priority, and session-end semantics. The local layer:

- narrows frontmatter to the neutral `name` and `description` contract;
- pins npm execution to `0.1.47` for reproducibility;
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
