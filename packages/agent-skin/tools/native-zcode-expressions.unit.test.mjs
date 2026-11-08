import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { execFileSync } from 'node:child_process';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

// The Swift fixture producer must capture the actual Runtime.evaluate bytes.
// Usage: ZCODE_NATIVE_EXPRESSION_DIR=/absolute/producer-output node --test this-file.mjs
// Producer layout: EXPRESSION-BINDINGS.json and expressions/Native-ZCodeRuntime.<key>.js
// Bindings: {metadata:{controllerInstanceID,createdByOperationID,payloadSHA256,documentToken},
//            sourceSHAs:{safeStatusExpression:<sha256>,disposeExpression:<sha256>}}
const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const nativeAvailable = process.platform === 'darwin';
const keys = ['safeStatusExpression', 'disposeExpression'];
const metadataKeys = ['controllerInstanceID', 'createdByOperationID', 'payloadSHA256', 'documentToken'];
let metadata = {};
const scripts = {};
if (nativeAvailable) {
  const artifactRoot = process.env.ZCODE_NATIVE_EXPRESSION_DIR ?? join(PACKAGE_ROOT, '.build', `native-runtime-expressions-${randomUUID()}`);
  if (!process.env.ZCODE_NATIVE_EXPRESSION_DIR) {
    execFileSync('python3', ['-B', join(PACKAGE_ROOT, 'tools/test-zcode-runtime.py'), '--build-canonical', '--out', artifactRoot],
      { cwd: PACKAGE_ROOT, stdio: 'inherit', timeout: 180000 });
  }
  const bindings = JSON.parse(readFileSync(join(artifactRoot, 'EXPRESSION-BINDINGS.json'), 'utf8'));
  assert.equal(bindings.owner, 'azhou-zcode-startup');
  assert.equal(bindings.version, 1);
  assert.equal(bindings.native_fixture_exit, 0);
  assert.equal(bindings.native_fixture_timed_out, false);
  assert.equal(bindings.canonical_source_bytes_unchanged_after, true);
  assert.equal(bindings.compile_receipt.native_exit, 0);
  for (const name of ['App.swift', 'Wallpaper.swift', 'SkinHostContract.swift', 'CodexSkinDriver.swift', 'ZCodeSkinDriver.swift', 'ZCodeSkinRuntime.swift', 'StartupNativeTests.swift']) {
    const source = join(PACKAGE_ROOT, 'Native', name);
    assert.equal(bindings.canonical_source_sha256[source], createHash('sha256').update(readFileSync(source)).digest('hex'), `${name} canonical source binding`);
  }
  assert.deepEqual(Object.keys(bindings.metadata).sort(), [...metadataKeys].sort());
  metadata = bindings.metadata;
  for (const field of metadataKeys) assert.equal(typeof metadata[field], 'string', field);
  assert.equal(metadata.controllerInstanceID.length, 36);
  assert.equal(metadata.createdByOperationID.length, 36);
  assert.equal(metadata.payloadSHA256.length, 64);
  assert.match(metadata.controllerInstanceID, /^[a-f\d]{8}-[a-f\d]{4}-4[a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i);
  assert.match(metadata.createdByOperationID, /^[a-f\d]{8}-[a-f\d]{4}-4[a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i);
  assert.match(metadata.payloadSHA256, /^[a-f\d]{64}$/);
  assert.ok(metadata.documentToken.length > 0);
  const generatedRoot = resolve(process.env.ZCODE_NATIVE_GENERATED_ROOT ?? join(PACKAGE_ROOT, '.build/unit-generated-sources'));
  mkdirSync(generatedRoot, { recursive: true });
  for (const key of keys) {
    const bytes = readFileSync(join(artifactRoot, 'expressions', `Native-ZCodeRuntime.${key}.js`));
    assert.equal(createHash('sha256').update(bytes).digest('hex'), bindings.sourceSHAs[key], `${key} source binding`);
    const filename = join(generatedRoot, `Native-ZCodeRuntime.${key}.js`);
    writeFileSync(filename, bytes);
    assert.deepEqual(readFileSync(filename), bytes, 'coverage alias retains exact producer bytes');
    scripts[key] = new vm.Script(bytes.toString('utf8'), { filename });
  }
}
const unitTest = (name, callback) => test(name, { skip: !nativeAvailable }, callback);
const plain = value => JSON.parse(JSON.stringify(value));
function state(overrides = {}) {
  return { ready: true, completed: false, runId: 7, phase: 'playing',
    completion: { skipped: false, beforeReady: false }, ...overrides };
}
function controller(overrides = {}) {
  return { owner: 'azhou-zcode-startup', version: 1, ...metadata,
    status() { return state(); }, dispose() { return { disposed: true }; }, ...overrides };
}
function context(api) {
  const result = vm.createContext({});
  if (arguments.length) Object.defineProperty(result, '__azhouStartup', { value: api, configurable: true });
  return result;
}
const run = (key, page) => plain(scripts[key].runInContext(page, { timeout: 1000 }));
const status = api => run('safeStatusExpression', context(api));
const dispose = api => run('disposeExpression', context(api));
function accessor(object, field, result, count) {
  Object.defineProperty(object, field, { configurable: true, get() { count.calls++; return result; } });
}

unitTest('exact status bytes expose only a verified controller and bind status receiver', () => {
  assert.deepEqual(run('safeStatusExpression', context()), { present: false });
  let receiver;
  const api = controller({ status() { receiver = this; return state(); } });
  assert.deepEqual(status(api), { present: true, owner: 'azhou-zcode-startup', version: 1,
    ...metadata, ready: true, completed: false, runId: 7, completion: { skipped: false, beforeReady: false }, phase: 'playing' });
  assert.equal(receiver, api);
  for (const overrides of [{ owner: 'foreign' }, { version: 2 }, { version: '1' }]) {
    let calls = 0;
    assert.deepEqual(status(controller({ ...overrides, status() { calls++; return state(); } })), { present: true, conflict: true });
    assert.equal(calls, 0);
  }
});

unitTest('status exposes the fixed interruption reason only for a failed run', () => {
  const read = (phase, reason) => status(controller({ status: () => state({ phase, reason, ready: false }) }));
  assert.equal(read('failed', 'startup-interrupted').reason, 'startup-interrupted');
  assert.equal(Object.hasOwn(read('failed', 'untrusted page text'), 'reason'), false);
  assert.equal(Object.hasOwn(read('playing', 'startup-interrupted'), 'reason'), false);
});

unitTest('global startup accessor is present and unconfirmed without invoking its getter (regression)', () => {
  const page = context(); const count = { calls: 0 };
  accessor(page, '__azhouStartup', controller(), count);
  const result = run('safeStatusExpression', page);
  assert.equal(count.calls, 0);
  assert.equal(result.present, true, 'accessor existence must not become an absent-controller proof');
  assert.ok(result.unconfirmed === true || result.conflict === true);
});

unitTest('status metadata accepts UUID case but refuses malformed UUID/hash/context before method invocation', () => {
  const upper = controller({ controllerInstanceID: metadata.controllerInstanceID.toUpperCase(),
    createdByOperationID: metadata.createdByOperationID.toUpperCase() });
  assert.equal(status(upper).ready, true);
  const invalid = [
    ['controllerInstanceID', 1], ['controllerInstanceID', metadata.controllerInstanceID + '\n'],
    ['controllerInstanceID', '00000000-0000-0000-0000-000000000000'],
    ['createdByOperationID', 1], ['createdByOperationID', metadata.createdByOperationID + '\n'],
    ['createdByOperationID', '00000000-0000-0000-0000-000000000000'],
    ['payloadSHA256', 1], ['payloadSHA256', metadata.payloadSHA256 + '\n'],
    ['payloadSHA256', 'g'.repeat(64)], ['payloadSHA256', 'A'.repeat(64)], ['documentToken', 1], ['documentToken', metadata.documentToken + '-foreign'],
  ];
  for (const [field, value] of invalid) {
    let calls = 0;
    assert.deepEqual(status(controller({ [field]: value, status() { calls++; return state(); } })),
      { present: true, unconfirmed: true }, field);
    assert.equal(calls, 0, field);
  }
});

unitTest('status accessors and non-callable methods are refused without invoking getters', () => {
  for (const field of ['owner', 'version', ...metadataKeys, 'status']) {
    const api = controller(); const count = { calls: 0 };
    accessor(api, field, field === 'status' ? () => state() : api[field], count);
    const result = status(api);
    assert.equal(count.calls, 0, field);
    assert.equal(result.present, true);
    assert.ok(result.conflict === true || result.unconfirmed === true, field);
  }
  for (const method of [null, {}, true]) assert.deepEqual(status(controller({ status: method })), { present: true, unconfirmed: true });
  assert.throws(() => status(controller({ status() { throw new Error('fixture status refusal'); } })), /fixture status refusal/);
});

unitTest('status result getters are ignored and unknown or unsafe values cannot claim ready completion', () => {
  const count = { calls: 0 }; const result = {};
  for (const field of ['ready', 'completed', 'runId', 'completion', 'phase']) accessor(result, field, true, count);
  const observed = status(controller({ status() { return result; } }));
  assert.equal(count.calls, 0);
  assert.deepEqual({ ready: observed.ready, completed: observed.completed, runId: observed.runId,
    completion: observed.completion, phase: observed.phase }, {
    ready: false, completed: false, runId: null, completion: { skipped: false, beforeReady: false }, phase: 'unconfirmed' });
  for (const phase of ['loading', 'playing', 'complete', 'settings', 'disposed', 'failed']) {
    assert.equal(status(controller({ status: () => state({ phase }) })).phase, phase);
  }
  const complete = status(controller({ status: () => state({ phase: 'complete', completed: true, runId: 8,
    completion: { skipped: true, beforeReady: true } }) }));
  assert.equal(complete.completed, true); assert.equal(complete.runId, 8);
  assert.deepEqual(complete.completion, { skipped: true, beforeReady: true });
  const unknown = status(controller({ status: () => state({ phase: 'private-phase', ready: 1, completed: 'yes', runId: 1.5,
    completion: { skipped: 1, beforeReady: 'yes' } }) }));
  assert.equal(unknown.phase, 'unconfirmed'); assert.equal(unknown.ready, false); assert.equal(unknown.completed, false);
  assert.equal(unknown.runId, null); assert.deepEqual(unknown.completion, { skipped: false, beforeReady: false });
  const completion = {}; const completionCount = { calls: 0 };
  accessor(completion, 'skipped', true, completionCount); accessor(completion, 'beforeReady', true, completionCount);
  assert.deepEqual(status(controller({ status: () => state({ completion }) })).completion, { skipped: false, beforeReady: false });
  assert.equal(completionCount.calls, 0);
});

unitTest('disposal requires exact receipt fields and binds the method receiver', () => {
  assert.deepEqual(run('disposeExpression', context()), { disposed: true, alreadyAbsent: true });
  let receiver; let calls = 0;
  const api = controller({ dispose() { receiver = this; calls++; return { disposed: true }; } });
  assert.deepEqual(dispose(api), { disposed: true }); assert.equal(receiver, api); assert.equal(calls, 1);
  for (const overrides of [{ owner: 'foreign' }, { version: 2 }, ...metadataKeys.map(field => ({ [field]: metadata[field] + '-foreign' }))]) {
    calls = 0;
    assert.deepEqual(dispose(controller({ ...overrides, dispose() { calls++; return { disposed: true }; } })), { disposed: false });
    assert.equal(calls, 0);
  }
  assert.deepEqual(dispose(controller({ createdByOperationID: metadata.createdByOperationID.toLowerCase() })), { disposed: true });
  assert.deepEqual(dispose(controller({ createdByOperationID: metadata.createdByOperationID.toUpperCase() })), { disposed: true });
  assert.deepEqual(dispose(controller({ createdByOperationID: 1 })), { disposed: false });
});

unitTest('global startup accessor cannot prove already-absent cleanup (regression)', () => {
  const page = context(); const count = { calls: 0 };
  accessor(page, '__azhouStartup', controller(), count);
  const result = run('disposeExpression', page);
  assert.equal(count.calls, 0);
  assert.equal(result.disposed, false, 'an unread accessor is not confirmed absent cleanup');
  assert.notEqual(result.alreadyAbsent, true);
});

unitTest('disposal ignores accessors, refuses non-methods and refuses non-boolean or throwing results', () => {
  for (const field of ['owner', 'version', ...metadataKeys, 'dispose']) {
    const api = controller(); const count = { calls: 0 };
    accessor(api, field, field === 'dispose' ? () => ({ disposed: true }) : api[field], count);
    assert.deepEqual(dispose(api), { disposed: false }, field); assert.equal(count.calls, 0, field);
  }
  for (const method of [null, {}, true]) assert.deepEqual(dispose(controller({ dispose: method })), { disposed: false });
  for (const result of [{}, { disposed: false }, { disposed: 1 }, { disposed: 'true' }, null]) {
    assert.deepEqual(dispose(controller({ dispose: () => result })), { disposed: false });
  }
  const result = {}; const count = { calls: 0 }; accessor(result, 'disposed', true, count);
  assert.deepEqual(dispose(controller({ dispose: () => result })), { disposed: false }); assert.equal(count.calls, 0);
  assert.throws(() => dispose(controller({ dispose() { throw new Error('fixture disposal refusal'); } })), /fixture disposal refusal/);
});
