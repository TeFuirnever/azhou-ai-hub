# Live DSH settings-section verification — 2026-11-07

Question (user): wallpaper fixed, but was "Azhou appearance" not supposed to appear in the Settings page?

## Verdict

Row present and panel mounts, on both carriers, zero console errors.

## Evidence

### Web repro carrier (azhou-skin-web profile, headless Chrome via CDP)

Loop: `/tmp/run-settings-loop.sh` boots `dsh azhou-skin-web --no-open --port 0`,
`/tmp/settings-loop.mjs` opens the Settings surface and asserts.

```
SANITY {"keys":["owner","version","install","status","openSettings","mountSettings","retryWallpaper","dispose"],"wallpaper":null}
TRIGGERS [{"tag":"button","label":"More","haspopup":"menu"},{"tag":"button","label":"Account menu","haspopup":"menu"}]
OPEN {"stage":"clicked","label":"Settings⌥⌘,"}
NAV {"dialogOpen":true,"azhou":true,"pet":true,"rows":["Account","General","Models","Built-in plugins","Agent presets","Pet Config","Azhou appearance","Open configuration file","Close","More account information","View usage","Top up"],"anywhere":true}
VERDICT row=true pet=true mount=true
CONSOLE_ERRORS none
```

### Real desktop carrier (DeepSeek Harness.app, pid 95413, started 15:52:30)

Process start (15:52) is after the candidate rebuild (15:44), so the running app
loads the merged-fix build. Plugin reached through the profile symlink
`~/.dsh/profiles/desktop/node_modules/azhou-agent-skin -> ~/azhou-agent-skin-candidate/azhou-agent-skin`.

Driven with agent-desktop + System Events (window w-3528):

- Account row (bottom left, `{150,953}`) opens the account menu
  (Settings ⌘, / Feedback / Sign out). Menu item screenshots:
  `/tmp/menu-open2.png` (cropped), `/tmp/desktop-acct.png`.
- Settings item clicked at screen `{80,835}` (window screenshot y/2 + 33 menu bar):
  modal opens with left nav `Account, General, Models, Built-in plugins,
  Agent presets, Pet Config, Azhou appeara…` — screenshot `/tmp/desktop-modal6.png`.
- "Azhou appearance" row clicked: panel mounts inside the dialog —
  "Azhou · Theme & Appearance, Running: 0.9.0 · build 35", tabs
  Workspace background / Startup animation / About & status, wallpaper
  thumbnail, Choose background image, Background strength slider (42),
  Restore all defaults / Cancel / Save — screenshot `/tmp/desktop-panel.png`.

## Notes

- Desktop Settings entry is the bottom-left account-row menu, not the More menu.
- Row label follows app locale: English UI renders "Azhou appearance";
  zh UI renders 阿舟主题与外观.
- PR #385 (`inject: ['slots']` activation fix) merged as 9249a54 before this run.
- Sign-out dialog misclick during driving was cancelled with Esc; session intact.

## Follow-up: sidebar capsule removed (#386, merged 481c5f3)

The bottom-left 阿舟 capsule was removed on DSH after the settings panel
covered its two instant actions. `createDSHPageAdapter` now honors a
top-level `sidebarEntry` configuration flag; both DSH payload builders emit
`sidebarEntry: false`, returning one inert frozen handle from `mountEntry`.

The settings-loop gained an entry-absence check sampled across the
post-animation reveal window (a pre-reveal entry is detached and invisible
to `querySelector`, which produced one false negative). Observed runs:

- Misnested flag (first attempt, caught by review): `ENTRY appeared=true`,
  `entryGone=false` — red, capsule still mounted.
- Corrected: `ENTRY appeared=false`, `VERDICT row=true pet=true mount=true
  entryGone=true`, zero console errors — green.

CI note: one coverage run failed on `ZCodeSkinDriverTests.swift:87`
(lock/cancellation precondition) with no Swift files changed; the failed-job
rerun passed — timing flake, not a regression. Candidate rebuilt from
merged main as 0.9.0 build 35; the capsule disappears after the next app
restart.
