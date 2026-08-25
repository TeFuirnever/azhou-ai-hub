# Provenance and composition boundary

## Immutable sources

### Caveman capability source

- Upstream: `JuliusBrussee/caveman`
- Repository: <https://github.com/JuliusBrussee/caveman>
- Commit: `11ddc0c9813c8f75365cd5be2f753df08712f154`
- License: MIT, retained at `LICENSES/Caveman-MIT.txt`
- Imported: 2026-08-23

The requested import basis was a user-provided local set containing the `caveman` core plus six companions: `cavecrew`, `caveman-commit`, `caveman-compress`, `caveman-help`, `caveman-review`, and `caveman-stats`. Every local entry file is content-addressed in `benchmarks/super-caveman/capability-map.json` and traced separately to the pinned upstream commit. `cavecrew`, `caveman-commit`, and `caveman-review` are byte-identical to that commit. `caveman`, `caveman-compress`, `caveman-help`, and `caveman-stats` are local derivative snapshots with different hashes; they are not represented as upstream bytes.

The derivative deltas cover response-mode wording, backup placement, platform-specific help, and statistics-overhead reporting. Super Caveman keeps their requested capability intent while replacing unsafe or host-specific behavior through the adaptation boundary below.

### ADHD-friendly response source

- Upstream: `ayghri/i-have-adhd`
- Repository: <https://github.com/ayghri/i-have-adhd>
- Commit: `b42a45a068e080294924bfba19a7a2e8944c48ff`
- Source file: `skills/i-have-adhd/SKILL.md`
- Source SHA-256: `938d0e350a0c2b0e2e6c3a9032542e062846d108e0f89dd27c798ba5b436397e`
- License: MIT, retained at `LICENSES/i-have-adhd-MIT.txt`
- Imported: 2026-08-23

## Local composition

`super-caveman` is one independently installable package:

- Caveman core supplies terse intensity and technical-token preservation.
- Six Caveman companions supply delegation, commit, review, compression, help, and statistics routes.
- `i-have-adhd` supplies its complete pinned output-behavior contract: persistence and stop semantics, all ten response rules, task and safety exceptions, and pre-send checks.

The complete response-behavior contract runs before Caveman compression. This keeps output executable without weakening the original terse-mode focus.

## Adaptation boundary

Local changes:

- replace Claude-only presets with capability-based delegation;
- replace model-specific compression subprocess/API calls with active-agent transformation plus deterministic guards;
- keep backups outside the source tree and add checkpointed no-clobber install/verified restore receipts;
- report statistics only from audited counters or explicitly authorized compatible logs;
- retain old Caveman commands only as compatibility triggers;
- fully adopt the pinned output-behavior semantics, covered by the original fourteen evaluation cases plus five closure cases, without installing upstream hooks, plugin adapters, global configuration, or persistence files;
- make no diagnosis or medical claim from response-style use.

Omitted upstream README files, model-specific package metadata, generated evaluation outputs, hooks, and separate alias packages are not runtime capabilities of this neutral skill.

## Reproducible update

1. Fetch both upstream repositories at immutable commits.
2. Hash the seven pinned Caveman entry files, the seven user-provided local entry snapshots, and `skills/i-have-adhd/SKILL.md`.
3. Compare both Caveman hash sets, their lineage labels, `benchmarks/super-caveman/capability-map.json`, and response fixtures.
4. Update one isolated candidate and its regressions.
5. Run repository verification and exact-diff human review before promotion.
