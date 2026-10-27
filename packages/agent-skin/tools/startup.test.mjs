import assert from 'node:assert/strict';
import test from 'node:test';
import { installStartup } from '../extension/renderer.mjs';

const mainURL = 'app://-/index.html?initialRoute=%2F';

function controlledHost({ body = true } = {}) {
  const listeners = new Set();
  const keyListeners = new Set();
  const observers = [];
  const frames = [];
  const timers = [];
  const document = {
    documentElement: {
      appendChild(frame) { frames.push(frame); frame.parentNode = this; },
    },
    activeElement: null,
    hasFocus: () => true,
    createElement(tag) {
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
    MutationObserver: class MutationObserver {
      constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
      observe() { this.observing = true; }
      disconnect() { this.disconnected = true; this.observing = false; }
      trigger() { if (this.observing) this.callback([]); }
    },
    addEventListener(type, listener) {
      if (type === 'message') listeners.add(listener);
      if (type === 'keydown') keyListeners.add(listener);
    },
    removeEventListener(type, listener) {
      if (type === 'message') listeners.delete(listener);
      if (type === 'keydown') keyListeners.delete(listener);
    },
    send(data, source) {
      for (const listener of listeners) listener({ data, source });
    },
    keydown(event) { for (const listener of keyListeners) listener(event); },
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
  return { host, frames, timers, observers, setBody: () => host.setBody(), listenerCount: () => listeners.size,
    keyListenerCount: () => keyListeners.size };
}

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
  assert.equal(frame.attributes.get('title'), 'Agent Skin startup');
  assert.equal(frame.attributes.get('aria-label'), 'Agent Skin startup overlay');
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

  const childShortcut = { metaKey: true, altKey: true, key: 'b', prevented: false,
    preventDefault() { this.prevented = true; } };
  firstFrame.contentWindow.dispatch('keydown', childShortcut);
  assert.equal(childShortcut.prevented, true);
  assert.equal(api.status().phase, 'settings');
  assert.equal(controlled.frames.length, 1, 'playing opens settings in the owned iframe');
  assert.equal(controlled.timers[0].cleared, true, 'the settings phase has no loading watchdog');

  const save = { type: 'azhou-startup', action: 'settings-close', runId: runs[0].runId };
  controlled.host.send(save, firstFrame.contentWindow);
  assert.equal(controlled.frames.length, 2, 'save creates one fresh play frame');
  assert.equal(api.status().phase, 'loading');
  assert.ok(api.status().runId > runs[0].runId);
  assert.equal(runs[1].intent, 'play');
  assert.equal(runs[1].assets, payload.assets);
  controlled.frames[1].contentWindow.flushAnimationFrame();
  assert.equal(api.status().phase, 'playing');

  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: runs[0].runId, skipped: true }, firstFrame.contentWindow);
  assert.equal(api.status().phase, 'playing', 'a late old frame cannot finish the current run');
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

  const parentShortcut = { metaKey: true, altKey: true, key: 'B', prevented: false,
    preventDefault() { this.prevented = true; } };
  controlled.host.keydown(parentShortcut);
  assert.equal(parentShortcut.prevented, true);
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
