import assert from 'node:assert/strict';
import test from 'node:test';
import { installStartup } from '../extension/renderer.mjs';

const mainURL = 'app://-/index.html?initialRoute=%2F';

function controlledHost({ body = true } = {}) {
  const listeners = new Set();
  const keyListeners = new Set();
  const scrollListeners = new Set();
  const observers = [];
  const frames = [];
  const controls = [];
  const timers = [];
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
    },
    removeEventListener(type, listener) {
      if (type === 'message') listeners.delete(listener);
      if (type === 'keydown') keyListeners.delete(listener);
      if (type === 'scroll') scrollListeners.delete(listener);
    },
    send(data, source) {
      for (const listener of listeners) listener({ data, source });
    },
    keydown(event) { for (const listener of keyListeners) listener(event); },
    scroll() { for (const listener of scrollListeners) listener(); },
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
    keyListenerCount: () => keyListeners.size, scrollListenerCount: () => scrollListeners.size };
}

function addAppearanceNavigation(fixture, { width = 220, count = 1, label = 'Your dot' } = {}) {
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
    const yourDot = createRow('a', label);
    const pinned = createRow('a', 'Pinned');
    nav.appendChild(yourDot);
    nav.appendChild(pinned);
    rows.push({ nav, yourDot, pinned, setWidth(value) { navWidth = value; } });
  }
  fixture.host.document.querySelectorAll = selector => selector === 'nav a[href]'
    ? rows.flatMap(({ yourDot, pinned }) => [yourDot, pinned])
    : fixture.host.document.appearanceControls ?? [];
  fixture.host.document.appearanceNavigation = rows;
  return rows;
}

function appearanceButton(fixture) {
  return fixture.controls.find(node => node.tagName === 'button');
}

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
    if (tag === 'div') {
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
  installStartup((...args) => { runId = args[14].runId; }, fixture.host);
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
  }, fixture.host);
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
  installStartup(payload, fixture.host);
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

test('appearance entry recognizes the exact Simplified Chinese Your dot navigation name', () => {
  const fixture = controlledHost();
  const [{ nav, yourDot, pinned }] = addAppearanceNavigation(fixture, { label: '你的 Dot' });
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    send({ type: 'azhou-startup', action: 'ready', runId: spec.runId });
  }, fixture.host);
  const entry = fixture.controls.find(node => node.tagName === 'div');
  assert.equal(nav.children[0], yourDot);
  assert.equal(nav.children[1], entry, 'the translated semantic anchor gets the same normal-flow row');
  assert.equal(nav.children[2], pinned);
  fixture.host.__azhouStartup.dispose();
});

test('appearance entry uses a stable left fallback and stops observing on dispose', () => {
  const fixture = controlledHost();
  const doc = fixture.host.document;
  let run;
  installStartup((_w, _d, _l, _p, _i, _img, _path, _url, _raf, _caf, _set, _clear, _module, send, spec) => {
    run = spec.runId;
    send({ type: 'azhou-startup', action: 'ready', runId: run });
  }, fixture.host);
  const api = fixture.host.__azhouStartup;
  fixture.host.send({ type: 'azhou-startup', action: 'complete', runId: run, skipped: false }, fixture.frames[0].contentWindow);
  const entry = fixture.controls.find(node => node.tagName === 'div');
  assert.equal(entry.style.position, 'fixed');
  assert.equal(entry.style.left, '10px');
  assert.equal(entry.style.bottom, '72px');
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
      entry = node;
      node.getBoundingClientRect = () => {
        const left = Number.parseFloat(node.style.left || '10px');
        const bottom = Number.parseFloat(node.style.bottom || '72px');
        const label = node.children[0].children.at(-1);
        const width = label.style.display === 'none' ? 48 : 150;
        const top = node.style.top && node.style.top !== 'auto'
          ? Number.parseFloat(node.style.top) : doc.documentElement.clientHeight - bottom - 44;
        return { left, right: left + width, width, top, bottom: top + 44, height: 44 };
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
  installStartup(payload, fixture.host);
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
  }, fixture.host);
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
  installStartup(payload, controlled.host);
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
  installStartup(payload, controlled.host);
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

test('the real controller and default iframe mount execute an explicit parent-realm payload bridge', () => {
  const controlled = controlledHost();
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
  }, controlled.host);

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
  }, controlled.host);
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
  installStartup(function () {}, controlled.host);
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

test('install does not replace an existing controller or an unknown owner', () => {
  const controlled = controlledHost();
  const payload = function () {};
  const first = installStartup(payload, controlled.host);
  const second = installStartup(payload, controlled.host);
  assert.deepEqual(first, { installed: true, alreadyActive: false });
  assert.deepEqual(second, { installed: true, alreadyActive: true });
  assert.equal(controlled.frames.length, 1);

  const unknown = controlledHost();
  const existing = { owner: 'unknown-owner', version: 9 };
  Object.defineProperty(unknown.host, '__azhouStartup', { value: existing, configurable: true });
  assert.deepEqual(installStartup(payload, unknown.host), {
    installed: false, alreadyActive: false, reason: 'owner-conflict',
  });
  assert.equal(unknown.host.__azhouStartup, existing);
  assert.equal(unknown.frames.length, 0);
});

test('dispose is idempotent and removes only its owned frame and listener', () => {
  const controlled = controlledHost();
  installStartup(function () {}, controlled.host);
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

  assert.deepEqual(installStartup(payload, controlled.host), { installed: true, alreadyActive: false });
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
  installStartup(payload, controlled.host);
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
  installStartup(function () {}, controlled.host);
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
  installStartup(function () {}, controlled.host);
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
    installStartup(payload, controlled.host);
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
  installStartup(payload, controlled.host);
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
  installStartup(payload, controlled.host);
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
  installStartup(payload, controlled.host);
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
  assert.deepEqual(installStartup(function () {}, unknown.host), {
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
  assert.deepEqual(installStartup(function () {}, supported.host), { installed: true, alreadyActive: false });
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

  installStartup(payload, controlled.host);
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
  installStartup(payload, controlled.host);
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

test('wallpaper retry refuses disabled, missing, and unknown-owner requests', async () => {
  const noRequest = controlledHost();
  const noRequestPayload = function (_window, _document, _location, _performance, _indexedDB,
    _Image, _Path2D, _URL, _raf, _caf, _setTimeout, _clearTimeout, _module, SEND, frameSpec) {
    SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
  };
  installStartup(noRequestPayload, noRequest.host);
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
  installStartup(disabledPayload, disabled.host);
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
  installStartup(unknownPayload, unknown.host);
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
  installStartup(payload, controlled.host);
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
  installStartup(payload, controlled.host);
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
  installStartup(payload, controlled.host);
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
