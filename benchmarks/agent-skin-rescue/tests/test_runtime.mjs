import assert from 'node:assert/strict';
import test from 'node:test';
import { validateRequest, exerciseFixture, runRequest } from '../runtime/offline.mjs';

test('host authority and missing fixture scope are refused before resource access', () => {
  for (const scope of ['host', 'offline-only', undefined]) {
    assert.throws(() => validateRequest({ schema: 'offline-runtime-request.v1', scope }), /fixture-only/);
  }
});

import { createR10Diagnostics } from '../rebind/r10-diagnostics.mjs';
const owner = '11111111-1111-4111-8111-111111111111';
const config = { owner, token: owner, id: 'agent-skin-zcode-probe-' + owner,
  action: 'mount', timeOrigin: 456.75, generationSHA256: 'a'.repeat(64) };
function fixtureWrappers() {
  const configurations = {
    mount: config,
    clean: { ...config, action: 'clean' },
    foreign: { ...config, action: 'clean', token: '22222222-2222-4222-8222-222222222222' },
    stale: { ...config, timeOrigin: 457.75 },
  };
  return Object.fromEntries(Object.entries(configurations).map(([key, value]) => [key, {
    config: value,
    source: '(() => { const d = (' + createR10Diagnostics.toString() + ')(' + JSON.stringify(value)
      + '); return d.inspect(globalThis).matched ? { installed: false, reason: "probe-only", '
      + 'assemblyObservation: d.run(globalThis) } : { installed:false, reason:"probe-target-mismatch" }; })()',
  }]));
}

test('one fixture context mounts, reads back, refuses foreign/stale and cleans the owned marker', () => {
  const result = exerciseFixture(fixtureWrappers());
  assert.equal(result.status, 'passed');
  assert.equal(result.contextCount, 1);
  assert.equal(result.mount.readback, owner);
  assert.equal(result.cleanup, 'known');
  assert.equal(result.remainingOwnedNodes, 0);
  assert.deepEqual(result.operations, ['append', 'remove']);
  assert.equal(result.hostValidation, 'not_run');
});


test('fixture cleanup errors remain unknown and cannot become success', () => {
  const result = exerciseFixture(fixtureWrappers(), { removeFailure: true });
  assert.equal(result.status, 'failed');
  assert.equal(result.cleanup, 'unknown');
  assert.equal(result.remainingOwnedNodes, 1);
});

test('an actual fixture generation change invalidates the old cleanup wrapper', () => {
  const result = exerciseFixture(fixtureWrappers(), { navigateAfterMount: true });
  assert.equal(result.status, 'failed');
  assert.equal(result.cleanup, 'unknown');
  assert.equal(result.remainingOwnedNodes, 1);
});

test('resource paths and hashes must be explicit and relative to the evidence root', () => {
  const valid = { schema: 'offline-runtime-request.v1', scope: 'fixture-only', root: '/synthetic/evidence',
    binding: { path: 'build/binding.json', sha256: 'a'.repeat(64) },
    producer: { path: 'producer/command.json', sha256: 'b'.repeat(64) } };
  assert.equal(validateRequest(valid), valid);
  for (const descriptor of [{ path: '', sha256: 'a'.repeat(64) },
    { path: '../escape', sha256: 'a'.repeat(64) }, { path: '/outside', sha256: 'a'.repeat(64) },
    { path: 'binding.json', sha256: 'invalid' }]) {
    assert.throws(() => validateRequest({ ...valid, binding: descriptor }), /bound binding/);
  }
});


import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
const worktree = fileURLToPath(new URL('../../../', import.meta.url));
function resourceCase() {
  const root = fs.mkdtempSync(path.join(worktree, '.scratch/runtime-boundary-'));
  fs.chmodSync(root, 0o700);
  const binding = Buffer.from('{"synthetic":"binding"}\n');
  const producer = Buffer.from('{"synthetic":"producer"}\n');
  fs.writeFileSync(path.join(root, 'binding.json'), binding, { flag: 'wx', mode: 0o600 });
  fs.writeFileSync(path.join(root, 'producer.json'), producer, { flag: 'wx', mode: 0o600 });
  const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
  return { root, request: { schema: 'offline-runtime-request.v1', scope: 'fixture-only', root,
    binding: { path: 'binding.json', sha256: sha(binding) },
    producer: { path: 'producer.json', sha256: sha(producer) } } };
}

test('fresh-output ownership never overwrites an existing result directory', () => {
  const { root, request } = resourceCase();
  const out = path.join(root, 'existing');
  fs.mkdirSync(out, { mode: 0o700 });
  fs.writeFileSync(path.join(out, 'result.json'), 'retained');
  assert.throws(() => runRequest(request, out), /EEXIST/);
  assert.equal(fs.readFileSync(path.join(out, 'result.json'), 'utf8'), 'retained');
});

test('changed binding bytes are refused before launching the checker or VM', () => {
  const { root, request } = resourceCase();
  fs.appendFileSync(path.join(root, 'binding.json'), 'changed');
  const out = path.join(root, 'tampered');
  const result = runRequest(request, out);
  assert.equal(result.status, 'refused');
  assert.equal(result.inputsUnchanged, false);
  assert.equal(result.contextCount, undefined);
  assert.equal(fs.existsSync(path.join(out, 'checker-command.json')), false);
  assert.match(result.error.message, /digest mismatch/);
});

test('a symbolic binding path and a non-private evidence root are refused', () => {
  const { root, request } = resourceCase();
  fs.symlinkSync('binding.json', path.join(root, 'linked.json'));
  const result = runRequest({ ...request, binding: { ...request.binding, path: 'linked.json' } },
    path.join(root, 'linked'));
  assert.equal(result.status, 'refused');
  assert.equal(result.contextCount, undefined);
  fs.chmodSync(root, 0o755);
  assert.throws(() => runRequest(request, path.join(root, 'not-private')), /private and owned/);
});


import { checkerReceipt } from '../runtime/offline.mjs';
import { spawnSync } from 'node:child_process';
function validateWithOriginalOracle(receipt) {
  const source = fileURLToPath(new URL('../', import.meta.url));
  const checked = spawnSync('python3', ['-B', '-c',
    'import json,sys;sys.path.insert(0,sys.argv[1]);from offline_runtime import validate_result;validate_result(json.load(sys.stdin))',
    source], { input: JSON.stringify(receipt), encoding: 'utf8', timeout: 5000 });
  assert.equal(checked.status, 0, checked.stderr);
}
const receiptMetadata = {
  command_id: 'fixture-checker-wait-model', argv: ['fixture-checker', '--synthetic-only'],
  cwd: '/synthetic/evidence', started_at: '2026-11-01T00:00:00.000Z',
  observed_at: '2026-11-01T00:00:01.000Z', inputs: [], argument_inputs: [],
  inputs_unchanged: true, argument_inputs_unchanged: true, raw_files: [],
};

test('modeled actual exit and known signal retain original C contract and Python wait semantics', () => {
  const exited = checkerReceipt({ pid: 123, status: 0, signal: null }, receiptMetadata);
  validateWithOriginalOracle(exited);
  assert.equal(exited.kind, 'C');
  assert.equal(exited.execution_state, 'exited');
  assert.equal(exited.exit_code, 0);
  assert.equal(exited.signal, null);
  assert.equal(exited.successful, true);
  const signaled = checkerReceipt({ pid: 123, status: null, signal: 'SIGTERM' }, receiptMetadata);
  validateWithOriginalOracle(signaled);
  assert.equal(signaled.kind, 'C');
  assert.equal(signaled.execution_state, 'signaled');
  assert.equal(signaled.exit_code, -15);
  assert.equal(signaled.signal, 15);
  assert.equal(signaled.successful, false);
  const timedOut = checkerReceipt({ pid: 123, status: null, signal: 'SIGTERM',
    error: { name: 'Error', code: 'ETIMEDOUT' } }, receiptMetadata);
  validateWithOriginalOracle(timedOut);
  assert.equal(timedOut.execution_state, 'timed_out');
  assert.equal(timedOut.exit_code, -15);
  assert.equal(timedOut.signal, 15);
});

test('spawn failure, absent wait and unknown signal cannot produce a C receipt', () => {
  for (const [waited, state] of [
    [{ pid: 0, status: null, signal: null, error: { name: 'Error', code: 'ENOENT' } }, 'not_started'],
    [{ pid: 123, status: null, signal: null }, 'exit_unknown'],
    [{ pid: 123, status: null, signal: 'UNRECOGNIZED_FIXTURE_SIGNAL' }, 'exit_unknown'],
    [{ pid: 123, status: null, signal: null, error: { code: 'ETIMEDOUT' } }, 'exit_unknown'],
  ]) {
    const receipt = checkerReceipt(waited, receiptMetadata);
    validateWithOriginalOracle(receipt);
    assert.equal(receipt.kind, 'E');
    assert.equal(receipt.execution_state, state);
    assert.equal(receipt.exit_code, null);
    assert.equal(receipt.signal, null);
    assert.equal(receipt.wait_observed, false);
    assert.equal(receipt.successful, false);
  }
});


function checkerPostcheckCase(mode) {
  const root = fs.mkdtempSync(path.join(worktree, '.scratch/runtime-postcheck-' + mode + '-'));
  fs.chmodSync(root, 0o700);
  const runtime = path.join(root, 'code/runtime/offline.mjs');
  const checker = path.join(root, 'code/rebind/check_binding.py');
  fs.mkdirSync(path.dirname(runtime), { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.dirname(checker), { recursive: true, mode: 0o700 });
  fs.copyFileSync(fileURLToPath(new URL('../runtime/offline.mjs', import.meta.url)), runtime);
  fs.chmodSync(runtime, 0o600);
  const script = 'from pathlib import Path\nimport os,sys\np=Path(__file__)\n'
    + (mode === 'delete' ? 'p.unlink()\n' :
      'target=p.parent.parent.parent/"outside-fixed-checker.py"\ntarget.write_bytes(p.read_bytes())\np.unlink()\np.symlink_to(target)\n')
    + 'sys.stdout.buffer.write(b"synthetic-checker-finished\\n")\n'
    + 'sys.stderr.buffer.write(b"synthetic-binary\\x00\\xff")\n';
  fs.writeFileSync(checker, script, { flag: 'wx', mode: 0o600 });
  const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
  const descriptor = name => {
    const bytes = Buffer.from('{"scope":"synthetic-input"}\n');
    fs.writeFileSync(path.join(root, name), bytes, { flag: 'wx', mode: 0o600 });
    return { path: name, sha256: hash(bytes) };
  };
  const request = { schema: 'offline-runtime-request.v1', scope: 'fixture-only', root,
    binding: descriptor('binding.json'), producer: descriptor('producer.json') };
  const requestPath = path.join(root, 'request.json'), out = path.join(root, 'out');
  fs.writeFileSync(requestPath, JSON.stringify(request), { flag: 'wx', mode: 0o600 });
  const argv = [process.execPath, runtime, '--request', requestPath, '--out', out];
  const startedAt = new Date().toISOString();
  const cli = spawnSync(argv[0], argv.slice(1), { encoding: null, timeout: 5000 });
  const finishedAt = new Date().toISOString();
  fs.writeFileSync(path.join(root, 'cli-stdout.raw'), cli.stdout || Buffer.alloc(0), { flag: 'wx', mode: 0o600 });
  fs.writeFileSync(path.join(root, 'cli-stderr.raw'), cli.stderr || Buffer.alloc(0), { flag: 'wx', mode: 0o600 });
  fs.writeFileSync(path.join(root, 'cli-observation.json'), JSON.stringify({
    scope: 'controlled public CLI postcheck fault', argv, started_at: startedAt, observed_at: finishedAt,
    actual_node_status: cli.status, actual_node_signal: cli.signal, error: cli.error?.code ?? null,
    runtime_sha256: hash(fs.readFileSync(runtime)), checker_before_sha256: hash(Buffer.from(script)),
    raw_sha256: { stdout: hash(cli.stdout || Buffer.alloc(0)), stderr: hash(cli.stderr || Buffer.alloc(0)) },
  }, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  assert.equal(cli.status, 1, (cli.stderr || '').toString());
  assert.equal(cli.signal, null);
  const receipt = JSON.parse(fs.readFileSync(path.join(out, 'checker-command.json'), 'utf8'));
  validateWithOriginalOracle(receipt);
  assert.equal(receipt.kind, 'C');
  assert.equal(receipt.exit_code, 0);
  assert.equal(receipt.signal, null);
  assert.equal(receipt.wait_observed, true);
  assert.equal(receipt.inputs_unchanged, false);
  assert.equal(receipt.successful, false);
  assert.ok(receipt.evidence_errors.some(error => error.phase === 'checker-postcheck'
    && error.code === (mode === 'delete' ? 'ENOENT' : 'ELOOP')));
  const result = JSON.parse(fs.readFileSync(path.join(out, 'result.json'), 'utf8'));
  assert.equal(result.status, 'refused');
  assert.equal(result.contextCount ?? 0, 0);
  assert.equal(result.operations?.length ?? 0, 0);
  assert.ok(result.evidence_errors.length);
  for (const item of receipt.outputs.raw_files) {
    assert.equal(path.isAbsolute(item.path), false);
    assert.equal(hash(fs.readFileSync(path.join(root, item.path))), item.sha256);
  }
  assert.deepEqual(fs.readFileSync(path.join(out, 'checker-stderr.raw')), Buffer.from('synthetic-binary\0\xff', 'latin1'));
}

test('a checker deleting its own fixed file preserves its observed C and refuses VM', () => {
  checkerPostcheckCase('delete');
});

test('a checker replacing its fixed file with an external symlink preserves C without following it', () => {
  checkerPostcheckCase('symlink');
});
