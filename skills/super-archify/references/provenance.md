# Provenance and local boundary

Repository-wide notices and the retained license copies live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md), [archify-Apache-2.0.txt](../../../LICENSES/archify-Apache-2.0.txt) and [archify-MIT.txt](../../../LICENSES/archify-MIT.txt). The independently installable package also retains its own `LICENSE`, `LICENSE-MIT`, `NOTICE` and `THIRD_PARTY_NOTICES.md`.

## Original import and current upstream baseline

| Field | Verified value |
|---|---|
| Official upstream | `https://github.com/tt-a1i/archify` |
| Original import | `v3.1.0` / `1c2b42d660e4a7571813fb43839c79e3e9ca7720` |
| Previous pin | `v3.2.0` / `208acba8d412335185b2056fedf54b3405df43fb` |
| Current stable release | [`v3.3.0`](https://github.com/tt-a1i/archify/releases/tag/v3.3.0) / `af3aaf3c36762f2afb62a4a09533f6c7273b07e5` |
| Release published | 2026-11-22T18:04:07Z; `draft=false`, `prerelease=false`, tag `v3.3.0` resolves to the commit (`git rev-parse v3.3.0^{commit}`) |
| Release artifact | `archify.zip` uploaded by `github-actions[bot]`, SHA-256 `00e4ff53267aee7dabf22ed333360cd3e380db20271a50264ae146ee25cf2538` |
| Verification date | 2026-11-23 (Asia/Shanghai), official release list and exact tag tree |
| Upstream package path / identity | `archify/` / `archify`; the Hub canonical package is `super-archify` |
| Upstream `archify/SKILL.md` SHA-256 | `e5c49b1c3e1b5b46ffb044aa676c46a58715cb34b459cbabd7f48e5887fed808` |
| License at the current immutable commit | Apache-2.0 (`LICENSE` SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`), with pre-transition MIT grants preserved upstream as `LICENSE-MIT` (SHA-256 `b799ab081703e7821ae5096d2c1abdf14bbdc75e8ea1c4045998c36ed6db9706`, byte-identical to the license text at the previous pins) and named in `NOTICE` (SHA-256 `4c88357b600f24214bd6d12ee70e37d66a160c6069bba2aec2d35486f6ff1a3a`); the transition names pre-transition commit `82c7e0f089a02a4d514714adf37dc2061682da5f` and keeps existing MIT grants and the separately versioned DSH adapter MIT |
| License at the earlier immutable commits | MIT, SHA-256 `b799ab081703e7821ae5096d2c1abdf14bbdc75e8ea1c4045998c36ed6db9706` |

Upstream adopted Apache-2.0 on stable main in PRs #1098/#1099 between v3.2.0 and v3.3.0. The retained `LICENSES/archify-MIT.txt` copy is byte-identical to the upstream `LICENSE-MIT` historical grant, so the MIT grant record continues unchanged while the vendored source now carries Apache-2.0. The separately versioned `archify-dsh-v1.1.0` release remains a DeepSeek Harness adapter line and is not this canonical skill's upgrade target. A default branch's license metadata does not replace the license at the selected stable commit.

The v3.3.0 capability baseline keeps the ten native diagram modes, typed schemas, deterministic CLI and browser gates, the Viewer runtime, the authoring/delivery/update contracts and the explainer family, and adds: the local-repository Code Analysis workbench (`modules/code-analysis/`, vendored parser/schema packages so the skill needs no install), Story walkthroughs with native HTML stages and video export (`story/`), the explicit PR review attachment (`pr/`, `references/pr-review.md`), cross-diagram drilldown navigation, authored node explanations in the Semantic Passport, a static SVG export path for README delivery, the Architecture Diagnosis offer, `bin/export-svg.mjs`, proactive-by-default explainer mode with an `[archify explainer: on-demand]` switch, the Russian locale moving from `examples/locales/` to `locales/`, and upstream removal of the fifteen pre-rendered example HTML files (#1453). Existing diagram and explainer capabilities remain present.

## Three-way migration and local layer

This pin move compares the v3.2.0 `archify/` tree (203 files), the Hub package and the complete v3.3.0 `archify/` tree (596 files). The prior fifteen rendered-example HTML exclusions dissolved because upstream itself stopped shipping them; the dev-only `package-lock.json` remains the single documented exclusion, and with the three Hub reference files the package carries 598 files. Per-file upstream and local digests, exclusions and dispositions are recorded in `tests/archify-vendor-manifest.json`.

The local capability-independent adaptations remain:

- canonical frontmatter (`name`, `description`, `invocation`), package/bin identity, existing display labels and canonical-folder command examples; the v3.3.0 upstream description exceeded the hub's 1024-character frontmatter ceiling after the Azhou prefix and coexistence carve, so the trigger surface is condensed with all native modes, Mermaid/repository evidence, Code Analysis, explainer English and Chinese triggers with the proactive default and on-demand switch, story/video export, `Not for dashboards` and all three boundary skill names retained — the full upstream description lives at the pinned source;
- the coexistence boundary: editable `.excalidraw` scenes belong to super-excalidraw-diagram; this skill delivers read-only native diagrams and explainer pages;
- the Azhou brand protocol, explicit holds and stable receipt (`super-archify.receipt.v1`), including honest `not-run` reporting for an optional explainer browser gate;
- the setup, provenance and compatibility references;
- removal of monorepo-only npm scripts and the development lockfile;
- display-name substitutions in user-facing usage/warning strings and canonical-folder command examples, replayed with byte-validated rules (`bin/archify.mjs`, `renderers/shared/cli.mjs`, `renderers/shared/brand-marks.mjs`, `recipes/scenarios.mjs`, the mode READMEs, `references/explainer-authoring.md`, `schemas/README.md`, `scripts/generate-validators.mjs`);
- the retained local documentation corrections where upstream still ships the stale text (`schemas/README.md` schema facts, the `explainer-authoring.md` diagram-count sentence);
- the generator-label and whitespace-only normalization (`assets/template.html` generator meta line, `renderers/workflow/workflow-compiler.mjs` whitespace-only lines);
- the retained local `examples/archify-repository.tree.json` packaging delta, `renderers/shared/diagnostics.mjs`, `scripts/generate-brand-marks.mjs` and the unchanged mode README deltas;
- the v3.2.0-era restore of the real sibling `bin/archify.mjs` identity in `bin/preview.mjs` and the upstream `archify` skillId in `skill-release.json`/`scripts/update-contract.mjs`; v3.3.0 keeps both, so `bin/preview.mjs` and `skill-release.json` now carry upstream bytes verbatim.

## Local compatibility fixes carried across this pin

The four PR #430-era files are re-derived against the v3.3.0 bytes:

| File | Local change | Preserved behavior and regression |
|---|---|---|
| `explainer/reader.js` | Hoisted attribute-complete `escapeText` over the Walk bar, Ask dialog and source cards; line numbers and source numbers pass through `escapeText`. The Clipboard availability guard is retired: upstream now owns `copyText` and routes snippet, Ask and feedback-email copies through it, so unavailable or rejecting Clipboard API writes reach the existing failure fallbacks (Ask keeps a retryable selected text) | Walk, Ask structure, source cards, the manual-copy fallbacks and the upstream retry flow retained; the hub regression now asserts the upstream failure notices and the `.ask-note` element |
| `explainer/render.mjs` | Unwrap complete style elements and escape HTML raw-text style terminators after CSS processing (anchors unchanged upstream at v3.3.0) | CSS range operators, native preview styles and themes retained; adversarial style text cannot close the enclosing style element |
| `explainer/browser-check.mjs` | Send selectors as CDP `Runtime.callFunctionOn` arguments in the page context, then release the receiver (the upstream v3.3.0 changes touch other functions; the hardened call sites replay verbatim) | Existing focus, Enter activation and native-viewer checks retained; selector data is not JavaScript source |
| `explainer/sources.mjs` | Reject explicit citation revisions conflicting with the document pin before fallback handling (upstream unchanged at v3.3.0, so the local bytes carry over unchanged) | Same-pin excerpts, explicit old document pins, inferred HEAD and no-repository plain references retained; two-commit regression covers silent revision replacement |

These are bounded local safety/correctness adaptations, not a new upstream version or an extra skill capability. The source commit, source digests and licenses remain pinned; packaged digests and each migration disposition describe the actual local bytes. Regression code lives in repository-level `tests/test_archify.py`; immutable upstream tests remain separate evidence.

## Retained third-party notices

The package retains JetBrains Mono's SIL OFL notice and every upstream notice. The explainer bundles the unmodified Pele 1.3.0 chart subset under `explainer/vendor/pele/`; its MIT license (kepano, 2026), npm tarball provenance, and embedded Lucide `rotate-ccw` ISC notice remain beside the bytes. The Story scanner vendors parse5 7.3.0 and entities 6.0.1 under `story/vendor/` with their licenses; the Code Analysis module vendors its parser and schema packages and records the SARIF 2.1.0, CodeQL fingerprint and three.js r128 notices in the package `THIRD_PARTY_NOTICES.md` beside their retained license files. Delivered charts stay static SVG unless a Story page plays them.

## Fidelity classification

Classification: `faithful` — upstream native-diagram, explainer, Code Analysis, story and PR-attachment capabilities are retained; canonical naming, interaction/receipt boundaries, standalone packaging and source records do not add a separate capability implementation. Internal runtime identities follow the actual source. Skill-standard §2.3.

The previously accepted CodeQL finding in `delta/architecture-delta.mjs` is unchanged by this pin move (the flagged `esc` construction is byte-identical at v3.3.0); no remediation claim is made. It remains an offline authoring-helper limitation recorded in the compatibility map.

## Reproducible source check

```bash
git clone https://github.com/tt-a1i/archify /tmp/archify-upstream
git -C /tmp/archify-upstream checkout af3aaf3c36762f2afb62a4a09533f6c7273b07e5
shasum -a 256 /tmp/archify-upstream/archify/SKILL.md /tmp/archify-upstream/archify/LICENSE /tmp/archify-upstream/archify/LICENSE-MIT
```

Compare the original import, the previous pin, the local package and the exact new tag before changing the pin. Retain the packaging exclusions and local wrapper, regenerate the complete source/local digest manifest, run the package integrity and behavior regressions, and verify real browser behavior before making a browser-quality claim. A default-branch commit is not a substitute for stable-release evidence.
