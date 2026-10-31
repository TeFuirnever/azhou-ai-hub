import assert from 'node:assert/strict';
import test from 'node:test';
import { bootstrapStartup } from '../extension/bootstrap.mjs';

test('startup bootstrap wires host, version, CSS, assets, and factories with fixed property descriptors', () => {
  const installAnimation = () => {};
  const installRenderer = () => {};
  const createLocalization = () => {};
  const createImageSettings = () => {};
  const assets = Object.freeze({ wallpaper: 'data:image/png;base64,AA==' });
  const host = { document: {} };
  const wallpaper = () => {};
  const calls = [];
  const installStartup = (...args) => { calls.push(args); return 'startup-result'; };
  const createWallpaperApplicator = (...args) => {
    calls.push(args);
    return wallpaper;
  };

  const pageAdapter = { identify: () => ({ kind: 'matched', documentToken: 'app://-/index.html' }) };
  const result = bootstrapStartup({
    installStartup,
    installAnimation,
    createLocalization,
    createImageSettings,
    createWallpaperApplicator,
    installRenderer,
    version: '0.9.0',
    css: 'body { color: red; }',
    assets,
    host,
    pageAdapter,
  });

  assert.equal(result, 'startup-result');
  assert.deepEqual(calls, [
    [installRenderer, { version: '0.9.0', css: 'body { color: red; }' }, host],
    [installAnimation, host, pageAdapter],
  ]);
  assert.equal(Object.getOwnPropertyDescriptor(installAnimation, 'pageAdapter'), undefined,
    'the page adapter must not be smuggled through installAnimation static properties');
  for (const [key, value] of Object.entries({
    assets,
    createLocalization,
    createImageSettings,
    applyWallpaper: wallpaper,
  })) {
    assert.deepEqual(Object.getOwnPropertyDescriptor(installAnimation, key), {
      value,
      writable: false,
      enumerable: false,
      configurable: false,
    });
  }
});

test('startup bootstrap propagates applicator and startup installation errors', () => {
  const installAnimation = () => {};
  const installRenderer = () => {};
  const host = {};
  const factoryError = new Error('applicator failed');
  const startupError = new Error('startup failed');
  let startupCalls = 0;

  assert.throws(() => bootstrapStartup({
    installStartup() { startupCalls++; },
    installAnimation,
    createLocalization() {},
    createImageSettings() {},
    createWallpaperApplicator() { throw factoryError; },
    installRenderer,
    version: '1',
    css: '',
    assets: {},
    host,
  }), error => error === factoryError);
  assert.equal(startupCalls, 0);

  assert.throws(() => bootstrapStartup({
    installStartup() { throw startupError; },
    installAnimation: () => {},
    createLocalization() {},
    createImageSettings() {},
    createWallpaperApplicator() { return () => {}; },
    installRenderer,
    version: '1',
    css: '',
    assets: {},
    host,
  }), error => error === startupError);
});

test('bootstrap passes the page adapter explicitly as the third installStartup argument', () => {
  const installAnimation = () => {};
  const installRenderer = () => {};
  const host = { document: {} };
  const pageAdapter = Object.freeze({
    identify: () => ({ kind: 'matched', documentToken: 'app://-/index.html?initialRoute=%2F' }),
    observeAppearance: () => ({}),
    appearanceText: () => ({ t: () => '' }),
    mountEntry: () => ({ remove() {} }),
    settingsEnvironment: () => ({ indexedDB: undefined }),
  });
  const startupArguments = [];
  const result = bootstrapStartup({
    installStartup: (...args) => { startupArguments.push(args); return 'installed'; },
    installAnimation,
    createLocalization: () => {},
    createImageSettings: () => {},
    createWallpaperApplicator: () => () => {},
    installRenderer,
    version: '1',
    css: '',
    assets: {},
    host,
    pageAdapter,
  });

  assert.equal(result, 'installed');
  assert.equal(startupArguments.length, 1);
  assert.equal(startupArguments[0].length, 3, 'installStartup receives exactly three arguments');
  assert.equal(startupArguments[0][0], installAnimation);
  assert.equal(startupArguments[0][1], host);
  assert.equal(startupArguments[0][2], pageAdapter, 'the third argument is the explicit page adapter');
  assert.equal(Object.getOwnPropertyDescriptor(installAnimation, 'pageAdapter'), undefined,
    'the adapter is never attached to installAnimation as a static property');
});
