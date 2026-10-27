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
};
for (let index = 2; index < process.argv.length; index++) {
  const key = process.argv[index];
  if (key === '--help') {
    console.log('node tools/test-startup-browser.mjs [--chrome /path/to/Chrome] [--out /path/to/evidence]');
    process.exit(0);
  }
  if (!['--chrome', '--out'].includes(key) || !process.argv[index + 1]) throw new Error('Unknown or missing argument: ' + key);
  options[key.slice(2)] = process.argv[++index];
}
options.chrome = resolve(options.chrome);
options.out = resolve(options.out);

const report = {
  schema: 1,
  scope: 'actual PageController and wallpaper renderer in an isolated headless Chrome with a local synthetic Codex-like page',
  startedAt: new Date().toISOString(),
  checks: [],
  screenshots: [],
  limitations: [
    'The app:// page identity is supplied through a local host adapter; no Codex process, profile, transport or user content is accessed.',
    'The wallpaper fixture uses one generated-in-test PNG pixel. The animation fixture separately generates synthetic PNGs and contours; it does not validate private or branded source art.',
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
  const [preview, wallpaperCSS, wallpaperRenderer, controllerRenderer, legacyWallpaperCSS, legacyWallpaperRenderer,
    helperExpressionJSON] = await Promise.all([
    readFile(join(ROOT, 'wallpaper/preview.html'), 'utf8'),
    readFile(join(ROOT, 'wallpaper/wallpaper.css'), 'utf8'),
    readFile(join(ROOT, 'wallpaper/renderer.js'), 'utf8'),
    readFile(join(ROOT, 'extension/renderer.mjs'), 'utf8'),
    readFile(join(ROOT, '../codex-startup-animation/wallpaper/wallpaper.css'), 'utf8'),
    readFile(join(ROOT, '../codex-startup-animation/wallpaper/renderer.js'), 'utf8'),
    readFile(join(ROOT, '.build/startup-helper-expressions.json'), 'utf8'),
  ]);
  const helperExpressions = JSON.parse(helperExpressionJSON);
  assert.deepEqual(Object.keys(helperExpressions).sort(), ['applyGuardSource', 'restoreSource', 'statusSource']);
  assert.ok(Object.values(helperExpressions).every(value => typeof value === 'string' && value.length > 0));
  const scriptStart = preview.lastIndexOf('<script type="module">');
  const scriptEnd = preview.indexOf('</script>', scriptStart) + '</script>'.length;
  assert.ok(scriptStart >= 0 && scriptEnd > scriptStart, 'The local preview fixture has a replaceable module entry');
  const fixtureHTML = preview.slice(0, scriptStart)
    + '<script src="/animation.js"></script><script type="module" src="/fixture.js"></script>'
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
    let bodyAvailable = !url.searchParams.has('hold-body');
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
    const host = {
      location: new URL('app://-/index.html?initialRoute=%2F'), document: hostDocument,
      MutationObserver, addEventListener: window.addEventListener.bind(window),
      removeEventListener: window.removeEventListener.bind(window),
      setTimeout: window.setTimeout.bind(window), clearTimeout: window.clearTimeout.bind(window),
    };
    const frameSpecs = [];
    const senders = new Map();
    const wallpaper = { version: '0.7.1', preview: true, image: ${JSON.stringify(pixelImage)},
      imageSHA256: ${JSON.stringify(imageSHA256)}, css: await fetch('/wallpaper.css').then(response => response.text()), strength: initialWallpaperStrength };
    const legacyWallpaper = { ...wallpaper, css: await fetch('/legacy-wallpaper.css').then(response => response.text()) };
    const fixturePayload = function (frameWindow, frameDocument, _location, _performance, _indexedDB,
      _Image, _Path2D, _URL, requestAnimationFrame, _cancelAnimationFrame, _setTimeout, _clearTimeout,
      _module, SEND, frameSpec) {
      frameSpecs.push({ runId: frameSpec.runId, intent: frameSpec.intent, protocolVersion: frameSpec.protocolVersion,
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
    const payload = url.searchParams.has('animation') ? window.installAnimation : fixturePayload;
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
      ? { wallpaper: ${JSON.stringify(pixelImage)}, avatar: animationAvatar, artwork: animationArtwork,
          contours: ${JSON.stringify(animationContourFixture)}, introTitle: 'Synthetic agent',
          introCaption: 'SYNTHETIC / TEST', artworkSubtitle: 'Generated fixture only' }
      : { wallpaper: ${JSON.stringify(pixelImage)} });
    payload.applyWallpaper = async (background, isCurrent) => {
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
    outerWindow.__startupInstallResult = result;
    outerWindow.__startupFrameSpecs = frameSpecs;
    outerWindow.__startupFixtureSend = (runId, message) => senders.get(runId)?.(message);
    outerWindow.__releaseBody = () => {
      bodyAvailable = true;
      const marker = document.createElement('span');
      marker.hidden = true;
      marker.dataset.bodyGate = 'open';
      document.documentElement.appendChild(marker);
      queueMicrotask(() => marker.remove());
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
    ['/wallpaper.css', ['text/css; charset=utf-8', wallpaperCSS]],
    ['/legacy-wallpaper.css', ['text/css; charset=utf-8', legacyWallpaperCSS]],
    ['/wallpaper/renderer.js', ['text/javascript; charset=utf-8', wallpaperRenderer]],
    ['/legacy/wallpaper/renderer.js', ['text/javascript; charset=utf-8', legacyWallpaperRenderer]],
    ['/extension/renderer.mjs', ['text/javascript; charset=utf-8', controllerRenderer]],
  ]);
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
  ]);
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
        introTitle: 'Synthetic agent', introCaption: 'SYNTHETIC / TEST', artworkSubtitle: 'Generated fixture only',
      };
    })();
  `;
  await writeFile(join(animationDefaultsDir, 'defaults.js'), syntheticDefaults, 'utf8');
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
      const frame=document.querySelector('iframe[title="Agent Skin startup"]');
      const unknown=document.querySelector('#fixture-unknown');
      return {frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length,
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
      frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length,
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
      frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length,
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
  await check('child shortcut opens settings in the same iframe and saved settings start a fresh run', async () => {
    const before = await cdp.evaluate('window.__startupAPI.status()');
    const opened = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="Agent Skin startup"]');
      frame.contentWindow.dispatchEvent(new KeyboardEvent('keydown',{key:'b',metaKey:true,altKey:true,cancelable:true}));
      return {count:document.querySelectorAll('iframe[title="Agent Skin startup"]').length,state:window.__startupAPI.status()};
    })()`);
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
    return { before: { runId: before.runId, phase: before.phase }, replay: { runId: replay.runId, phase: replay.phase }, spec };
  });
  await check('complete removes the frame, parent shortcut creates a settings frame, and cancellation does not replay', async () => {
    const play = await cdp.evaluate('window.__startupAPI.status()');
    await cdp.evaluate(`window.__startupFixtureSend(${play.runId},{type:'azhou-startup',action:'complete',runId:${play.runId},skipped:false})`);
    assert.equal((await cdp.evaluate('window.__startupAPI.status()')).phase, 'complete');
    assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[title=\\"Agent Skin startup\\"]").length'), 0);
    assert.equal(await cdp.evaluate(`(()=>{const input=document.querySelector('textarea');input.focus();return document.activeElement===input;})()`), true);
    const shortcut = await cdp.evaluate(`(()=>{
      const event=new KeyboardEvent('keydown',{key:'B',metaKey:true,altKey:true,cancelable:true});
      const dispatched=window.dispatchEvent(event);
      return {dispatched,defaultPrevented:event.defaultPrevented,count:document.querySelectorAll('iframe[title="Agent Skin startup"]').length};
    })()`);
    assert.equal(shortcut.defaultPrevented, true);
    assert.equal(shortcut.count, 1);
    const settings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='settings'&&state.ready?state:false;
    })()`), 10000, 'settings-intent ready');
    const spec = await cdp.evaluate('window.__startupFrameSpecs.at(-1)');
    assert.equal(spec.intent, 'settings');
    assert.equal(await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="Agent Skin startup"]');
      frame.contentDocument.querySelector('#startup-fixture-settings-input').focus();
      return document.activeElement===frame;
    })()`), true);
    await cdp.evaluate(`window.__startupFixtureSend(${settings.runId},{type:'azhou-startup',action:'complete',runId:${settings.runId},skipped:true})`);
    const cancelled = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(cancelled.phase, 'complete');
    assert.deepEqual(cancelled.completion, { cause: 'settings-cancel', beforeReady: false });
    assert.equal(await cdp.evaluate(`document.activeElement===document.querySelector('textarea')`), true,
      'cancel restores the host control focused before the settings iframe opened');

    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    const secondSettings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='settings'&&state.ready?state:false;
    })()`), 10000, 'second settings-intent ready');
    await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="Agent Skin startup"]');
      frame.contentDocument.querySelector('#startup-fixture-settings-input').focus();
      document.querySelector('#theme').focus();
    })()`);
    await cdp.evaluate(`window.__startupFixtureSend(${secondSettings.runId},{type:'azhou-startup',action:'complete',runId:${secondSettings.runId},skipped:true})`);
    assert.equal(await cdp.evaluate('document.activeElement===document.querySelector("#theme")'), true,
      'cleanup leaves a later host focus change alone');
    return { settings: { runId: settings.runId, phase: settings.phase }, completion: cancelled.completion,
      restoredHostFocus: true, preservedLaterFocus: true };
  });
  await check('completed page remains editable and wallpaper survives animation completion', async () => {
    const result = await cdp.evaluate(`(()=>{
      const input=document.querySelector('textarea');
      input.focus();input.value='synthetic host input';
      const rect=input.getBoundingClientRect();
      return {focused:document.activeElement===input,hit:document.elementFromPoint(rect.x+8,rect.y+8)===input,
        inputValue:input.value,wallpaper:window.__startupAPI.status().wallpaper.applied,
        frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length};
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
        frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length,
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
    await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:42})`);
    await until(() => cdp.evaluate('window.__decodeGateCount===1'), 10000, 'first real decode gate');
    await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:0})`);
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
    const sendBackground = strength => cdp.evaluate(`window.__startupFixtureSend(${state.runId},{
      type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:${strength}})`);
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
      assert.equal(committed.version, '0.7.1');
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
    const before = await cdp.evaluate(`({phase:window.__startupAPI.status().phase,frames:document.querySelectorAll('iframe[title="Agent Skin startup"]').length})`);
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
      installed:Object.hasOwn(window,'__azhouStartup'),frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length
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
      frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length,
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
      const frame=document.querySelector('iframe[title="Agent Skin startup"]');
      const doc=frame?.contentDocument,stage=doc?.querySelector('[data-agent-skin-stage]');
      return {frameCount:document.querySelectorAll('iframe[title="Agent Skin startup"]').length,
        root:!!stage,prewarmed:stage?.dataset.prewarmed==='true',duration:stage?.dataset.duration,
        canvas:doc?.querySelector('canvas')?.dataset.coordinateSize,
        skip:!!doc?.querySelector('[data-agent-skin-skip]')};
    })()`);
    assert.deepEqual(beforeSkip, { frameCount: 1, root: true, prewarmed: true, duration: '12', canvas: '1536x1024', skip: true });
    await cdp.evaluate(`(()=>{
      const button=document.querySelector('iframe[title="Agent Skin startup"]').contentDocument.querySelector('[data-agent-skin-skip]');
      button.click();button.click();
    })()`);
    const completed = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI.status();return value.phase==='complete'&&!value.overlay?value:false;
    })()`), 5000, 'idempotent startup skip');
    assert.deepEqual(completed.completion, { cause: 'skip', beforeReady: false });
    assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[title=\\"Agent Skin startup\\"]").length'), 0);
    return { readyRun: { runId: state.runId, phase: state.phase, ready: state.ready }, beforeSkip, completed: completed.completion };
  });

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
  await check('one RC3 canvas stays registered at all required times, viewport sizes and DPR values', async () => {
    const expectedStages = new Map([
      [0, 'pulse'], [1.15, 'identity'], [4.18, 'dispersing'], [4.74, 'scattered'],
      [5.08, 'drawing'], [7.18, 'colorize'], [7.43, 'portrait'], [11, 'shutter'], [12, 'complete'],
    ]);
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
        const actualViewport = await cdp.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})');
        assert.deepEqual(actualViewport, { width: size.width, height: size.height, dpr },
          `emulated viewport for ${size.name} at DPR ${dpr}`);
        for (const [seconds, expectedStage] of expectedStages) {
          await cdp.evaluate(`window.launcherUI.seek(${seconds})`);
          const state = await cdp.evaluate(`(()=>{
            const root=document.querySelector('[data-agent-skin-stage]');
            const canvas=root.querySelector('canvas[data-agent-skin-canvas]');
            const report=window.launcherUI.report();
            return {stage:report.stage,progress:report.animationProgress,viewport:report.viewport,
              backing:{width:canvas.width,height:canvas.height},css:{width:canvas.clientWidth,height:canvas.clientHeight},
              prewarmed:root.dataset.prewarmed,coordinateSize:canvas.dataset.coordinateSize};
          })()`);
          assert.equal(state.stage, expectedStage, `phase at ${seconds}s`);
          assert.equal(state.prewarmed, 'true');
          assert.equal(state.coordinateSize, '1536x1024');
          assert.equal(state.css.width, size.width, JSON.stringify(state));
          assert.equal(state.css.height, size.height, JSON.stringify(state));
          assert.equal(state.backing.width, size.width * dpr);
          assert.equal(state.backing.height, size.height * dpr);
          matrix.push({ size: size.name, dpr, seconds, ...state });
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
    return { screenshotCount: matrix.length, matrix, colorRegistration: { beforeColor, colorizeStart, portraitColor }, prewarmed: animationReady.resources };
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

  report.finishedAt = new Date().toISOString();
  report.passed = report.checks.length > 0 && report.checks.every(item => item.passed);
} catch (error) {
  report.fatalError = safeError(error);
  if (chromeError && !cdp) report.ownChromeStartupError = chromeError.slice(-1200);
} finally {
  try { await cleanup(); } catch (error) { report.cleanupError = safeError(error); }
  report.finishedAt = new Date().toISOString();
  report.passed = !report.fatalError && !report.cleanupError && report.cleanup?.ownChromeStopped
    && report.cleanup.temporaryProfileRemoved && report.cleanup.serverClosed
    && report.checks.length > 0 && report.checks.every(item => item.passed);
  await mkdir(options.out, { recursive: true });
  await writeFile(join(options.out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ passed: report.passed, report: join(options.out, 'report.json'),
    checks: report.checks.map(({ name, passed }) => ({ name, passed })), fatalError: report.fatalError }));
  if (!report.passed) process.exitCode = 1;
}
