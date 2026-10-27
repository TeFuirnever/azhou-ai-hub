# Hub monorepo migration — 2026-10-26

## Result

The Hub now maintains the three projects under `packages/`. Their development source no longer depends on the old sibling checkouts. Existing canonical packages under `skills/` retain their independent installation paths and contracts.

| Package | Imported basis | Maintenance and delivery |
| --- | --- | --- |
| [pstack-agent-harness](../packages/pstack-agent-harness/UPSTREAM.md) | Commit `356c6e0f978df729eb16f227d795f34d221c5aad`; all 373 tracked source files, with documented migration edits | Native toolchain and version retained; MIT notices retained |
| [agent-orchestration-kit](../packages/agent-orchestration-kit/UPSTREAM.md) | Local continuation commit `4d1a2081f96cdab8a9ea0fe3d357312471546dcc`; all 75 tracked files, with package documentation adaptations | Native transactional installer and profiles retained; Apache-2.0 retained |
| [codex-startup-animation](../packages/codex-startup-animation/UPSTREAM.md) | Base `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248` plus the maintained dirty worktree; active source, tools, tests and docs, version `0.7.1` / build `8` | Fork attribution retained; no open-source grant recorded; user is contacting the upstream maintainer. Private media and deprecated extension paths excluded |

`hub-package.json` declares runtime paths without tracked per-file hash locks. The existing `integrations` commands resolve canonical in-repository packages by default. Plans fingerprint current package inputs; applying a stale plan fails before native execution. Private installation snapshots embed their input manifest so receipt-owned cleanup can still operate after development source changes or disappears. Snapshots are installed runtime state, not a second development source.

The external `integrations/*/source-lock.json` files were removed. Original commit fields are import provenance, not the current Hub revision. Package versions remain independent; this migration does not create a release or reset upstream versions. CI now includes the package Python gate, the pstack native suite and the macOS wallpaper validator.

## Verification

| Check | Observed result |
| --- | --- |
| `python3 scripts/verify.py --print-summary` | All 8 gates passed: repository policy, 582 Hub unit tests, package gate, three registered benchmark-integrity suites, working and staged whitespace |
| Package Python gate | 42 orchestration tests and 21 isolated animation-installer tests passed; macOS commands in installer fixtures are mocked |
| Integration boundary tests | 77 passed, including source changes after plan validation, stale animation payloads, identical inputs from another checkout, and cleanup after live source removal |
| pstack full native suite | 1310 passed, 36 skipped, 0 failed; Bun `1.3.14`, frozen package dependencies and isolated Pi `1.1.0` matching the upstream CI prerequisite |
| pstack generator | 85 generated files current after import and EOF normalization |
| Animation additional checks | 34 pet tests and 97 compiled Swift wallpaper-validation checks passed; shell/Python/JavaScript syntax and package paths checked |
| Independent review | Fixed the reviewed-plan/snapshot race and both animation payload identity cases; bounded independent recheck found no remaining material issue in those fixes |
| Fresh staged-tree export | Catalog and help for all 3 entries passed; pstack/router dry-run plans and animation source check used only the export's `packages/`; no installation-target writes or private media exported |

The initial full run found a regression-test expectation still being corrected and imported EOF whitespace; these were resolved before the final passing gate. The fresh-export fixture initially supplied a symlinked Python executable as a stand-in native executable; retrying with its resolved path satisfied the adapter's explicit non-symlink contract.

## Limits

- This is local migration and validation. No remote push, public release, global installation, Codex restart or live appearance change was performed.
- The animation package has no recorded source redistribution grant. Attribution does not replace permission; the Hub license does not cover that package. The user will contact its upstream maintainer before external distribution.
- Private image, scene, wallpaper and icon inputs were intentionally excluded. Full app build, real host handoff and wallpaper visual acceptance were not rerun.
- Native package lifecycle suites are explicitly unvalidated on Windows; package metadata is still checked there. Python `3.11`, hosted CI and `actionlint` were not available as local validation environments.
- Original source directories were read-only during this work and retained as recovery sources. The animation import was compared against current source bytes and modes; no pre-migration byte digest exists, so no historical byte-level unchanged claim is made.

See [integration operations](../docs/integrations.md), [provenance and updates](../docs/integration-provenance.md) and the [support matrix](../docs/support-matrix.md).
