# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Diagram-Design-MIT.txt](../../../LICENSES/Diagram-Design-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/cathrynlavery/diagram-design` |
| Immutable commit | `d7b0176d7e60c6f2ff54067991491ac7622c81fb` |
| Upstream path | `skills/diagram-design/` |
| Upstream `SKILL.md` SHA-256 | `0f8159717762225aad4f8aec9162ffecd1ad19f12f41157c5874dfc047017cc1` |
| Upstream `LICENSE` SHA-256 | `bb7e12e91fecef43024111123ff784cec6c485585561d8b552557c0173b3ed29` |
| Upstream `THIRD_PARTY_LICENSES.md` SHA-256 | `ad931154e2f91bf545fc9c442666a2159aa56c0af3cca0b7246e02c6efeab6ba` |
| License | MIT, copyright 2025 Cathryn Lavery |
| Upstream version | frontmatter metadata version `"2.6"` (recorded 2026-11-22) |

The upstream repository published no Git tags or releases as of 2026-11-22, so skill-standard §1.2 reports this adoption as having no formal stable release and pins the immutable commit at the `main` tip; `git rev-parse HEAD` and `git ls-remote` were compared on 2026-11-22 and agree at the pinned commit.

The capability baseline at the locked commit is the complete diagram pipeline: fifty visual types with the semantic-pattern → visual-type selection layer, the three-variant template skin system, `.drawio` / Mermaid / `.excalidraw` / PlantUML import through the four packaged extract scripts, the style-guide gate with its profile mechanism, the bundled reference corpus (70 reference pages) and example/template assets (242 HTML files), the eight packaged Python scripts (self-check, geometry verification, SVG/PNG export, the four import extractors), and the bundled third-party icon and font content (Tabler Icons, Simple Icons, log-z/logos, Devicon, Instrument Serif, and one-off Wikimedia/icepanel icons with trademark notes) declared by the upstream [`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md), which ships with the package unchanged.

## Azhou-maintained adaptation

- vendors every upstream file byte-identically from the pinned commit — all 70 reference pages, all 242 assets, all 8 scripts, the upstream `LICENSE` and the upstream `THIRD_PARTY_LICENSES.md` are unmodified; `SKILL.md` keeps the upstream body verbatim below the title and carries only the packaging increments listed here (the upstream `SKILL.md` SHA-256 above identifies the unmodified source);
- narrows frontmatter to the neutral `name`, `description`, and `invocation` contract; the upstream `license: MIT` key and the `metadata.version "2.6"` field move into this record;
- adds the Azhou identity anchor, the brand protocol, and the stable receipt (`super-diagram-design.receipt.v1`);
- adds [setup.md](setup.md) recording the Python 3 runtime baseline and the optional Playwright export/preview boundary that the upstream assumes preinstalled;
- adds this provenance record and the [upstream compatibility map](upstream-compatibility.md);
- compresses the frontmatter description's fifty-type enumeration to representative types, and names the functional boundaries with `super-archify` and `super-excalidraw-diagram` in the entry description; the upstream name `diagram-design` keeps working as a trigger.

Classification: `faithful` — the complete upstream capability is retained (byte-identically except the packaging increments on `SKILL.md`), and every local addition (frontmatter normalization, brand protocol, receipt, provenance, setup and compatibility records) is packaging or interaction layer, which skill-standard §2.3 excludes from `adapted`. Precedent: verbatim retention of the entire upstream capability with packaging-only additions decides `faithful`. Skill-standard §2.3.

## Showcase deferral

The skill-standard §4 showcase scene (`assets/skills/super-diagram-design-effect.png`) is deferred to a dedicated maintainer visual pass per the #478 deferral precedent: it must come from the governed azhou-scenes pipeline with a named human visual P0 approval and metadata sanitization before publishing. The READMEs carry the catalog row without a showcase section until that pass lands, and the hero digits and their alt-text counts stay at their landed state in the meantime. Next action: run the dedicated visual pass, then extend both README showcase sections 1:1.

## Reproducible source check

```bash
git clone https://github.com/cathrynlavery/diagram-design /tmp/diagram-design-src
git -C /tmp/diagram-design-src checkout d7b0176d7e60c6f2ff54067991491ac7622c81fb
shasum -a 256 /tmp/diagram-design-src/skills/diagram-design/SKILL.md /tmp/diagram-design-src/LICENSE
```

Expected SHA-256 values: `0f8159717762225aad4f8aec9162ffecd1ad19f12f41157c5874dfc047017cc1` (upstream `SKILL.md`) and `bb7e12e91fecef43024111123ff784cec6c485585561d8b552557c0173b3ed29` (upstream `LICENSE`, byte-identical to [LICENSES/Diagram-Design-MIT.txt](../../../LICENSES/Diagram-Design-MIT.txt)).

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
git clone https://github.com/cathrynlavery/diagram-design /tmp/diagram-design-src
git -C /tmp/diagram-design-src checkout d7b0176d7e60c6f2ff54067991491ac7622c81fb
python -c "import hashlib; print(hashlib.sha256(open('/tmp/diagram-design-src/skills/diagram-design/SKILL.md','rb').read()).hexdigest())"
```
