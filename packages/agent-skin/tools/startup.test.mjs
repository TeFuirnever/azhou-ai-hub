import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { createHash, webcrypto } from 'node:crypto';
import { runInNewContext } from 'node:vm';
import { installStartup } from '../extension/renderer.mjs';
import { createCodexPageAdapter } from '../extension/codex-page-adapter.mjs';
import { createDSHPageAdapter } from '../extension/hosts/dsh.mjs';
import { createWallpaperApplicator } from '../wallpaper/apply.js';
const pageAdapter = createCodexPageAdapter(globalThis);
const imageSettingsSource = readFileSync(new URL('../image-settings.js', import.meta.url), 'utf8');
const imageSettingsContext = {};
runInNewContext(`${imageSettingsSource}\nglobalThis.createImageSettings = createImageSettings;`, imageSettingsContext);
const createImageSettings = imageSettingsContext.createImageSettings;

const mainURL = 'app://-/index.html?initialRoute=%2F';

function controlledHost({ body = true } = {}) {
  const listeners = new Set();
  const keyListeners = new Set();
  const scrollListeners = new Set();
  const pageHideListeners = new Set();
  const pageShowListeners = new Set();
  const observers = [];
  const frames = [];
  const controls = [];
  const timers = [];
  let hostUIReady = true;
  const hostControl = {
    tagName: 'DIV', style: {}, hidden: false,
    getAttribute(name) { return name === 'role' ? 'textbox' : null; },
    matches(selector) { return selector.includes('[role="textbox"]'); },
    getBoundingClientRect() { return { left: 200, right: 500, width: 300, top: 680, bottom: 780, height: 100 }; },
  };
  const controlWrapper = {
    style: { opacity: '1' },
    getBoundingClientRect() { return { left: 200, right: 800, width: 600, top: 600, bottom: 790, height: 190 }; },
    querySelector(selector) { return selector.includes('[role="textbox"]') ? hostControl : null; },
  };
  const appRoot = {
    style: {},
    getBoundingClientRect() { return { left: 0, right: 1024, width: 1024, top: 0, bottom: 800, height: 800 }; },
    querySelectorAll() { return hostUIReady ? [hostControl] : []; },
  };
  controlWrapper.parentNode = appRoot;
  hostControl.parentNode = controlWrapper;
  const documentElement = {
    children: [],
    appendChild(node) {
      if (node.parentNode?.removeChild) node.parentNode.removeChild(node);
      if (node.contentWindow) frames.push(node);
      node.parentNode = this;
      this.children.push(node);
      return node;
    },
    insertBefore(node, reference) {
      if (node.parentNode?.removeChild) node.parentNode.removeChild(node);
      const index = reference == null ? this.children.length : this.children.indexOf(reference);
      this.children.splice(index, 0, node);
      node.parentNode = this;
      return node;
    },
    removeChild(node) {
      const index = this.children.indexOf(node);
      if (index >= 0) this.children.splice(index, 1);
      node.parentNode = null;
      return node;
    },
  };
  const document = {
    documentElement,
    querySelectorAll: () => [],
    getElementById(id) { return id === 'root' ? appRoot : null; },
    activeElement: null,
    hasFocus: () => true,
    createElement(tag) {
      if (tag !== 'iframe') {
        const events = new Map();
        const node = {
          tagName: tag, style: {}, hidden: false, children: [], attributes: new Map(),
          setAttribute(name, value) { this.attributes.set(name, value); },
          appendChild(child) { this.children.push(child); return child; },
          attachShadow() { this.shadowRoot = { appendChild: child => this.appendChild(child) }; return this.shadowRoot; },
          addEventListener(type, listener) { events.set(type, listener); },
          removeEventListener(type) { events.delete(type); },
          click() { if (!this.disabled) events.get('click')?.(); },
          focus() { document.activeElement = this; },
          remove() { this.parentNode?.removeChild?.(this); this.removed = true; },
        };
        controls.push(node);
        return node;
      }
      assert.equal(tag, 'iframe');
      const callbacks = [];
      const frameListeners = new Map();
      const contentWindow = {
        location: new URL('about:blank'),
        performance: { now: () => 0 },
        indexedDB: {},
        Image: class Image {},
        Path2D: class Path2D {},
        URL,
        document: { documentElement: {}, activeElement: null },
        requestAnimationFrame(callback) { callbacks.push(callback); return callbacks.length; },
        cancelAnimationFrame(id) { callbacks[id - 1] = null; },
        setTimeout(callback, delay) { return { callback, delay }; },
        clearTimeout(timer) { timer.cleared = true; },
        addEventListener(type, listener) {
          if (!frameListeners.has(type)) frameListeners.set(type, new Set());
          frameListeners.get(type).add(listener);
        },
        removeEventListener(type, listener) { frameListeners.get(type)?.delete(listener); },
        dispatch(type, event) { for (const listener of frameListeners.get(type) ?? []) listener(event); },
        evalCalls: 0,
        eval() { this.evalCalls += 1; throw new Error('iframe eval must not be used'); },
        flushAnimationFrame() { callbacks.shift()?.(0); },
      };
      contentWindow.window = contentWindow;
      contentWindow.self = contentWindow;
      const attributes = new Map();
      const frame = {
        attributes,
        style: { cssText: '' },
        contentWindow,
        src: '',
        removed: false,
        setAttribute(name, value) { attributes.set(name, value); },
        addEventListener() {},
        remove() { this.removed = true; this.parentNode = null; },
      };
      return frame;
    },
  };
  if (body) document.body = {};

  const host = {
    location: new URL(mainURL),
    document,
    CSS: { supports: (kind, value) => kind === 'color'
      && /^(?:#[\da-f]{3,8}|(?:rgb|rgba|hsl|hsla)\([^)]*\)|transparent|currentcolor)$/i.test(String(value).trim()) },
    getComputedStyle(node) { return node.computedStyle ?? node.style ?? {}; },
    MutationObserver: class MutationObserver {
      constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
      observe(_target, options) { this.observing = true; this.options = options; }
      disconnect() { this.disconnected = true; this.observing = false; }
      trigger(records = []) { if (this.observing) this.callback(records); }
    },
    addEventListener(type, listener) {
      if (type === 'message') listeners.add(listener);
      if (type === 'keydown') keyListeners.add(listener);
      if (type === 'scroll') scrollListeners.add(listener);
      if (type === 'pagehide') pageHideListeners.add(listener);
      if (type === 'pageshow') pageShowListeners.add(listener);
    },
    removeEventListener(type, listener) {
      if (type === 'message') listeners.delete(listener);
      if (type === 'keydown') keyListeners.delete(listener);
      if (type === 'scroll') scrollListeners.delete(listener);
      if (type === 'pagehide') pageHideListeners.delete(listener);
      if (type === 'pageshow') pageShowListeners.delete(listener);
    },
    send(data, source) {
      for (const listener of listeners) listener({ data, source });
    },
    keydown(event) { for (const listener of keyListeners) listener(event); },
    scroll() { for (const listener of scrollListeners) listener(); },
    pagehide() { for (const listener of pageHideListeners) listener(); },
    pageshow() { for (const listener of pageShowListeners) listener(); },
    setBody() {
      document.body = {};
      for (const observer of observers) observer.trigger();
    },
    setTimeout(callback, delay) {
      const timer = { callback, delay, cleared: false };
      timers.push(timer);
      return timer;
    },
    clearTimeout(timer) { timer.cleared = true; },
  };
  return { host, frames, controls, timers, observers, setBody: () => host.setBody(), listenerCount: () => listeners.size,
    keyListenerCount: () => keyListeners.size, scrollListenerCount: () => scrollListeners.size,
    pageHideListenerCount: () => pageHideListeners.size,
    pageShowListenerCount: () => pageShowListeners.size,
    appRoot, hostControl, controlWrapper,
    setHostUIReady(value) { hostUIReady = value; } };
}

function addAppearanceNavigation(fixture, { width = 220, count = 1, label = 'Your dot', layout = 'links' } = {}) {
  const rows = [];
  const createRow = (tagName, textContent, getWidth = () => width) => ({
    tagName,
    textContent,
    style: {},
    hidden: false,
    href: tagName === 'a' ? '/' : undefined,
    children: [],
    parentNode: null,
    get parentElement() { return this.parentNode; },
    get nextSibling() {
      const siblings = this.parentNode?.children ?? [];
      return siblings[siblings.indexOf(this) + 1] ?? null;
    },
    setAttribute(name, value) { (this.attributes ??= new Map()).set(name, value); },
    getAttribute(name) { return this.attributes?.get(name) ?? null; },
    closest(selector) {
      for (let node = this; node; node = node.parentNode) {
        if (selector === '[role="listitem"]' && node.getAttribute?.('role') === 'listitem') return node;
      }
      return null;
    },
    appendChild(child) { return this.insertBefore(child, null); },
    insertBefore(child, reference) {
      child.parentNode?.removeChild?.(child);
      const index = reference == null ? this.children.length : this.children.indexOf(reference);
      this.children.splice(index, 0, child);
      child.parentNode = this;
      return child;
    },
    removeChild(child) {
      const index = this.children.indexOf(child);
      if (index >= 0) this.children.splice(index, 1);
      child.parentNode = null;
      return child;
    },
    contains(node) { return this === node || this.children.some(child => child.contains?.(node)); },
    getBoundingClientRect() { const currentWidth = getWidth(); return { left: 0, right: currentWidth,
      width: currentWidth, height: 600, top: 0, bottom: 600 }; },
  });
  for (let index = 0; index < count; index += 1) {
    let navWidth = width;
    const nav = createRow('nav', undefined, () => navWidth);
    if (layout === 'home' || layout === 'wrapped') {
      nav.setAttribute('aria-label', 'Home');
      const header = createRow('div', undefined, () => navWidth);
      const navList = createRow('div', undefined, () => navWidth);
      navList.setAttribute('class', 'group/nav-list flex flex-col');
      const yourDot = createRow('button', label);
      let list, listItem;
      if (layout === 'wrapped') {
        list = createRow('div', undefined, () => navWidth); list.setAttribute('role', 'list');
        listItem = createRow('div', undefined, () => navWidth); listItem.setAttribute('role', 'listitem');
        const wrapper = createRow('div', undefined, () => navWidth);
        wrapper.appendChild(yourDot); listItem.appendChild(wrapper); list.appendChild(listItem); navList.appendChild(list);
      } else navList.appendChild(yourDot);
      header.appendChild(navList);
      nav.appendChild(header);
      const scrollContent = createRow('div', undefined, () => navWidth);
      const pinned = createRow('section', 'Pinned');
      const chatTitle = createRow('button', 'Your dot');
      scrollContent.appendChild(pinned);
      scrollContent.appendChild(chatTitle);
      nav.appendChild(scrollContent);
      rows.push({ nav, header, navList, yourDot, list, listItem, scrollContent, pinned, chatTitle,
        setWidth(value) { navWidth = value; } });
    } else {
      const yourDot = createRow('a', label);
      const pinned = createRow('a', 'Pinned');
      nav.appendChild(yourDot);
      nav.appendChild(pinned);
      rows.push({ nav, yourDot, pinned, setWidth(value) { navWidth = value; } });
    }
  }
  fixture.host.document.querySelectorAll = selector => {
    const matches = [];
    if (layout === 'home' || layout === 'wrapped') {
      if (selector.includes('[class~="group/nav-list"]')) matches.push(...rows.map(({ yourDot }) => yourDot));
      else if (selector.includes('nav button')) matches.push(...rows.flatMap(({ yourDot, chatTitle }) => [yourDot, chatTitle]));
    } else if (selector.includes('nav a[href]')) {
      matches.push(...rows.flatMap(({ yourDot, pinned }) => [yourDot, pinned]));
    }
    return matches.length ? matches : fixture.host.document.appearanceControls ?? [];
  };
  fixture.host.document.appearanceNavigation = rows;
  return rows;
}

function appearanceButton(fixture) {
  return fixture.controls.find(node => node.tagName === 'button');
}

function dshFixture({ body = true, gate = false, randomUUID = true } = {}) {
  const fixture = controlledHost({ body });
  const createElement = fixture.host.document.createElement;
  fixture.host.document.createElement = tag => {
    const element = createElement.call(fixture.host.document, tag);
    if (tag === 'iframe') element.ownerDocument = fixture.host.document;
    return element;
  };
  fixture.host.top = fixture.host;
  fixture.host.__ModuleLoader__ = { load() {} };
  fixture.host.__DSH_BOOT__ = { web: true };
  fixture.host.crypto = randomUUID ? { randomUUID: () => 'dsh-startup-test-document' } : {};
  fixture.host.getComputedStyle = () => ({ getPropertyValue: () => '' });
  const pageAdapter = createDSHPageAdapter(fixture.host, { sidebarEntry: false });
  let gatePhase = 'waiting';
  const expiryListeners = new Set();
  const expireGate = () => {
    if (['released', 'expired'].includes(gatePhase)) return false;
    gatePhase = 'expired';
    for (const listener of [...expiryListeners]) listener();
    expiryListeners.clear();
    return true;
  };
  const calls = { claims: 0, readies: 0, releases: 0, launches: 0, specs: [] };
  if (gate) {
    const startupGate = Object.freeze({
      owner: 'azhou-dsh-startup-gate-v1',
      claim() { calls.claims += 1; if (gatePhase !== 'waiting') return false; gatePhase = 'claimed'; return true; },
      ready() { calls.readies += 1; if (gatePhase !== 'claimed') return false; gatePhase = 'released'; expiryListeners.clear(); return true; },
      release() { calls.releases += 1; return expireGate(); },
      expire: expireGate,
      onExpire(listener) {
        if (typeof listener !== 'function') return () => false;
        if (gatePhase === 'expired') { listener(); return () => false; }
        if (gatePhase === 'released') return () => false;
        expiryListeners.add(listener);
        let active = true;
        return () => {
          if (!active) return false;
          active = false;
          return expiryListeners.delete(listener);
        };
      },
      status() { return gatePhase; },
    });
    Object.defineProperty(fixture.host, '__azhouDshStartupGate', { value: startupGate });
  }
  const payload = (...args) => {
    const send = args[13];
    const frameSpec = args[14];
    calls.specs.push(frameSpec);
    return { preview: { beginLaunch() { calls.launches += 1; return true; } } };
  };
  payload.assets = {};
  return {
    ...fixture, pageAdapter, payload, calls,
    gate: fixture.host.__azhouDshStartupGate,
    gatePhase: () => gatePhase,
    sendReady() {
      fixture.host.send({ type: 'azhou-startup', action: 'ready', runId: fixture.host.__azhouStartup.status().runId },
        fixture.frames.at(-1).contentWindow);
    },
  };
}

function dshSettingsStorage(record, { openFailure = false, holdFirstRead = false } = {}) {
  const state = { opens: [], transactions: [], requests: [], aborts: 0, releaseFirst: null };
  const database = {
    objectStoreNames: { contains(name) { return name === 'settings'; } },
    transaction(storeName, mode) {
      const transaction = {
        storeName, mode, aborted: false,
        objectStore(name) {
          assert.equal(name, 'settings');
          return { get(key) {
            const request = { result: record };
            state.requests.push({ key, request, transaction });
            let delivered = false;
            const deliver = () => {
              if (delivered) return;
              delivered = true;
              request.onsuccess?.();
              transaction.oncomplete?.();
            };
            if (holdFirstRead && state.requests.length === 1) state.releaseFirst = deliver;
            else queueMicrotask(deliver);
            return request;
          } };
        },
        abort() {
          if (this.aborted) return;
          this.aborted = true;
          state.aborts += 1;
          queueMicrotask(() => this.onabort?.());
        },
      };
      state.transactions.push(transaction);
      return transaction;
    },
    close() {},
  };
  const indexedDB = {
    open(name, version) {
      state.opens.push({ name, version });
      const request = {};
      queueMicrotask(() => {
        if (openFailure) {
          request.error = new Error('isolated storage failure');
          request.onerror?.();
        } else {
          request.result = database;
          request.onsuccess?.();
        }
      });
      return request;
    },
  };
  return { indexedDB, state };
}

const SAVED_DSH_IMAGE = 'data:image/png;base64,AA==';

function realDSHWallpaperFixture(options = {}) {
  const fixture = dshFixture({ gate: options.gate ?? false, randomUUID: false });
  const saved = { schemaVersion: 1, avatar: SAVED_DSH_IMAGE, artwork: SAVED_DSH_IMAGE,
    contours: [[[0, 0], [1, 1]]], introTitle: 'Saved title', introCaption: 'Saved caption',
    artworkSubtitle: 'Saved background', wallpaperStrength: options.wallpaperStrength ?? 31 };
  const storage = dshSettingsStorage(saved, options);
  const { host } = fixture;
  let imageIndex = 0;
  const entryStateListeners = new Set();
  const entryNotices = [];
  const basePageAdapter = fixture.pageAdapter;
  fixture.pageAdapter = {
    ...basePageAdapter,
    mountEntry(...args) {
      const entry = basePageAdapter.mountEntry(...args);
      return { ...entry, setWallpaperFailure(failure, announcementKey) {
        entry.setWallpaperFailure(failure, announcementKey);
        const notice = { failure: failure ? { ...failure } : null, announcementKey };
        entryNotices.push(notice);
        for (const listener of [...entryStateListeners]) listener(notice);
      } };
    },
  };
  host.indexedDB = storage.indexedDB;
  host.crypto = { subtle: webcrypto.subtle };
  host.atob = globalThis.atob;
  host.URL = URL;
  host.Image = class {
    constructor() { this.index = imageIndex++; }
    get naturalWidth() { return this.index % 2 === 0 ? 512 : 1536; }
    get naturalHeight() { return this.index % 2 === 0 ? 512 : 1024; }
    set src(value) {
      this.value = value;
      if (!value || value === 'data:,') return;
      queueMicrotask(() => { if (this.value === value) this.onload?.(); });
    }
    removeAttribute(name) { if (name === 'src') this.src = 'data:,'; }
  };
  host.AbortController = AbortController;
  host.performance = globalThis.performance;
  const mainSurface = { isConnected: true, closest: () => null };
  host.document.querySelectorAll = selector => selector === '[data-slot="main"]' ? [mainSurface] : [];
  const rendererCalls = [];
  const installRenderer = async offered => {
    rendererCalls.push({ image: offered.image, strength: offered.strength });
    if (options.failFirstApply && rendererCalls.length === 1) {
      return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-unsupported', imageDecoded: false };
    }
    const wallpaper = Object.freeze({ owner: 'azhou.dsh-startup-animation', version: '0.9.0',
      status: () => ({ applied: true, imageDecoded: true }), dispose() {} });
    Object.defineProperty(host, '__azhouWallpaper', { value: wallpaper,
      configurable: true, enumerable: false, writable: false });
    return { applied: true, imageDecoded: true };
  };
  fixture.payload.assets = { avatar: SAVED_DSH_IMAGE, artwork: SAVED_DSH_IMAGE,
    contours: [[[0, 0], [1, 1]]], introTitle: 'Default title', introCaption: 'Default caption',
    artworkSubtitle: 'Default background', wallpaperStrength: 42 };
  fixture.payload.createImageSettings = createImageSettings;
  fixture.payload.applyWallpaper = createWallpaperApplicator(installRenderer,
    { version: '0.9.0', css: '', pageAdapter: fixture.pageAdapter }, host);
  const waitForWallpaper = (api, predicate, message, timeoutMs = 5000) => {
    const current = () => api.status().wallpaper;
    const matches = () => predicate(current(), entryNotices.at(-1) ?? null);
    if (matches()) return Promise.resolve(current());
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error, wallpaper) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        entryStateListeners.delete(check);
        if (error) reject(error);
        else resolve(wallpaper);
      };
      const check = () => {
        try {
          const wallpaper = current();
          if (matches()) finish(null, wallpaper);
        } catch (error) { finish(error); }
      };
      const timer = setTimeout(() => finish(new Error(message)), timeoutMs);
      entryStateListeners.add(check);
      check();
    });
  };
  return { ...fixture, storage, rendererCalls, saved, entryNotices, waitForWallpaper };
}

async function waitForCondition(predicate, message) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.fail(message);
}

test('DSH without an early gate stays prepared, retains wallpaper and can open settings', () => {
  const fixture = dshFixture({ gate: false });
  Object.defineProperty(fixture.host, '__azhouWallpaper', { value: Object.freeze({
    owner: 'azhou.dsh-startup-animation', version: '0.9.0',
    status: () => ({ applied: true, imageDecoded: true }), dispose() {},
  }) });
  assert.deepEqual(installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated'),
    { installed: true, alreadyActive: false });
  const api = fixture.host.__azhouStartup;
  assert.equal(api.status().phase, 'prepared');
  assert.equal(api.status().overlay, false);
  assert.equal(fixture.frames.length, 0, 'no bridge means no autoplay overlay');
  assert.equal(api.status().wallpaper.applied, true, 'preexisting DSH wallpaper state survives preparation');
  assert.equal(api.openSettings(), true, 'settings remain available after gate fail-open');
  assert.equal(fixture.calls.specs.at(-1).externalStartGate, false, 'settings animation is not held behind startup gate');
  fixture.sendReady();
  assert.equal(api.status().phase, 'settings');
  assert.equal(fixture.calls.launches, 0, 'settings route does not invoke startup playback');
  api.dispose();
});

test('a DSH page without the gate reads its own saved wallpaper and applies it without autoplay', async () => {
  const fixture = realDSHWallpaperFixture();
  assert.equal(Object.hasOwn(fixture.host, '__azhouWallpaper'), false,
    'a new document starts without a preinstalled wallpaper controller');
  assert.deepEqual(installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated'),
    { installed: true, alreadyActive: false });
  const api = fixture.host.__azhouStartup;
  await fixture.waitForWallpaper(api, wallpaper => wallpaper.applied, 'saved DSH wallpaper was not applied');
  assert.deepEqual(fixture.storage.state.opens, [{ name: 'azhou-dsh-startup', version: 1 }]);
  assert.equal(fixture.storage.state.requests[0].key, 'images');
  assert.equal(fixture.storage.state.transactions[0].mode, 'readonly');
  assert.deepEqual(fixture.rendererCalls, [{ image: fixture.saved.artwork, strength: 31 }]);
  assert.equal(api.status().phase, 'prepared');
  assert.equal(api.status().wallpaper.applied, true);
  assert.equal(api.status().overlay, false);
  assert.equal(fixture.frames.length, 0, 'missing gate never starts the animation iframe');
  assert.equal(typeof fixture.pageAdapter.identify(fixture.host).documentToken, 'object',
    'the insecure HTTP path uses an in-memory document identity without randomUUID');
  api.dispose();
});

test('a claimed DSH gate timeout restores saved wallpaper while preserving the failed run', async () => {
  const fixture = realDSHWallpaperFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const frame = fixture.frames[0];
  assert.equal(fixture.calls.launches, 0);
  assert.equal(fixture.gatePhase(), 'claimed');

  assert.equal(fixture.gate.expire(), true);
  assert.equal(api.status().phase, 'failed');
  assert.equal(api.status().reason, 'startup-gate-expired');
  assert.equal(frame.removed, true, 'the stalled startup frame is gone before restoration begins');
  await fixture.waitForWallpaper(api, wallpaper => wallpaper.applied,
    'saved wallpaper did not restore after the gate timeout');

  const status = api.status();
  assert.equal(status.phase, 'failed', 'wallpaper restoration does not replace the failure terminal state');
  assert.equal(status.reason, 'startup-gate-expired');
  assert.equal(status.ready, false);
  assert.equal(status.wallpaper.applied, true);
  assert.deepEqual(fixture.rendererCalls, [{ image: fixture.saved.artwork, strength: 31 }]);
  assert.equal(fixture.calls.launches, 0, 'restoration does not replay the animation');
  api.dispose();
});

test('a DSH renderer timeout before ready restores saved wallpaper and keeps timeout terminal state', async () => {
  const fixture = realDSHWallpaperFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const frame = fixture.frames[0];
  const watchdog = fixture.timers.find(timer => timer.delay === 25_000);
  assert.ok(watchdog);
  watchdog.callback();
  assert.equal(api.status().phase, 'timeout');
  assert.equal(api.status().reason, 'overlay-timeout');
  assert.equal(frame.removed, true);

  await fixture.waitForWallpaper(api, wallpaper => wallpaper.applied,
    'saved wallpaper did not restore after the pre-ready renderer timeout');
  const status = api.status();
  assert.equal(status.phase, 'timeout');
  assert.equal(status.reason, 'overlay-timeout');
  assert.equal(status.ready, false);
  assert.equal(status.wallpaper.applied, true);
  assert.equal(fixture.calls.launches, 0);
  api.dispose();
});

test('a DSH asset error before ready restores saved wallpaper and preserves its failure reason', async () => {
  const fixture = realDSHWallpaperFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const frame = fixture.frames[0];
  fixture.host.send({ type: 'azhou-startup', action: 'assetError', reason: 'asset-invalid',
    runId: api.status().runId }, frame.contentWindow);

  await fixture.waitForWallpaper(api, wallpaper => wallpaper.applied,
    'saved wallpaper did not restore after the pre-ready asset error');
  const status = api.status();
  assert.equal(status.phase, 'failed');
  assert.equal(status.reason, 'asset-invalid');
  assert.equal(status.ready, false);
  assert.equal(status.wallpaper.applied, true);
  assert.equal(frame.removed, true);
  assert.equal(fixture.calls.launches, 0);
  api.dispose();
});

test('a DSH skip before ready restores saved wallpaper without changing skip completion', async () => {
  const fixture = realDSHWallpaperFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const frame = fixture.frames[0];
  fixture.host.send({ type: 'azhou-startup', action: 'complete', skipped: true,
    runId: api.status().runId }, frame.contentWindow);

  await fixture.waitForWallpaper(api, wallpaper => wallpaper.applied,
    'saved wallpaper did not restore after the pre-ready skip');
  const status = api.status();
  assert.equal(status.phase, 'complete');
  assert.equal(status.completion.cause, 'skip');
  assert.equal(status.completion.beforeReady, true);
  assert.equal(status.ready, false);
  assert.equal(status.wallpaper.applied, true);
  assert.equal(frame.removed, true);
  assert.equal(fixture.calls.launches, 0);
  api.dispose();
});

test('a DSH settings preview cancels pending recovery and wins over the late saved read', async () => {
  const fixture = realDSHWallpaperFixture({ gate: true, holdFirstRead: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const startupFrame = fixture.frames[0];
  fixture.host.send({ type: 'azhou-startup', action: 'complete', skipped: true,
    runId: api.status().runId }, startupFrame.contentWindow);
  await waitForCondition(() => typeof fixture.storage.state.releaseFirst === 'function',
    'early skip did not start the saved wallpaper read');

  const target = { children: [], appendChild(child) {
    child.parentNode = this; this.children.push(child); return child;
  }, removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    child.parentNode = null;
  } };
  const disposeSettings = api.mountSettings(target);
  assert.equal(typeof disposeSettings, 'function');
  assert.equal(fixture.storage.state.aborts, 1, 'opening settings cancels the pending saved-state read');
  const settingsFrame = target.children[0];
  const settingsRunId = fixture.calls.specs.at(-1).runId;
  fixture.host.send({ type: 'azhou-startup', action: 'background', runId: settingsRunId,
    image: fixture.saved.artwork, strength: 57 }, settingsFrame.contentWindow);
  await fixture.waitForWallpaper(api, wallpaper => wallpaper.applied,
    'the settings preview did not apply');
  fixture.storage.state.releaseFirst();
  await new Promise(resolve => setImmediate(resolve));

  assert.deepEqual(fixture.rendererCalls, [{ image: fixture.saved.artwork, strength: 57 }],
    'the cancelled recovery cannot overwrite the user preview');
  assert.equal(api.status().completion.cause, 'skip');
  assert.equal(api.status().wallpaper.applied, true);
  disposeSettings();
  api.dispose();
});

test('pagehide cancels a pending pre-ready DSH recovery before its saved read can write', async () => {
  const fixture = realDSHWallpaperFixture({ gate: true, holdFirstRead: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const frame = fixture.frames[0];
  fixture.host.send({ type: 'azhou-startup', action: 'complete', skipped: true,
    runId: api.status().runId }, frame.contentWindow);
  await waitForCondition(() => typeof fixture.storage.state.releaseFirst === 'function',
    'pre-ready skip did not start the wallpaper read');

  fixture.host.pagehide();
  assert.equal(fixture.storage.state.aborts, 1, 'pagehide aborts the recovery transaction');
  fixture.storage.state.releaseFirst();
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(fixture.rendererCalls.length, 0, 'the late saved result cannot write after pagehide');
  assert.equal(api.status().phase, 'complete');
  assert.equal(api.status().completion.cause, 'skip');
  api.dispose();
});

test('a disposed DSH recovery cannot overwrite the new page controller state', async () => {
  const fixture = realDSHWallpaperFixture({ gate: true, holdFirstRead: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const oldApi = fixture.host.__azhouStartup;
  const startupFrame = fixture.frames[0];
  fixture.host.send({ type: 'azhou-startup', action: 'complete', skipped: true,
    runId: oldApi.status().runId }, startupFrame.contentWindow);
  await waitForCondition(() => typeof fixture.storage.state.releaseFirst === 'function',
    'old page recovery did not start its settings read');

  oldApi.dispose();
  fixture.host.location = new URL('https://chat.deepseek.com/conversation/next');
  fixture.host.document = { ...fixture.host.document };
  const nextSettings = dshSettingsStorage({ ...fixture.saved, artwork: 'data:image/png;base64,Ag==', wallpaperStrength: 49 });
  fixture.host.indexedDB = nextSettings.indexedDB;
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const nextApi = fixture.host.__azhouStartup;
  await fixture.waitForWallpaper(nextApi, wallpaper => wallpaper.applied,
    'new page did not restore its own saved wallpaper');
  fixture.storage.state.releaseFirst();
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(nextApi.status().phase, 'prepared');
  assert.equal(nextApi.status().wallpaper.applied, true);
  assert.deepEqual(fixture.rendererCalls, [{ image: 'data:image/png;base64,Ag==', strength: 49 }],
    'the old page read cannot overwrite the new page settings');
  nextApi.dispose();
});

test('a saved disabled DSH wallpaper remains disabled without invoking the renderer', async () => {
  const fixture = realDSHWallpaperFixture({ wallpaperStrength: 0 });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  await waitForCondition(() => api.status().wallpaper.reason === 'disabled',
    'saved disabled wallpaper state was not restored');
  assert.equal(fixture.rendererCalls.length, 0);
  assert.equal(api.status().phase, 'prepared');
  assert.equal(api.status().overlay, false);
  assert.equal(fixture.frames.length, 0);
  api.dispose();
});

test('a settled DSH preparation failure is announced and can be retried without playback', async () => {
  const fixture = realDSHWallpaperFixture({ failFirstApply: true, holdFirstRead: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  await waitForCondition(() => typeof fixture.storage.state.releaseFirst === 'function',
    'the DSH preparation did not start its saved wallpaper read');

  const busy = await api.retryWallpaper();
  assert.equal(busy.reason, 'busy', 'an active preparation cannot race its wallpaper retry');
  assert.equal(api.status().phase, 'prepared');
  assert.equal(fixture.rendererCalls.length, 0);

  const failureNotice = fixture.waitForWallpaper(api, (_wallpaper, notice) =>
    notice?.failure?.failureCode === 'shell-unsupported', 'settled DSH failure was not announced');
  fixture.storage.state.releaseFirst();
  await failureNotice;
  assert.equal(api.status().wallpaper.failureCode, 'shell-unsupported');
  assert.equal(api.status().phase, 'prepared');
  assert.equal(fixture.frames.length, 0, 'wallpaper recovery does not start the animation');

  const retry = await api.retryWallpaper();
  assert.equal(retry.retried, true);
  assert.equal(retry.wallpaper.applied, true);
  assert.equal(api.status().phase, 'prepared');
  assert.equal(api.status().wallpaper.applied, true);
  assert.equal(fixture.rendererCalls.length, 2);
  assert.equal(fixture.calls.launches, 0);
  assert.deepEqual(fixture.entryNotices.at(-1), { failure: null, announcementKey: 'applied' });
  api.dispose();
});

test('DSH settings read failure is fail-open and leaves the host interactive', async () => {
  const fixture = realDSHWallpaperFixture({ openFailure: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  await waitForCondition(() => api.status().wallpaper.reason === 'storage-unavailable',
    'settings failure did not settle');
  assert.equal(fixture.rendererCalls.length, 0);
  assert.equal(api.status().phase, 'prepared');
  assert.equal(api.status().overlay, false);
  assert.equal(fixture.frames.length, 0);
  api.dispose();
});

test('DSH wallpaper restore has one deadline and ignores a storage result arriving after timeout', async () => {
  const fixture = realDSHWallpaperFixture({ holdFirstRead: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  await waitForCondition(() => typeof fixture.storage.state.releaseFirst === 'function',
    'isolated DSH settings read did not become pending');
  const deadline = fixture.timers.find(timer => timer.delay === 10_000 && !timer.cleared);
  assert.ok(deadline, 'the DSH restore owns a bounded deadline');
  deadline.callback();
  assert.equal(api.status().wallpaper.failureCode, 'retry-timeout');
  assert.equal(fixture.storage.state.aborts, 1, 'timeout disposes the outstanding DSH settings transaction');
  fixture.storage.state.releaseFirst();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(fixture.rendererCalls.length, 0, 'late settings cannot start wallpaper application');
  assert.equal(api.status().phase, 'prepared');
  assert.equal(api.status().overlay, false);
  assert.equal(fixture.frames.length, 0);
  assert.equal(fixture.timers.some(timer => !timer.cleared && [5_000, 10_000].includes(timer.delay)), false,
    'the read and owner deadlines are cleared');
  api.dispose();
});

test('opening settings cancels the DSH restore so a newer settings wallpaper wins', async () => {
  const fixture = realDSHWallpaperFixture({ holdFirstRead: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  await waitForCondition(() => typeof fixture.storage.state.releaseFirst === 'function',
    'isolated DSH settings read did not become pending');
  assert.equal(api.openSettings(), true);
  assert.equal(fixture.storage.state.aborts, 1, 'opening settings cancels and disposes the old read');
  const frame = fixture.frames.at(-1);
  fixture.host.send({ type: 'azhou-startup', action: 'background', runId: api.status().runId,
    image: SAVED_DSH_IMAGE, strength: 54 }, frame.contentWindow);
  await fixture.waitForWallpaper(api, wallpaper => wallpaper.applied, 'new settings wallpaper was not applied');
  fixture.storage.state.releaseFirst();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(fixture.rendererCalls, [{ image: SAVED_DSH_IMAGE, strength: 54 }]);
  assert.equal(api.status().wallpaper.applied, true, 'the cancelled read does not replace the settings result');
  assert.equal(api.status().phase, 'loading', 'the settings frame remains available');
  api.dispose();
});

test('DSH pagehide and HMR dispose cancel old reads and ignore late results', async () => {
  const pagehide = realDSHWallpaperFixture({ holdFirstRead: true });
  installStartup(pagehide.payload, pagehide.host, pagehide.pageAdapter, 'dsh-gated');
  await waitForCondition(() => typeof pagehide.storage.state.releaseFirst === 'function',
    'pagehide fixture read did not become pending');
  pagehide.host.pagehide();
  assert.equal(pagehide.storage.state.aborts, 1);
  pagehide.storage.state.releaseFirst();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(pagehide.rendererCalls.length, 0);
  pagehide.host.__azhouStartup.dispose();

  const hmr = realDSHWallpaperFixture({ holdFirstRead: true });
  installStartup(hmr.payload, hmr.host, hmr.pageAdapter, 'dsh-gated');
  const oldApi = hmr.host.__azhouStartup;
  await waitForCondition(() => typeof hmr.storage.state.releaseFirst === 'function',
    'HMR fixture read did not become pending');
  oldApi.dispose();
  assert.equal(hmr.storage.state.aborts, 1, 'dispose closes the old page operation');
  installStartup(hmr.payload, hmr.host, hmr.pageAdapter, 'dsh-gated');
  const newApi = hmr.host.__azhouStartup;
  await hmr.waitForWallpaper(newApi, wallpaper => wallpaper.applied,
    'replacement controller did not restore saved wallpaper');
  hmr.storage.state.releaseFirst();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(hmr.rendererCalls, [{ image: hmr.saved.artwork, strength: 31 }]);
  assert.equal(newApi.status().wallpaper.applied, true);
  assert.equal(newApi.status().phase, 'prepared');
  assert.equal(hmr.frames.length, 0, 'HMR replacement does not replay the animation');
  newApi.dispose();
});

test('DSH gate claim precedes playback and releases only after the frame reports ready', () => {
  const fixture = dshFixture({ gate: true });
  assert.deepEqual(installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated'),
    { installed: true, alreadyActive: false });
  const api = fixture.host.__azhouStartup;
  assert.equal(fixture.calls.claims, 1);
  assert.equal(fixture.gatePhase(), 'claimed');
  assert.equal(api.status().phase, 'loading');
  assert.equal(fixture.calls.specs[0].externalStartGate, true);
  assert.match(fixture.frames[0].style.cssText, /z-index:2147483646/,
    'the gated DSH animation stays below the bridge cover');
  assert.deepEqual(installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated'),
    { installed: true, alreadyActive: true });
  assert.equal(fixture.calls.claims, 1, 'duplicate installer does not claim or restart the document gate');
  fixture.sendReady();
  assert.equal(api.status().phase, 'playing');
  assert.equal(fixture.calls.readies, 1);
  assert.equal(fixture.calls.launches, 1);
  assert.equal(fixture.gatePhase(), 'released');
  api.dispose();
});

test('ordinary startup overlays keep the maximum layer while DSH gated overlays sit below the cover', () => {
  const gated = dshFixture({ gate: true });
  installStartup(gated.payload, gated.host, gated.pageAdapter, 'dsh-gated');
  assert.match(gated.frames[0].style.cssText, /z-index:2147483646/);
  gated.host.__azhouStartup.dispose();

  const ordinary = controlledHost();
  installStartup(() => ({}), ordinary.host, pageAdapter);
  assert.match(ordinary.frames[0].style.cssText, /z-index:2147483647/,
    'non-DSH entry points keep their existing top layer');
  ordinary.host.__azhouStartup.dispose();
});

test('expired DSH claim fails closed and a late ready message cannot start playback', () => {
  const fixture = dshFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const frame = fixture.frames[0];
  const frameObserver = fixture.observers.at(-1);
  const watchdog = fixture.timers.find(timer => timer.delay === 25_000);
  assert.equal(frameObserver.observing, true);
  assert.equal(watchdog.cleared, false);
  assert.equal(fixture.gate.release(), true, 'simulate the early bridge watchdog expiring');
  assert.equal(fixture.host.__azhouStartup.status().phase, 'failed');
  assert.equal(fixture.host.__azhouStartup.status().reason, 'startup-gate-expired');
  assert.equal(frame.removed, true, 'gate expiry immediately removes the never-ready player iframe');
  assert.equal(frameObserver.disconnected, true, 'gate expiry disconnects the player frame observer');
  assert.equal(watchdog.cleared, true, 'the gate event cancels the longer renderer fallback watchdog');
  fixture.sendReady();
  assert.equal(fixture.host.__azhouStartup.status().phase, 'failed');
  assert.equal(fixture.host.__azhouStartup.status().reason, 'startup-gate-expired');
  assert.equal(fixture.calls.launches, 0);
  fixture.host.__azhouStartup.dispose();
});

test('normal DSH ready and gate release do not trigger expiry cleanup', () => {
  const fixture = dshFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const frame = fixture.frames[0];
  const frameObserver = fixture.observers.at(-1);
  fixture.sendReady();
  assert.equal(api.status().phase, 'playing');
  assert.equal(fixture.gatePhase(), 'released');
  assert.equal(fixture.gate.expire(), false, 'a normally released gate cannot report an expiry');
  assert.equal(api.status().phase, 'playing');
  assert.equal(frame.removed, false, 'the ready player remains active');
  assert.equal(frameObserver.disconnected, false, 'the active player observer remains connected');
  api.dispose();
  assert.equal(frame.removed, true);
  assert.equal(frameObserver.disconnected, true);
});

test('DSH skip before player ready releases the gate instead of stranding its cover', () => {
  const fixture = dshFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  const frame = fixture.frames[0];
  assert.equal(fixture.gatePhase(), 'claimed');
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: api.status().runId,
    skipped: true }, frame.contentWindow);
  assert.equal(api.status().phase, 'complete');
  assert.equal(api.status().completion.cause, 'skip');
  assert.equal(fixture.gatePhase(), 'expired');
  assert.equal(frame.removed, true);
  assert.equal(fixture.calls.launches, 0, 'skip can terminate before launch without starting the animation');
  api.dispose();
});

test('DSH player natural completion after the 12-second run leaves gate released', () => {
  const fixture = dshFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const api = fixture.host.__azhouStartup;
  fixture.sendReady();
  const frame = fixture.frames[0];
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: api.status().runId,
    skipped: false }, frame.contentWindow);
  assert.equal(api.status().phase, 'complete');
  assert.equal(api.status().completion.cause, 'natural');
  assert.equal(fixture.gatePhase(), 'released');
  assert.equal(frame.removed, true);
  assert.equal(fixture.calls.launches, 1);
  api.dispose();
});

test('DSH payload failure and controller disposal release only the owned gate and frame', () => {
  const broken = dshFixture({ gate: true });
  const throws = () => { throw new Error('synthetic payload failure'); };
  assert.equal(installStartup(throws, broken.host, broken.pageAdapter, 'dsh-gated').installed, true);
  assert.equal(broken.host.__azhouStartup.status().phase, 'failed');
  assert.equal(broken.gatePhase(), 'expired');
  assert.equal(broken.frames[0].removed, true, 'startup failure removes its own animation iframe');
  assert.equal(broken.calls.releases, 1);
  broken.host.__azhouStartup.dispose();

  const closed = dshFixture({ gate: true });
  installStartup(closed.payload, closed.host, closed.pageAdapter, 'dsh-gated');
  const frame = closed.frames[0];
  assert.equal(closed.gatePhase(), 'claimed');
  closed.host.__azhouStartup.dispose();
  assert.equal(closed.gatePhase(), 'expired');
  assert.equal(frame.removed, true, 'close removes the owned animation iframe');
  assert.equal(closed.calls.launches, 0);
});

test('DSH renderer watchdog expires a never-ready frame and releases its early cover', () => {
  const fixture = dshFixture({ gate: true });
  installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated');
  const watchdog = fixture.timers.find(timer => !timer.cleared && timer.delay === 25_000);
  assert.ok(watchdog);
  watchdog.callback();
  assert.equal(fixture.host.__azhouStartup.status().phase, 'timeout');
  assert.equal(fixture.gatePhase(), 'expired');
  assert.equal(fixture.frames[0].removed, true, 'never-ready animation iframe is removed at its own watchdog');
  assert.equal(fixture.calls.launches, 0);
  fixture.host.__azhouStartup.dispose();
});

test('DSH client without body cannot claim and the early cover remains watchdog-owned', () => {
  const fixture = dshFixture({ body: false, gate: true });
  assert.deepEqual(installStartup(fixture.payload, fixture.host, fixture.pageAdapter, 'dsh-gated'),
    { installed: false, alreadyActive: false, reason: 'page-unsupported' });
  assert.equal(fixture.calls.claims, 0);
  assert.equal(fixture.frames.length, 0);
  assert.equal(fixture.gate.status(), 'waiting');
  fixture.gate.release();
  assert.equal(fixture.gate.status(), 'expired', 'the bridge watchdog can reveal an unclaimed page');
});

test('hidden navigation falls back to a visible left entry and scroll repositions it', () => {
  const fixture = controlledHost();
  const [{ nav }] = addAppearanceNavigation(fixture);
  nav.hidden = true;
  const doc = fixture.host.document;
  doc.documentElement.clientHeight = 800;
  doc.documentElement.clientWidth = 1024;
  doc.appearanceControls = [];
  let entry;
  const createElement = doc.createElement;
  doc.createElement = tag => {
    const node = createElement(tag);
    if (tag === 'div' && !entry) {
      entry = node;
      node.getBoundingClientRect = () => {
        const left = Number.parseFloat(node.style.left || '10px');
        const width = node.children[0].children.at(-1).style.display === 'none' ? 48 : 150;
        const top = node.style.top && node.style.top !== 'auto'
          ? Number.parseFloat(node.style.top)
          : doc.documentElement.clientHeight - Number.parseFloat(node.style.bottom || '72px') - 44;
        return { left, right: left + width, width, top, bottom: top + 44, height: 44 };
      };
    }
    return node;
  };
  let runId;
  installStartup((...args) => { runId = args[14].runId; }, fixture.host, pageAdapter);
  fixture.host.send({ type: 'azhou-startup', action: 'ready', runId }, fixture.frames[0].contentWindow);
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false }, fixture.frames[0].contentWindow);
  entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  assert.equal(entry.parentNode, fixture.host.document.documentElement);
  assert.equal(entry.style.left, '10px');
  assert.equal(entry.style.top, '684px');
  doc.appearanceControls = [{ getBoundingClientRect: () => ({ left: 0, right: 72, width: 72, top: 672, bottom: 720, height: 48 }) }];
  const timersBefore = fixture.timers.length;
  fixture.host.scroll();
  fixture.host.scroll();
  assert.equal(fixture.timers.length, timersBefore + 1, 'scroll events share one pending collision re-evaluation');
  const scrollTimer = fixture.timers.at(-1);
  assert.equal(scrollTimer.delay, 80, 'scroll collision checks are throttled');
  scrollTimer.callback();
  assert.equal(entry.style.top, '728px', 'scrolling controls moves the fallback to a clear left slot');
  fixture.host.scroll();
  const pending = fixture.timers.at(-1);
  fixture.host.__azhouStartup.dispose();
  assert.equal(pending.cleared, true, 'dispose clears a pending scroll positioning task');
  assert.equal(fixture.scrollListenerCount(), 0, 'scroll listener is released');
});

test('display-none navigation and zero-size ancestors use fallback, then reclaim the entry when shown', () => {
  const fixture = controlledHost();
  const [{ nav, yourDot, pinned }] = addAppearanceNavigation(fixture);
  nav.style.display = 'none';
  let runId;
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    runId = spec.runId;
    send({ type: 'azhou-startup', action: 'ready', runId });
  }, fixture.host, pageAdapter);
  const api = fixture.host.__azhouStartup;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false }, fixture.frames[0].contentWindow);
  const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
  assert.equal(entry.parentNode, fixture.host.document.documentElement, 'display:none cannot take over the entry');

  nav.style.display = 'block';
  const zeroAncestor = {
    tagName: 'div', style: {}, hidden: false, children: [nav], parentNode: null,
    get parentElement() { return this.parentNode; },
    getBoundingClientRect() { return { left: 0, right: 0, width: 0, top: 0, bottom: 0, height: 0 }; },
    contains(node) { return node === nav || nav.contains?.(node) === true; },
  };
  nav.parentNode = zeroAncestor;
  observer.trigger([{ target: nav, type: 'attributes', attributeName: 'style' }]);
  fixture.timers.at(-1).callback();
  assert.equal(entry.parentNode, fixture.host.document.documentElement, 'a zero-size ancestor keeps the entry on the left');

  zeroAncestor.getBoundingClientRect = () => ({ left: 0, right: 220, width: 220, top: 0, bottom: 600, height: 600 });
  observer.trigger([{ target: zeroAncestor, type: 'attributes', attributeName: 'style' }]);
  fixture.timers.at(-1).callback();
  assert.equal(nav.children[0], yourDot);
  assert.equal(nav.children[1], entry, 'the same entry returns to normal flow after its ancestor is visible');
  assert.equal(nav.children[2], pinned);
  api.dispose();
});

test('appearance entry joins the unique Your dot navigation row before Pinned', () => {
  const fixture = controlledHost();
  const [{ nav, yourDot, pinned, setWidth }] = addAppearanceNavigation(fixture);
  let runId;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runId = frameSpec.runId;
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.createLocalization = ({ locale }) => ({ t: key => ({
    characterName: locale === 'en' ? 'Azhou' : '阿舟',
    openAppearance: locale === 'en' ? 'Open appearance settings' : '打开外观设置',
    appearanceLabel: locale === 'en' ? 'Azhou appearance settings' : '阿舟外观设置',
    overlayLabel: locale === 'en' ? 'Azhou startup animation' : '阿舟启动动画',
  })[key] });
  payload.assets = { entryAvatar: 'data:image/png;base64,AA==' };
  installStartup(payload, fixture.host, pageAdapter);
  const entry = fixture.controls.find(node => node.tagName === 'div');
  const button = appearanceButton(fixture);
  assert.equal(nav.children[0], yourDot);
  assert.equal(nav.children[1], entry);
  assert.equal(nav.children[2], pinned);
  assert.equal(entry.style.position, 'static', 'the host navigation owns the entry position');
  assert.equal(entry.style.left, '');
  assert.equal(entry.style.bottom, '');
  assert.equal(button.children.at(-1).textContent, '阿舟外观');
  assert.equal(button.attributes.get('aria-label'), '阿舟外观');
  assert.ok(button.children.some(node => node.tagName === 'img' && node.src === payload.assets.entryAvatar));
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false }, fixture.frames[0].contentWindow);
  const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
  setWidth(52);
  observer.trigger([{ target: nav, type: 'attributes' }]);
  fixture.timers.at(-1).callback();
  assert.equal(button.children.at(-1).style.display, 'none', 'the collapsed row keeps the avatar without overflowing its label');
  assert.equal(button.attributes.get('aria-label'), '阿舟外观', 'the collapsed icon remains recognizable to assistive technology');
  setWidth(220);
  observer.trigger([{ target: nav, type: 'attributes' }]);
  fixture.timers.at(-1).callback();
  assert.equal(button.children.at(-1).style.display, '', 'the label returns when the navigation expands');
  fixture.host.__azhouStartup.dispose();
});

test('appearance entry follows the Home Your dot button, ignores a same-named chat, and fits a narrow sidebar', () => {
  for (const label of ['Your dot', '你的 Dot']) {
    const fixture = controlledHost();
    const [{ nav, navList, yourDot, scrollContent, pinned, chatTitle, setWidth }] =
      addAppearanceNavigation(fixture, { label, layout: 'home' });
    let runId;
    const payload = function (_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) {
      runId = spec.runId;
      send({ type: 'azhou-startup', action: 'ready', runId });
    };
    payload.assets = { entryAvatar: 'data:image/png;base64,AA==' };
    installStartup(payload, fixture.host, pageAdapter);
    const api = fixture.host.__azhouStartup;
    const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
    const button = appearanceButton(fixture);

    assert.equal(nav.children[0].children[0], navList);
    assert.equal(navList.children[0], yourDot);
    assert.equal(navList.children[1], entry, 'the owned row follows the system button in normal flow');
    assert.equal(entry.style.position, 'static');
    assert.equal(entry.style.left, '');
    assert.equal(entry.style.bottom, '');
    assert.equal(scrollContent.children[0], pinned, 'Pinned remains after the system navigation row');
    assert.equal(scrollContent.children[1], chatTitle, 'a same-named user chat stays in the scroll content');

    fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false }, fixture.frames[0].contentWindow);
    setWidth(52);
    const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
    observer.trigger([{ target: nav, type: 'attributes', attributeName: 'style' }]);
    fixture.timers.at(-1).callback();
    assert.equal(navList.children[1], entry, 'a collapsed sidebar keeps the row in its normal-flow slot');
    assert.equal(button.children.at(-1).style.display, 'none', 'the collapsed row hides its text to avoid overflow');
    assert.equal(button.children[0].tagName, 'img', 'the avatar remains visible in the narrow row');
    assert.equal(button.attributes.get('aria-label'), '阿舟外观');
    api.dispose();
  }
});

test('appearance entry stays below Your dot when an unread count appears and disappears', () => {
  const fixture = controlledHost();
  const [{ list, listItem, yourDot }] = addAppearanceNavigation(fixture, { layout: 'wrapped' });
  let runId;
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    runId = spec.runId;
    send({ type: 'azhou-startup', action: 'ready', runId });
  }, fixture.host, pageAdapter);
  const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  assert.equal(list.children[1], entry);
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false }, fixture.frames[0].contentWindow);
  const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
  yourDot.textContent = 'Your dot1';
  observer.trigger([{ target: yourDot, type: 'childList' }]);
  fixture.timers.at(-1).callback();
  assert.equal(list.children[0], listItem);
  assert.equal(list.children[1], entry, 'unread badge must not dislodge the entry');
  assert.equal(entry.style.position, 'static');
  yourDot.textContent = 'Your dot';
  observer.trigger([{ target: yourDot, type: 'childList' }]);
  fixture.timers.at(-1).callback();
  assert.equal(list.children[1], entry);
  fixture.host.__azhouStartup.dispose();
});

test('appearance recognizes initial numeric unread badges without matching unrelated labels', () => {
  for (const [label, expected] of [['Your dot1', true], ['你的 Dot 99+', true], ['Your dot settings', false]]) {
    const fixture = controlledHost();
    const [{ list }] = addAppearanceNavigation(fixture, { label, layout: 'wrapped' });
    installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
      send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
    }, fixture.host, pageAdapter);
    const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
    assert.equal(entry.parentNode === list, expected, label);
    fixture.host.__azhouStartup.dispose();
  }
});

test('appearance entry uses wrapped Home list rows and refuses unsupported wrappers', () => {
  for (const valid of [true, false]) {
    const fixture = controlledHost();
    const [{ list, listItem }] = addAppearanceNavigation(fixture, { layout: 'wrapped' });
    if (!valid) list.setAttribute('role', 'group');
    installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
      send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
    }, fixture.host, pageAdapter);
    const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
    assert.equal(entry.parentNode, valid ? list : fixture.host.document.documentElement);
    if (valid) assert.equal(list.children[1], entry, 'the owned entry follows the wrapped Your dot row');
    assert.equal(entry.style.position, valid ? 'static' : 'fixed');
    assert.equal(list.children[0], listItem);
    fixture.host.__azhouStartup.dispose();
  }
});

test('appearance entry accepts a boxless display-contents ancestor but rejects hidden navigation', () => {
  for (const hidden of [false, true]) {
    const fixture = controlledHost();
    const [{ nav, navList }] = addAppearanceNavigation(fixture, { layout: 'home' });
    nav.parentNode = {
      tagName: 'DIV', hidden,
      computedStyle: { display: 'contents', visibility: 'visible' },
      getBoundingClientRect: () => ({ width: 0, height: 0 }),
    };
    installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
      send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
    }, fixture.host, pageAdapter);
    const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
    assert.equal(entry.parentNode === navList, !hidden);
    assert.equal(entry.style.position, hidden ? 'fixed' : 'static');
    fixture.host.__azhouStartup.dispose();
  }
});

test('duplicate Home Your dot buttons keep the appearance entry on its fallback', () => {
  const fixture = controlledHost();
  addAppearanceNavigation(fixture, { count: 2, layout: 'home' });
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
  }, fixture.host, pageAdapter);
  const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  assert.equal(entry.parentNode, fixture.host.document.documentElement);
  assert.equal(entry.style.position, 'fixed');
  assert.equal(entry.style.left, '10px');
  fixture.host.__azhouStartup.dispose();
});

test('appearance entry reanchors into a late Home Your dot button navigation', () => {
  const fixture = controlledHost();
  addAppearanceNavigation(fixture, { count: 0, layout: 'home' });
  let runId;
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    runId = spec.runId;
    send({ type: 'azhou-startup', action: 'ready', runId });
  }, fixture.host, pageAdapter);
  const api = fixture.host.__azhouStartup;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false }, fixture.frames[0].contentWindow);
  const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
  assert.equal(entry.parentNode, fixture.host.document.documentElement);

  const [row] = addAppearanceNavigation(fixture, { layout: 'home' });
  fixture.host.document.documentElement.appendChild(row.nav);
  observer.trigger([{ target: fixture.host.document.documentElement, type: 'childList', addedNodes: [row.nav] }]);
  fixture.timers.at(-1).callback();
  assert.equal(row.navList.children[1], entry, 'a late system button reclaims the entry into normal flow');
  assert.equal(entry.style.position, 'static');
  api.dispose();
});

test('appearance entry recognizes the exact Simplified Chinese Your dot navigation name', () => {
  const fixture = controlledHost();
  const [{ nav, yourDot, pinned }] = addAppearanceNavigation(fixture, { label: '你的 Dot' });
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
  }, fixture.host, pageAdapter);
  const entry = fixture.controls.find(node => node.tagName === 'div');
  assert.equal(nav.children[0], yourDot);
  assert.equal(nav.children[1], entry, 'the translated semantic anchor gets the same normal-flow row');
  assert.equal(nav.children[2], pinned);
  fixture.host.__azhouStartup.dispose();
});

test('appearance entry uses a stable left fallback and stops observing on dispose', () => {
  const fixture = controlledHost();
  const doc = fixture.host.document;
  doc.documentElement.clientHeight = 800;
  doc.documentElement.clientWidth = 1024;
  const createElement = doc.createElement;
  doc.createElement = tag => {
    const node = createElement(tag);
    if (tag === 'div') node.getBoundingClientRect = () => ({ width: 120, height: 44 });
    return node;
  };
  let run;
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    run = spec.runId;
    send({ type: 'azhou-startup', action: 'ready', runId: run });
  }, fixture.host, pageAdapter);
  const api = fixture.host.__azhouStartup;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: run, skipped: false }, fixture.frames[0].contentWindow);
  const entry = fixture.controls.find(node => node.tagName === 'div');
  assert.equal(entry.style.position, 'fixed');
  assert.equal(entry.style.left, '10px');
  assert.equal(entry.style.top, '684px');
  assert.equal(entry.style.display, 'block');
  const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
  assert.ok(observer);
  const beforeOwnStyleMutation = fixture.timers.length;
  observer.trigger([{ target: entry, type: 'attributes', attributeName: 'style' }]);
  assert.equal(fixture.timers.length, beforeOwnStyleMutation, 'owned element style changes do not schedule another positioning pass');
  const unrelated = { getBoundingClientRect: () => ({ left: 300, right: 700, width: 400 }) };
  const before = fixture.timers.length;
  observer.trigger([{ target: unrelated, type: 'attributes' }]);
  assert.equal(fixture.timers.length, before, 'unrelated chat mutations do not schedule navigation scans');
  const last = fixture.timers.at(-1);
  api.dispose();
  assert.equal(observer.disconnected, true);
  if (last) assert.equal(last.cleared, true);
});

test('Escape before a usable host control keeps Appearance hidden and restores its fallback when controls arrive', () => {
  const fixture = controlledHost();
  const doc = fixture.host.document;
  doc.documentElement.clientHeight = 800;
  doc.documentElement.clientWidth = 1024;
  doc.querySelectorAll = selector => selector.includes('[role="textbox"]') ? [fixture.hostControl] : [];
  let loadingOverlay = null;
  doc.elementFromPoint = () => loadingOverlay ?? fixture.hostControl;
  fixture.setHostUIReady(false);
  fixture.controlWrapper.style.opacity = '0';
  const createElement = doc.createElement;
  doc.createElement = tag => {
    const node = createElement(tag);
    if (tag === 'div' && !node.getBoundingClientRect) {
      node.getBoundingClientRect = () => {
        const left = Number.parseFloat(node.style.left || '10px');
        const top = node.style.top && node.style.top !== 'auto'
          ? Number.parseFloat(node.style.top) : doc.documentElement.clientHeight - Number.parseFloat(node.style.bottom || '72px') - 44;
        return { left, right: left + 150, width: 150, top, bottom: top + 44, height: 44 };
      };
    }
    return node;
  };
  let runId;
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, _send, spec) => {
    runId = spec.runId;
  }, fixture.host, pageAdapter);
  const api = fixture.host.__azhouStartup;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: true }, fixture.frames[0].contentWindow);
  const entry = fixture.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  assert.equal(api.status().completion.beforeReady, true, 'the skipped animation completed before the host controls exist');
  assert.equal(entry.style.display, 'none', 'the lower-left fallback stays hidden during the host splash');

  const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
  fixture.setHostUIReady(true);
  observer.trigger([{ target: fixture.controlWrapper, type: 'attributes', attributeName: 'style' }]);
  fixture.timers.at(-1).callback();
  assert.equal(entry.style.display, 'none', 'a hidden editor wrapper does not establish a usable host page');

  fixture.controlWrapper.style.opacity = '1';
  fixture.controlWrapper.getBoundingClientRect = () => ({ left: 200, right: 200, width: 0, top: 600, bottom: 600, height: 0 });
  loadingOverlay = { tagName: 'DIV' };
  observer.trigger([{ target: fixture.controlWrapper, type: 'attributes', attributeName: 'style' }]);
  fixture.timers.at(-1).callback();
  assert.equal(entry.style.display, 'none', 'a visible control stays unavailable while a loading overlay intercepts pointer hits');

  loadingOverlay = null;
  observer.trigger([{ target: doc.documentElement, type: 'childList', addedNodes: [], removedNodes: [] }]);
  fixture.timers.at(-1).callback();
  assert.equal(entry.style.display, 'block', 'a visible editor restores fallback even when its host wrapper has a zero-size box');
  assert.equal(entry.style.position, 'fixed');
  assert.equal(entry.style.left, '10px');
  const bounds = entry.getBoundingClientRect();
  const textbox = fixture.hostControl.getBoundingClientRect();
  const horizontalOverlap = bounds.left < textbox.right && bounds.right > textbox.left;
  assert.ok(!horizontalOverlap || bounds.bottom + 8 <= textbox.top || bounds.top >= textbox.bottom + 8,
    'the recovered fallback keeps clearance from the host textbox');
  api.dispose();
});

test('left fallback avoids update and account controls and remains clickable', () => {
  const fixture = controlledHost();
  const doc = fixture.host.document;
  doc.documentElement.clientHeight = 800;
  doc.documentElement.clientWidth = 1024;
  let entry;
  const createElement = doc.createElement;
  doc.createElement = tag => {
    const node = createElement(tag);
    if (tag === 'div') {
      const setAttribute = node.setAttribute.bind(node);
      node.setAttribute = (name, value) => {
        setAttribute(name, value);
        if (name !== 'data-agent-skin-entry' || value !== 'appearance') return;
        entry = node;
        node.getBoundingClientRect = () => {
          const left = Number.parseFloat(node.style.left || '10px');
          const bottom = Number.parseFloat(node.style.bottom || '72px');
          const button = node.children.find(child => child.attributes?.has('aria-haspopup'));
          const label = button?.children.at(-1);
          const width = label?.style.display === 'none' ? 48 : 150;
          const top = node.style.top && node.style.top !== 'auto'
            ? Number.parseFloat(node.style.top) : doc.documentElement.clientHeight - bottom - 44;
          return { left, right: left + width, width, top, bottom: top + 44, height: 44 };
        };
      };
    }
    return node;
  };
  const blockers = [
    { getBoundingClientRect: () => ({ left: 0, right: 72, width: 72, top: 672, bottom: 720, height: 48 }) },
    { getBoundingClientRect: () => ({ left: 0, right: 72, width: 72, top: 736, bottom: 784, height: 48 }) },
  ];
  doc.querySelectorAll = () => blockers;
  const runs = [];
  const payload = function (_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) {
    runs.push(spec);
    send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
  };
  installStartup(payload, fixture.host, pageAdapter);
  const api = fixture.host.__azhouStartup;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[0].runId, skipped: false }, fixture.frames[0].contentWindow);
  const button = appearanceButton(fixture);
  const bounds = entry.getBoundingClientRect();
  assert.equal(entry.style.left, '10px', 'the fallback stays in the left column');
  assert.ok(blockers.every(control => {
    const other = control.getBoundingClientRect();
    return bounds.right <= other.left || bounds.left >= other.right || bounds.bottom + 8 <= other.top || bounds.top >= other.bottom + 8;
  }), 'the fallback leaves vertical clearance around update and account controls');
  button.click();
  assert.equal(api.status().phase, 'settings');
  assert.ok(runs.length >= 2, 'the avoided fallback stays clickable');
  api.dispose();
});

test('appearance entry follows a late unique navigation and falls back across ambiguity and replacement', () => {
  const fixture = controlledHost();
  addAppearanceNavigation(fixture, { count: 0 });
  let runId;
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    runId = spec.runId;
    send({ type: 'azhou-startup', action: 'ready', runId });
  }, fixture.host, pageAdapter);
  const api = fixture.host.__azhouStartup;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false }, fixture.frames[0].contentWindow);
  const entry = fixture.controls.find(node => node.tagName === 'div');
  const observer = fixture.observers.find(item => item.options?.childList && item.options?.attributes);
  assert.equal(entry.style.position, 'fixed', 'without a recognized host row the entry stays on the left');

  const [first] = addAppearanceNavigation(fixture);
  fixture.host.document.documentElement.appendChild(first.nav);
  observer.trigger([{ target: fixture.host.document.documentElement, type: 'childList', addedNodes: [first.nav] }]);
  fixture.timers.at(-1).callback();
  assert.equal(first.nav.children[1], entry, 'a late unique nav relocates the entry into normal flow');
  assert.equal(entry.style.position, 'static');

  const ambiguous = addAppearanceNavigation(fixture, { count: 2 });
  ambiguous.forEach(({ nav }) => fixture.host.document.documentElement.appendChild(nav));
  observer.trigger([{ target: fixture.host.document.documentElement, type: 'childList', addedNodes: ambiguous.map(({ nav }) => nav) }]);
  fixture.timers.at(-1).callback();
  assert.equal(entry.parentNode, fixture.host.document.documentElement, 'ambiguous anchors return to the stable fallback');
  assert.equal(entry.style.position, 'fixed');
  assert.equal(entry.style.left, '10px');

  fixture.host.document.documentElement.removeChild(first.nav);
  ambiguous.forEach(({ nav }) => fixture.host.document.documentElement.removeChild(nav));
  const [replacement] = addAppearanceNavigation(fixture);
  fixture.host.document.documentElement.appendChild(replacement.nav);
  observer.trigger([{ target: fixture.host.document.documentElement, type: 'childList',
    removedNodes: [first.nav, ...ambiguous.map(({ nav }) => nav)], addedNodes: [replacement.nav] }]);
  fixture.timers.at(-1).callback();
  assert.equal(replacement.nav.children[1], entry, 'a replacement host row receives the same owned entry');
  assert.equal(replacement.nav.children[2], replacement.pinned);
  api.dispose();
});

test('a visible appearance button opens settings after playback without a keyboard shortcut', () => {
  const controlled = controlledHost();
  const runs = [];
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runs.push(frameSpec);
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[0].runId, skipped: false }, controlled.frames[0].contentWindow);
  const officialShortcut = { metaKey: true, altKey: true, key: 'b', prevented: false,
    preventDefault() { this.prevented = true; } };
  controlled.host.keydown(officialShortcut);
  assert.equal(officialShortcut.prevented, false, 'the official browser shortcut is left to the host');
  assert.equal(runs.length, 1);
  const button = controlled.controls.find(node => node.tagName === 'button');
  assert.ok(button, 'appearance settings has a clickable primary entry');
  button.click();
  assert.equal(api.status().phase, 'settings');
  assert.equal(runs[1].intent, 'settings');
  assert.equal(runs.length, 2);
  api.dispose();
  assert.ok(controlled.controls.some(node => node.removed), 'dispose removes the owned entry');
  button.click();
  assert.equal(runs.length, 2, 'a disposed entry cannot reopen settings');
});

test('official language and theme flow into the overlay and update without restarting its run', () => {
  const controlled = controlledHost();
  const root = controlled.host.document.documentElement;
  root.lang = 'en-US';
  root.dataset = { theme: 'light' };
  root.getAttribute = name => name === 'lang' ? root.lang : root.dataset.theme;
  controlled.host.getComputedStyle = () => ({ getPropertyValue: name => ({
    '--color-surface': '#fafafa', '--color-text-primary': '#202020',
    '--color-text-secondary': '#606060', '--color-border': '#dddddd',
  })[name] || '', colorScheme: root.dataset.theme });
  const appearances = [];
  let spec;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    spec = frameSpec;
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
    return { updateAppearance: value => appearances.push(value), dispose() {} };
  };
  payload.createLocalization = ({ locale }) => ({ t: key => ({
    characterName: locale === 'en' ? 'Azhou' : '阿舟',
    openAppearance: locale === 'en' ? 'Open appearance settings' : '打开外观设置',
    appearanceLabel: locale === 'en' ? 'Azhou appearance settings' : '阿舟外观设置',
    overlayLabel: locale === 'en' ? 'Azhou startup animation' : '阿舟启动动画',
  })[key] });
  payload.assets = { entryAvatar: 'data:image/png;base64,AA==' };
  installStartup(payload, controlled.host, pageAdapter);
  assert.equal(spec.appearance.locale, 'en');
  assert.equal(spec.appearance.theme, 'light');
  assert.equal(spec.appearance.colors.surface, '#fafafa');
  const button = appearanceButton(controlled);
  assert.equal(button.attributes.get('aria-label'), 'Azhou Appearance');
  const api = controlled.host.__azhouStartup;
  const runId = api.status().runId;
  root.lang = 'zh-CN'; root.dataset.theme = 'dark';
  controlled.observers.forEach(observer => observer.trigger());
  assert.equal(appearances.at(-1).locale, 'zh-CN');
  assert.equal(appearances.at(-1).theme, 'dark');
  assert.equal(api.status().runId, runId);
  assert.equal(controlled.frames.length, 1);
  assert.equal(api.status().phase, 'playing');
  assert.equal(button.attributes.get('aria-label'), '阿舟外观');
  assert.equal(button.children.at(-1).textContent, '阿舟外观');
  assert.ok(controlled.controls.some(node => node.tagName === 'img' && node.src === payload.assets.entryAvatar));
  api.dispose();
  assert.ok(controlled.observers.every(observer => observer.disconnected));
  root.lang = 'en'; controlled.observers.forEach(observer => observer.trigger());
  assert.equal(appearances.at(-1).locale, 'zh-CN');
});

test('wallpaper receives the first valid official surface and follows theme fallbacks', async () => {
  const controlled = controlledHost();
  const root = controlled.host.document.documentElement;
  root.lang = 'en-US';
  root.dataset = { theme: 'dark' };
  root.getAttribute = name => name === 'lang' ? root.lang : root.dataset.theme;
  let tokens = {
    '--app-color-background-surface': 'not-a-color',
    '--color-surface': 'rgb(200, 210, 220)',
  };
  controlled.host.getComputedStyle = () => ({
    getPropertyValue: name => tokens[name] || '',
    colorScheme: root.dataset.theme,
  });
  const appliedSurfaces = [];
  const wallpaperAPI = {
    owner: 'azhou.codex-startup-animation', version: '0.9.0',
    status: () => ({ applied: true, imageDecoded: true, reason: '' }),
    updateSurface(value) { appliedSurfaces.push(value); return true; },
    dispose() {},
  };
  let spec;
  let backgroundRequest;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    spec = frameSpec;
    backgroundRequest = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,AA==', strength: 42 });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = async value => {
    appliedSurfaces.push(value.surface);
    controlled.host.__azhouWallpaper = wallpaperAPI;
    return { applied: true };
  };
  installStartup(payload, controlled.host, pageAdapter);
  await backgroundRequest;
  assert.equal(spec.appearance.colors.surface, 'rgb(200, 210, 220)',
    'an invalid higher-priority token falls through to the next valid token');
  assert.equal(appliedSurfaces[0], 'rgb(200, 210, 220)',
    'the wallpaper applicator receives the resolved color rather than a raw token');

  tokens = {
    '--app-color-background-surface': 'rgb(10, 20, 30)',
    '--color-surface': 'rgb(200, 210, 220)',
  };
  root.dataset.theme = 'light';
  controlled.observers.forEach(observer => observer.trigger());
  assert.equal(appliedSurfaces.at(-1), 'rgb(10, 20, 30)', 'the app token has first priority');

  tokens = { '--app-color-background-surface': 'not-a-color', '--color-surface': 'also-not-a-color' };
  root.dataset.theme = 'dark';
  controlled.observers.forEach(observer => observer.trigger());
  assert.equal(appliedSurfaces.at(-1), '#10121c', 'invalid dark tokens use the dark fallback');

  root.dataset.theme = 'light';
  controlled.observers.forEach(observer => observer.trigger());
  assert.equal(appliedSurfaces.at(-1), '#ffffff', 'invalid light tokens use the light fallback');
  controlled.host.__azhouStartup.dispose();
});

test('the real controller and default iframe mount execute an explicit parent-realm payload bridge', () => {
  const controlled = controlledHost();
  controlled.host.document.documentElement.lang = 'en-US';
  const observed = {};
  const result = installStartup(function (
    window, document, location, performance, indexedDB, Image, Path2D, URL,
    requestAnimationFrame, cancelAnimationFrame, setTimeout, clearTimeout, module, SEND, frameSpec,
  ) {
    Object.assign(observed, {
      window, document, location, performance, indexedDB, Image, Path2D, URL,
      requestAnimationFrame, cancelAnimationFrame, setTimeout, clearTimeout, module,
    });
    requestAnimationFrame(() => SEND({
      type: 'azhou-startup', action: 'ready', runId: frameSpec.runId,
    }));
  }, controlled.host, pageAdapter);

  assert.deepEqual(result, { installed: true, alreadyActive: false });
  assert.equal(controlled.frames.length, 1);
  const frame = controlled.frames[0];
  assert.equal(frame.src, 'about:blank');
  assert.equal(frame.attributes.get('title'), 'Azhou startup animation');
  assert.equal(frame.attributes.get('aria-label'), 'Azhou startup animation');
  assert.equal(frame.contentWindow.evalCalls, 0);
  assert.equal(controlled.listenerCount(), 1);

  const loading = controlled.host.__azhouStartup.status();
  assert.equal(loading.phase, 'loading');
  assert.equal(loading.ready, false);
  assert.equal(loading.overlay, true);
  assert.equal(frame.contentWindow.window, frame.contentWindow);
  assert.equal(observed.window, frame.contentWindow);
  assert.equal(observed.document, frame.contentWindow.document);
  assert.equal(observed.location, frame.contentWindow.location);
  assert.equal(observed.performance, frame.contentWindow.performance);
  assert.equal(observed.indexedDB, frame.contentWindow.indexedDB);
  assert.equal(observed.Image, frame.contentWindow.Image);
  assert.equal(observed.Path2D, frame.contentWindow.Path2D);
  assert.equal(observed.URL, frame.contentWindow.URL);
  assert.equal(observed.module, undefined);

  const runId = loading.runId;
  const ready = { type: 'azhou-startup', action: 'ready', runId };
  controlled.host.send(ready, {});
  controlled.host.send({ ...ready, runId: runId + 1 }, frame.contentWindow);
  controlled.host.send({ ...ready, action: 'unknown' }, frame.contentWindow);
  assert.equal(controlled.host.__azhouStartup.status().phase, 'loading');
  frame.contentWindow.flushAnimationFrame();
  assert.equal(controlled.host.__azhouStartup.status().phase, 'playing');
  assert.equal(controlled.host.__azhouStartup.status().ready, true);
  controlled.host.send(ready, {});
  assert.equal(controlled.host.__azhouStartup.status().phase, 'playing');
});

test('a real minimal payload can skip before ready and the controller records that result', () => {
  const controlled = controlledHost();
  const result = installStartup(function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    SEND({ type: 'azhou-startup', action: 'complete', runId: frameSpec.runId, skipped: true });
  }, controlled.host, pageAdapter);
  assert.deepEqual(result, { installed: true, alreadyActive: false });

  const status = controlled.host.__azhouStartup.status();
  assert.equal(status.phase, 'complete');
  assert.equal(status.ready, false);
  assert.equal(status.completed, true);
  assert.equal(status.overlay, false);
  assert.deepEqual(status.completion, { cause: 'skip', beforeReady: true });
  assert.equal(controlled.frames[0].removed, true);
  assert.equal(controlled.timers[0].cleared, true);
});

test('the loading watchdog releases a never-ready overlay and keeps a typed timeout receipt', () => {
  const controlled = controlledHost();
  installStartup(function () {}, controlled.host, pageAdapter);
  const frame = controlled.frames[0];
  const timer = controlled.timers[0];
  assert.equal(timer.delay, 25_000);
  timer.callback();

  const status = controlled.host.__azhouStartup.status();
  assert.equal(status.phase, 'timeout');
  assert.equal(status.reason, 'overlay-timeout');
  assert.equal(status.overlay, false);
  assert.equal(frame.removed, true);
  assert.equal(controlled.listenerCount(), 0);
  controlled.host.send({ type: 'azhou-startup', action: 'ready', runId: status.runId }, frame.contentWindow);
  assert.equal(controlled.host.__azhouStartup.status().ready, false);
});

test('a ready playback timeout keeps its receipt and reopens settings through the appearance entry', () => {
  const controlled = controlledHost();
  addAppearanceNavigation(controlled);
  const runs = [];
  let disposedFrames = 0;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runs.push({ ...frameSpec, send: SEND });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
    return { dispose() { disposedFrames++; } };
  };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  const firstFrame = controlled.frames[0];
  const watchdog = controlled.timers.find(timer => timer.delay === 25_000);
  const entry = controlled.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  const button = appearanceButton(controlled);
  assert.equal(api.status().phase, 'playing');
  assert.equal(entry.style.display, 'none');

  watchdog.callback();
  const timedOut = api.status();
  assert.equal(timedOut.phase, 'timeout');
  assert.equal(timedOut.reason, 'overlay-timeout');
  assert.equal(timedOut.ready, true);
  assert.equal(timedOut.completed, false);
  assert.equal(timedOut.completion, null);
  assert.equal(timedOut.overlay, false);
  assert.equal(firstFrame.removed, true);
  assert.equal(disposedFrames, 1);
  assert.equal(controlled.listenerCount(), 0);
  assert.equal(entry.style.display, 'block', 'a prepared run can expose settings without claiming playback completed');
  assert.equal(button.disabled, false);

  const complete = { type: 'azhou-startup', action: 'complete', runId: runs[0].runId, skipped: false };
  runs[0].send(complete);
  assert.deepEqual(api.status(), timedOut, 'a late direct frame bridge cannot rewrite the timeout');
  button.click();
  assert.equal(runs.length, 2);
  assert.equal(runs[1].intent, 'settings', 'recovery starts settings rather than replaying startup');
  assert.notEqual(runs[1].runId, runs[0].runId);
  assert.equal(api.status().phase, 'settings');
  assert.equal(api.status().completed, false);
  assert.equal(api.openSettings(), false, 'an active settings session is not replaced');

  controlled.host.send({ ...complete, runId: runs[1].runId, skipped: true }, firstFrame.contentWindow);
  controlled.host.send(complete, controlled.frames[1].contentWindow);
  runs[0].send({ ...complete, runId: runs[1].runId, skipped: true });
  watchdog.callback();
  assert.equal(api.status().phase, 'settings', 'old sources, run IDs and watchdogs cannot close the new run');
  assert.equal(disposedFrames, 1);

  runs[1].send({ type: 'azhou-startup', action: 'complete', runId: runs[1].runId, skipped: true });
  assert.equal(api.status().phase, 'complete');
  assert.deepEqual(api.status().completion, { cause: 'settings-cancel', beforeReady: false });
  assert.equal(entry.style.display, 'block');
  assert.equal(disposedFrames, 2);
  api.dispose();
  button.click();
  assert.equal(api.openSettings(), false);
  assert.equal(runs.length, 2);
});

test('a ready timeout retries the same appearance entry when navigation becomes usable', () => {
  const controlled = controlledHost();
  const [{ nav }] = addAppearanceNavigation(controlled);
  nav.hidden = true;
  controlled.setHostUIReady(false);
  const runs = [];
  installStartup((...args) => {
    const send = args[13], spec = args[14];
    runs.push(spec);
    send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
  }, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  const entry = controlled.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
  controlled.timers.find(timer => timer.delay === 25_000).callback();
  assert.equal(api.status().phase, 'timeout');
  assert.equal(entry.style.display, 'none', 'timeout recovery still respects host layout availability');

  nav.hidden = false;
  const observer = controlled.observers.find(item => item.options?.childList && item.options?.attributes);
  observer.trigger([{ target: nav, type: 'attributes', attributeName: 'hidden' }]);
  const scheduled = controlled.timers.at(-1);
  assert.equal(scheduled.delay, 80, 'the enabled entry retains its bounded layout retry');
  scheduled.callback();
  assert.equal(entry.style.display, 'block');
  assert.equal(nav.children[1], entry, 'the original entry moves back into the navigation');
  assert.equal(controlled.controls.filter(node => node.attributes?.get('data-agent-skin-entry') === 'appearance').length, 1);
  appearanceButton(controlled).click();
  assert.equal(runs[1].intent, 'settings');
  api.dispose();
});

test('appearance recovery stays closed for loading, unready timeout, asset failure and disposal', () => {
  for (const outcome of ['timeout', 'failed', 'disposed']) {
    const controlled = controlledHost();
    addAppearanceNavigation(controlled);
    installStartup(function () {}, controlled.host, pageAdapter);
    const api = controlled.host.__azhouStartup;
    const entry = controlled.controls.find(node => node.attributes?.get('data-agent-skin-entry') === 'appearance');
    const runId = api.status().runId;
    assert.equal(api.openSettings(), false, 'loading cannot open a second run');
    if (outcome === 'timeout') controlled.timers.find(timer => timer.delay === 25_000).callback();
    else if (outcome === 'failed') controlled.host.send({
      type: 'azhou-startup', action: 'assetError', reason: 'asset-invalid', runId,
    }, controlled.frames[0].contentWindow);
    else api.dispose();
    assert.equal(api.status().phase, outcome);
    assert.equal(api.status().ready, false);
    assert.equal(api.openSettings(), false);
    appearanceButton(controlled).click();
    assert.equal(controlled.frames.length, 1, outcome + ' never creates a settings frame');
    if (outcome !== 'disposed') assert.equal(entry.style.display, 'none');
    api.dispose();
  }
});

test('install does not replace an existing controller or an unknown owner', () => {
  const controlled = controlledHost();
  const payload = function () {};
  const first = installStartup(payload, controlled.host, pageAdapter);
  const second = installStartup(payload, controlled.host, pageAdapter);
  assert.deepEqual(first, { installed: true, alreadyActive: false });
  assert.deepEqual(second, { installed: true, alreadyActive: true });
  assert.equal(controlled.frames.length, 1);

  const unknown = controlledHost();
  const existing = { owner: 'unknown-owner', version: 9 };
  Object.defineProperty(unknown.host, '__azhouStartup', { value: existing, configurable: true });
  assert.deepEqual(installStartup(payload, unknown.host, pageAdapter), {
    installed: false, alreadyActive: false, reason: 'owner-conflict',
  });
  assert.equal(unknown.host.__azhouStartup, existing);
  assert.equal(unknown.frames.length, 0);
});

test('snapshot support stays additive to same-owner controllers from the prior API surface', () => {
  const prior = controlledHost();
  const oldAPI = Object.freeze({ owner: 'azhou-codex-startup', version: 1,
    status() { return { phase: 'complete' }; }, openSettings() {}, dispose() {} });
  Object.defineProperty(prior.host, '__azhouStartup', { value: oldAPI, configurable: true });
  assert.deepEqual(installStartup(function () {}, prior.host, pageAdapter), {
    installed: true, alreadyActive: true,
  }, 'a same-owner/version controller remains recognized even without the new optional export methods');
  assert.equal(typeof prior.host.__azhouStartup.beginSettingsSnapshot, 'undefined');
  assert.equal(prior.frames.length, 0, 'the compatibility check does not install over the older live controller');

  const foreign = controlledHost();
  Object.defineProperty(foreign.host, '__azhouStartup', {
    value: Object.freeze({ ...oldAPI, owner: 'foreign-startup' }), configurable: true,
  });
  assert.deepEqual(installStartup(function () {}, foreign.host, pageAdapter), {
    installed: false, alreadyActive: false, reason: 'owner-conflict',
  }, 'an unrelated owner still cannot adopt the controller global');
  assert.equal(foreign.frames.length, 0);
});

test('dispose is idempotent and removes only its owned frame and listener', () => {
  const controlled = controlledHost();
  installStartup(function () {}, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  const frame = controlled.frames[0];
  assert.deepEqual(api.dispose(), { disposed: true });
  assert.deepEqual(api.dispose(), { disposed: true });
  assert.equal(Object.hasOwn(controlled.host, '__azhouStartup'), false);
  assert.equal(controlled.listenerCount(), 0);
  assert.equal(frame.removed, true);
  assert.equal(controlled.timers[0].cleared, true);
});

test('play and settings frames share one controller and each new run gets fresh identity', () => {
  const controlled = controlledHost();
  const hostFocus = { isConnected: true, focus() { controlled.host.document.activeElement = this; } };
  controlled.host.document.activeElement = hostFocus;
  const runs = [];
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runs.push(frameSpec);
    raf(() => SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId }));
    return {
      openSettings() {
        if (frameSpec.intent !== 'play') return false;
        SEND({ type: 'azhou-startup', action: 'settings-open', runId: frameSpec.runId });
        return true;
      },
      dispose() {},
    };
  };
  payload.assets = Object.freeze({ fixture: 'controlled-assets' });

  assert.deepEqual(installStartup(payload, controlled.host, pageAdapter), { installed: true, alreadyActive: false });
  const api = controlled.host.__azhouStartup;
  assert.equal(api.openSettings(), false, 'loading resources cannot open settings');
  assert.equal(controlled.frames.length, 1);
  const firstFrame = controlled.frames[0];
  firstFrame.contentWindow.flushAnimationFrame();
  assert.equal(api.status().phase, 'playing');

  assert.equal(api.openSettings(), true);
  assert.equal(api.status().phase, 'settings');
  assert.equal(controlled.frames.length, 1, 'playing opens settings in the owned iframe');
  assert.equal(controlled.timers[0].cleared, true, 'the settings phase has no loading watchdog');

  controlled.host.document.activeElement = firstFrame;
  const save = { type: 'azhou-startup', action: 'settings-close', runId: runs[0].runId };
  controlled.host.send(save, firstFrame.contentWindow);
  assert.equal(controlled.frames.length, 1, 'save closes without replaying');
  assert.equal(api.status().phase, 'complete');
  assert.equal(api.status().runId, runs[0].runId);
  assert.deepEqual(api.status().completion, { cause: 'settings-save', beforeReady: false });
  assert.equal(controlled.host.document.activeElement, hostFocus, 'saving restores host focus');

  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[0].runId, skipped: true }, firstFrame.contentWindow);
  assert.deepEqual(api.status().completion, { cause: 'settings-save', beforeReady: false },
    'a late old frame cannot replace the save result');
  assert.equal(api.openSettings(), true);
  assert.equal(runs[1].intent, 'settings');
  assert.ok(api.status().runId > runs[0].runId);
});

test('complete opens a settings-intent frame and cancellation preserves the saved state', () => {
  const controlled = controlledHost();
  const runs = [];
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runs.push(frameSpec);
    raf(() => SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId }));
    return { dispose() {} };
  };
  payload.assets = { fixture: true };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  controlled.frames[0].contentWindow.flushAnimationFrame();
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[0].runId, skipped: false }, controlled.frames[0].contentWindow);
  assert.equal(api.status().phase, 'complete');
  assert.equal(controlled.frames[0].removed, true);

  controlled.controls.find(node => node.tagName === 'button').click();
  assert.equal(controlled.frames.length, 2);
  assert.equal(runs[1].intent, 'settings');
  assert.ok(runs[1].runId > runs[0].runId);
  assert.equal(runs[1].assets, payload.assets);
  assert.equal(api.status().phase, 'loading');
  controlled.frames[1].contentWindow.flushAnimationFrame();
  assert.equal(api.status().phase, 'settings', 'settings ready never enters playing');

  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[1].runId, skipped: true }, controlled.frames[1].contentWindow);
  assert.equal(api.status().phase, 'complete');
  assert.deepEqual(api.status().completion, { cause: 'settings-cancel', beforeReady: false });
  assert.equal(controlled.frames[1].removed, true);
});

test('a missing body uses a temporary observer within the original loading deadline', () => {
  const controlled = controlledHost({ body: false });
  installStartup(function () {}, controlled.host, pageAdapter);
  assert.equal(controlled.frames.length, 0);
  assert.equal(controlled.timers.length, 1);
  assert.equal(controlled.timers[0].delay, 25_000);
  assert.equal(controlled.observers.length, 1);
  assert.equal(controlled.observers[0].observing, true);

  controlled.setBody();
  assert.equal(controlled.frames.length, 1);
  assert.equal(controlled.observers[0].disconnected, true);
  controlled.host.__azhouStartup.dispose();
  assert.equal(controlled.observers[0].disconnected, true);
});

test('body wait expiry uses the same run transition and cannot mount later', () => {
  const controlled = controlledHost({ body: false });
  installStartup(function () {}, controlled.host, pageAdapter);
  const runId = controlled.host.__azhouStartup.status().runId;
  controlled.timers[0].callback();
  assert.deepEqual(controlled.host.__azhouStartup.status(), {
    owner: 'azhou-codex-startup', version: 1, phase: 'timeout', runId,
    ready: false, completed: false, overlay: false, reason: 'overlay-timeout',
    wallpaper: { applied: false, reason: '', imageDecoded: false }, completion: null,
  });
  assert.equal(controlled.observers[0].disconnected, true);
  controlled.setBody();
  assert.equal(controlled.frames.length, 0);
});

test('wallpaper can finish after natural playback but is cancelled by skip or disposal', async () => {
  for (const completion of ['natural', 'skip', 'dispose']) {
    const controlled = controlledHost();
    let finishWallpaper, stillCurrent;
    const runs = [];
    const payload = (...args) => {
      const SEND = args[13], frameSpec = args[14];
      runs.push(frameSpec);
      SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
        image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
      return { dispose() {} };
    };
    payload.applyWallpaper = (_request, isCurrent) => new Promise(resolve => {
      stillCurrent = isCurrent;
      finishWallpaper = resolve;
    });
    installStartup(payload, controlled.host, pageAdapter);
    const api = controlled.host.__azhouStartup;
    const source = controlled.frames[0].contentWindow;
    controlled.host.send({ type: 'azhou-startup', action: 'ready', runId: runs[0].runId }, source);
    if (completion === 'dispose') api.dispose();
    else controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[0].runId,
      skipped: completion === 'skip' }, source);
    assert.equal(stillCurrent(), completion === 'natural', completion);
    finishWallpaper({ applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-timeout' });
    await Promise.resolve();
    await Promise.resolve();
    if (completion === 'natural') assert.equal(api.status().wallpaper.failureCode, 'shell-timeout');
    api.dispose();
  }
});

test('a late wallpaper callback cannot update a disposed run', async () => {
  const controlled = controlledHost();
  let finishWallpaper;
  let stillCurrent;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    raf(() => SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId }));
    return { dispose() {} };
  };
  payload.applyWallpaper = (_background, isCurrent) => new Promise((resolve) => {
    stillCurrent = isCurrent;
    finishWallpaper = resolve;
  });
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  const frame = controlled.frames[0];
  frame.contentWindow.flushAnimationFrame();
  assert.equal(api.status().phase, 'playing');
  assert.equal(stillCurrent(), true);
  api.dispose();
  assert.equal(stillCurrent(), false);
  finishWallpaper({ applied: true });
  await Promise.resolve();
  assert.equal(Object.hasOwn(controlled.host, '__azhouStartup'), false);
  assert.equal(frame.removed, true);
  assert.equal(controlled.listenerCount(), 0);
  assert.equal(controlled.keyListenerCount(), 0);
  assert.equal(controlled.timers[0].cleared, true);
});

test('a newer disabled background invalidates an earlier decode within the same run', async () => {
  const controlled = controlledHost();
  let isCurrent;
  let release;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    raf(() => SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId }));
    return { dispose() {} };
  };
  payload.applyWallpaper = (_background, current) => new Promise(resolve => { isCurrent = current; release = resolve; });
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  const frame = controlled.frames[0];
  assert.equal(isCurrent(), true);
  frame.contentWindow.flushAnimationFrame();
  controlled.host.send({ type: 'azhou-startup', action: 'background', runId: api.status().runId,
    image: 'data:image/png;base64,aGVsbG8=', strength: 0 }, frame.contentWindow);
  assert.equal(api.status().wallpaper.reason, 'disabled');
  assert.equal(isCurrent(), false, 'strength zero supersedes pending wallpaper work');
  release({ applied: true });
  await Promise.resolve();
  assert.equal(api.status().wallpaper.reason, 'disabled');
});

test('a fresh settings frame restores its captured host focus without stealing a later focus change', () => {
  const controlled = controlledHost();
  const hostInput = { isConnected: true, focusCount: 0,
    focus() { this.focusCount += 1; controlled.host.document.activeElement = this; } };
  const laterButton = { isConnected: true, focusCount: 0,
    focus() { this.focusCount += 1; controlled.host.document.activeElement = this; } };
  controlled.host.document.activeElement = { isConnected: true, focus() {} };
  const runs = [];
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runs.push(frameSpec);
    raf(() => SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId }));
    return { dispose() {} };
  };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  controlled.frames[0].contentWindow.flushAnimationFrame();
  controlled.host.document.activeElement = hostInput;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[0].runId, skipped: false },
    controlled.frames[0].contentWindow);

  assert.equal(api.openSettings(), true);
  controlled.frames[1].contentWindow.flushAnimationFrame();
  controlled.host.document.activeElement = controlled.frames[1];
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[1].runId, skipped: true },
    controlled.frames[1].contentWindow);
  assert.equal(controlled.host.document.activeElement, hostInput,
    'cancel restores the host control focused immediately before the settings iframe opened');
  assert.equal(hostInput.focusCount, 1);

  assert.equal(api.openSettings(), true);
  controlled.frames[2].contentWindow.flushAnimationFrame();
  controlled.host.document.activeElement = controlled.frames[2];
  controlled.host.document.activeElement = laterButton;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[2].runId, skipped: true },
    controlled.frames[2].contentWindow);
  assert.equal(controlled.host.document.activeElement, laterButton,
    'cleanup does not replace a later host focus change');
  assert.equal(laterButton.focusCount, 0);
});

test('only the exact supported wallpaper owner is composed and disposed', () => {
  const unknown = controlledHost();
  let unknownDisposals = 0;
  unknown.host.__azhouWallpaper = {
    owner: 'azhou.codex-startup-animation', version: '0.7.0',
    status: () => ({ applied: true }), dispose() { unknownDisposals += 1; },
  };
  assert.deepEqual(installStartup(function () {}, unknown.host, pageAdapter), {
    installed: false, alreadyActive: false, reason: 'owner-conflict',
  });
  assert.equal(unknown.frames.length, 0);
  assert.equal(unknownDisposals, 0);

  const supported = controlledHost();
  let legacyDisposals = 0;
  supported.host.__azhouWallpaper = {
    owner: 'azhou.codex-startup-animation', version: '0.7.1',
    status: () => ({ applied: true, imageDecoded: true, reason: '' }),
    dispose() { legacyDisposals += 1; },
  };
  assert.deepEqual(installStartup(function () {}, supported.host, pageAdapter), { installed: true, alreadyActive: false });
  assert.equal(supported.host.__azhouStartup.status().wallpaper.applied, true);
  supported.host.__azhouStartup.dispose();
  assert.equal(legacyDisposals, 1);
});

test('a failed wallpaper can be retried by the completed controller without replaying startup', async () => {
  const controlled = controlledHost();
  const image = 'data:image/png;base64,aGVsbG8=';
  const strengths = [];
  const runs = [];
  let initialWallpaper;
  let attempts = 0;
  const wallpaperAPI = {
    owner: 'azhou.codex-startup-animation', version: '0.7.1',
    status: () => ({ applied: true, imageDecoded: true, reason: '' }), dispose() {},
  };
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runs.push(frameSpec);
    initialWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image, strength: 42 });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = async (background, isCurrent) => {
    attempts += 1;
    strengths.push(background.strength);
    assert.equal(background.image, image);
    assert.equal(isCurrent(), true);
    if (attempts === 1) {
      controlled.host.__azhouWallpaper = wallpaperAPI;
      return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'styles-not-effective' };
    }
    controlled.host.__azhouWallpaper = {
      owner: 'azhou.codex-startup-animation', version: '0.7.1',
      status: () => ({ applied: true, imageDecoded: true, reason: '' }), dispose() {},
    };
    return { applied: true };
  };

  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  const originalFrame = controlled.frames[0];
  const originalRunId = api.status().runId;
  await initialWallpaper;
  assert.deepEqual(api.status().wallpaper, {
    applied: false, reason: 'wallpaper-unsupported', imageDecoded: false,
    failureStage: 'styles', failureCode: 'styles-not-effective',
  });
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: originalRunId, skipped: false },
    originalFrame.contentWindow);
  assert.equal(api.status().phase, 'complete');

  const retried = await api.retryWallpaper();
  assert.equal(retried.retried, true);
  assert.deepEqual(retried.previousFailure, {
    reason: 'wallpaper-unsupported', failureStage: 'styles', failureCode: 'styles-not-effective',
  });
  assert.equal(retried.wallpaper.applied, true);
  assert.equal(api.status().phase, 'complete');
  assert.equal(api.status().runId, originalRunId);
  assert.equal(controlled.host.__azhouStartup, api);
  assert.equal(controlled.frames.length, 1);
  assert.equal(originalFrame.removed, true);
  assert.equal(runs.length, 1, 'retry must not recreate the startup animation');

  const repeated = await api.retryWallpaper();
  assert.equal(repeated.retried, false);
  assert.equal(repeated.reason, 'already-applied');
  assert.equal(attempts, 2);
  assert.deepEqual(strengths, [42, 42], 'retry reuses the last validated strength');
});

test('status, retry, and dispose refuse an externally replaced same-owner wallpaper API', async () => {
  const controlled = controlledHost();
  let initialWallpaper;
  let attempts = 0;
  let foreignDisposals = 0;
  const ownedWallpaperAPI = {
    owner: 'azhou.codex-startup-animation', version: '0.7.1',
    status: () => ({ applied: true, imageDecoded: true, reason: '' }), dispose() {},
  };
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    initialWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = () => {
    attempts += 1;
    controlled.host.__azhouWallpaper = ownedWallpaperAPI;
    return { applied: true };
  };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  await initialWallpaper;
  const runId = api.status().runId;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false },
    controlled.frames[0].contentWindow);
  assert.equal(api.status().wallpaper.applied, true);

  controlled.host.__azhouWallpaper = {
    owner: 'azhou.codex-startup-animation', version: '0.7.1',
    status: () => ({ applied: true, imageDecoded: true, reason: '' }),
    dispose() { foreignDisposals += 1; },
  };
  assert.equal(api.status().wallpaper.reason, 'owner-conflict');
  assert.equal((await api.retryWallpaper()).reason, 'unknown-owner');
  api.dispose();
  assert.equal(attempts, 1);
  assert.equal(foreignDisposals, 0);
});

test('startup wallpaper failure is announced at the entry and the UI retry clears it without replay', async () => {
  const controlled = controlledHost();
  const senders = [];
  let initialWallpaper;
  let attempts = 0;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    senders.push({ SEND, frameSpec });
    if (frameSpec.intent === 'play') {
      initialWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
        image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    }
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = () => {
    attempts += 1;
    if (attempts === 1) {
      return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-unsupported' };
    }
    controlled.host.__azhouWallpaper = {
      owner: 'azhou.codex-startup-animation', version: '0.7.1',
      status: () => ({ applied: true, imageDecoded: true, reason: '' }), dispose() {},
    };
    return { applied: true };
  };

  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  await initialWallpaper;
  const runId = api.status().runId;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false },
    controlled.frames[0].contentWindow);

  const recovery = controlled.controls.find(node => node.attributes?.has('data-agent-skin-wallpaper-recovery'));
  const retryButton = controlled.controls.find(node => node.attributes?.has('data-agent-skin-wallpaper-retry'));
  assert.equal(recovery.style.display, 'block');
  assert.equal(recovery.children[0].textContent, '启动背景未应用');
  assert.equal(recovery.children[1].textContent, '当前页面暂时无法监测可用的工作区背景区域。');
  assert.equal(retryButton.attributes.get('aria-label'), '重试启动背景');
  assert.equal(senders.length, 1, 'startup failure leaves the original run and appearance entry in place');

  retryButton.click();
  const retry = await api.retryWallpaper();
  assert.equal(retry.retried, true);
  assert.equal(retry.wallpaper.applied, true);
  assert.equal(attempts, 2);
  assert.equal(api.status().runId, runId);
  assert.equal(controlled.frames.length, 1, 'the retry does not create another startup frame');
  assert.equal(recovery.style.display, 'none', 'success removes the startup error from the existing entry');
  assert.equal(controlled.controls.find(node => node.attributes?.has('data-agent-skin-wallpaper-live'))
    .textContent, '启动背景已应用。');
  api.dispose();
});

test('settings wallpaper failure stays with the settings run and cannot replace startup recovery', async () => {
  const controlled = controlledHost();
  const senders = [];
  let initialWallpaper;
  let attempts = 0;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    senders.push({ SEND, frameSpec });
    if (frameSpec.intent === 'play') {
      initialWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
        image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    }
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = () => {
    attempts += 1;
    return { applied: false, reason: 'wallpaper-unsupported',
      failureCode: attempts === 1 ? 'shell-unsupported' : 'image-decode-failed' };
  };

  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  await initialWallpaper;
  const startupRunId = api.status().runId;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: startupRunId, skipped: false },
    controlled.frames[0].contentWindow);
  const recovery = controlled.controls.find(node => node.attributes?.has('data-agent-skin-wallpaper-recovery'));
  const reason = controlled.controls.find(node => node.attributes?.has('data-agent-skin-wallpaper-reason'));
  assert.equal(recovery.style.display, 'block');
  assert.match(reason.textContent, /工作区背景区域/);

  appearanceButton(controlled).click();
  assert.equal(api.status().phase, 'settings');
  const settingsRunId = api.status().runId;
  assert.ok(settingsRunId > startupRunId);
  const settingsWallpaper = await senders[1].SEND({ type: 'azhou-startup', action: 'background',
    runId: settingsRunId, image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
  assert.equal(settingsWallpaper.failureCode, 'image-decode-failed');
  assert.equal(api.status().phase, 'settings');
  assert.equal(recovery.style.display, 'none', 'the settings error is not copied into the startup entry');
  assert.match(reason.textContent, /工作区背景区域/,
    'the settings failure does not replace the prior startup reason stored for its own notice');

  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: settingsRunId, skipped: true },
    controlled.frames[1].contentWindow);
  assert.equal(api.status().completion.cause, 'settings-cancel');
  assert.equal(recovery.style.display, 'block', 'canceling settings restores only the original startup notice');
  assert.match(reason.textContent, /工作区背景区域/);
  api.dispose();
});

test('wallpaper retry refuses disabled, missing, and unknown-owner requests', async () => {
  const noRequest = controlledHost();
  const noRequestPayload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  installStartup(noRequestPayload, noRequest.host, pageAdapter);
  const noRequestAPI = noRequest.host.__azhouStartup;
  const noRequestRun = noRequestAPI.status().runId;
  noRequest.host.send({ type: 'azhou-startup', action: 'complete', runId: noRequestRun, skipped: false },
    noRequest.frames[0].contentWindow);
  assert.equal((await noRequestAPI.retryWallpaper()).reason, 'no-request');
  assert.equal(noRequest.frames.length, 1);

  const disabled = controlledHost();
  let disabledWallpaper;
  let disabledApplies = 0;
  const disabledPayload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    disabledWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 0 });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  disabledPayload.applyWallpaper = () => { disabledApplies += 1; };
  installStartup(disabledPayload, disabled.host, pageAdapter);
  const disabledAPI = disabled.host.__azhouStartup;
  await disabledWallpaper;
  const disabledRun = disabledAPI.status().runId;
  disabled.host.send({ type: 'azhou-startup', action: 'complete', runId: disabledRun, skipped: false },
    disabled.frames[0].contentWindow);
  assert.equal((await disabledAPI.retryWallpaper()).reason, 'disabled');
  assert.equal(disabledApplies, 0);

  const unknown = controlledHost();
  let attempts = 0;
  let unknownWallpaper;
  const unknownPayload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    unknownWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  unknownPayload.applyWallpaper = () => {
    attempts += 1;
    return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-unsupported' };
  };
  installStartup(unknownPayload, unknown.host, pageAdapter);
  const unknownAPI = unknown.host.__azhouStartup;
  await unknownWallpaper;
  const unknownRun = unknownAPI.status().runId;
  unknown.host.send({ type: 'azhou-startup', action: 'complete', runId: unknownRun, skipped: false },
    unknown.frames[0].contentWindow);
  let unknownDisposals = 0;
  unknown.host.__azhouWallpaper = {
    owner: 'someone-else', version: '9', status: () => ({ applied: true }),
    dispose() { unknownDisposals += 1; },
  };
  assert.equal((await unknownAPI.retryWallpaper()).reason, 'unknown-owner');
  assert.equal(attempts, 1);
  assert.equal(unknownDisposals, 0);
  assert.equal(unknown.frames.length, 1);
});

test('wallpaper exceptions retain only whitelisted failure codes and mapped stages', async () => {
  const controlled = controlledHost();
  let wallpaperRequest;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    wallpaperRequest = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = () => {
    const error = new Error('private filesystem path /Users/private/image.png');
    error.code = 'shell-timeout';
    throw error;
  };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  await wallpaperRequest;
  assert.deepEqual(api.status().wallpaper, {
    applied: false, reason: 'wallpaper-unsupported', imageDecoded: false,
    failureStage: 'shell', failureCode: 'shell-timeout',
  });
});

test('concurrent wallpaper retries share one attempt and a new settings run cancels it', async () => {
  const controlled = controlledHost();
  let initialWallpaper;
  let finishRetry;
  let retryIsCurrent;
  let attempts = 0;
  const runs = [];
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    runs.push(frameSpec);
    if (frameSpec.intent === 'play') {
      initialWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
        image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    }
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = (_background, isCurrent) => {
    attempts += 1;
    if (attempts === 1) return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-failed' };
    retryIsCurrent = isCurrent;
    return new Promise(resolve => { finishRetry = resolve; });
  };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  await initialWallpaper;
  const originalRun = api.status().runId;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: originalRun, skipped: false },
    controlled.frames[0].contentWindow);

  const retry = api.retryWallpaper();
  const concurrentRetry = api.retryWallpaper();
  assert.equal(attempts, 2, 'concurrent calls only invoke applyWallpaper once');
  assert.equal(api.openSettings(), true);
  assert.ok(api.status().runId > originalRun);
  assert.equal(retryIsCurrent(), false, 'opening settings invalidates the pending retry');
  const result = await retry;
  const concurrentResult = await concurrentRetry;
  assert.equal(result.reason, 'operation-cancelled');
  assert.deepEqual(concurrentResult, result);
  finishRetry({ applied: true });
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(api.status().phase, 'settings');
  assert.equal(api.status().wallpaper.failureCode, 'apply-failed');
  assert.equal(attempts, 2);
  assert.equal(runs.length, 2, 'only the explicit settings action creates a second frame');
  api.dispose();
});

test('wallpaper retry times out and a late result cannot revive the canceled attempt', async () => {
  const controlled = controlledHost();
  let initialWallpaper;
  let finishRetry;
  let retryIsCurrent;
  let attempts = 0;
  const payload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    initialWallpaper = SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  payload.applyWallpaper = (_background, isCurrent) => {
    attempts += 1;
    if (attempts === 1) return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-failed' };
    retryIsCurrent = isCurrent;
    return new Promise(resolve => { finishRetry = resolve; });
  };
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  await initialWallpaper;
  const runId = api.status().runId;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId, skipped: false },
    controlled.frames[0].contentWindow);

  const retry = api.retryWallpaper();
  const retryTimer = controlled.timers.at(-1);
  assert.equal(retryTimer.delay, 10_000);
  retryTimer.callback();
  const result = await retry;
  assert.equal(result.retried, true);
  assert.equal(result.reason, 'timeout');
  assert.equal(result.wallpaper.failureCode, 'retry-timeout');
  assert.equal(retryIsCurrent(), false);
  assert.equal((await api.retryWallpaper()).reason, 'timeout', 'a still-running helper is not duplicated');
  assert.equal(attempts, 2);

  finishRetry({ applied: true });
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(api.status().wallpaper.failureCode, 'retry-timeout');
  assert.equal(api.status().wallpaper.applied, false);
  api.dispose();
});

test('a missing page adapter refuses installation before any page work', () => {
  const controlled = controlledHost();
  const document = controlled.host.document;
  const createElement = document.createElement;
  let createdElements = 0;
  document.createElement = (...args) => {
    createdElements += 1;
    return createElement(...args);
  };
  assert.deepEqual(installStartup(function () {}, controlled.host), {
    installed: false, alreadyActive: false, reason: 'page-unsupported',
  });
  assert.equal(createdElements, 0, 'no DOM element is created without a bound page adapter');
  assert.equal(controlled.frames.length, 0, 'no overlay frame is mounted');
  assert.equal(Object.getOwnPropertyDescriptor(controlled.host, '__azhouStartup'), undefined,
    'no controller global is defined');
});

test('a wrong page identified through the adapter performs zero page operations', () => {
  const wrong = controlledHost();
  wrong.host.location = new URL('app://-/index.html?initialRoute=%2Fquick-chat');
  const document = wrong.host.document;
  const createElement = document.createElement;
  let createdElements = 0;
  let definePropertyCalls = 0;
  document.createElement = (...args) => {
    createdElements += 1;
    return createElement(...args);
  };
  const host = wrong.host;
  const defineProperty = Object.defineProperty;
  const instrumentedHost = new Proxy(host, {
    defineProperty(target, key, descriptor) {
      definePropertyCalls += 1;
      return defineProperty(target, key, descriptor);
    },
  });
  assert.deepEqual(installStartup(function () {}, instrumentedHost, pageAdapter), {
    installed: false, alreadyActive: false, reason: 'page-unsupported',
  });
  assert.equal(createdElements, 0, 'a wrong page creates no DOM element');
  assert.equal(definePropertyCalls, 0, 'a wrong page defines no controller global');
  assert.equal(wrong.frames.length, 0, 'a wrong page mounts no frame and opens no database');
});

test('an adapter-injected settings environment supplies the frame indexedDB', () => {
  const controlled = controlledHost();
  const sentinelIndexedDB = { __adapterInjected: true };
  const adapter = Object.freeze({
    identify: host2 => pageAdapter.identify(host2),
    observeAppearance: host2 => pageAdapter.observeAppearance(host2),
    appearanceText: (...args) => pageAdapter.appearanceText(...args),
    mountEntry: (...args) => pageAdapter.mountEntry(...args),
    settingsEnvironment: () => ({ indexedDB: sentinelIndexedDB }),
  });
  let observedIndexedDB;
  const result = installStartup(function (_window, _document, _location, _performance, indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _set, _clear, _module, send, frameSpec) {
    observedIndexedDB = indexedDB;
    send({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
    send({ type: 'azhou-startup', action: 'complete', runId: frameSpec.runId, skipped: false });
  }, controlled.host, adapter);
  assert.deepEqual(result, { installed: true, alreadyActive: false });
  assert.equal(observedIndexedDB, sentinelIndexedDB,
    'the settings environment injection seam carries the adapter-provided indexedDB');
  controlled.host.__azhouStartup.dispose();
});

test('a late asynchronous wallpaper result cannot complete or resurrect a disposed run', async () => {
  const controlled = controlledHost();
  let finishApply;
  const payload = function (...args) {
    const send = args[13];
    const frameSpec = args[14];
    send({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    send({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
    send({ type: 'azhou-startup', action: 'complete', runId: frameSpec.runId, skipped: false });
  };
  payload.applyWallpaper = () => new Promise(resolve => { finishApply = resolve; });
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  assert.equal(api.status().phase, 'complete');
  const disposedRunId = api.status().runId;
  api.dispose();
  assert.equal(api.status().phase, 'disposed');
  finishApply({ applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-timeout' });
  await new Promise(resolve => setImmediate(resolve));
  const late = api.status();
  assert.equal(late.phase, 'disposed', 'a late wallpaper result cannot resurrect a disposed run');
  assert.equal(late.runId, disposedRunId, 'a late wallpaper result cannot renumber the disposed run');
  assert.equal(late.wallpaper.applied, false);
  assert.equal(controlled.frames[0].removed, true, 'the overlay frame stays removed after dispose');
});

test('a partially failed wallpaper application reports its recovery state and stays retryable', async () => {
  const controlled = controlledHost();
  const image = 'data:image/png;base64,aGVsbG8=';
  let applyResult = { applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-timeout' };
  const payload = function (...args) {
    const send = args[13];
    const frameSpec = args[14];
    send({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId, image, strength: 42 });
    send({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
    send({ type: 'azhou-startup', action: 'complete', runId: frameSpec.runId, skipped: false });
  };
  payload.applyWallpaper = () => Promise.resolve(applyResult);
  const wallpaperAPI = {
    owner: 'azhou.codex-startup-animation', version: '0.7.1',
    status: () => ({ applied: false, imageDecoded: true, reason: '' }), dispose() {},
  };
  controlled.host.__azhouWallpaper = wallpaperAPI;
  installStartup(payload, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  await new Promise(resolve => setImmediate(resolve));
  const failed = api.status().wallpaper;
  assert.equal(failed.applied, false);
  assert.equal(failed.failureCode, 'shell-timeout');
  assert.equal(failed.failureStage, 'shell');
  // The saved request stays recorded: recovery reports what failed and keeps retry available.
  const retry = await api.retryWallpaper();
  assert.equal(retry.retried, true, 'the recovery entry keeps the failed request retryable');
  assert.equal(retry.wallpaper.applied, false);
  assert.equal(retry.wallpaper.failureCode, 'shell-timeout',
    'a retry that fails again keeps reporting the real recovery state');
  assert.equal(api.status().phase, 'complete', 'recovery does not replay the startup run');
  assert.equal(controlled.frames.length, 1, 'recovery does not remount the startup overlay');
  assert.equal(retry.previousFailure.failureCode, 'shell-timeout',
    'the retry result reports the failure it recovered from');
  api.dispose();
});

test('the codex page adapter exposes its host strategy seam explicitly', () => {
  const adapter = createCodexPageAdapter(globalThis);
  const controlled = controlledHost();
  const identification = adapter.identify(controlled.host);
  assert.equal(identification.kind, 'matched');
  assert.equal(identification.documentToken, adapter.identify(controlled.host).documentToken);
  assert.deepEqual(adapter.identify({ location: { href: 'not a url' } }),
    { kind: 'unmatched', reason: 'page-unsupported' });
  assert.deepEqual(adapter.identify(undefined), { kind: 'unmatched', reason: 'page-unsupported' });
  const pluginHost = { location: new URL('app://-/index.html?initialRoute=%2Favatar') };
  assert.equal(adapter.identify(pluginHost).kind, 'unmatched',
    'a plugin route is not the main page');

  const appearance = adapter.observeAppearance(controlled.host);
  assert.equal(appearance.theme, 'light');
  assert.equal(appearance.locale, 'zh-CN');
  assert.ok(appearance.colors.surface, 'the appearance fallback surface stays available');

  const sentinel = {};
  assert.deepEqual(adapter.settingsEnvironment({ indexedDB: sentinel }), { indexedDB: sentinel });
  assert.deepEqual(adapter.settingsEnvironment(), { indexedDB: globalThis.indexedDB });

  const registered = [];
  const withRegistry = createCodexPageAdapter(globalThis, {},
    { registerCleanup: resource => registered.push(resource) });
  const resource = { key: 'adapter-resource', dispose: () => {} };
  assert.equal(withRegistry.registerCleanup(resource), true);
  assert.deepEqual(registered, [resource]);
  assert.equal(withRegistry.registerCleanup(null), false, 'malformed resources are refused');
  assert.equal(adapter.registerCleanup(resource), false,
    'without a controller registry the adapter refuses to own a second lifecycle');

  const mounted = controlledHost();
  mounted.host.document.documentElement.lang = 'en-US';
  // Known limit (C0): mountEntry takes no cleanup registry — the entry node stays
  // owned by the controller's dispose path, so there is no entry resource to register.
  assert.equal(adapter.mountEntry.length, 8, 'mountEntry exposes the controller-owned entry surface only');
  const entry = adapter.mountEntry(mounted.host.document, () => {}, null, undefined,
    adapter.observeAppearance(mounted.host), mounted.host, () => {}, () => {});
  assert.equal(typeof entry.remove, 'function');
  assert.doesNotThrow(() => entry.remove());
});


test('explicit DSH owner is independent and cannot adopt a Codex controller', () => {
  const adapter = Object.freeze({ ...pageAdapter, controllerOwner: 'azhou-dsh-startup',
    controllerWallpaper: Object.freeze({ owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: true }),
    controllerMetadata: { controllerInstanceID: '11111111-1111-4111-8111-111111111111', createdByOperationID: '22222222-2222-4222-8222-222222222222', payloadSHA256: 'a'.repeat(64), documentToken: 'synthetic-CDP-unique-context' } });
  const host = controlledHost().host;
  assert.equal(installStartup(function () {}, host, adapter).installed, true);
  assert.equal(host.__azhouStartup.owner, 'azhou-dsh-startup');
  assert.equal(host.__azhouStartup.status().owner, 'azhou-dsh-startup');
  assert.equal(installStartup(function () {}, host, adapter).alreadyActive, true);
  assert.equal(installStartup(function () {}, host, pageAdapter).reason, 'owner-conflict');
  host.__azhouStartup.dispose();
  assert.equal(installStartup(function () {}, host, pageAdapter).installed, true);
  assert.equal(host.__azhouStartup.owner, 'azhou-codex-startup');
  host.__azhouStartup.dispose();
});

test('unsupported or accessor controller owners refuse without page writes', () => {
  for (const descriptor of [{ value: 'other' }, { get() { throw Error('must not read getter'); } }]) {
    const controlled = controlledHost();
    const adapter = { ...pageAdapter };
    Object.defineProperty(adapter, 'controllerOwner', descriptor);
    assert.equal(installStartup(function () {}, controlled.host, adapter).reason, 'owner-conflict');
    assert.equal(controlled.frames.length, 0);
    assert.equal(Object.hasOwn(controlled.host, '__azhouStartup'), false);
  }
});

test('host settings namespace reaches the actual factory while legacy identity is unchanged', () => {
  const namespace = Object.freeze({ databaseName: 'azhou-synthetic-startup', databaseVersion: 1,
    storeName: 'settings', settingsKey: 'images' });
  for (const custom of [false, true]) {
    const controlled = controlledHost();
    const adapter = custom ? Object.freeze({ ...pageAdapter,
      settingsEnvironment: source => ({ indexedDB: source.indexedDB, settingsNamespace: namespace }) }) : pageAdapter;
    const factory = input => input;
    let observed;
    const payload = (...args) => { observed = args[15]; };
    payload.createImageSettings = factory;
    assert.equal(installStartup(payload, controlled.host, adapter).installed, true);
    const input = { document: 'synthetic-document', indexedDB: 'synthetic-idb' };
    assert.equal(controlled.frames[0].attributes.has('data-agent-skin-controller-instance'), false);
    assert.equal(controlled.controls.some(node => node.attributes?.has('data-agent-skin-controller-instance')), false);
    assert.equal(observed === factory, !custom);
    const result = observed(input);
    assert.equal(result.settingsNamespace, custom ? namespace : undefined);
    assert.equal(result.indexedDB, input.indexedDB);
    controlled.host.__azhouStartup.dispose();
  }
});


test('controller metadata is validated before writes and retained by the actual controller', () => {
  const metadata = { controllerInstanceID: '11111111-1111-4111-8111-111111111111',
    createdByOperationID: '22222222-2222-4222-8222-222222222222', payloadSHA256: 'a'.repeat(64),
    documentToken: 'synthetic-CDP-unique-context' };
  for (const bad of [undefined, {}, { ...metadata, payloadSHA256: 'wrong' },
    { ...metadata, documentToken: '' }, { ...metadata, payloadSHA256: metadata.payloadSHA256 + '\n' },
    { ...metadata, controllerInstanceID: metadata.controllerInstanceID + '\n' }, { ...metadata, controllerInstanceID: 'legacy-v1-unreported' }]) {
    const controlled = controlledHost();
    const adapter = { ...pageAdapter, controllerOwner: 'azhou-dsh-startup',
      controllerWallpaper: Object.freeze({ owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: true }), controllerMetadata: bad };
    assert.equal(installStartup(function () {}, controlled.host, adapter).reason, 'controller-metadata-invalid');
    assert.equal(controlled.frames.length, 0);
  }
  const controlled = controlledHost();
  const adapter = { ...pageAdapter, controllerOwner: 'azhou-dsh-startup',
    controllerWallpaper: Object.freeze({ owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: true }), controllerMetadata: metadata };
  assert.equal(installStartup(function () {}, controlled.host, adapter).installed, true);
  assert.equal(controlled.frames[0].attributes.get('data-agent-skin-controller-instance'), metadata.controllerInstanceID);
  assert.equal(controlled.controls.filter(node => node.attributes?.get('data-agent-skin-controller-instance') === metadata.controllerInstanceID).length, 1);
  metadata.documentToken = 'changed-after-install';
  assert.equal(controlled.host.__azhouStartup.status().documentToken, 'synthetic-CDP-unique-context');
  assert.equal(controlled.host.__azhouStartup.controllerInstanceID, metadata.controllerInstanceID);
  assert.equal(controlled.host.__azhouStartup.status().payloadSHA256, metadata.payloadSHA256);
  controlled.host.__azhouStartup.dispose();
});

test('mountSettings joins the controller api additively and stays inert without wallpaper ports', () => {
  const controlled = controlledHost();
  installStartup(function () {}, controlled.host, pageAdapter);
  const api = controlled.host.__azhouStartup;
  assert.deepEqual(Object.keys(api), ['owner', 'version', 'install', 'status',
    'beginSettingsSnapshot', 'prepareWorkspace', 'cancelWorkspace', 'readSettingsSnapshotChunk', 'disposeSettingsSnapshot',
    'openSettings', 'mountSettings', 'retryWallpaper', 'dispose'],
  'controller APIs are additive and remain grouped on the single owner');
  const target = { children: [], appendChild(node) { this.children.push(node); node.parentNode = this; return node; } };
  assert.equal(api.mountSettings(target), null,
    'adapters without wallpaper ports keep the overlay as their only settings UX');
  assert.equal(target.children.length, 0, 'a gated-off mount never writes into the target');
  api.dispose();
});

test('mountSettings embeds the same panel into a host element and its disposer unwires everything', () => {
  const controlled = controlledHost();
  controlled.host.document.documentElement.lang = 'zh-CN';
  const specs = [];
  const payload = function (_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) {
    specs.push({ spec, send });
    if (spec.intent === 'settings') return { updateAppearance() {} };
  };
  const adapter = { ...pageAdapter, controllerOwner: 'azhou-dsh-startup',
    controllerWallpaper: Object.freeze({ owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: false }),
    wallpaper: Object.freeze({ validPage: () => true, shellState: () => 'ready', surfaces: () => [],
      attributes: Object.freeze({ surfaceMarker: 'data-x', observeFilter: [] }), css: '', scope: 'test' }) };
  installStartup(payload, controlled.host, adapter);
  const api = controlled.host.__azhouStartup;
  const target = { children: [], appendChild(node) { this.children.push(node); node.parentNode = this; return node; } };
  const listenersBefore = controlled.listenerCount();
  let closed = 0;
  const dispose = api.mountSettings(target, { onClose: () => { closed += 1; } });
  assert.equal(typeof dispose, 'function', 'an admitted host gets a disposer');
  assert.equal(target.children.length, 1, 'the embed mounts exactly one iframe into the target');
  const embed = target.children[0];
  assert.equal(embed.style.cssText, 'display:block;width:100%;height:100%;border:0;background:transparent',
    'the embed fills its container without overlay positioning or backdrop');
  assert.equal(embed.attributes.get('title'), '阿舟主题与外观', 'the embed carries the appearance label');
  assert.equal(api.mountSettings(null), null, 'a missing target is refused');
  assert.equal(api.mountSettings({ appendChild: 'not a function' }), null, 'a non-element target is refused');
  assert.equal(specs.length, 2, 'one overlay run and one embed mount');
  const mountSpec = specs[1].spec;
  assert.equal(specs[0].spec.intent, 'play');
  assert.equal(mountSpec.intent, 'settings', 'the embed starts straight in the settings intent');
  assert.notEqual(mountSpec.runId, specs[0].spec.runId, 'the embed runs on its own run id');

  // Overlay isolation: embed traffic never moves the startup state machine.
  assert.equal(api.status().phase, 'loading');
  controlled.host.send({ type: 'azhou-startup', action: 'ready', runId: mountSpec.runId }, embed.contentWindow);
  assert.equal(api.status().phase, 'loading', 'an embed ready never completes the overlay run');
  controlled.host.send({ type: 'azhou-startup', action: 'settings-close', runId: mountSpec.runId },
    controlled.frames[0].contentWindow);
  assert.equal(closed, 0, 'a foreign source cannot drive the embed close');

  // The panel's wallpaper request flows through the shared wallpaper pipeline.
  controlled.host.send({ type: 'azhou-startup', action: 'background', runId: mountSpec.runId,
    image: 'data:image/png;base64,AAAA', strength: 42 }, embed.contentWindow);
  assert.equal(api.status().wallpaper.failureCode, 'apply-unavailable',
    'the embed background request reaches the wallpaper pipeline');
  assert.equal(api.status().phase, 'loading', 'wallpaper application never moves the overlay run');

  // Appearance propagation reaches live embeds.
  controlled.setBody();
  assert.equal(embed.attributes.get('title'), '阿舟主题与外观', 'appearance refresh keeps the embed labeled');

  // Panel-driven close (save): host onClose fires once, frame removed, listener unwired.
  controlled.host.send({ type: 'azhou-startup', action: 'settings-close', runId: mountSpec.runId }, embed.contentWindow);
  assert.equal(closed, 1, 'the panel-driven close reaches the host onClose exactly once');
  assert.equal(embed.removed, true, 'the embed iframe is removed on the panel close');
  assert.equal(controlled.listenerCount(), listenersBefore, 'the embed message listener is unwired');
  dispose();
  dispose();
  assert.equal(controlled.listenerCount(), listenersBefore, 'the disposer is idempotent after a panel close');

  // A cancel (complete/skipped) closes the embed through the same path.
  const secondTarget = { children: [], appendChild(node) { this.children.push(node); node.parentNode = this; return node; } };
  const secondDispose = api.mountSettings(secondTarget);
  assert.equal(typeof secondDispose, 'function');
  const secondEmbed = secondTarget.children[0];
  const cancelSpec = specs[specs.length - 1].spec;
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: cancelSpec.runId, skipped: true },
    secondEmbed.contentWindow);
  assert.equal(secondEmbed.removed, true, 'a panel cancel removes the embed');
  assert.equal(closed, 1, 'without an onClose the cancel still tears down silently');
  secondDispose();

  const savedBody = controlled.host.document.body;
  controlled.host.document.body = null;
  assert.equal(api.mountSettings(secondTarget), null, 'a host without a document body refuses the embed');
  controlled.host.document.body = savedBody;
  api.dispose();
});

test('an embed assetError tears the embed down and reaches the host onClose once', () => {
  const controlled = controlledHost();
  controlled.host.document.documentElement.lang = 'zh-CN';
  const specs = [];
  const payload = function (_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) {
    specs.push({ spec, send });
    if (spec.intent === 'settings') return { updateAppearance() {} };
  };
  const adapter = { ...pageAdapter, controllerOwner: 'azhou-dsh-startup',
    controllerWallpaper: Object.freeze({ owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: false }),
    wallpaper: Object.freeze({ validPage: () => true, shellState: () => 'ready', surfaces: () => [],
      attributes: Object.freeze({ surfaceMarker: 'data-x', observeFilter: [] }), css: '', scope: 'test' }) };
  installStartup(payload, controlled.host, adapter);
  const api = controlled.host.__azhouStartup;

  // Pre-open failure: beginPrepare() can assetError before the panel opens
  // (localization unavailable) — the embed must not stay half-open.
  const target = { children: [], appendChild(node) { this.children.push(node); node.parentNode = this; return node; } };
  const listenersBefore = controlled.listenerCount();
  let closed = 0;
  const dispose = api.mountSettings(target, { onClose: () => { closed += 1; } });
  assert.equal(typeof dispose, 'function');
  const embed = target.children[0];
  const mountSpec = specs[specs.length - 1].spec;
  controlled.host.send({ type: 'azhou-startup', action: 'assetError', runId: mountSpec.runId,
    reason: 'localization-unavailable' }, embed.contentWindow);
  assert.equal(embed.removed, true, 'a pre-open assetError removes the embed iframe');
  assert.equal(closed, 1, 'the host onClose fires exactly once for a failed embed');
  assert.equal(controlled.listenerCount(), listenersBefore, 'the embed message listener is unwired');
  dispose();
  dispose();
  assert.equal(controlled.listenerCount(), listenersBefore, 'the disposer is idempotent after an assetError');

  // Post-open failure: any reason counts, once the panel is already up.
  const secondTarget = { children: [], appendChild(node) { this.children.push(node); node.parentNode = this; return node; } };
  const secondDispose = api.mountSettings(secondTarget);
  const secondEmbed = secondTarget.children[0];
  const secondSpec = specs[specs.length - 1].spec;
  controlled.host.send({ type: 'azhou-startup', action: 'ready', runId: secondSpec.runId }, secondEmbed.contentWindow);
  controlled.host.send({ type: 'azhou-startup', action: 'assetError', runId: secondSpec.runId,
    reason: 'asset-invalid' }, secondEmbed.contentWindow);
  assert.equal(secondEmbed.removed, true, 'a post-open assetError with any reason removes the embed');
  secondDispose();

  // A foreign source (the overlay frame) cannot close an embed via assetError.
  const thirdTarget = { children: [], appendChild(node) { this.children.push(node); node.parentNode = this; return node; } };
  const thirdDispose = api.mountSettings(thirdTarget);
  const thirdEmbed = thirdTarget.children[0];
  const thirdSpec = specs[specs.length - 1].spec;
  controlled.host.send({ type: 'azhou-startup', action: 'assetError', runId: thirdSpec.runId,
    reason: 'localization-unavailable' }, controlled.frames[0].contentWindow);
  assert.equal(thirdEmbed.removed, false, 'a foreign-source assetError never closes the embed');
  thirdDispose();
  api.dispose();
});

test('disposing the controller tears down live settings embeds and late frame handles still dispose', async () => {
  const controlled = controlledHost();
  let handleDisposed = 0;
  let releaseHandle;
  const payload = function (_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, _send, spec) {
    if (spec.intent !== 'settings') return undefined;
    return new Promise(resolve => { releaseHandle = resolve; });
  };
  const adapter = { ...pageAdapter, controllerOwner: 'azhou-dsh-startup',
    controllerWallpaper: Object.freeze({ owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: false }),
    wallpaper: Object.freeze({ validPage: () => true, shellState: () => 'ready', surfaces: () => [],
      attributes: Object.freeze({ surfaceMarker: 'data-x', observeFilter: [] }), css: '', scope: 'test' }) };
  installStartup(payload, controlled.host, adapter);
  const api = controlled.host.__azhouStartup;
  const target = { children: [], appendChild(node) { this.children.push(node); node.parentNode = this; return node; } };
  const before = controlled.listenerCount();
  const dispose = api.mountSettings(target);
  assert.equal(typeof dispose, 'function');
  assert.equal(target.children.length, 1);
  api.dispose();
  assert.equal(target.children[0].removed, true, 'the embed iframe is removed by controller teardown');
  assert.equal(controlled.listenerCount(), before - 1, 'the embed listener is unwired by controller teardown');
  dispose();
  releaseHandle({ dispose() { handleDisposed += 1; }, updateAppearance() {} });
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(handleDisposed, 1, 'a handle resolving after disposal is still disposed, once');
  assert.equal(api.mountSettings(target), null, 'a disposed controller never mounts new embeds');
});

function snapshotSettings(overrides = {}) {
  return Object.freeze({
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AA==',
    artwork: 'data:image/png;base64,AA==',
    contours: Object.freeze([Object.freeze([Object.freeze([0, 0]), Object.freeze([2, 2])])]),
    introTitle: '阿舟 AI 实验室',
    introCaption: 'AZHOU / AI LAB',
    artworkSubtitle: '和阿舟一起做出来。',
    wallpaperStrength: 42,
    ...overrides,
  });
}

function snapshotResult(status = 'valid', settings = snapshotSettings(), explicitText = {
  introTitle: true, introCaption: true, artworkSubtitle: true,
}) {
  return Object.freeze({
    status,
    settings,
    explicitText: Object.freeze(explicitText),
    baseline: 'must-never-cross-the-controller-boundary',
  });
}

function snapshotFixture(snapshotSource, { playbackOwner = 'page', observeAppearance, wallpaperApply, existingWallpaper } = {}) {
  const controlled = controlledHost();
  if (existingWallpaper) controlled.host.__azhouWallpaper = existingWallpaper;
  controlled.host.crypto = webcrypto;
  const indexedDB = { marker: 'host-settings-database' };
  controlled.host.indexedDB = indexedDB;
  const settingsNamespace = Object.freeze({ databaseName: 'test', databaseVersion: 1,
    storeName: 'settings', settingsKey: 'images' });
  const assets = Object.freeze({
    avatar: 'data:image/png;base64,AA==',
    artwork: 'data:image/png;base64,AA==',
    contours: Object.freeze([Object.freeze([Object.freeze([0, 0]), Object.freeze([2, 2])])]),
    wallpaperStrength: 42,
    themeConfig: Object.freeze({}),
  });
  const factoryInputs = [];
  const loadDefaults = [];
  const frameSpecs = [];
  let loadCalls = 0;
  let disposeCalls = 0;
  const payload = function (...args) { if (args[14]) frameSpecs.push(args[14]); };
  Object.defineProperties(payload, {
    assets: { value: assets },
    ...(wallpaperApply ? { applyWallpaper: { value: (value, current) => wallpaperApply(value, current, controlled.host) } } : {}),
    createLocalization: { value: () => ({ t: key => key, subscribe: () => () => {} }) },
    createImageSettings: { value: input => {
      factoryInputs.push(input);
      return {
        loadSnapshot(defaults) {
          loadCalls += 1;
          loadDefaults.push(defaults);
          return typeof snapshotSource === 'function' ? snapshotSource(defaults) : snapshotSource;
        },
        dispose() { disposeCalls += 1; },
      };
    } },
  });
  const adapter = Object.freeze({ ...pageAdapter,
    ...(observeAppearance ? { observeAppearance } : {}),
    settingsEnvironment: source => ({ indexedDB: source.indexedDB, settingsNamespace }),
  });
  assert.equal(installStartup(payload, controlled.host, adapter, playbackOwner).installed, true);
  return {
    ...controlled,
    api: controlled.host.__azhouStartup,
    assets,
    indexedDB,
    settingsNamespace,
    factoryInputs,
    loadDefaults,
    payload,
    adapter,
    frameSpecs,
    loadCalls: () => loadCalls,
    disposeCalls: () => disposeCalls,
  };
}

function snapshotRequest(api, runNonce = 'native-run-01') {
  return { owner: api.owner, runId: api.status().runId, runNonce };
}

function snapshotChunkRequest(request, descriptor, index, offset) {
  return { ...request, snapshotID: descriptor.snapshotID, index, offset };
}

test('native-owned startup prepares a stable controller without page playback and exports one snapshot', async () => {
  const settings = snapshotSettings();
  const result = snapshotResult('valid', settings);
  const fixture = snapshotFixture(result, { playbackOwner: 'native' });
  const { api } = fixture;
  const prepared = api.status();
  assert.equal(prepared.playbackOwner, 'native');
  assert.equal(prepared.phase, 'prepared');
  assert.equal(prepared.prepared, true);
  assert.equal(prepared.runId > 0, true);
  assert.equal(prepared.ready, false, 'page ready stays false because no page player ran');
  assert.equal(prepared.completed, false);
  assert.equal(prepared.overlay, false);
  assert.equal(prepared.wallpaperDisposition, 'pending');
  assert.equal(prepared.wallpaper.applied, false, 'controller installation alone never claims wallpaper applied');
  assert.equal(fixture.frames.length, 0, 'preparation mounts no iframe');
  assert.equal(fixture.listenerCount(), 0, 'no page playback message bridge is installed');
  assert.equal(appearanceButton(fixture).disabled, false, 'the existing manual settings entry remains available');

  assert.deepEqual(installStartup(fixture.payload, fixture.host, fixture.adapter, 'native'), {
    installed: true, alreadyActive: true,
  }, 'repeated installation keeps the existing prepared controller');
  assert.equal(api.status().runId, prepared.runId, 'the prepared run identity is stable');

  const request = snapshotRequest(api, 'native-prepared-run');
  const descriptor = await api.beginSettingsSnapshot(request);
  assert.equal(descriptor.ok, true);
  assert.equal(descriptor.runId, prepared.runId);
  const chunk = api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 0, 0));
  assert.equal(chunk.ok, true);
  const bytes = Buffer.from(chunk.dataBase64, 'base64');
  assert.equal(createHash('sha256').update(bytes).digest('hex'), descriptor.sha256);
  const snapshot = JSON.parse(bytes.toString('utf8'));
  assert.equal(snapshot.status, 'valid');
  assert.deepEqual(snapshot.settings, settings);
  assert.equal(api.status().wallpaperDisposition, 'pending',
    'a settings snapshot does not claim the host wallpaper was applied');

  appearanceButton(fixture).click();
  assert.equal(fixture.frames.length, 1, 'manual settings continues to use its owned frame');
  assert.equal(fixture.frameSpecs[0].intent, 'settings', 'manual settings does not begin automatic playback');
  assert.equal(api.status().overlay, true, 'only the explicit settings action covers the host page');
  api.dispose();
  assert.equal(fixture.frames[0].removed, true, 'controller disposal releases the manual settings frame');
  assert.equal(fixture.pageHideListenerCount(), 0);
  assert.equal(fixture.pageShowListenerCount(), 0);
});

test('native-owned preparation fails closed and cleans listeners when the entry cannot mount', () => {
  const noBody = controlledHost({ body: false });
  const failedBody = installStartup(function () {}, noBody.host, pageAdapter, 'native');
  assert.equal(failedBody.installed, false);
  assert.equal(Object.hasOwn(noBody.host, '__azhouStartup'), false);
  assert.equal(noBody.frames.length, 0);
  assert.equal(noBody.listenerCount(), 0);
  assert.equal(noBody.pageHideListenerCount(), 0);
  assert.equal(noBody.pageShowListenerCount(), 0);

  const mountFailure = controlledHost();
  const brokenAdapter = { ...pageAdapter, mountEntry() { throw new Error('entry unavailable'); } };
  const failedEntry = installStartup(function () {}, mountFailure.host, brokenAdapter, 'native');
  assert.equal(failedEntry.installed, false);
  assert.equal(Object.hasOwn(mountFailure.host, '__azhouStartup'), false);
  assert.equal(mountFailure.frames.length, 0);
  assert.equal(mountFailure.listenerCount(), 0);
  assert.equal(mountFailure.pageHideListenerCount(), 0);
  assert.equal(mountFailure.pageShowListenerCount(), 0);
});

test('snapshot appearance is captured once from the bound host page and covered by the content digest', async () => {
  let completeRead;
  let currentAppearance = { locale: 'zh-CN', theme: 'dark' };
  const fixture = snapshotFixture(() => new Promise(resolve => { completeRead = resolve; }), {
    playbackOwner: 'native', observeAppearance: () => currentAppearance,
  });
  const request = snapshotRequest(fixture.api);
  const pending = fixture.api.beginSettingsSnapshot(request);
  currentAppearance = { locale: 'en', theme: 'light' };
  completeRead(snapshotResult());
  const descriptor = await pending;
  const chunk = fixture.api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 0, 0));
  const bytes = Buffer.from(chunk.dataBase64, 'base64');
  assert.deepEqual(JSON.parse(bytes.toString('utf8')).appearance, { locale: 'zh-CN', theme: 'dark' });
  assert.equal(createHash('sha256').update(bytes).digest('hex'), descriptor.sha256);
  fixture.api.dispose();
});

test('invalid host snapshot appearance fails without substituting local preferences', async () => {
  for (const appearance of [{ locale: 'fr', theme: 'light' }, { locale: 'en', theme: 'auto' }]) {
    const fixture = snapshotFixture(snapshotResult(), { observeAppearance: () => appearance });
    const result = await fixture.api.beginSettingsSnapshot(snapshotRequest(fixture.api));
    assert.deepEqual(result, { ok: false, reason: 'snapshot-invalid' });
    assert.equal(fixture.loadCalls(), 0);
    fixture.api.dispose();
  }
});

test('missing settings export uses one host factory and survives natural frame teardown', async () => {
  let finishRead;
  const result = snapshotResult('missing', snapshotSettings(), {
    introTitle: false, introCaption: false, artworkSubtitle: false,
  });
  const fixture = snapshotFixture(() => new Promise(resolve => { finishRead = resolve; }));
  const { api } = fixture;
  const request = snapshotRequest(api);
  const pending = api.beginSettingsSnapshot(request);
  const repeated = api.beginSettingsSnapshot(request);
  assert.equal(fixture.loadCalls(), 1, 'a repeated begin for the same run returns the same single load');
  assert.equal(fixture.factoryInputs.length, 1, 'the snapshot uses a separate host-side settings factory');
  assert.equal(fixture.factoryInputs[0].indexedDB, fixture.indexedDB);
  assert.equal(fixture.factoryInputs[0].document, fixture.host.document);
  assert.equal(fixture.factoryInputs[0].settingsNamespace, fixture.settingsNamespace);

  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: request.runId, skipped: true },
    fixture.frames[0].contentWindow);
  assert.equal(api.status().phase, 'complete');
  finishRead(result);
  const descriptor = await pending;
  assert.deepEqual(await repeated, descriptor);
  assert.equal(descriptor.status, 'missing', 'confirmed absence stays distinct from read failure');
  assert.equal(descriptor.digestAlgorithm, 'sha-256');
  assert.equal(descriptor.chunkSize, 64 * 1024);
  assert.equal(descriptor.chunkCount, 1);
  assert.equal(fixture.loadDefaults[0], fixture.assets, 'the loader receives the packaged defaults once');
  assert.equal(fixture.disposeCalls(), 1, 'the independent settings API is disposed after the read');

  const chunk = api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 0, 0));
  const bytes = Buffer.from(chunk.dataBase64, 'base64');
  assert.equal(chunk.ok, true);
  assert.equal(chunk.status, 'missing');
  assert.equal(chunk.offset, 0);
  assert.equal(chunk.totalBytes, descriptor.byteLength);
  assert.equal(chunk.dataBase64.length, 4 * Math.ceil(chunk.byteLength / 3));
  assert.equal(createHash('sha256').update(bytes).digest('hex'), descriptor.sha256);
  const parsed = JSON.parse(bytes.toString('utf8'));
  assert.equal(parsed.status, 'missing');
  assert.equal(Object.hasOwn(parsed, 'baseline'), false, 'the raw loader baseline is never serialized');
  assert.equal(Object.hasOwn(parsed.settings, 'baseline'), false);
  assert.equal(api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 0, 0)).reason,
    'snapshot-not-found', 'the final chunk releases its backing bytes');
  assert.equal(fixture.pageHideListenerCount(), 1);
  assert.equal(fixture.pageShowListenerCount(), 1);
  api.dispose();
  assert.equal(fixture.pageHideListenerCount(), 0, 'controller disposal unwires pagehide');
  assert.equal(fixture.pageShowListenerCount(), 0, 'controller disposal unwires pageshow');
});

test('failed settings reads return no defaults or chunks and cannot be retried in the same run', async () => {
  const fixture = snapshotFixture(Object.freeze({ status: 'failure', reason: 'settings-unavailable' }));
  const request = snapshotRequest(fixture.api);
  const result = await fixture.api.beginSettingsSnapshot(request);
  assert.deepEqual(result, { ok: false, reason: 'settings-unavailable' });
  assert.equal(Object.hasOwn(result, 'dataBase64'), false);
  assert.equal(Object.hasOwn(result, 'settings'), false);
  assert.equal(fixture.loadCalls(), 1);
  assert.equal(fixture.disposeCalls(), 1);
  assert.equal((await fixture.api.beginSettingsSnapshot(request)).reason, 'snapshot-already-used');
  fixture.api.dispose();
});

test('valid snapshot chunks honor byte boundaries, integrity, strict order and owner binding', async () => {
  let setting = snapshotSettings({ artwork: 'data:image/png;base64,' + 'A'.repeat(64 * 1024 + 80) });
  let snapshot = snapshotResult('valid', setting);
  let expected = Buffer.from(JSON.stringify({ status: 'valid', settings: setting,
    explicitText: snapshot.explicitText, appearance: { locale: 'zh-CN', theme: 'light' } }), 'utf8');
  while ((expected.length - 64 * 1024) % 3 === 0) {
    setting = snapshotSettings({ artwork: setting.artwork + 'A' });
    snapshot = snapshotResult('valid', setting);
    expected = Buffer.from(JSON.stringify({ status: 'valid', settings: setting,
      explicitText: snapshot.explicitText, appearance: { locale: 'zh-CN', theme: 'light' } }), 'utf8');
  }
  const fixture = snapshotFixture(snapshot);
  const { api } = fixture;
  const request = snapshotRequest(api, 'native-run-boundary');
  const wrongOwner = await api.beginSettingsSnapshot({ ...request, owner: 'foreign-owner' });
  assert.deepEqual(wrongOwner, { ok: false, reason: 'snapshot-request-invalid' });
  assert.equal(fixture.loadCalls(), 0, 'owner mismatch is refused before reading settings');
  const descriptor = await api.beginSettingsSnapshot(request);
  assert.equal(descriptor.byteLength, expected.length);
  assert.equal(descriptor.chunkCount, 2);
  assert.equal(descriptor.byteLength <= 24 * 1024 * 1024 + 4 * 1024, true);

  const first = api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 0, 0));
  assert.equal(first.byteLength, 64 * 1024);
  assert.equal(first.dataBase64.length, 87_384, '64 KiB base64 expansion stays below the 2 MiB CDP cap');
  const second = api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 1, 64 * 1024));
  assert.equal(second.offset, 64 * 1024);
  assert.equal(second.byteLength, expected.length - 64 * 1024);
  const joined = Buffer.concat([Buffer.from(first.dataBase64, 'base64'), Buffer.from(second.dataBase64, 'base64')]);
  assert.deepEqual(joined, expected);
  const encodedByChunk = 4 * Math.ceil(first.byteLength / 3) + 4 * Math.ceil(second.byteLength / 3);
  assert.equal(descriptor.encodedByteLength, encodedByChunk);
  assert.ok(descriptor.encodedByteLength > 4 * Math.ceil(expected.length / 3),
    'separate chunk padding adds bytes beyond one-shot base64 length');
  assert.equal(createHash('sha256').update(joined).digest('hex'), descriptor.sha256);

  const outOfOrder = snapshotFixture(snapshot);
  const outRequest = snapshotRequest(outOfOrder.api, 'native-run-order');
  const outDescriptor = await outOfOrder.api.beginSettingsSnapshot(outRequest);
  assert.deepEqual(outOfOrder.api.readSettingsSnapshotChunk(
    snapshotChunkRequest(outRequest, outDescriptor, 1, 64 * 1024)),
  { ok: false, reason: 'snapshot-order-invalid' });
  assert.equal(outOfOrder.api.readSettingsSnapshotChunk(
    snapshotChunkRequest(outRequest, outDescriptor, 0, 0)).reason, 'snapshot-not-found',
  'a sequence error erases the active export');
  api.dispose();
  outOfOrder.api.dispose();
});

test('legal-size normalized settings plus envelope exceed 20 MiB and remain exportable', async () => {
  const MiB = 1024 * 1024;
  const prefix = 'data:image/png;base64,';
  const point = index => [index % 2 ? 1.234567890123456 : 2.345678901234567, 1023.1234567890123];
  const settings = snapshotSettings({
    avatar: prefix + 'A'.repeat(2 * MiB - prefix.length),
    artwork: prefix + 'A'.repeat(12 * MiB - prefix.length),
    contours: [Array.from({ length: 161_310 }, (_, index) => point(index))],
    artworkSubtitle: '舟'.repeat(60),
  });
  const snapshot = snapshotResult('valid', settings);
  const normalizedBytes = Buffer.byteLength(JSON.stringify(settings), 'utf8');
  const expectedBytes = Buffer.byteLength(JSON.stringify({ status: 'valid', settings,
    explicitText: snapshot.explicitText, appearance: { locale: 'zh-CN', theme: 'light' } }), 'utf8');
  assert.equal(normalizedBytes <= 20 * MiB, true, 'the normalized record stays within the existing loader cap');
  assert.equal(expectedBytes > 20 * MiB, true, 'JSON status and text envelope must fit beyond the raw record cap');

  const fixture = snapshotFixture(snapshot);
  const request = snapshotRequest(fixture.api, 'native-run-large');
  const descriptor = await fixture.api.beginSettingsSnapshot(request);
  assert.equal(descriptor.byteLength, expectedBytes);
  assert.equal(descriptor.byteLength <= 24 * MiB + 4 * 1024, true,
    'the raw transfer cap includes the bundle-bounded default subset plus its envelope');
  let chunkEncodedBytes = 0;
  for (let offset = 0; offset < expectedBytes; offset += 64 * 1024) {
    chunkEncodedBytes += 4 * Math.ceil(Math.min(64 * 1024, expectedBytes - offset) / 3);
  }
  assert.equal(descriptor.encodedByteLength, chunkEncodedBytes,
    'base64 total sums the separately padded chunks, not a hypothetical one-shot stream');
  assert.equal(descriptor.chunkCount, Math.ceil(expectedBytes / (64 * 1024)));
  assert.equal(fixture.api.disposeSettingsSnapshot({ ...request, snapshotID: descriptor.snapshotID }).disposed, true);
  assert.equal(fixture.api.readSettingsSnapshotChunk(
    snapshotChunkRequest(request, descriptor, 0, 0)).reason, 'snapshot-not-found');
  assert.equal(fixture.disposeCalls(), 1);
  fixture.api.dispose();
});

for (const navigate of [false, true]) {
  test(`pending snapshot ${navigate ? 'rejects observed A to B to A' : 'completes on the same observed page'}`, async () => {
    let finishRead;
    let wallpaperWrites = 0;
    const fixture = snapshotFixture(() => new Promise(resolve => { finishRead = resolve; }), {
      playbackOwner: 'native', wallpaperApply: () => { wallpaperWrites += 1; },
    });
    const { api, adapter, host } = fixture;
    const request = snapshotRequest(api, 'native-observed-page');
    const pending = api.beginSettingsSnapshot(request);
    const first = adapter.identify(host).documentToken;
    if (navigate) {
      host.location = new URL('app://-/index.html?initialRoute=%2Fthread');
      adapter.identify(host);
      host.location = new URL(mainURL);
    }
    const current = adapter.identify(host).documentToken;
    if (!navigate) assert.equal(current, first);
    finishRead(snapshotResult('valid'));
    const descriptor = await pending;
    if (navigate) {
      assert.deepEqual(descriptor, { ok: false, reason: 'snapshot-stale' });
      assert.equal(api.readSettingsSnapshotChunk({ ...request,
        snapshotID: `${request.runId}:${request.runNonce}`, index: 0, offset: 0 }).ok, false);
      assert.deepEqual(await api.beginSettingsSnapshot(request), { ok: false, reason: 'snapshot-stale' });
      assert.equal(fixture.disposeCalls(), 1);
    } else {
      assert.equal(descriptor.ok, true);
      assert.equal(api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 0, 0)).ok, true);
    }
    assert.equal(wallpaperWrites, 0);
    api.dispose();
  });
}

test('pagehide and run replacement erase pending snapshots and reject late callbacks', async () => {
  let finishRead;
  const fixture = snapshotFixture(() => new Promise(resolve => { finishRead = resolve; }));
  const { api } = fixture;
  const request = snapshotRequest(api, 'native-run-cancel');
  const pending = api.beginSettingsSnapshot(request);
  fixture.host.pagehide();
  assert.equal(fixture.disposeCalls(), 1, 'pagehide disposes the active host-side settings factory');
  finishRead(snapshotResult('valid', snapshotSettings({ artwork: 'data:image/png;base64,SECRET' })));
  const late = await pending;
  assert.deepEqual(late, { ok: false, reason: 'snapshot-cancelled' });
  assert.equal(JSON.stringify(late).includes('SECRET'), false);
  assert.equal(api.readSettingsSnapshotChunk({ ...request, snapshotID: `${request.runId}:${request.runNonce}`,
    index: 0, offset: 0 }).reason, 'snapshot-not-found');
  fixture.host.pageshow();

  const nextRun = snapshotFixture(snapshotResult('valid'));
  const nextApi = nextRun.api;
  const nextRequest = snapshotRequest(nextApi, 'native-run-replace');
  nextRun.host.send({ type: 'azhou-startup', action: 'complete', runId: nextRequest.runId, skipped: true },
    nextRun.frames[0].contentWindow);
  const descriptor = await nextApi.beginSettingsSnapshot(nextRequest);
  assert.equal(nextApi.openSettings(), true, 'opening a replacement run releases the export');
  assert.equal(nextRun.disposeCalls(), 1);
  assert.equal(nextApi.readSettingsSnapshotChunk(
    snapshotChunkRequest(nextRequest, descriptor, 0, 0)).reason, 'snapshot-not-found');
  const replacementRequest = snapshotRequest(nextApi, 'native-run-dispose');
  const replacementDescriptor = await nextApi.beginSettingsSnapshot(replacementRequest);
  nextApi.dispose();
  assert.equal(nextApi.readSettingsSnapshotChunk(
    snapshotChunkRequest(replacementRequest, replacementDescriptor, 0, 0)).reason, 'snapshot-not-found',
  'controller disposal erases an active byte buffer');
  nextApi.dispose();
  api.dispose();
});

test('snapshot timeout clears digest input and ignores an uncancellable late digest', async () => {
  const fixture = snapshotFixture(snapshotResult('valid'));
  let finishDigest;
  let digestInput;
  let markDigestStarted;
  const digestStarted = new Promise(resolve => { markDigestStarted = resolve; });
  fixture.host.crypto = { subtle: { digest(_algorithm, bytes) {
    digestInput = bytes;
    markDigestStarted();
    return new Promise(resolve => { finishDigest = resolve; });
  } } };
  const { api } = fixture;
  const request = snapshotRequest(api, 'native-run-digest-timeout');
  const pending = api.beginSettingsSnapshot(request);
  await digestStarted;
  assert.ok(digestInput.some(byte => byte !== 0), 'the digest receives the serialized settings bytes');
  const timer = fixture.timers.find(candidate => candidate.delay === 30_000 && !candidate.cleared);
  assert.ok(timer, 'the export has its own retention deadline after the page animation completes');
  timer.callback();
  assert.deepEqual(await pending, { ok: false, reason: 'snapshot-timeout' },
    'the caller is released even while WebCrypto is still pending');
  assert.ok(digestInput.every(byte => byte === 0), 'the controller-owned digest input is cleared immediately');
  assert.equal(api.readSettingsSnapshotChunk({ ...request, snapshotID: `${request.runId}:${request.runNonce}`,
    index: 0, offset: 0 }).reason, 'snapshot-not-found');

  finishDigest(new Uint8Array(32).buffer);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(api.readSettingsSnapshotChunk({ ...request, snapshotID: `${request.runId}:${request.runNonce}`,
    index: 0, offset: 0 }).reason, 'snapshot-not-found', 'a late digest cannot recreate the export');
  api.dispose();
});

test('chunk reads wait for atomic descriptor commit while the digest is pending', async () => {
  const snapshot = snapshotResult('valid');
  const fixture = snapshotFixture(snapshot);
  let finishDigest;
  let digestInput;
  let markDigestStarted;
  const digestStarted = new Promise(resolve => { markDigestStarted = resolve; });
  fixture.host.crypto = { subtle: { digest(_algorithm, bytes) {
    digestInput = bytes;
    markDigestStarted();
    return new Promise(resolve => { finishDigest = resolve; });
  } } };
  const { api } = fixture;
  const request = snapshotRequest(api, 'native-run-digest-gate');
  const pending = api.beginSettingsSnapshot(request);
  await digestStarted;

  const snapshotID = `${request.runId}:${request.runNonce}`;
  const early = api.readSettingsSnapshotChunk({ ...request, snapshotID, index: 0, offset: 0 });
  assert.deepEqual(early, { ok: false, reason: 'snapshot-not-ready' },
    'knowing the predicted handle cannot read bytes or consume sequence before digest completion');

  const serialized = Buffer.from(digestInput);
  const digestBuffer = createHash('sha256').update(serialized).digest();
  const digestResult = digestBuffer.buffer.slice(digestBuffer.byteOffset,
    digestBuffer.byteOffset + digestBuffer.byteLength);
  finishDigest(digestResult);
  const descriptor = await pending;
  assert.equal(descriptor.sha256, digestBuffer.toString('hex'));
  assert.equal(descriptor.snapshotID, snapshotID);

  const chunk = api.readSettingsSnapshotChunk({ ...request, snapshotID, index: 0, offset: 0 });
  assert.equal(chunk.ok, true, 'the first read succeeds after descriptor commit');
  assert.deepEqual(Buffer.from(chunk.dataBase64, 'base64'), serialized);
  assert.equal(chunk.sha256, descriptor.sha256);
  api.dispose();
});

test('an unread descriptor expires and releases its retained chunk buffer', async () => {
  const fixture = snapshotFixture(snapshotResult('valid'));
  const { api } = fixture;
  const request = snapshotRequest(api, 'native-run-transfer-timeout');
  const descriptor = await api.beginSettingsSnapshot(request);
  assert.equal(descriptor.ok, true);
  const timer = fixture.timers.find(candidate => candidate.delay === 30_000 && !candidate.cleared);
  assert.ok(timer);
  timer.callback();
  assert.equal(timer.cleared, true);
  assert.equal(api.readSettingsSnapshotChunk(snapshotChunkRequest(request, descriptor, 0, 0)).reason,
    'snapshot-not-found', 'an abandoned transfer cannot retain bytes indefinitely');
  api.dispose();
});


test('native workspace preparation is explicit, bounded, and separate from page readiness', async () => {
  const fixture = snapshotFixture(snapshotResult('valid', { ...snapshotSettings(), wallpaperStrength: 0 }),
    { playbackOwner: 'native' });
  const request = { ...snapshotRequest(fixture.api), expiresAt: 7000 };
  assert.equal(fixture.loadCalls(), 0);
  assert.deepEqual(fixture.api.prepareWorkspace(request), { ok: true, accepted: true });
  assert.deepEqual(fixture.api.prepareWorkspace(request), { ok: true, accepted: true });
  assert.equal(fixture.api.prepareWorkspace({ ...request, runNonce: 'another-run' }).ok, false);
  await new Promise(resolve => setImmediate(resolve));
  const status = fixture.api.status();
  assert.equal(status.wallpaperDisposition, 'disabled');
  assert.equal(status.ready, false);
  assert.equal(status.completed, false);
  assert.equal(status.phase, 'prepared');
  assert.equal(fixture.loadCalls(), 1, 'duplicate requests cannot re-read or apply');
  assert.equal(fixture.frames.length, 0);
  const descriptor = await fixture.api.beginSettingsSnapshot(request);
  assert.equal(descriptor.ok, true, 'independent read-only export remains available');
  assert.equal(fixture.loadCalls(), 2, 'wallpaper and playback report separate effective reads');
  fixture.api.dispose();
});

test('native wallpaper storage failure and missing apply capability report degradation without playing', async () => {
  for (const result of [{ status: 'failure', reason: 'read-failed' }, snapshotResult()]) {
    const fixture = snapshotFixture(result, { playbackOwner: 'native' });
    fixture.api.prepareWorkspace({ ...snapshotRequest(fixture.api), expiresAt: 7000 });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(fixture.api.status().wallpaperDisposition, 'degraded');
    assert.equal(fixture.api.status().ready, false);
    assert.equal(fixture.frames.length, 0);
    fixture.api.dispose();
  }
  const page = snapshotFixture(snapshotResult());
  assert.equal(page.api.prepareWorkspace({ ...snapshotRequest(page.api), expiresAt: 7000 }).ok, false,
    'legacy page playback cannot opt into native preparation');
  page.api.dispose();
});

test('native workspace watchdog and disposal reject late settings without a wallpaper write', async () => {
  let resolve;
  const fixture = snapshotFixture(() => new Promise(done => { resolve = done; }), { playbackOwner: 'native' });
  fixture.api.prepareWorkspace({ ...snapshotRequest(fixture.api), expiresAt: 7000 });
  await Promise.resolve();
  const timer = fixture.timers.find(timer => !timer.cleared);
  assert.ok(timer);
  timer.callback();
  assert.equal(fixture.api.status().wallpaperDisposition, 'degraded');
  resolve(snapshotResult('valid', { ...snapshotSettings(), wallpaperStrength: 0 }));
  await new Promise(done => setImmediate(done));
  assert.equal(fixture.api.status().wallpaperDisposition, 'degraded', 'late load cannot replace timeout');
  fixture.api.dispose();
});


test('native preparation invokes the existing wallpaper engine with effective host settings', async () => {
  const settings = snapshotSettings();
  const calls = [];
  const fixture = snapshotFixture(snapshotResult('valid', settings), { playbackOwner: 'native',
    wallpaperApply: async (value, current, host) => {
      assert.equal(current(), true);
      calls.push(value);
      host.__azhouWallpaper = {
        owner: 'azhou.codex-startup-animation', version: '0.9.0',
        status: () => ({ applied: true, imageDecoded: true, reason: '' }),
        updateSurface() { return true; }, dispose() {},
      };
      return { applied: true };
    } });
  fixture.api.prepareWorkspace({ ...snapshotRequest(fixture.api), expiresAt: 7000 });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].image, settings.artwork);
  assert.equal(calls[0].strength, settings.wallpaperStrength);
  assert.equal(fixture.api.status().wallpaperDisposition, 'applied');
  assert.equal(fixture.frames.length, 0);
  assert.equal(fixture.api.status().ready, false);
  fixture.api.dispose();
});


test('prepared status ignores prior applied wallpaper until this run reads and applies its own settings', async () => {
  let resolve;
  let oldDisposed = 0;
  const existingWallpaper = {
    owner: 'azhou.codex-startup-animation', version: '0.9.0',
    status: () => ({ applied: true, imageDecoded: true, reason: '' }),
    updateSurface() { return true; }, dispose() { oldDisposed += 1; },
  };
  const fixture = snapshotFixture(() => new Promise(done => { resolve = done; }),
    { playbackOwner: 'native', existingWallpaper });
  assert.equal(fixture.api.status().wallpaperDisposition, 'pending');
  const request = { ...snapshotRequest(fixture.api), expiresAt: 6000 };
  fixture.api.prepareWorkspace(request);
  await Promise.resolve();
  const pending = fixture.api.status();
  assert.equal(pending.wallpaperDisposition, 'pending');
  assert.equal(pending.wallpaper.applied, false);
  assert.deepEqual(pending.workspace, { runId: request.runId, runNonce: request.runNonce, phase: 'pending' });
  resolve(snapshotResult('valid', { ...snapshotSettings(), wallpaperStrength: 0 }));
  await new Promise(done => setImmediate(done));
  assert.equal(fixture.api.status().wallpaperDisposition, 'disabled');
  assert.equal(fixture.api.status().workspace.phase, 'complete');
  assert.equal(oldDisposed, 1, 'new disabled settings dispose the bound prior wallpaper');
  fixture.api.dispose();
});

test('cancelWorkspace is nonce-bound and rejects late async reads without applying wallpaper', async () => {
  let resolve;
  let applies = 0;
  const fixture = snapshotFixture(() => new Promise(done => { resolve = done; }), {
    playbackOwner: 'native', wallpaperApply: async () => { applies += 1; return { applied: true }; },
  });
  const request = { ...snapshotRequest(fixture.api), expiresAt: 6000 };
  fixture.api.prepareWorkspace(request);
  await Promise.resolve();
  assert.equal(fixture.api.cancelWorkspace({ ...request, runNonce: 'wrong-run' }).ok, false);
  assert.equal(fixture.api.status().workspace.phase, 'pending');
  assert.deepEqual(fixture.api.cancelWorkspace(request), { ok: true, cancelled: true });
  resolve(snapshotResult());
  await new Promise(done => setImmediate(done));
  assert.equal(applies, 0);
  assert.equal(fixture.api.status().workspace.phase, 'cancelled');
  fixture.api.dispose();
});

test('page monotonic lease blocks delayed settings and apply even when watchdog has not fired', async () => {
  for (const stage of ['load', 'apply']) {
    let now = 1000;
    let resolve;
    let current;
    let commits = 0;
    const fixture = snapshotFixture(stage === 'load' ? () => new Promise(done => { resolve = done; }) : snapshotResult(), {
      playbackOwner: 'native', wallpaperApply: async (_value, isCurrent) => {
        current = isCurrent;
        await new Promise(done => { resolve = done; });
        if (isCurrent()) commits += 1;
        return { applied: true };
      },
    });
    fixture.host.performance = { now: () => now };
    fixture.api.prepareWorkspace({ ...snapshotRequest(fixture.api), expiresAt: 1050 });
    await new Promise(done => setImmediate(done));
    const timer = fixture.timers.find(timer => !timer.cleared);
    assert.equal(timer.delay, 50, 'native remaining lease shortens the independent page watchdog');
    now = 1051;
    if (current) assert.equal(current(), false, 'apply commit predicate checks lease directly');
    resolve(snapshotResult());
    await new Promise(done => setImmediate(done));
    assert.equal(commits, 0);
    assert.notEqual(fixture.api.status().wallpaperDisposition, 'applied');
    fixture.api.dispose();
  }
});
