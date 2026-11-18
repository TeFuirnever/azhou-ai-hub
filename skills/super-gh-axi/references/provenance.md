# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Gh-Axi-MIT.txt](../../../LICENSES/Gh-Axi-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Audited source | configured user skill root, `gh-axi/SKILL.md` |
| Upstream | `https://github.com/kunchenguid/gh-axi` |
| Immutable commit | `911a0868600b125aafe5e7f77197a0eb5a5b493c` |
| Upstream tag | `gh-axi-v0.1.51` |
| Upstream path | `skills/gh-axi/SKILL.md` |
| Upstream source SHA-256 | `3d01b3112442275d52cc5847cb17543c710128f4591346e77eeecc30c45e76f3` |
| CLI baseline | `gh-axi@0.1.51` |
| npm integrity | `sha512-uZ/DIKzfmYOPkcHdM7Dn8fBmdO7bZt7QzcZ6ZXUz55m58UbdfemQ3rlZNYT6avH3h7d9tPAjwUeMJ9JmFqVjAA==` |
| npm tarball SHA-256 | `fee983711774d8fa50ecec90a51aa8032538648c6877fcb1c44d7bd9716d54c2` |
| License | MIT, copyright 2026 Kun Chen |

The recorded hash identifies the unmodified upstream skill baseline at the locked commit and official release. The upstream repository generates its installable skill from its own source; this package imports that generated behavior rather than the gh-axi CLI code. On import (2026-11-17) the `skills/gh-axi/SKILL.md` bytes were verified identical between the tag commit and the npm `0.1.51` release tarball, and the tarball SHA-256 and npm `dist.integrity` were computed from the downloaded tarball and cross-checked against the npm registry (the official registry and the mirror returned the same digests). The audited maintainer shell copy differs from the upstream baseline by exactly one inserted project-rules-win clause; that clause is adopted here as a documented local enhancement, not as upstream bytes.

## Azhou-maintained adaptation

Azhou AI Hub keeps the upstream CLI-first design: the command, flag, and workflow surface is read from the locked CLI at run time and never baked into the package. The local layer:

- narrows frontmatter to the neutral `name`, `description`, and `invocation` contract, translating the upstream host-specific `user-invocable: false` into `invocation: model-invoked discipline` (the upstream `author` and `metadata.hermes` keys are not copied);
- pins npm execution to `0.1.51` for reproducibility where upstream instructs the unpinned `npx -y gh-axi`;
- adds the project-rules-win precedence clause (prefer this over `gh` and other methods for GitHub operations unless the current repository's rules name a different tool or recipe for the task), already present in the audited shell copy, as a documented local enhancement;
- adds the Azhou identity, stage language, status dictionary, and stable receipt ([brand-layer](brand-layer.md));
- adds setup, provenance, capability mapping, and explicit authorization checkpoints (global installs, hook installs, baseline updates, credential and secret handling, named-mutation-only boundaries);
- keeps the pre-rename `gh-axi` name working as a compatibility trigger;
- adds no capability carve sentence: the GitHub operations surface has no overlap with the other canonical packages (checked against every canonical description at adoption, 2026-11-17).

No gh-axi application code, `dist/` bundle, or runtime assets are vendored. `npx` downloads the external CLI at execution time; `skills/super-gh-axi/` contains the Azhou-authored orchestration layer only. The wrapped `gh` binary and its authentication stay external.

## Showcase scene

`assets/skills/super-gh-axi-effect.png` (added 2026-11-17) is the package's skill showcase scene under skill-standard §4. It was generated with the maintainer's local azhou-gen pipeline: azhou-scenes `article_16_9` mode, Qwen-Image-2.1 edit with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`), scene quality anchor `03-production-alert` recorded observation-only (`used_as_image_gen_reference=false`), final tier, seed 21, run `azhou-20261117T131932Z-gh-axi-showcase-s21`, and the 1664×960 raw candidate shipped **metadata-sanitized before publishing**: a chunk whitelist keeps only IHDR/IDAT/IEND, so the shipped file (SHA-256 `64c17580947743509a2f0447d59e86482153ab8427b11c92ada7cab1c64ee7b8`) carries no prompt text, no local paths and no runtime identity, while the pixel stream (IHDR payload and all IDAT bytes) stays byte-identical to the approved candidate (SHA-256 `ae0b014187fe8bf167eca8b2509ec685b65c133fcd3622049d387e61fff40f03`, kept Git-external only). The full receipt chain (preflight → dispatch → postflight, `execution_scope=local_candidate_only`, `asset_status=HOLD` until the named human visual P0 approved it on 2026-11-17) and the approval record stay Git-external in the maintainer's store. Repository-wide notice: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/gh-axi/911a0868600b125aafe5e7f77197a0eb5a5b493c/skills/gh-axi/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `3d01b3112442275d52cc5847cb17543c710128f4591346e77eeecc30c45e76f3`.

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
curl -fsSL https://raw.githubusercontent.com/kunchenguid/gh-axi/911a0868600b125aafe5e7f77197a0eb5a5b493c/skills/gh-axi/SKILL.md \
  | python -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
```

Release tarball check:

```bash
curl -fsSL -o /tmp/gh-axi-0.1.51.tgz https://registry.npmjs.org/gh-axi/-/gh-axi-0.1.51.tgz
shasum -a 256 /tmp/gh-axi-0.1.51.tgz
npm view gh-axi@0.1.51 dist.integrity
```

Expected tarball SHA-256: `fee983711774d8fa50ecec90a51aa8032538648c6877fcb1c44d7bd9716d54c2`. Expected npm `dist.integrity`: `sha512-uZ/DIKzfmYOPkcHdM7Dn8fBmdO7bZt7QzcZ6ZXUz55m58UbdfemQ3rlZNYT6avH3h7d9tPAjwUeMJ9JmFqVjAA==`.

## Fidelity classification

Classification: `faithful` — the upstream trigger surface and CLI-first design are preserved at the locked baseline; the local layer only repackages (neutral frontmatter with the invocation translation, locked version pin, Azhou interaction layer, authorization checkpoints) and adds or removes no capability route. The canonical name is `super-gh-axi` (renamed from `gh-axi`); the old name survives only as a compatibility trigger in the entry description and as the external CLI's own package name. Skill-standard §2.3.
