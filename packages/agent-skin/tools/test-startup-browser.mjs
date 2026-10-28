#!/usr/bin/env node
// Isolated synthetic-host browser checks. This runner owns only its temporary Chrome profile.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { access, copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const options = {
  chrome: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  out: join(ROOT, '.build/startup-browser-evidence'),
  generatedPayload: null,
  only: [],
};
for (let index = 2; index < process.argv.length; index++) {
  const key = process.argv[index];
  if (key === '--help') {
    console.log('node tools/test-startup-browser.mjs [--chrome /path/to/Chrome] [--out /path/to/evidence] [--generated-payload /path/to/install.js] [--only <exact check name>]');
    process.exit(0);
  }
  if (!['--chrome', '--out', '--generated-payload', '--only'].includes(key) || !process.argv[index + 1]) throw new Error('Unknown or missing argument: ' + key);
  const value = process.argv[++index];
  if (key === '--only') options.only.push(value);
  else if (key === '--generated-payload') options.generatedPayload = value;
  else options[key.slice(2)] = value;
}
options.chrome = resolve(options.chrome);
options.out = resolve(options.out);
if (options.generatedPayload) options.generatedPayload = resolve(options.generatedPayload);
const onlyChecks = options.only.length ? new Set(options.only) : null;

const report = {
  schema: 1,
  scope: 'actual PageController and wallpaper renderer in an isolated headless Chrome with a local synthetic Codex-like page',
  startedAt: new Date().toISOString(),
  checks: [],
  screenshots: [],
  limitations: [
    'The app:// page identity is supplied through a local host adapter; no Codex process, profile, transport or user content is accessed.',
    'The wallpaper fixture uses one generated-in-test PNG pixel. The animation fixture separately generates synthetic PNGs and contours; it does not validate private or branded source art.',
    'The cold-start wallpaper check withholds and reinserts the synthetic shell in this local host; it models delayed shell mount timing but does not establish official Codex mount timing.',
    'CSP results cover the renderer after local module loading; they do not prove the official app permits the production script evaluation.',
    'Animation screenshots use an isolated Chrome file page and do not validate native WKWebView presentation or real host identity.',
    'JavaScript rAF and canvas-submission timings exclude GPU, compositor, presentation and system-memory timing.',
  ],
};
let server;
let chrome;
let profile;
let cdp;
let stopping = false;
let chromeError = '';

function safeError(error) {
  return String(error?.message || error).replace(/data:image\/[^\s"']+/g, '[fixture image omitted]').slice(0, 1200);
}

async function until(operation, milliseconds = 10000, label = 'condition') {
  const deadline = Date.now() + milliseconds;
  let last;
  do {
    try {
      const value = await operation();
      if (value) return value;
    } catch (error) { last = error; }
    await delay(60);
  } while (Date.now() < deadline);
  throw new Error('Timed out waiting for ' + label + (last ? ': ' + safeError(last) : ''));
}

async function check(name, operation) {
  if (onlyChecks && !onlyChecks.has(name)) {
    report.checks.push({ name, skipped: true });
    return null;
  }
  const started = Date.now();
  try {
    const details = await operation();
    report.checks.push({ name, passed: true, elapsedMs: Date.now() - started, details });
    return details;
  } catch (error) {
    report.checks.push({ name, passed: false, elapsedMs: Date.now() - started, error: safeError(error) });
    return null;
  }
}

class CDP {
  constructor(socket) {
    this.socket = socket;
    this.nextID = 1;
    this.pending = new Map();
    socket.addEventListener('message', event => {
      let value;
      try { value = JSON.parse(event.data); } catch { return; }
      if (!value.id || !this.pending.has(value.id)) return;
      const pending = this.pending.get(value.id);
      this.pending.delete(value.id);
      clearTimeout(pending.timer);
      value.error ? pending.reject(new Error(value.error.message)) : pending.resolve(value.result);
    });
    socket.addEventListener('close', () => {
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timer);
        pending.reject(new Error('Fixture CDP closed'));
      }
      this.pending.clear();
    });
  }
  static async open(address, expectedPort) {
    const url = new URL(address);
    assert.equal(url.protocol, 'ws:');
    assert.equal(url.hostname, '127.0.0.1');
    assert.equal(Number(url.port), expectedPort);
    assert.ok(url.pathname.startsWith('/devtools/page/'));
    const socket = new WebSocket(address);
    await new Promise((resolveOpen, reject) => {
      const timer = setTimeout(() => { socket.close(); reject(new Error('Fixture WebSocket timeout')); }, 5000);
      socket.addEventListener('open', () => { clearTimeout(timer); resolveOpen(); }, { once: true });
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Fixture WebSocket failed')); }, { once: true });
    });
    return new CDP(socket);
  }
  call(method, params = {}) {
    const id = this.nextID++;
    return new Promise((resolveCall, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error('Fixture CDP timeout: ' + method)); }, 12000);
      this.pending.set(id, { resolve: resolveCall, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.call('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      timeout: 10000,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  }
  close() { this.socket.close(); }
}

async function cleanup() {
  if (stopping) return;
  stopping = true;
  try { cdp?.close(); } catch {}
  if (chrome && chrome.exitCode === null && chrome.signalCode === null) {
    const exited = new Promise(resolveExit => chrome.once('exit', resolveExit));
    chrome.kill('SIGTERM');
    await Promise.race([exited, delay(2000)]);
    if (chrome.exitCode === null && chrome.signalCode === null) {
      chrome.kill('SIGKILL');
      await Promise.race([exited, delay(1000)]);
    }
  }
  if (server) {
    server.closeAllConnections();
    await new Promise(resolveClose => server.close(resolveClose));
  }
  if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 4, retryDelay: 100 });
  report.cleanup = {
    ownChromeStopped: !chrome || chrome.exitCode !== null || chrome.signalCode !== null,
    temporaryProfileRemoved: !!profile,
    serverClosed: !server?.listening,
  };
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => cleanup().finally(() => process.exit(signal === 'SIGINT' ? 130 : 143)));
}

try {
  assert.equal(typeof WebSocket, 'function', 'Use Node 22+ with its built-in WebSocket');
  await access(options.chrome);
  await mkdir(options.out, { recursive: true });
  const [preview, wallpaperCSS, wallpaperRenderer, controllerRenderer, imageSettingsSource, localizationSource, legacyWallpaperCSS,
    legacyWallpaperRenderer, helperExpressionJSON, generatedPayloadSource] = await Promise.all([
    readFile(join(ROOT, 'wallpaper/preview.html'), 'utf8'),
    readFile(join(ROOT, 'wallpaper/wallpaper.css'), 'utf8'),
    readFile(join(ROOT, 'wallpaper/renderer.js'), 'utf8'),
    readFile(join(ROOT, 'extension/renderer.mjs'), 'utf8'),
    readFile(join(ROOT, 'image-settings.js'), 'utf8'),
    readFile(join(ROOT, 'localization.js'), 'utf8'),
    readFile(join(ROOT, '../codex-startup-animation/wallpaper/wallpaper.css'), 'utf8'),
    readFile(join(ROOT, '../codex-startup-animation/wallpaper/renderer.js'), 'utf8'),
    readFile(join(ROOT, '.build/startup-helper-expressions.json'), 'utf8'),
    options.generatedPayload ? readFile(options.generatedPayload, 'utf8') : Promise.resolve(null),
  ]);
  const generatedPayloadRoute = generatedPayloadSource === null ? null : `(() => {
    const host = globalThis.__agentSkinFixtureHost;
    globalThis.__generatedPayloadResult = (function(window, location, document, globalThis) {
      return ${generatedPayloadSource};
    }).call(host, host, host.location, document, host);
  })();`;
  if (generatedPayloadSource !== null) {
    assert.ok(generatedPayloadRoute.includes(generatedPayloadSource),
      'the app-route realm adapter embeds the unmodified generated payload source');
  }
  const helperExpressions = JSON.parse(helperExpressionJSON);
  assert.deepEqual(Object.keys(helperExpressions).sort(), ['applyGuardSource', 'restoreSource', 'statusSource']);
  assert.ok(Object.values(helperExpressions).every(value => typeof value === 'string' && value.length > 0));
  const scriptStart = preview.lastIndexOf('<script type="module">');
  const scriptEnd = preview.indexOf('</script>', scriptStart) + '</script>'.length;
  assert.ok(scriptStart >= 0 && scriptEnd > scriptStart, 'The local preview fixture has a replaceable module entry');
  const fixtureHTML = preview.slice(0, scriptStart)
    + '<script src="/localization.js"></script><script src="/image-settings.js"></script><script src="/animation.js"></script><script type="module" src="/fixture.js"></script>'
    + preview.slice(scriptEnd);
  const pixelBytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC', 'base64');
  const pixelImage = 'data:image/png;base64,' + pixelBytes.toString('base64');
  const imageSHA256 = createHash('sha256').update(pixelBytes).digest('hex');
  const animationAvatarSVG = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><defs><linearGradient id="a" x2="1" y2="1"><stop stop-color="#f6b36b"/><stop offset="1" stop-color="#d86684"/></linearGradient></defs><rect width="512" height="512" fill="url(#a)"/><circle cx="256" cy="256" r="188" fill="#f7d4ad"/><path d="M91 258Q77 73 252 61Q423 75 422 259L378 192Q317 254 153 207Z" fill="#392d4b"/><ellipse cx="196" cy="265" rx="14" ry="20" fill="#31283d"/><ellipse cx="308" cy="265" rx="14" ry="20" fill="#31283d"/><path d="M206 338Q256 380 306 338" fill="none" stroke="#a54f61" stroke-width="13" stroke-linecap="round"/><path d="M140 466Q256 382 372 466" fill="#e3778d"/></svg>';
  const animationArtworkSVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024"><defs><linearGradient id="b" x2="0" y2="1"><stop stop-color="#d9a7d6"/><stop offset=".58" stop-color="#f4d39e"/><stop offset="1" stop-color="#423c64"/></linearGradient></defs><rect width="1536" height="1024" fill="url(#b)"/><circle cx="1210" cy="190" r="110" fill="#fff0bd"/><path d="M0 700L240 390L452 690L700 300L988 710L1220 420L1536 720V1024H0Z" fill="#837aa5"/><path d="M0 812Q270 690 560 820T1110 800T1536 770V1024H0Z" fill="#514e7d"/><path d="M145 860L420 550L640 860M806 826L1070 504L1358 838" fill="none" stroke="#fff6dd" stroke-width="16"/><g fill="#fff8e8"><circle cx="250" cy="170" r="8"/><circle cx="650" cy="120" r="6"/><circle cx="930" cy="220" r="7"/><circle cx="1400" cy="330" r="8"/></g></svg>';
  const animationContourFixture = [
    [[145, 860], [420, 550], [640, 860]],
    [[806, 826], [1070, 504], [1358, 838]],
    [[0, 700], [240, 390], [452, 690], [700, 300], [988, 710], [1220, 420], [1536, 720]],
  ];
  const fixtureModule = `
    import { installStartup } from '/extension/renderer.mjs';
    import { installRenderer } from '/wallpaper/renderer.js';
    import { installRenderer as installLegacyWallpaper } from '/legacy/wallpaper/renderer.js';
    const outerWindow = window;
    const url = new URL(location.href);
    if (url.searchParams.has('initial-light-theme')) document.documentElement.dataset.theme = 'light';
    const nativeMutationObserver = window.MutationObserver;
    const trackedMutationObservers = [];
    const mutationObserverState = new WeakMap();
    window.MutationObserver = class extends nativeMutationObserver {
      constructor(callback) {
        super(callback);
        mutationObserverState.set(this, { active: false, disconnectCalls: 0, kind: 'unclassified' });
        trackedMutationObservers.push(this);
      }
      observe(target, options) {
        const state = mutationObserverState.get(this);
        const attributesOnly = options?.attributes === true && options?.childList !== true;
        const wallpaperShellWait = options?.childList === true && options?.subtree === true
          && options?.attributeFilter?.includes('data-app-shell-frame');
        state.kind = wallpaperShellWait ? 'wallpaper-shell-wait'
          : attributesOnly ? 'appearance-attributes-only' : 'other';
        state.active = true;
        return super.observe(target, options);
      }
      disconnect() {
        const state = mutationObserverState.get(this);
        state.active = false;
        state.disconnectCalls++;
        return super.disconnect();
      }
    };
    let bodyAvailable = !url.searchParams.has('hold-body');
    const heldShell = url.searchParams.has('hold-shell')
      ? document.querySelector('[data-app-shell-frame]') : null;
    const heldShellFragment = document.createDocumentFragment();
    if (heldShell) heldShellFragment.appendChild(heldShell);
    const initialWallpaperStrength = url.searchParams.has('no-initial-wallpaper') ? 0 : 42;
    if (url.searchParams.get('legacy-wash') === 'host-important') {
      document.documentElement.style.setProperty('--azhou-wallpaper-wash', 'host-wash', 'important');
    }
    const hostDocument = {
      get documentElement() { return document.documentElement; },
      get body() { return bodyAvailable ? document.body : undefined; },
      get activeElement() { return document.activeElement; },
      hasFocus: document.hasFocus.bind(document),
      createElement: document.createElement.bind(document),
    };
    let host;
    host = url.searchParams.has('generated-payload')
      ? new Proxy(window, { get(target, name) {
        if (['window', 'self', 'top', 'globalThis'].includes(name)) return host;
        if (name === 'location') return new URL('app://-/index.html?initialRoute=%2F');
        if (name === 'document') return hostDocument;
        const value = Reflect.get(target, name, target);
        return ['addEventListener', 'removeEventListener', 'setTimeout', 'clearTimeout', 'getComputedStyle', 'matchMedia'].includes(name)
          && typeof value === 'function' ? value.bind(target) : value;
      } })
      : {
        location: new URL('app://-/index.html?initialRoute=%2F'), document: hostDocument,
        MutationObserver, addEventListener: window.addEventListener.bind(window),
        removeEventListener: window.removeEventListener.bind(window),
        getComputedStyle: window.getComputedStyle.bind(window),
        matchMedia: window.matchMedia.bind(window),
        setTimeout: window.setTimeout.bind(window), clearTimeout: window.clearTimeout.bind(window),
      };
    let generatedInstallResult;
    if (url.searchParams.has('generated-payload')) {
      globalThis.__agentSkinFixtureHost = host;
      const script = document.createElement('script');
      script.src = '/generated-startup.js';
      await new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = () => reject(new Error('builder-generated startup payload failed to load'));
        document.head.appendChild(script);
      });
      generatedInstallResult = globalThis.__generatedPayloadResult;
    }
    const frameSpecs = [];
    const animationRuns = [];
    const senders = new Map();
    const wallpaper = { version: '0.9.0', preview: true, image: ${JSON.stringify(pixelImage)},
      imageSHA256: ${JSON.stringify(imageSHA256)}, css: await fetch('/wallpaper.css').then(response => response.text()), strength: initialWallpaperStrength };
    const legacyWallpaper = { ...wallpaper, version: '0.7.1', css: await fetch('/legacy-wallpaper.css').then(response => response.text()) };
    const fixturePayload = function (frameWindow, frameDocument, _location, _performance, _indexedDB,
      _Image, _Path2D, _URL, requestAnimationFrame, _cancelAnimationFrame, _setTimeout, _clearTimeout,
      _module, SEND, frameSpec) {
      frameSpecs.push({ runId: frameSpec.runId, intent: frameSpec.intent, protocolVersion: frameSpec.protocolVersion,
        appearance: frameSpec.appearance,
        hasWallpaper: frameSpec.assets?.wallpaper === ${JSON.stringify(pixelImage)} });
      senders.set(frameSpec.runId, SEND);
      const overlay = frameDocument.createElement('div');
      overlay.setAttribute('data-startup-fixture-overlay', String(frameSpec.runId));
      overlay.setAttribute('aria-label', 'Synthetic Agent Skin ' + frameSpec.intent);
      overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;background:transparent';
      frameDocument.body.appendChild(overlay);
      if (frameSpec.intent === 'settings') {
        const settingsInput = frameDocument.createElement('input');
        settingsInput.id = 'startup-fixture-settings-input';
        settingsInput.setAttribute('aria-label', 'Synthetic settings input');
        frameDocument.body.appendChild(settingsInput);
      }
      requestAnimationFrame(() => {
        if (!url.searchParams.has('legacy')) {
          SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
            image: frameSpec.assets.wallpaper, strength: initialWallpaperStrength });
        }
        SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
      });
      return {
        openSettings() {
          if (frameSpec.intent !== 'play') return false;
          SEND({ type: 'azhou-startup', action: 'settings-open', runId: frameSpec.runId });
          return true;
        },
        dispose() { overlay.remove(); },
      };
    };
    const installActualAnimation = function (...args) {
      const frameSpec = args[14];
      const frameWindow = args[0];
      frameSpecs.push({ runId: frameSpec.runId, intent: frameSpec.intent, protocolVersion: frameSpec.protocolVersion,
        appearance: frameSpec.appearance, hasWallpaper: frameSpec.assets?.wallpaper === ${JSON.stringify(pixelImage)} });
      const contextPrototype = frameWindow.CanvasRenderingContext2D?.prototype;
      if (contextPrototype && !frameWindow.__fixtureAnimationTextDraws) {
        const originalFillText = contextPrototype.fillText;
        Object.defineProperty(frameWindow, '__fixtureAnimationTextDraws', { value: [], configurable: true });
        contextPrototype.fillText = function (text, ...rest) {
          const value = String(text);
          if (['Synthetic agent', 'SYNTHETIC / TEST', 'Generated fixture only'].includes(value)) {
            frameWindow.__fixtureAnimationTextDraws.push(value);
          }
          return originalFillText.call(this, text, ...rest);
        };
      }
      if (url.searchParams.has('hold-identity-bitmap')) {
        const createBitmap = frameWindow.createImageBitmap.bind(frameWindow);
        let requests = 0;
        let releaseHeldBitmap = null;
        frameWindow.createImageBitmap = source => {
          const request = ++requests;
          outerWindow.__fixtureIdentityBitmapRequests = requests;
          return createBitmap(source).then(bitmap => {
            if (request !== 3) return bitmap;
            outerWindow.__fixtureIdentityBitmapPending = true;
            return new Promise(resolve => {
              releaseHeldBitmap = () => resolve(bitmap);
              outerWindow.__releaseFixtureIdentityBitmap = () => {
                if (!releaseHeldBitmap) return false;
                const release = releaseHeldBitmap;
                releaseHeldBitmap = null;
                outerWindow.__fixtureIdentityBitmapPending = false;
                release();
                return true;
              };
            });
          });
        };
      }
      const handle = window.installAnimation(...args);
      const run = { runId: frameSpec.runId, intent: frameSpec.intent,
        settingsCommitted: frameSpec.settingsCommitted === true, appearance: frameSpec.appearance };
      if (url.searchParams.has('natural-settings-replay')) {
        const samplePreviewReport = handle.preview.report;
        run.sampleDisposedResources = () => ({
          sampledAt: outerWindow.performance.now(),
          report: samplePreviewReport(),
        });
        const dispose = handle.dispose;
        handle.dispose = () => {
          return dispose();
        };
      } else {
        run.assets = frameSpec.assets;
        run.handle = handle;
      }
      animationRuns.push(run);
      return handle;
    };
    const payload = url.searchParams.has('animation')
      ? (url.searchParams.has('animation-hold') ? function (...args) {
        const frameWindow = args[0];
        const createBitmap = frameWindow.createImageBitmap.bind(frameWindow);
        frameWindow.__fixtureHeldBitmapRequests = 0;
        frameWindow.__fixtureHeldBitmapReleases = 0;
        frameWindow.createImageBitmap = source => {
          frameWindow.__fixtureHeldBitmapRequests++;
          return createBitmap(source).then(bitmap => new Promise(resolve => {
            outerWindow.setTimeout(() => resolve({
              width: bitmap.width,
              height: bitmap.height,
              close() { frameWindow.__fixtureHeldBitmapReleases++; bitmap.close(); },
            }), 800);
          }));
        };
        outerWindow.__animationPendingFrame = frameWindow;
        return installActualAnimation(...args);
      } : installActualAnimation)
      : fixturePayload;
    if (url.searchParams.has('animation') && typeof payload !== 'function') {
      throw new Error('animation installer is not exposed by the canonical source');
    }
    let animationAvatar = '', animationArtwork = '';
    if (url.searchParams.has('animation')) {
      const normalize = async (svg, width, height) => {
        const image = new Image();
        image.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
        await image.decode();
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        canvas.getContext('2d').drawImage(image, 0, 0, width, height);
        return canvas.toDataURL('image/png');
      };
      animationAvatar = await normalize(${JSON.stringify(animationAvatarSVG)}, 512, 512);
      animationArtwork = await normalize(${JSON.stringify(animationArtworkSVG)}, 1536, 1024);
    }
    payload.assets = Object.freeze(url.searchParams.has('animation')
      ? { wallpaper: ${JSON.stringify(pixelImage)}, wallpaperStrength: initialWallpaperStrength,
          avatar: animationAvatar, artwork: animationArtwork,
          contours: ${JSON.stringify(animationContourFixture)}, introTitle: 'Synthetic agent',
          introCaption: 'SYNTHETIC / TEST', artworkSubtitle: 'Generated fixture only' }
      : { wallpaper: ${JSON.stringify(pixelImage)} });
    payload.createLocalization = window.createLocalization;
    if (url.searchParams.has('animation')) {
      const createSettings = window.createImageSettings;
      if (url.searchParams.has('settings-open-pending')) {
        payload.createImageSettings = environment => createSettings({ ...environment, indexedDB: {
          open() { outerWindow.__fixtureIDBStage = 'open'; return {}; },
        } });
      } else if (url.searchParams.has('settings-get-pending')) {
        const database = {
          objectStoreNames: { contains: name => name === 'settings' },
          transaction() {
            const transaction = {
              aborted: false,
              objectStore() { return { get() { outerWindow.__fixtureIDBStage = 'get'; return {}; } }; },
              abort() {
                if (transaction.aborted) return;
                transaction.aborted = true;
                outerWindow.__fixtureIDBAbortCount = (outerWindow.__fixtureIDBAbortCount || 0) + 1;
                queueMicrotask(() => transaction.onabort?.({ target: transaction }));
              },
            };
            return transaction;
          },
          close() {},
        };
        payload.createImageSettings = environment => createSettings({ ...environment, indexedDB: {
          open() {
            outerWindow.__fixtureIDBStage = 'open';
            const request = { result: database };
            queueMicrotask(() => request.onsuccess?.({ target: request }));
            return request;
          },
        } });
      } else if (url.searchParams.has('settings-blocked')) {
        payload.createImageSettings = environment => createSettings({ ...environment, indexedDB: {
          open() { const request = {}; queueMicrotask(() => request.onblocked?.({ target: request })); return request; },
        } });
      } else payload.createImageSettings = createSettings;
    }
    let wallpaperApplications = 0;
    payload.applyWallpaper = async (background, isCurrent) => {
      wallpaperApplications++;
      outerWindow.__fixtureWallpaperApplications = wallpaperApplications;
      if (url.searchParams.has('wallpaper-fail') && wallpaperApplications === 1) {
        throw new Error('synthetic wallpaper failure');
      }
      if (url.searchParams.get('wallpaper-hold') === String(wallpaperApplications)) {
        await new Promise(resolve => { outerWindow.__releaseFixtureWallpaper = resolve; });
        if (!isCurrent()) return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
      }
      const state = await installRenderer({ ...wallpaper, image: background.image,
        strength: background.strength, isCurrent });
      const api = window.__azhouWallpaper;
      if (api) Object.defineProperty(host, '__azhouWallpaper', { value: api, configurable: true, writable: true });
      return state;
    };
    const unknownDecoration = document.createElement('div');
    unknownDecoration.id = 'fixture-unknown';
    unknownDecoration.style.cssText = 'position:fixed;right:12px;top:80px;width:18px;height:18px;pointer-events:none;background-image:linear-gradient(red,blue)';
    document.getElementById('root').appendChild(unknownDecoration);
    if (url.searchParams.has('hold-decode')) {
      const original = HTMLImageElement.prototype.decode;
      const decodeGates = [], pendingGates = new Set();
      HTMLImageElement.prototype.decode = function () {
        return original.call(this).then(() => new Promise(resolve => {
          const index = decodeGates.length;
          decodeGates.push({ resolve, source: this.src });
          pendingGates.add(index);
          outerWindow.__decodeGateCount = decodeGates.length;
          outerWindow.__decodePending = pendingGates.size > 0;
        }));
      };
      outerWindow.__releaseDecodeAt = index => {
        decodeGates[index]?.resolve();
        pendingGates.delete(index);
        outerWindow.__decodePending = pendingGates.size > 0;
        if (!pendingGates.size) HTMLImageElement.prototype.decode = original;
      };
      outerWindow.__releaseDecode = () => outerWindow.__releaseDecodeAt(0);
      const createURL = URL.createObjectURL.bind(URL), revokeURL = URL.revokeObjectURL.bind(URL), urls = new Set();
      URL.createObjectURL = value => { const result = createURL(value); urls.add(result); outerWindow.__fixtureBlobCount = urls.size; return result; };
      URL.revokeObjectURL = value => { urls.delete(value); outerWindow.__fixtureBlobCount = urls.size; return revokeURL(value); };
    }
    let legacyWallpaperAPI;
    if (url.searchParams.has('legacy')) {
      try {
        await installLegacyWallpaper(legacyWallpaper);
        legacyWallpaperAPI = window.__azhouWallpaper;
        Object.defineProperty(host, '__azhouWallpaper', { value: legacyWallpaperAPI, configurable: true, writable: true });
        outerWindow.__legacyWallpaperAPI = legacyWallpaperAPI;
      } catch (error) { outerWindow.__legacyWallpaperError = String(error?.message || error); }
    }
    const result = url.searchParams.has('legacy-only')
      ? { installed: false, alreadyActive: false, reason: 'fixture-no-controller' }
      : installStartup(payload, host);
    outerWindow.__fixtureHost = host;
    outerWindow.__startupAPI = host.__azhouStartup;
    outerWindow.__startupInstallResult = generatedInstallResult || result;
    outerWindow.__startupFrameSpecs = frameSpecs;
    outerWindow.__startupAnimationRuns = animationRuns;
    outerWindow.__startupFixtureSend = (runId, message) => senders.get(runId)?.(message);
    outerWindow.__releaseBody = () => {
      bodyAvailable = true;
      const marker = document.createElement('span');
      marker.hidden = true;
      marker.dataset.bodyGate = 'open';
      document.documentElement.appendChild(marker);
      queueMicrotask(() => marker.remove());
    };
    outerWindow.__releaseShell = () => {
      if (heldShellFragment.childNodes.length) document.getElementById('root').appendChild(heldShellFragment);
      return !!document.querySelector('[data-app-shell-frame]');
    };
    outerWindow.__fixtureMutationObserverStats = () => {
      const states = trackedMutationObservers.map(observer => mutationObserverState.get(observer));
      const summarize = kind => {
        const selected = states.filter(state => state.kind === kind);
        return { created: selected.length, active: selected.filter(state => state.active).length,
          disconnectCalls: selected.reduce((total, state) => total + state.disconnectCalls, 0) };
      };
      return { created: states.length, active: states.filter(state => state.active).length,
        disconnectCalls: states.reduce((total, state) => total + state.disconnectCalls, 0),
        wallpaperShellWait: summarize('wallpaper-shell-wait'),
        appearanceAttributesOnly: summarize('appearance-attributes-only') };
    };
    outerWindow.__startupSurfaceBefore = (() => {
      const read = selector => { const node = document.querySelector(selector); return node ? getComputedStyle(node).backgroundColor : ''; };
      return { composer: read('.composer'), code: read('pre'), menu: read('[role="menu"]'), unknown: read('#fixture-unknown') };
    })();
  `;
  const routes = new Map([
    ['/fixture.html', ['text/html; charset=utf-8', fixtureHTML]],
    ['/csp-style.html', ['text/html; charset=utf-8', fixtureHTML]],
    ['/csp-blob.html', ['text/html; charset=utf-8', fixtureHTML]],
    ['/fixture.js', ['text/javascript; charset=utf-8', fixtureModule]],
    ['/animation.js', ['text/javascript; charset=utf-8', await readFile(join(ROOT, 'animation.js'), 'utf8')]],
    ['/image-settings.js', ['text/javascript; charset=utf-8', imageSettingsSource]],
    ['/localization.js', ['text/javascript; charset=utf-8', localizationSource]],
    ['/wallpaper.css', ['text/css; charset=utf-8', wallpaperCSS]],
    ['/legacy-wallpaper.css', ['text/css; charset=utf-8', legacyWallpaperCSS]],
    ['/wallpaper/renderer.js', ['text/javascript; charset=utf-8', wallpaperRenderer]],
    ['/legacy/wallpaper/renderer.js', ['text/javascript; charset=utf-8', legacyWallpaperRenderer]],
    ['/extension/renderer.mjs', ['text/javascript; charset=utf-8', controllerRenderer]],
  ]);
  if (generatedPayloadRoute !== null) {
    routes.set('/generated-startup.js', ['text/javascript; charset=utf-8', generatedPayloadRoute]);
  }
  server = createServer((request, response) => {
    const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
    const route = routes.get(pathname);
    if (!route) { response.writeHead(404); response.end('Unknown fixture route'); return; }
    response.setHeader('Content-Type', route[0]);
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    if (pathname === '/csp-style.html') {
      response.setHeader('Content-Security-Policy', "default-src 'none'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; object-src 'none'");
    } else if (pathname === '/csp-blob.html') {
      response.setHeader('Content-Security-Policy', "default-src 'none'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; object-src 'none'");
    }
    response.end(route[1]);
  });
  await new Promise((resolveListen, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveListen); });
  const origin = 'http://127.0.0.1:' + server.address().port;
  profile = await mkdtemp(join(tmpdir(), 'azhou-startup-browser-'));
  const animationPreviewDir = join(profile, 'agent-skin-preview');
  const animationDefaultsDir = join(animationPreviewDir, 'assets/defaults');
  await mkdir(animationDefaultsDir, { recursive: true });
  await Promise.all([
    copyFile(join(ROOT, 'index.html'), join(animationPreviewDir, 'index.html')),
    copyFile(join(ROOT, 'style.css'), join(animationPreviewDir, 'style.css')),
    copyFile(join(ROOT, 'animation.js'), join(animationPreviewDir, 'animation.js')),
    copyFile(join(ROOT, 'localization.js'), join(animationPreviewDir, 'localization.js')),
    copyFile(join(ROOT, 'image-settings.js'), join(animationPreviewDir, 'image-settings.js')),
  ]);
  const maximumSubtitle = '和阿舟一起，把复杂问题拆清楚；再整理线索、验证方法、修正错误，把每个想法一步步做成可以复用的真实结果。并分享可复用成果。';
  assert.equal(maximumSubtitle.length, 60, 'the synthetic subtitle fixture reaches the 60 UTF-16 code-unit limit');
  const maximumIntroTitle = '阿舟陪你把复杂问题拆清楚再做吧！';
  const maximumIntroCaption = '帮助你梳理线索、拆解任务、验证假设、记录过程，并把可复用的方法应用到项目中，留下清楚可靠的结果。';
  assert.equal(maximumIntroTitle.length, 16, 'the synthetic intro title fixture reaches the 16 UTF-16 code-unit limit');
  assert.equal(maximumIntroCaption.length, 48, 'the synthetic intro caption fixture reaches the 48 UTF-16 code-unit limit');
  const syntheticDefaults = `
    (() => {
      function png(width, height, paint) {
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        paint(canvas.getContext('2d'));
        return canvas.toDataURL('image/png');
      }
      const avatar = png(512, 512, ctx => {
        const gradient = ctx.createLinearGradient(0, 0, 512, 512);
        gradient.addColorStop(0, '#f5bc82'); gradient.addColorStop(1, '#bf607d');
        ctx.fillStyle = gradient; ctx.fillRect(0, 0, 512, 512);
        ctx.fillStyle = '#342b42'; ctx.beginPath(); ctx.ellipse(256, 242, 178, 194, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#f8d9bd'; ctx.beginPath(); ctx.ellipse(256, 266, 142, 166, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#352d43'; ctx.beginPath(); ctx.ellipse(207, 258, 10, 17, 0, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.ellipse(305, 258, 10, 17, 0, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#a54f61'; ctx.lineWidth = 10; ctx.lineCap = 'round'; ctx.beginPath(); ctx.arc(256, 313, 39, .3, Math.PI - .3); ctx.stroke();
        ctx.fillStyle = '#e3778d'; ctx.beginPath(); ctx.ellipse(256, 468, 142, 58, 0, Math.PI, 0); ctx.fill();
      });
      const artwork = png(1536, 1024, ctx => {
        const gradient = ctx.createLinearGradient(0, 0, 0, 1024);
        gradient.addColorStop(0, '#d9a7d6'); gradient.addColorStop(.58, '#f4d39e'); gradient.addColorStop(1, '#423c64');
        ctx.fillStyle = gradient; ctx.fillRect(0, 0, 1536, 1024);
        ctx.fillStyle = '#fff0bd'; ctx.beginPath(); ctx.arc(1210, 190, 110, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#837aa5'; ctx.beginPath(); ctx.moveTo(0, 700); ctx.lineTo(240, 390); ctx.lineTo(452, 690); ctx.lineTo(700, 300); ctx.lineTo(988, 710); ctx.lineTo(1220, 420); ctx.lineTo(1536, 720); ctx.lineTo(1536, 1024); ctx.lineTo(0, 1024); ctx.fill();
        ctx.fillStyle = '#514e7d'; ctx.beginPath(); ctx.moveTo(0, 812); ctx.quadraticCurveTo(270, 690, 560, 820); ctx.quadraticCurveTo(830, 930, 1110, 800); ctx.quadraticCurveTo(1320, 720, 1536, 770); ctx.lineTo(1536, 1024); ctx.lineTo(0, 1024); ctx.fill();
        ctx.strokeStyle = '#fff6dd'; ctx.lineWidth = 16; ctx.beginPath(); ctx.moveTo(145, 860); ctx.lineTo(420, 550); ctx.lineTo(640, 860); ctx.moveTo(806, 826); ctx.lineTo(1070, 504); ctx.lineTo(1358, 838); ctx.stroke();
        ctx.fillStyle = '#fff8e8'; for (const [x, y, r] of [[250, 170, 8], [650, 120, 6], [930, 220, 7], [1400, 330, 8]]) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
      });
      window.AGENT_SKIN_ASSETS = {
        avatar, artwork,
        contours: [
          [[145, 860], [420, 550], [640, 860]],
          [[806, 826], [1070, 504], [1358, 838]],
          [[0, 700], [240, 390], [452, 690], [700, 300], [988, 710], [1220, 420], [1536, 720]],
          [[0, 812], [270, 690], [560, 820], [830, 930], [1110, 800], [1320, 720], [1536, 770]],
        ],
        introTitle: 'Synthetic agent', introCaption: 'SYNTHETIC / TEST', artworkSubtitle: ${JSON.stringify(maximumSubtitle)},
      };
    })();
  `;
  await writeFile(join(animationDefaultsDir, 'contours.js'), syntheticDefaults, 'utf8');
  const identityVariants = [
    { name: 'english', title: 'Synthetic agent', caption: 'SYNTHETIC / TEST' },
    { name: 'maximum-chinese', title: maximumIntroTitle, caption: maximumIntroCaption },
    { name: 'empty', title: '', caption: '' },
  ];
  for (const variant of identityVariants) {
    const variantDir = join(profile, 'agent-skin-preview-identity-' + variant.name);
    const variantDefaultsDir = join(variantDir, 'assets/defaults');
    await mkdir(variantDefaultsDir, { recursive: true });
    await Promise.all([
      copyFile(join(ROOT, 'index.html'), join(variantDir, 'index.html')),
      copyFile(join(ROOT, 'style.css'), join(variantDir, 'style.css')),
      copyFile(join(ROOT, 'animation.js'), join(variantDir, 'animation.js')),
      copyFile(join(ROOT, 'localization.js'), join(variantDir, 'localization.js')),
      copyFile(join(ROOT, 'image-settings.js'), join(variantDir, 'image-settings.js')),
    ]);
    const identityDefaults = syntheticDefaults.replace(
      "introTitle: 'Synthetic agent', introCaption: 'SYNTHETIC / TEST'",
      'introTitle: ' + JSON.stringify(variant.title) + ', introCaption: ' + JSON.stringify(variant.caption),
    );
    assert.notEqual(identityDefaults, syntheticDefaults);
    await writeFile(join(variantDefaultsDir, 'contours.js'), identityDefaults, 'utf8');
    variant.dir = variantDir;
  }
  const upperPreviewDir = join(profile, 'agent-skin-preview-upper');
  const upperDefaultsDir = join(upperPreviewDir, 'assets/defaults');
  await mkdir(upperDefaultsDir, { recursive: true });
  await Promise.all([
    copyFile(join(ROOT, 'index.html'), join(upperPreviewDir, 'index.html')),
    copyFile(join(ROOT, 'style.css'), join(upperPreviewDir, 'style.css')),
    copyFile(join(ROOT, 'animation.js'), join(upperPreviewDir, 'animation.js')),
    copyFile(join(ROOT, 'localization.js'), join(upperPreviewDir, 'localization.js')),
    copyFile(join(ROOT, 'image-settings.js'), join(upperPreviewDir, 'image-settings.js')),
  ]);
  const upperDefaults = `
    (() => {
      function png(width, height, seed) {
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        const context = canvas.getContext('2d'); const image = context.createImageData(width, height);
        let value = seed >>> 0;
        for (let offset = 0; offset < image.data.length; offset += 4) {
          value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
          image.data[offset] = value >>> 24;
          value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
          image.data[offset + 1] = value >>> 24;
          value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
          image.data[offset + 2] = value >>> 24;
          image.data[offset + 3] = 255;
        }
        context.putImageData(image, 0, 0);
        return canvas.toDataURL('image/png');
      }
      const contours = [];
      for (let pathIndex = 0; pathIndex < 1200; pathIndex++) {
        const points = [];
        for (let pointIndex = 0; pointIndex < 250; pointIndex++) {
          points.push([
            (pathIndex * 73 + pointIndex * 17 + 13) % 1537,
            (pathIndex * 41 + pointIndex * 29 + 7) % 1025,
          ]);
        }
        contours.push(points);
      }
      window.AGENT_SKIN_ASSETS = {
        avatar: png(512, 512, 0x31840c0f), artwork: png(1536, 1024, 0x5eed1234), contours,
        introTitle: 'Synthetic upper-bound agent', introCaption: 'SYNTHETIC / RESOURCE TEST',
        artworkSubtitle: ${JSON.stringify(maximumSubtitle)},
      };
    })();
  `;
  await writeFile(join(upperDefaultsDir, 'contours.js'), upperDefaults, 'utf8');
  chrome = spawn(options.chrome, [
    '--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
    '--disable-default-apps', '--disable-sync', '--disable-extensions', '--disable-component-update', '--no-pings',
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', '--user-data-dir=' + profile,
    '--window-size=1512,889', 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  chrome.on('error', error => { chromeError = safeError(error); });
  chrome.stderr.on('data', chunk => { chromeError = (chromeError + chunk.toString()).slice(-4000); });
  const debugPort = await until(async () => {
    if (chrome.exitCode !== null || chrome.signalCode !== null) throw new Error('Own Chrome exited: ' + chromeError);
    const file = await readFile(join(profile, 'DevToolsActivePort'), 'utf8');
    const port = Number(file.split('\n')[0]);
    assert.ok(port > 0 && port < 65536);
    return port;
  }, 15000, 'isolated Chrome DevToolsActivePort');
  const endpoint = 'http://127.0.0.1:' + debugPort;
  const fetchJSON = async path => {
    const response = await fetch(endpoint + path, { signal: AbortSignal.timeout(2000) });
    assert.ok(response.ok);
    return response.json();
  };
  const browser = await fetchJSON('/json/version');
  const page = await until(async () => (await fetchJSON('/json/list')).find(target => target.type === 'page' && target.url === 'about:blank'), 5000, 'isolated blank page');
  cdp = await CDP.open(page.webSocketDebuggerUrl, debugPort);
  await cdp.call('Page.enable');
  await cdp.call('Runtime.enable');
  report.environment = {
    node: process.version,
    platform: process.platform,
    chromeExecutable: options.chrome,
    chromePID: chrome.pid,
    browser: browser.Browser,
    protocolVersion: browser['Protocol-Version'],
    isolatedTemporaryProfile: true,
    debugPortPolicy: 'port 0 was used only by this disposable fixture; this is not a claim about the official app',
  };

  async function navigate(path) {
    const result = await cdp.call('Page.navigate', { url: origin + path });
    assert.ok(!result.errorText, result.errorText);
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'synthetic host page load');
    await until(() => cdp.evaluate('window.__startupInstallResult !== undefined'), 10000, 'real PageController install');
  }
  async function animationPixelEvidence() {
    return cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const run=window.__startupAnimationRuns?.at(-1);
      const animationDocument=frame?.contentDocument||document;
      const canvas=animationDocument.querySelector('canvas[data-agent-skin-canvas]');
      const report=run?.handle?.preview?.report?.()||window.launcherUI?.report?.();
      if(!canvas||!report)return false;
      const context=canvas.getContext('2d'),image=context.getImageData(0,0,canvas.width,canvas.height),data=image.data;
      const viewport=report.viewport,scale=Math.max(viewport.width/1536,viewport.height/1024);
      const offsetX=(viewport.width-1536*scale)/2,offsetY=(viewport.height-1024*scale)/2;
      const ratioX=canvas.width/viewport.width,ratioY=canvas.height/viewport.height;
      const pixelAt=(x,y)=>{
        const px=Math.max(0,Math.min(canvas.width-1,Math.floor((x*scale+offsetX)*ratioX)));
        const py=Math.max(0,Math.min(canvas.height-1,Math.floor((y*scale+offsetY)*ratioY)));
        const index=(py*canvas.width+px)*4;
        return [data[index],data[index+1],data[index+2],data[index+3]];
      };
      const identity={dark:0,light:0};
      for(let y=680;y<870;y+=3)for(let x=180;x<1356;x+=3){
        const [r,g,b,a]=pixelAt(x,y),luma=.2126*r+.7152*g+.0722*b;
        if(a>200&&luma<110)identity.dark++;
        if(a>200&&luma>215)identity.light++;
      }
      const segments=[
        [[145,860],[420,550]],[[420,550],[640,860]],
        [[806,826],[1070,504]],[[1070,504],[1358,838]],
        [[0,700],[240,390]],[[240,390],[452,690]],[[452,690],[700,300]],
        [[700,300],[988,710]],[[988,710],[1220,420]],[[1220,420],[1536,720]],
      ];
      const line={dark:0,light:0},seen=new Set();
      for(const [[x1,y1],[x2,y2]] of segments){
        const dx=x2-x1,dy=y2-y1,length=Math.hypot(dx,dy),steps=Math.ceil(length/3);
        const nx=-dy/length,ny=dx/length;
        for(let step=2;step<steps-2;step++){
          const t=step/steps,x=x1+dx*t,y=y1+dy*t;
          for(const offset of [-1,0,1]){
            const [r,g,b,a]=pixelAt(x+nx*offset,y+ny*offset),luma=.2126*r+.7152*g+.0722*b;
            const key=[Math.round((x+nx*offset)*scale),Math.round((y+ny*offset)*scale)].join(':');
            if(seen.has(key))continue;
            seen.add(key);
            if(a>200&&luma<160)line.dark++;
            if(a>200&&luma>170)line.light++;
          }
        }
      }
      return {stage:report.stage,elapsed:report.elapsed,sceneRenderCount:report.jsFrame.sceneRenderCount,
        surface:pixelAt(8,8),identity,line,resources:report.resources};
    })()`);
  }
  async function evaluateNativeHelper(name, { startup = 'actual', wallpaper = 'actual' } = {}) {
    const source = helperExpressions[name];
    assert.equal(typeof source, 'string', 'native helper expression is emitted by the compiled Swift test target');
    const binding = (kind, name) => {
      if (kind === 'none') return 'undefined';
      if (kind === 'unknown') return "({ owner: 'fixture-unknown-owner' })";
      if (kind !== 'actual') throw new Error('Unknown native helper binding: ' + kind);
      return name === 'startup'
        ? 'actualWindow.__fixtureHost?.__azhouStartup'
        : '(actualWindow.__azhouWallpaper || actualWindow.__fixtureHost?.__azhouWallpaper)';
    };
    const expression = `(()=>{
      const actualWindow=document.defaultView;
      const window={};window.top=window;
      const location=new URL('app://-/index.html?initialRoute=%2F');
      const globalThis={};
      const startup=${binding(startup, 'startup')};
      const wallpaper=${binding(wallpaper, 'wallpaper')};
      if(startup!==undefined)Object.defineProperty(globalThis,'__azhouStartup',{value:startup,configurable:true});
      if(wallpaper!==undefined)Object.defineProperty(globalThis,'__azhouWallpaper',{value:wallpaper,configurable:true});
      return (${source});
    })()`;
    return cdp.evaluate(expression);
  }
  async function screenshot(name) {
    await cdp.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
    const viewport = await cdp.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,theme:document.documentElement.dataset.theme})');
    const result = await cdp.call('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
    const bytes = Buffer.from(result.data, 'base64');
    assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    const pixels = { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
    await writeFile(join(options.out, name), bytes);
    const detail = { file: name, ...viewport, pixels };
    report.screenshots.push(detail);
    return detail;
  }
  async function appearanceEntryMetrics() {
    return cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const shadow=entry?.shadowRoot,button=shadow?.querySelector('button[aria-label="阿舟主题与外观"]');
      if(!entry||!button)return null;
      const rect=button.getBoundingClientRect(),x=rect.left+rect.width/2,y=rect.top+rect.height/2;
      const target=document.elementFromPoint(x,y),shadowTarget=shadow.elementFromPoint?.(x,y);
      const avatar=button.querySelector('img'),avatarStyle=avatar&&getComputedStyle(avatar);
      const nameLabel=button.querySelector('span'),nameStyle=nameLabel&&getComputedStyle(nameLabel);
      const input=document.querySelector('textarea'),menu=document.querySelector('[role="menu"]');
      const inputRect=input?.getBoundingClientRect(),menuRect=menu?.getBoundingClientRect();
      const rectData=value=>value&&({x:value.x,y:value.y,width:value.width,height:value.height});
      const overlap=value=>{
        if(!value)return null;
        const left=Math.max(rect.left,value.left),top=Math.max(rect.top,value.top);
        const right=Math.min(rect.right,value.right),bottom=Math.min(rect.bottom,value.bottom);
        const width=Math.max(0,right-left),height=Math.max(0,bottom-top);
        const point=width&&height?{x:left+width/2,y:top+height/2}:null;
        const pageTarget=point&&document.elementFromPoint(point.x,point.y);
        const buttonTarget=point&&shadow.elementFromPoint?.(point.x,point.y);
        return {x:left,y:top,width,height,area:width*height,
          coveredByEntry:pageTarget===entry,coveredByButton:buttonTarget===button,
          hit:pageTarget?.tagName?.toLowerCase()||null};
      };
      const inputTarget=inputRect&&document.elementFromPoint(inputRect.left+Math.min(8,inputRect.width/2),
        inputRect.top+Math.min(8,inputRect.height/2));
      const menuTarget=menuRect&&document.elementFromPoint(menuRect.left+menuRect.width/2,menuRect.top+menuRect.height/2);
      const composer=document.querySelector('.composer'),sidebar=document.querySelector('.sidebar');
      const composerLabel=composer?.querySelector('footer span'),sendButton=composer?.querySelector('footer button');
      const entryStyle=getComputedStyle(entry),buttonStyle=getComputedStyle(button);
      return {display:entryStyle.display,position:entryStyle.position,left:entryStyle.left,bottom:entryStyle.bottom,
        buttonPosition:buttonStyle.position,padding:buttonStyle.padding,rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
        buttonText:button.textContent,buttonAriaLabel:button.getAttribute('aria-label'),
        avatar:avatar?{width:avatar.getBoundingClientRect().width,height:avatar.getBoundingClientRect().height,
          display:avatarStyle.display,borderRadius:avatarStyle.borderRadius,objectFit:avatarStyle.objectFit}:null,
        nameLabel:nameLabel?{text:nameLabel.textContent,fontSize:nameStyle.fontSize,lineHeight:nameStyle.lineHeight}:null,
        entryHit:target===entry,buttonHit:!!button&&(shadowTarget===button||button.contains(shadowTarget)),documentFocus:document.activeElement===entry,
        shadowFocus:shadow.activeElement===button,
        viewport:{width:innerWidth,height:innerHeight},
        sidebarRect:rectData(sidebar?.getBoundingClientRect()),composerRect:rectData(composer?.getBoundingClientRect()),
        inputRect:rectData(inputRect),inputOverlap:overlap(inputRect),composerOverlap:overlap(composer?.getBoundingClientRect()),
        composerLabelRect:rectData(composerLabel?.getBoundingClientRect()),composerLabelOverlap:overlap(composerLabel?.getBoundingClientRect()),
        sendButtonRect:rectData(sendButton?.getBoundingClientRect()),sendButtonOverlap:overlap(sendButton?.getBoundingClientRect()),
        inputHit:!!input&&(inputTarget===input||input.contains(inputTarget)),
        menuRect:rectData(menuRect),menuOverlap:overlap(menuRect),
        menuHit:!!menu&&(menuTarget===menu||menu.contains(menuTarget))};
    })()`);
  }
  async function clickAppearanceEntry() {
    const point = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const button=entry?.shadowRoot?.querySelector('button[aria-label="阿舟主题与外观"]');
      if(!button)return false;
      const rect=button.getBoundingClientRect();
      return {x:rect.left+rect.width/2,y:rect.top+rect.height/2};
    })()`);
    if (!point) return false;
    await cdp.call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x, y: point.y });
    await cdp.call('Input.dispatchMouseEvent', { type: 'mousePressed', x: point.x, y: point.y, button: 'left', clickCount: 1 });
    await cdp.call('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x, y: point.y, button: 'left', clickCount: 1 });
    return cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const button=entry?.shadowRoot?.querySelector('button[aria-label="阿舟主题与外观"]');
      return {focused:!!button&&document.activeElement===entry&&entry.shadowRoot.activeElement===button,
        state:window.__startupAPI.status()};
    })()`);
  }

  const initialLightCheck = 'initial light appearance draws readable identity and cached path pixels from theme-only host state';
  if (!onlyChecks || onlyChecks.has(initialLightCheck)) {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&initial-light-theme=1');
  }
  await check(initialLightCheck, async () => {
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status(),frame=document.querySelector('iframe[aria-label]');
      const spec=window.__startupFrameSpecs?.at(-1),run=window.__startupAnimationRuns?.at(-1);
      return state?.phase==='playing'&&state.ready&&frame&&run?.handle?.preview?.report?.()
        ?{theme:spec.appearance.theme,colors:spec.appearance.colors,phase:state.phase}:false;
    })()`), 15000, 'theme-only light host and actual animation are ready');
    assert.equal(ready.theme, 'light');
    assert.equal(ready.colors.text, undefined, 'the synthetic host supplies no explicit text color token');
    assert.equal(ready.colors.muted, undefined, 'the synthetic host supplies no explicit muted color token');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.pause()');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(2.2)');
    const identity = await animationPixelEvidence();
    assert.equal(identity.stage, 'identity');
    assert.ok(identity.surface[0] > 220 && identity.surface[1] > 220,
      'theme-only light appearance keeps the rendered canvas surface light: ' + JSON.stringify(identity.surface));
    assert.ok(identity.identity.dark > 40,
      'the initial light identity title and caption contain dark rendered pixels: ' + JSON.stringify(identity.identity));
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(7.25)');
    const line = await animationPixelEvidence();
    assert.equal(line.stage, 'colorize');
    assert.ok(line.line.dark > 10,
      'the cached contour strokes use a dark color on the initial light host: ' + JSON.stringify(line.line));
    return { hostAppearance: ready, identity: { surface: identity.surface, pixels: identity.identity },
      colorize: { surface: line.surface, contourPixels: line.line } };
  });

  const darkToLightCheck = 'live dark-to-light host changes redraw identity and cached contour pixels';
  if (!onlyChecks || onlyChecks.has(darkToLightCheck)) {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  }
  await check(darkToLightCheck, async () => {
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status(),run=window.__startupAnimationRuns?.at(-1);
      return state?.phase==='playing'&&state.ready&&run?.handle?.preview?.report?.()?state:false;
    })()`), 15000, 'dark host animation is ready before changing appearance');
    await cdp.evaluate(`(()=>{
      const preview=window.__startupAnimationRuns.at(-1).handle.preview;
      preview.pause();preview.seek(2.2);
    })()`);
    const darkIdentity = await animationPixelEvidence();
    assert.equal(darkIdentity.stage, 'identity');
    assert.ok(darkIdentity.surface[0] < 100 && darkIdentity.identity.light > 40,
      'the dark identity frame has a dark surface and visible light title/caption: ' + JSON.stringify(darkIdentity));

    await cdp.evaluate(`(()=>{
      const root=document.documentElement;
      root.lang='en';root.dataset.theme='light';
      root.style.setProperty('--color-text','#202123');
      root.style.setProperty('--color-text-secondary','#65666c');
      root.style.setProperty('--color-border','#dedee3');
    })()`);
    const updated = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),root=document.documentElement;
      return root.lang==='en'&&root.dataset.theme==='light'&&frame?.title==='Azhou startup animation'
        ?{locale:root.lang,theme:root.dataset.theme,title:frame.title}:false;
    })()`), 3000, 'host appearance observer applies English light settings');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(2.2)');
    const lightIdentity = await animationPixelEvidence();
    assert.equal(lightIdentity.stage, 'identity');
    assert.ok(lightIdentity.surface[0] > 220 && lightIdentity.identity.dark > 40,
      'identity title and caption redraw in dark ink on the light host: ' + JSON.stringify(lightIdentity));
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(7.25)');
    const lightLine = await animationPixelEvidence();
    assert.equal(lightLine.stage, 'colorize');
    assert.ok(lightLine.line.dark > 10,
      'cached contour strokes are rebuilt with dark ink after the host theme change: ' + JSON.stringify(lightLine.line));
    return { runId: ready.runId, updated, dark: { surface: darkIdentity.surface, identity: darkIdentity.identity },
      light: { identity: { surface: lightIdentity.surface, pixels: lightIdentity.identity },
        colorize: { surface: lightLine.surface, contourPixels: lightLine.line } } };
  });

  const delayedAppearanceCheck = 'appearance update during identity bitmap preparation redraws identity and cached contours';
  if (!onlyChecks || onlyChecks.has(delayedAppearanceCheck)) {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&hold-identity-bitmap=1');
  }
  await check(delayedAppearanceCheck, async () => {
    const pending = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return window.__fixtureIdentityBitmapPending
        ?{state,requests:window.__fixtureIdentityBitmapRequests}:false;
    })()`), 15000, 'the third createImageBitmap request for identity is held during preparation');
    assert.equal(pending.requests, 3, 'the first two image bitmaps complete and only identity remains pending');
    assert.equal(pending.state.phase, 'loading');
    assert.equal(pending.state.ready, false);
    await cdp.evaluate(`(()=>{
      const root=document.documentElement;
      root.lang='en';root.dataset.theme='light';
      root.style.setProperty('--color-text','#202123');
      root.style.setProperty('--color-text-secondary','#65666c');
      root.style.setProperty('--color-border','#dedee3');
    })()`);
    const updated = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),root=document.documentElement;
      return root.lang==='en'&&root.dataset.theme==='light'&&frame?.title==='Azhou startup animation'
        ?{locale:root.lang,theme:root.dataset.theme,title:frame.title}:false;
    })()`), 3000, 'host appearance changes while the identity bitmap is pending');
    assert.equal(await cdp.evaluate('window.__releaseFixtureIdentityBitmap()'), true,
      'the delayed identity bitmap can be released after the host appearance update');
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'preparation retries with the latest host appearance');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.pause()');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(2.2)');
    const identity = await animationPixelEvidence();
    assert.equal(identity.stage, 'identity');
    assert.ok(identity.surface[0] > 220 && identity.identity.dark > 40,
      'the retried identity bitmap uses the latest light text colors: ' + JSON.stringify(identity));
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(7.25)');
    const line = await animationPixelEvidence();
    assert.equal(line.stage, 'colorize');
    assert.ok(line.line.dark > 10,
      'the cached contour canvas uses the latest light text color: ' + JSON.stringify(line.line));
    return { heldRequest: pending.requests, updated, ready: { runId: ready.runId, locale: ready.locale, theme: ready.theme },
      identity: { surface: identity.surface, pixels: identity.identity }, colorize: { surface: line.surface, contourPixels: line.line } };
  });

  await navigate('/fixture.html');
  const normalReady = await until(() => cdp.evaluate(`(()=>{
    const state=window.__startupAPI?.status();
    return state?.phase==='playing' && state.ready && state.wallpaper?.applied ? state : false;
  })()`), 15000, 'ready page and verified static wallpaper');
  await check('real controller and wallpaper renderer apply one decoded scene with a valid CSS sentinel', async () => {
    const state = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(state.owner, 'azhou-codex-startup');
    assert.equal(state.version, 1);
    assert.equal(state.phase, 'playing');
    assert.equal(state.wallpaper.imageDecoded, true);
    assert.equal(state.wallpaper.backgroundMatched, true);
    assert.equal(state.wallpaper.coverMatched, true);
    assert.equal(state.wallpaper.washMatched, true);
    assert.equal(state.wallpaper.unsupportedDecorations.length, 0);
    const details = await cdp.evaluate(`(()=>{
      const read=selector=>{const node=document.querySelector(selector);return node?getComputedStyle(node).backgroundColor:'';};
      const frame=document.querySelector('iframe[aria-label]');
      const unknown=document.querySelector('#fixture-unknown');
      return {frameCount:document.querySelectorAll('iframe[aria-label]').length,
        frameEvalCount:0,styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        unknownBefore:window.__startupSurfaceBefore.unknown,unknownAfter:getComputedStyle(unknown).backgroundImage,
        surfaces:{composerBefore:window.__startupSurfaceBefore.composer,composerAfter:read('.composer'),
          codeBefore:window.__startupSurfaceBefore.code,codeAfter:read('pre'),
          menuBefore:window.__startupSurfaceBefore.menu,menuAfter:read('[role="menu"]')},
        frameIntent:window.__startupFrameSpecs[0].intent,frameRunId:window.__startupFrameSpecs[0].runId,
        frameSpecAssets:window.__startupFrameSpecs[0].hasWallpaper};
    })()`);
    assert.equal(details.frameCount, 1);
    assert.equal(details.styleCount, 1);
    assert.equal(details.frameIntent, 'play');
    assert.equal(details.frameSpecAssets, true);
    assert.equal(details.unknownAfter, 'linear-gradient(rgb(255, 0, 0), rgb(0, 0, 255))');
    assert.equal(details.surfaces.composerAfter, details.surfaces.composerBefore);
    assert.equal(details.surfaces.codeAfter, details.surfaces.codeBefore);
    assert.equal(details.surfaces.menuAfter, details.surfaces.menuBefore);
    return { state, details };
  });
  await check('compiled native helper status and apply guard execute against the live fixture API objects', async () => {
    const before = await cdp.evaluate(`({runId:window.__startupAPI.status().runId,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length})`);
    const status = await evaluateNativeHelper('statusSource');
    assert.equal(status.applied, true);
    assert.equal(status.startup.installed, true);
    assert.equal(status.startup.owner, 'azhou-codex-startup');
    assert.equal(status.startup.phase, 'playing');
    const active = await evaluateNativeHelper('applyGuardSource');
    assert.deepEqual(active, { state: 'startup-active', applied: false });
    const unknownStartup = await evaluateNativeHelper('applyGuardSource', { startup: 'unknown', wallpaper: 'none' });
    assert.deepEqual(unknownStartup, { state: 'owner-conflict', applied: false });
    const unknownWallpaper = await evaluateNativeHelper('applyGuardSource', { startup: 'none', wallpaper: 'unknown' });
    assert.deepEqual(unknownWallpaper, { state: 'owner-conflict', applied: false });
    const after = await cdp.evaluate(`({runId:window.__startupAPI.status().runId,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length})`);
    assert.deepEqual(after, before, 'status and apply guards are read-only');
    return { status, active, unknownStartup, unknownWallpaper, before, after };
  });
  await check('deep and light synthetic host screenshots preserve controls and unknown decoration', async () => {
    const shots = [];
    for (const [theme, file] of [['dark', 'startup-wallpaper-dark.png'], ['light', 'startup-wallpaper-light.png']]) {
      await cdp.evaluate('document.documentElement.dataset.theme=' + JSON.stringify(theme));
      const state = await cdp.evaluate('window.__startupAPI.status()');
      assert.equal(state.wallpaper.applied, true);
      shots.push(await screenshot(file));
    }
    return shots;
  });
  await check('PageController openSettings API opens settings during playback and saved settings start a fresh run', async () => {
    const before = await cdp.evaluate('window.__startupAPI.status()');
    const opened = await cdp.evaluate(`(()=>{
      const accepted=window.__startupAPI.openSettings();
      return {accepted,count:document.querySelectorAll('iframe[aria-label]').length,
        state:window.__startupAPI.status()};
    })()`);
    assert.equal(opened.accepted, true);
    assert.equal(opened.count, 1);
    assert.equal(opened.state.phase, 'settings');
    assert.equal(opened.state.runId, before.runId);
    await cdp.evaluate(`window.__startupFixtureSend(${before.runId},{type:'azhou-startup',action:'settings-close',runId:${before.runId}})`);
    const replay = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='playing'&&state.ready&&state.runId>${before.runId}?state:false;
    })()`), 10000, 'fresh play run after settings save');
    const spec = await cdp.evaluate('window.__startupFrameSpecs.at(-1)');
    assert.equal(spec.intent, 'play');
    assert.ok(spec.runId > before.runId);
    await cdp.evaluate(`window.__startupFixtureSend(${replay.runId},{type:'azhou-startup',action:'complete',runId:${replay.runId},skipped:false})`);
    await until(() => cdp.evaluate('window.__startupAPI.status().phase === "complete"'), 3000,
      'complete the replay before checking API focus restoration');
    const inputOpen = await cdp.evaluate(`(()=>{
      const input=document.querySelector('textarea');input.focus();
      const accepted=window.__startupAPI.openSettings();
      return {accepted,inputFocused:document.activeElement===input,state:window.__startupAPI.status()};
    })()`);
    assert.equal(inputOpen.inputFocused, true);
    assert.equal(inputOpen.accepted, true);
    const apiSettings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='settings'&&state.ready&&state.runId>${replay.runId}?state:false;
    })()`), 10000, 'host input opens a settings-intent run through the PageController API');
    await cdp.evaluate(`window.__startupFixtureSend(${apiSettings.runId},{type:'azhou-startup',action:'complete',runId:${apiSettings.runId},skipped:true})`);
    await until(() => cdp.evaluate('window.__startupAPI.status().phase === "complete"'), 3000,
      'cancel the API-opened settings run');
    const apiFocusRestored = await cdp.evaluate(`(()=>{
      const input=document.querySelector('textarea');return document.activeElement===input;
    })()`);
    assert.equal(apiFocusRestored, true, 'API-opened settings returns focus to the previously focused host input');
    return { before: { runId: before.runId, phase: before.phase }, replay: { runId: replay.runId, phase: replay.phase },
      spec, apiSettings: { runId: apiSettings.runId, phase: apiSettings.phase }, apiFocusRestored };
  });
  await check('complete exposes the appearance button, opens settings, and cancellation restores focus without replay', async () => {
    const play = await cdp.evaluate('window.__startupAPI.status()');
    await cdp.evaluate(`window.__startupFixtureSend(${play.runId},{type:'azhou-startup',action:'complete',runId:${play.runId},skipped:false})`);
    assert.equal((await cdp.evaluate('window.__startupAPI.status()')).phase, 'complete');
    assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0);
    assert.equal(await cdp.evaluate(`(()=>{const input=document.querySelector('textarea');input.focus();return document.activeElement===input;})()`), true);
    const entry = await appearanceEntryMetrics();
    assert.equal(entry.display, 'block');
    assert.equal(entry.position, 'fixed');
    assert.equal(entry.buttonPosition, 'static');
    assert.equal(entry.left, '10px');
    assert.equal(entry.bottom, '72px');
    assert.ok(entry.rect.width >= 39 && entry.rect.width <= 44,
      'the synthetic appearance button stays compact without an avatar: ' + JSON.stringify(entry.rect));
    assert.equal(entry.padding, '5px 9px 5px 5px');
    assert.equal(entry.buttonText, '阿舟');
    assert.equal(entry.buttonAriaLabel, '阿舟主题与外观');
    assert.equal(entry.entryHit, true);
    assert.equal(entry.buttonHit, true);
    assert.equal(entry.inputHit, true);
    assert.equal(entry.menuHit, true);
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
    await screenshot('appearance-entry-dark.png');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
    await screenshot('appearance-entry-light.png');
    const opened = await clickAppearanceEntry();
    assert.equal(opened.focused, true);
    assert.equal(opened.state.phase, 'loading');
    const settings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='settings'&&state.ready?state:false;
    })()`), 10000, 'appearance button settings-intent ready');
    const spec = await cdp.evaluate('window.__startupFrameSpecs.at(-1)');
    assert.equal(spec.intent, 'settings');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
    await screenshot('appearance-settings-dark.png');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
    await screenshot('appearance-settings-light.png');
    assert.equal(await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      frame.contentDocument.querySelector('#startup-fixture-settings-input').focus();
      return document.activeElement===frame;
    })()`), true);
    await cdp.evaluate(`window.__startupFixtureSend(${settings.runId},{type:'azhou-startup',action:'complete',runId:${settings.runId},skipped:true})`);
    const cancelled = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(cancelled.phase, 'complete');
    assert.deepEqual(cancelled.completion, { cause: 'settings-cancel', beforeReady: false });
    const focusAfterButtonCancel = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const button=entry?.shadowRoot?.querySelector('button[aria-label="阿舟主题与外观"]');
      return {visible:entry?.style.display==='block',documentFocus:document.activeElement===entry,
        shadowFocus:entry?.shadowRoot?.activeElement===button};
    })()`);
    assert.deepEqual(focusAfterButtonCancel, { visible: true, documentFocus: true, shadowFocus: true });

    const reopen = await clickAppearanceEntry();
    assert.equal(reopen.focused, true);
    const secondSettings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='settings'&&state.ready?state:false;
    })()`), 10000, 'second settings-intent ready');
    await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      frame.contentDocument.querySelector('#startup-fixture-settings-input').focus();
      document.querySelector('#theme').focus();
    })()`);
    await cdp.evaluate(`window.__startupFixtureSend(${secondSettings.runId},{type:'azhou-startup',action:'complete',runId:${secondSettings.runId},skipped:true})`);
    assert.equal(await cdp.evaluate('document.activeElement===document.querySelector("#theme")'), true,
      'cleanup leaves a later host focus change alone');
    return { settings: { runId: settings.runId, phase: settings.phase }, completion: cancelled.completion,
      restoredHostFocus: true, preservedLaterFocus: true };
  });
  await check('appearance entry geometry in collapsed-sidebar narrow viewport', async () => {
    const state = await cdp.evaluate('window.__startupAPI.status()');
    if (state.phase === 'playing') {
      await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'complete',runId:${state.runId},skipped:false})`);
      await until(() => cdp.evaluate('window.__startupAPI.status().phase === "complete"'), 3000,
        'complete the animation before checking the appearance entry');
    }
    const originalStyles = await cdp.evaluate(`(()=>{
      const shell=document.querySelector('[data-app-shell-frame]'),sidebar=document.querySelector('.sidebar');
      return {shell:shell?.getAttribute('style'),sidebar:sidebar?.getAttribute('style')};
    })()`);
    let metrics;
    try {
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 640, height: 720, screenWidth: 640, screenHeight: 720, deviceScaleFactor: 1, mobile: false,
      });
      await cdp.evaluate(`(()=>{
        const shell=document.querySelector('[data-app-shell-frame]'),sidebar=document.querySelector('.sidebar');
        shell.style.gridTemplateColumns='64px minmax(0,1fr)';
        sidebar.style.width='64px';sidebar.style.overflow='hidden';
      })()`);
      await cdp.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
      metrics = await appearanceEntryMetrics();
      assert.ok(metrics, 'completed page still exposes the appearance entry');
      assert.equal(metrics.rect.height, 44,
        'the compact narrow-viewport appearance button retains a 44px touch target');
      await screenshot('appearance-entry-collapsed-sidebar-640x720.png');
      assert.equal(metrics.entryHit, true, 'the entry host is hit-testable in the collapsed-sidebar viewport');
      assert.equal(metrics.buttonHit, true, 'the shadow button is hit-testable in the collapsed-sidebar viewport: '
        + JSON.stringify({ rect: metrics.rect, viewport: metrics.viewport, entryHit: metrics.entryHit,
          buttonHit: metrics.buttonHit }));
      assert.equal(metrics.inputHit, true, 'the host textarea remains hit-testable in the collapsed-sidebar viewport');
      assert.equal(metrics.menuHit, true, 'the host menu remains hit-testable in the collapsed-sidebar viewport');
      assert.equal(metrics.inputOverlap.area, 0, 'the appearance entry does not overlap the host textarea');
      assert.equal(metrics.menuOverlap.area, 0, 'the appearance entry does not overlap the host menu');
      assert.equal(metrics.composerOverlap.area, 0,
        'appearance entry must not cover the protected composer surface: ' + JSON.stringify({
          button: metrics.rect, composer: metrics.composerRect, overlap: metrics.composerOverlap,
          footerLabel: metrics.composerLabelRect, footerLabelOverlap: metrics.composerLabelOverlap,
          textarea: metrics.inputRect, textareaOverlap: metrics.inputOverlap,
        }));
      return { modeledLayout: { sidebarWidth: 64, viewport: { width: 640, height: 720 } }, ...metrics };
    } finally {
      await cdp.evaluate(`(()=>{
        const shell=document.querySelector('[data-app-shell-frame]'),sidebar=document.querySelector('.sidebar');
        const restore=(node,value)=>value===null?node.removeAttribute('style'):node.setAttribute('style',value);
        if(shell)restore(shell,${JSON.stringify(originalStyles.shell)});
        if(sidebar)restore(sidebar,${JSON.stringify(originalStyles.sidebar)});
      })()`);
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 1512, height: 889, screenWidth: 1512, screenHeight: 889, deviceScaleFactor: 1, mobile: false,
      });
    }
  });
  await check('completed page remains editable and wallpaper survives animation completion', async () => {
    const result = await cdp.evaluate(`(()=>{
      const input=document.querySelector('textarea');
      input.focus();input.value='synthetic host input';
      const rect=input.getBoundingClientRect();
      return {focused:document.activeElement===input,hit:document.elementFromPoint(rect.x+8,rect.y+8)===input,
        inputValue:input.value,wallpaper:window.__startupAPI.status().wallpaper.applied,
        frameCount:document.querySelectorAll('iframe[aria-label]').length};
    })()`);
    assert.equal(result.focused, true);
    assert.equal(result.hit, true);
    assert.equal(result.inputValue, 'synthetic host input');
    assert.equal(result.wallpaper, true);
    assert.equal(result.frameCount, 0);
    return await screenshot('startup-after-complete-input.png');
  });
  await check('restore keeps host-edited property, attribute and stylesheet', async () => {
    const result = await cdp.evaluate(`(()=>{
      const root=document.documentElement, style=document.getElementById('azhou-wallpaper-style');
      root.setAttribute('data-azhou-wallpaper','host-later');
      root.style.setProperty('--azhou-wallpaper-image','host-image','important');
      root.style.setProperty('--azhou-wallpaper-wash','host-wash','important');
      style.textContent+='\\n/* host update */';
      window.__startupAPI.dispose();
      return {startup:!!window.__startupAPI.status,installed:Object.hasOwn(window,'__azhouStartup'),
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        attribute:root.getAttribute('data-azhou-wallpaper'),image:root.style.getPropertyValue('--azhou-wallpaper-image'),
        imagePriority:root.style.getPropertyPriority('--azhou-wallpaper-image'),wash:root.style.getPropertyValue('--azhou-wallpaper-wash'),
        washPriority:root.style.getPropertyPriority('--azhou-wallpaper-wash'),styleConnected:style.isConnected,
        styleChanged:style.textContent.includes('host update'),wallpaperGlobal:!!window.__azhouWallpaper};
    })()`);
    assert.deepEqual(result, { startup: true, installed: false, frameCount: 0, attribute: 'host-later',
      image: 'host-image', imagePriority: 'important', wash: 'host-wash', washPriority: 'important',
      styleConnected: true, styleChanged: true, wallpaperGlobal: false });
    return result;
  });

  await navigate('/fixture.html?hold-decode=1&no-initial-wallpaper=1');
  await check('a same-run disable invalidates a real pending wallpaper decode before DOM commit', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI.status();return value.phase==='playing'&&value.ready?value:false;
    })()`), 10000, 'playing with wallpaper initially disabled');
    await cdp.evaluate(`(()=>{window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:42});return true})()`);
    await until(() => cdp.evaluate('window.__decodeGateCount===1'), 10000, 'first real decode gate');
    await cdp.evaluate(`(()=>{window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:0});return true})()`);
    const disabled = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(disabled.wallpaper.applied, false);
    assert.equal(disabled.wallpaper.reason, 'disabled');
    await cdp.evaluate('window.__releaseDecodeAt(0)');
    await until(() => cdp.evaluate('window.__decodePending===false'), 5000, 'stale decode completion');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,150))');
    const after = await cdp.evaluate(`({wallpaper:window.__startupAPI.status().wallpaper,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
      wallpaperGlobal:!!window.__azhouWallpaper})`);
    assert.equal(after.wallpaper.applied, false);
    assert.equal(after.wallpaper.reason, 'disabled');
    assert.equal(after.styleCount, 0);
    assert.equal(after.rootAttribute, null);
    assert.equal(after.wallpaperGlobal, false);
    return { before: { runId: state.runId, phase: state.phase }, disabled, after };
  });

  await navigate('/fixture.html?hold-decode=1&no-initial-wallpaper=1');
  await check('out-of-order nonzero background requests keep the last requested appearance', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI.status();return value.phase==='playing'&&value.ready?value:false;
    })()`), 10000, 'playing with wallpaper initially disabled');
    const sendBackground = strength => cdp.evaluate(`(()=>{window.__startupFixtureSend(${state.runId},{
      type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:${strength}});return true})()`);
    await sendBackground(42);
    await until(() => cdp.evaluate('window.__decodeGateCount===1'), 10000, 'first nonzero decode gate');
    await sendBackground(22);
    await until(() => cdp.evaluate('window.__decodeGateCount===2'), 10000, 'second nonzero decode gate');
    await cdp.evaluate('window.__releaseDecodeAt(1)');
    const latest = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.wallpaper.applied&&state.wallpaper.washMatched?state:false;
    })()`), 10000, 'latest nonzero background commit');
    const committed = await cdp.evaluate(`({wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
      image:document.documentElement.style.getPropertyValue('--azhou-wallpaper-image'),
      wallpaper:window.__azhouWallpaper.status()})`);
    assert.equal(latest.wallpaper.applied, true);
    await cdp.evaluate('window.__releaseDecodeAt(0)');
    await until(() => cdp.evaluate('window.__decodePending===false&&window.__fixtureBlobCount===1'), 5000, 'stale request Blob cleanup');
    const after = await cdp.evaluate(`({wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
      image:document.documentElement.style.getPropertyValue('--azhou-wallpaper-image'),
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      wallpaper:window.__startupAPI.status().wallpaper})`);
    assert.equal(after.wash, committed.wash);
    assert.equal(after.image, committed.image);
    assert.equal(after.styleCount, 1);
    assert.equal(after.wallpaper.applied, true);
    assert.equal(after.wallpaper.washMatched, true);
    return { latestStrength: 22, committed, after };
  });

  await navigate('/fixture.html?legacy=1&legacy-only=1');
  await check('compiled native helpers recognize the exact legacy wallpaper without a controller and restore it', async () => {
    const before = await evaluateNativeHelper('statusSource', { startup: 'none' });
    assert.equal(before.applied, true);
    assert.deepEqual(before.startup, { installed: false });
    assert.deepEqual(await evaluateNativeHelper('applyGuardSource', { startup: 'none' }), { state: 'ready', applied: false });
    await cdp.evaluate("window.__fixtureSavedValue='fixture-saved-wallpaper-strength-42'");
    const restored = await evaluateNativeHelper('restoreSource', { startup: 'none' });
    assert.deepEqual(restored, { restored: true, applied: false });
    const after = await cdp.evaluate(`({savedValue:window.__fixtureSavedValue,wallpaper:!!window.__azhouWallpaper,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper')})`);
    assert.deepEqual(after, { savedValue: 'fixture-saved-wallpaper-strength-42', wallpaper: false,
      styleCount: 0, rootAttribute: null });
    return { before, restored, after };
  });

  for (const scenario of [
    { label: 'absent wash baseline', query: '', expectedWash: '', expectedPriority: '' },
    { label: 'host wash important baseline', query: '&legacy-wash=host-important', expectedWash: 'host-wash', expectedPriority: 'important' },
    { label: 'later host wash edit', query: '', editWash: true, expectedWash: 'host-later', expectedPriority: 'important' },
  ]) {
    await navigate('/fixture.html?legacy=1' + scenario.query);
    await check('frozen legacy wallpaper replacement restores ' + scenario.label, async () => {
      const setup = await cdp.evaluate(`({legacyError:window.__legacyWallpaperError||'',
        legacyApplied:window.__legacyWallpaperAPI?.status().applied===true,controller:typeof window.__startupAPI?.status==='function'})`);
      assert.equal(setup.legacyError, '', JSON.stringify(setup));
      assert.equal(setup.legacyApplied, true, JSON.stringify(setup));
      assert.equal(setup.controller, true, JSON.stringify(setup));
      const state = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status();return value.phase==='playing'&&value.ready?value:false;
      })()`), 10000, 'controller ready after frozen legacy wallpaper takeover');
      assert.equal(await cdp.evaluate('window.__azhouWallpaper===window.__legacyWallpaperAPI'), true,
        'legacy wallpaper remains the active owner until this controlled takeover request');
      await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:42})`);
      const committed = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status(),api=window.__azhouWallpaper;
        return value.wallpaper.applied&&api!==window.__legacyWallpaperAPI
          ?{state:value,owner:api.owner,version:api.version,apiApplied:api.status().applied}:false;
      })()`), 10000, 'candidate wallpaper after legacy dispose');
      assert.equal(committed.state.wallpaper.applied, true);
      assert.equal(committed.owner, 'azhou.codex-startup-animation');
      assert.equal(committed.version, '0.9.0');
      assert.equal(committed.apiApplied, true);
      if (scenario.editWash) await cdp.evaluate("document.documentElement.style.setProperty('--azhou-wallpaper-wash','host-later','important')");
      const beforeRestore = await cdp.evaluate(`({wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
        priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-wash')})`);
      await cdp.evaluate('window.__startupAPI.dispose()');
      const restored = await cdp.evaluate(`({startup:Object.hasOwn(window.__fixtureHost,'__azhouStartup'),
        wallpaper:!!window.__azhouWallpaper,styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
        wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
        priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-wash')})`);
      assert.deepEqual(restored, { startup: false, wallpaper: false, styleCount: 0, rootAttribute: null,
        wash: scenario.expectedWash, priority: scenario.expectedPriority });
      return { scenario: scenario.label, beforeRestore, restored };
    });
  }

  await navigate('/fixture.html?hold-body=1');
  await check('real DOM observer waits for a delayed body and disconnects after mount', async () => {
    const before = await cdp.evaluate(`({phase:window.__startupAPI.status().phase,frames:document.querySelectorAll('iframe[aria-label]').length})`);
    assert.deepEqual(before, { phase: 'loading', frames: 0 });
    await cdp.evaluate('window.__releaseBody()');
    const state = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='playing'&&state.ready?state:false;
    })()`), 10000, 'controller starts after body appears');
    assert.equal(state.overlay, true);
    return { before, state: { phase: state.phase, ready: state.ready, runId: state.runId } };
  });

  await navigate('/fixture.html?hold-decode=1');
  await check('real late image decode after dispose cannot restore wallpaper or revive a run', async () => {
    await until(() => cdp.evaluate('window.__decodePending === true'), 10000, 'real Blob image decode gate');
    const before = await cdp.evaluate('({phase:window.__startupAPI.status().phase,blobCount:window.__fixtureBlobCount})');
    await cdp.evaluate('window.__startupAPI.dispose()');
    await cdp.evaluate('window.__releaseDecode()');
    const after = await until(() => cdp.evaluate(`(()=>({
      blobCount:window.__fixtureBlobCount,wallpaper:!!window.__azhouWallpaper,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      installed:Object.hasOwn(window,'__azhouStartup'),frameCount:document.querySelectorAll('iframe[aria-label]').length
    }))()`), 5000, 'late decode cleanup');
    assert.equal(before.phase, 'playing');
    assert.equal(before.blobCount, 1);
    assert.deepEqual(after, { blobCount: 0, wallpaper: false, styleCount: 0, installed: false, frameCount: 0 });
    return { before, after };
  });

  for (const [path, expectedReason] of [
    ['/csp-style.html', 'wallpaper-unsupported'],
    ['/csp-blob.html', 'wallpaper-unsupported'],
  ]) {
    await navigate(path);
    await check('CSP refusal is visible in wallpaper state: ' + path, async () => {
      const state = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status();
        return value.phase==='playing'&&value.ready&&value.wallpaper?.reason?value:false;
      })()`), 12000, 'CSP wallpaper failure with animation ready');
      assert.equal(state.wallpaper.applied, false);
      assert.equal(state.wallpaper.reason, expectedReason);
      assert.equal(state.ready, true, 'wallpaper failure does not impersonate animation readiness');
      assert.equal(await cdp.evaluate('!!window.__azhouWallpaper'), false);
      assert.equal(await cdp.evaluate('document.querySelectorAll("#azhou-wallpaper-style").length'), 0);
      return { phase: state.phase, ready: state.ready, wallpaper: state.wallpaper };
    });
  }

  await navigate('/fixture.html');
  await check('compiled native restore removes active startup and wallpaper while preserving the saved value', async () => {
    await until(() => cdp.evaluate(`(()=>{const state=window.__startupAPI?.status();return state?.phase==='playing'&&state.ready&&state.wallpaper.applied?state:false;})()`),
      10000, 'active controller and wallpaper for native restore');
    await cdp.evaluate("window.__fixtureSavedValue='fixture-saved-wallpaper-strength-42'");
    const restored = await evaluateNativeHelper('restoreSource');
    assert.deepEqual(restored, { restored: true, applied: false, startup: true });
    const after = await cdp.evaluate(`({savedValue:window.__fixtureSavedValue,
      startup:Object.hasOwn(window.__fixtureHost,'__azhouStartup'),wallpaper:!!window.__azhouWallpaper,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper')})`);
    assert.deepEqual(after, { savedValue: 'fixture-saved-wallpaper-strength-42', startup: false,
      wallpaper: false, frameCount: 0, styleCount: 0, rootAttribute: null });
    return { restored, after };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  await check('the real installer warms both normalized images before ready and skip completes once through the default iframe mount', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI?.status();return value?.phase==='playing'&&value.ready?value:false;
    })()`), 15000, 'animation payload prepared through default iframe mount');
    const beforeSkip = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const doc=frame?.contentDocument,stage=doc?.querySelector('[data-agent-skin-stage]');
      return {frameCount:document.querySelectorAll('iframe[aria-label]').length,
        root:!!stage,prewarmed:stage?.dataset.prewarmed==='true',duration:stage?.dataset.duration,
        canvas:doc?.querySelector('canvas')?.dataset.coordinateSize,
        skip:!!doc?.querySelector('[data-agent-skin-skip]')};
    })()`);
    assert.deepEqual(beforeSkip, { frameCount: 1, root: true, prewarmed: true, duration: '12', canvas: '1536x1024', skip: true });
    await cdp.evaluate(`(()=>{
      const button=document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]');
      button.click();button.click();
    })()`);
    const completed = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI.status();return value.phase==='complete'&&!value.overlay?value:false;
    })()`), 5000, 'idempotent startup skip');
    assert.deepEqual(completed.completion, { cause: 'skip', beforeReady: false });
    assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0);
    return { readyRun: { runId: state.runId, phase: state.phase, ready: state.ready }, beforeSkip, completed: completed.completion };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&wallpaper-fail=1&wallpaper-hold=11');
  await check('real settings UI uses its public API and appearance button across cancel, save, conflict, replay and disposal', async () => {
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'actual animation play frame prepared with generated assets');
    assert.equal(initial.wallpaper.reason, 'disabled', 'generated defaults disable host wallpaper before settings are saved');
    const initialRun = await cdp.evaluate(`window.__startupAnimationRuns.at(-1)?.runId`);
    assert.equal(initialRun, initial.runId);
    assert.equal(await cdp.evaluate(`window.__startupAnimationRuns.at(-1)?.intent`), 'play');

    const childAPI = await cdp.evaluate(`(()=>{
      const accepted=window.__startupAPI.openSettings();
      const frame=document.querySelector('iframe[aria-label]');
      return {accepted,count:document.querySelectorAll('iframe[aria-label]').length,
        dialog:frame.contentDocument.querySelector('dialog')?.open===true,state:window.__startupAPI.status()};
    })()`);
    assert.equal(childAPI.accepted, true);
    assert.equal(childAPI.count, 1, 'opening through the public API does not replace the run');
    assert.equal(childAPI.dialog, true, 'the actual child settings dialog opens');
    assert.equal(childAPI.state.phase, 'settings');
    assert.equal(childAPI.state.runId, initial.runId);
    const unsavedDraft = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),doc=frame.contentDocument;
      const title=doc.querySelector('input[aria-label^="启动标题"]');
      title.value='Discard draft';title.dispatchEvent(new Event('input',{bubbles:true}));
      const strength=doc.querySelector('input[type="range"]');
      strength.value='42';strength.dispatchEvent(new Event('input',{bubbles:true}));
      return {title:title.value,strength:strength.value,hostWallpaper:!!window.__azhouWallpaper,
        wallpaper:window.__startupAPI.status().wallpaper};
    })()`);
    assert.deepEqual(unsavedDraft.wallpaper, { applied: false, reason: 'disabled', imageDecoded: false });
    assert.equal(unsavedDraft.hostWallpaper, false, 'editing the draft cannot apply a host wallpaper');
    const childCancel = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      frame.contentWindow.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true}));
      return window.__startupAPI.status();
    })()`);
    const childCancelled = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='complete'&&state.completion?.cause==='settings-cancel'?state:false;
    })()`), 5000, 'public API settings cancel');
    assert.equal(childCancel.runId, initial.runId);
    assert.deepEqual(childCancelled.completion, { cause: 'settings-cancel', beforeReady: false });
    assert.equal(await cdp.evaluate(`window.__startupAnimationRuns.length`), 1,
      'canceling an in-play draft does not create another animation run');

    const canceledEntry = await appearanceEntryMetrics();
    assert.equal(canceledEntry.display, 'block');
    const appearanceClick = await clickAppearanceEntry();
    assert.equal(appearanceClick.focused, true);
    const settingsRun = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
      return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
    })()`), 15000, 'appearance button launches the actual settings-intent frame and opens its dialog');
    assert.ok(settingsRun.runId > initial.runId);
    assert.equal(await cdp.evaluate('window.__startupAnimationRuns.at(-1).intent'), 'settings');
    assert.equal(await cdp.evaluate('window.__fixtureWallpaperApplications || 0'), 0,
      'the settings-intent frame does not apply a fallback or draft wallpaper');
    const defaultPanel = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      return {title:doc.querySelector('input[aria-label^="启动标题"]').value,
        strength:doc.querySelector('input[type="range"]').value,
        wallpaper:window.__startupAPI.status().wallpaper};
    })()`);
    assert.equal(defaultPanel.title, 'Synthetic agent', 'the canceled draft was not persisted');
    assert.equal(defaultPanel.strength, '0');
    assert.deepEqual(defaultPanel.wallpaper, { applied: false, reason: 'disabled', imageDecoded: false });
    await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const title=doc.querySelector('input[aria-label^="启动标题"]');
      title.value='Local draft';title.dispatchEvent(new Event('input',{bubbles:true}));
      const strength=doc.querySelector('input[type="range"]');
      strength.value='42';strength.dispatchEvent(new Event('input',{bubbles:true}));
    })()`);
    assert.equal(await cdp.evaluate('window.__fixtureWallpaperApplications || 0'), 0,
      'editing an unopened run still has no host wallpaper side effect');

    const externalCommit = await cdp.evaluate(`(async()=>{
      const assets=window.__startupAnimationRuns[0].assets;
      const api=window.createImageSettings({document,Image,URL,indexedDB,performance,
        setTimeout:setTimeout.bind(window),clearTimeout:clearTimeout.bind(window)});
      try{
        const loaded=await api.load(assets);
        const saved=await api.save({...loaded.settings,introTitle:'External',wallpaperStrength:42});
        return {reason:loaded.reason,baseline:loaded.baseline,title:saved.introTitle,strength:saved.wallpaperStrength};
      }finally{api.dispose();}
    })()`);
    assert.equal(externalCommit.reason, '');
    assert.equal(externalCommit.baseline, undefined);
    assert.equal(externalCommit.title, 'External');
    assert.equal(externalCommit.strength, 42);
    await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
    })()`);
    const conflictStatus = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const status=frame?.contentDocument.querySelector('[data-agent-skin-settings] [aria-live="polite"]');
      return status?.textContent.includes('其他页面已更新设置')?status.textContent:false;
    })()`), 10000, 'settings transaction detects a real concurrent page update');
    const conflictState = await cdp.evaluate(`({state:window.__startupAPI.status(),runCount:window.__startupAnimationRuns.length,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      dialogOpen:document.querySelector('iframe[aria-label]').contentDocument.querySelector('dialog')?.open})`);
    assert.equal(conflictState.state.phase, 'settings');
    assert.equal(conflictState.state.runId, settingsRun.runId);
    assert.equal(conflictState.runCount, 2, 'failed save did not send settings-close or replay');
    assert.equal(conflictState.frameCount, 1);
    assert.equal(conflictState.dialogOpen, true);
    assert.ok(conflictStatus.includes('其他页面已更新设置'));

    await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      frame.contentDocument.querySelector('button[aria-label="取消并关闭设置"]').click();
    })()`);
    const conflictCancelled = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='complete'&&state.completion?.cause==='settings-cancel'?state:false;
    })()`), 5000, 'cancel after conflict keeps the external record and avoids replay');
    assert.equal(conflictCancelled.runId, settingsRun.runId);

    const retryClick = await clickAppearanceEntry();
    assert.equal(retryClick.focused, true);
    const retrySettings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
      return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
    })()`), 15000, 'appearance button reopens settings after the failed baseline is refreshed');
    assert.ok(retrySettings.runId > settingsRun.runId);
    const retryValues = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      return {title:doc.querySelector('input[aria-label^="启动标题"]').value,
        strength:doc.querySelector('input[type="range"]').value};
    })()`);
    assert.deepEqual(retryValues, { title: 'External', strength: '42' });
    await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const title=doc.querySelector('input[aria-label^="启动标题"]');
      title.value='Saved title';title.dispatchEvent(new Event('input',{bubbles:true}));
      doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
    })()`);
    const savedPlay = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='playing'&&state.ready&&state.runId> ${retrySettings.runId}?state:false;
    })()`), 15000, 'transaction complete starts the new play run');
    const replay = await cdp.evaluate(`({run:window.__startupAnimationRuns.at(-1),applications:window.__fixtureWallpaperApplications || 0,
      notice:document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-wallpaper-result]')?.textContent,
      state:window.__startupAPI.status()})`);
    assert.equal(replay.run.intent, 'play');
    assert.equal(replay.run.settingsCommitted, true);
    assert.equal(replay.applications, 1);
    assert.equal(replay.state.wallpaper.reason, 'wallpaper-unsupported');
    const expectedWallpaperNotice = await cdp.evaluate(`window.createLocalization({locale:document.documentElement.lang})
      .t('animation.wallpaper.failed.body')`);
    assert.ok(replay.notice.includes(expectedWallpaperNotice),
      'post-commit wallpaper failure keeps its localized child result');
    const settingsResources = await cdp.evaluate(`(()=>{
      const run=window.__startupAnimationRuns.find(item=>item.runId===${retrySettings.runId});
      return run.handle.preview.report().resources;
    })()`);
    for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
      assert.equal(settingsResources[resource], 0, 'old settings frame releases ' + resource + ' after replay');
    }

    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    await until(() => cdp.evaluate(`document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog')?.open`),
      5000, 'public API opens settings after persistence');
    const persistedValues = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      return {title:doc.querySelector('input[aria-label^="启动标题"]').value,
        strength:doc.querySelector('input[type="range"]').value};
    })()`);
    assert.deepEqual(persistedValues, { title: 'Saved title', strength: '42' },
      'the replay child loaded committed fields before preparing the frame');

    const settingsReplayRuns = [{ runId: savedPlay.runId, intent: replay.run.intent,
      committed: replay.run.settingsCommitted, subtitle: 'Generated fixture only' }];
    let currentReplayRunId = savedPlay.runId;
    let expectedSubtitle = 'Generated fixture only';
    for (let cycle = 2; cycle <= 10; cycle++) {
      if (cycle > 2) {
        assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
        await until(() => cdp.evaluate(`(()=>{
          const state=window.__startupAPI.status();
          const dialog=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog');
          return state.phase==='settings'&&state.runId===${currentReplayRunId}&&dialog?.open?state:false;
        })()`), 5000, 'public settings API before saved replay ' + cycle);
      }
      const openedValues = await cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        return {state:{phase:state.phase,runId:state.runId},
          title:doc.querySelector('input[aria-label^="启动标题"]').value,
          subtitle:doc.querySelector('textarea[aria-label^="背景字幕"]').value,
          strength:doc.querySelector('input[type="range"]').value};
      })()`);
      assert.deepEqual(openedValues, { state: { phase: 'settings', runId: currentReplayRunId },
        title: 'Saved title', subtitle: expectedSubtitle, strength: '42' },
      'each replay reloads the committed record before settings opens again');
      const nextSubtitle = 'Generated replay ' + cycle;
      await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        const subtitle=doc.querySelector('textarea[aria-label^="背景字幕"]');
        subtitle.value=${JSON.stringify(nextSubtitle)};subtitle.dispatchEvent(new Event('input',{bubbles:true}));
        doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
      })()`);
      const nextReplay = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='playing'&&state.ready&&state.runId>${currentReplayRunId}
          &&window.__fixtureWallpaperApplications===${cycle}?{state,run:window.__startupAnimationRuns.at(-1)}:false;
      })()`), 15000, 'settings save ' + cycle + ' creates a fresh play run');
      assert.equal(nextReplay.run.intent, 'play');
      assert.equal(nextReplay.run.settingsCommitted, true);
      const released = await cdp.evaluate(`(()=>{
        const run=window.__startupAnimationRuns.find(item=>item.runId===${currentReplayRunId});
        return run.handle.preview.report().resources;
      })()`);
      for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
        assert.equal(released[resource], 0, 'settings replay ' + cycle + ' releases old ' + resource);
      }
      settingsReplayRuns.push({ runId: nextReplay.state.runId, intent: nextReplay.run.intent,
        committed: nextReplay.run.settingsCommitted, subtitle: nextSubtitle, released });
      currentReplayRunId = nextReplay.state.runId;
      expectedSubtitle = nextSubtitle;
    }
    assert.equal(settingsReplayRuns.length, 10, 'ten saved settings runs were prepared');
    const lateRun = currentReplayRunId;
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),dialog=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog');
      return state.phase==='settings'&&state.runId===${lateRun}&&dialog?.open?true:false;
    })()`), 5000, 'public settings API opens the final replay before the held late result');
    await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const subtitle=doc.querySelector('textarea[aria-label^="背景字幕"]');
      subtitle.value='Late wallpaper test';subtitle.dispatchEvent(new Event('input',{bubbles:true}));
      doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
    })()`);
    const lateApply = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='playing'&&state.ready&&state.runId>${lateRun}
        &&window.__fixtureWallpaperApplications===11?{state,run:window.__startupAnimationRuns.at(-1)}:false;
    })()`), 15000, 'late committed wallpaper result is held across disposal after ten saved replays');
    assert.equal(lateApply.run.settingsCommitted, true);
    assert.equal(lateApply.run.intent, 'play');
    const secondSettingsResources = await cdp.evaluate(`(()=>{
      const run=window.__startupAnimationRuns.find(item=>item.runId===${lateRun});
      return run.handle.preview.report().resources;
    })()`);
    for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
      assert.equal(secondSettingsResources[resource], 0, 'second settings replay releases ' + resource);
    }
    assert.equal(await cdp.evaluate('typeof window.__releaseFixtureWallpaper'), 'function');
    await cdp.evaluate('window.__startupAPI.dispose()');
    await cdp.evaluate('window.__releaseFixtureWallpaper()');
    const afterLate = await cdp.evaluate(`(()=>{
      const held=window.__startupAnimationRuns.find(item=>item.runId===${lateApply.state.runId});
      const resources=held.handle.preview.report().resources;
      const frame=document.querySelector('iframe[aria-label]');
      return {installed:Object.hasOwn(window,'__azhouStartup'),frameCount:frame?1:0,
        wallpaper:!!window.__azhouWallpaper,resources};
    })()`);
    assert.equal(afterLate.installed, false);
    assert.equal(afterLate.frameCount, 0);
    assert.equal(afterLate.wallpaper, false);
    for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
      assert.equal(afterLate.resources[resource], 0, 'disposed replay releases ' + resource);
    }

    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
    const busyRun = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'fresh actual animation for busy Escape and dispose check');
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    await until(() => cdp.evaluate(`document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog')?.open`),
      5000, 'public settings API opens the actual panel for busy Escape check');
    const busyStart = await cdp.evaluate(`(async()=>{
      const frame=document.querySelector('iframe[aria-label]'),win=frame.contentWindow,doc=frame.contentDocument;
      const proto=win.HTMLImageElement.prototype;
      let owner=proto,descriptor;
      while(owner&&!descriptor){descriptor=Object.getOwnPropertyDescriptor(owner,'src');owner=Object.getPrototypeOf(owner);}
      if(!descriptor?.set)throw new Error('image source setter unavailable in isolated Chrome');
      Object.defineProperty(proto,'src',{configurable:true,enumerable:descriptor.enumerable,
        get:descriptor.get,set(value){
          if(String(value).startsWith('blob:')){win.__heldSettingsDecode={image:this,onload:this.onload};return;}
          return descriptor.set.call(this,value);
        }});
      const canvas=doc.createElement('canvas');canvas.width=64;canvas.height=64;
      const context=canvas.getContext('2d');context.fillStyle='#f6a55a';context.fillRect(0,0,64,64);
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
      const file=new win.File([blob],'generated-busy.png',{type:'image/png'});
      const input=doc.querySelector('input[data-agent-skin-image-input="avatar"]');
      const transfer=new win.DataTransfer();transfer.items.add(file);input.files=transfer.files;
      input.dispatchEvent(new win.Event('change',{bubbles:true}));
      for(let attempt=0;attempt<30&&!win.__heldSettingsDecode;attempt++)
        await new Promise(resolve=>win.setTimeout(resolve,0));
      const disabled=input.disabled,open=doc.querySelector('dialog').open;
      const fileInputs=[...doc.querySelectorAll('input[type="file"]')];
      const footerButtons=[...doc.querySelectorAll('[data-agent-skin-settings] footer button')];
      const save=footerButtons.at(-1),cancel=footerButtons.at(-2);
      save.click();
      const escape=new win.KeyboardEvent('keydown',{key:'Escape',cancelable:true});
      win.dispatchEvent(escape);
      const held=win.__heldSettingsDecode;
      window.__releaseLateSettingsDecode=()=>held?.onload?.call(held.image);
      return {disabled,otherImportDisabled:fileInputs[1]?.disabled===true,saveDisabled:save.disabled,
        cancelDisabled:cancel.disabled,open,escapePrevented:escape.defaultPrevented,held:Boolean(held),
        runId:window.__startupAPI.status().runId};
    })()`);
    assert.equal(busyStart.disabled, true, 'an active import locks settings controls synchronously');
    assert.equal(busyStart.otherImportDisabled, true, 'a second image import is unavailable while busy');
    assert.equal(busyStart.saveDisabled, true, 'save is unavailable while import is busy');
    assert.equal(busyStart.cancelDisabled, true, 'local cancel is unavailable while import is busy');
    assert.equal(busyStart.open, true);
    assert.equal(busyStart.escapePrevented, true);
    assert.equal(busyStart.held, true, 'the generated import decoder is held for the late-callback check');
    assert.equal(busyStart.runId, busyRun.runId);
    const busyStillOpen = await cdp.evaluate(`({phase:window.__startupAPI.status().phase,runId:window.__startupAPI.status().runId,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      dialogOpen:document.querySelector('iframe[aria-label]').contentDocument.querySelector('dialog')?.open})`);
    assert.equal(busyStillOpen.phase, 'settings');
    assert.equal(busyStillOpen.runId, busyRun.runId);
    assert.equal(busyStillOpen.frameCount, 1);
    assert.equal(busyStillOpen.dialogOpen, true, 'Esc cannot cancel while a child image operation is busy');
    await cdp.evaluate('window.__startupAPI.dispose()');
    const busyResources = await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.report().resources');
    const lateImportAfterDispose = await cdp.evaluate(`(()=>{
      const invoked=typeof window.__releaseLateSettingsDecode==='function';
      window.__releaseLateSettingsDecode?.();
      const frame=document.querySelector('iframe[aria-label]');
      return {invoked,installed:Object.hasOwn(window,'__azhouStartup'),frameCount:frame?1:0,
        animationRunCount:window.__startupAnimationRuns.length};
    })()`);
    assert.equal(lateImportAfterDispose.invoked, true);
    assert.equal(lateImportAfterDispose.installed, false);
    assert.equal(lateImportAfterDispose.frameCount, 0);
    for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
      assert.equal(busyResources[resource], 0, 'disposed busy-import frame releases ' + resource);
    }
    const lateSettingsImage = { removed: lateImportAfterDispose.frameCount === 0,
      apiRemoved: !lateImportAfterDispose.installed, callbackInvoked: lateImportAfterDispose.invoked };
    assert.equal(lateSettingsImage.removed, true);
    assert.equal(lateSettingsImage.apiRemoved, true);
    return { initialRun: initial.runId, childAPI: { phase: childAPI.state.phase, runId: childAPI.state.runId },
      childCancelled: childCancelled.completion, settingsRun: settingsRun.runId,
      externalCommit, conflict: { status: conflictStatus, runId: conflictState.state.runId,
        runCount: conflictState.runCount }, replay: { runId: savedPlay.runId, committed: replay.run.settingsCommitted,
        wallpaper: replay.state.wallpaper, notice: replay.notice, released: settingsResources },
      persistedValues, settingsReplayRuns, lateRun: lateApply.state.runId, afterLate,
      busyEscape: { runId: busyRun.runId, busyStart, stillOpen: busyStillOpen,
        lateSettingsImage, released: busyResources, afterDispose: lateImportAfterDispose },
      secondReplayResources: secondSettingsResources };
  });

  await cdp.evaluate('window.__startupAPI?.dispose()');
  await cdp.evaluate(`new Promise((resolve,reject)=>{
    const request=indexedDB.deleteDatabase('azhou-codex-startup');
    request.onsuccess=()=>resolve(true);request.onerror=()=>reject(request.error);
    request.onblocked=()=>reject(new Error('fixture settings database remained open before the default-assets check'));
  })`);
  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  await check('official language and theme update the active animation and draft without adding preferences', async () => {
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      const frame=document.querySelector('iframe[title="阿舟启动动画"]');
      return state?.phase==='playing'&&state.ready&&frame?{state,frameCount:document.querySelectorAll('iframe').length}:false;
    })()`), 15000, 'localized startup frame ready for official appearance changes');
    const before = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="阿舟启动动画"]'),doc=frame.contentDocument;
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),button=entry.shadowRoot.querySelector('button');
      const report=window.__startupAnimationRuns.at(-1).handle.preview.report();
      return {runId:window.__startupAPI.status().runId,frameTitle:frame.title,frameAria:frame.getAttribute('aria-label'),
        frameSpecAppearance:window.__startupAnimationRuns.at(-1).appearance,
        locale:doc.documentElement.lang,theme:doc.documentElement.dataset.theme,
        stageLabel:doc.querySelector('[data-agent-skin-stage]').getAttribute('aria-label'),
        entryText:button.textContent,entryAria:button.getAttribute('aria-label'),
        entryTitle:button.title,report,drawnText:frame.contentWindow.__fixtureAnimationTextDraws||[]};
    })()`);
    assert.equal(before.frameSpecAppearance.locale, 'zh-CN');
    assert.equal(before.locale, 'zh-CN');
    assert.equal(before.theme, 'dark');
    assert.equal(before.frameTitle, '阿舟启动动画');
    assert.equal(before.frameAria, '阿舟启动动画');
    assert.equal(before.stageLabel, '阿舟启动动画');
    assert.equal(before.entryText, '阿舟');
    assert.equal(before.entryAria, '阿舟主题与外观');
    assert.equal(before.entryTitle, '打开主题与外观');
    assert.ok(before.drawnText.includes('Synthetic agent'), 'explicit asset title remains in the identity canvas');
    assert.ok(before.drawnText.includes('SYNTHETIC / TEST'), 'explicit asset caption remains in the identity canvas');

    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="阿舟启动动画"]');
      return window.__startupAPI.status().phase==='settings'
        &&frame?.contentDocument.querySelector('[data-agent-skin-settings]')?.open===true;
    })()`), 5000, 'actual settings dialog opens in the current play run');
    const draftBefore = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[title="阿舟启动动画"]').contentDocument;
      const title=doc.querySelector('[data-agent-skin-settings] input[type="text"]');
      const strength=doc.querySelector('[data-agent-skin-settings] input[type="range"]');
      title.value='Draft survives';title.dispatchEvent(new Event('input',{bubbles:true}));
      strength.value='33';strength.dispatchEvent(new Event('input',{bubbles:true}));
      return {title:title.value,strength:strength.value,heading:doc.querySelector('[data-agent-skin-settings] h2').textContent,
        titleLabel:title.getAttribute('aria-label')};
    })()`);
    assert.equal(draftBefore.title, 'Draft survives');
    assert.equal(draftBefore.strength, '33');
    assert.equal(draftBefore.heading, '阿舟 · 主题与外观');
    assert.equal(draftBefore.titleLabel, '启动标题（最多 16 个字符）');

    await cdp.evaluate(`(()=>{
      const root=document.documentElement;
      root.lang='en-US';root.dataset.theme='light';
      root.style.setProperty('--color-surface','#f8fafc');
      root.style.setProperty('--color-text-primary','#172033');
      root.style.setProperty('--color-text-secondary','#536176');
      root.style.setProperty('--color-border','#cbd5e1');
    })()`);
    const updated = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="Azhou startup animation"]'),doc=frame?.contentDocument;
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),button=entry?.shadowRoot?.querySelector('button');
      const dialog=doc?.querySelector('[data-agent-skin-settings]'),title=dialog?.querySelector('input[type="text"]');
      if(!frame||frame.title!=='Azhou startup animation'||doc.documentElement.lang!=='en'
        ||doc.documentElement.dataset.theme!=='light'||dialog?.querySelector('h2')?.textContent!=='Azhou · Theme & Appearance'
        ||title?.getAttribute('aria-label')!=='Startup title (up to 16 characters)')return false;
      return {runId:window.__startupAPI.status().runId,phase:window.__startupAPI.status().phase,
        frameCount:document.querySelectorAll('iframe').length,runCount:window.__startupAnimationRuns.length,
        frameTitle:frame.title,frameAria:frame.getAttribute('aria-label'),locale:doc.documentElement.lang,
        theme:doc.documentElement.dataset.theme,colorScheme:doc.documentElement.style.colorScheme,
        stage:window.__startupAnimationRuns.at(-1).handle.preview.report().stage,
        colors:Object.fromEntries(['surface','text','muted','border'].map(key=>[key,
          doc.documentElement.style.getPropertyValue('--agent-skin-'+key)])),
        entryText:button.textContent,entryAria:button.getAttribute('aria-label'),entryTitle:button.title,
        rootAria:doc.querySelector('[data-agent-skin-stage]').getAttribute('aria-label'),
        stageText:doc.querySelector('[data-agent-skin-stage-text]').textContent,
        heading:dialog.querySelector('h2').textContent,title:title.value,strength:dialog.querySelector('input[type="range"]').value,
        titleLabel:title.getAttribute('aria-label'),settingsText:dialog.textContent,
        drawnText:frame.contentWindow.__fixtureAnimationTextDraws||[],
        recordKeys:Object.keys(window.__startupAnimationRuns.at(-1).assets).sort()};
    })()`), 5000, 'official host locale/theme observer updates the current overlay and settings draft');
    assert.equal(updated.runId, before.runId);
    assert.equal(updated.phase, 'settings');
    assert.equal(updated.frameCount, 1);
    assert.equal(updated.runCount, 1);
    assert.equal(updated.frameAria, 'Azhou startup animation');
    assert.equal(updated.locale, 'en');
    assert.equal(updated.theme, 'light');
    assert.equal(updated.colorScheme, 'light');
    assert.deepEqual(updated.colors, {
      surface: '#f8fafc', text: '#172033', muted: '#536176', border: '#cbd5e1',
    });
    assert.equal(updated.entryText, 'Azhou');
    assert.equal(updated.entryAria, 'Azhou theme and appearance');
    assert.equal(updated.entryTitle, 'Open theme and appearance');
    assert.equal(updated.rootAria, 'Azhou startup animation');
    const englishStages = {
      pulse: 'The lab is lighting up', identity: 'Azhou is setting up the workspace',
      dispersing: 'The portrait and text are spreading into line art',
      scattered: 'The line art is gathering', drawing: 'Azhou and the background are appearing',
      colorize: 'Color is being added to the scene', portrait: 'Azhou is finishing the scene',
      shutter: 'The animation is almost finished', complete: 'Finished',
    };
    assert.equal(updated.stageText, englishStages[updated.stage]);
    assert.equal(updated.heading, 'Azhou · Theme & Appearance');
    assert.equal(updated.title, 'Draft survives');
    assert.equal(updated.strength, '33');
    assert.equal(updated.titleLabel, 'Startup title (up to 16 characters)');
    assert.ok(updated.drawnText.includes('Synthetic agent'), 'appearance changes preserve and redraw explicit default text');
    const inheritedSettings = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[title="Azhou startup animation"]').contentDocument;
      const value=key=>doc.querySelector('[data-agent-skin-setting-value="'+key+'"]').textContent;
      return {theme:value('theme'),locale:value('locale'),surface:value('surface'),
        sections:[...doc.querySelectorAll('[data-agent-skin-settings-section]')].map(el=>el.dataset.agentSkinSettingsSection),
        preferenceControls:doc.querySelectorAll('select,input[name="theme"],input[name="locale"],input[name="reducedMotion"]').length};
    })()`);
    assert.deepEqual(inheritedSettings, { theme: 'Light', locale: 'en', surface: '#f8fafc',
      sections: ['identity', 'startup', 'workspace', 'inherited'], preferenceControls: 0 });
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await until(() => cdp.evaluate(`document.querySelector('iframe[title="Azhou startup animation"]').contentDocument
      .querySelector('[data-agent-skin-setting-value="reducedMotion"]').textContent==='On'`), 5000, 'system motion readout')
      .catch(async error => { throw new Error(error.message + ': ' + JSON.stringify(await cdp.evaluate(`({
        outer:matchMedia('(prefers-reduced-motion: reduce)').matches,
        inner:document.querySelector('iframe').contentWindow.matchMedia('(prefers-reduced-motion: reduce)').matches,
        reduced:window.__startupAnimationRuns.at(-1).handle.preview.report().reduced,
        readout:document.querySelector('iframe').contentDocument.querySelector('[data-agent-skin-setting-value="reducedMotion"]').textContent})`))); });
    await cdp.call('Emulation.setEmulatedMedia', { features: [] });
    assert.equal(updated.recordKeys.some(key => key === 'locale' || key === 'theme'), false,
      'appearance preferences are absent from the animation assets record shape');

    const settingsAPI = await cdp.evaluate(`(async()=>{
      const frame=document.querySelector('iframe[title="Azhou startup animation"]');
      const win=frame.contentWindow;
      const api=window.createImageSettings({document:frame.contentDocument,Image:win.Image,URL:win.URL,
        indexedDB:win.indexedDB,performance:win.performance,setTimeout:win.setTimeout.bind(win),
        clearTimeout:win.clearTimeout.bind(win)});
      try{
        const result=await api.load(window.__startupAnimationRuns.at(-1).assets);
        return {keys:Object.keys(result.settings).sort(),baseline:result.baseline};
      }finally{api.dispose();}
    })()`);
    assert.equal(settingsAPI.baseline, undefined);
    assert.equal(settingsAPI.keys.some(key => key === 'locale' || key === 'theme'), false,
      'the IndexedDB settings schema does not persist language or theme preferences');
    await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="Azhou startup animation"]');
      [...frame.contentDocument.querySelectorAll('[data-agent-skin-settings] footer button')]
        .find(button=>button.textContent.trim()==='Cancel')?.click();
    })()`);
    const afterCancel = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(afterCancel.runId, before.runId);
    assert.equal(afterCancel.phase, 'complete');
    return { initial: { runId: before.runId, locale: before.locale, theme: before.theme,
      entryAria: before.entryAria }, updated: { runId: updated.runId, phase: updated.phase,
      locale: updated.locale, theme: updated.theme, colors: updated.colors,
      draft: { title: updated.title, strength: updated.strength }, frameCount: updated.frameCount,
      runCount: updated.runCount }, customText: ['Synthetic agent', 'SYNTHETIC / TEST'],
      settingsKeys: settingsAPI.keys, canceledRunId: afterCancel.runId };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&settings-open-pending=1');
  await check('IDB open and get pending do not open settings from key events and Escape remains safe', async () => {
    const exercisePendingLoad = async kind => {
      if (kind === 'get') await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&settings-get-pending=1');
      const pending = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='loading'&&window.__fixtureIDBStage==='${kind==='open'?'open':'get'}'
          ?{state,stage:window.__fixtureIDBStage}:false;
      })()`), 10000, kind + ' request remains pending during startup load');
      const keys = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const parentEvent=new KeyboardEvent('keydown',{key:'b',metaKey:true,altKey:true,cancelable:true});
        window.dispatchEvent(parentEvent);
        const parentAfter=window.__startupAPI.status();
        const childEvent=new frame.contentWindow.KeyboardEvent('keydown',{key:'b',metaKey:true,altKey:true,cancelable:true});
        frame.contentWindow.dispatchEvent(childEvent);
        const childAfter=window.__startupAPI.status();
        const childDialog=frame.contentDocument.querySelector('dialog');
        const parentEscape=new KeyboardEvent('keydown',{key:'Escape',cancelable:true});
        window.dispatchEvent(parentEscape);
        const parentEscapeAfter=window.__startupAPI.status();
        return {parentPrevented:parentEvent.defaultPrevented,parentRunId:parentAfter.runId,
          parentPhase:parentAfter.phase,childPrevented:childEvent.defaultPrevented,
          childRunId:childAfter.runId,childPhase:childAfter.phase,dialogOpen:childDialog?.open===true,
          frameCount:document.querySelectorAll('iframe[aria-label]').length,
          parentEscapePrevented:parentEscape.defaultPrevented,parentEscapePhase:parentEscapeAfter.phase,
          parentEscapeRunId:parentEscapeAfter.runId};
      })()`);
      assert.equal(keys.parentPrevented, false, 'the parent key event has no settings action before resources are ready');
      assert.equal(keys.parentPhase, 'loading');
      assert.equal(keys.parentRunId, pending.state.runId);
      assert.equal(keys.childPrevented, false, 'the child key event has no settings action');
      assert.equal(keys.childPhase, 'loading');
      assert.equal(keys.childRunId, pending.state.runId);
      assert.equal(keys.dialogOpen, false);
      assert.equal(keys.frameCount, 1);
      assert.equal(keys.parentEscapePrevented, false, 'the parent has no Escape action during a pending load');
      assert.equal(keys.parentEscapePhase, 'loading');
      assert.equal(keys.parentEscapeRunId, pending.state.runId);

      const childEscape = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const event=new frame.contentWindow.KeyboardEvent('keydown',{key:'Escape',cancelable:true});
        frame.contentWindow.dispatchEvent(event);
        return {prevented:event.defaultPrevented,state:window.__startupAPI.status()};
      })()`);
      const ended = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='skip'&&!state.overlay?state:false;
      })()`), 5000, kind + ' child Escape completes the pending run once');
      assert.equal(childEscape.prevented, true);
      assert.equal(ended.runId, pending.state.runId);
      assert.equal(await cdp.evaluate('window.__startupAnimationRuns.length'), 1,
        kind + ' pending load does not start a duplicate run');
      assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0);
      if (kind === 'get') {
        await until(() => cdp.evaluate('window.__fixtureIDBAbortCount > 0'), 1000,
          'disposing the pending get aborts its readonly transaction');
      }
      await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,100))');
      const final = await cdp.evaluate(`({state:window.__startupAPI.status(),runs:window.__startupAnimationRuns.length,
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        stage:window.__fixtureIDBStage,aborts:window.__fixtureIDBAbortCount||0})`);
      assert.equal(final.state.phase, 'complete', 'late storage callbacks cannot revive the dismissed run');
      assert.equal(final.runs, 1);
      assert.equal(final.frameCount, 0);
      return { pending, keys, childEscape: { prevented: childEscape.prevented,
        cause: ended.completion, abortCount: final.aborts }, final: final.state.phase };
    };
    const open = await exercisePendingLoad('open');
    const get = await exercisePendingLoad('get');
    return { open, get };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  await check('a top-level page refresh reloads committed settings fields from IndexedDB', async () => {
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'startup play is ready before saving refresh fields');
    const fields = { introTitle: 'Refresh title', introCaption: 'REFRESH / PERSISTED',
      artworkSubtitle: 'Synthetic settings after top-level reload', wallpaperStrength: 19 };
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true,
      'the supported PageController API opens settings during playback');
    await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      const dialog=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog');
      return state.phase==='settings'&&dialog?.open?state:false;
    })()`), 5000, 'settings dialog opens before the committed reload setup');
    await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      for(const [label,value] of [["input[aria-label^='启动标题']",${JSON.stringify(fields.introTitle)}],
        ["input[aria-label^='标题说明']",${JSON.stringify(fields.introCaption)}],
        ["textarea[aria-label^='背景字幕']",${JSON.stringify(fields.artworkSubtitle)}]]){
        const control=doc.querySelector(label);control.value=value;control.dispatchEvent(new Event('input',{bubbles:true}));
      }
      const strength=doc.querySelector('input[type="range"]');strength.value='${fields.wallpaperStrength}';
      strength.dispatchEvent(new Event('input',{bubbles:true}));
      doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
    })()`);
    const saved = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),run=window.__startupAnimationRuns.at(-1);
      return state.phase==='playing'&&state.ready&&state.runId>${initial.runId}?{state,run}:false;
    })()`), 15000, 'the settings transaction commits before top-level refresh');
    assert.equal(saved.run.settingsCommitted, true);
    const timeOriginBeforeReload = await cdp.evaluate('performance.timeOrigin');
    await cdp.call('Page.reload', { ignoreCache: true });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'top-level refresh completes');
    await until(() => cdp.evaluate('window.__startupInstallResult !== undefined'), 10000,
      'top-level refresh installs a fresh controller');
    const after = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status(),run=window.__startupAnimationRuns?.at(-1);
      return state?.phase==='playing'&&state.ready&&run?.intent==='play'?{state,run}:false;
    })()`), 15000, 'top-level refresh reloads persisted settings and prepares the startup');
    const timeOriginAfterReload = await cdp.evaluate('performance.timeOrigin');
    assert.notEqual(timeOriginAfterReload, timeOriginBeforeReload, 'Page.reload created a new top-level document');
    assert.equal(await cdp.evaluate('window.__startupAnimationRuns.length'), 1);
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true,
      'the refreshed PageController API opens the actual settings dialog');
    await until(() => cdp.evaluate(`document.querySelector('iframe[aria-label]')
      ?.contentDocument.querySelector('dialog')?.open`), 5000,
    'the refreshed top-level page opens its actual settings dialog for a field readback');
    const reloadedFields = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      return {introTitle:doc.querySelector('input[aria-label^="启动标题"]').value,
        introCaption:doc.querySelector('input[aria-label^="标题说明"]').value,
        artworkSubtitle:doc.querySelector('textarea[aria-label^="背景字幕"]').value,
        wallpaperStrength:Number(doc.querySelector('input[type="range"]').value)};
    })()`);
    assert.deepEqual(reloadedFields, fields,
      'the new top-level document reads all committed fields from IndexedDB');
    return { committedBeforeReload: saved.run.settingsCommitted, afterReload: {
      runId: after.run.runId, intent: after.run.intent, settingsCommitted: after.run.settingsCommitted,
    }, reloadedFields, timeOriginChanged: timeOriginAfterReload !== timeOriginBeforeReload };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&natural-settings-replay=1');
  await check('ten saved settings runs naturally complete and release resources through a five-second settle', async () => {
    await cdp.call('Performance.enable');
    const heapMetrics = async () => {
      const { metrics = [] } = await cdp.call('Performance.getMetrics');
      const values = Object.fromEntries(metrics.map(metric => [metric.name, metric.value]));
      return {
        available: Number.isFinite(values.JSHeapUsedSize),
        usedJSHeapBytes: Number.isFinite(values.JSHeapUsedSize) ? values.JSHeapUsedSize : null,
        totalJSHeapBytes: Number.isFinite(values.JSHeapTotalSize) ? values.JSHeapTotalSize : null,
        timestamp: Number.isFinite(values.Timestamp) ? values.Timestamp : null,
      };
    };
    const zeroResourceKeys = ['liveImages', 'liveBitmaps', 'liveCanvases', 'livePaths', 'liveRAF', 'liveObjectURLs'];
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'actual animation is ready before the first settings save');
    let priorRunId = initial.runId;
    let expectedTitle = null;
    const cycles = [];

    for (let round = 1; round <= 10; round++) {
      assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true,
        'the public API opens settings for replay ' + round);
      const panel = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const frame=document.querySelector('iframe[aria-label]');
        const dialog=frame?.contentDocument.querySelector('dialog');
        const title=frame?.contentDocument.querySelector('input[aria-label^="启动标题"]')?.value;
        return state.phase==='settings'&&dialog?.open?{state,title}:false;
      })()`), 10000, 'settings panel opens before natural replay ' + round);
      if (expectedTitle === null) expectedTitle = panel.title;
      else assert.equal(panel.title, expectedTitle, 'replay ' + round + ' reads the previous committed title');
      const nextTitle = 'Natural run ' + String(round).padStart(2, '0');
      await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        const title=doc.querySelector('input[aria-label^="启动标题"]');
        title.value=${JSON.stringify(nextTitle)};title.dispatchEvent(new Event('input',{bubbles:true}));
        doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
      })()`);
      const started = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),run=window.__startupAnimationRuns.at(-1);
        return state.phase==='playing'&&state.ready&&state.runId>${priorRunId}
          ?{state,run}:false;
      })()`), 15000, 'save ' + round + ' creates a fresh ready play run');
      assert.equal(started.run.intent, 'play');
      assert.equal(started.run.settingsCommitted, true);
      const playbackStartedAt = Date.now();
      const completed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.runId===${started.state.runId}&&state.phase==='complete'
          &&state.completion?.cause==='natural'&&!state.overlay?state:false;
      })()`), 30000, 'settings-save replay ' + round + ' completes naturally');
      const completedAt = Date.now();
      assert.deepEqual(completed.completion, { cause: 'natural', beforeReady: false });
      assert.equal(completed.completed, true);
      assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0,
        'natural completion removes the child before the settle window');
      const finalReport = await cdp.evaluate(`(()=>{
        const run=window.__startupAnimationRuns.find(item=>item.runId===${started.state.runId});
        return run.sampleDisposedResources();
      })()`);
      assert.equal(finalReport.report.completed, true);
      assert.equal(finalReport.report.skipped, false);
      assert.equal(finalReport.report.elapsed, finalReport.report.duration);
      assert.ok(finalReport.report.jsFrame.rafIntervalMs?.count > 100, 'natural playback records actual rAF samples');
      assert.ok(finalReport.report.jsFrame.renderSubmissionMs?.count > 100,
        'natural playback records actual canvas submission samples');
      for (const key of zeroResourceKeys) assert.equal(finalReport.report.resources[key], 0,
        'natural completion releases ' + key);
      assert.equal(finalReport.report.resources.framesPending, 0);
      const heapAtComplete = await heapMetrics();

      const settleStartedAt = process.hrtime.bigint();
      while (process.hrtime.bigint() - settleStartedAt < 5_000_000_000n) await delay(25);
      const settleElapsedMs = Number(process.hrtime.bigint() - settleStartedAt) / 1_000_000;
      assert.ok(settleElapsedMs >= 5000, 'each natural run gets a full five-second settle observation');
      const afterSettle = await cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const run=window.__startupAnimationRuns.find(item=>item.runId===${started.state.runId});
        const observation=run.sampleDisposedResources();
        run.sampleDisposedResources=null;
        return {state,observation,frameCount:document.querySelectorAll(
          'iframe[aria-label]').length};
      })()`);
      const heapAfterSettle = await heapMetrics();
      assert.equal(afterSettle.state.runId, started.state.runId);
      assert.equal(afterSettle.state.phase, 'complete');
      assert.deepEqual(afterSettle.state.completion, { cause: 'natural', beforeReady: false });
      assert.equal(afterSettle.frameCount, 0);
      assert.ok(afterSettle.observation.sampledAt >= finalReport.sampledAt + 5000,
        'the post-settle resource sample is freshly taken after the full five-second window');
      assert.deepEqual(afterSettle.observation.report.resources, finalReport.report.resources,
        'fresh live resource counters remain at their released values after the settle window');
      for (const key of zeroResourceKeys) assert.equal(afterSettle.observation.report.resources[key], 0);
      cycles.push({
        round,
        runId: started.state.runId,
        introTitle: nextTitle,
        completion: completed.completion,
        wallTimeFromReadyToCompleteMs: completedAt - playbackStartedAt,
        settleElapsedMs,
        resourceSampleGapMs: afterSettle.observation.sampledAt - finalReport.sampledAt,
        rafIntervalMs: finalReport.report.jsFrame.rafIntervalMs,
        renderSubmissionMs: finalReport.report.jsFrame.renderSubmissionMs,
        releasedResources: afterSettle.observation.report.resources,
        heapAtComplete,
        heapAfterSettle,
      });
      expectedTitle = nextTitle;
      priorRunId = started.state.runId;
    }
    assert.equal(cycles.length, 10);
    return {
      firstRunId: cycles[0].runId,
      lastRunId: cycles.at(-1).runId,
      cycles,
      memory: {
        javascriptHeapMetric: 'Chrome DevTools Performance.getMetrics JSHeapUsedSize/JSHeapTotalSize',
        sampledAtNaturalCompleteAndAfterEachFiveSecondSettle: true,
        systemMemoryIndependentlyMeasured: false,
        limitation: 'No OS process RSS or whole-system memory sampler was run; JS heap metrics are not system-memory measurements.',
      },
    };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&settings-blocked=1');
  await check('an unavailable settings database shows safe fallback status in playback and in the panel', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI?.status();
      const frame=document.querySelector('iframe[aria-label]');
      return value?.phase==='playing'&&value.ready&&frame?.contentDocument.querySelector('[data-agent-skin-settings-result]')?value:false;
    })()`), 15000, 'normal play shows a non-sensitive settings fallback status');
    const playbackNotice = await cdp.evaluate(`document.querySelector('iframe[aria-label]')
      .contentDocument.querySelector('[data-agent-skin-settings-result]').textContent`);
    const expectedPlaybackNotice = await cdp.evaluate(`window.createLocalization({locale:document.documentElement.lang})
      .t('settings.load.unavailable')`);
    assert.equal(playbackNotice, expectedPlaybackNotice);
    const opened = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const accepted=window.__startupAPI.openSettings();
      return {accepted,state:window.__startupAPI.status()};
    })()`);
    const panelStatus = await until(() => cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const status=doc?.querySelector('[data-agent-skin-settings] [aria-live="polite"]');
      return status?.textContent?status.textContent:false;
    })()`), 5000, 'settings panel explains the unavailable database');
    assert.equal(opened.accepted, true);
    assert.equal(opened.state.phase, 'settings');
    assert.equal(opened.state.runId, state.runId);
    assert.equal(panelStatus, '暂时无法读取保存设置；当前使用默认设置，原记录未删除。');
    assert.equal(panelStatus.includes('Synthetic'), false, 'status text does not expose stored profile values');
    return { phase: state.phase, runId: state.runId, playbackNotice, panelStatus };
  });

  await check('portrait identity and dispersing layouts keep legal titles and captions inside the registered canvas', async () => {
    const cases = [];
    for (const variant of identityVariants) {
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 1440, height: 900, screenWidth: 1440, screenHeight: 900,
        deviceScaleFactor: 1, mobile: false,
      });
      await cdp.call('Page.navigate', { url: pathToFileURL(join(variant.dir, 'index.html')).href });
      await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, variant.name + ' identity page load');
      await until(() => cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        return root?.dataset.prewarmed==='true'&&window.launcherUI?.report()?true:false;
      })()`), 15000, variant.name + ' identity assets prewarm');
      await cdp.evaluate('window.launcherUI.pause()');
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 390, height: 844, screenWidth: 390, screenHeight: 844,
        deviceScaleFactor: 1, mobile: false,
      });
      await cdp.evaluate(`window.launcherUI.updateAppearance({locale:'en',theme:'light',colors:{
        surface:'#fafafa',text:'#202020',muted:'#606060',border:'#dddddd'}})`);
      const portrait = await until(() => cdp.evaluate(`(()=>{
        const viewport=window.launcherUI.report().viewport;
        return viewport.width===390&&viewport.height===844?viewport:false;
      })()`), 3000, variant.name + ' responsive portrait relayout');
      await cdp.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
      const controls = await cdp.evaluate(`(()=>{
        const bar=document.querySelector('#preview-controls'),rect=bar.getBoundingClientRect();
        const children=['#replay','#pause','#timeline','#elapsed'].map(selector=>{
          const node=document.querySelector(selector),bounds=node.getBoundingClientRect();
          return {selector,left:bounds.left,right:bounds.right,width:bounds.width,
            contained:bounds.left>=rect.left-1&&bounds.right<=rect.right+1};
        });
        return {visible:!bar.hidden,rect:{left:rect.left,right:rect.right,width:rect.width},
          clientWidth:bar.clientWidth,scrollWidth:bar.scrollWidth,children};
      })()`);
      assert.equal(controls.visible,true,'preview controls stay visible in the narrow viewport');
      assert.ok(controls.scrollWidth<=controls.clientWidth,
        'narrow English controls do not overflow their container: '+JSON.stringify(controls));
      assert.ok(controls.children.every(child=>child.contained),
        'every narrow English control stays inside the toolbar: '+JSON.stringify(controls));
      const variantStages = [];
      for (const [seconds, expectedStage] of [[1.65, 'identity'], [4.18, 'dispersing'], [4.74, 'scattered']]) {
        await cdp.evaluate(`window.launcherUI.seek(${seconds})`);
        const state = await cdp.evaluate(`(()=>{
          const canvas=document.querySelector('[data-agent-skin-canvas]');
          const report=window.launcherUI.report();
          const scale=Math.max(innerWidth/1536,innerHeight/1024);
          const offsetX=(innerWidth-1536*scale)/2,offsetY=(innerHeight-1024*scale)/2;
          const inViewport=(x,y)=>x*scale+offsetX>=0&&x*scale+offsetX<innerWidth
            &&y*scale+offsetY>=0&&y*scale+offsetY<innerHeight;
          const samples=[];
          for(let y=64;y<960;y+=8)for(let x=64;x<1472;x+=8){
            const px=Math.round((x*scale+offsetX)*devicePixelRatio),py=Math.round((y*scale+offsetY)*devicePixelRatio);
            if(px<0||py<0||px>=canvas.width||py>=canvas.height)continue;
            const data=canvas.getContext('2d').getImageData(px,py,1,1).data;
            if(data[0]>55||data[1]>55||data[2]>55)samples.push({x,y});
          }
          return {stage:report.stage,progress:report.animationProgress,viewport:report.viewport,
            sampleCount:samples.length,offscreenSamples:samples.filter(point=>!inViewport(point.x,point.y)).length,
            identityTextSamples:samples.filter(point=>point.y>=590&&point.y<850).length,
            crop:{scale,offsetX,offsetY},resources:report.resources};
        })()`);
        const screenshotFile = `identity-${variant.name}-${String(seconds).replace('.', 'p')}s.png`;
        const shot = await screenshot(screenshotFile);
        assert.equal(state.stage, expectedStage, variant.name + ' stage at ' + seconds);
        assert.ok(state.sampleCount > 5, variant.name + ' identity art remains visible at ' + seconds + ': ' + JSON.stringify(state));
        if (seconds === 1.65 && (variant.title || variant.caption)) {
          assert.ok(state.identityTextSamples > 5, variant.name + ' identity text remains visible within the portrait canvas: ' + JSON.stringify(state));
        }
        assert.equal(state.offscreenSamples, 0, variant.name + ' visible identity samples remain inside the portrait viewport: ' + JSON.stringify(state));
        assert.equal(state.resources.liveRAF, 0, variant.name + ' preview remains paused while seeking');
        variantStages.push({ seconds, ...state, screenshot: shot.file });
      }
      cases.push({ name: variant.name, titleCodeUnits: variant.title.length,
        captionCodeUnits: variant.caption.length, portrait, controls, stages: variantStages });
    }
    return { viewport: { width: 390, height: 844, dpr: 1 }, cases };
  });

  await navigate('/fixture.html?animation=1&animation-hold=1&no-initial-wallpaper=1');
  await check('skip while decoded ImageBitmaps are pending completes before ready and closes late bitmaps', async () => {
    const held = await until(() => cdp.evaluate(`(()=>{
      const frame=window.__animationPendingFrame;
      return frame?.__fixtureHeldBitmapRequests>=2
        ?{requests:frame.__fixtureHeldBitmapRequests,releases:frame.__fixtureHeldBitmapReleases}:false;
    })()`), 10000, 'both real decoded animation bitmaps held before ready');
    const before = await cdp.evaluate(`({state:window.__startupAPI.status(),
      frameCount:document.querySelectorAll('iframe[aria-label]').length})`);
    assert.equal(before.state.phase, 'loading');
    assert.equal(before.state.ready, false);
    assert.equal(before.state.overlay, true);
    assert.equal(before.frameCount, 1);
    assert.equal(held.requests, 2);
    await cdp.evaluate(`(()=>{
      const button=document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]');
      button.click();button.click();
    })()`);
    const completed = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='complete'&&!state.overlay?state:false;
    })()`), 3000, 'early skip completes and removes the unready overlay');
    assert.equal(completed.ready, false);
    assert.deepEqual(completed.completion, { cause: 'skip', beforeReady: true });
    await until(() => cdp.evaluate('window.__animationPendingFrame.__fixtureHeldBitmapReleases===2'), 3000,
      'stale image bitmap results close after early completion');
    await delay(100);
    const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      requests:window.__animationPendingFrame.__fixtureHeldBitmapRequests,
      releases:window.__animationPendingFrame.__fixtureHeldBitmapReleases})`);
    assert.deepEqual(after.state.completion, completed.completion);
    assert.equal(after.state.ready, false, 'a late decode cannot emit ready after early completion');
    assert.equal(after.frameCount, 0);
    assert.equal(after.requests, after.releases);
    return { before: { phase: before.state.phase, ready: before.state.ready, held },
      completion: completed.completion, after: { phase: after.state.phase, ready: after.state.ready,
        frameCount: after.frameCount, requests: after.requests, releases: after.releases } };
  });

  await cdp.call('Page.addScriptToEvaluateOnNewDocument', { source: `(()=>{
    const prototype=window.MediaQueryList?.prototype;if(!prototype)return;
    const state={added:0,removed:0,active:0,windowResize:0,visualViewportResize:0,queryCount:0};
    const queries=[];
    window.addEventListener('resize',()=>state.windowResize++);
    window.visualViewport?.addEventListener('resize',()=>state.visualViewportResize++);
    Object.defineProperty(window,'__agentSkinResolutionWatch',{value:state,configurable:true});
    const matchMedia=window.matchMedia.bind(window);
    window.matchMedia=function(expression){
      const query=matchMedia(expression);
      if(String(expression).startsWith('(resolution:')){queries.push(query);state.queryCount++;}
      return query;
    };
    state.dispatchLatest=()=>queries.at(-1)?.dispatchEvent(new Event('change'))===true;
    const add=prototype.addEventListener,remove=prototype.removeEventListener;
    prototype.addEventListener=function(type,listener,options){
      if(type==='change'&&this.media?.startsWith('(resolution:')){state.added++;state.active++;}
      return add.call(this,type,listener,options);
    };
    prototype.removeEventListener=function(type,listener,options){
      if(type==='change'&&this.media?.startsWith('(resolution:')){state.removed++;state.active--;}
      return remove.call(this,type,listener,options);
    };
  })()` });
  await cdp.call('Page.navigate', { url: pathToFileURL(join(animationPreviewDir, 'index.html')).href });
  await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'synthetic Agent Skin preview load');
  const animationReady = await until(() => cdp.evaluate(`(()=>{
    const root=document.querySelector('[data-agent-skin-stage]');
    const report=window.launcherUI?.report();
    return window.launcherUI&&root?.dataset.prewarmed==='true'
      &&report.resources.liveImages+report.resources.liveBitmaps>0
      ?window.launcherUI.report():false;
  })()`), 15000, 'generated animation images prewarm through the local preview shell');
  await cdp.evaluate('window.launcherUI.pause()');

  await check('public preview report confirms static frame reuse and dynamic replay behavior', async () => {
    await cdp.evaluate('window.launcherUI.pause()');
    const readReport = () => cdp.evaluate(`(()=>{
      const report=window.launcherUI.report();
      return {elapsed:report.elapsed,stage:report.stage,completed:report.completed,skipped:report.skipped,
        sceneRenderCount:report.jsFrame.sceneRenderCount,resources:report.resources};
    })()`);
    const seekAndRead = async seconds => {
      const result = await cdp.evaluate(`(()=>{
        const accepted=window.launcherUI.seek(${seconds});
        const report=window.launcherUI.report();
        return {accepted,elapsed:report.elapsed,stage:report.stage,
          sceneRenderCount:report.jsFrame.sceneRenderCount};
      })()`);
      assert.equal(result.accepted, true, 'the public preview seek remains available');
      return result;
    };
    const initial = await readReport();
    assert.ok(Number.isInteger(initial.sceneRenderCount), 'public report exposes canvas scene submissions');

    const identityFirst = await seekAndRead(1.8);
    const identitySecond = await seekAndRead(2.4);
    const identityThird = await seekAndRead(3.7);
    assert.equal(identityFirst.stage, 'identity');
    assert.equal(identitySecond.sceneRenderCount, identityFirst.sceneRenderCount,
      'a static identity frame is submitted once while its stage and layout remain stable');
    assert.equal(identityThird.sceneRenderCount, identityFirst.sceneRenderCount);
    assert.equal(identityFirst.sceneRenderCount - initial.sceneRenderCount, 1);

    const scatteredFirst = await seekAndRead(4.8);
    const scatteredSecond = await seekAndRead(4.95);
    assert.equal(scatteredFirst.stage, 'scattered');
    assert.equal(scatteredFirst.sceneRenderCount, identityThird.sceneRenderCount + 1,
      'crossing to another static stage submits its changed frame once');
    assert.equal(scatteredSecond.sceneRenderCount, scatteredFirst.sceneRenderCount);

    const drawingFirst = await seekAndRead(5.2);
    const drawingSecond = await seekAndRead(6.2);
    assert.equal(drawingFirst.stage, 'drawing');
    assert.equal(drawingSecond.stage, 'drawing');
    assert.equal(drawingFirst.sceneRenderCount, scatteredSecond.sceneRenderCount + 1);
    assert.equal(drawingSecond.sceneRenderCount, drawingFirst.sceneRenderCount + 1,
      'animated drawing continues to submit changed frames');

    const portraitBeforePlateau = await seekAndRead(9.0);
    const portraitFirst = await seekAndRead(9.3);
    const portraitSecond = await seekAndRead(10.8);
    assert.equal(portraitBeforePlateau.stage, 'portrait');
    assert.equal(portraitFirst.stage, 'portrait');
    assert.equal(portraitSecond.stage, 'portrait');
    assert.equal(portraitBeforePlateau.sceneRenderCount, drawingSecond.sceneRenderCount + 1,
      'the portrait progress bar continues to render before it reaches 100%');
    assert.equal(portraitFirst.sceneRenderCount, portraitBeforePlateau.sceneRenderCount + 1,
      'the final progress value is rendered when the full-progress plateau begins');
    assert.equal(portraitSecond.sceneRenderCount, portraitFirst.sceneRenderCount,
      'the static full-progress portrait is reused through the end of the stage');

    await seekAndRead(5.5);
    const beforeSkip = await readReport();
    await cdp.evaluate('window.launcherUI.skip()');
    const afterSkip = await readReport();
    assert.equal(afterSkip.completed, true);
    assert.equal(afterSkip.skipped, true);
    assert.equal(afterSkip.stage, 'complete');
    assert.equal(afterSkip.sceneRenderCount, beforeSkip.sceneRenderCount + 1,
      'skip submits one completion frame before releasing scene resources');
    for (const key of ['liveImages', 'liveBitmaps', 'liveCanvases', 'livePaths', 'liveRAF']) {
      assert.equal(afterSkip.resources[key], 0, `skip releases ${key}`);
    }

    await cdp.evaluate('window.launcherUI.updateAppearance({locale:"en"})');
    assert.match(await cdp.evaluate('document.getElementById("elapsed").textContent'), /12\.0 \/ 12\.0 s$/,
      'completed previews update time units even after releasing their canvas');

    assert.equal(await cdp.evaluate('window.launcherUI.replay()'), true);
    const replayStarted = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]');
      return root?.dataset.prewarmed==='true'&&root.dataset.playing==='true'
        ?window.launcherUI.report():false;
    })()`), 10000, 'preview replay after the skipped completion frame');
    await cdp.evaluate('window.launcherUI.pause()');
    assert.equal(replayStarted.completed, false);
    assert.ok(replayStarted.jsFrame.sceneRenderCount < afterSkip.sceneRenderCount,
      'replay starts a fresh canvas submission count');
    const replayScatterFirst = await seekAndRead(4.8);
    const replayScatterSecond = await seekAndRead(4.95);
    assert.equal(replayScatterFirst.stage, 'scattered');
    assert.equal(replayScatterSecond.sceneRenderCount, replayScatterFirst.sceneRenderCount,
      'static rendering reuse remains active after replay');

    return {
      counts: {
        identity: { submissions: identityFirst.sceneRenderCount - initial.sceneRenderCount, seeks: 3 },
        scattered: { submissions: scatteredSecond.sceneRenderCount - identityThird.sceneRenderCount, seeks: 2 },
        drawing: { submissions: drawingSecond.sceneRenderCount - scatteredSecond.sceneRenderCount, seeks: 2 },
        portrait: { submissions: portraitSecond.sceneRenderCount - drawingSecond.sceneRenderCount, seeks: 3 },
        skip: { completionFrameSubmitted: afterSkip.sceneRenderCount === beforeSkip.sceneRenderCount + 1,
          releasedResources: afterSkip.resources },
        replay: { submissions: replayScatterSecond.sceneRenderCount - replayStarted.jsFrame.sceneRenderCount,
          stage: replayScatterSecond.stage },
      },
      measurement: 'sceneRenderCount counts JavaScript 2D-canvas renderScene submissions; it does not measure GPU or presented frames',
    };
  });

  const seekRaceCheck = 'public preview seek restores identity pixels after async backward bitmap resolution';
  let seekHarnessScriptIdentifier = '';
  if (!onlyChecks || onlyChecks.has(seekRaceCheck)) {
    const installedScript = await cdp.call('Page.addScriptToEvaluateOnNewDocument', { source: `(()=>{
      const nativeRAF=window.requestAnimationFrame.bind(window);
      const nativeCancel=window.cancelAnimationFrame.bind(window);
      const nativeBitmap=window.createImageBitmap.bind(window);
      const pendingFrames=new Map(),pendingBitmaps=[];
      let nextFrame=0,holdBitmaps=false;
      window.requestAnimationFrame=callback=>{const id=++nextFrame;pendingFrames.set(id,callback);return id;};
      window.cancelAnimationFrame=id=>{pendingFrames.delete(id);return nativeCancel(id);};
      window.createImageBitmap=(...args)=>holdBitmaps
        ?new Promise((resolve,reject)=>{
          const stableArgs=args.slice();
          if(stableArgs[0] instanceof HTMLCanvasElement){
            const source=stableArgs[0],snapshot=document.createElement('canvas');
            snapshot.width=source.width;snapshot.height=source.height;
            snapshot.getContext('2d').drawImage(source,0,0);
            stableArgs[0]=snapshot;
          }
          pendingBitmaps.push({args:stableArgs,resolve,reject});
        })
        :nativeBitmap(...args);
      window.__agentSkinPublicHarness={pendingFrames,pendingBitmaps,
        runNext(timestamp){const item=pendingFrames.entries().next().value;if(!item)return false;
          pendingFrames.delete(item[0]);item[1](timestamp);return true;},
        hold(){holdBitmaps=true;},
        async resolveBitmap(index){const item=pendingBitmaps[index];if(!item)return false;
          try{item.resolve(await nativeBitmap(...item.args));return true;}catch(error){item.reject(error);throw error;}},
        restore(){window.requestAnimationFrame=nativeRAF;window.cancelAnimationFrame=nativeCancel;window.createImageBitmap=nativeBitmap;},
      };
    })()` });
    seekHarnessScriptIdentifier = installedScript.identifier;
    await cdp.call('Page.navigate', { url: pathToFileURL(join(animationPreviewDir, 'index.html')).href });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'seek-race preview load');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'seek-race preview prewarm');
  }
  await check(seekRaceCheck, async () => {
    const pauseAtScattered = await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.launcherUI.resume();
      const advanced=window.__agentSkinPublicHarness.runNext(performance.now()+5080);
      window.launcherUI.pause();
      return {advanced,report:window.launcherUI.report()};
    })()`);
    assert.equal(pauseAtScattered.advanced, true, 'the actual public handle advances the captured natural frame');
    assert.ok(Math.abs(pauseAtScattered.report.elapsed - 5.08) <= 0.001,
      'the captured natural frame advances within 1 ms of the requested 5.08 seconds: '
        + pauseAtScattered.report.elapsed);
    assert.equal(pauseAtScattered.report.resources.liveBitmaps, 2,
      'natural playback releases the identity bitmap after entering scattered');
    await cdp.evaluate('window.__agentSkinPublicHarness.hold()');
    assert.equal(await cdp.evaluate('window.launcherUI.seek(1)'), true);
    assert.equal(await cdp.evaluate('window.launcherUI.seek(2)'), true);
    assert.equal(await cdp.evaluate('window.launcherUI.seek(8)'), true);
    const pending = await cdp.evaluate(`({count:window.__agentSkinPublicHarness.pendingBitmaps.length,
      elapsed:window.launcherUI.report().elapsed})`);
    assert.equal(pending.count, 2, 'both identity scrubs start a delayed bitmap request');
    assert.equal(pending.elapsed, 8, 'the latest public seek is visible before either bitmap completes');

    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(1)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterSecond = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterSecond.elapsed, 8, 'the newer delayed bitmap cannot overwrite seek(8)');
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterFirst = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterFirst.elapsed, 8, 'the older delayed bitmap cannot overwrite seek(8)');
    assert.equal(afterFirst.resources.liveBitmaps, 2, 'both stale seek bitmaps are closed exactly once');
    assert.equal(await cdp.evaluate('window.launcherUI.dispose()'), true);
    const disposed = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(disposed.elapsed, 8);
    for (const kind of ['Bitmaps', 'Canvases', 'Paths']) assert.equal(disposed.resources['live' + kind], 0);
    assert.equal(disposed.resources.liveRAF, 0);

    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'skip-race preview reload');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'skip-race preview prewarm');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.launcherUI.resume();
      window.__agentSkinPublicHarness.runNext(performance.now()+5080);window.launcherUI.pause();
      window.__agentSkinPublicHarness.hold();window.launcherUI.seek(1);window.launcherUI.skip();
    })()`);
    const skipped = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(skipped.completed, true);
    assert.equal(skipped.skipped, true);
    assert.equal(skipped.resources.liveBitmaps, 0);
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterSkippedLateResult = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterSkippedLateResult.elapsed, 12);
    assert.equal(afterSkippedLateResult.completed, true);
    assert.equal(afterSkippedLateResult.resources.liveBitmaps, 0, 'a late result cannot revive a skipped scene');

    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'dispose-race preview reload');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'dispose-race preview prewarm');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.launcherUI.resume();
      window.__agentSkinPublicHarness.runNext(performance.now()+5080);window.launcherUI.pause();
      window.__agentSkinPublicHarness.hold();window.launcherUI.seek(1);window.launcherUI.dispose();
    })()`);
    const beforeLateDisposeResult = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(beforeLateDisposeResult.resources.liveBitmaps, 0);
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterDisposedLateResult = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterDisposedLateResult.resources.liveBitmaps, 0, 'a late disposed result is closed without revival');
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'backward-restore preview reload');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'backward-restore preview prewarm');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.__agentSkinPublicHarness.hold();window.launcherUI.seek(6);
    })()`);
    const releasedAtSix = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(releasedAtSix.stage, 'drawing');
    assert.equal(releasedAtSix.resources.liveBitmaps, 2,
      'entering drawing releases only the intermediate identity bitmap');
    await cdp.evaluate('window.launcherUI.seek(2.2)');
    const beforeIdentityBitmap = await animationPixelEvidence();
    assert.equal(beforeIdentityBitmap.stage, 'identity');
    assert.ok(beforeIdentityBitmap.identity.light > 40,
      'the identity canvas draws immediately from its retained canvas while the restored bitmap is pending: '
        + JSON.stringify(beforeIdentityBitmap.identity));
    assert.equal(await cdp.evaluate('window.__agentSkinPublicHarness.pendingBitmaps.length'), 1,
      'the backward seek has one held identity-bitmap request');
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterIdentityBitmap = await animationPixelEvidence();
    assert.equal(afterIdentityBitmap.stage, 'identity');
    assert.equal(afterIdentityBitmap.sceneRenderCount, beforeIdentityBitmap.sceneRenderCount + 1,
      'resolving the restored bitmap invalidates the static key and redraws the identity frame');
    assert.deepEqual(afterIdentityBitmap.identity, beforeIdentityBitmap.identity,
      'the asynchronously restored bitmap preserves the actual rendered identity pixels');
    assert.equal(afterIdentityBitmap.resources.liveBitmaps, 3);
    return { scatteredResources: pauseAtScattered.report.resources, finalElapsed: afterFirst.elapsed,
      disposedResources: disposed.resources, skippedLateResources: afterSkippedLateResult.resources,
      disposedLateResources: afterDisposedLateResult.resources,
      backwardRestore: { releasedResources: releasedAtSix.resources,
        beforeResolution: { sceneRenderCount: beforeIdentityBitmap.sceneRenderCount, pixels: beforeIdentityBitmap.identity },
        afterResolution: { sceneRenderCount: afterIdentityBitmap.sceneRenderCount,
          liveBitmaps: afterIdentityBitmap.resources.liveBitmaps, pixels: afterIdentityBitmap.identity } } };
  });
  if (!onlyChecks || onlyChecks.has(seekRaceCheck)) {
    await cdp.call('Page.removeScriptToEvaluateOnNewDocument', { identifier: seekHarnessScriptIdentifier });
    await cdp.call('Page.navigate', { url: pathToFileURL(join(animationPreviewDir, 'index.html')).href });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'preview restore after seek test');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'preview restore after seek test prewarm');
  }

  await check('reduced motion is static or opacity-only from initial preference and after a phase-four toggle', async () => {
    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'reduced-motion preview load');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'reduced-motion preview prewarm');
    const initial = await cdp.evaluate(`({reduced:window.launcherUI.report().reduced,
      playing:document.querySelector('[data-agent-skin-stage]').dataset.playing})`);
    assert.equal(initial.reduced, true, 'the renderer reads the reduced preference before its first playback');
    assert.equal(await cdp.evaluate('window.launcherUI.pause()'), true);
    try {
    const traceAt = async seconds => cdp.evaluate(`(()=>{
      const context=document.querySelector('canvas[data-agent-skin-canvas]').getContext('2d');
      const proto=CanvasRenderingContext2D.prototype, names=['arc','beginPath','clearRect','drawImage','fill','fillRect',
        'fillText','lineTo','moveTo','rect','restore','rotate','save','scale','setTransform','stroke','strokeRect','translate'];
      const originals=new Map(),trace=[];
      for(const name of names){
        const original=proto[name];originals.set(name,original);
        proto[name]=function(...args){
          if(this.canvas?.hasAttribute('data-agent-skin-canvas'))
            trace.push({name,args:args.map(arg=>arg instanceof Path2D?'Path2D':typeof arg==='object'?arg?.constructor?.name:arg)});
          return original.apply(this,args);
        };
      }
      try{
        window.launcherUI.seek(${seconds});
        const shape=trace.map(({name,args})=>[name,args]);
        const report=window.launcherUI.report();
        return {report,shape};
      }finally{for(const [name,original] of originals)proto[name]=original;}
    })()`);
    const compareShape = async (name, first, second) => {
      const a=await traceAt(first),b=await traceAt(second);
      assert.equal(a.report.stage, name, `${name} first sample stage`);
      assert.equal(b.report.stage, name, `${name} second sample stage`);
      assert.equal(a.report.reduced, true);
      assert.equal(b.report.reduced, true);
      if (!a.shape.length || !b.shape.length) {
        assert.equal(b.report.jsFrame.sceneRenderCount, a.report.jsFrame.sceneRenderCount,
          `${name} may reuse an already submitted static frame without issuing new canvas commands`);
        return { stage:name, first, second, commands:Math.max(a.shape.length,b.shape.length), cachedFrameReused:true };
      }
      assert.deepEqual(b.shape,a.shape,`${name} may change opacity while reduced, but not geometry`);
      return { stage:name, first, second, commands:a.shape.length, cachedFrameReused:false };
    };

    const checks=[];
    checks.push(await compareShape('pulse',0.05,0.8));
    checks.push(await compareShape('identity',1.3,3.7));
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced===false'), 2000,
      'reduced-motion preference turns off before the phase-four toggle');
    const normalAtPhaseFour = await cdp.evaluate(`(()=>{
      window.launcherUI.seek(4.2);
      return {stage:window.launcherUI.report().stage,reduced:window.launcherUI.report().reduced};
    })()`);
    assert.deepEqual(normalAtPhaseFour,{stage:'dispersing',reduced:false});
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced===true'), 2000,
      'reduced-motion preference toggles during identity dispersal');
    checks.push(await compareShape('dispersing',4.2,4.68));
    checks.push(await compareShape('scattered',4.75,5.0));
    checks.push(await compareShape('drawing',5.2,6.8));
    checks.push(await compareShape('colorize',7.19,7.4));
    checks.push(await compareShape('portrait',7.5,10.8));
    checks.push(await compareShape('shutter',11.1,11.9));
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced===false'), 2000,
      'reduced-motion preference restores after static render checks');
    return { initialPreferenceBeforePlayback:initial.reduced, phaseFourToggle:normalAtPhaseFour,
      opacityMayVary:true, stages:checks };
    } finally {
      await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
      await cdp.call('Page.navigate', { url: previewURL });
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
        &&window.launcherUI?.report()?true:false`), 15000, 'default preview restored after reduced-motion checks');
    }
  });

  await check('scattered and drawing stages render bounded prewarmed path fragments sampled from identity tiles', async () => {
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    const capture = seconds => cdp.evaluate(`(()=>{
      const proto=CanvasRenderingContext2D.prototype,names=['arc','drawImage','stroke','translate','rotate'];
      const originals=new Map(),state={strokes:0,nonPathStrokes:0,dots:0,drawImages:0,canvasImages:0,translates:[],rotations:[]};
      for(const name of names){
        const original=proto[name];originals.set(name,original);
        proto[name]=function(...args){
          if(this.canvas?.hasAttribute('data-agent-skin-canvas')){
            if(name==='stroke'){if(args[0] instanceof Path2D)state.strokes++;else state.nonPathStrokes++;}
            if(name==='arc')state.dots++;
            if(name==='drawImage'){state.drawImages++;if(args[0] instanceof HTMLCanvasElement)state.canvasImages++;}
            if(name==='translate')state.translates.push(args.slice(0,2));
            if(name==='rotate')state.rotations.push(args[0]);
          }
          return original.apply(this,args);
        };
      }
      try{window.launcherUI.seek(${seconds});return {...state,report:window.launcherUI.report()};}
      finally{for(const [name,original]of originals)proto[name]=original;}
    })()`);
    const inspectVariant = async dir => {
      await cdp.call('Page.navigate', { url: pathToFileURL(join(dir, 'index.html')).href });
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
        &&window.launcherUI?.report()?true:false`), 15000, 'fragment fixture prewarm');
      await cdp.evaluate('window.launcherUI.pause()');
      await cdp.evaluate('window.launcherUI.seek(4.73)');
      const beforeRelease = await cdp.evaluate('window.launcherUI.report()');
      const scattered = await capture(4.74);
      assert.equal(scattered.report.stage,'scattered');
      assert.equal(beforeRelease.resources.liveBitmaps,3,'the sampled identity bitmap is alive until the 4.74s boundary');
      assert.equal(scattered.report.resources.liveBitmaps,2,'the identity bitmap is released at the scattered boundary');
      assert.ok(scattered.strokes>=20,'scattered draws individual Path2D line fragments');
      assert.equal(scattered.strokes,scattered.report.resources.livePaths,'each live prewarmed fragment renders as one path');
      assert.equal(scattered.nonPathStrokes,0);
      assert.equal(scattered.dots,0,'fragments use line geometry instead of point dots');
      assert.equal(scattered.drawImages,0,'identity pixels are sampled before 4.74s and no image tiles persist into scattered');
      assert.equal(scattered.rotations.length,scattered.strokes,'each segment has one fixed scatter transform');
      const bounds = await cdp.evaluate(`(()=>{
        const contours=window.AGENT_SKIN_ASSETS.contours;let length=0;
        for(const points of contours)for(let index=1;index<points.length;index++)
          length+=Math.hypot(points[index][0]-points[index-1][0],points[index][1]-points[index-1][1]);
        const span=Math.max(18,length/1400);
        return {length,span,fragments:Math.ceil(length/span)+contours.length};
      })()`);
      assert.ok(scattered.strokes<=bounds.fragments,
        `segment count follows the span=max(18,totalLength/1400) bound: ${JSON.stringify(bounds)}`);
      const drawingStart = await capture(5.08);
      const drawingEnd = await capture(6.8);
      const frontChecks = [5.6,6.2,6.8,7.17].map(seconds=>({seconds,promise:capture(seconds)}));
      const frontFrames = await Promise.all(frontChecks.map(async frame=>({seconds:frame.seconds,...await frame.promise})));
      assert.equal(drawingStart.report.stage,'drawing');
      assert.equal(drawingEnd.report.stage,'drawing');
      assert.equal(drawingStart.strokes,scattered.strokes);
      assert.equal(drawingEnd.strokes,scattered.strokes);
      assert.equal(drawingStart.drawImages,0,'the full line canvas stays cached until the post-transition color stage');
      assert.equal(drawingEnd.drawImages,0);
      for(const frame of frontFrames){
        assert.equal(frame.report.stage,'drawing');
        assert.equal(frame.strokes,scattered.strokes);
        assert.equal(frame.drawImages,0);
      }
      const drawingScreenshot = await screenshot('animation-mid-drawing-' + (dir===animationPreviewDir?'english':'maximum-chinese') + '.png');
      const scatterAnchors = scattered.translates.filter((_,index)=>index%2===0);
      const startAnchors = drawingStart.translates.filter((_,index)=>index%2===0);
      const endAnchors = drawingEnd.translates.filter((_,index)=>index%2===0);
      assert.equal(scatterAnchors.length,scattered.strokes);
      assert.notDeepEqual(startAnchors,endAnchors,'drawing transforms fragments from their scatter anchors toward their path targets');
      assert.deepEqual(startAnchors,scatterAnchors,'the normalized sweep starts with all fragments at their seeded scatter targets');
      const smooth=value=>{const amount=Math.max(0,Math.min(1,value));return amount*amount*(3-2*amount);};
      const expectedAnchorsAt=frame=>{
        const p=Math.max(0,Math.min(1,(frame.seconds-5.08)/2.1));
        const front=1.5*p-0.25;
        return scatterAnchors.map((source,index)=>{
          const centerTranslate=scattered.translates[index*2+1];
          const targetX=-centerTranslate[0],targetY=-centerTranslate[1];
          const band=Math.max(0.01,Math.min(0.12,bounds.span/1536));
          const progress=smooth((front-targetX/1536+band)/(2*band));
          return [source[0]+(targetX-source[0])*progress,source[1]+(targetY-source[1])*progress];
        });
      };
      const verifyFrontFrame=frame=>{
        const actual=frame.translates.filter((_,index)=>index%2===0),expected=expectedAnchorsAt(frame);
        assert.equal(actual.length,expected.length);
        for(let index=0;index<actual.length;index++)for(let axis=0;axis<2;axis++)
          assert.ok(Math.abs(actual[index][axis]-expected[index][axis])<0.02,
            `front controls fragment ${index} at ${frame.seconds}s: ${JSON.stringify({actual:actual[index],expected:expected[index]})}`);
        return actual;
      };
      for(const frame of frontFrames)verifyFrontFrame(frame);
      for(const frame of frontFrames.filter(value=>value.seconds===5.6||value.seconds===6.2)){
        const anchors=verifyFrontFrame(frame);
        let leftProgress=0,leftCount=0,rightProgress=0,rightCount=0;
        for(let index=0;index<scatterAnchors.length;index++){
          const targetX=-scattered.translates[index*2+1][0];
          const start=scatterAnchors[index],target=[targetX,-scattered.translates[index*2+1][1]];
          const total=Math.hypot(target[0]-start[0],target[1]-start[1]);
          const progress=total?Math.min(1,Math.hypot(anchors[index][0]-start[0],anchors[index][1]-start[1])/total):1;
          if(targetX<1536*0.3){leftProgress+=progress;leftCount++;}
          if(targetX>1536*0.7){rightProgress+=progress;rightCount++;}
        }
        assert.ok(leftCount>0&&rightCount>0);
        leftProgress/=leftCount;rightProgress/=rightCount;
        assert.ok(leftProgress>rightProgress,`the prescribed front reaches left targets before right targets at ${frame.seconds}s`);
      }
      const endpoints=frontFrames.find(value=>value.seconds===7.17);
      const finalAnchors=verifyFrontFrame(endpoints);
      const targetAnchors=scatterAnchors.map((_,index)=>[-scattered.translates[index*2+1][0],-scattered.translates[index*2+1][1]]);
      assert.deepEqual(finalAnchors.map(point=>point.map(value=>Math.round(value*100)/100)),
        targetAnchors.map(point=>point.map(value=>Math.round(value*100)/100)),
        'the 1.5*p-0.25 front fully returns every fragment before colorize');
      const colorize = await capture(7.18);
      assert.equal(colorize.report.stage,'colorize');
      assert.equal(colorize.canvasImages,1,'the final contour canvas is used after fragments reach their paths');
      const scatterSignature = scatterAnchors.reduce((hash,point)=>{
        for(const value of point)hash=Math.imul(hash^Math.round(value*100),16777619)>>>0;
        return hash;
      },2166136261);
      return { name:dir===animationPreviewDir?'english':dir.split('-').at(-1),
        bitmaps:{beforeRelease:beforeRelease.resources.liveBitmaps,atRelease:scattered.report.resources.liveBitmaps},
        fragments:scattered.strokes,fragmentBound:bounds.fragments,scatterSignature,scatterCount:scatterAnchors.length,
        scatterAnchors:scatterAnchors.slice(0,24),
        drawingStartAnchors:startAnchors.slice(0,24),drawingEndAnchors:endAnchors.slice(0,24),
        drawingScreenshot:drawingScreenshot.file,lineCanvasImagesAtColorize:colorize.canvasImages };
    };
    try {
      const english = await inspectVariant(animationPreviewDir);
      const chinese = await inspectVariant(identityVariants.find(value=>value.name==='maximum-chinese').dir);
      assert.notEqual(english.scatterSignature,chinese.scatterSignature,
        'scatter positions are sampled from each currently prepared identity canvas');
      return { identityVariants:[english,chinese] };
    } finally {
      await cdp.call('Page.navigate', { url: previewURL });
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
        &&window.launcherUI?.report()?true:false`), 15000, 'default preview restored after fragment checks');
    }
  });

  await check('one RC3 canvas stays registered at all required times, viewport sizes and DPR values', async () => {
    const expectedStages = new Map([
      [0, 'pulse'], [1.15, 'identity'], [4.18, 'dispersing'], [4.74, 'scattered'],
      [5.08, 'drawing'], [7.18, 'colorize'], [7.43, 'portrait'], [11, 'shutter'], [12, 'complete'],
    ]);
    const subtitle = await cdp.evaluate('window.AGENT_SKIN_ASSETS.artworkSubtitle');
    assert.equal(subtitle.length, 60, 'portrait uses the longest legal subtitle fixture');
    const sizes = [
      { name: 'wide', width: 1440, height: 900 },
      { name: 'compact', width: 980, height: 640 },
      { name: 'portrait', width: 390, height: 844 },
    ];
    const matrix = [];
    for (const size of sizes) {
      for (const dpr of [1, 2]) {
        await cdp.call('Emulation.setDeviceMetricsOverride', {
          width: size.width, height: size.height, screenWidth: size.width, screenHeight: size.height,
          deviceScaleFactor: dpr, mobile: false,
        });
        await cdp.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
        let injectedResolutionChange = false;
        const observedDPR = await cdp.evaluate('window.launcherUI.report().viewport.dpr');
        if (observedDPR !== dpr) {
          injectedResolutionChange = await cdp.evaluate('window.__agentSkinResolutionWatch.dispatchLatest()');
          assert.equal(injectedResolutionChange, true, 'the active resolution MediaQueryList receives a change event');
          await cdp.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
        }
        const actualViewport = await cdp.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})');
        assert.deepEqual(actualViewport, { width: size.width, height: size.height, dpr },
          `emulated viewport for ${size.name} at DPR ${dpr}`);
        for (const [seconds, expectedStage] of expectedStages) {
          await cdp.evaluate(`window.launcherUI.seek(${seconds})`);
          const state = await cdp.evaluate(`(()=>{
            const root=document.querySelector('[data-agent-skin-stage]');
            const canvas=root.querySelector('canvas[data-agent-skin-canvas]');
            const report=window.launcherUI.report();
            const rect=element=>{const value=element.getBoundingClientRect();return {left:value.left,top:value.top,right:value.right,bottom:value.bottom};};
            return {stage:report.stage,progress:report.animationProgress,viewport:report.viewport,
              backing:{width:canvas.width,height:canvas.height},css:{width:canvas.clientWidth,height:canvas.clientHeight},
              skip:rect(root.querySelector('[data-agent-skin-skip]')),
              controls:rect(document.querySelector('#preview-controls')),
              headerRight:rect(document.querySelector('.preview-heading span:last-child')),
              prewarmed:root.dataset.prewarmed,coordinateSize:canvas.dataset.coordinateSize};
          })()`);
          assert.equal(state.stage, expectedStage, `phase at ${seconds}s`);
          assert.equal(state.prewarmed, 'true');
          assert.equal(state.coordinateSize, '1536x1024');
          assert.equal(state.css.width, size.width, JSON.stringify(state));
          assert.equal(state.css.height, size.height, JSON.stringify(state));
          assert.equal(state.backing.width, size.width * dpr);
          assert.equal(state.backing.height, size.height * dpr);
          const overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
          const layout = JSON.stringify({ size: size.name, dpr, skip: state.skip, controls: state.controls, headerRight: state.headerRight });
          assert.equal(overlaps(state.skip, state.controls), false, `skip remains outside the preview control bar: ${layout}`);
          assert.equal(overlaps(state.skip, state.headerRight), false, `skip remains outside the heading text: ${layout}`);
          matrix.push({ size: size.name, dpr, seconds, injectedResolutionChange, ...state });
          await screenshot(`animation-${size.name}-dpr${dpr}-${String(seconds).replace('.', 'p')}s.png`);
        }
      }
    }

    const samplePixel = async seconds => cdp.evaluate(`(()=>{
      window.launcherUI.seek(${seconds});
      const canvas=document.querySelector('[data-agent-skin-canvas]');
      const context=canvas.getContext('2d');
      const scale=Math.max(innerWidth/1536,innerHeight/1024);
      const x=Math.round((1500*scale+(innerWidth-1536*scale)/2)*devicePixelRatio);
      const y=Math.round((100*scale+(innerHeight-1024*scale)/2)*devicePixelRatio);
      const pixel=context.getImageData(x,y,1,1).data;
      return {stage:window.launcherUI.report().stage,pixel:[pixel[0],pixel[1],pixel[2],pixel[3]]};
    })()`);
    await cdp.call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    await cdp.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
    const beforeColor = await samplePixel(7.17);
    const colorizeStart = await samplePixel(7.18);
    const portraitColor = await samplePixel(7.43);
    assert.deepEqual(beforeColor.pixel, [16, 18, 28, 255], 'background pixels remain dark before colorize');
    assert.deepEqual(colorizeStart.pixel, [16, 18, 28, 255], 'colorize starts with zero artwork opacity');
    assert.ok(portraitColor.pixel[0] + portraitColor.pixel[1] + portraitColor.pixel[2] > 360,
      'the same artwork becomes visible only after the colorize interval');
    assert.equal(beforeColor.stage, 'drawing');
    assert.equal(colorizeStart.stage, 'colorize');
    assert.equal(portraitColor.stage, 'portrait');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    const reducedState = await until(() => cdp.evaluate(`window.launcherUI.report().reduced === true
      ?window.launcherUI.report():false`), 2000, 'real browser reduced-motion media change');
    await cdp.evaluate('window.launcherUI.seek(5.7)');
    const reducedDrawing = await cdp.evaluate(`({state:window.launcherUI.report(),
      visibleProgress:document.querySelector('[data-agent-skin-progress]').textContent})`);
    assert.equal(reducedDrawing.state.stage, 'drawing');
    assert.equal(reducedDrawing.state.reduced, true);
    await screenshot('animation-reduced-motion-drawing.png');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced === false'), 2000, 'reduced-motion media restoration');
    return { subtitleLength: subtitle.length, screenshotCount: matrix.length, matrix,
      colorRegistration: { beforeColor, colorizeStart, portraitColor }, prewarmed: animationReady.resources };
  });

  await check('DPR watcher rebinds across scale changes and disposal releases its listener and scene resources', async () => {
    const beforeDPR = await cdp.evaluate('window.__agentSkinResolutionWatch');
    assert.equal(beforeDPR.active, 1, 'one resolution listener is bound after the viewport matrix');
    await cdp.call('Emulation.setDeviceMetricsOverride', {
      width: 1440, height: 900, screenWidth: 1440, screenHeight: 900,
      deviceScaleFactor: 2, mobile: false,
    });
    await cdp.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
    if (await cdp.evaluate('window.launcherUI.report().viewport.dpr') !== 2) {
      assert.equal(await cdp.evaluate('window.__agentSkinResolutionWatch.dispatchLatest()'), true,
        'the active resolution MediaQueryList receives a change event');
    }
    let rebound;
    try {
      rebound = await until(() => cdp.evaluate(`(()=>{
        const report=window.launcherUI.report(),watch=window.__agentSkinResolutionWatch;
        return report.viewport.dpr===2&&report.resources.liveRAF===0&&watch.active===1&&watch.added>1
          ?{report,watch}:false;
      })()`), 3000, 'resolution observer rebinds at DPR 2');
    } catch (error) {
      const snapshot = await cdp.evaluate(`({report:window.launcherUI.report(),watch:window.__agentSkinResolutionWatch,
        resolution1:matchMedia('(resolution: 1dppx)').matches,resolution2:matchMedia('(resolution: 2dppx)').matches})`);
      throw new Error(`${error.message}; snapshot=${JSON.stringify(snapshot)}`);
    }
    assert.equal(rebound.watch.added, rebound.watch.removed + 1);
    const started = await cdp.evaluate('window.launcherUI.replay()');
    assert.equal(started, true);
    const playing = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]'),state=window.launcherUI.report();
      return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'&&state.elapsed>0?state:false;
    })()`), 10000, 'replay after DPR observer rebind');
    assert.equal(playing.viewport.dpr, 2);
    assert.equal(playing.resources.liveRAF, 1);
    assert.ok(playing.resources.liveBitmaps > 0);
    const disposed = await cdp.evaluate('window.launcherUI.dispose()');
    assert.equal(disposed, true);
    const afterDispose = await cdp.evaluate(`({report:window.launcherUI.report(),watch:window.__agentSkinResolutionWatch})`);
    assert.equal(afterDispose.watch.active, 0);
    assert.equal(afterDispose.watch.added, afterDispose.watch.removed);
    for (const kind of ['Images', 'Bitmaps', 'Canvases', 'Paths']) {
      assert.equal(afterDispose.report.resources['live' + kind], 0, `${kind} are released at disposal`);
    }
    assert.equal(afterDispose.report.resources.liveRAF, 0);
    assert.equal(afterDispose.report.resources.framesPending, 0);
    await delay(120);
    const settled = await cdp.evaluate('window.launcherUI.report()');
    assert.deepEqual(settled.resources, afterDispose.report.resources, 'disposed resources and frame counts stay stable');
    assert.deepEqual(await cdp.evaluate('window.__agentSkinResolutionWatch'), afterDispose.watch);
    const replayAfterDispose = await cdp.evaluate('window.launcherUI.replay()');
    assert.equal(replayAfterDispose, false, 'a disposed preview cannot replay');

    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'preview reload for late bitmap race');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'`),
      10000, 'fresh preview prewarm before late bitmap race');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();
      const original=window.createImageBitmap.bind(window),pending=[];
      window.__fixtureOriginalCreateImageBitmap=original;
      window.__fixturePendingBitmaps=pending;
      window.createImageBitmap=source=>new Promise(resolve=>{
        let stableSource=source;
        if(source instanceof HTMLCanvasElement){
          stableSource=document.createElement('canvas');
          stableSource.width=source.width;stableSource.height=source.height;
          stableSource.getContext('2d').drawImage(source,0,0);
        }
        pending.push({source:stableSource,resolve});
      });
      return window.launcherUI.replay();
    })()`);
    await until(() => cdp.evaluate('window.__fixturePendingBitmaps.length===2'),
      10000, 'two replay bitmaps held before identity bitmap preparation');
    await cdp.evaluate(`Promise.all(window.__fixturePendingBitmaps.slice(0,2).map(async item=>{
      item.resolve(await window.__fixtureOriginalCreateImageBitmap(item.source));
    }))`);
    await until(() => cdp.evaluate('window.__fixturePendingBitmaps.length===3'),
      10000, 'identity bitmap held after the replay artwork bitmaps resolve');
    const heldResources = await cdp.evaluate('window.launcherUI.report().resources');
    assert.equal(heldResources.liveBitmaps, 2);
    assert.equal(heldResources.liveRAF, 0);
    assert.equal(await cdp.evaluate('window.launcherUI.dispose()'), true);
    const lateDisposed = await cdp.evaluate(`({report:window.launcherUI.report(),watch:window.__agentSkinResolutionWatch,
      prewarmed:document.querySelector('[data-agent-skin-stage]').dataset.prewarmed,
      playing:document.querySelector('[data-agent-skin-stage]').dataset.playing})`);
    assert.equal(lateDisposed.watch.active, 0);
    assert.equal(lateDisposed.prewarmed, 'false');
    assert.equal(lateDisposed.playing, 'false');
    assert.equal(lateDisposed.report.resources.liveBitmaps, 0);
    assert.equal(lateDisposed.report.resources.liveRAF, 0);
    assert.equal(await cdp.evaluate('window.launcherUI.replay()'), false);
    await cdp.evaluate(`(async()=>{
      const item=window.__fixturePendingBitmaps[2];
      const bitmap=await window.__fixtureOriginalCreateImageBitmap(item.source);
      item.source.width=0;item.source.height=0;item.resolve(bitmap);
    })()`);
    const lateSettled = await until(() => cdp.evaluate(`(()=>{
      const state=window.launcherUI.report(),resources=state.resources;
      return resources.liveBitmaps===0&&resources.createdBitmaps===resources.releasedBitmaps
        &&resources.liveRAF===0&&resources.framesPending===0
        ?{state,prewarmed:document.querySelector('[data-agent-skin-stage]').dataset.prewarmed}:false;
    })()`), 3000, 'late bitmap closes without reviving disposed preview');
    assert.equal(lateSettled.prewarmed, 'false');
    await delay(120);
    const afterLateSettle = await cdp.evaluate('window.launcherUI.report().resources');
    assert.deepEqual(afterLateSettle, lateSettled.state.resources, 'late callbacks cannot add frames or resources after disposal');

    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'preview reload for following checks');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'`),
      10000, 'preview ready for following checks');
    await cdp.evaluate('window.launcherUI.pause()');
    return { beforeDPR, rebound: rebound.watch, playing: playing.resources,
      disposed: afterDispose.watch, finalResources: settled.resources, settleMs: 120,
      replayAfterDispose, heldResources, lateDispose: { watcher: lateDisposed.watch,
        resources: lateDisposed.report.resources, replayAfterDispose: false },
      lateSettledResources: afterLateSettle, lateSettleMs: 120 };
  });

  await check('local preview controls pause, resume, seek and replay the same prepared scene', async () => {
    const controls = await cdp.evaluate(`({visible:!document.querySelector('#preview-controls').hidden,
      timeline:document.querySelector('#timeline').max,handle:typeof window.launcherUI.replay==='function'})`);
    assert.deepEqual(controls, { visible: true, timeline: '12', handle: true });
    await cdp.evaluate("document.querySelector('#pause').click()");
    const startingElapsed = await cdp.evaluate('window.launcherUI.report().elapsed');
    const started = await until(() => cdp.evaluate('document.querySelector("[data-agent-skin-stage]").dataset.playing === "true"'), 1500, 'preview resume before pause check');
    await until(() => cdp.evaluate(`window.launcherUI.report().elapsed>${startingElapsed + 0.04}`), 2000, 'preview clock advance before pause check');
    await cdp.evaluate("document.querySelector('#pause').click()");
    const pausedAt = await cdp.evaluate('window.launcherUI.report().elapsed');
    await delay(180);
    const stillPausedAt = await cdp.evaluate('window.launcherUI.report().elapsed');
    assert.ok(Math.abs(stillPausedAt - pausedAt) < 0.02, 'pause freezes the shared rAF clock');
    await cdp.evaluate("document.querySelector('#pause').click()");
    const resumed = await until(() => cdp.evaluate(`window.launcherUI.report().elapsed>${pausedAt + 0.04}`), 2000, 'preview resume');
    await cdp.evaluate(`(()=>{const input=document.querySelector('#timeline');input.value='2.34';input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    const seek = await cdp.evaluate('window.launcherUI.report()');
    assert.ok(Math.abs(seek.elapsed - 2.34) < 0.03);
    await cdp.evaluate("document.querySelector('#replay').click()");
    const replayed = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]');
      return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'&&window.launcherUI.report().elapsed>0
        ?window.launcherUI.report():false;
    })()`), 10000, 'preview replay after resource release');
    return { controls, started, pausedAt, stillPausedAt, resumed, seek: { elapsed: seek.elapsed, stage: seek.stage }, replayed: { elapsed: replayed.elapsed, stage: replayed.stage } };
  });

  await check('repeated preview replay releases JavaScript-owned resources after a five second settle', async () => {
    const cycles = [];
    for (let index = 0; index < 10; index++) {
      await cdp.evaluate("document.querySelector('[data-agent-skin-skip]').click()");
      const completed = await until(() => cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        const resources=window.launcherUI.report().resources;
        return root.dataset.completed==='true'&&resources.liveImages===0&&resources.liveBitmaps===0
          &&resources.liveCanvases===0&&resources.livePaths===0&&resources.liveRAF===0
          ?resources:false;
      })()`), 3000, 'resource release after replay skip ' + index);
      cycles.push(completed);
      if (index < 9) {
        await cdp.evaluate("document.querySelector('#replay').click()");
        await until(() => cdp.evaluate(`(()=>{
          const root=document.querySelector('[data-agent-skin-stage]');
          const resources=window.launcherUI.report().resources;
          return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'
            &&resources.liveImages+resources.liveBitmaps>0;
        })()`), 10000, 'replay prepare ' + (index + 2));
      }
    }
    await delay(5000);
    const settled = await cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]');
      return {rootCount:document.querySelectorAll('[data-agent-skin-stage]').length,
        iframeCount:document.querySelectorAll('iframe').length,completed:root.dataset.completed==='true',
        report:window.launcherUI.report()};
    })()`);
    assert.equal(settled.rootCount, 1);
    assert.equal(settled.iframeCount, 0);
    assert.equal(settled.completed, true);
    for (const [kind, created, released, live] of [
      ['images', 'createdImages', 'releasedImages', 'liveImages'],
      ['bitmaps', 'createdBitmaps', 'releasedBitmaps', 'liveBitmaps'],
      ['canvases', 'createdCanvases', 'releasedCanvases', 'liveCanvases'],
      ['paths', 'createdPaths', 'releasedPaths', 'livePaths'],
    ]) {
      assert.equal(settled.report.resources[created], settled.report.resources[released], `${kind} are released`);
      assert.equal(settled.report.resources[live], 0, `${kind} are not left live`);
    }
    assert.equal(settled.report.resources.liveRAF, 0);
    assert.equal(settled.report.resources.liveObjectURLs, 0);
    assert.equal(settled.report.jsFrame.scope, 'JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing');
    return { replayCycles: cycles.length, finalResources: settled.report.resources,
      jsFrame: settled.report.jsFrame, settleSeconds: 5, rootCount: settled.rootCount, iframeCount: settled.iframeCount };
  });

  await check('skip and Escape finish idempotently at the first second, a transition, and the final second', async () => {
    const results = [];
    for (const [seconds, input] of [[0.4, 'button'], [4.5, 'escape'], [11.6, 'button']]) {
      await cdp.evaluate("document.querySelector('#replay').click()");
      await until(() => cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        return root.dataset.prewarmed==='true'&&root.dataset.playing==='true';
      })()`), 10000, 'phase skip replay prewarm');
      await cdp.evaluate('window.launcherUI.pause()');
      await cdp.evaluate(`window.launcherUI.seek(${seconds})`);
      const stage = await cdp.evaluate('window.launcherUI.report().stage');
      if (input === 'escape') {
        await cdp.evaluate("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true}))");
      } else {
        await cdp.evaluate("document.querySelector('[data-agent-skin-skip]').click();document.querySelector('[data-agent-skin-skip]').click()");
      }
      const state = await cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        return {completed:root.dataset.completed==='true',report:window.launcherUI.report()};
      })()`);
      assert.equal(state.completed, true);
      assert.equal(state.report.completed, true);
      assert.equal(state.report.skipped, true);
      assert.equal(state.report.resources.liveRAF, 0);
      results.push({ seconds, phase: stage, input, skipped: state.report.skipped, resources: state.report.resources });
    }
    assert.equal(results[0].phase, 'pulse');
    assert.equal(results[1].phase, 'dispersing');
    assert.equal(results[2].phase, 'shutter');
    return results;
  });

  await check('one upper-bound natural replay with the 60-unit Chinese subtitle settles without resource growth', async () => {
    await cdp.call('Page.navigate', { url: pathToFileURL(join(upperPreviewDir, 'index.html')).href });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'upper subtitle fixture page load');
    const prepared = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]'),state=window.launcherUI?.report();
      return root?.dataset.prewarmed==='true'&&state?state:false;
    })()`), 30000, 'upper path fixture and longest subtitle prewarm');
    const bounds = await cdp.evaluate(`(()=>{
      const assets=window.AGENT_SKIN_ASSETS;
      return {contourPaths:assets.contours.length,
        contourPoints:assets.contours.reduce((sum,path)=>sum+path.length,0),
        subtitleCodeUnits:assets.artworkSubtitle.length,subtitle:assets.artworkSubtitle};
    })()`);
    assert.equal(bounds.contourPaths, 1200);
    assert.equal(bounds.contourPoints, 300000);
    assert.equal(bounds.subtitleCodeUnits, 60);
    const completed = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]'),state=window.launcherUI.report();
      return root.dataset.completed==='true'&&state.completed&&state.stage==='complete'
        &&state.resources.liveRAF===0&&state.resources.liveImages===0&&state.resources.liveBitmaps===0
        &&state.resources.liveCanvases===0&&state.resources.livePaths===0?state:false;
    })()`), 30000, 'one natural upper-bound replay completes and releases resources');
    assert.equal(completed.elapsed, 12);
    assert.ok(completed.jsFrame.rafIntervalMs?.count > 100);
    assert.ok(completed.jsFrame.renderSubmissionMs?.count > 100);
    const settleBaseline = { resources: completed.resources, jsFrame: completed.jsFrame };
    await delay(5000);
    const afterSettle = await cdp.evaluate('window.launcherUI.report()');
    assert.deepEqual({ resources: afterSettle.resources, jsFrame: afterSettle.jsFrame }, settleBaseline);
    return { bounds: { contourPaths: bounds.contourPaths, contourPoints: bounds.contourPoints,
      subtitleCodeUnits: bounds.subtitleCodeUnits }, initialResources: prepared.resources,
      elapsedSeconds: completed.elapsed, resources: completed.resources, jsFrame: completed.jsFrame,
      settleSeconds: 5, measurementScope: completed.jsFrame.scope };
  });

  await check('RC6 default and upper path-limit fixtures naturally complete ten 12-second replays with five-second settle checks', async () => {
    const limits = {
      avatarDataURLChars: 2 * 1024 * 1024,
      artworkDataURLChars: 12 * 1024 * 1024,
      contourPaths: 1200,
      contourPoints: 300000,
      serializedRecordChars: 20 * 1024 * 1024,
    };
    const fixtures = [
      { name: 'default', dir: animationPreviewDir, expectedPaths: 4, expectedPoints: 20 },
      { name: 'upper', dir: upperPreviewDir, expectedPaths: 1200, expectedPoints: 300000 },
    ];
    const result = [];
    for (const fixture of fixtures) {
      await cdp.call('Page.navigate', { url: pathToFileURL(join(fixture.dir, 'index.html')).href });
      await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, fixture.name + ' fixture page load');
      const prewarmed = await until(() => cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        return window.launcherUI&&root?.dataset.prewarmed==='true'?window.launcherUI.report():false;
      })()`), 30000, fixture.name + ' fixture image and path prewarm');
      const assetBounds = await cdp.evaluate(`(()=>{
        const assets=window.AGENT_SKIN_ASSETS;
        const pointCount=assets.contours.reduce((total,path)=>total+path.length,0);
        const record=JSON.stringify({avatar:assets.avatar,artwork:assets.artwork,contours:assets.contours,
          introTitle:assets.introTitle,introCaption:assets.introCaption,artworkSubtitle:assets.artworkSubtitle});
        return {avatarDataURLChars:assets.avatar.length,artworkDataURLChars:assets.artwork.length,
          contourPaths:assets.contours.length,contourPoints:pointCount,serializedRecordChars:record.length,
          resources:window.launcherUI.report().resources};
      })()`);
      assert.ok(assetBounds.avatarDataURLChars <= limits.avatarDataURLChars, 'avatar data URL stays within its configured bound');
      assert.ok(assetBounds.artworkDataURLChars <= limits.artworkDataURLChars, 'artwork data URL stays within its configured bound');
      assert.ok(assetBounds.contourPaths <= limits.contourPaths && assetBounds.contourPaths === fixture.expectedPaths);
      assert.ok(assetBounds.contourPoints <= limits.contourPoints && assetBounds.contourPoints === fixture.expectedPoints);
      assert.ok(assetBounds.serializedRecordChars <= limits.serializedRecordChars, 'serialized settings record stays within its configured bound');
      await cdp.evaluate('window.launcherUI.pause()');

      const rounds = [];
      for (let index = 0; index < 10; index++) {
        const startedAt = Date.now();
        await cdp.evaluate("document.querySelector('#replay').click()");
        await until(() => cdp.evaluate(`(()=>{
          const root=document.querySelector('[data-agent-skin-stage]');
          return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'
            &&window.launcherUI.report().elapsed>0;
        })()`), 30000, fixture.name + ' natural playback start ' + (index + 1));
        const completed = await until(() => cdp.evaluate(`(()=>{
          const root=document.querySelector('[data-agent-skin-stage]');
          const state=window.launcherUI.report();
          return root.dataset.completed==='true'&&state.completed&&state.stage==='complete'
            &&state.resources.liveRAF===0&&state.resources.liveImages===0&&state.resources.liveBitmaps===0
            &&state.resources.liveCanvases===0&&state.resources.livePaths===0?state:false;
        })()`), 30000, fixture.name + ' natural animation completion ' + (index + 1));
        assert.equal(completed.elapsed, 12);
        assert.ok(completed.jsFrame.rafIntervalMs?.count > 100, 'natural replay records actual rAF intervals');
        assert.ok(completed.jsFrame.renderSubmissionMs?.count > 100, 'natural replay records actual canvas submission work');
        const settleBaseline = { resources: completed.resources, jsFrame: completed.jsFrame };
        await delay(5000);
        const afterSettle = await cdp.evaluate('window.launcherUI.report()');
        assert.deepEqual({ resources: afterSettle.resources, jsFrame: afterSettle.jsFrame }, settleBaseline,
          fixture.name + ' resources and frame samples stay stable for five seconds after complete');
        assert.equal(afterSettle.resources.framesPending, 0);
        assert.equal(afterSettle.resources.liveObjectURLs, 0);
        rounds.push({ round: index + 1, wallTimeMs: Date.now() - startedAt,
          elapsedSeconds: completed.elapsed, resources: completed.resources, jsFrame: completed.jsFrame });
      }
      result.push({ fixture: fixture.name, assetBounds, initialResources: prewarmed.resources, rounds });
    }
    return { limits, fixtures: result, measurementScope: 'JS rAF interval and 2D canvas submission only; GPU/compositor/presentation/system-memory timing not measured' };
  });

  if (options.generatedPayload) {
    await cdp.call('Storage.clearDataForOrigin', { origin, storageTypes: 'indexeddb' });
    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('builder-generated wallpaper waits for a late supported shell and remains after animation completion', async () => {
      const waiting = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied
          &&document.querySelectorAll('[data-app-shell-frame]').length===0
          &&document.querySelectorAll('#azhou-wallpaper-style').length===0
          ?{phase:state.phase,runId:state.runId,wallpaper:state.wallpaper}:false;
      })()`), 15000, 'generated animation ready while the synthetic shell is not mounted');
      assert.equal(waiting.phase, 'playing');
      assert.equal(waiting.wallpaper.applied, false);
      assert.equal(waiting.wallpaper.imageDecoded, false);
      await delay(250);
      const held = await cdp.evaluate(`(()=>({state:window.__startupAPI.status(),
        shellCount:document.querySelectorAll('[data-app-shell-frame]').length,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length}))()`);
      assert.equal(held.state.phase, 'playing');
      assert.equal(held.state.ready, true);
      assert.equal(held.state.wallpaper.applied, false);
      assert.equal(held.shellCount, 0);
      assert.equal(held.styleCount, 0);

      assert.equal(await cdp.evaluate('window.__releaseShell()'), true, 'the supported synthetic shell mounts later');
      let applied;
      try {
        applied = await until(() => cdp.evaluate(`(()=>{
          const state=window.__startupAPI.status().wallpaper;
          const api=window.__azhouWallpaper?.status?.();
          const style=document.querySelector('#azhou-wallpaper-style');
          return state.applied&&state.imageDecoded&&api?.applied&&api.imageDecoded&&style
            ?{controller:state,api,owner:window.__azhouWallpaper.owner,
              styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
              styleOwner:style.getAttribute('data-azhou-owner')}:false;
        })()`), 5000, 'wallpaper apply after the supported shell mounts');
      } catch (error) {
        const afterMount = await cdp.evaluate(`(()=>({state:window.__startupAPI.status(),
          shellCount:document.querySelectorAll('[data-app-shell-frame]').length,
          styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
          wallpaperOwner:window.__azhouWallpaper?.owner||null}))()`);
        error.message += '; beforeMount=' + JSON.stringify({ waiting, held })
          + '; afterMount=' + JSON.stringify(afterMount);
        throw error;
      }
      assert.equal(applied.owner, 'azhou.codex-startup-animation');
      assert.equal(applied.styleCount, 1);
      assert.equal(applied.styleOwner, 'azhou.codex-startup-animation');

      const skipped = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const button=frame?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();
        return true;
      })()`);
      assert.equal(skipped, true, 'the real generated animation exposes its skip control');
      const complete = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completed&&state.wallpaper.applied
          &&document.querySelectorAll('iframe[aria-label]').length===0
          ?{phase:state.phase,completion:state.completion,wallpaper:state.wallpaper}:false;
      })()`), 5000, 'animation completion with the static wallpaper still applied');
      assert.equal(complete.phase, 'complete');
      assert.deepEqual(complete.completion, { cause: 'skip', beforeReady: false });
      const shot = await screenshot('wallpaper-late-shell-after-complete.png');
      const entry = await appearanceEntryMetrics();
      assert.equal(entry.display, 'block');
      assert.equal(entry.entryHit, true);
      assert.equal(entry.buttonHit, true);
      assert.equal(entry.composerOverlap.area, 0);
      const opened = await clickAppearanceEntry();
      assert.equal(opened.focused, true);
      const settings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
        return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
      })()`), 15000, 'generated payload appearance button opens settings after animation completion');
      await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        frame.contentWindow.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true}));
      })()`);
      const canceledSettings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const button=entry?.shadowRoot?.querySelector('button[aria-label="阿舟主题与外观"]');
        return state.phase==='complete'&&state.completion?.cause==='settings-cancel'
          &&document.activeElement===entry&&entry.shadowRoot.activeElement===button?state:false;
      })()`), 5000, 'generated payload settings cancellation restores the appearance button focus');
      return { waiting, shellMounted: true, applied, complete, screenshot: shot,
        entry: { rect: entry.rect, buttonText: entry.buttonText, composerOverlap: entry.composerOverlap },
        settings: { runId: settings.runId, phase: settings.phase }, canceledSettings: canceledSettings.completion };
    });
    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('disposing during a generated wallpaper shell wait cleans its observer and rejects a late shell', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied?state:false;
      })()`), 15000, 'generated animation ready before wallpaper shell wait disposal');
      await until(() => cdp.evaluate('window.__fixtureMutationObserverStats().wallpaperShellWait.active>0'), 2000,
        'temporary wallpaper shell observer');
      const before = await cdp.evaluate(`({state:window.__startupAPI.status(),
        observers:window.__fixtureMutationObserverStats(),styleCount:document.querySelectorAll('#azhou-wallpaper-style').length})`);
      assert.equal(before.state.phase, 'playing');
      assert.equal(before.state.wallpaper.applied, false);
      assert.equal(before.styleCount, 0);

      const disposed = await cdp.evaluate(`(()=>{
        const api=window.__startupAPI;
        api.dispose();
        return api.status();
      })()`);
      assert.equal(disposed.phase, 'disposed');
      const cleaned = await until(() => cdp.evaluate(`(()=>{
        const observers=window.__fixtureMutationObserverStats();
        return observers.active===0&&observers.disconnectCalls>0?observers:false;
      })()`), 2000, 'wallpaper observer cleanup after controller disposal');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      await delay(250);
      const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
        wallpaperOwner:window.__azhouWallpaper?.owner||null,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
        observers:window.__fixtureMutationObserverStats()})`);
      assert.equal(after.state.phase, 'disposed');
      assert.equal(after.state.wallpaper.applied, false);
      assert.equal(after.wallpaperOwner, null);
      assert.equal(after.styleCount, 0);
      assert.equal(after.rootAttribute, null);
      assert.equal(after.observers.active, 0);
      return { ready: { phase: ready.phase, runId: ready.runId }, before, disposed,
        cleaned, shellMountedAfterDispose: true, after };
    });

    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('skipping a generated animation during wallpaper wait rejects a shell mounted afterward', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied?state:false;
      })()`), 15000, 'generated animation ready before skip during wallpaper wait');
      await until(() => cdp.evaluate('window.__fixtureMutationObserverStats().wallpaperShellWait.active>0'), 2000,
        'temporary wallpaper observer before skip');
      const skipped = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const button=frame?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();
        return true;
      })()`);
      assert.equal(skipped, true);
      const completed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='skip'?state:false;
      })()`), 3000, 'play run completes while the wallpaper observer is pending');
      const cleaned = await until(() => cdp.evaluate(`(()=>{
        const observers=window.__fixtureMutationObserverStats();
        return observers.wallpaperShellWait.active===0&&observers.wallpaperShellWait.disconnectCalls>0?observers:false;
      })()`), 2000, 'wallpaper observer cleanup after skip');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      await delay(250);
      const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
        wallpaperOwner:window.__azhouWallpaper?.owner||null,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
        observers:window.__fixtureMutationObserverStats()})`);
      assert.equal(completed.phase, 'complete');
      assert.equal(after.state.wallpaper.applied, false);
      assert.equal(after.wallpaperOwner, null);
      assert.equal(after.styleCount, 0);
      assert.equal(after.rootAttribute, null);
      assert.equal(after.observers.wallpaperShellWait.active, 0);
      assert.equal(after.observers.appearanceAttributesOnly.active, 1,
        'the controller keeps its root-appearance observer while its completed entry remains available');
      const disposed = await cdp.evaluate(`(()=>{
        const api=window.__startupAPI;
        api.dispose();
        return {state:api.status(),observers:window.__fixtureMutationObserverStats()};
      })()`);
      assert.equal(disposed.state.phase, 'disposed');
      assert.equal(disposed.observers.active, 0,
        'final controller disposal disconnects the root-appearance observer');
      return { ready: { phase: ready.phase, runId: ready.runId }, completed, cleaned,
        shellMountedAfterSkip: true, after, disposed };
    });

    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('generated wallpaper shell wait is bounded and leaves no observer when the shell stays unsupported', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied?state:false;
      })()`), 15000, 'generated animation ready before wallpaper wait timeout');
      const pending = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),observers=window.__fixtureMutationObserverStats();
        return observers.wallpaperShellWait.active>0?{state,observers}:false;
      })()`), 2000, 'bounded wallpaper observer is active');
      assert.equal(pending.state.wallpaper.reason, '');
      const started = Date.now();
      const timedOut = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.wallpaper.reason==='wallpaper-unsupported'?state:false;
      })()`), 6500, 'wallpaper unsupported after bounded shell wait');
      const elapsedMs = Date.now() - started;
      assert.ok(elapsedMs >= 3500 && elapsedMs <= 6500,
        'the wallpaper request remains pending for the bounded shell wait before returning unsupported');
      const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
        observers:window.__fixtureMutationObserverStats(),shellCount:document.querySelectorAll('[data-app-shell-frame]').length,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        wallpaperOwner:window.__azhouWallpaper?.owner||null})`);
      assert.equal(timedOut.phase, 'playing');
      assert.equal(after.state.wallpaper.applied, false);
      assert.equal(after.observers.wallpaperShellWait.active, 0);
      assert.ok(after.observers.wallpaperShellWait.disconnectCalls > 0);
      assert.equal(after.observers.appearanceAttributesOnly.active, 1,
        'the controller keeps its root-appearance observer after the bounded shell wait ends');
      assert.equal(after.shellCount, 0);
      assert.equal(after.styleCount, 0);
      assert.equal(after.wallpaperOwner, null);
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      await delay(250);
      const late = await cdp.evaluate(`({state:window.__startupAPI.status(),
        observers:window.__fixtureMutationObserverStats(),
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        wallpaperOwner:window.__azhouWallpaper?.owner||null})`);
      assert.equal(late.state.wallpaper.applied, false);
      assert.equal(late.observers.wallpaperShellWait.active, 0);
      assert.equal(late.styleCount, 0);
      assert.equal(late.wallpaperOwner, null);
      const disposed = await cdp.evaluate(`(()=>{
        const api=window.__startupAPI;
        api.dispose();
        return {state:api.status(),observers:window.__fixtureMutationObserverStats()};
      })()`);
      assert.equal(disposed.state.phase, 'disposed');
      assert.equal(disposed.observers.active, 0,
        'final controller disposal disconnects the root-appearance observer');
      return { ready: { runId: ready.runId, phase: ready.phase }, pending, elapsedMs, timedOut, after, late, disposed };
    });
    await navigate('/fixture.html?generated-payload=1');
    await check('builder-generated startup payload activates the complete controller and saves settings before replay', async () => {
      const initial = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return window.__startupInstallResult?.installed===true&&state?.phase==='playing'&&state.ready?state:false;
      })()`), 15000, 'builder-generated controller and animation ready');
      assert.equal(await cdp.evaluate('document.querySelectorAll(\'iframe[aria-label]\').length'), 1);
      const wallpaper = await until(() => cdp.evaluate(`(()=>{
        const controller=window.__startupAPI.status().wallpaper;
        const api=window.__azhouWallpaper?.status?.();
        const style=document.querySelector('#azhou-wallpaper-style');
        return controller.applied&&controller.imageDecoded&&api?.applied&&api.imageDecoded&&style
          ?{controller,api,owner:window.__azhouWallpaper.owner,version:window.__azhouWallpaper.version,
            styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,styleOwner:style.getAttribute('data-azhou-owner')}
          :false;
      })()`), 10000, 'builder-generated wallpaper applied and decoded in the app route realm');
      assert.equal(wallpaper.controller.applied, true);
      assert.equal(wallpaper.controller.imageDecoded, true);
      assert.equal(wallpaper.api.applied, true);
      assert.equal(wallpaper.api.imageDecoded, true);
      assert.equal(wallpaper.owner, 'azhou.codex-startup-animation');
      assert.equal(wallpaper.version, '0.9.0');
      assert.equal(wallpaper.styleCount, 1);
      assert.equal(wallpaper.styleOwner, 'azhou.codex-startup-animation');
      await cdp.evaluate('window.__ticket05InitialWallpaperAPI=window.__azhouWallpaper;true');
      const firstRun = initial.runId;
      assert.equal(await cdp.evaluate('window.__fixtureHost.__azhouStartup.openSettings()'), true);
      await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        return window.__startupAPI.status().phase==='settings'&&frame?.contentDocument.querySelector('dialog')?.open===true;
      })()`), 5000, 'generated payload settings panel');
      const themePage = await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        const value=key=>doc.querySelector('[data-agent-skin-setting-value="'+key+'"]').textContent;
        return {appName:value('appName'),botName:value('botName'),version:value('version'),
          source:value('source'),sections:doc.querySelectorAll('[data-agent-skin-settings-section]').length};
      })()`);
      assert.equal(themePage.appName, '阿舟 AI 实验室');
      assert.equal(themePage.botName, '阿舟');
      assert.equal(themePage.version, '0.9.0 · 10');
      assert.equal(themePage.sections, 4);
      assert.equal(themePage.source, '构建默认值');
      const draft = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame.contentDocument;
        const title=doc.querySelector('input[aria-label^="启动标题"]');
        title.value='生成载荷保存验证';title.dispatchEvent(new Event('input',{bubbles:true}));
        const button=[...doc.querySelectorAll('button')].find(item=>item.textContent.trim()==='保存并重播');
        if(!button)throw new Error('generated payload settings save control is missing');
        button.click();
        return {title:title.value,button:button.textContent.trim()};
      })()`);
      assert.equal(draft.title, '生成载荷保存验证');
      const replay = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.runId>${firstRun}&&state.phase==='playing'&&state.ready?state:false;
      })()`), 15000, 'settings commit and generated payload replay');
      assert.ok(replay.runId > firstRun);
      const replayWallpaper = await until(() => cdp.evaluate(`(()=>{
        const startup=window.__startupAPI.status(),api=window.__azhouWallpaper;
        const apiState=api?.status?.(),style=document.querySelector('#azhou-wallpaper-style');
        return startup.runId===${replay.runId}&&api!==window.__ticket05InitialWallpaperAPI
          &&startup.wallpaper.applied&&startup.wallpaper.imageDecoded&&apiState?.applied&&apiState.imageDecoded&&style
          ?{controller:startup.wallpaper,api:apiState,owner:api.owner,version:api.version,
            styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,styleOwner:style.getAttribute('data-azhou-owner')}
          :false;
      })()`), 10000, 'saved settings replay keeps the newly applied generated wallpaper');
      assert.equal(replayWallpaper.controller.applied, true);
      assert.equal(replayWallpaper.controller.imageDecoded, true);
      assert.equal(replayWallpaper.api.applied, true);
      assert.equal(replayWallpaper.api.imageDecoded, true);
      assert.equal(replayWallpaper.owner, 'azhou.codex-startup-animation');
      assert.equal(replayWallpaper.version, '0.9.0');
      assert.equal(replayWallpaper.styleCount, 1);
      assert.equal(replayWallpaper.styleOwner, 'azhou.codex-startup-animation');
      assert.equal(await cdp.evaluate('delete window.__ticket05InitialWallpaperAPI'), true);
      assert.equal(await cdp.evaluate('window.__fixtureHost.__azhouStartup.openSettings()'), true);
      const persisted = await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const title=frame?.contentDocument.querySelector('input[aria-label^="启动标题"]');
        return window.__startupAPI.status().phase==='settings'&&title?title.value:false;
      })()`), 10000, 'settings value persisted through generated payload replay');
      assert.equal(persisted, '生成载荷保存验证');
      const disposed = await cdp.evaluate(`(()=>{
        window.__fixtureHost.__azhouStartup.dispose();
        return {owned:Object.hasOwn(window.__fixtureHost,'__azhouStartup'),
          frames:document.querySelectorAll('iframe[aria-label]').length,
          wallpaper:!!window.__azhouWallpaper,styles:document.querySelectorAll('#azhou-wallpaper-style').length};
      })()`);
      assert.deepEqual(disposed, { owned: false, frames: 0, wallpaper: false, styles: 0 });
      return { firstRun, replayRun: replay.runId, wallpaper, replayWallpaper, savedTitle: persisted, disposed };
    });

    await navigate('/csp-style.html?generated-payload=1');
    await check('generated appearance entry stays styled and opens settings under strict style-src self after completion', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready?state:false;
      })()`), 15000, 'generated animation ready under strict style-src self');
      const skip = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const button=frame?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();return true;
      })()`);
      assert.equal(skip, true, 'generated animation exposes its skip control under strict CSP');
      const completed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='skip'?state:false;
      })()`), 5000, 'generated animation completes under strict style-src self');
      const entry = await appearanceEntryMetrics();
      await screenshot('appearance-entry-csp-style-src-self.png');
      const diagnostic = JSON.stringify({ phase: completed.phase, viewport: entry?.viewport,
        display: entry?.display, position: entry?.position, rect: entry?.rect,
        avatar: entry?.avatar, nameLabel: entry?.nameLabel,
        entryHit: entry?.entryHit, buttonHit: entry?.buttonHit, buttonText: entry?.buttonText });
      assert.equal(entry?.display, 'block', 'appearance entry is visible under strict CSP: ' + diagnostic);
      assert.equal(entry.position, 'fixed', 'appearance entry positioning is available under strict CSP: ' + diagnostic);
      assert.ok(entry.rect.width >= 44 && entry.rect.width <= 120,
        'appearance entry stays within compact avatar-and-name geometry under strict CSP: ' + diagnostic);
      assert.deepEqual(entry.avatar, { width: 32, height: 32, display: 'block', borderRadius: '10px', objectFit: 'cover' },
        'generated avatar keeps its bounded styled dimensions under strict CSP: ' + diagnostic);
      assert.deepEqual(entry.nameLabel, { text: '阿舟', fontSize: '12px', lineHeight: '18px' },
        'generated avatar name remains visible with the button typography under strict CSP: ' + diagnostic);
      assert.equal(entry.entryHit, true, 'appearance entry host is hit-testable under strict CSP: ' + diagnostic);
      assert.equal(entry.buttonHit, true, 'shadow button is hit-testable under strict CSP: ' + diagnostic);
      const opened = await clickAppearanceEntry();
      assert.equal(opened.focused, true, 'the generated appearance button receives a real pointer click');
      const settings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
        return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
      })()`), 15000, 'generated appearance entry opens settings under strict style-src self');
      await screenshot('appearance-settings-csp-style-src-self.png');
      return { ready: { runId: ready.runId, phase: ready.phase }, completed: completed.completion,
        entry, settings: { runId: settings.runId, phase: settings.phase }, pointerFocused: opened.focused };
    });
  }

  report.finishedAt = new Date().toISOString();
  report.selectedChecks = options.only;
  report.passed = report.checks.some(item => item.passed)
    && report.checks.every(item => item.passed || item.skipped);
} catch (error) {
  report.fatalError = safeError(error);
  if (chromeError && !cdp) report.ownChromeStartupError = chromeError.slice(-1200);
} finally {
  try { await cleanup(); } catch (error) { report.cleanupError = safeError(error); }
  report.finishedAt = new Date().toISOString();
  report.passed = !report.fatalError && !report.cleanupError && report.cleanup?.ownChromeStopped
    && report.cleanup.temporaryProfileRemoved && report.cleanup.serverClosed
    && report.checks.some(item => item.passed)
    && report.checks.every(item => item.passed || item.skipped);
  await mkdir(options.out, { recursive: true });
  await writeFile(join(options.out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ passed: report.passed, report: join(options.out, 'report.json'),
    checks: report.checks.map(({ name, passed, skipped }) => ({ name, passed, skipped })), fatalError: report.fatalError }));
  if (!report.passed) process.exitCode = 1;
}
