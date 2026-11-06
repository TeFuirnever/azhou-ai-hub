# Agent Skin DSH plugin live-host receipt (2026-11-05)

Scope: the `azhou-agent-skin` plugin loading and rendering in a real DeepSeek Harness web client, on the maintainer machine, against DeepSeek Harness desktop 0.2.1-rc.5. This receipt supersedes the in-host boundary of the [live-install receipt](live-dsh-plugin-install-2026-11-05.md). Every claim names the command that produced it. Screenshots are preserved with SHA-256 prefixes at `~/azhou-agent-skin-candidate/evidence-2026-11-05/` on the maintainer machine and stay out of Git.

## Setup

- `dsh --profile azhou-skin-web --from-default-profile web` created a fresh web profile from the shipped template (bundles `@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-web-app`).
- `dsh plugin --profile azhou-skin-web add ~/azhou-agent-skin-candidate/azhou-agent-skin` registered the plugin; the profile bundle list afterwards reads `["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app", "azhou-agent-skin"]`.
- Booting the profile printed `dsh web: http://127.0.0.1:3080/?token=…` and opened the listener on 127.0.0.1:3080.

## Probing method

Three headless Google Chrome runs (`--headless=new`, fresh throwaway user-data dirs, 1512×889) drove the tokenized URL over the DevTools protocol: page probes by `Runtime.evaluate`, screenshots by `Page.captureScreenshot`. No DSH internals were modified; the production `desktop` profile and its session were untouched.

## Verified, each from a probe or screenshot

- Boot graph and module loading. At t+4s the page exposes `__DSH_BOOT__` and a functional `window.__ModuleLoader__.load`; one full-screen overlay iframe is present (the startup animation playing over the real shell).
- Controller. At t+21s `window.__azhouStartup` is registered with the api surface `owner, version, install, status, openSettings, retryWallpaper, dispose` and `owner === "azhou-dsh-startup"`.
- Startup animation. The overlay iframe present at t+4s is gone at t+21s. `status()` reports `phase:"complete", runId:1, ready:true, completed:true, completion:{cause:"natural", beforeReady:false}`.
- Wallpaper. `status()` reports `wallpaper.applied === true` with `imageDecoded:true, matchedSurfaces:1, transparentSurfaces:1, rootClear:true, workspaceBackgroundClear:true` and the remaining layer checks clear. The applied image is the payload's frozen default: `DEFAULT_ASSETS` in `client.js` carries the 1536×1024 Azhou artwork data URL and `wallpaperStrength:42`, which also matches the settings slider's default position.
- Appearance entry. `document.querySelector('[data-agent-skin-entry]')` exists, sits inside the real sidebar column (`inColumn:true`), renders `display:flex`, and the late screenshot shows the 阿舟 pill at the sidebar bottom (sha256 `6e6915fe…`).
- Theme. The live body carries `data-ds-dark-theme` and the adapter picked up the host's real palette token `--dsw-alias-bg-base: #151517`, not the hardcoded fallback.
- Settings overlay. Clicking the entry button inside its shadow root opens the overlay: one iframe titled `Azhou startup animation`. The settings screenshot (sha256 `372d55ce…`) shows the panel `Azhou · Theme & Appearance`, `Running: 0.9.0 · build 33`, the three tabs, the Azhou lab-scene wallpaper preview, and the strength slider at 42.
- Serving note. A bare `fetch('/plugins/azhou-agent-skin/client.js')` from the page answers 404; the loader serves plugin modules through its revisioned route, and the registered controller plus rendered entry are the working proof that the real route served `client.js`.

The instance stays booted at `http://127.0.0.1:3080/?token=…` (see the boot log for the token) so the operator can open the same page directly.

## Not performed, not claimed

Human aesthetic acceptance is open, and with it the operator's decision to install into the production `desktop` profile. The wallpaper import flow (file dialog through the settings overlay) was not exercised; the applied wallpaper is the built-in default artwork. DSH's own Plugin Manager page was not opened, so its rendering of the title, description, and icon stays unclaimed.
