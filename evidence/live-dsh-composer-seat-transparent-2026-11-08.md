# Live DSH composer seat transparency verification — 2026-11-08

Follow-up to [live-dsh-pagebar-desktop-2026-11-08.md](live-dsh-pagebar-desktop-2026-11-08.md):
the DSH composer seat under-fade (`[class*='composerSeat']`, painted
`transparent → base-color 36px` by the host once a session is active,
`[data-phase='active']`) covered the wallpaper below the input card with a
flat opaque band. #404 (squash `6f62dcc`) drops it with
`background-color: transparent; background-image: none`, matching the ZCode
and ChatGPT hosts, which render the wallpaper around the composer with no
fade.

## Observed

- Headless DPR2 active session (1336×784@2): seat computed
  `background-image: none`, `background-color: rgba(0,0,0,0)`; pixels below
  the composer at full wallpaper brightness `(117,61,35)…(144,74,37)`. The
  rejected 78% intermediate fade measured `(42,29,25)`; the pre-fix band read
  flat `(21,21,23)/(44,44,46)`.
- Real desktop carrier (window 1512×888@2x): wallpaper flows around and below
  the composer at full brightness (dress and floor visible) and the
  dock/status text stays readable; verified with an agent-desktop window
  capture.
- Parity reference: `extension/hosts/zcode.mjs` already renders all surfaces
  fully transparent and the Codex host has no composer fade; no other host
  needed a matching rule.

## Notes

- The canonical change landed through PR #404 (CI 15/15 green,
  `scripts/verify.py` passed before push). During the round the desktop
  profile ran an equivalent in-place patched client.js; re-run
  `tools/build-dsh-plugin.py` and the installer to align the installed
  artifact with the canonical build when convenient.
- `assets/private/` stays git-ignored, so `tools/build-dsh-plugin.py` needs
  the maintainer checkout with the icon input present.
