import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import test from 'node:test';
import { createWallpaperApplicator } from '../wallpaper/apply.js';

const VALUE = { image: 'data:image/png;base64,AA==', strength: 37, surface: 'rgb(10, 20, 30)' };
const FRAME_SELECTOR = '[data-app-shell-frame]';
const SURFACE_SELECTOR = '[data-app-shell-main-surface],[data-app-shell-page-surface]';
const ATTRIBUTE_FILTER = ['data-app-shell-frame', 'data-app-shell-main-surface', 'data-app-shell-page-surface'];

function createHost({ shell = false, observer = true, observeThrows = false, digest = webcrypto } = {}) {
  const observers = [];
  const timers = [];
  const attributes = new Set();
  let rootPresent = shell;
  const applicationRoot = {
    querySelector(selector) {
      if (selector === FRAME_SELECTOR && attributes.has('data-app-shell-frame')) return {};
      if (selector === SURFACE_SELECTOR
          && (attributes.has('data-app-shell-main-surface') || attributes.has('data-app-shell-page-surface'))) return {};
      return null;
    },
  };
  if (shell) {
    attributes.add('data-app-shell-frame');
    attributes.add('data-app-shell-main-surface');
  }
  const document = {
    body: {}, documentElement: {},
    getElementById(id) { return id === 'root' && rootPresent ? applicationRoot : null; },
  };
  class Observer {
    constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
    observe(target, options) {
      this.target = target;
      this.options = options;
      if (observeThrows) throw new Error('observer denied');
    }
    disconnect() { this.disconnected = true; }
    trigger() { this.callback(); }
  }
  const host = {
    document,
    crypto: digest,
    atob: globalThis.atob,
    setTimeout(callback, delay) {
      const timer = { callback, delay, cleared: false, fire() { callback(); } };
      timers.push(timer);
      return timer;
    },
    clearTimeout(timer) { if (timer) timer.cleared = true; },
  };
  if (observer) host.MutationObserver = Observer;
  return {
    host, observers, timers, applicationRoot,
    mountRoot() { rootPresent = true; },
    setAttribute(name) { attributes.add(name); },
  };
}

function rendererRecorder() {
  const calls = [];
  return { calls, installRenderer(value) { calls.push(value); return { applied: true, imageDecoded: true }; } };
}

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 40; attempt++) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.fail('condition did not become true');
}

function expectedDigest() {
  return createHash('sha256').update(Buffer.from([0])).digest('hex');
}

test('an existing supported shell receives a verified image and the renderer result', async () => {
  const fixture = createHost({ shell: true });
  const renderer = rendererRecorder();
  const isCurrent = () => true;
  const apply = createWallpaperApplicator(renderer.installRenderer, { version: '0.9.0', css: 'body{color:red}' }, fixture.host);

  const result = await apply(VALUE, isCurrent);

  assert.deepEqual(result, { applied: true, imageDecoded: true });
  assert.equal(renderer.calls.length, 1);
  assert.deepEqual(renderer.calls[0], {
    version: '0.9.0', image: VALUE.image, imageSHA256: expectedDigest(), css: 'body{color:red}',
    strength: VALUE.strength, surface: VALUE.surface, isCurrent,
  });
  assert.equal(fixture.observers.length, 0);
  assert.equal(fixture.timers.length, 0);
});

test('a late attribute-based shell is awaited without expiring a naturally completed caller', async () => {
  const fixture = createHost();
  const renderer = rendererRecorder();
  let playback = 'playing';
  const isCurrent = () => playback !== 'cancelled';
  const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '.wallpaper{}' }, fixture.host);
  const pending = apply(VALUE, isCurrent);
  await waitFor(() => fixture.observers.length === 1 && fixture.timers.length === 1);
  const [observer] = fixture.observers;
  const [timer] = fixture.timers;
  assert.equal(observer.target, fixture.host.document.documentElement);
  assert.equal(observer.options.attributes, true);
  assert.deepEqual(observer.options.attributeFilter, ATTRIBUTE_FILTER);
  assert.equal(timer.delay, 60000);

  fixture.mountRoot();
  fixture.setAttribute('data-app-shell-frame');
  observer.trigger();
  assert.equal(renderer.calls.length, 0, 'a frame alone is not a supported shell');
  fixture.setAttribute('data-app-shell-page-surface');
  playback = 'completed';
  assert.equal(isCurrent(), true, 'natural completion keeps the caller valid for wallpaper setup');
  observer.trigger();

  assert.deepEqual(await pending, { applied: true, imageDecoded: true });
  assert.equal(renderer.calls.length, 1);
  assert.equal(renderer.calls[0].isCurrent, isCurrent);
  assert.equal(observer.disconnected, true);
  assert.equal(timer.cleared, true);
  timer.fire();
  assert.equal(renderer.calls.length, 1, 'a settled wait cannot install twice');
});

test('an unsupported observer or an observer setup exception returns a typed shell failure', async t => {
  await t.test('observer is unavailable', async () => {
    const fixture = createHost({ observer: false });
    const renderer = rendererRecorder();
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    assert.deepEqual(await apply(VALUE), {
      applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-unsupported', imageDecoded: false,
    });
    assert.equal(fixture.timers.length, 0);
    assert.equal(renderer.calls.length, 0);
  });

  await t.test('observe throws', async () => {
    const fixture = createHost({ observeThrows: true });
    const renderer = rendererRecorder();
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    assert.deepEqual(await apply(VALUE), {
      applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-unsupported', imageDecoded: false,
    });
    assert.equal(fixture.observers[0].disconnected, true);
    assert.equal(fixture.timers.length, 0);
    assert.equal(renderer.calls.length, 0);
  });
});

test('a cold shell timeout clears its timer and disconnects its observer', async () => {
  const fixture = createHost();
  const renderer = rendererRecorder();
  const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
  const pending = apply(VALUE);
  await waitFor(() => fixture.observers.length === 1 && fixture.timers.length === 1);
  const [observer] = fixture.observers;
  const [timer] = fixture.timers;

  timer.fire();

  assert.deepEqual(await pending, {
    applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-timeout', imageDecoded: false,
  });
  assert.equal(timer.cleared, true);
  assert.equal(observer.disconnected, true);
  assert.equal(renderer.calls.length, 0);
});

test('cancellation is checked before digest, after digest, and while awaiting the shell', async t => {
  await t.test('already stale work does not decode or observe', async () => {
    let digestCalls = 0;
    const fixture = createHost({ shell: true, digest: { subtle: { digest() { digestCalls++; return webcrypto.subtle.digest(...arguments); } } } });
    const renderer = rendererRecorder();
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    assert.deepEqual(await apply(VALUE, () => false), { applied: false, reason: 'operation-cancelled' });
    assert.equal(digestCalls, 0);
    assert.equal(renderer.calls.length, 0);
  });

  await t.test('stale work after digest does not wait for a shell', async () => {
    let resolveDigest;
    const fixture = createHost({ digest: { subtle: { digest: () => new Promise(resolve => { resolveDigest = resolve; }) } } });
    const renderer = rendererRecorder();
    let current = true;
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    const pending = apply(VALUE, () => current);
    await waitFor(() => typeof resolveDigest === 'function');
    current = false;
    resolveDigest(new Uint8Array(32).buffer);
    assert.deepEqual(await pending, { applied: false, reason: 'operation-cancelled' });
    assert.equal(fixture.observers.length, 0);
    assert.equal(renderer.calls.length, 0);
  });

  await t.test('stale work during shell waiting disconnects and clears resources', async () => {
    const fixture = createHost();
    const renderer = rendererRecorder();
    let current = true;
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    const pending = apply(VALUE, () => current);
    await waitFor(() => fixture.observers.length === 1 && fixture.timers.length === 1);
    current = false;
    fixture.observers[0].trigger();
    assert.deepEqual(await pending, { applied: false, reason: 'operation-cancelled', imageDecoded: false });
    assert.equal(fixture.observers[0].disconnected, true);
    assert.equal(fixture.timers[0].cleared, true);
    assert.equal(renderer.calls.length, 0);
  });

  await t.test('a caller invalidated immediately after shell resolution is not installed', async () => {
    const fixture = createHost();
    const renderer = rendererRecorder();
    let current = true;
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    const pending = apply(VALUE, () => current);
    await waitFor(() => fixture.observers.length === 1);
    fixture.mountRoot();
    fixture.setAttribute('data-app-shell-frame');
    fixture.setAttribute('data-app-shell-main-surface');
    fixture.observers[0].trigger();
    current = false;
    assert.deepEqual(await pending, { applied: false, reason: 'operation-cancelled', imageDecoded: false });
    assert.equal(renderer.calls.length, 0);
  });
});

test('invalid input is typed while digest and renderer failures stay at their original boundaries', async t => {
  await t.test('invalid input', async () => {
    const fixture = createHost({ shell: true });
    const renderer = rendererRecorder();
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    assert.deepEqual(await apply(null), {
      applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-unavailable', imageDecoded: false,
    });
    assert.equal(renderer.calls.length, 0);
  });

  await t.test('missing crypto support', async () => {
    const fixture = createHost({ shell: true, digest: null });
    const apply = createWallpaperApplicator(() => assert.fail('renderer must not run'), { version: '1', css: '' }, fixture.host);
    assert.deepEqual(await apply(VALUE), {
      applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-unavailable', imageDecoded: false,
    });
  });

  await t.test('missing base64 decoder', async () => {
    const fixture = createHost({ shell: true });
    fixture.host.atob = undefined;
    const apply = createWallpaperApplicator(() => assert.fail('renderer must not run'), { version: '1', css: '' }, fixture.host);
    assert.deepEqual(await apply(VALUE), {
      applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-unavailable', imageDecoded: false,
    });
  });

  await t.test('digest rejection is propagated without shell observation', async () => {
    const fixture = createHost({ digest: { subtle: { digest: async () => { throw new Error('digest failed'); } } } });
    const renderer = rendererRecorder();
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    await assert.rejects(apply(VALUE), /digest failed/);
    assert.equal(fixture.observers.length, 0);
    assert.equal(renderer.calls.length, 0);
  });

  await t.test('renderer rejection is propagated after a supported shell', async () => {
    const fixture = createHost({ shell: true });
    const apply = createWallpaperApplicator(async () => { throw new Error('renderer failed'); },
      { version: '1', css: '' }, fixture.host);
    await assert.rejects(apply(VALUE), /renderer failed/);
  });
});
