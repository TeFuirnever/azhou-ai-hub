import assert from 'node:assert/strict';
import test from 'node:test';
import { installStartup } from '../extension/renderer.mjs';

const mainURL = 'app://-/index.html?initialRoute=%2F';

function controlledHost() {
  const listeners = new Set();
  const frames = [];
  const timers = [];

  const host = {
    location: new URL(mainURL),
    document: {
      documentElement: {
        appendChild(frame) { frames.push(frame); },
      },
      createElement(tag) {
        assert.equal(tag, 'iframe');
        const callbacks = [];
        const contentWindow = {
          location: new URL('about:blank'),
          performance: { now: () => 0 },
          indexedDB: {},
          Image: class Image {},
          Path2D: class Path2D {},
          URL,
          document: { documentElement: {} },
          requestAnimationFrame(callback) { callbacks.push(callback); return callbacks.length; },
          cancelAnimationFrame(id) { callbacks[id - 1] = null; },
          setTimeout(callback, delay) { return { callback, delay }; },
          clearTimeout(timer) { timer.cleared = true; },
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
          remove() { this.removed = true; },
        };
        return frame;
      },
    },
    addEventListener(type, listener) {
      if (type === 'message') listeners.add(listener);
    },
    removeEventListener(type, listener) {
      if (type === 'message') listeners.delete(listener);
    },
    send(data, source) {
      for (const listener of listeners) listener({ data, source });
    },
    setTimeout(callback, delay) {
      const timer = { callback, delay, cleared: false };
      timers.push(timer);
      return timer;
    },
    clearTimeout(timer) { timer.cleared = true; },
  };
  return { host, frames, timers, listenerCount: () => listeners.size };
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
