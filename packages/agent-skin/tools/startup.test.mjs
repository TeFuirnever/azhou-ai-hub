import assert from 'node:assert/strict';
import test from 'node:test';
import { installStartup } from '../extension/renderer.mjs';

const mainURL = 'app://-/index.html?initialRoute=%2F';
const testOnlyProbe = '/* isolated test-only startup probe */';

function controlledHost() {
  const listeners = new Set();
  const frames = [];
  const timers = [];
  const host = {
    location: new URL(mainURL),
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
  const mount = (_host, payload, runId) => {
    const contentWindow = {};
    const frame = { payload, runId, contentWindow, removed: false };
    frame.remove = () => { frame.removed = true; };
    frames.push(frame);
    return frame;
  };
  return { host, frames, timers, mount, listenerCount: () => listeners.size };
}

test('install exposes a typed loading status and mounts one controlled frame', () => {
  const controlled = controlledHost();
  const result = installStartup(testOnlyProbe, controlled.host, controlled.mount);
  assert.deepEqual(result, { installed: true, alreadyActive: false });
  assert.equal(controlled.frames.length, 1);
  assert.equal(controlled.frames[0].payload, testOnlyProbe);
  assert.ok(Number.isSafeInteger(controlled.frames[0].runId) && controlled.frames[0].runId > 0);
  assert.equal(controlled.listenerCount(), 1);

  const status = controlled.host.__azhouStartup.status();
  assert.deepEqual({
    owner: status.owner,
    version: status.version,
    phase: status.phase,
    runId: status.runId,
    ready: status.ready,
    completed: status.completed,
    overlay: status.overlay,
    reason: status.reason,
  }, {
    owner: 'azhou-codex-startup', version: 1, phase: 'loading', runId: controlled.frames[0].runId,
    ready: false, completed: false, overlay: true, reason: '',
  });
  assert.deepEqual(status.wallpaper, { applied: false, reason: '', imageDecoded: false });
  assert.equal(status.completion, null);
});

test('only the current frame and run can mark startup ready', () => {
  const controlled = controlledHost();
  installStartup(testOnlyProbe, controlled.host, controlled.mount);
  const { runId, contentWindow } = controlled.frames[0];
  const message = { type: 'azhou-startup', action: 'ready', runId };

  controlled.host.send(message, {});
  controlled.host.send({ ...message, runId: runId + 1 }, contentWindow);
  controlled.host.send({ ...message, action: 'unknown' }, contentWindow);
  assert.equal(controlled.host.__azhouStartup.status().phase, 'loading');

  controlled.host.send(message, contentWindow);
  assert.equal(controlled.host.__azhouStartup.status().phase, 'playing');
  assert.equal(controlled.host.__azhouStartup.status().ready, true);
  controlled.host.send(message, contentWindow);
  assert.equal(controlled.host.__azhouStartup.status().phase, 'playing');
});

test('a skip during loading closes the overlay without claiming readiness', () => {
  const controlled = controlledHost();
  installStartup(testOnlyProbe, controlled.host, controlled.mount);
  const frame = controlled.frames[0];
  controlled.host.send({ type: 'azhou-startup', action: 'complete', runId: frame.runId, skipped: true }, frame.contentWindow);

  const status = controlled.host.__azhouStartup.status();
  assert.equal(status.phase, 'complete');
  assert.equal(status.ready, false);
  assert.equal(status.completed, true);
  assert.equal(status.overlay, false);
  assert.deepEqual(status.completion, { cause: 'skip', beforeReady: true });
  assert.equal(frame.removed, true);
  assert.equal(controlled.timers[0].cleared, true);
});

test('the loading watchdog releases a never-ready overlay and keeps a typed timeout receipt', () => {
  const controlled = controlledHost();
  installStartup(testOnlyProbe, controlled.host, controlled.mount);
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
  controlled.host.send({ type: 'azhou-startup', action: 'ready', runId: frame.runId }, frame.contentWindow);
  assert.equal(controlled.host.__azhouStartup.status().ready, false);
});

test('install does not replace an existing controller or an unknown owner', () => {
  const controlled = controlledHost();
  const first = installStartup(testOnlyProbe, controlled.host, controlled.mount);
  const second = installStartup(testOnlyProbe, controlled.host, controlled.mount);
  assert.deepEqual(first, { installed: true, alreadyActive: false });
  assert.deepEqual(second, { installed: true, alreadyActive: true });
  assert.equal(controlled.frames.length, 1);

  const unknown = controlledHost();
  const existing = { owner: 'unknown-owner', version: 9 };
  Object.defineProperty(unknown.host, '__azhouStartup', { value: existing, configurable: true });
  assert.deepEqual(installStartup(testOnlyProbe, unknown.host, unknown.mount), {
    installed: false, alreadyActive: false, reason: 'owner-conflict',
  });
  assert.equal(unknown.host.__azhouStartup, existing);
  assert.equal(unknown.frames.length, 0);
});

test('dispose is idempotent and removes only its owned frame and listener', () => {
  const controlled = controlledHost();
  installStartup(testOnlyProbe, controlled.host, controlled.mount);
  const api = controlled.host.__azhouStartup;
  const frame = controlled.frames[0];
  assert.deepEqual(api.dispose(), { disposed: true });
  assert.deepEqual(api.dispose(), { disposed: true });
  assert.equal(Object.hasOwn(controlled.host, '__azhouStartup'), false);
  assert.equal(controlled.listenerCount(), 0);
  assert.equal(frame.removed, true);
  assert.equal(controlled.timers[0].cleared, true);
});
