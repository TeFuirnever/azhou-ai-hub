# Agent Skin E2E incident regression index (L6, 2026-11-08)

Source: the 2026-11-08 edition of the design document
`.planning/agent-skin-e2e-test-system.md` (maintainer-only and git-ignored; read it
from the maintainer checkout by absolute path). This page is the in-repo L6 landing
of its incident list: one named regression per incident family, where a failing
guard cites the original evidence instead of exiting quietly. The "this round"
column records what the 2026-11-08 E2E-system change (E1-E5) added on top of the
guards that already existed.

## Layers and entries

| Layer | Entry |
|---|---|
| L0 static gate | `tools/check-private-assets.py` against `tools/private-assets.MANIFEST.expected` (first `quick` step) |
| L1 unit | existing `tools/test-*.py` suites (identity-wait series landed with build 41) |
| L2 synthetic integration | trap-state contract exercised through the L5 audit (see F6) |
| L3 artifact integrity | `tools/ship-zcode.py`, guarded by `tools/test-ship-zcode.py` |
| L4 disposable cold start | `tools/e2e-cold-start.py` |
| L5 daily double-click | `tools/e2e-daily.py` |
| Runner discipline | `tools/e2e.py --layer quick\|cold\|daily\|all` |

`python3 tools/e2e.py --layer quick` is the per-PR tier: the L0 private-asset gate
plus the two E2E-family unit suites, cheapest first, fail fast. It is wired per PR
as the `agent-skin e2e quick layer` suite inside `scripts/verify_packages.py`
(reached from `scripts/verify.py` and the CI `tests` job), so tool regressions fail
the repository gate instead of waiting for someone to remember the manual command
(P8.1). `tools/private-assets.MANIFEST.expected` ships in Git (outside the assets tree, which repository
policy keeps free of tracked files) to make that wiring possible
on every checkout: wherever `assets/private` holds any artwork the gate is strict
(existence, non-symlink form, optional sha256 baselines), and an artwork-free
checkout — the CI shape — passes in an explicit `fresh-checkout` mode that names
itself in the report instead of failing structurally red. `cold` and `daily`
touch a real host, so both default to `--plan` (no process is started) and only run
for real behind an explicit `--execute` with a loud warning. The runner asserts on
startup that the working directory's git toplevel equals its own worktree, runs
every child without an intermediate pipe so the first failing exit code reaches the
caller untouched, and appends its own record to `.local/e2e-run.jsonl`.

## Incident families

| Family | Representative incidents | Guard layer | Guard file or command | This round's new guard |
|---|---|---|---|---|
| F1 host identity / version drift | P1.1 build 34: host auto-update past the pinned fingerprint failed closed with no process, log or dialog; P1.2 the fingerprint refusal was invisible before the journal existed | L4/L5 | `tools/e2e-cold-start.py`, `tools/e2e-daily.py` — journal event-chain verdicts | `zcode-validate-identity-refused` is a refusal stage in both chain verdicts, so a mismatched host turns the run red instead of silently exiting (journal capture itself landed with build 40) |
| F2 timing races ("world not ready when checked") | P2.1 rc36 surface assert raced a hidden page at 1.3 s; P2.2 2026-11-08 one-shot `NSRunningApplication` re-query hit an unregistered window; P2.3 rc38 animation-completion flake; P2.4 a killed host auto-relaunches with its debug port | L1 + L4/L5 | L1 identity-wait suite (`tools/test-startup-native.py`, build 41); `tools/e2e-cold-start.py`, `tools/e2e-daily.py` | both E2E layers assert the ordered, complete, refusal-free chain; the bounded readiness wait (8 s budget / 80 attempts) remains the launcher-side fix landed with build 41 |
| F3 artifact integrity / assembly | P3.1 `payloadSHA256` stamped with the wrong object (4x `asset-invalid`); P3.2 `startup/install.js` embeds the build number so the digest is per-build; P3.3 post-build Resources edits break the ad-hoc seal and `.build` residue breaks the next codesign; P3.4 a fresh worktree lacks `assets/private` | L3 (core) + L0 | `python3 tools/ship-zcode.py` (`--dry-run` plans, a real stamp needs `--evidence`): clean-residue, build, stamp, codesign, codesign-verify, verify-stamp; `python3 tools/check-private-assets.py` for P3.4 | both tools: `payloadSHA256` is always the freshly measured `sha256(startup/install.js)` and is re-measured after signing; missing private assets fail at L0 with a maintainer-worktree copy hint |
| F4 observability gaps | P4.1 before build 40 a failed daily double-click left zero diagnostics ("clicked, nothing happened, guess") | L4/L5 prerequisite | the `events.jsonl` journal (build 40) that the E2E verdicts consume | the E2E layers assert on journal increments; the runner applies the same standard to itself via `.local/e2e-run.jsonl` |
| F5 probe / tool blind spots | P5.1 the entry chip lives in an open shadow root, invisible to `textContent`/`innerHTML` probes; P5.2 ZCode overwrites argv with `process.title` so pgrep-by-path is blind; P5.3 the working probe lived only in an untracked `.local` worktree | L4/L5 tooling | `tools/probe_dom.mjs` (shadow-aware, read-only, git-owned); `tools/e2e-daily.py` follows the receipt pid/port instead of pgrep | both: the probe queries `[data-agent-skin-entry].shadowRoot` and is invoked by both E2E layers; daily identity resolution reads the receipt, not the process list |
| F6 state consistency (trap states) | P6.1 driver died between receipt write and injection: receipt present, skin absent; P6.2 receipt, port, process and DOM were never cross-audited | L2 + L5 | `tools/e2e-daily.py` `audit_four_way` (receipt, lsof listener, process liveness, probed DOM) | the four-way audit and the P6.1 trap-state red (with cold-restart advice) landed this round; the L2 synthetic crash simulation was folded into this contract rather than shipped as a separate fixture |
| F7 idempotence / re-entry | P7.1 rc38 nested groups made `parentElement!==sidebar` always true: `position()` re-inserted forever and an observer rescheduled itself | L1 + L5 | L1 nested-group re-insert assertions (pre-existing); `tools/e2e-daily.py` `assert_idempotent_second_click` | the daily double-click idempotence verdict: the second click must be exactly `launcher-start -> target-activated -> launcher-exit` with no injection replay |
| F8 process / environment | P8.1 build 36: tests ran in the main checkout against changed worktree code (fake green); P8.2 a gate pipeline ate exit codes (`verify.py \| tail` then chained commands); P8.3/P8.4 rc35-era debugging rounds and leftovers | runner | `python3 tools/e2e.py` | worktree pinning (`git rev-parse --show-toplevel` equality), pipe-free child execution with exact exit-code propagation, self-journaling of every run |
| F9 registration / install ownership | P9.1 `azhou-install-registry register` accepts only the Codex identity, leaving the ZCode entry installed-but-unregistered; P9.2 the ZCode install was a manual cp+codesign with no audit tool | L3 (+ registry CLI as a separate task) | `python3 tools/ship-zcode.py` full-chain receipt; an explicit `--install` is the only path that writes `~/Applications` | the manual cp+codesign path is replaced by the receipt chain; P9.1 registry registration remains uncovered and stays a separately tracked task |
| F10 data / assets | P10.1 `assets/private` is untracked by design, with no expected-file list to fail early | L0 | `tools/private-assets.MANIFEST.expected` + `python3 tools/check-private-assets.py` (first `quick` step) | both: the manifest ships in Git; wherever any artwork is present, existence, non-symlink form and optional sha256 baselines are strictly checked, so a partial or drifted maintainer copy fails at L0 instead of late inside a build, while artwork-free checkouts pass in the explicit fresh-checkout mode |

## New-incident procedure

1. Record the incident with its evidence receipt before touching code.
2. Register it here: extend an existing family row or open the next `F<n>`, and
   name the guard layer and file or command that will hold the regression.
3. Fix, then land the named guard; a guard that fails must cite the original
   incident receipt in its output.
