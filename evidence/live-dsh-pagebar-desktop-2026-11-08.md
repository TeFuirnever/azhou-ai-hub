# Live DSH page-header wallpaper verification after restart — 2026-11-08

Follow-up to [live-dsh-pagebar-wallpaper-2026-11-07.md](live-dsh-pagebar-wallpaper-2026-11-07.md):
the user restarted DeepSeek Harness (new process group, started 13:30, loading
the 0.9.0 build 39 candidate assembled from `be13740`) and agent-desktop
verification confirmed the fix on the real desktop carrier.

## Observed

- Home view: wallpaper active; the sidebar 阿舟 capsule is gone
  (`sidebarEntry: false` live since #386).
- Plugins page (window temporarily enlarged from the user's mini-window for a
  full-resolution capture, [live-plugins6.png] evidence in session): the
  header band — title, subtitle, Installed/Discover tabs, Refresh/Add plugin —
  shows the wallpaper with no opaque strip; text readable.
- Automation tasks page (mini-window capture): wallpaper across the page,
  consistent with the repro-carrier CDP verification in the 2026-11-07
  receipt.
- The user resized the window back to mini during verification; the window
  was left in the user's control.

## Notes

- No repo changes; this receipt records the live-desktop round only. The fix
  itself is #393 (`be13740`).
- Issue #390 (flaky Swift coverage leg) was closed the same day: #391
  synchronized the cancellation fixtures and a 10-consecutive-green acceptance
  loop ran on the unchanged `c2ebcc8` tree; a `/tmp`-symlink dual-path-form
  coverage-export artifact was documented there as local-only.
