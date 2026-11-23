# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Lavish-AXI-MIT.txt](../../../LICENSES/Lavish-AXI-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Audited source | configured user skill root, `lavish/SKILL.md` |
| Upstream | `https://github.com/kunchenguid/lavish-axi` |
| Immutable commit | `2b32b92ec8e8fcfb7069af3e1a89c0cabc3bf9aa` |
| Upstream tag | `lavish-axi-v0.1.98` |
| Upstream path | `skills/lavish/SKILL.md` |
| Upstream source SHA-256 | `00ea380ff3e993d58029e4467901333138726f734755e0eef254de2fe4c2f1ef` |
| CLI baseline | `lavish-axi@0.1.98` |
| npm integrity | `sha512-LGadkBwrutayCodUzcuE68xZ5roAQr76tNq6UQQjyTAozZJZulbm2/3sHqq8IVxLa74aVrUnkLYi18emYlhlCQ==` |
| npm tarball SHA-256 | `429d796a03771a759d1df8967a58ff596ad5b5634a6382a530b4f917ea67d0fb` |
| License | MIT, copyright 2026 Kun Chen |

The recorded hash identifies the unmodified upstream skill baseline at the locked commit and official release. The upstream repository generates its installable skill from its own source; this package imports that generated behavior rather than the Lavish application code. At the 0.1.98 re-lock (2026-11-23) the `skills/lavish/SKILL.md` bytes were verified identical between the tag commit and the npm `0.1.98` release tarball, and the tarball SHA-256 and npm `dist.integrity` were computed from the downloaded tarball and cross-checked against the npm registry; the skill bytes are unchanged from the 0.1.97 import (2026-11-16).

## Azhou-maintained adaptation

Azhou AI Hub keeps the upstream CLI-first design: the current workflow, design direction, playbooks, polling rules, editable-whiteboard behavior, export/share commands, and session-end semantics are read from the locked CLI at run time. The local layer:

- narrows frontmatter to the neutral `name`, `description`, and `invocation` contract;
- pins npm execution to `0.1.98` for reproducibility where upstream instructs the unpinned `npx -y lavish-axi`;
- adds the Azhou identity, stage language, status dictionary, and stable receipt ([brand-layer](brand-layer.md));
- adds setup, provenance, capability mapping, and explicit authorization checkpoints (publication, global installs, hook installs, session reopening);
- keeps the pre-rename `/lavish` name working as a compatibility trigger;
- names the functional boundaries with `super-archify`, `super-excalidraw-diagram`, and `super-imagegen` in the description.

No Lavish application code, browser bundle, logos, screenshots, or runtime assets are vendored. `npx` downloads the external CLI at execution time; `skills/super-lavish/` contains the Azhou-authored orchestration layer only. The CLI's own bundled third-party components are attributed by the upstream `THIRD-PARTY-NOTICES.md` shipped inside the npm package (SHA-256 `882673c8dec1bd8ad6ab936a08e83eb0ed86cba7c79780ab9cfb055dae67aeef` at this release); they are consumed at run time through `npx`, not redistributed from this repository.

## Showcase scene

`assets/skills/super-lavish-effect.png` (added 2026-11-16) is the package's skill showcase scene under skill-standard §4. It was generated with the maintainer's local azhou-gen pipeline: azhou-scenes `article_16_9` mode, Qwen-Image-2.1 edit with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`), scene quality anchor `04-code-review-rework` recorded observation-only (`used_as_image_gen_reference=false`), final tier, seed 23, and the 1664×960 raw candidate shipped unmodified (candidate SHA-256 `d41c71a2eec7976c0cd8dd4c0e2c1fef7b19642b1528d4c924d9e06c4e491a97`). The full receipt chain (run `azhou-20261116T032044Z-lavish-circle-s2`, preflight → dispatch → postflight, `execution_scope=local_candidate_only`, `asset_status=HOLD` until the named human visual P0 approved it on 2026-11-16) and the approval record stay Git-external in the maintainer's store. Repository-wide notice: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/lavish-axi/2b32b92ec8e8fcfb7069af3e1a89c0cabc3bf9aa/skills/lavish/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `00ea380ff3e993d58029e4467901333138726f734755e0eef254de2fe4c2f1ef`.

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/lavish-axi/2b32b92ec8e8fcfb7069af3e1a89c0cabc3bf9aa/skills/lavish/SKILL.md \
  | python -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
```

Release tarball check:

```bash
curl -fsSL -o /tmp/lavish-axi-0.1.98.tgz https://registry.npmjs.org/lavish-axi/-/lavish-axi-0.1.98.tgz
shasum -a 256 /tmp/lavish-axi-0.1.98.tgz
npm view lavish-axi@0.1.98 dist.integrity
```

Expected tarball SHA-256: `429d796a03771a759d1df8967a58ff596ad5b5634a6382a530b4f917ea67d0fb`. Expected npm `dist.integrity`: `sha512-LGadkBwrutayCodUzcuE68xZ5roAQr76tNq6UQQjyTAozZJZulbm2/3sHqq8IVxLa74aVrUnkLYi18emYlhlCQ==`.

## Fidelity classification

Classification: `faithful` — the upstream review workflow and its CLI-first design are preserved at the locked baseline; the local layer only repackages (neutral frontmatter, locked version pin, Azhou interaction layer, authorization checkpoints) and adds or removes no capability route. The canonical name is `super-lavish` (renamed from `lavish` under the repository rename milestone); the old name survives only as a compatibility trigger in the entry description. Skill-standard §2.3.
