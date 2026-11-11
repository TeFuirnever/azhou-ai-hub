# Provenance and local boundary

Repository-wide notices and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [archify-MIT.txt](../../../LICENSES/archify-MIT.txt). The independently installable package also retains its own `LICENSE` and `THIRD_PARTY_NOTICES.md`.

## Original import and current upstream baseline

| Field | Verified value |
|---|---|
| Official upstream | `https://github.com/tt-a1i/archify` |
| Original import | `v3.1.0` / `1c2b42d660e4a7571813fb43839c79e3e9ca7720` |
| Current stable release | [`v3.2.0`](https://github.com/tt-a1i/archify/releases/tag/v3.2.0) / `208acba8d412335185b2056fedf54b3405df43fb` |
| Release published | 2026-10-19T00:43:00Z; `draft=false`, `prerelease=false` |
| Verification date | 2026-11-10 (Asia/Shanghai), official release list and exact tag tree |
| Upstream package path / identity | `archify/` / `archify`; the Hub canonical package is `super-archify` |
| Upstream `archify/SKILL.md` SHA-256 | `93434ad579983f4cff639c2b7230c311e0785cc48a25b66b1498e1802be7de91` |
| License at both immutable commits | MIT, SHA-256 `b799ab081703e7821ae5096d2c1abdf14bbdc75e8ea1c4045998c36ed6db9706` |

The newer `archify-dsh-v1.1.0` release is a separately versioned DeepSeek Harness adapter. It is not this canonical skill's upgrade target. The default branch's license metadata also does not replace the license at the selected stable commit.

The v3.2.0 capability baseline contains the ten native diagram modes, typed schemas, deterministic CLI and browser gates, Viewer runtime, authoring/delivery/update contracts, and the new one-page explainer family. Explainers include Markdown authoring, panels, native diagrams, charts, source cards, patching, writing diagnostics and export controls. Existing diagram capabilities remain present.

## Three-way migration and local layer

The migration compares the original v3.1.0 `archify/` tree, the Hub implementation, and the complete v3.2.0 `archify/` tree. The source tree contains 203 files; retaining the existing 15 generated-example HTML exclusions and development `package-lock.json` exclusion, then the three Hub reference files, yields 190 packaged files. Per-file upstream and local digests, exclusions and dispositions are recorded in `tests/archify-vendor-manifest.json`.

The local capability-independent adaptations remain:

- canonical frontmatter (`name`, `description`, `invocation`), package/bin identity, existing display labels and canonical-folder command examples;
- the coexistence boundary: editable `.excalidraw` scenes belong to super-excalidraw-diagram; this skill delivers read-only native diagrams and explainer pages;
- the Azhou brand protocol, explicit holds and stable receipt (`super-archify.receipt.v1`), including honest `not-run` reporting for an optional explainer browser gate;
- the setup, provenance and compatibility references;
- removal of monorepo-only npm scripts and development lockfile, omission of generated example HTML, and the existing whitespace-only normalization.

The old canonical rename had also reached two runtime contracts. These are repaired against the actual upstream implementation:

| Contract | Previous local defect | Current behavior / regression |
|---|---|---|
| Live preview subprocess | `bin/preview.mjs` selected the nonexistent sibling `super-archify.mjs` | Uses the actual `archify.mjs`; the preview regression waits for a verified artifact, not just server startup |
| Stable update identity | Local `skillId` was renamed while the trusted manifest URL still supplied upstream `archify` | `skill-release.json` and `scripts/update-contract.mjs` retain upstream `archify`; the official-manifest regression verifies the shared identity |

These internal filenames and upstream protocol identifiers are not canonical discovery names. Restoring them does not install or mutate another skill, change pstack, or authorize automatic updates.

## Local compatibility fixes found during integration

PR #430's first CodeQL analysis reported six new paths in the v3.2.0 explainer (three dynamic text-to-HTML paths, one style-fragment rewrite, and two data-to-code constructions). This is a static-analysis finding count, not evidence of six exploited incidents. A separate review also found that plain repository citations silently replaced an explicit revision. All four affected source files were absent from the prior v3.1.0 package and matched the immutable v3.2.0 source before these local fixes.

| File | Local change | Preserved behavior and regression |
|---|---|---|
| `explainer/reader.js` | Escape dynamic text/attribute values before HTML construction; explicitly reject unavailable clipboard writes | Walk, Ask and source-card structure retained. Ask keeps selected manual-copy text when the Clipboard API is absent or rejects; snippet reports failure; successful copies retain existing behavior |
| `explainer/render.mjs` | Unwrap complete style elements and escape HTML raw-text style terminators after CSS processing | CSS range operators, native preview styles and themes retained; adversarial style text cannot close the enclosing style element |
| `explainer/browser-check.mjs` | Send selectors as CDP `Runtime.callFunctionOn` arguments in the page context, then release the receiver | Existing focus, Enter activation and native-viewer checks retained; selector data is not JavaScript source |
| `explainer/sources.mjs` | Reject explicit citation revisions conflicting with the document pin before fallback handling | Same-pin excerpts, explicit old document pins, inferred HEAD and no-repository plain references retained; two-commit regression covers silent revision replacement |

The revision inconsistency was reproduced with real Git commits and original inputs. A later integration review also reproduced false copy-success when the Clipboard API is absent; a shared async availability check routes both copy handlers to their existing fallback. The same frozen six branch observations improve from four to six passes in actual Chrome, with the four successful controls retained. A separate authentication replay binds the exact same browser version in both arms; original runs and their version-recording limit remain preserved. CodeQL paths, concrete regression results and limits are recorded separately in the task evidence. These are bounded local safety/correctness adaptations, not a new upstream version or an extra skill capability. The source commit, source digests and license remain unchanged; packaged digests and each migration disposition describe the actual local bytes. Regression code lives in repository-level `tests/test_archify.py`; immutable upstream tests remain separate evidence.

## Retained third-party notices

The package retains JetBrains Mono's SIL OFL notice and every upstream notice. The new explainer bundles the unmodified Pele 1.3.0 chart subset under `explainer/vendor/pele/`; its MIT license (kepano, 2026), npm tarball provenance, and embedded Lucide `rotate-ccw` ISC notice remain beside the bytes. Delivered charts are static SVG, as the upstream package documents.

## Fidelity classification

Classification: `faithful` — upstream native-diagram and explainer capabilities are retained; canonical naming, interaction/receipt boundaries, standalone packaging and source records do not add a separate capability implementation. Internal runtime identities follow the actual source. Skill-standard §2.3.

The previously accepted CodeQL finding in `delta/architecture-delta.mjs` is unchanged by this pin move; no remediation claim is made. It remains an offline authoring-helper limitation recorded in the compatibility map.

## Reproducible source check

```bash
git clone https://github.com/tt-a1i/archify /tmp/archify-upstream
git -C /tmp/archify-upstream checkout 208acba8d412335185b2056fedf54b3405df43fb
shasum -a 256 /tmp/archify-upstream/archify/SKILL.md /tmp/archify-upstream/LICENSE
```

Compare the original import, local package and exact new tag before changing the pin. Retain the packaging exclusions and local wrapper, regenerate the complete source/local digest manifest, run the package integrity and behavior regressions, and verify real browser behavior before making a browser-quality claim. A default-branch commit is not a substitute for stable-release evidence.
