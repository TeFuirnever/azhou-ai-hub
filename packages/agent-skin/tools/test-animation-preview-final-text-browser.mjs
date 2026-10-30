import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { dirname, join, parse, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const options = {
  chrome: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  preview: join(ROOT, '.build/azhou-payload/Contents/Resources/web/index.html'),
  out: join(ROOT, '.build/animation-preview-browser-evidence'),
  screenshot: null,
};

for (let index = 2; index < process.argv.length; index++) {
  const key = process.argv[index];
  if (!['--chrome', '--preview', '--out', '--screenshot'].includes(key) || !process.argv[index + 1]) {
    throw new Error('Usage: node test-animation-preview-final-text-browser.mjs [--chrome PATH] [--preview FILE] [--out DIR] [--screenshot FILE]');
  }
  const value = process.argv[++index];
  if (key === '--chrome') options.chrome = resolve(value);
  else if (key === '--preview') options.preview = resolve(value);
  else if (key === '--out') options.out = resolve(value);
  else options.screenshot = value;
}
options.screenshot = options.screenshot
  ? resolve(options.out, options.screenshot)
  : join(options.out, 'preview-shutter-focus.png');
const screenshotParts = parse(options.screenshot);
const forcedScreenshot = join(screenshotParts.dir,
  `${screenshotParts.name}-forced-colors${screenshotParts.ext || '.png'}`);

const cdpTimeoutMs = 12000;
let chrome;
let socket;
let profile;

async function until(operation, label, timeoutMs = 12000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  do {
    try {
      const value = await operation();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await delay(50);
  } while (Date.now() < deadline);
  throw new Error(`Timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ''}`);
}

class CDP {
  constructor(webSocket) {
    this.socket = webSocket;
    this.nextID = 1;
    this.pending = new Map();
    this.methodByID = new Map();
    webSocket.addEventListener('message', event => {
      let value;
      try { value = JSON.parse(event.data); } catch { return; }
      if (!value.id || !this.pending.has(value.id)) return;
      const pending = this.pending.get(value.id);
      this.pending.delete(value.id);
      const method = this.methodByID.get(value.id);
      this.methodByID.delete(value.id);
      clearTimeout(pending.timer);
      value.error ? pending.reject(new Error(`${method}: ${value.error.message}`)) : pending.resolve(value.result);
    });
    webSocket.addEventListener('close', () => {
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timer);
        pending.reject(new Error('Chrome DevTools connection closed'));
      }
      this.pending.clear();
    });
  }

  call(method, params = {}) {
    const id = this.nextID++;
    this.methodByID.set(id, method);
    return new Promise((resolveCall, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Chrome DevTools timeout: ${method}`));
      }, cdpTimeoutMs);
      this.pending.set(id, { resolve: resolveCall, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const result = await this.call('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      timeout: cdpTimeoutMs,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    }
    return result.result?.value;
  }
}

async function stopChrome() {
  try { socket?.close(); } catch {}
  if (!chrome || chrome.exitCode !== null || chrome.signalCode !== null) return;
  const exited = new Promise(resolveExit => chrome.once('exit', resolveExit));
  chrome.kill('SIGTERM');
  await Promise.race([exited, delay(2000)]);
  if (chrome.exitCode === null && chrome.signalCode === null) {
    chrome.kill('SIGKILL');
    await Promise.race([exited, delay(1000)]);
  }
}

async function sendTab(cdp) {
  const key = { key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 48 };
  await cdp.call('Input.dispatchKeyEvent', { ...key, type: 'rawKeyDown' });
  await cdp.call('Input.dispatchKeyEvent', { ...key, type: 'keyUp' });
}

async function tabTo(cdp, targetID) {
  for (let count = 1; count <= 8; count++) {
    await sendTab(cdp);
    const activeID = await cdp.evaluate('document.activeElement?.id || ""');
    if (activeID === targetID) return count;
  }
  throw new Error(`Real Tab navigation did not reach #${targetID}`);
}

await access(options.chrome);
await access(options.preview);
await access(join(dirname(options.preview), 'assets/defaults/contours.js'));
await mkdir(options.out, { recursive: true });
await mkdir(dirname(options.screenshot), { recursive: true });

try {
  profile = await mkdtemp(join(tmpdir(), 'agent-skin-final-text-'));
  chrome = spawn(options.chrome, [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-background-networking',
    '--disable-renderer-backgrounding',
    '--allow-file-access-from-files',
    '--force-device-scale-factor=1',
    '--window-size=800,900',
    '--remote-debugging-port=0',
    '--remote-allow-origins=*',
    `--user-data-dir=${profile}`,
    'about:blank',
  ], { stdio: 'ignore' });

  const activePortPath = join(profile, 'DevToolsActivePort');
  const activePort = await until(async () => {
    const contents = await readFile(activePortPath, 'utf8').catch(() => '');
    const port = Number(contents.split('\n')[0]);
    return Number.isInteger(port) && port > 0 ? port : null;
  }, 'isolated Chrome DevTools port');
  const endpoint = `http://127.0.0.1:${activePort}`;
  const targetResponse = await fetch(`${endpoint}/json/new?about:blank`, { method: 'PUT' });
  assert.equal(targetResponse.ok, true, 'isolated Chrome must create a fresh preview tab');
  const target = await targetResponse.json();
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolveOpen, reject) => {
    const timer = setTimeout(() => reject(new Error('Timed out connecting to isolated Chrome')), 5000);
    socket.addEventListener('open', () => { clearTimeout(timer); resolveOpen(); }, { once: true });
    socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Could not connect to isolated Chrome')); }, { once: true });
  });
  const cdp = new CDP(socket);
  await cdp.call('Page.enable');
  await cdp.call('Runtime.enable');
  await cdp.call('DOM.enable');
  await cdp.call('Accessibility.enable');
  await cdp.call('Page.navigate', { url: pathToFileURL(options.preview).href });

  await until(async () => cdp.evaluate(`(() => {
    try {
      return document.readyState === 'complete'
        && typeof window.launcherUI?.report === 'function'
        && window.launcherUI.report().resources.liveBitmaps > 0;
    } catch { return false; }
  })()`), 'generated preview assets and animation readiness', 20000);

  const hooked = await cdp.evaluate(`(() => {
    const canvas = document.querySelector('[data-agent-skin-canvas]');
    const prototype = window.CanvasRenderingContext2D?.prototype;
    if (!canvas || !prototype || window.__finalTextCaptureInstalled) return false;
    const original = prototype.fillText;
    Object.defineProperty(window, '__finalCanvasTextRects', { value: [], configurable: true });
    Object.defineProperty(window, '__finalTextCaptureInstalled', { value: true });
    prototype.fillText = function (text, x, y, maxWidth) {
      if (this.canvas === canvas && Number(y) >= 830) {
        const metrics = this.measureText(String(text));
        const matrix = this.getTransform();
        const bounds = canvas.getBoundingClientRect();
        const scaleX = bounds.width / canvas.width;
        const scaleY = bounds.height / canvas.height;
        const width = Math.min(metrics.width, Number.isFinite(maxWidth) ? maxWidth : metrics.width);
        const align = this.textAlign;
        const leftOffset = align === 'center' ? Number(x) - width / 2
          : ['right', 'end'].includes(align) ? Number(x) - width : Number(x);
        const rightOffset = leftOffset + width;
        const ascent = Math.max(metrics.actualBoundingBoxAscent || 0, metrics.fontBoundingBoxAscent || 0);
        const descent = Math.max(metrics.actualBoundingBoxDescent || 0, metrics.fontBoundingBoxDescent || 0);
        const topOffset = Number(y) - ascent;
        const bottomOffset = Number(y) + descent;
        const left = bounds.left + (matrix.a * leftOffset + matrix.e) * scaleX;
        const right = bounds.left + (matrix.a * rightOffset + matrix.e) * scaleX;
        const top = bounds.top + (matrix.d * topOffset + matrix.f) * scaleY;
        const bottom = bounds.top + (matrix.d * bottomOffset + matrix.f) * scaleY;
        window.__finalCanvasTextRects.push({ left, right, top, bottom });
      }
      return original.call(this, text, x, y, maxWidth);
    };
    return true;
  })()`);
  assert.equal(hooked, true, 'the real preview canvas must expose its rendered text geometry');

  const seekStarted = await cdp.evaluate(`window.launcherUI.seek(11.2)`);
  assert.equal(seekStarted, true, 'the local preview must seek to the shutter phase');
  await until(async () => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.stage === 'shutter'
    && window.__finalCanvasTextRects?.length > 0`), 'shutter stage and canvas subtitle drawing');
  await cdp.evaluate(`document.fonts?.ready.then(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))`);

  const evidence = await cdp.evaluate(`(() => {
    const stage = document.querySelector('[data-agent-skin-stage]');
    const label = document.querySelector('[data-agent-skin-stage-text]');
    const labelStyle = getComputedStyle(label);
    const box = label.getBoundingClientRect();
    const stageBox = { left: box.left, right: box.right, top: box.top, bottom: box.bottom };
    const subtitleBoxes = window.__finalCanvasTextRects.slice(-4);
    const overlaps = subtitleBoxes.map(text => ({
      left: Math.max(stageBox.left, text.left),
      right: Math.min(stageBox.right, text.right),
      top: Math.max(stageBox.top, text.top),
      bottom: Math.min(stageBox.bottom, text.bottom),
    })).map(box => Math.max(0, box.right - box.left) * Math.max(0, box.bottom - box.top));
    const visuallyPresent = labelStyle.display !== 'none'
      && labelStyle.visibility !== 'hidden' && Number(labelStyle.opacity) > 0;
    const canvas = document.querySelector('[data-agent-skin-canvas]');
    return {
      stage: stage?.dataset.stage || '',
      viewport: { width: innerWidth, height: innerHeight },
      stageText: {
        display: labelStyle.display,
        visibility: labelStyle.visibility,
        opacity: labelStyle.opacity,
        box: stageBox,
      },
      canvas: { width: canvas.width, height: canvas.height },
      canvasSubtitleBoxes: subtitleBoxes,
      overlapArea: overlaps.reduce((sum, value) => sum + value, 0),
      visibleOverlapArea: visuallyPresent ? overlaps.reduce((sum, value) => sum + value, 0) : 0,
    };
  })()`);

  const { root: documentNode } = await cdp.call('DOM.getDocument', { depth: -1, pierce: true });
  const { nodeId } = await cdp.call('DOM.querySelector', {
    nodeId: documentNode.nodeId,
    selector: '[data-agent-skin-stage-text]',
  });
  assert.ok(nodeId > 0, 'the generated preview stage text node must be queryable');
  const accessibility = await cdp.call('Accessibility.getPartialAXTree', { nodeId, fetchRelatives: true });
  const accessibleNodes = accessibility.nodes || [];
  const liveValue = accessibleNodes.flatMap(node => node.properties || [])
    .find(property => property.name === 'live')?.value?.value || '';
  const accessibilityEvidence = {
    exposed: accessibleNodes.some(node => !node.ignored),
    hasAccessibleName: accessibleNodes.some(node => !node.ignored
      && typeof node.name?.value === 'string' && node.name.value.length > 0),
    live: liveValue,
  };

  const tabsToPause = await tabTo(cdp, 'pause');
  const normalFocus = await cdp.evaluate(`(() => {
    const target = document.getElementById('pause');
    const style = getComputedStyle(target);
    return {
      active: document.activeElement === target,
      focusVisible: target.matches(':focus-visible'),
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
      outlineOffset: style.outlineOffset,
      outlineColor: style.outlineColor,
      boxShadow: style.boxShadow,
      bounds: (() => { const box = target.getBoundingClientRect(); return { left: box.left, top: box.top, width: box.width, height: box.height }; })(),
    };
  })()`);
  const normalScreenshot = await cdp.call('Page.captureScreenshot', {
    format: 'png', fromSurface: true, captureBeyondViewport: false,
  });
  await writeFile(options.screenshot, Buffer.from(normalScreenshot.data, 'base64'));
  console.log(JSON.stringify({
    shutter: evidence,
    accessibility: accessibilityEvidence,
    normalFocus: { tabsToPause, ...normalFocus },
    screenshot: options.screenshot,
  }, null, 2));

  assert.equal(evidence.stage, 'shutter', 'the screenshot must show the final shutter interval');
  assert.ok(evidence.canvasSubtitleBoxes.length > 0, 'the browser must render the subtitle into the real canvas');
  assert.equal(evidence.visibleOverlapArea, 0,
    'shutter-stage DOM text must not visibly overlap the actual rendered canvas subtitle; see the geometry and screenshot above');
  assert.equal(evidence.stageText.opacity, '0', 'shutter stage text must be visually hidden without removing its live region');
  assert.equal(accessibilityEvidence.exposed, true, 'the stage text must remain in the accessibility tree');
  assert.equal(accessibilityEvidence.hasAccessibleName, true, 'assistive technology must retain the current stage text');
  assert.equal(accessibilityEvidence.live, 'polite', 'stage changes must remain a polite live announcement');
  assert.equal(normalFocus.active, true, 'real Tab input must focus the preview pause control');
  assert.equal(normalFocus.focusVisible, true, 'keyboard focus must match :focus-visible');
  assert.equal(normalFocus.outlineStyle, 'solid', 'normal focus must retain its high-contrast inner outline');
  assert.ok(Number.parseFloat(normalFocus.outlineWidth) >= 2, 'normal focus inner outline must be at least 2px');
  assert.notEqual(normalFocus.boxShadow, 'none', 'normal focus must show the second visible ring');

  await cdp.call('Emulation.setEmulatedMedia', {
    features: [{ name: 'forced-colors', value: 'active' }],
  });
  const forcedColorsActive = await cdp.evaluate("matchMedia('(forced-colors: active)').matches");
  assert.equal(forcedColorsActive, true, 'Chrome must enter forced-colors emulation');
  await cdp.evaluate('document.activeElement?.blur()');
  const forcedTabsToPause = await tabTo(cdp, 'pause');
  const forcedFocus = await cdp.evaluate(`(() => {
    const target = document.getElementById('pause');
    const style = getComputedStyle(target);
    return {
      active: document.activeElement === target,
      focusVisible: target.matches(':focus-visible'),
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
      outlineOffset: style.outlineOffset,
      outlineColor: style.outlineColor,
      boxShadow: style.boxShadow,
    };
  })()`);
  const forcedColorCapture = await cdp.call('Page.captureScreenshot', {
    format: 'png', fromSurface: true, captureBeyondViewport: false,
  });
  await writeFile(forcedScreenshot, Buffer.from(forcedColorCapture.data, 'base64'));
  console.log(JSON.stringify({ forcedColorsActive, forcedFocus: { tabsToPause: forcedTabsToPause, ...forcedFocus }, screenshot: forcedScreenshot }, null, 2));
  assert.equal(forcedFocus.active, true, 'real Tab input must focus the preview pause control in forced-colors mode');
  assert.equal(forcedFocus.focusVisible, true, 'forced-colors keyboard focus must match :focus-visible');
  assert.equal(forcedFocus.outlineStyle, 'double', 'forced-colors focus must use a two-line system-color outline');
  assert.ok(Number.parseFloat(forcedFocus.outlineWidth) >= 3, 'forced-colors focus outline must be at least 3px');
} finally {
  await stopChrome();
  if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 4, retryDelay: 100 });
}
