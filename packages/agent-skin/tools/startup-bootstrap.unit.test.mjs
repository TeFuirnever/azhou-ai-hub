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
  });

  assert.equal(result, 'startup-result');
  assert.deepEqual(calls, [
    [installRenderer, { version: '0.9.0', css: 'body { color: red; }' }, host],
    [installAnimation, host],
  ]);
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
