#!/usr/bin/env node
// Uses an isolated headless Chrome and test-generated image pixels only.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CHROME_DEFAULT = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const MAX_INPUT_BYTES = 31_457_280;
const options = { chrome: CHROME_DEFAULT };
for (let index = 2; index < process.argv.length; index++) {
  const key = process.argv[index];
  if (key === '--help') {
    console.log('node tools/test-image-settings-browser.mjs [--chrome /path/to/Chrome]');
    process.exit(0);
  }
  if (key !== '--chrome' || !process.argv[index + 1]) throw new Error('Unknown or missing argument: ' + key);
  options.chrome = process.argv[++index];
}
options.chrome = resolve(options.chrome);

async function until(operation, milliseconds, label) {
  const deadline = Date.now() + milliseconds;
  let lastError;
  do {
    try {
      const value = await operation();
      if (value) return value;
    } catch (error) { lastError = error; }
    await delay(40);
  } while (Date.now() < deadline);
  throw new Error('Timed out waiting for ' + label + (lastError ? ': ' + String(lastError.message || lastError) : ''));
}

class CDP {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    socket.addEventListener('message', event => {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      message.error ? pending.reject(new Error(message.error.message)) : pending.resolve(message.result);
    });
    socket.addEventListener('close', () => {
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timer);
        pending.reject(new Error('Chrome DevTools socket closed'));
      }
      this.pending.clear();
    });
  }
  static async open(address) {
    const socket = new WebSocket(address);
    await new Promise((resolveOpen, reject) => {
      const timer = setTimeout(() => { socket.close(); reject(new Error('Chrome DevTools connection timed out')); }, 5000);
      socket.addEventListener('open', () => { clearTimeout(timer); resolveOpen(); }, { once: true });
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Chrome DevTools connection failed')); }, { once: true });
    });
    return new CDP(socket);
  }
  call(method, params = {}, timeoutMs = 100_000) {
    const id = this.nextId++;
    return new Promise((resolveCall, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('Chrome DevTools request timed out: ' + method));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolveCall, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.call('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      timeout: 90_000,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.result?.description || result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    }
    return result.result?.value;
  }
  close() { this.socket.close(); }
}

function browserChecks(maxInputBytes) {
  return (async () => {
    const frame = document.createElement('iframe');
    const frameLoaded = new Promise(resolve => { frame.addEventListener('load', resolve, { once: true }); });
    frame.src = 'about:blank';
    document.body.append(frame);
    await frameLoaded;
    const child = frame.contentWindow;
    const childDocument = frame.contentDocument;
    childDocument.documentElement.lang = 'zh-CN';
    childDocument.documentElement.style.colorScheme = 'dark';
    childDocument.documentElement.style.setProperty('--agent-skin-surface', 'rgb(18, 24, 36)');
    childDocument.documentElement.style.setProperty('--agent-skin-text', 'rgb(238, 240, 245)');
    childDocument.documentElement.style.setProperty('--agent-skin-muted', 'rgb(176, 186, 204)');
    childDocument.documentElement.style.setProperty('--agent-skin-border', 'rgb(92, 108, 132)');
    const localization = createLocalization({ locale: childDocument.documentElement.lang });
    const appearanceAvatarCanvas = childDocument.createElement('canvas');
    appearanceAvatarCanvas.width = 8;
    appearanceAvatarCanvas.height = 8;
    appearanceAvatarCanvas.getContext('2d').fillRect(0, 0, 8, 8);
    const appearanceAvatar = appearanceAvatarCanvas.toDataURL('image/png');
    const created = [];
    const revoked = [];
    const urlApi = {
      createObjectURL(blob) {
        const url = child.URL.createObjectURL(blob);
        created.push(url);
        return url;
      },
      revokeObjectURL(url) {
        revoked.push(url);
        child.URL.revokeObjectURL(url);
      },
    };
    const api = createImageSettings({
      document: childDocument,
      Image: child.Image,
      URL: urlApi,
      indexedDB: child.indexedDB,
      localization,
      appearanceAvatar,
      setTimeout: child.setTimeout.bind(child),
      clearTimeout: child.clearTimeout.bind(child),
      performance: child.performance,
    });
    const canvasFor = (width, height, paint) => {
      const canvas = childDocument.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      paint(canvas.getContext('2d'));
      return canvas;
    };
    const blobFor = (canvas, type) => new Promise((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Chrome could not encode a synthetic ' + type)), type, 0.95);
    });
    const fileFor = async (canvas, type, name) => new child.File([await blobFor(canvas, type)], name, { type });
    const readPixel = async (dataURL, x, y) => {
      const image = new child.Image();
      image.src = dataURL;
      await image.decode();
      const canvas = childDocument.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context.drawImage(image, 0, 0);
      return Array.from(context.getImageData(x, y, 1, 1).data);
    };

    const formatCanvas = canvasFor(80, 60, context => {
      context.fillStyle = '#1557a0';
      context.fillRect(0, 0, 80, 60);
      context.fillStyle = '#f0c419';
      context.fillRect(20, 10, 40, 40);
    });
    const formats = [];
    for (const type of ['image/png', 'image/jpeg', 'image/webp']) {
      const result = await api.importImage(await fileFor(formatCanvas, type, 'synthetic.' + type.slice(6)), 'avatar');
      formats.push({ type, dimensions: [result.width, result.height], png: result.dataURL.startsWith('data:image/png;base64,'), byteCount: result.bytes === result.dataURL.length });
    }

    const cropCanvas = canvasFor(800, 400, context => {
      context.fillStyle = '#f00000';
      context.fillRect(0, 0, 400, 400);
      context.fillStyle = '#0000f0';
      context.fillRect(400, 0, 400, 400);
    });
    const crop = await api.importImage(await fileFor(cropCanvas, 'image/png', 'crop.png'), 'avatar');
    const cropLeft = await readPixel(crop.dataURL, 128, 256);
    const cropRight = await readPixel(crop.dataURL, 384, 256);

    const portraitCanvas = canvasFor(400, 800, context => {
      context.fillStyle = '#f00000';
      context.fillRect(0, 0, 400, 400);
      context.fillStyle = '#0000f0';
      context.fillRect(0, 400, 400, 400);
    });
    const portrait = await api.importImage(await fileFor(portraitCanvas, 'image/png', 'portrait.png'), 'avatar');
    const portraitTop = await readPixel(portrait.dataURL, 256, 128);
    const portraitBottom = await readPixel(portrait.dataURL, 256, 384);

    const squareCanvas = canvasFor(120, 120, context => {
      context.fillStyle = '#f00000';
      context.fillRect(0, 0, 60, 120);
      context.fillStyle = '#0000f0';
      context.fillRect(60, 0, 60, 120);
    });
    const square = await api.importImage(await fileFor(squareCanvas, 'image/png', 'square.png'), 'avatar');
    const squareLeft = await readPixel(square.dataURL, 128, 256);
    const squareRight = await readPixel(square.dataURL, 384, 256);

    const alphaCanvas = canvasFor(200, 100, context => {
      context.clearRect(0, 0, 200, 100);
      context.fillStyle = '#00ff40';
      context.fillRect(80, 30, 40, 40);
    });
    const alpha = await api.importImage(await fileFor(alphaCanvas, 'image/png', 'alpha.png'), 'avatar');
    const transparentCorner = await readPixel(alpha.dataURL, 8, 8);

    const artCanvas = canvasFor(800, 400, context => {
      context.fillStyle = '#1b3f60';
      context.fillRect(0, 0, 800, 400);
      context.fillStyle = '#ffe000';
      context.fillRect(390, 0, 20, 400);
    });
    const art = await api.importImage(await fileFor(artCanvas, 'image/png', 'artwork.png'), 'artwork');
    const artCenter = await readPixel(art.dataURL, 768, 512);
    const contourRegistration = art.contours.flat().some(([x, y]) => Math.abs(x - 768) < 32 && y > 100 && y < 900);

    const flatCanvas = canvasFor(128, 128, context => {
      context.fillStyle = '#373737';
      context.fillRect(0, 0, 128, 128);
    });
    let flatReason = '';
    try { await api.importImage(await fileFor(flatCanvas, 'image/png', 'flat.png'), 'artwork'); }
    catch (error) { flatReason = error.reason || ''; }

    const smallPng = await blobFor(cropCanvas, 'image/png');
    const padding = new Uint8Array(maxInputBytes - smallPng.size);
    const boundaryFile = new child.File([smallPng, padding], 'exact-30-mib.png', { type: 'image/png' });
    const boundary = await api.importImage(boundaryFile, 'avatar');

    const defaults = {
      avatar: crop.dataURL,
      artwork: art.dataURL,
      contours: art.contours,
      introTitle: 'Generated base',
      introCaption: '',
      artworkSubtitle: 'Generated fixture only',
      wallpaperStrength: 42,
    };
    const initiallyLoaded = await api.load(defaults);
    api.openSettings();
    const settingsDialog = childDocument.querySelector('dialog[data-agent-skin-settings]');
    const titleInput = settingsDialog.querySelector('input[type="text"]');
    titleInput.value = 'Local draft';
    titleInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    localization.setLocale('en');
    const inputStyle = child.getComputedStyle(titleInput);
    const restoreButton = settingsDialog.querySelector('footer button');
    const buttonStyle = child.getComputedStyle(restoreButton);
    const saveButton = settingsDialog.querySelector('footer button:last-child');
    const saveStyle = child.getComputedStyle(saveButton);
    const identityAvatar = settingsDialog.querySelector('[data-agent-skin-appearance-avatar]');
    const appearance = {
      locale: localization.locale,
      dialogCount: childDocument.querySelectorAll('dialog[data-agent-skin-settings]').length,
      title: settingsDialog.querySelector('#agent-skin-settings-title').textContent,
      appearanceAvatar: Boolean(identityAvatar?.src.startsWith('data:image/png;base64,')),
      appearanceAvatarAlt: identityAvatar?.getAttribute('alt'),
      fieldLabel: titleInput.getAttribute('aria-label'),
      draftValue: titleInput.value,
      colorScheme: child.getComputedStyle(settingsDialog).colorScheme,
      surface: child.getComputedStyle(settingsDialog).backgroundColor,
      inputSurface: inputStyle.backgroundColor,
      inputText: inputStyle.color,
      inputBorder: inputStyle.borderTopColor,
      buttonSurface: buttonStyle.backgroundColor,
      buttonText: buttonStyle.color,
      buttonBorder: buttonStyle.borderTopColor,
      saveSurface: saveStyle.backgroundColor,
      saveText: saveStyle.color,
    };
    api.cancelSettings();
    const initialCandidate = {
      schemaVersion: 1,
      avatar: crop.dataURL,
      artwork: art.dataURL,
      contours: art.contours,
      introTitle: 'Saved fixture',
      introCaption: '',
      artworkSubtitle: 'Generated fixture only',
      wallpaperStrength: 27,
    };
    const initialCommit = await api.save(initialCandidate);

    const secondPage = childDocument.createElement('iframe');
    const secondPageLoaded = new Promise(resolve => secondPage.addEventListener('load', resolve, { once: true }));
    secondPage.src = 'about:blank';
    childDocument.body.append(secondPage);
    await secondPageLoaded;
    const secondWindow = secondPage.contentWindow;
    const secondDocument = secondPage.contentDocument;
    const secondAPI = createImageSettings({
      document: secondDocument,
      Image: secondWindow.Image,
      URL: secondWindow.URL,
      indexedDB: secondWindow.indexedDB,
      setTimeout: secondWindow.setTimeout.bind(secondWindow),
      clearTimeout: secondWindow.clearTimeout.bind(secondWindow),
      performance: secondWindow.performance,
    });
    const secondPageBaseline = await secondAPI.load(defaults);
    const winningCandidate = { ...initialCommit, introTitle: 'Page A wins' };
    const competingCandidate = { ...secondPageBaseline.settings, introTitle: 'Page B stale' };
    const winningCommit = await api.save(winningCandidate);
    let conflictReason = '';
    try { await secondAPI.save(competingCandidate); }
    catch (error) { conflictReason = error.reason || ''; }
    const reloaded = await api.load(defaults);
    secondAPI.dispose();
    secondPage.remove();
    const versionchange = await new Promise((resolve, reject) => {
      const request = child.indexedDB.open('azhou-codex-startup', 2);
      let blocked = false;
      let oldVersion = null;
      const timer = child.setTimeout(() => reject(new Error('versionchange close timed out')), 5000);
      request.onblocked = () => { blocked = true; };
      request.onupgradeneeded = event => { oldVersion = event.oldVersion; };
      request.onerror = () => { child.clearTimeout(timer); reject(request.error || new Error('versionchange upgrade failed')); };
      request.onsuccess = () => {
        child.clearTimeout(timer);
        const db = request.result;
        const result = { blocked, oldVersion, version: db.version };
        db.close();
        resolve(result);
      };
    });
    api.dispose();

    frame.remove();
    return {
      formats,
      cropLeft,
      cropRight,
      portraitTop,
      portraitBottom,
      squareLeft,
      squareRight,
      transparentCorner,
      artCenter,
      contourRegistration,
      flatReason,
      boundarySize: boundaryFile.size,
      boundaryDimensions: [boundary.width, boundary.height],
      revokedCount: revoked.length,
      createdCount: created.length,
      idleCancelResult: api.cancelImport(),
      appearance,
      storage: {
        initialReason: initiallyLoaded.reason,
        initialBaseline: initiallyLoaded.baseline,
        initialTitle: initialCommit.introTitle,
        hasAppearanceAvatar: Object.hasOwn(initialCommit, 'appearanceAvatar'),
        secondPageLoadedTitle: secondPageBaseline.settings.introTitle,
        winningTitle: winningCommit.introTitle,
        conflictReason,
        reloadedTitle: reloaded.settings.introTitle,
        reloadedBaselineTitle: reloaded.baseline?.introTitle,
        versionchange,
      },
    };
  })();
}

let server;
let chrome;
let cdp;
let profile;

async function cleanup() {
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
}

try {
  assert.equal(typeof WebSocket, 'function', 'Node 22 or newer is required for the built-in WebSocket');
  const imageSettings = await readFile(join(PACKAGE_ROOT, 'image-settings.js'));
  const localizationSource = await readFile(join(PACKAGE_ROOT, 'localization.js'));
  const html = '<!doctype html><meta charset="utf-8"><title>image settings fixture</title>'
    + '<script src="/localization.js"></script><script src="/image-settings.js"></script>'
    + '<script>window.imageSettingsReady = typeof createImageSettings === "function" && typeof createLocalization === "function";</script>';
  server = createServer((request, response) => {
    if (request.url === '/image-settings.js') {
      response.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      response.end(imageSettings);
    } else if (request.url === '/localization.js') {
      response.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      response.end(localizationSource);
    } else if (request.url === '/' || request.url === '/index.html') {
      response.setHeader('content-security-policy',
        "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'");
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
      response.end(html);
    } else {
      response.writeHead(404);
      response.end();
    }
  });
  await new Promise((resolveListen, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolveListen);
  });
  const origin = 'http://127.0.0.1:' + server.address().port;
  profile = await mkdtemp(join(tmpdir(), 'agent-skin-image-settings-chrome-'));
  chrome = spawn(options.chrome, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-extensions', '--remote-debugging-port=0',
    '--remote-allow-origins=*', '--user-data-dir=' + profile, 'about:blank',
  ], { stdio: 'ignore' });
  chrome.once('error', error => { throw error; });
  const activePortFile = await until(async () => {
    try { return await readFile(join(profile, 'DevToolsActivePort'), 'utf8'); }
    catch { return null; }
  }, 15_000, 'Chrome DevTools port');
  const port = Number(activePortFile.split('\n')[0]);
  const target = await until(async () => {
    const response = await fetch('http://127.0.0.1:' + port + '/json/list');
    if (!response.ok) return null;
    const targets = await response.json();
    return targets.find(item => item.type === 'page' && item.webSocketDebuggerUrl);
  }, 10_000, 'isolated Chrome page');
  cdp = await CDP.open(target.webSocketDebuggerUrl);
  await cdp.call('Runtime.enable');
  await cdp.call('Page.enable');
  await cdp.call('Page.navigate', { url: origin + '/' });
  await until(() => cdp.evaluate('window.imageSettingsReady === true'), 10_000, 'image settings source load');
  const expression = '(' + browserChecks.toString() + ')(' + MAX_INPUT_BYTES + ')';
  const result = await cdp.evaluate(expression);

  assert.deepEqual(result.formats.map(item => item.type), ['image/png', 'image/jpeg', 'image/webp']);
  for (const item of result.formats) {
    assert.deepEqual(item.dimensions, [512, 512]);
    assert.equal(item.png, true);
    assert.equal(item.byteCount, true);
  }
  assert.ok(result.cropLeft[0] > result.cropLeft[2], 'left side of the center crop stays red');
  assert.ok(result.cropRight[2] > result.cropRight[0], 'right side of the center crop stays blue');
  assert.ok(result.portraitTop[0] > result.portraitTop[2], 'top of the portrait crop stays red');
  assert.ok(result.portraitBottom[2] > result.portraitBottom[0], 'bottom of the portrait crop stays blue');
  assert.ok(result.squareLeft[0] > result.squareLeft[2], 'left side of a square source stays red');
  assert.ok(result.squareRight[2] > result.squareRight[0], 'right side of a square source stays blue');
  assert.deepEqual(result.transparentCorner, [16, 17, 20, 255]);
  assert.deepEqual(result.artCenter.slice(0, 3), [255, 224, 0]);
  assert.equal(result.contourRegistration, true);
  assert.equal(result.flatReason, 'asset-invalid');
  assert.equal(result.boundarySize, MAX_INPUT_BYTES);
  assert.deepEqual(result.boundaryDimensions, [512, 512]);
  assert.equal(result.revokedCount, result.createdCount);
  assert.equal(result.idleCancelResult, false);
  assert.deepEqual(result.appearance, {
    locale: 'en',
    dialogCount: 1,
    title: 'Azhou · Appearance',
    appearanceAvatar: true,
    appearanceAvatarAlt: '',
    fieldLabel: 'Startup title (up to 16 characters)',
    draftValue: 'Local draft',
    colorScheme: 'dark',
    surface: 'rgb(18, 24, 36)',
    inputSurface: 'rgb(18, 24, 36)',
    inputText: 'rgb(238, 240, 245)',
    inputBorder: 'rgb(92, 108, 132)',
    buttonSurface: 'rgb(18, 24, 36)',
    buttonText: 'rgb(238, 240, 245)',
    buttonBorder: 'rgb(92, 108, 132)',
    saveSurface: 'rgb(238, 240, 245)',
    saveText: 'rgb(18, 24, 36)',
  });
  assert.equal(result.storage.initialReason, '');
  assert.equal(result.storage.initialBaseline, undefined);
  assert.equal(result.storage.initialTitle, 'Saved fixture');
  assert.equal(result.storage.hasAppearanceAvatar, false);
  assert.equal(result.storage.secondPageLoadedTitle, 'Saved fixture');
  assert.equal(result.storage.winningTitle, 'Page A wins');
  assert.equal(result.storage.conflictReason, 'settings-conflict');
  assert.equal(result.storage.reloadedTitle, 'Page A wins');
  assert.equal(result.storage.reloadedBaselineTitle, 'Page A wins');
  assert.equal(result.storage.versionchange.blocked, false,
    'the settings connection closes on versionchange so the newer open can proceed');
  assert.equal(result.storage.versionchange.oldVersion, 1);
  assert.equal(result.storage.versionchange.version, 2);
  console.log(JSON.stringify({
    status: 'PASS',
    scope: 'synthetic image import, host-locale settings and theme tokens under strict style CSP, real IndexedDB save/reload, two-page conflict and versionchange close',
    formats: result.formats.map(item => item.type),
    boundaryBytes: result.boundarySize,
    objectURLsReleased: result.revokedCount + '/' + result.createdCount,
    storage: result.storage,
  }, null, 2));
} catch (error) {
  console.error(error.stack || String(error));
  process.exitCode = 1;
} finally {
  await cleanup();
}
