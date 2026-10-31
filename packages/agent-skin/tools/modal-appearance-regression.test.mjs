import assert from 'node:assert/strict';
import test from 'node:test';
import { installStartup } from '../extension/renderer.mjs';
import { createCodexPageAdapter } from '../extension/codex-page-adapter.mjs';
const pageAdapter = createCodexPageAdapter(globalThis);

const mainURL = 'app://-/index.html?initialRoute=%2F';

function createElement(tagName, document) {
  const listeners = new Map();
  const element = {
    nodeType: 1,
    tagName: tagName.toUpperCase(),
    children: [],
    parentNode: null,
    isConnected: false,
    inert: false,
    hidden: false,
    style: {},
    attributes: new Map(),
    setAttribute(name, value) { this.attributes.set(name, String(value)); },
    getAttribute(name) { return this.attributes.get(name) ?? null; },
    addEventListener(type, listener) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(listener);
    },
    removeEventListener(type, listener) { listeners.get(type)?.delete(listener); },
    focus() { document.activeElement = this; },
    appendChild(child) { return insertChild(this, child, this.children.length); },
    insertBefore(child, reference) {
      const index = reference == null ? this.children.length : this.children.indexOf(reference);
      return insertChild(this, child, index < 0 ? this.children.length : index);
    },
    removeChild(child) {
      const index = this.children.indexOf(child);
      if (index >= 0) this.children.splice(index, 1);
      child.parentNode = null;
      child.isConnected = false;
      return child;
    },
    contains(child) { return this === child || this.children.some(item => item.contains?.(child)); },
    attachShadow() {
      const host = this;
      this.shadowRoot = {
        host,
        children: [],
        appendChild(child) {
          if (child.parentNode?.removeChild) child.parentNode.removeChild(child);
          child.parentNode = this;
          child.isConnected = host.isConnected;
          this.children.push(child);
          return child;
        },
      };
      return this.shadowRoot;
    },
    click() { for (const listener of listeners.get('click') ?? []) listener(); },
    remove() { this.parentNode?.removeChild?.(this); },
  };
  element.contains = child => element === child || element.children.some(item => item.contains?.(child));
  return element;
}

function insertChild(parent, child, index) {
  if (child.parentNode?.removeChild) child.parentNode.removeChild(child);
  parent.children.splice(index, 0, child);
  child.parentNode = parent;
  child.isConnected = parent.isConnected === true || parent.host?.isConnected === true;
  return child;
}

function createFixture({ children = [], tokens = {}, colorScheme = 'light' } = {}) {
  const observers = [];
  const messageListeners = new Set();
  const timers = [];
  const document = {
    documentElement: null,
    body: null,
    activeElement: null,
    querySelectorAll: () => [],
    createElement(tagName) {
      const element = createElement(tagName, document);
      if (tagName === 'iframe') {
        element.contentWindow = {
          location: new URL('about:blank'),
          performance: { now: () => 0 },
          indexedDB: {},
          Image: class Image {},
          Path2D: class Path2D {},
          URL,
          requestAnimationFrame: () => 1,
          cancelAnimationFrame() {},
          setTimeout: () => ({}),
          clearTimeout() {},
        };
        element.contentWindow.window = element.contentWindow;
        element.contentWindow.self = element.contentWindow;
      }
      return element;
    },
  };
  const root = createElement('html', document);
  root.isConnected = true;
  root.lang = 'en-US';
  root.dataset = { theme: 'light' };
  root.getAttribute = name => name === 'lang' ? root.lang
    : name === 'data-theme' ? root.dataset.theme : null;
  document.documentElement = root;

  const body = createElement('body', document);
  body.isConnected = true;
  document.body = body;
  for (const child of children) body.appendChild(child);

  class MutationObserver {
    constructor(callback) {
      this.callback = callback;
      this.records = [];
      observers.push(this);
    }
    observe(target, options) { this.target = target; this.options = options; this.connected = true; }
    disconnect() { this.connected = false; }
    takeRecords() { return this.records.splice(0); }
    trigger(records = []) { if (this.connected) this.callback(records); }
  }

  const host = {
    location: new URL(mainURL),
    navigator: { language: 'en-US' },
    document,
    CSS: { supports: (kind, value) => kind === 'color'
      && /^(?:#[\da-f]{3,8}|(?:rgb|rgba|hsl|hsla)\([^)]*\)|var\s*\(|currentcolor$)/i.test(String(value).trim()) },
    getComputedStyle() {
      return {
        colorScheme,
        getPropertyValue(name) { return tokens[name] ?? ''; },
      };
    },
    MutationObserver,
    addEventListener(type, listener) { if (type === 'message') messageListeners.add(listener); },
    removeEventListener(type, listener) { if (type === 'message') messageListeners.delete(listener); },
    send(data, source) { for (const listener of messageListeners) listener({ data, source }); },
    setTimeout(callback, delay) {
      const timer = { callback, delay, cleared: false };
      timers.push(timer);
      return timer;
    },
    clearTimeout(timer) { if (timer) timer.cleared = true; },
  };
  return { host, body, root, observers, timers, tokens };
}

function startupPayload(onFrame) {
  return function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, send, spec) {
    const handle = onFrame({ send, spec });
    send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
    return handle ?? { dispose() {} };
  };
}

function frameIn(body) {
  return body.children.find(child => child.tagName === 'IFRAME');
}

test('settings isolation locks current and added host siblings, then restores only owned inert state', () => {
  const main = createElement('main', null);
  const alreadyInert = createElement('aside', null);
  alreadyInert.inert = true;
  const fixture = createFixture({ children: [main, alreadyInert] });
  const frames = [];
  const payload = startupPayload(frame => { frames.push(frame); });

  assert.deepEqual(installStartup(payload, fixture.host, pageAdapter), { installed: true, alreadyActive: false });
  const api = fixture.host.__azhouStartup;
  const playFrame = frameIn(fixture.body);
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: frames[0].spec.runId, skipped: false },
    playFrame.contentWindow);
  assert.equal(api.status().phase, 'complete');

  assert.equal(api.openSettings(), true);
  const settingsFrame = frameIn(fixture.body);
  assert.equal(frames[1].spec.intent, 'settings');
  assert.equal(main.inert, true, 'opening settings isolates an interactive host sibling');
  assert.equal(alreadyInert.inert, true, 'a host sibling that was already inert remains inert');

  const childObserver = fixture.observers.find(observer => observer.target === fixture.body
    && observer.options?.childList && !observer.options?.attributes);
  const inertObserver = fixture.observers.find(observer => observer.options?.attributeFilter?.includes('inert'));
  assert.ok(childObserver);
  assert.ok(inertObserver);
  childObserver.trigger([{ type: 'childList', target: fixture.body, addedNodes: [settingsFrame], removedNodes: [] }]);
  assert.equal(settingsFrame.inert, false, 'the settings iframe stays outside its own inert boundary');

  const lateHostNode = createElement('section', null);
  fixture.body.appendChild(lateHostNode);
  childObserver.trigger([{ type: 'childList', target: fixture.body, addedNodes: [lateHostNode], removedNodes: [] }]);
  assert.equal(lateHostNode.inert, true, 'host content added during settings joins the modal boundary');

  inertObserver.trigger([{ type: 'attributes', target: main }]);
  main.inert = false;
  inertObserver.trigger([{ type: 'attributes', target: main }]);
  assert.equal(main.inert, true, 'the modal remains isolated after the host clears its owned inert value');

  const removedHostNode = createElement('article', null);
  fixture.body.appendChild(removedHostNode);
  childObserver.trigger([{ type: 'childList', target: fixture.body, addedNodes: [removedHostNode], removedNodes: [] }]);
  assert.equal(removedHostNode.inert, true);
  fixture.body.removeChild(removedHostNode);
  childObserver.trigger([{ type: 'childList', target: fixture.body, addedNodes: [], removedNodes: [removedHostNode] }]);
  assert.equal(removedHostNode.inert, false, 'a detached host node regains its original state immediately');
  fixture.body.appendChild(removedHostNode);
  childObserver.trigger([{ type: 'childList', target: fixture.body, addedNodes: [removedHostNode], removedNodes: [] }]);
  assert.equal(removedHostNode.inert, true, 'the same node is isolated again if the host reattaches it');

  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: frames[1].spec.runId, skipped: true },
    settingsFrame.contentWindow);
  assert.equal(api.status().phase, 'complete');
  assert.equal(main.inert, false, 'cancel restores the host value captured before settings opened');
  assert.equal(lateHostNode.inert, false, 'cancel releases dynamically isolated host content');
  assert.equal(removedHostNode.inert, false, 'cancel releases a detached and later reattached host node');
  assert.equal(alreadyInert.inert, true, 'cleanup does not clear host-owned inert state');
  assert.equal(childObserver.connected, false);
  assert.equal(inertObserver.connected, false);
  api.dispose();
});

test('settings appearance follows valid host tokens and stops updating the closed frame', () => {
  const colorScheme = 'dark';
  const tokens = {
    '--app-color-background-surface': 'var(--unresolved-surface)',
    '--color-surface': 'rgb(200, 210, 220)',
  };
  const fixture = createFixture({ tokens, colorScheme });
  fixture.root.dataset.theme = '';
  const frames = [];
  const updatesByRun = new Map();
  const payload = startupPayload(({ spec }) => {
    const updates = [];
    updatesByRun.set(spec.runId, updates);
    frames.push({ spec });
    return {
      updateAppearance(value) { updates.push(value); },
      dispose() {},
    };
  });

  assert.deepEqual(installStartup(payload, fixture.host, pageAdapter), { installed: true, alreadyActive: false });
  const api = fixture.host.__azhouStartup;
  assert.equal(frames[0].spec.appearance.theme, 'dark', 'the host color scheme supplies a missing theme attribute');
  assert.equal(frames[0].spec.appearance.colors.surface, 'rgb(200, 210, 220)',
    'an unresolved higher-priority token falls through to a valid surface color');
  const playFrame = frameIn(fixture.body);
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: frames[0].spec.runId, skipped: false },
    playFrame.contentWindow);

  assert.equal(api.openSettings(), true);
  const settingsFrame = frameIn(fixture.body);
  const settingsRunId = frames[1].spec.runId;
  const appearanceObserver = fixture.observers.find(observer => observer.options?.attributeFilter?.includes('data-theme'));
  assert.equal(frames[1].spec.intent, 'settings');
  assert.equal(updatesByRun.get(settingsRunId).at(-1).colors.surface, 'rgb(200, 210, 220)');

  fixture.root.dataset.theme = 'light';
  fixture.root.lang = 'zh-CN';
  tokens['--app-color-background-surface'] = 'rgb(10, 20, 30)';
  appearanceObserver.trigger([{ type: 'attributes', target: fixture.root, attributeName: 'data-theme' }]);
  assert.equal(api.status().runId, settingsRunId, 'a host appearance change does not restart the settings run');
  assert.deepEqual(
    (({ locale, theme, colors }) => ({ locale, theme, surface: colors.surface }))(updatesByRun.get(settingsRunId).at(-1)),
    { locale: 'zh-CN', theme: 'light', surface: 'rgb(10, 20, 30)' },
  );

  fixture.root.dataset.theme = 'dark';
  tokens['--app-color-background-surface'] = 'currentColor';
  tokens['--color-surface'] = '';
  appearanceObserver.trigger([{ type: 'attributes', target: fixture.root, attributeName: 'data-theme' }]);
  assert.equal(updatesByRun.get(settingsRunId).at(-1).colors.surface, '#10121c',
    'a later invalid token does not retain the previous theme surface');

  const updatesBeforeClose = updatesByRun.get(settingsRunId).length;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: settingsRunId, skipped: true },
    settingsFrame.contentWindow);
  fixture.root.dataset.theme = 'light';
  appearanceObserver.trigger([{ type: 'attributes', target: fixture.root, attributeName: 'data-theme' }]);
  assert.equal(updatesByRun.get(settingsRunId).length, updatesBeforeClose,
    'the closed settings frame no longer owns appearance updates');

  api.dispose();
  assert.equal(appearanceObserver.connected, false, 'dispose releases the host appearance observer');
});
