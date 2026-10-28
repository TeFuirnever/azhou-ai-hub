import assert from 'node:assert/strict';
import test from 'node:test';
import { installStartup } from '../extension/renderer.mjs';

function fixture() {
  const listeners = new Set(), frames = [];
  const document = {
    documentElement: { appendChild(node) { node.parentNode = this; } },
    body: {}, activeElement: null, hasFocus: () => true,
    createElement(tag) {
      const node = { style: {}, children: [], setAttribute() {},
        appendChild(child) { this.children.push(child); },
        addEventListener() {}, removeEventListener() {}, remove() { this.removed = true; } };
      node.attachShadow = () => ({ appendChild(child) { node.appendChild(child); } });
      if (tag === 'iframe') {
        node.contentWindow = { location: new URL('about:blank'), performance: {}, indexedDB: {}, URL,
          document: { documentElement: {} }, addEventListener() {}, removeEventListener() {},
          setTimeout, clearTimeout, requestAnimationFrame() {}, cancelAnimationFrame() {} };
        frames.push(node);
      }
      return node;
    },
  };
  const host = { document, location: new URL('app://-/index.html?initialRoute=%2F'),
    addEventListener(type, fn) { if (type === 'message') listeners.add(fn); },
    removeEventListener(type, fn) { if (type === 'message') listeners.delete(fn); },
    setTimeout() { return 1; }, clearTimeout() {} };
  const runs = [];
  const payload = (...args) => { runs.push({ spec: args[14], send: args[13] }); return { dispose() {} }; };
  return { host, frames, payload, runs, listeners };
}

test('saving settings closes the editor without replaying the startup animation', () => {
  const { host, frames, payload, listeners } = fixture();
  installStartup(payload, host);
  const api = host.__azhouStartup;
  const send = (frame, action, extra = {}) => {
    for (const listener of listeners) listener({ source: frame.contentWindow,
      data: { type: 'azhou-startup', action, runId: api.status().runId, ...extra } });
  };
  send(frames[0], 'ready');
  send(frames[0], 'complete', { skipped: false });
  assert.equal(api.openSettings(), true);
  send(frames[1], 'ready');
  const settingsRun = api.status().runId;
  send(frames[1], 'settings-close');
  assert.equal(frames.length, 2, 'saving does not create an animation replay');
  assert.equal(api.status().runId, settingsRun);
  assert.equal(api.status().phase, 'complete');
  assert.deepEqual(api.status().completion, { cause: 'settings-save', beforeReady: false });
  assert.equal(frames[1].removed, true);
  api.dispose();
});

test('saved wallpaper can finish after the settings editor closes and remains cancellable', async () => {
  for (const dispose of [false, true]) {
    const { host, frames, payload, runs, listeners } = fixture();
    let finish, isCurrent;
    payload.applyWallpaper = (_request, current) => new Promise(resolve => { finish = resolve; isCurrent = current; });
    installStartup(payload, host);
    const api = host.__azhouStartup;
    const send = (frame, action, extra = {}) => {
      for (const listener of listeners) listener({ source: frame.contentWindow,
        data: { type: 'azhou-startup', action, runId: api.status().runId, ...extra } });
    };
    send(frames[0], 'ready');
    send(frames[0], 'complete', { skipped: false });
    api.openSettings();
    send(frames[1], 'ready');
    const pending = runs[1].send({ type: 'azhou-startup', action: 'background', runId: api.status().runId,
      image: 'data:image/png;base64,aGVsbG8=', strength: 42 });
    send(frames[1], 'settings-close');
    if (dispose) api.dispose();
    assert.equal(isCurrent(), !dispose);
    finish({ applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-timeout' });
    await pending;
    if (!dispose) assert.equal(api.status().wallpaper.failureCode, 'shell-timeout');
    api.dispose();
  }
});
