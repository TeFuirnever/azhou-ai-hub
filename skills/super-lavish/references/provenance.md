# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Lavish-AXI-MIT.txt](../../../LICENSES/Lavish-AXI-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Audited source | configured user skill root, `lavish/SKILL.md` |
| Upstream | `https://github.com/kunchenguid/lavish-axi` |
| Immutable commit | `79aa0a18dba9c1a1dcec6db19d2ef4eb7643754b` |
| Upstream tag | `lavish-axi-v0.1.97` |
| Upstream path | `skills/lavish/SKILL.md` |
| Upstream source SHA-256 | `00ea380ff3e993d58029e4467901333138726f734755e0eef254de2fe4c2f1ef` |
| CLI baseline | `lavish-axi@0.1.97` |
| npm integrity | `sha512-Ux6/kePVt7DboZpROPKnrBNQaLtyaVDdC5wTT5X+roCR2e7AGI8Q4HDGbLFAXlm9zQlJO+SWRW9xHYHDI9F/UQ==` |
| npm tarball SHA-256 | `84e4d91c173e91b966c506da770a649d533766d93985739d26b8592143127662` |
| License | MIT, copyright 2026 Kun Chen |

The recorded hash identifies the unmodified upstream skill baseline at the locked commit and official release. The upstream repository generates its installable skill from its own source; this package imports that generated behavior rather than the Lavish application code. On import (2026-11-16) the `skills/lavish/SKILL.md` bytes were verified identical between the tag commit and the npm `0.1.97` release tarball, and the tarball SHA-256 and npm `dist.integrity` were computed from the downloaded tarball and cross-checked against the npm registry.

## Azhou-maintained adaptation

Azhou AI Hub keeps the upstream CLI-first design: the current workflow, design direction, playbooks, polling rules, editable-whiteboard behavior, export/share commands, and session-end semantics are read from the locked CLI at run time. The local layer:

- narrows frontmatter to the neutral `name`, `description`, and `invocation` contract;
- pins npm execution to `0.1.97` for reproducibility where upstream instructs the unpinned `npx -y lavish-axi`;
- adds the Azhou identity, stage language, status dictionary, and stable receipt ([brand-layer](brand-layer.md));
- adds setup, provenance, capability mapping, and explicit authorization checkpoints (publication, global installs, hook installs, session reopening);
- keeps the pre-rename `/lavish` name working as a compatibility trigger;
- names the functional boundaries with `super-archify` and `super-excalidraw-diagram` in the description.

No Lavish application code, browser bundle, logos, screenshots, or runtime assets are vendored. `npx` downloads the external CLI at execution time; `skills/super-lavish/` contains the Azhou-authored orchestration layer only. The CLI's own bundled third-party components are attributed by the upstream `THIRD-PARTY-NOTICES.md` shipped inside the npm package (SHA-256 `882673c8dec1bd8ad6ab936a08e83eb0ed86cba7c79780ab9cfb055dae67aeef` at this release); they are consumed at run time through `npx`, not redistributed from this repository.

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/lavish-axi/79aa0a18dba9c1a1dcec6db19d2ef4eb7643754b/skills/lavish/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `00ea380ff3e993d58029e4467901333138726f734755e0eef254de2fe4c2f1ef`.

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/lavish-axi/79aa0a18dba9c1a1dcec6db19d2ef4eb7643754b/skills/lavish/SKILL.md \
  | python -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
```

Release tarball check:

```bash
curl -fsSL -o /tmp/lavish-axi-0.1.97.tgz https://registry.npmjs.org/lavish-axi/-/lavish-axi-0.1.97.tgz
shasum -a 256 /tmp/lavish-axi-0.1.97.tgz
npm view lavish-axi@0.1.97 dist.integrity
```

Expected tarball SHA-256: `84e4d91c173e91b966c506da770a649d533766d93985739d26b8592143127662`. Expected npm `dist.integrity`: `sha512-Ux6/kePVt7DboZpROPKnrBNQaLtyaVDdC5wTT5X+roCR2e7AGI8Q4HDGbLFAXlm9zQlJO+SWRW9xHYHDI9F/UQ==`.

## Fidelity classification

Classification: `faithful` — the upstream review workflow and its CLI-first design are preserved at the locked baseline; the local layer only repackages (neutral frontmatter, locked version pin, Azhou interaction layer, authorization checkpoints) and adds or removes no capability route. The canonical name is `super-lavish` (renamed from `lavish` under the repository rename milestone); the old name survives only as a compatibility trigger in the entry description. Skill-standard §2.3.
