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
  const html = '<!doctype html><meta charset="utf-8"><title>image settings fixture</title>'
    + '<script src="/image-settings.js"></script><script>window.imageSettingsReady = typeof createImageSettings === "function";</script>';
  server = createServer((request, response) => {
    if (request.url === '/image-settings.js') {
      response.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      response.end(imageSettings);
    } else if (request.url === '/' || request.url === '/index.html') {
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
  console.log(JSON.stringify({
    status: 'PASS',
    scope: 'synthetic PNG/JPEG/WebP decode, crop, transparent composite, same-crop contours, flat artwork rejection, 30 MiB valid input boundary',
    formats: result.formats.map(item => item.type),
    boundaryBytes: result.boundarySize,
    objectURLsReleased: result.revokedCount + '/' + result.createdCount,
  }, null, 2));
} catch (error) {
  console.error(error.stack || String(error));
  process.exitCode = 1;
} finally {
  await cleanup();
}
