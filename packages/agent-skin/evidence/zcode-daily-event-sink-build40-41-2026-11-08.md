# ZCode daily event sink + identity-readiness wait — build 40/41 receipts (2026-11-08)

Scope: the daily double-click launcher (LSUIElement, `local.azhou.zcode-startup`) gained a host-scoped
startup-event journal, and the cold-start identity re-validation that the journal exposed as a transient
failure was replaced with a bounded readiness wait. Branch `codex/agent-skin-daily-event-sink`,
commits `f331dd7` (sink, build 40) and `6e1b629` (readiness wait, build 41). Lease
`804f2bbc13bf3478541c94b2165a9dbe` (holder `agent-skin-daily-event-sink`).

## Incident that motivated the work

2026-11-08 15:21 (build 39): the driver cold-launched ZCode (receipt written, CDP listening) but no skin
landed and the driver exited silently — daily-mode diagnostics were impossible because every launcher
event went to stdout, which Finder discards for an `LSUIElement` app. Port conflict was ruled out
(`allocateLoopbackPort()` binds `127.0.0.1:0`); the failure stage could not be determined.

## f331dd7 — daily event sink (build 40)

- `StartupLogPolicy.filePath(arguments:dailyEventDirectory:)`: explicit `--log` keeps priority; a plain
  launch now falls back to `~/Library/Logs/AzhouZCodeStartup/events.jsonl` (`AzhouCodexStartup` for the
  Codex host); `--probe`, `--preview`, `--smoke-test` never touch the daily file.
- The sink opens through a WallpaperJournal-grade handle: `O_NOFOLLOW`, 0700 dir / 0600 file, 2 MiB
  in-place truncate bound, append-only JSONL (`azhou-startup.event.v1`).
- 9 new checks in `tools/test-startup-native.py`; `runtime_build` 40; three READMEs synced (also
  removing a stale duplicated build-35 span that had survived the #395 merge in `README.zh-CN.md`).

The journal immediately paid for itself during acceptance:

| time | launcher PID | stage | reason |
|---|---|---|---|
| 16:35 ×4 | 29378/29407/29417/30469 | `open-proof` | `asset-invalid` — maintainer stamp error: `payloadSHA256` must be `sha256(startup/install.js)` (verified against the retired build-39 bundle: `7f45d4bf…`), not the build-output sha256Tree fingerprint |
| 16:44 | 43374 | `validate-process` | `target-identity` — transient: the same binary passed on the 16:58 cold start |
| 16:58 | 61376 | full chain | `open-proof → open-request → controller-ready → startup-ready`, exit 0 |

Post-build stamping also breaks the ad-hoc seal; every install is re-signed
(`codesign --force --sign -`) and re-verified before handoff.

## 6e1b629 — identity readiness wait (build 41)

The assembly re-queries the freshly opened host with a new `NSRunningApplication`; a host that has not
finished LaunchServices registration fails that one-shot snapshot. `settledValidate` now:

- polls every 100 ms inside the unregistered window, bounded by an 8 s clock budget **and** an
  80-attempt cap (the cap also bounds a static unit-fake clock);
- refuses a confirmed different bundle identity immediately (transient vs permanent split);
- emits `zcode-validate-identity-refused {observed, expectedPID, expectedLaunchTime}` before the final
  refusal, so the next anomaly is diagnosable from the journal alone;
- keeps the `kernelReady` one-shot path unchanged; assembly validate/activate closures become async.

## Gates

- `tools/test-startup-native.py`: **697 checks passed** (build 40: 693 + sink suite; build 41 adds the
  identity-wait suite — unregistered host awaited, confirmed mismatch refuses fast, final refusal
  reports observed state).
- `tools/test-zcode-native.py`: `passed: true` (build 40 and 41).
- `scripts/verify.py`: exit 0 after each change.
- Build 41: `tools/build-macos.sh --host zcode` exit 0, payload fingerprint `45d01211…`;
  `startup/install.js` embeds the build number, so its digest is per-build (build 40 `7e9d40cd…`,
  build 41 `c07fdd53…`) — the stamp must always use the freshly built digest.

## Real-host acceptance (build 41, daily profile, 2026-11-08 evening)

Cold start via double-click: `launcher-start → zcode-open-request{port 64486} → zcode-open-selected-process{hostPID 62079}
→ zcode-target-summary → zcode-page-bound → zcode-controller-ready → startup-ready` in 2.67 s, exit 0;
no refusal events. CDP probes against receipt port 64486: `data-azhou-wallpaper=active` with 2 surfaces
(full window 1512×889 + main pane 1171×832), and the sidebar entry present inside its shadow root
(`label "Azhou Appearance"`, avatar, 316×44 at y=168, inside the sidebar). Maintainer visual
confirmation: wallpaper and entry seen in the daily window.

Probe-tooling note: the entry lives in a shadow root, so `textContent`/`innerHTML` probes (including
`.local/zcode-rc35-20261105/probe-live-dom.mjs`) are blind to it — query
`[data-agent-skin-entry]` + `shadowRoot` instead.

## Post-acceptance commit: deadline-bounded identity wait

The PR review (P2) noted the readiness wait started a fresh 8 s budget regardless of the caller's
operation deadline, so the hot branch could wait past its deadline and still activate. The follow-up
commit threads the operation deadline through `validateProcess`/`activateExisting`, caps the identity
wait to the remaining budget (`deadline-exhausted` refuses immediately with its own diagnostic event),
and re-checks the deadline before the hot branch returns `.activated`. Gates re-run after the commit:
`test-startup-native.py` 699 checks, `test-zcode-native.py` passed, `scripts/verify.py` exit 0. The
installed build 41 predates this cap (a rare, bounded overshoot inside the unregistered window only);
the cap ships with the branch and rides the next stamped build.

## Known leftovers

- The retired build-39 app is preserved at
  `.local/zcode-build40-20261108/retired-build39.app`; build 40 is rebuildable from `f331dd7` and was
  not backed up separately.
- `azhou-install-registry register` still refuses the ZCode bundle identity (installer CLI is
  Codex-only); the ZCode entry remains installed-but-unregistered, same as build 39.
- The rc34 worktree lease and its `assets/private`/`.local` evidence remain held pending the maintainer
  decision recorded in the roadmap.
