import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import vm from 'node:vm';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE_PATH = join(ROOT, 'animation.js');
const source = await readFile(SOURCE_PATH, 'utf8');
const animationContext = {};
new vm.Script(source, { filename: SOURCE_PATH }).runInNewContext(animationContext);
const { installAnimation } = animationContext;
const localizationContext = {};
new vm.Script(await readFile(join(ROOT, 'localization.js'), 'utf8'), {
  filename: join(ROOT, 'localization.js'),
}).runInNewContext(localizationContext);
const imageSettingsContext = {};
new vm.Script(await readFile(join(ROOT, 'image-settings.js'), 'utf8'), {
  filename: join(ROOT, 'image-settings.js'),
}).runInNewContext(imageSettingsContext);

const TRANSPARENT_PIXELS = new Uint8ClampedArray(1536 * 1024 * 4);
for (let offset = 3; offset < TRANSPARENT_PIXELS.length; offset += 4) TRANSPARENT_PIXELS[offset] = 255;

class Element {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.nodeType = 1;
    this.attributes = new Map();
    this.dataset = {};
    this.style = {
      cssText: '', properties: new Map(),
      setProperty(name, value) { this.properties.set(name, String(value)); },
      getPropertyValue(name) { return this.properties.get(name) || ''; },
    };
    this.children = [];
    this.listeners = new Map();
    this.hidden = false;
    this.disabled = false;
    this.value = '';
    this.className = '';
    this.classList = {
      values: new Set(),
      add: (...names) => names.forEach(name => this.classList.values.add(name)),
      remove: (...names) => names.forEach(name => this.classList.values.delete(name)),
      contains: name => this.classList.values.has(name),
    };
  }
  get childNodes() { return this.children; }
  get firstChild() { return this.children[0] || null; }
  setAttribute(name, value) {
    const text = String(value);
    this.attributes.set(name, text);
    if (name.startsWith('data-')) {
      const key = name.slice(5).replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
      this.dataset[key] = text;
    }
  }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  insertBefore(child, before) {
    const index = this.children.indexOf(before);
    if (index < 0) return this.appendChild(child);
    this.children.splice(index, 0, child); child.parentNode = this; return child;
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parentNode = null;
    this.children = [];
    this.append(...children);
  }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(listener);
  }
  removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
  dispatch(type, event = {}) {
    for (const listener of this.listeners.get(type) ?? []) listener({ target: this, ...event });
  }
  click() { if (!this.disabled) this.dispatch('click'); }
  remove() {
    this.removed = true;
    this.parentNode?.children && (this.parentNode.children = this.parentNode.children.filter(child => child !== this));
    this.parentNode = null;
  }
  matches(selector) {
    const tagAndData = /^([a-z]+)?\[data-([a-z0-9-]+)\]$/i.exec(selector);
    if (tagAndData) {
      const key = tagAndData[2].replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
      return (!tagAndData[1] || this.tagName === tagAndData[1].toUpperCase())
        && Object.hasOwn(this.dataset, key);
    }
    const data = /^\[data-([a-z0-9-]+)\]$/i.exec(selector);
    if (data) {
      const key = data[1].replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
      return Object.hasOwn(this.dataset, key);
    }
    return selector.toLowerCase() === this.tagName.toLowerCase();
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const found = [];
    const visit = parent => {
      for (const child of parent.children) {
        if (child.matches?.(selector)) found.push(child);
        if (Array.isArray(child.children)) visit(child);
      }
    };
    visit(this);
    return found;
  }
  getBoundingClientRect() { return this.rect || { width: 1280, height: 800 }; }
}

function createFixture({ intent = 'preview', assets, localization = true, settings = true,
  failCanvas = false, resizeObserverFallback = false, reducedMotion = false,
  makeBitmap = true, bitmapMode = 'ok', imageOptions = {}, native = false, nativeMode,
  existingStage = true, rootWidth = 1280, rootHeight = 800, failShowModal = false,
  noResizeObserver = false, noMatchMedia = false, legacyMedia = false,
  backgroundResult, throwBackground = false, settingsCommitted = false, skipInstall = false,
  settingsAdapter = null,
  theme = 'dark' } = {}) {
  const raf = new Map();
  const timers = new Map();
  const windowListeners = new Map();
  const mediaListeners = new Set();
  const resizeObservers = [];
  const bitmapPromises = [];
  const pendingDecodes = [];
  const images = [];
  const drawnTexts = { identity: [], stage: [] };
  let bitmapCallCount = 0;
  const messages = [];
  let nextId = 1;
  let now = 0;
  let imageIndex = 0;
  const root = new Element('section');
  root.rect = { width: rootWidth, height: rootHeight };
  root.setAttribute('data-agent-skin-stage', '');
  const timeline = new Element('input'); timeline.id = 'timeline'; timeline.value = '0';
  const controls = new Element('div'); controls.id = 'preview-controls';
  const pause = new Element('button'); pause.id = 'pause';
  const replay = new Element('button'); replay.id = 'replay';
  const elapsed = new Element('span'); elapsed.id = 'elapsed';
  const preexisting = [timeline, controls, pause, replay, elapsed];
  const documentRoot = new Element('html');
  documentRoot.dataset.theme = theme;
  const body = new Element('body');
  const document = {
    documentElement: documentRoot, body, title: 'Local preview', activeElement: null,
    createTextNode(value) { return { nodeType: 3, nodeValue: String(value), parentNode: null }; },
    createElement(tagName) {
      if (tagName === 'canvas') {
        const element = new Element('canvas');
        element.width = 0; element.height = 0;
        element.getContext = () => failCanvas ? null : context2d(element);
        return element;
      }
      const element = new Element(tagName);
      if (tagName === 'dialog') {
        element.showModal = () => { if (failShowModal) throw new Error('dialog unavailable'); element.open = true; };
        element.close = () => { element.open = false; };
      }
      return element;
    },
    querySelector(selector) { return selector === '[data-agent-skin-stage]' && existingStage ? root : null; },
    getElementById(id) { return preexisting.find(element => element.id === id) ?? null; },
  };
  const context2d = canvas => ({
    canvas, globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1,
    save() {}, restore() {}, setTransform() {}, clearRect() {}, fillRect() {},
    beginPath() {}, arc() {}, stroke() {}, fill() {}, clip() {}, drawImage() {},
    translate() {}, rotate() {}, moveTo() {}, lineTo() {},
    strokeText() {}, measureText(value) {
      const pixels = Number(/(\d+(?:\.\d+)?)px/.exec(this.font)?.[1] || 16);
      return { width: String(value).length * pixels * 0.6 };
    },
    getImageData() { return { data: TRANSPARENT_PIXELS }; },
    fillText(value) {
      const destination = canvas.width === 1536 && canvas.height === 1024
        ? drawnTexts.identity : drawnTexts.stage;
      destination.push(String(value));
    },
  });
  for (const element of preexisting) document.body.appendChild(element);
  if (existingStage) document.body.appendChild(root);
  const matchMedia = query => {
    const listeners = new Set();
    const result = {
      media: query, matches: query.includes('prefers-reduced-motion') ? reducedMotion : true,
      listenerCount() { return listeners.size; },
      dispatch(matches) { result.matches = matches; for (const listener of listeners) listener({ matches }); },
    };
    if (legacyMedia) {
      result.addListener = listener => listeners.add(listener);
      result.removeListener = listener => listeners.delete(listener);
    } else {
      result.addEventListener = (_type, listener) => listeners.add(listener);
      result.removeEventListener = (_type, listener) => listeners.delete(listener);
    }
    mediaListeners.add(result);
    return result;
  };
  const window = {
    navigator: { language: 'en-US' }, Float32Array,
    innerWidth: 1280, innerHeight: 800, devicePixelRatio: 1,
    CSS: { supports: (_kind, value) => !/[;{}]/.test(value) && !value.includes('bogus') },
    visualViewport: { addEventListener() {}, removeEventListener() {} },
    addEventListener(type, listener) {
      if (!windowListeners.has(type)) windowListeners.set(type, new Set());
      windowListeners.get(type).add(listener);
    },
    removeEventListener(type, listener) { windowListeners.get(type)?.delete(listener); },
    ResizeObserver: noResizeObserver ? undefined : class {
      constructor(callback) { this.callback = callback; resizeObservers.push(this); }
      observe(_node, options) {
        if (resizeObserverFallback && options?.box) throw new Error('unsupported observe option');
      }
      disconnect() { this.disconnected = true; }
      trigger() { this.callback(); }
    },
    matchMedia: noMatchMedia ? undefined : matchMedia,
    createImageBitmap: makeBitmap ? async canvas => {
      const index = bitmapCallCount++;
      if (bitmapMode === 'throw') throw new Error('bitmap unavailable');
      if (bitmapMode === 'pending') return new Promise((resolve, reject) => bitmapPromises.push({ resolve, reject, canvas }));
      if (bitmapMode === 'second-reject' && index === 1) throw new Error('second bitmap failed');
      return { source: canvas, closed: false, close() { this.closed = true; } };
    } : undefined,
    location: new URL('file:///tmp/preview.html'),
  };
  if (native) {
    window.webkit = { messageHandlers: { launcher: { postMessage: message => messages.push(message) } } };
    window.__agentSkinNativeMode = nativeMode;
  }
  class ImageMock {
    constructor() {
      const index = imageIndex++;
      this.naturalWidth = index % 2 === 0 ? 512 : 1536;
      this.naturalHeight = index % 2 === 0 ? 512 : 1024;
      this.complete = false;
      this.onerror = null;
      this.onload = null;
      this.options = imageOptions;
      this.index = index;
      images.push(this);
      if (imageOptions.noDecode) this.decode = undefined;
    }
    decode() {
      if (imageOptions.pendingAfterInitial && this.index >= 2 || imageOptions.decode === 'pending') {
        return new Promise((resolve, reject) => pendingDecodes.push({ resolve, reject, image: this }));
      }
      if (imageOptions.decode === 'reject') return Promise.reject(new Error('native decoder details'));
      if (imageOptions.wrongDimensions) this.naturalWidth--;
      this.complete = true;
      return Promise.resolve();
    }
    set src(value) {
      this._src = value;
      if (!value) this.complete = false;
      else if (imageOptions.noDecode) queueMicrotask(() => this.onload?.());
    }
    get src() { return this._src; }
  }
  const fakeURL = {
    createObjectURL: () => `blob:animation-${nextId++}`,
    revokeObjectURL() {},
  };
  const environment = {
    document, Image: ImageMock, URL: fakeURL, indexedDB: undefined,
    performance: { now: () => now },
    setTimeout(callback, delay) { const id = nextId++; timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
  };
  const requestAnimationFrame = callback => { const id = nextId++; raf.set(id, callback); return id; };
  const cancelAnimationFrame = id => raf.delete(id);
  class Path2DMock {
    constructor() { this.commands = []; }
    moveTo(x, y) { this.commands.push(['M', x, y]); }
    lineTo(x, y) { this.commands.push(['L', x, y]); }
  }
  const payload = assets || {
    avatar: 'data:image/png;base64,AA==', artwork: 'data:image/png;base64,AA==',
    contours: [[[10, 10], [40, 20], [80, 15], [110, 45]]],
  };
  let resolveReady;
  const ready = new Promise(resolve => { resolveReady = resolve; });
  const send = message => {
    messages.push(message);
    if (message.action === 'ready') resolveReady(message);
    if (message.action === 'background' && backgroundResult) return backgroundResult();
    if (message.action === 'background' && throwBackground) throw new Error('wallpaper adapter failed');
    return undefined;
  };
  let settingsInstance = null;
  const settingsFactory = settingsAdapter ? () => {
    settingsInstance = settingsAdapter;
    return settingsInstance;
  } : settings ? options => {
    settingsInstance = imageSettingsContext.createImageSettings(options);
    return settingsInstance;
  } : undefined;
  const localizationFactory = localization === 'throw' ? () => { throw new Error('locale setup failed'); }
    : localization ? options => localizationContext.createLocalization(options) : undefined;
  const handle = skipInstall ? null : installAnimation(
    window, document, window.location, environment.performance, undefined, ImageMock, Path2DMock,
    fakeURL, requestAnimationFrame, cancelAnimationFrame,
    environment.setTimeout, environment.clearTimeout, undefined, send,
    { runId: 'unit-run', intent, assets: payload, settingsCommitted }, settingsFactory, localizationFactory,
  );
  Object.assign(window, {
    document, Image: ImageMock, Path2D: Path2DMock, URL: fakeURL, indexedDB: undefined,
    performance: environment.performance,
    requestAnimationFrame, cancelAnimationFrame,
    setTimeout: environment.setTimeout, clearTimeout: environment.clearTimeout,
    createImageSettings: settingsFactory, createLocalization: localizationFactory,
    AGENT_SKIN_ASSETS: payload,
  });
  function flushFrame(timestamp) {
    now = timestamp;
    const entry = raf.entries().next().value;
    if (!entry) return false;
    raf.delete(entry[0]);
    entry[1](timestamp);
    return true;
  }
  function dispatchWindow(type, event) {
    for (const listener of windowListeners.get(type) ?? []) listener(event);
  }
  return { handle, get root() { return document.body.querySelector('[data-agent-skin-stage]') || root; }, timeline, pause, replay, elapsed, controls, body, document,
    window, timers, raf, messages, mediaListeners, resizeObservers, bitmapPromises, pendingDecodes, images, resolveReady,
    ImageMock, Path2DMock, environment, payload, settingsFactory, settingsInstance, localizationFactory,
    ready, flushFrame, dispatchWindow, drawnTexts, setNow(value) { now = value; } };
}

async function waitReady(fixture) {
  await new Promise(resolve => setImmediate(resolve));
  const failed = fixture.messages.find(message => message.action === 'assetError');
  if (failed) throw new Error(`animation failed to mount or prepare: ${JSON.stringify(failed)}`);
  await Promise.race([fixture.ready, new Promise((_, reject) => setTimeout(() => reject(new Error('animation did not become ready')), 2500))]);
}

async function waitForMessage(fixture, action) {
  for (let attempt = 0; attempt < 20; attempt++) {
    const message = fixture.messages.find(item => item.action === action);
    if (message) return message;
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.fail(`animation did not send ${action}`);
}

function makePNGFile() {
  const signature = Uint8Array.of(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a);
  return { size: 64, type: 'image/png', slice(start, end) {
    return { async arrayBuffer() {
      const bytes = signature.slice(start, end);
      return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    } };
  } };
}

test('the preview API prepares valid artwork, draws every phase, reacts to appearance, and releases on replay and skip', async () => {
  const fixture = createFixture({ resizeObserverFallback: true });
  await waitReady(fixture);
  assert.equal(fixture.messages[0].action, 'ready');
  assert.equal(fixture.handle.preview.report().stage, 'pulse');
  assert.ok(fixture.handle.preview.report().resources.liveBitmaps > 0);
  fixture.handle.preview.waiting();
  assert.equal(fixture.handle.openSettings(), false, 'preview does not open the saved-settings dialog');

  for (const [seconds, phase] of [
    [2, 'identity'], [4.5, 'dispersing'], [4.9, 'scattered'], [6, 'drawing'],
    [7.3, 'colorize'], [8, 'portrait'], [11.5, 'shutter'],
  ]) {
    assert.equal(fixture.handle.preview.seek(seconds), true);
    assert.equal(fixture.handle.preview.report().stage, phase);
  }
  fixture.handle.preview.setReduced(true);
  for (const [seconds, phase] of [
    [1, 'pulse'], [4.4, 'dispersing'], [4.9, 'scattered'], [6, 'drawing'],
    [7.3, 'colorize'], [8, 'portrait'], [11.5, 'shutter'],
  ]) {
    fixture.handle.preview.seek(seconds);
    assert.equal(fixture.handle.preview.report().stage, phase);
  }
  fixture.handle.preview.setReduced(false);
  assert.equal(fixture.handle.updateAppearance(null), false);
  assert.equal(fixture.handle.updateAppearance({}), true);
  fixture.handle.updateAppearance({ locale: 'zh-CN', theme: 'light', colors: {
    surface: '#fdfdfd', text: '#222', muted: 'bogus', border: 'var(--line)',
  } });
  assert.equal(fixture.document.documentElement.lang, 'zh-CN');
  assert.equal(fixture.document.documentElement.dataset.theme, 'light');
  assert.equal(fixture.document.documentElement.style.getPropertyValue('--agent-skin-surface'), '#fdfdfd');
  assert.notEqual(fixture.document.documentElement.style.getPropertyValue('--agent-skin-muted'), 'bogus');

  fixture.timeline.value = '6';
  fixture.timeline.dispatch('input');
  assert.equal(fixture.handle.preview.report().stage, 'drawing');
  fixture.pause.click();
  fixture.pause.click();
  fixture.handle.preview.seek(2);
  fixture.handle.preview.pause();
  fixture.handle.preview.resume();
  fixture.dispatchWindow('keydown', {
    key: ' ', code: 'Space', target: { tagName: 'DIV' }, preventDefault() { this.prevented = true; },
  });
  fixture.dispatchWindow('keydown', { key: 'Space', code: 'Space', target: { tagName: 'INPUT' }, preventDefault() { this.prevented = true; } });
  for (const query of fixture.mediaListeners) if (query.media.includes('prefers-reduced-motion')) query.dispatch(true);
  fixture.handle.preview.beginLaunch();
  assert.equal(fixture.body.classList.contains('agent-skin-native-launch'), true);
  fixture.handle.preview.promoteLaunch();
  fixture.handle.preview.error('fixture-safe detail');
  assert.equal(fixture.root.querySelector('[data-agent-skin-error-body]').textContent, 'fixture-safe detail');
  fixture.handle.preview.report();

  assert.equal(fixture.handle.preview.replay(), true);
  await waitForMessage(fixture, 'ready');
  for (let attempt = 0; attempt < 20 && fixture.root.dataset.prewarmed !== 'true'; attempt++) {
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.equal(fixture.root.dataset.prewarmed, 'true');
  fixture.handle.preview.skip();
  assert.equal(fixture.handle.preview.report().completed, true);
  assert.equal(fixture.handle.preview.report().skipped, true);
  assert.equal(fixture.messages.filter(item => item.action === 'complete').length, 1);
  assert.equal(fixture.handle.dispose(), true);
  assert.equal(fixture.handle.dispose(), false);
  assert.equal(fixture.handle.preview.report().resources.liveRAF, 0);
});

test('playing completes naturally and keyboard shortcuts skip only a supported preview target', async () => {
  const fixture = createFixture({ intent: 'play', settings: false, makeBitmap: false });
  await waitReady(fixture);
  assert.equal(fixture.handle.preview.report().resources.liveImages, 2);
  assert.equal(fixture.handle.preview.report().resources.liveBitmaps, 0);
  assert.equal(fixture.flushFrame(100), true);
  assert.equal(fixture.flushFrame(13000), true);
  assert.equal(fixture.handle.preview.report().completed, true);
  assert.equal(fixture.handle.preview.report().skipped, false);
  assert.equal(fixture.messages.some(item => item.action === 'background'), true);

  const preview = createFixture({ native: true, nativeMode: 'preview', settings: false });
  await waitReady(preview);
  assert.equal(preview.handle.preview.report().resources.liveRAF, 0, 'native preview waits for explicit playback');
  preview.handle.preview.beginLaunch();
  preview.dispatchWindow('keydown', {
    key: 'Escape', preventDefault() { this.prevented = true; },
  });
  assert.equal(preview.handle.preview.report().skipped, true);
  assert.equal(preview.handle.dispose(), true);
});

test('startup failures send a fixed asset reason and partial mounts are cleaned up', async () => {
  const invalid = createFixture({ assets: { avatar: 'invalid', artwork: 'invalid', contours: [] }, settings: false });
  await waitForMessage(invalid, 'assetError');
  assert.deepEqual({ ...invalid.messages.find(item => item.action === 'assetError') }, {
    type: 'azhou-startup', action: 'assetError', runId: 'unit-run', reason: 'asset-invalid',
  });
  assert.equal(invalid.handle.dispose(), true);

  const wrongImage = createFixture({ settings: false, imageOptions: { decode: 'reject' } });
  await waitForMessage(wrongImage, 'assetError');
  assert.equal(wrongImage.messages.find(item => item.action === 'assetError').reason, 'asset-invalid');

  const badCanvas = createFixture({ failCanvas: true, settings: false });
  assert.equal(badCanvas.messages[0].action, 'assetError');
  assert.equal(badCanvas.messages[0].reason, 'asset-invalid');
  assert.equal(badCanvas.handle.dispose(), false);

  const noLocalization = createFixture({ localization: false, settings: false });
  assert.equal(noLocalization.messages[0].action, 'assetError');
  assert.equal(noLocalization.messages[0].reason, 'localization-unavailable');
  assert.equal(noLocalization.handle.dispose(), false);
});

test('settings intent opens through the real settings panel and Escape cancels playback safely', async () => {
  const fixture = createFixture({ intent: 'settings', settings: true });
  await waitReady(fixture);
  assert.equal(fixture.document.body.querySelector('dialog')?.open, true);
  assert.equal(fixture.handle.openSettings(), false, 'an already open settings panel cannot open twice');
  let prevented = false;
  fixture.dispatchWindow('keydown', { key: 'Escape', preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(fixture.handle.preview.report().completed, true);
  assert.equal(fixture.handle.preview.report().skipped, true);
  assert.equal(fixture.messages.some(message => message.action === 'complete'), true);
  fixture.handle.dispose();
});

test('busy image import keeps settings open when Escape is pressed', async () => {
  const fixture = createFixture({ intent: 'settings', settings: true,
    imageOptions: { pendingAfterInitial: true } });
  await waitReady(fixture);
  const input = fixture.document.body.querySelectorAll('input')
    .find(element => element.getAttribute('data-agent-skin-image-input') === 'avatar');
  assert.ok(input);
  input.files = [makePNGFile()];
  input.dispatch('change');
  let prevented = false;
  let stopped = false;
  fixture.dispatchWindow('keydown', {
    key: 'Escape', preventDefault() { prevented = true; }, stopImmediatePropagation() { stopped = true; },
  });
  assert.equal(prevented, true);
  assert.equal(stopped, true);
  assert.equal(fixture.document.body.querySelector('dialog')?.open, true);
  fixture.handle.dispose();
});

test('a failed dialog mount resumes playback and a committed wallpaper failure gets a localized notice', async () => {
  const failedDialog = createFixture({ intent: 'play', settings: true, failShowModal: true });
  await waitReady(failedDialog);
  assert.equal(failedDialog.handle.openSettings(), false);
  assert.equal(failedDialog.handle.preview.report().resources.liveRAF, 1);
  failedDialog.handle.dispose();

  const failedWallpaper = createFixture({ intent: 'play', settings: false, settingsCommitted: true,
    backgroundResult: () => Promise.resolve({ applied: false, reason: 'styles-not-effective' }) });
  await waitReady(failedWallpaper);
  for (let attempt = 0; attempt < 10 && !failedWallpaper.root.querySelector('[data-agent-skin-wallpaper-result]'); attempt++) {
    await new Promise(resolve => setImmediate(resolve));
  }
  const notice = failedWallpaper.root.querySelector('[data-agent-skin-wallpaper-result]');
  assert.ok(notice);
  assert.ok(notice.querySelector('[data-agent-skin-wallpaper-title]'));
  failedWallpaper.handle.updateAppearance({ theme: 'light' });
  assert.ok(notice.querySelector('[data-agent-skin-wallpaper-body]'));
  failedWallpaper.handle.dispose();
});

test('the local preview adapter uses its own browser bindings and preserves the configured preview API', async () => {
  const fixture = createFixture({ skipInstall: true, existingStage: false, settings: false });
  const previewContext = vm.createContext({ window: fixture.window, document: fixture.document });
  new vm.Script(source, { filename: SOURCE_PATH }).runInContext(previewContext);
  for (let attempt = 0; attempt < 30 && fixture.document.body.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed !== 'true'; attempt++) {
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.equal(typeof fixture.window.launcherUI?.seek, 'function');
  assert.equal(fixture.document.body.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed, 'true');
  assert.equal(fixture.window.launcherUI.seek(7.3), true);
  assert.equal(fixture.window.launcherUI.report().stage, 'colorize');
  assert.equal(fixture.window.launcherUI.dispose(), true);
});

test('narrow layouts preserve long localized copy and rebind legacy media listeners', async () => {
  const title = '阿舟实验室'.repeat(12);
  const caption = `${'阿舟'.repeat(13)}，${'继续观察系统如何把每个真实过程整理成可复用经验'.repeat(3)}`;
  const subtitle = `${'一起把过程整理'.repeat(5)}，留给后来者继续使用`;
  const fixture = createFixture({ rootWidth: 400, rootHeight: 800, theme: 'light', legacyMedia: true,
    assets: { avatar: 'data:image/png;base64,AA==', artwork: 'data:image/png;base64,AA==',
      contours: [[[0, 0], [2, 0], { x: 50, y: 0 }, { x: 80, y: 0 }]],
      introTitle: title, introCaption: caption, artworkSubtitle: subtitle } });
  await waitReady(fixture);

  const titleIndex = fixture.drawnTexts.identity.indexOf(title);
  assert.notEqual(titleIndex, -1, 'the identity canvas receives the full configured title');
  assert.ok(fixture.drawnTexts.identity.slice(titleIndex + 1).join('').startsWith(caption),
    'wrapped caption lines preserve punctuation and every source character');
  assert.equal(fixture.document.documentElement.dataset.theme, 'light');
  fixture.handle.preview.seek(8);
  assert.equal(fixture.handle.preview.report().stage, 'portrait');
  assert.ok(fixture.drawnTexts.stage.join('').includes(subtitle), 'narrow portrait layout keeps all subtitle text');
  fixture.handle.updateAppearance({ reducedMotion: true });
  assert.equal(fixture.handle.preview.report().reduced, true);

  const motionQuery = [...fixture.mediaListeners].find(query => query.media.includes('prefers-reduced-motion'));
  const oldRatioQuery = [...fixture.mediaListeners].find(query => query.media.includes('resolution:'));
  assert.equal(motionQuery.listenerCount(), 1);
  assert.equal(oldRatioQuery.listenerCount(), 1);
  fixture.window.devicePixelRatio = 2;
  oldRatioQuery.dispatch(false);
  assert.equal(oldRatioQuery.listenerCount(), 0, 'the previous resolution listener is detached');
  const newRatioQuery = [...fixture.mediaListeners].find(query => query.media.includes('resolution: 2dppx'));
  assert.equal(newRatioQuery.listenerCount(), 1, 'the new device pixel ratio is observed');
  motionQuery.dispatch(false);
  assert.equal(fixture.handle.preview.report().reduced, false);
  fixture.handle.dispose();
  assert.equal(motionQuery.listenerCount(), 0);
  assert.equal(newRatioQuery.listenerCount(), 0);
});

test('an unavailable saved-settings store falls back to defaults and shows only a safe notice', async () => {
  const fixture = createFixture();
  fixture.settingsInstance.load = async () => { throw new Error('private database details'); };
  await waitReady(fixture);
  const notice = fixture.root.querySelector('[data-agent-skin-settings-result]');
  assert.ok(notice);
  assert.equal(notice.textContent,
    'Saved settings are temporarily unavailable. Defaults are in use; the record was kept.');
  assert.equal(notice.textContent.includes('private database details'), false);
  fixture.handle.updateAppearance({ locale: 'zh-CN' });
  assert.equal(notice.textContent, '暂时无法读取保存设置；当前使用默认设置，原记录未删除。');
  fixture.handle.dispose();
});

test('a bitmap conversion failure releases decoded images and any earlier bitmap', async () => {
  const fixture = createFixture({ settings: false, bitmapMode: 'second-reject' });
  await waitForMessage(fixture, 'assetError');
  const resources = fixture.handle.preview.report().resources;
  assert.equal(fixture.messages.find(message => message.action === 'assetError').reason, 'asset-invalid');
  assert.equal(resources.createdBitmaps, 1);
  assert.equal(resources.releasedBitmaps, 1);
  assert.equal(resources.liveBitmaps, 0);
  assert.equal(resources.liveImages, 0);
  fixture.handle.dispose();
});

test('skip during prewarm invalidates pending image work without sending a late error', async () => {
  const fixture = createFixture({ settings: false, imageOptions: { decode: 'pending' } });
  for (let attempt = 0; attempt < 20 && fixture.pendingDecodes.length < 2; attempt++) {
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.equal(fixture.pendingDecodes.length, 2);
  assert.equal(fixture.handle.preview.skip(), undefined);
  assert.equal(fixture.handle.preview.report().completed, true);
  assert.equal(fixture.handle.preview.report().skipped, true);
  for (const pending of fixture.pendingDecodes) pending.resolve();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(fixture.messages.some(message => message.action === 'assetError'), false);
  assert.equal(fixture.messages.some(message => message.action === 'ready'), false);
  assert.equal(fixture.handle.preview.report().resources.liveImages, 0);
  fixture.handle.dispose();
});

test('the animation adapter reports a committed settings close and releases the old scene', async () => {
  let callbacks;
  const settingsAdapter = {
    async load(defaults) { return { settings: defaults, baseline: defaults }; },
    isSettingsOpen() { return false; },
    isBusy() { return false; },
    openSettings(options) { callbacks = options; options.onOpen(); return true; },
    dispose() {},
  };
  const fixture = createFixture({ intent: 'play', settingsAdapter });
  await waitReady(fixture);
  assert.equal(fixture.handle.openSettings(), true);
  assert.equal(fixture.messages.some(message => message.action === 'settings-open'), true);
  callbacks.onSaved();
  assert.equal(fixture.messages.some(message => message.action === 'settings-close'), true);
  assert.equal(fixture.handle.preview.report().resources.liveImages, 0);
  assert.equal(fixture.handle.preview.report().resources.liveBitmaps, 0);
  fixture.handle.dispose();
});

test('late identity bitmaps are closed after a resize or a seek makes them stale', async () => {
  const fixture = createFixture({ settings: false, bitmapMode: 'pending', rootWidth: 400, rootHeight: 800 });
  const waitForBitmaps = async count => {
    for (let attempt = 0; attempt < 30 && fixture.bitmapPromises.length < count; attempt++) {
      await new Promise(resolve => setImmediate(resolve));
    }
    assert.equal(fixture.bitmapPromises.length, count);
  };
  const resolveBitmap = pending => {
    const bitmap = { source: pending.canvas, closed: false, close() { this.closed = true; } };
    pending.resolve(bitmap);
    return bitmap;
  };

  await waitForBitmaps(2);
  resolveBitmap(fixture.bitmapPromises[0]);
  resolveBitmap(fixture.bitmapPromises[1]);
  await waitForBitmaps(3);
  const staleLayoutBitmap = fixture.bitmapPromises[2];
  fixture.root.rect = { width: 700, height: 800 };
  fixture.resizeObservers[0].trigger();
  const stale = resolveBitmap(staleLayoutBitmap);
  await waitForBitmaps(4);
  resolveBitmap(fixture.bitmapPromises[3]);
  await waitReady(fixture);
  assert.equal(stale.closed, true, 'a bitmap rendered for the previous viewport is released');

  fixture.handle.preview.seek(8);
  fixture.handle.preview.seek(2);
  await waitForBitmaps(5);
  const lateRestore = fixture.bitmapPromises[4];
  fixture.handle.preview.seek(6);
  const late = resolveBitmap(lateRestore);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(late.closed, true, 'a restored identity bitmap is closed after a later seek');
  fixture.handle.dispose();
});

test('image load fallback works without decode and bad decoded dimensions are released', async () => {
  const fallback = createFixture({ settings: false, imageOptions: { noDecode: true } });
  await waitReady(fallback);
  assert.equal(fallback.images.length, 2);
  assert.equal(fallback.handle.preview.report().resources.liveImages, 0);
  fallback.handle.dispose();

  const wrongDimensions = createFixture({ settings: false, imageOptions: { wrongDimensions: true } });
  await waitForMessage(wrongDimensions, 'assetError');
  assert.equal(wrongDimensions.messages.find(message => message.action === 'assetError').reason, 'asset-invalid');
  assert.equal(wrongDimensions.handle.preview.report().resources.liveImages, 0);
  wrongDimensions.handle.dispose();
});
