import path from 'node:path';
import vm from 'node:vm';
import fs from 'node:fs';
import crypto from 'node:crypto';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HASH = /^[0-9a-f]{64}$/;
export function validateRequest(request) {
  if (!request || request.scope !== 'fixture-only') throw new Error('fixture-only scope required');
  if (request.schema !== 'offline-runtime-request.v1') throw new Error('request schema mismatch');
  if (typeof request.root !== 'string' || !path.isAbsolute(request.root)
      || request.root.split(path.sep).includes('..') || path.resolve(request.root) === path.parse(request.root).root)
    throw new Error('absolute private evidence root required');
  for (const key of ['binding', 'producer']) {
    const descriptor = request[key];
    if (!descriptor || Object.keys(descriptor).sort().join(',') !== 'path,sha256'
        || typeof descriptor.path !== 'string' || !descriptor.path || path.isAbsolute(descriptor.path)
        || descriptor.path.split(/[\\/]/).includes('..') || !HASH.test(descriptor.sha256))
      throw new Error('bound ' + key + ' descriptor required');
  }
  return request;
}

export function exerciseFixture(wrappers, faults = {}) {
  const styles = new Map(), operations = [], checks = [];
  let contextCount = 0;
  const config = wrappers.mount.config;
  const document = {
    documentElement: {},
    head: { appendChild(node) {
      if (styles.has(node.id)) throw new Error('fixture duplicate marker');
      styles.set(node.id, node); operations.push('append');
    } },
    getElementById(id) { return styles.get(id) || null; },
    querySelectorAll(selector) { return styles.has(selector.slice(1)) ? [styles.get(selector.slice(1))] : []; },
    createElement(kind) {
      if (kind !== 'style') throw new Error('fixture only supports diagnostic styles');
      return { dataset: {}, remove() {
        if (faults.removeFailure) throw new Error('synthetic remove failure');
        if (styles.get(this.id) !== this) throw new Error('fixture marker identity changed');
        styles.delete(this.id); operations.push('remove');
      } };
    },
  };
  const sandbox = {
    URL, document, performance: { timeOrigin: config.timeOrigin },
    location: { href: 'file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html' },
    getComputedStyle() { return { getPropertyValue(name) {
      if (name !== '--agent-skin-zcode-probe') throw new Error('unsupported fixture readback');
      const value = [...styles.values()][0]?.textContent || '';
      return /--agent-skin-zcode-probe:([^;}]+)/.exec(value)?.[1] || '';
    } }; },
  };
  sandbox.top = sandbox;
  const context = vm.createContext(sandbox); contextCount += 1;
  const evaluate = name => {
    if (!wrappers[name] || typeof wrappers[name].source !== 'string'
        || Buffer.byteLength(wrappers[name].source) > 24 * 1024 * 1024) throw new Error('missing or oversized wrapper');
    return new vm.Script(wrappers[name].source, { filename: name + '-fixture.js' })
      .runInContext(context, { timeout: 3000 });
  };
  const observation = result => {
    if (!result || result.installed !== false || result.reason !== 'probe-only')
      throw new Error('fixture wrapper admission refused');
    return JSON.parse(JSON.stringify(result.assemblyObservation));
  };
  const expect = (name, condition) => {
    checks.push({ name, passed: Boolean(condition) });
    if (!condition) throw new Error('fixture check failed: ' + name);
  };
  const result = { schema: 'offline-runtime-fixture.v1', scope: 'fixture-only',
    hostValidation: 'not_run', contextCount, checks, operations, cleanup: 'unknown', status: 'failed' };
  try {
    result.mount = observation(evaluate('mount'));
    expect('mount-readback', result.mount.state === 'mounted' && result.mount.count === 1
      && result.mount.readback === config.token && styles.size === 1);
    expect('same-context-repeat', observation(evaluate('mount')).state === 'reused' && operations.length === 1);
    expect('foreign-owner-refused', observation(evaluate('foreign')).state === 'ownership-mismatch'
      && styles.size === 1 && operations.length === 1);
    const stale = evaluate('stale');
    expect('stale-generation-refused', (stale.reason === 'probe-target-mismatch'
      || stale.assemblyObservation?.state === 'document-generation-mismatch')
      && styles.size === 1 && operations.length === 1);
    if (faults.navigateAfterMount) sandbox.performance.timeOrigin += 1;
    result.clean = observation(evaluate('clean'));
    expect('owned-cleanup', result.clean.state === 'disposed' && result.clean.count === 0 && styles.size === 0);
    expect('double-cleanup', observation(evaluate('clean')).state === 'already-disposed'
      && operations.join(',') === 'append,remove');
    result.cleanup = 'known';
    result.status = 'passed';
  } catch (error) {
    result.error = { type: error.name, message: String(error.message).slice(0, 240) };
    if (styles.size) {
      try {
        result.cleanupAttempt = observation(evaluate('clean'));
        if (result.cleanupAttempt.state === 'disposed' && styles.size === 0) result.cleanup = 'known';
      } catch (cleanupError) {
        result.cleanupError = { type: cleanupError.name };
      }
    } else result.cleanup = 'known';
  }
  result.remainingOwnedNodes = styles.size;
  return result;
}

const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

export function checkerReceipt(waited, metadata) {
  const rawSignal = waited.signal ?? null;
  const signalNumber = typeof rawSignal === 'string' ? os.constants.signals[rawSignal] : null;
  let code = null;
  if (Number.isInteger(waited.status) && waited.status >= 0 && rawSignal === null) code = waited.status;
  else if (waited.status == null && Number.isInteger(signalNumber) && signalNumber > 0) code = -signalNumber;
  const timedOut = waited.error?.code === 'ETIMEDOUT';
  const notStarted = code === null && !waited.pid && waited.error && !timedOut && rawSignal === null;
  const state = code === null ? (notStarted ? 'not_started' : 'exit_unknown')
    : timedOut ? 'timed_out' : code < 0 ? 'signaled' : 'exited';
  const error = waited.error ? { type: waited.error.name || 'Error', code: waited.error.code ?? null } : null;
  const receipt = {
    kind: code === null ? 'E' : 'C', command_id: metadata.command_id,
    started_at: metadata.started_at, observed_at: metadata.observed_at,
    argv: [...metadata.argv], cwd: metadata.cwd, execution_state: state,
    exit_code: code, signal: code !== null && code < 0 ? -code : null,
    wait_observed: code !== null, error,
    raw_wait: { pid: waited.pid ?? null, status: waited.status ?? null, signal: rawSignal },
    inputs: metadata.inputs, argument_inputs: metadata.argument_inputs,
    evidence_errors: [...(metadata.evidence_errors || [])],
    inputs_unchanged: metadata.inputs_unchanged,
    argument_inputs_unchanged: metadata.argument_inputs_unchanged,
    outputs: { mode: 'separate', raw_files: metadata.raw_files },
    scope: 'offline fixture checker; not host evidence',
  };
  receipt.successful = state === 'exited' && code === 0 && error === null
    && receipt.inputs_unchanged === true && receipt.argument_inputs_unchanged === true;
  return receipt;
}

const identity = info => ['dev', 'ino', 'uid', 'mode', 'size', 'mtimeNs', 'ctimeNs', 'nlink']
  .map(key => String(info[key])).join(':');
const directoryIdentity = info => ['dev', 'ino', 'uid', 'mode'].map(key => String(info[key])).join(':');


function readFixedChecker(checker) {
  const parent = path.dirname(checker);
  if (fs.realpathSync(parent) !== parent) throw new Error('checker parent is not canonical');
  const fd = fs.openSync(checker, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const before = fs.fstatSync(fd, { bigint: true });
    if (!before.isFile() || Number(before.uid) !== process.getuid() || Number(before.nlink) !== 1
        || (Number(before.mode) & 0o022) || before.size > BigInt(1024 * 1024))
      throw new Error('fixed checker identity or permissions refused');
    const bytes = fs.readFileSync(fd);
    if (identity(before) !== identity(fs.fstatSync(fd, { bigint: true }))
        || identity(before) !== identity(fs.lstatSync(checker, { bigint: true })))
      throw new Error('fixed checker changed during descriptor read');
    return { bytes, identity: identity(before) };
  } finally { fs.closeSync(fd); }
}

function resourceReader(root) {
  const initial = fs.lstatSync(root, { bigint: true });
  if (!initial.isDirectory() || fs.realpathSync(root) !== root
      || Number(initial.uid) !== process.getuid() || (Number(initial.mode) & 0o777) !== 0o700)
    throw new Error('resource evidence root is not private and owned');
  const rootIdentity = directoryIdentity(initial);
  const observed = new Map();
  const inside = name => {
    const relative = path.relative(root, name);
    return relative && relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative);
  };
  function read(descriptor) {
    if (!descriptor || typeof descriptor.path !== 'string' || !descriptor.path
        || path.isAbsolute(descriptor.path) || descriptor.path.split(/[\\/]/).includes('..'))
      throw new Error('unsafe resource descriptor');
    const name = path.join(root, descriptor.path);
    if (!inside(name) || fs.realpathSync(name) !== name
        || directoryIdentity(fs.lstatSync(root, { bigint: true })) !== rootIdentity)
      throw new Error('resource path or root identity changed');
    const fd = fs.openSync(name, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    let bytes;
    try {
      const before = fs.fstatSync(fd, { bigint: true });
      if (!before.isFile() || Number(before.uid) !== process.getuid()
          || Number(before.nlink) !== 1 || (Number(before.mode) & 0o022)
          || before.size > BigInt(24 * 1024 * 1024)) throw new Error('resource file identity or size refused');
      bytes = fs.readFileSync(fd);
      if (identity(before) !== identity(fs.fstatSync(fd, { bigint: true }))
          || identity(before) !== identity(fs.lstatSync(name, { bigint: true })))
        throw new Error('resource bytes changed while reading');
    } finally { fs.closeSync(fd); }
    const sha256 = digest(bytes);
    if ((descriptor.sha256 && sha256 !== descriptor.sha256)
        || (observed.has(descriptor.path) && observed.get(descriptor.path) !== sha256))
      throw new Error('resource digest mismatch');
    observed.set(descriptor.path, sha256);
    return bytes;
  }
  function recheck() {
    for (const [name, sha256] of [...observed]) read({ path: name, sha256 });
  }
  return { read, recheck, observed, inside };
}

export function runRequest(request, outputPath, requestFile = null) {
  validateRequest(request);
  const reader = resourceReader(request.root);
  if (typeof outputPath !== 'string' || path.resolve(outputPath) !== outputPath
      || !reader.inside(outputPath) || fs.realpathSync(path.dirname(outputPath)) !== path.dirname(outputPath))
    throw new Error('output must be a fresh directory inside the evidence root');
  fs.mkdirSync(outputPath, { mode: 0o700 });
  const outputIdentity = directoryIdentity(fs.lstatSync(outputPath, { bigint: true }));
  const artifact = (name, bytes) => {
    if (directoryIdentity(fs.lstatSync(outputPath, { bigint: true })) !== outputIdentity)
      throw new Error('output directory identity changed');
    const fd = fs.openSync(path.join(outputPath, name), 'wx', 0o600);
    try { fs.writeFileSync(fd, bytes); } finally { fs.closeSync(fd); }
    return { path: path.relative(request.root, path.join(outputPath, name)), sha256: digest(bytes), bytes: bytes.length };
  };
  const jsonArtifact = (name, value) => artifact(name, Buffer.from(JSON.stringify(value, null, 2) + '\n'));
  let sequence = 0;
  const runtimeCommandId = crypto.randomUUID(), checkerCommandId = crypto.randomUUID();
  const event = (name, details = {}, command = { command_id: runtimeCommandId, argv: process.argv }) =>
    jsonArtifact('event-' + String(sequence++).padStart(2, '0') + '.json',
      { kind: 'E', observed_at: new Date().toISOString(), command_id: command.command_id,
        argv: [...command.argv], exit_code: null, event: name,
        checker_command_id: checkerCommandId, ...details });
  const result = { schema: 'offline-runtime-result.v1', kind: 'A', scope: 'fixture-only',
    hostValidation: 'not_run', status: 'refused', cleanup: 'unknown', inputsUnchanged: false };
  event('started');
  try {
    if (requestFile) reader.read(requestFile);
    reader.read(request.binding);
    reader.read(request.producer);
    const checker = fileURLToPath(new URL('../rebind/check_binding.py', import.meta.url));
    const checkerSnapshot = readFixedChecker(checker);
    const checkerBefore = digest(checkerSnapshot.bytes);
    const argv = ['python3', '-B', checker, '--root', request.root,
      '--binding', request.binding.path, '--producer', request.producer.path];
    const startedAt = new Date().toISOString();
    event('checker-started', {}, { command_id: checkerCommandId, argv });
    const checked = spawnSync(argv[0], argv.slice(1),
      { cwd: request.root, encoding: null, timeout: 10000, maxBuffer: 8 * 1024 * 1024 });
    const finishedAt = new Date().toISOString();
    const raw = [artifact('checker-stdout.raw', checked.stdout || Buffer.alloc(0)),
      artifact('checker-stderr.raw', checked.stderr || Buffer.alloc(0))];
    const evidenceErrors = [];
    const evidenceError = (phase, error) => evidenceErrors.push({
      phase, type: error.name || 'Error', code: error.code ?? null,
      message: String(error.message).slice(0, 240),
    });
    let checkerUnchanged = false;
    try {
      const after = readFixedChecker(checker);
      checkerUnchanged = digest(after.bytes) === checkerBefore && after.identity === checkerSnapshot.identity;
      if (!checkerUnchanged) evidenceError('checker-postcheck',
        Object.assign(new Error('checker fingerprint changed after observed wait'), { code: 'CHECKER_CHANGED' }));
    } catch (error) { evidenceError('checker-postcheck', error); }
    let argumentInputsUnchanged = true;
    try { reader.read(request.binding); reader.read(request.producer); }
    catch (error) { argumentInputsUnchanged = false; evidenceError('argument-inputs-postcheck', error); }
    result.evidence_errors = evidenceErrors;
    const receipt = checkerReceipt(checked, {
      command_id: checkerCommandId, argv, cwd: request.root,
      started_at: startedAt, observed_at: finishedAt,
      inputs: [{ path: checker, sha256: checkerBefore, identity: checkerSnapshot.identity }],
      argument_inputs: [request.binding, request.producer],
      inputs_unchanged: checkerUnchanged, argument_inputs_unchanged: argumentInputsUnchanged,
      raw_files: raw, evidence_errors: evidenceErrors,
    });
    result.checkerCommand = jsonArtifact('checker-command.json', receipt);
    if (!receipt.successful) throw new Error('resource checker did not complete successfully');
    const proof = JSON.parse(checked.stdout.toString('utf8'));
    if (proof.kind !== 'A' || proof.status !== 'verified-resources-only'
        || proof.host_validation !== 'not_run' || proof.binding_sha256 !== request.binding.sha256
        || proof.producer_receipt_sha256 !== request.producer.sha256)
      throw new Error('resource proof is not bound to the requested producer bytes');
    reader.read(proof.base_payload);
    reader.read(proof.startup_manifest);
    const wrappers = {};
    for (const key of ['mount', 'clean', 'foreign', 'stale']) {
      const descriptor = proof.wrappers?.[key];
      if (!descriptor || !descriptor.config) throw new Error('missing bound fixture wrapper');
      wrappers[key] = { config: descriptor.config, source: reader.read(descriptor).toString('utf8') };
    }
    event('resources-verified', { bindingSHA256: proof.binding_sha256 });
    const exercise = exerciseFixture(wrappers);
    reader.recheck();
    try {
      const after = readFixedChecker(checker);
      if (digest(after.bytes) !== checkerBefore || after.identity !== checkerSnapshot.identity)
        throw new Error('checker changed during fixture exercise');
    } catch (error) { evidenceError('checker-final-postcheck', error); throw error; }
    Object.assign(result, exercise, { schema: 'offline-runtime-result.v1', kind: 'A',
      inputsUnchanged: true, resourceProof: { bindingSHA256: proof.binding_sha256,
        producerSHA256: proof.producer_receipt_sha256, sourceCommit: proof.source_commit,
        commandCount: proof.command_count } });
  } catch (error) {
    result.error = { type: error.name, message: String(error.message).slice(0, 240) };
  }
  result.inputs = [...reader.observed].map(([name, sha256]) => ({ path: name, sha256 }));
  event('analysis-finished', { status: result.status, cleanup: result.cleanup });
  jsonArtifact('result.json', result);
  return result;
}

function main(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    if (!['--request', '--out'].includes(argv[index]) || !argv[index + 1] || options[argv[index]])
      throw new Error('usage: offline.mjs --request JSON --out NEW_DIRECTORY');
    options[argv[index]] = argv[index + 1];
  }
  if (!options['--request'] || !options['--out']) throw new Error('request and output paths required');
  const requestBytes = fs.readFileSync(options['--request']);
  if (requestBytes.length > 1024 * 1024) throw new Error('request exceeds bound');
  const request = JSON.parse(requestBytes.toString('utf8'));
  validateRequest(request);
  const requestPath = path.relative(request.root, path.resolve(options['--request']));
  const result = runRequest(request, path.resolve(options['--out']), { path: requestPath, sha256: digest(requestBytes) });
  process.stdout.write(JSON.stringify({ schema: result.schema, scope: result.scope, status: result.status,
    cleanup: result.cleanup, contextCount: result.contextCount ?? 0, hostValidation: 'not_run' }) + '\n');
  return result.status === 'passed' && result.cleanup === 'known' && result.inputsUnchanged ? 0 : 1;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { process.exitCode = main(process.argv.slice(2)); }
  catch (error) {
    process.stderr.write(JSON.stringify({ status: 'refused', error: error.name, message: String(error.message).slice(0, 240),
      scope: 'fixture-only', hostValidation: 'not_run' }) + '\n');
    process.exitCode = 2;
  }
}
