# Agent Skin DeepSeek Harness plugin contract

This page is reference for the `azhou-agent-skin` DSH plugin package. It records what the package contains, how the client module behaves, and what is deliberately absent. Build and evidence commands live in the [assembly receipt](../../../evidence/dsh-agent-skin-assembly-2026-11-05.md).

## Package layout

`python3 -B tools/build-dsh-plugin.py` from `packages/agent-skin/` assembles `.build/azhou-dsh-plugin/azhou-agent-skin/`:

| File | Role |
| --- | --- |
| `package.json` | `dsh.bundle.patch` → `./cordis.patch.yml`; `dsh.client` `{platform:"web", immediately:true, inject:[]}`; exports `.`, `./client`, `./locale/*.json`, `./package.json` |
| `cordis.patch.yml` | One insert row `id: azhou-agent-skin`, `name: 'azhou-agent-skin'` |
| `index.js` | Host half, the official no-op `export function apply() {}` |
| `client.js` | `window.__ModuleLoader__.load` factory embedding the neutral core plus `createDSHPageAdapter` and the bootstrap wiring |
| `locale/{zh,en}.json` | Plugin Manager `meta.title` and `meta.description` |
| `icon.png` | 256×256 PNG generated from the theme icon input, within the 256 KiB limit |
| `manifest.json` | Build receipt: source inputs, per-file digests, `targetHost: dsh`, the no-install scope string |

The emitter reuses `build_startup(host='dsh')` from `tools/build-startup.py` for the payload body, so the animation, settings, and wallpaper code is the same neutral core the Codex and ZCode payloads embed. The DSH page adapter is `extension/hosts/dsh.mjs`.

## Client module behavior

`client.js` registers one factory whose module exports `{apply, inject}` with `inject: ['slots']` — the cordis service the settings-section registration reads; an undeclared access would throw and fail activation. `apply(ctx)` does the following, in order:

1. Returns `{installed:false, reason:'page-unsupported'}` unless the page shows the DSH boot graph, a top-level window with `__ModuleLoader__` and an own `__DSH_BOOT__` data property.
2. If the document is still loading, waits for `DOMContentLoaded` and returns `{installed:false, reason:'dom-loading'}`; the wait listener is registered through `ctx.effect` and returns its own disposer.
3. Creates the page adapter with one disposal sink. The sink wraps each disposal function as `ctx.effect(() => () => fn(), label)`, because cordis runs an effect callback immediately and uses its return value as the disposer. The adapter's `registerCleanup` and the controller's owner-checked `__azhouStartup` disposal both route through the sink, so deactivating the plugin removes the entry, observers, overlay, and wallpaper.
4. Registers the settings section once through `ctx.effect` (see "Settings page" below).
5. Runs the bootstrap tail with the page adapter configured `sidebarEntry: false`. The host Settings modal is the only appearance entry on this carrier; the adapter returns one inert frozen handle so the controller's optional entry calls stay safe with no DOM node, observer, or timer. Animation visibility follows the controller's existing flow; the plugin adds no new trigger policy.

The wallpaper surface is the unique `[data-slot='main']` element. The page adapter still implements the full imperative entry handle (stable sidebar column beside the `[data-slot='sidebar.footer.action']` container, never inside the React-rendered slot list) for builds that pass `sidebarEntry: true`; the emitted payloads pass `false` because the settings-section slot replaced the capsule's two instant actions — animation replay lives in the panel's Startup animation tab (preview), wallpaper retry in the panel's apply/save path. Theme comes from `data-ds-dark-theme` on `body` and the `--dsw-*` token variables the host writes inline on `body`. Settings persist in IndexedDB under the `azhou-dsh-startup` namespace, separate from the Codex and ZCode databases.

## Settings page

The client also registers one `settings.section` slot row — `id: azhou-appearance`, `order: 40`, label 阿舟主题与外观 / Azhou appearance — the same slot contract dsh-pet uses for `pet-config`. React comes from the module loader's platform table (`require('react')`, `require('react/jsx-runtime')`); when that table lacks React the registration degrades silently and the overlay stays the settings UX. The section renders a transparent container capped at 720px with `--dsw-alias-*` tokens and, on mount, calls `mountSettings(container, { onClose })` on the `window.__azhouStartup` controller, which places the same panel iframe the overlay uses — same payload document, same settings namespace, same message channel — sized to fill the container with no fixed positioning or backdrop. Keyboard behavior inside the embed stays the standalone dialog's: while focus is inside the iframe the panel dialog owns Escape, so Escape closes the dialog, sends `settings-close`, tears the embed down, and focus returns to the host settings navigation — the host modal does not own Esc while the embed has focus. A panel `assetError` (any reason, before or after the panel opens) tears the embed down the same way and notifies `onClose`. The v1 limitation: the embedded presentation still reuses the standalone dialog's focus handling (a modal focus trap inside the iframe); a non-modal embedded presentation is the tracked follow-up issue. The controller admits the method only on hosts whose page adapter declares the wallpaper ports group, so on Codex it stays inert. Mounting returns a disposer; the section calls it on unmount, the disposer is idempotent, and a panel-driven `settings-close` (or cancel) notifies `onClose` — wired to the shell-provided `close` prop — and tears the embed down itself, so settings-modal open/close cycles mount and dispose cleanly with no duplicate iframes or leaked message listeners.

## Adapter capability groups

Since commit `5b9ea50`, a page adapter declares host behavior instead of neutral files branching on host names. `controllerWallpaper` carries `{owner, requiresControllerMetadata}`; a `wallpaper` ports group carries `{validPage, shellState, surfaces, attributes, css, scope}` and is atomic, an adapter that declares it partially is refused as `invalid-host-adapter`. An adapter without the group keeps the built-in Codex anchor path, which the standalone wallpaper payload and the preview fixture still use. The baseline key `zcodeAttributes` in `wallpaper/renderer.js` keeps its name verbatim so live 0.9.0 ZCode installations transfer recorded baselines across a replacement.

## Deliberate limits

- The default wallpaper is the payload's frozen `DEFAULT_ASSETS` artwork (1536×1024, `wallpaperStrength: 42`), the same object the Codex and ZCode payloads embed, and the controller applies it on first run; the live-host receipt observed it applied with all layer checks clear. Heavier additional artwork should not ride `client.js`: a follow-up can serve it from a host-half `webServer` prefix route, the pattern both installed third-party skins use.
- In-host rendering is verified to the machine level. The [live-host receipt](../../../evidence/live-dsh-plugin-host-2026-11-05.md) records the controller registered, the animation completing naturally, the sidebar entry mounted in the real column (2026-11-05, before the capsule was removed), the host palette token picked up, the default wallpaper applied, and the settings overlay opening. The [settings-section receipt](../../../evidence/live-dsh-settings-section-2026-11-07.md) records the `Azhou appearance` row and embedded panel verified on the real desktop carrier and the capsule's removal checked across the post-animation reveal window. The production desktop profile runs the package through the profile workspace symlink (live since 2026-11-06); still open: the wallpaper import dialog on DSH and Plugin Manager display.
- No `dsh.compatibility.dshReleases` map. Compatibility declarations follow accepted live-host rounds; the wallpaper passed user acceptance on 2026-11-07, and no dedicated animation acceptance round is recorded yet.
