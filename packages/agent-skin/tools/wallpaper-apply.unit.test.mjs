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

test('the image digest and appearance use one snapshot during asynchronous preparation', async t => {
  await t.test('input changes while the image digest is pending', async () => {
    let finishDigest;
    const digest = { subtle: { digest: (...args) => new Promise((resolve, reject) => {
      finishDigest = () => webcrypto.subtle.digest(...args).then(resolve, reject);
    }) } };
    const fixture = createHost({ shell: true, digest });
    const renderer = rendererRecorder();
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    const input = { ...VALUE };
    const pending = apply(input);
    await waitFor(() => typeof finishDigest === 'function');
    Object.assign(input, { image: 'data:image/png;base64,AQ==', strength: 72, surface: 'white' });
    finishDigest();
    assert.deepEqual(await pending, { applied: true, imageDecoded: true });
    assert.equal(renderer.calls.length, 1);
    assert.equal(renderer.calls[0].image, VALUE.image);
    assert.equal(renderer.calls[0].imageSHA256, expectedDigest());
    assert.equal(renderer.calls[0].strength, VALUE.strength);
    assert.equal(renderer.calls[0].surface, VALUE.surface);
  });

  await t.test('input changes while the supported shell is mounting', async () => {
    const fixture = createHost();
    const renderer = rendererRecorder();
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '' }, fixture.host);
    const input = { ...VALUE };
    const pending = apply(input);
    await waitFor(() => fixture.observers.length === 1);
    Object.assign(input, { image: 'data:image/png;base64,AQ==', strength: 72, surface: 'white' });
    fixture.mountRoot();
    fixture.setAttribute('data-app-shell-frame');
    fixture.setAttribute('data-app-shell-main-surface');
    fixture.observers[0].trigger();
    assert.deepEqual(await pending, { applied: true, imageDecoded: true });
    assert.equal(renderer.calls.length, 1);
    assert.equal(renderer.calls[0].image, VALUE.image);
    assert.equal(renderer.calls[0].imageSHA256, expectedDigest());
    assert.equal(renderer.calls[0].strength, VALUE.strength);
    assert.equal(renderer.calls[0].surface, VALUE.surface);
  });
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


test('a changing host adapter cannot cross the asynchronous apply boundary', async t => {
  const unsupported = { applied: false, reason: 'wallpaper-unsupported', failureCode: 'shell-unsupported', imageDecoded: false };
  function adapterFor(shellState) {
    return { controllerWallpaper: { owner: 'azhou.zcode-startup-animation' }, wallpaper: {
      validPage: () => true, shellState, surfaces: () => [], css: 'original', scope: 'original',
      attributes: { surfaceMarker: 'data-test-surface', observeFilter: ['class'] },
    } };
  }
  await t.test('CSS changes while digest is pending', async () => {
    let finishDigest;
    const digest = { subtle: { digest: (...args) => new Promise((resolve, reject) => {
      finishDigest = () => webcrypto.subtle.digest(...args).then(resolve, reject);
    }) } };
    const fixture = createHost({ digest }), renderer = rendererRecorder();
    const adapter = adapterFor(() => 'ready');
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
    const pending = apply(VALUE);
    await waitFor(() => typeof finishDigest === 'function');
    adapter.wallpaper.css = 'foreign'; finishDigest();
    assert.deepEqual(await pending, unsupported);
    assert.equal(renderer.calls.length, 0);
  });
  for (const field of ['validPage', 'shellState', 'scope', 'wallpaper', 'attributes', 'marker', 'controller']) {
    await t.test(field + ' changes while digest is pending', async () => {
      let finishDigest;
      const digest = { subtle: { digest: (...args) => new Promise((resolve, reject) => {
        finishDigest = () => webcrypto.subtle.digest(...args).then(resolve, reject);
      }) } };
      const fixture = createHost({ digest }), renderer = rendererRecorder();
      const adapter = adapterFor(() => 'ready');
      const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
      const pending = apply(VALUE);
      await waitFor(() => typeof finishDigest === 'function');
      if (field === 'validPage') adapter.wallpaper.validPage = () => false;
      if (field === 'shellState') adapter.wallpaper.shellState = () => 'ready';
      if (field === 'scope') adapter.wallpaper.scope = 'foreign';
      if (field === 'wallpaper') adapter.wallpaper = { ...adapter.wallpaper };
      if (field === 'attributes') adapter.wallpaper.attributes = { ...adapter.wallpaper.attributes };
      if (field === 'marker') adapter.wallpaper.attributes.surfaceMarker = 'foreign';
      if (field === 'controller') adapter.controllerWallpaper = { ...adapter.controllerWallpaper };
      finishDigest();
      assert.deepEqual(await pending, unsupported);
      assert.equal(renderer.calls.length, 0);
    });
  }
  await t.test('cancellation keeps precedence when the adapter also changes', async () => {
    let finishDigest, current = true;
    const digest = { subtle: { digest: (...args) => new Promise((resolve, reject) => {
      finishDigest = () => webcrypto.subtle.digest(...args).then(resolve, reject);
    }) } };
    const fixture = createHost({ digest }), renderer = rendererRecorder();
    const adapter = adapterFor(() => 'ready');
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
    const pending = apply(VALUE, () => current);
    await waitFor(() => typeof finishDigest === 'function');
    adapter.wallpaper.css = 'foreign'; current = false; finishDigest();
    assert.deepEqual(await pending, { applied: false, reason: 'operation-cancelled' });
    assert.equal(renderer.calls.length, 0);
  });
  await t.test('surface method changes while shell is pending', async () => {
    const fixture = createHost(), renderer = rendererRecorder();
    let ready = false;
    const adapter = adapterFor(() => ready ? 'ready' : null);
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
    const pending = apply(VALUE);
    await waitFor(() => fixture.observers.length === 1);
    adapter.wallpaper.surfaces = () => ['foreign']; ready = true; fixture.observers[0].trigger();
    assert.deepEqual(await pending, unsupported);
    assert.equal(renderer.calls.length, 0);
    assert.equal(fixture.observers[0].disconnected, true);
    assert.equal(fixture.timers[0].cleared, true);
  });
  await t.test('adapter change immediately after timeout is reported as unsupported', async () => {
    const fixture = createHost(), renderer = rendererRecorder();
    const adapter = adapterFor(() => null);
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
    const pending = apply(VALUE);
    await waitFor(() => fixture.timers.length === 1);
    fixture.timers[0].fire();
    adapter.wallpaper.css = 'foreign';
    assert.deepEqual(await pending, unsupported);
    assert.equal(renderer.calls.length, 0);
  });
  await t.test('shell callback changes owner during its own execution', async () => {
    const fixture = createHost(), renderer = rendererRecorder();
    const adapter = adapterFor(() => { adapter.controllerWallpaper.owner = 'foreign'; return 'ready'; });
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
    assert.deepEqual(await apply(VALUE), unsupported);
    assert.equal(renderer.calls.length, 0);
  });
  await t.test('observer filter changes while shell is pending', async () => {
    const fixture = createHost(), renderer = rendererRecorder();
    let ready = false;
    const adapter = adapterFor(() => ready ? 'ready' : null);
    const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
    const pending = apply(VALUE);
    await waitFor(() => fixture.observers.length === 1);
    adapter.wallpaper.attributes.observeFilter.push('foreign');
    assert.deepEqual(fixture.observers[0].options.attributeFilter, ['class']);
    ready = true; fixture.observers[0].trigger();
    assert.deepEqual(await pending, unsupported);
    assert.equal(renderer.calls.length, 0);
  });
});

test('a stable mutable adapter keeps its receiver and can be changed between requests', async () => {
  const fixture = createHost(), renderer = rendererRecorder();
  const adapter = { controllerWallpaper: { owner: 'azhou.zcode-startup-animation' }, wallpaper: {
    shellState() { assert.equal(this, adapter.wallpaper); return 'ready'; }, css: 'first',
    attributes: { surfaceMarker: 'data-test-surface', observeFilter: ['class'] },
  } };
  adapter.wallpaper.attributes.observeFilter.every = null;
  const apply = createWallpaperApplicator(renderer.installRenderer, { version: '1', css: '', pageAdapter: adapter }, fixture.host);
  assert.equal((await apply(VALUE)).applied, true);
  assert.equal(renderer.calls[0].pageAdapter, adapter);
  adapter.wallpaper.css = 'next request';
  assert.equal((await apply(VALUE)).applied, true);
  assert.equal(renderer.calls[1].pageAdapter, adapter);
});

test('ZCode uses its explicit shell port and passes the same bound adapter to the renderer', async () => {
  const fixture = createHost({ shell: false });
  const renderer = rendererRecorder();
  const adapter = Object.freeze({ wallpaper: Object.freeze({
    shellState(isCurrent, host) { assert.equal(host, fixture.host);return isCurrent() ? 'ready' : 'cancelled'; },
    attributes: Object.freeze({ surfaceMarker: 'data-azhou-zcode-wallpaper-surface',
      observeFilter: ['data-testid', 'hidden', 'aria-hidden', 'class', 'style'] }),
  }) });
  const apply = createWallpaperApplicator(renderer.installRenderer, { version: '0.9.0', css: 'synthetic-css', pageAdapter: adapter }, fixture.host);
  assert.equal((await apply(VALUE, () => true)).applied, true);
  assert.equal(renderer.calls[0].pageAdapter, adapter);
  assert.equal(fixture.observers.length, 0);
});
