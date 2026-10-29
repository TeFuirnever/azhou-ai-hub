import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import vm from 'node:vm';

const TEST_PATH = fileURLToPath(import.meta.url);
const PACKAGE_ROOT = resolve(dirname(TEST_PATH), '..');
const GENERATED_ROOT = join(PACKAGE_ROOT, '.build', 'unit-generated-sources');
const STARTUP_TEST_RUNNER = join(PACKAGE_ROOT, 'tools', 'test-startup-native.py');
const STARTUP_TEST_BINARY = join(PACKAGE_ROOT, '.build', 'startup-native-tests');
const APP_HREF = 'app://-/index.html?initialRoute=%2F';
const EXPRESSION_KEYS = [
  'statusSource', 'applyGuardSource', 'retrySource', 'restoreSource',
  'inspectExpression', 'statusExpression', 'disposeExpression', 'installExpression',
];

let generatedSources = {};
let sourcePaths = {};
let scripts = {};
const nativeExpressionsAvailable = process.platform === 'darwin';

if (nativeExpressionsAvailable) {
  execFileSync('python3', ['-B', STARTUP_TEST_RUNNER], { cwd: PACKAGE_ROOT, stdio: 'inherit' });
  const emitted = execFileSync(STARTUP_TEST_BINARY, ['--emit-unit-expressions'], {
    cwd: PACKAGE_ROOT, encoding: 'utf8', maxBuffer: 4 * 1024 * 1024,
  });
  generatedSources = JSON.parse(emitted);
  assert.deepEqual(Object.keys(generatedSources).sort(), [...EXPRESSION_KEYS].sort());
  mkdirSync(GENERATED_ROOT, { recursive: true });
  for (const key of EXPRESSION_KEYS) {
    assert.equal(typeof generatedSources[key], 'string');
    assert.ok(generatedSources[key].length > 0);
    const path = join(GENERATED_ROOT, `Native-Wallpaper.${key}.js`);
    sourcePaths[key] = path;
    writeFileSync(path, generatedSources[key], 'utf8');
    const source = readFileSync(path, 'utf8');
    assert.equal(source, generatedSources[key], `${key} is stored byte-for-byte`);
    scripts[key] = new vm.Script(source, { filename: path });
  }
}

function pageContext({ href = APP_HREF, topLevel = true } = {}) {
  const window = {};
  window.top = topLevel ? window : {};
  return vm.createContext({ URL, location: { href }, window });
}

function defineGlobal(context, key, descriptor) {
  Object.defineProperty(context, key, { configurable: true, ...descriptor });
}

function defineDataGlobal(context, key, value) {
  defineGlobal(context, key, { value, writable: true, enumerable: true });
}

function evaluate(key, context) {
  return scripts[key].runInContext(context);
}

function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

function startupAPI({ owner = 'azhou-codex-startup', version = 1,
  status = () => ({ phase: 'idle' }), retryWallpaper, dispose } = {}) {
  const api = {};
  Object.defineProperties(api, {
    owner: { value: owner, configurable: true, enumerable: true },
    version: { value: version, configurable: true, enumerable: true },
    status: { value: status, configurable: true, enumerable: true },
  });
  if (retryWallpaper) Object.defineProperty(api, 'retryWallpaper', { value: retryWallpaper, configurable: true });
  if (dispose) Object.defineProperty(api, 'dispose', { value: dispose, configurable: true });
  return api;
}

function wallpaperAPI({ owner = 'azhou.codex-startup-animation', version = '0.9.0',
  status = () => ({ applied: true, imageDecoded: true, matchedSurfaces: 3, backgroundMatched: true }), dispose } = {}) {
  const api = {};
  Object.defineProperties(api, {
    owner: { value: owner, configurable: true, enumerable: true },
    version: { value: version, configurable: true, enumerable: true },
    status: { value: status, configurable: true, enumerable: true },
  });
  if (dispose) Object.defineProperty(api, 'dispose', { value: dispose, configurable: true });
  return api;
}

function validStartupState(overrides = {}) {
  return {
    owner: 'azhou-codex-startup', version: 1, phase: 'completed', runId: 8,
    ready: true, completed: true, overlay: false,
    completion: { cause: 'natural', beforeReady: false },
    ...overrides,
  };
}

function unitTest(name, callback) {
  test(name, { skip: !nativeExpressionsAvailable }, callback);
}

unitTest('fresh native output is written byte-for-byte and attributed to each generated file path', () => {
  assert.deepEqual(Object.keys(sourcePaths).sort(), [...EXPRESSION_KEYS].sort());
  for (const key of EXPRESSION_KEYS) {
    assert.equal(readFileSync(sourcePaths[key], 'utf8'), generatedSources[key]);
  }
});

unitTest('inspect and status expressions expose the real controller status shape', async t => {
  await t.test('missing controller is reported without reading page globals beyond the URL', () => {
    const context = pageContext();
    assert.deepEqual(plain(evaluate('inspectExpression', context)), {
      href: APP_HREF, controllerPresent: false,
    });
    assert.deepEqual(plain(evaluate('statusExpression', context)), { href: APP_HREF, missing: true });
  });

  await t.test('controller methods are called on their owning API', () => {
    let receiver;
    const api = startupAPI({ status() { receiver = this; return { phase: 'playing', runId: 4 }; } });
    const context = pageContext();
    defineDataGlobal(context, '__azhouStartup', api);
    assert.deepEqual(plain(evaluate('inspectExpression', context)), { href: APP_HREF, controllerPresent: true });
    assert.deepEqual(plain(evaluate('statusExpression', context)), {
      href: APP_HREF, missing: false, status: { phase: 'playing', runId: 4 },
    });
    assert.equal(receiver, api);
  });

  await t.test('a throwing status getter remains a visible expression failure', async () => {
    const api = {};
    Object.defineProperty(api, 'status', { get() { throw new Error('status getter'); } });
    const context = pageContext();
    defineDataGlobal(context, '__azhouStartup', api);
    assert.throws(() => evaluate('statusExpression', context), /status getter/);
  });
});

unitTest('the wallpaper status source validates page identity and reports owned application state', async t => {
  await t.test('wrong route does not inspect either owner', () => {
    let calls = 0;
    const context = pageContext({ href: 'app://-/index.html?initialRoute=%2Favatar' });
    defineDataGlobal(context, '__azhouWallpaper', wallpaperAPI({ status() { calls++; return {}; } }));
    defineDataGlobal(context, '__azhouStartup', startupAPI({ status() { calls++; return {}; } }));
    const result = plain(evaluate('statusSource', context));
    assert.equal(result.reason, 'wrong-page');
    assert.deepEqual(result.startup, { installed: false });
    assert.equal(calls, 0);
  });

  await t.test('owned wallpaper and completed startup failure are combined', () => {
    const context = pageContext();
    const wallpaperState = {
      applied: true, imageDecoded: true, matchedSurfaces: 3, backgroundMatched: true, reason: 'applied',
    };
    const state = validStartupState({
      completion: { cause: 'natural', beforeReady: false },
      wallpaper: { applied: false, failureCode: 'shell-timeout' },
    });
    defineDataGlobal(context, '__azhouWallpaper', wallpaperAPI({ status: () => wallpaperState }));
    defineDataGlobal(context, '__azhouStartup', startupAPI({ status: () => state }));

    const result = plain(evaluate('statusSource', context));

    assert.equal(result.reason, 'applied');
    assert.equal(result.imageDecoded, true);
    assert.equal(result.failureCode, 'shell-timeout');
    assert.deepEqual(result.startup, {
      installed: true, owner: 'azhou-codex-startup', version: 1, phase: 'completed', runId: 8,
      ready: true, completed: true, overlay: false,
      completion: { cause: 'natural', beforeReady: false },
    });
  });

  await t.test('settings-save completion survives the native wallpaper status expression', () => {
    const context = pageContext();
    const completion = { cause: 'settings-save', beforeReady: false };
    defineDataGlobal(context, '__azhouWallpaper', wallpaperAPI());
    defineDataGlobal(context, '__azhouStartup', startupAPI({
      status: () => validStartupState({ completion }),
    }));

    const result = plain(evaluate('statusSource', context));

    assert.deepEqual(result.startup.completion, completion);
  });

  await t.test('invalid completion is removed and status method exceptions become fixed receipts', () => {
    const context = pageContext();
    defineDataGlobal(context, '__azhouWallpaper', wallpaperAPI({ status() { throw new Error('private'); } }));
    defineDataGlobal(context, '__azhouStartup', startupAPI({
      status: () => validStartupState({ completion: { cause: 'manual', beforeReady: 'no' } }),
    }));
    const result = plain(evaluate('statusSource', context));
    assert.equal(result.reason, 'owner-conflict');
    assert.deepEqual(result.startup.completion, null);
  });

  await t.test('owner getters are not invoked', () => {
    let getterCalls = 0;
    const wallpaper = {};
    Object.defineProperty(wallpaper, 'owner', { get() { getterCalls++; return 'azhou.codex-startup-animation'; } });
    const startup = {};
    Object.defineProperty(startup, 'owner', { get() { getterCalls++; return 'azhou-codex-startup'; } });
    const context = pageContext();
    defineDataGlobal(context, '__azhouWallpaper', wallpaper);
    defineDataGlobal(context, '__azhouStartup', startup);
    const result = plain(evaluate('statusSource', context));
    assert.equal(result.reason, 'owner-conflict');
    assert.deepEqual(result.startup, { installed: false });
    assert.equal(getterCalls, 0);
  });
});

unitTest('the apply guard accepts only recognized owners and callable data properties', () => {
  const empty = pageContext();
  assert.deepEqual(plain(evaluate('applyGuardSource', empty)), { state: 'ready', applied: false });

  const active = pageContext();
  defineDataGlobal(active, '__azhouStartup', startupAPI());
  assert.deepEqual(plain(evaluate('applyGuardSource', active)), { state: 'startup-active', applied: false });

  const startupConflict = pageContext();
  defineDataGlobal(startupConflict, '__azhouStartup', startupAPI({ owner: 'foreign' }));
  assert.deepEqual(plain(evaluate('applyGuardSource', startupConflict)), { state: 'owner-conflict', applied: false });

  const wallpaper = pageContext();
  defineDataGlobal(wallpaper, '__azhouWallpaper', wallpaperAPI({ dispose() {} }));
  assert.deepEqual(plain(evaluate('applyGuardSource', wallpaper)), { state: 'ready', applied: false });

  const unknown = pageContext();
  defineDataGlobal(unknown, '__azhouWallpaper', wallpaperAPI({ owner: 'foreign' }));
  assert.deepEqual(plain(evaluate('applyGuardSource', unknown)), { state: 'owner-conflict', applied: false });

  let getterCalls = 0;
  const accessor = {};
  Object.defineProperty(accessor, 'owner', { get() { getterCalls++; return 'azhou.codex-startup-animation'; } });
  const conflict = pageContext();
  defineDataGlobal(conflict, '__azhouWallpaper', accessor);
  assert.deepEqual(plain(evaluate('applyGuardSource', conflict)), { state: 'owner-conflict', applied: false });
  assert.equal(getterCalls, 0);
});

unitTest('retry validates page and owner, awaits retry, and sanitizes asynchronous decline', async t => {
  await t.test('wrong route', async () => {
    const context = pageContext({ href: 'app://-/index.html?initialRoute=%2Fquick-chat' });
    assert.deepEqual(plain(await evaluate('retrySource', context)), { state: 'owner-conflict', applied: false });
  });

  await t.test('missing or unknown controller', async () => {
    assert.deepEqual(plain(await evaluate('retrySource', pageContext())), {
      state: 'retry-unavailable', applied: false,
    });
    const context = pageContext();
    defineDataGlobal(context, '__azhouStartup', startupAPI({ owner: 'foreign', retryWallpaper: async () => ({}) }));
    assert.deepEqual(plain(await evaluate('retrySource', context)), { state: 'owner-conflict', applied: false });
  });

  await t.test('missing retry method', async () => {
    const context = pageContext();
    defineDataGlobal(context, '__azhouStartup', startupAPI());
    assert.deepEqual(plain(await evaluate('retrySource', context)), { state: 'retry-unavailable', applied: false });
  });

  await t.test('success retains the receiver and asynchronous decline is fixed', async () => {
    let receiver;
    const expected = { state: 'applied', applied: true };
    const success = pageContext();
    const api = startupAPI({ retryWallpaper() { receiver = this; return Promise.resolve(expected); } });
    Object.defineProperty(api, 'retryWallpaper', { value: api.retryWallpaper, configurable: true });
    defineDataGlobal(success, '__azhouStartup', api);
    assert.deepEqual(plain(await evaluate('retrySource', success)), expected);
    assert.equal(receiver, api);

    const declining = pageContext();
    defineDataGlobal(declining, '__azhouStartup', startupAPI({ retryWallpaper: async () => { throw new Error('private decline'); } }));
    assert.deepEqual(plain(await evaluate('retrySource', declining)), { state: 'retry-failed', applied: false });
  });

  await t.test('accessor properties are not executed', async () => {
    let getterCalls = 0;
    const api = {};
    Object.defineProperties(api, {
      owner: { get() { getterCalls++; return 'azhou-codex-startup'; } },
      version: { value: 1 },
      status: { value() {} },
      retryWallpaper: { value() { getterCalls++; } },
    });
    const context = pageContext();
    defineDataGlobal(context, '__azhouStartup', api);
    assert.deepEqual(plain(await evaluate('retrySource', context)), { state: 'owner-conflict', applied: false });
    assert.equal(getterCalls, 0);
  });
});

unitTest('restore removes only the recognized startup or wallpaper owner and reports cleanup state', async t => {
  await t.test('wrong page and absent owner', () => {
    const wrongPage = pageContext({ href: 'app://-/index.html?initialRoute=%2Fnotification' });
    assert.deepEqual(plain(evaluate('restoreSource', wrongPage)), { restored: false, reason: 'wrong-page' });
    assert.deepEqual(plain(evaluate('restoreSource', pageContext())), { restored: true, applied: false });
  });

  await t.test('startup disposal is verified by a subsequent disposed status', () => {
    const context = pageContext();
    let disposed = false;
    const api = startupAPI({
      dispose() { disposed = true; return { disposed: true }; },
      status() { return { phase: disposed ? 'disposed' : 'playing' }; },
    });
    defineDataGlobal(context, '__azhouStartup', api);
    assert.deepEqual(plain(evaluate('restoreSource', context)), { restored: true, applied: false, startup: true });
    assert.equal(disposed, true);
  });

  await t.test('unknown startup owner is left intact', () => {
    let calls = 0;
    const context = pageContext();
    defineDataGlobal(context, '__azhouStartup', startupAPI({ owner: 'foreign', dispose() { calls++; }, status() { calls++; } }));
    assert.deepEqual(plain(evaluate('restoreSource', context)), { restored: false, reason: 'owner-conflict' });
    assert.equal(calls, 0);
  });

  await t.test('wallpaper dispose state and thrown cleanup stay distinct', () => {
    const context = pageContext();
    let applied = true;
    const api = wallpaperAPI({ dispose() { applied = false; }, status() { return { applied }; } });
    defineDataGlobal(context, '__azhouWallpaper', api);
    assert.deepEqual(plain(evaluate('restoreSource', context)), { restored: true, applied: false });

    const failing = pageContext();
    defineDataGlobal(failing, '__azhouWallpaper', wallpaperAPI({ dispose() { throw new Error('native failure'); } }));
    assert.deepEqual(plain(evaluate('restoreSource', failing)), { restored: false, reason: 'restore-failed' });
  });

  await t.test('owner accessors are ignored', () => {
    let calls = 0;
    const api = { version: '0.9.0', status() { calls++; }, dispose() { calls++; } };
    Object.defineProperty(api, 'owner', { get() { calls++; return 'azhou.codex-startup-animation'; } });
    const context = pageContext();
    defineDataGlobal(context, '__azhouWallpaper', api);
    assert.deepEqual(plain(evaluate('restoreSource', context)), { restored: false, reason: 'owner-conflict' });
    assert.equal(calls, 0);
  });
});

unitTest('dispose and install expressions enforce the connector page and return async install results', async t => {
  await t.test('dispose is limited to the expected URL and exact startup owner', () => {
    let receiver;
    let calls = 0;
    const context = pageContext();
    const api = startupAPI({ dispose() { receiver = this; calls++; return { disposed: true }; } });
    defineDataGlobal(context, '__azhouStartup', api);
    assert.deepEqual(plain(evaluate('disposeExpression', context)), { disposed: true });
    assert.equal(receiver, api);
    assert.equal(calls, 1);

    const wrongPage = pageContext({ href: 'app://-/index.html?initialRoute=%2Fmini' });
    defineDataGlobal(wrongPage, '__azhouStartup', api);
    assert.deepEqual(plain(evaluate('disposeExpression', wrongPage)), { disposed: false });
    assert.equal(calls, 1);

    const unknown = pageContext();
    defineDataGlobal(unknown, '__azhouStartup', startupAPI({ owner: 'foreign', dispose() { calls++; } }));
    assert.deepEqual(plain(evaluate('disposeExpression', unknown)), { disposed: false });
    assert.equal(calls, 1);
  });

  await t.test('dispose rejects accessor capabilities without invoking them', () => {
    let calls = 0;
    const api = { owner: 'azhou-codex-startup', version: 1 };
    Object.defineProperty(api, 'dispose', { get() { calls++; return () => calls++; } });
    const context = pageContext();
    defineDataGlobal(context, '__azhouStartup', api);
    assert.deepEqual(plain(evaluate('disposeExpression', context)), { disposed: false });
    assert.equal(calls, 0);
  });

  await t.test('install accepts the concrete supported URL and rejects a changed URL', async () => {
    assert.deepEqual(plain(await evaluate('installExpression', pageContext())), { installed: true });
    const wrongPage = pageContext({ href: 'app://-/index.html?initialRoute=%2Fdetached' });
    assert.deepEqual(plain(await evaluate('installExpression', wrongPage)), {
      installed: false, alreadyActive: false, reason: 'page-unsupported',
    });
  });
});
