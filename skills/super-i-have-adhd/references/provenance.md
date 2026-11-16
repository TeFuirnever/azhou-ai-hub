# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [I-have-Adhd-MIT.txt](../../../LICENSES/I-have-Adhd-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/ayghri/i-have-adhd` |
| Immutable commit | `1ecea1993b7fce257ffbd686c070948b5e07eda6` |
| Upstream path | `skills/i-have-adhd/SKILL.md` |
| Upstream source SHA-256 | `88955c019bbb1419ff4b49dbb1f80a867467de6233d7865af2e06a7d7b76c7d3` |
| Upstream LICENSE SHA-256 | `8acbb618089b738404f76ac60fca1aaa995d9a87995eddf95f0b777acd7f7d2c` |
| License | MIT, copyright 2026 Ayoub Ghriss |

The recorded hashes identify the unmodified upstream skill at the locked commit; the upstream ships only the instruction file and its license, so nothing else exists to vendor. The upstream entry carries host-specific frontmatter (`disable-model-invocation: true`, metadata tags); the package replaces it with the neutral frontmatter contract and does not copy host-specific keys.

## Adoption evidence

Adoption rides the bounded pilot specified in [docs/specs/super-i-have-adhd-pilot.md](../../../docs/specs/super-i-have-adhd-pilot.md): the U0 freeze recorded the upstream commit, both SHA-256 digests and the attribution before any comparison; the U1 execution ran the three-arm comparison (A upstream / B current / C minimal candidate) over the frozen integration-handoff packet in one dynamic-workflow run after the U0 freeze; the U2 judgment pass produced the **provisional promote** decision. Declared limits, kept with the decision: the judgment is non-blind (the maintainer read the outputs), rests on a single sample of a single recorded workflow, and makes no quantitative, medical, cross-harness, or model-quality claim. Raw prompts, outputs, receipts and the judgment record stay Git-external in the pilot evidence store.

## Azhou-maintained adaptation

The package keeps the upstream instruction body verbatim (everything below the upstream `# i-have-adhd` title in the frozen `SKILL.md`); the local layer:

- narrows frontmatter to the neutral `name`, `description`, and `invocation` contract; `invocation: both` follows the pilot judgment, and the upstream host-specific `disable-model-invocation: true` is not copied;
- adds the Azhou identity, stage language, status dictionary, and stable receipt ([brand-layer](brand-layer.md));
- adds a setup reference recording the zero-dependency, instruction-only boundary;
- appends five presentation constraints as the Azhou delta: conclusions carry their source pointers or limits nearby; state changes stay separate from pending decisions; the output never creates evidence; a Review Contract is optional and never fabricated; output contains no machine-local absolute paths and references packets with relative paths — the last constraint closes the absolute-path leak observed in the pilot run;
- names the functional boundaries with `super-eli5`, `super-arch-doc`, and `super-imagegen` in the entry description, and keeps the upstream name `i-have-adhd` and `拆步` working as triggers.

## Showcase scene

`assets/skills/super-i-have-adhd-effect.png` (added 2026-11-17) is the package's skill showcase scene under skill-standard §4. It was generated with the maintainer's local azhou-gen pipeline: azhou-scenes `article_16_9` mode, Qwen-Image-2.1 edit with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`), the scene quality anchor `02-message-overload` recorded observation-only (`used_as_image_gen_reference=false`), seed 23. The shipped PNG is the approved raw candidate **metadata-sanitized before publishing** (candidate SHA-256 `2e1cb65711936bcd3e6cb1cc95ea9bb837f36b35cd78280a19c7a104845f5676`, whose unmodified bytes stay Git-external in the maintainer's store): a chunk whitelist keeps only IHDR, IDAT and IEND and strips the pipeline-embedded eXIf/iTXt/tEXt metadata (scene prompt, local model and reference paths, runtime identity), so the shipped file (SHA-256 `838bdd4bcd4d50ce4e1249c47f4ad146a279286b4fe26036b1c6fd104502a8e2`) carries no prompt text, no local paths and no runtime identity; the pixel stream (IHDR and all IDAT bytes) is byte-identical to the approved candidate, and a repository test pins the absence of ancillary metadata chunks. The full receipt chain (run `azhou-20261116T132145Z-iha-showcase-s23`, preflight → dispatch → postflight) and the standalone approval artifact for the named human visual P0 (`p0-approval-s23.json`, approved 2026-11-17, the maintainer adopting the recommended candidate s23 with a `go` instruction) stay Git-external in the maintainer's store; the formal governed-workspace colour audit remains open. Repository-wide notice: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/ayghri/i-have-adhd/1ecea1993b7fce257ffbd686c070948b5e07eda6/skills/i-have-adhd/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `88955c019bbb1419ff4b49dbb1f80a867467de6233d7865af2e06a7d7b76c7d3`.

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
curl -fsSL https://raw.githubusercontent.com/ayghri/i-have-adhd/1ecea1993b7fce257ffbd686c070948b5e07eda6/skills/i-have-adhd/SKILL.md \
  | python -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
```

License copy check against the retained file:

```bash
curl -fsSL https://raw.githubusercontent.com/ayghri/i-have-adhd/1ecea1993b7fce257ffbd686c070948b5e07eda6/LICENSE \
  | shasum -a 256
```

Expected SHA-256: `8acbb618089b738404f76ac60fca1aaa995d9a87995eddf95f0b777acd7f7d2c`, byte-identical to [LICENSES/I-have-Adhd-MIT.txt](../../../LICENSES/I-have-Adhd-MIT.txt).

## Fidelity classification

Classification: `adapted` — the upstream capability is extended, not merely repackaged: the frozen output-shaping rules gain five Azhou-maintained presentation constraints (source/limit proximity, decision-continuity separation, an evidence-integrity boundary, an optional Review Contract, and a relative-path-only output rule) that add behavior on top of the original flow, beside the neutral frontmatter and the Azhou interaction layer. The upstream instruction body itself is retained verbatim, and the upstream name keeps working as a trigger. Skill-standard §2.3.
