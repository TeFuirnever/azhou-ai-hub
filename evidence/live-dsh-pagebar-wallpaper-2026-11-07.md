# Live DSH page-header wallpaper layer fix — 2026-11-07

User report (screenshot): on the real desktop Plugins page the header band
(title, subtitle, Installed/Discover tabs, Refresh/Add plugin) rendered on an
opaque black strip while the rest of the page showed the wallpaper.

## Root cause

`elementsFromPoint` at the band returned no painter: the strip is painted by
`w6M7KW_pageBar::before` (position:absolute, `rgb(21,21,23)`), a pseudo
element of the shared page-header bar pattern. The wallpaper ports'
transparentization list never included pseudo elements. The same sweep found a
second opaque painter on standalone pages: `section.CDG4uW_page`
(Automation tasks paints its whole content area opaque; the `_page` CSS-module
container). Neither layer is covered by the chat-view-tuned selector set.

## Fix (PR, hosts/dsh.mjs wallpaper.css)

Two additive rules, both gated on `html[data-azhou-wallpaper="active"]` and
scoped inside `#root`:

- `#root [class*="pageBar"]::before` — background transparent, image none.
- `#root section[class$="_page"]` — background transparent, image none.

The suffix after the CSS-module hash is the stable half of the class name.

## Evidence (azhou-skin-web repro profile, CDP, build 0.9.0 build 35 + fix)

- Plugins: `pageBar::before` computed `rgba(0,0,0,0) / none`; large painters
  reduced to the sidebar surfaces (`PIRFFq_sidebarCol`, `kB3qhq_root` —
  unchanged by design). Screenshot `/tmp/multipage-1.png`: wallpaper visible
  through the header band, text readable.
- Automation tasks: `section[class$="_page"]` computed transparent; large
  painters reduced to the sidebar surfaces. Screenshot
  `/tmp/multipage-2.png`: whole page shows the wallpaper.
- Controller status after skip: `wallpaper.applied:true`,
  `backgroundMatched/washMatched/coverMatched/rootClear` all true — the added
  rules do not break the layer checks.
- `python3 tools/verify-artifacts.py --verify-dsh-plugin` exit 0 on the
  rebuilt candidate.

## Driving note

Probes must skip the startup animation (click `[data-agent-skin-skip]` inside
the overlay iframe) and wait for the overlay iframe to be removed BEFORE
navigating; earlier probes sampled mid-animation and mis-identified the
overlay as the page content. `data-azhou-wallpaper` stays active across
navigation to Plugins and Automation tasks (attribute checked 0.5s/2s/3.5s
after nav) — no teardown on standalone pages.
