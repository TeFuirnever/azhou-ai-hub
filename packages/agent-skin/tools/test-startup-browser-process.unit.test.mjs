import assert from 'node:assert/strict';
import { EventEmitter, once } from 'node:events';
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, readFile, rename, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { canRemoveProfile, profileIdentity, removeOwnedProfile, trackOwnedChild } from './test-startup-browser-process.mjs';

class Child extends EventEmitter {
  constructor(pid = 123) { super(); this.pid = pid; this.signals = []; }
  kill(signal) { this.signals.push(signal); return true; }
}

test('owned child exit and close are observed once before cleanup', async () => {
  const child = new Child(), owner = trackOwnedChild(child);
  child.kill = signal => {
    child.signals.push(signal);
    queueMicrotask(() => { child.emit('exit', 0, null); child.emit('close', 0, null); });
    return true;
  };
  const first = owner.stop({ termMs: 10, killMs: 10 }), second = owner.stop();
  assert.equal(first, second);
  assert.equal(await first, true);
  assert.deepEqual(child.signals, ['SIGTERM']);
  assert.deepEqual(owner.state, { exited: true, closed: true, spawnFailed: false });
});

test('a child spawned by the test exits and closes before it is considered stopped', async () => {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
  const owner = trackOwnedChild(child);
  await once(child, 'spawn');
  assert.equal(await owner.stop({ termMs: 1000, killMs: 1000 }), true);
  assert.equal(owner.state.exited, true);
  assert.equal(owner.state.closed, true);
});

test('unconfirmed exit, missing close and signal errors cannot authorize cleanup', async () => {
  const stuck = new Child(), stuckOwner = trackOwnedChild(stuck);
  assert.equal(await stuckOwner.stop({ termMs: 2, killMs: 2 }), false);
  assert.deepEqual(stuck.signals, ['SIGTERM', 'SIGKILL']);
  const noClose = new Child(), noCloseOwner = trackOwnedChild(noClose);
  noClose.kill = () => { queueMicrotask(() => noClose.emit('exit', 0, null)); return true; };
  assert.equal(await noCloseOwner.stop({ termMs: 5, killMs: 2, closeMs: 2 }), false);
  const broken = new Child(), brokenOwner = trackOwnedChild(broken);
  broken.kill = () => { throw new Error('signal failed'); };
  await assert.rejects(brokenOwner.stop(), /signal failed/);
});

test('a reported spawn failure without a child PID is safe to recognize', async () => {
  const child = new Child(); delete child.pid;
  const owner = trackOwnedChild(child);
  child.emit('error', new Error('spawn failed'));
  assert.equal(await owner.stop({ termMs: 2, killMs: 2 }), true);
  assert.deepEqual(child.signals, []);
});

test('profile removal rejects replacement and symlink without touching either tree', async () => {
  const root = await mkdtemp(join(tmpdir(), 'agent-skin-profile-test-'));
  try {
    const target = join(root, 'profile'), saved = join(root, 'saved');
    await mkdir(target); await writeFile(join(target, 'original'), 'original');
    const identity = await profileIdentity(target);
    await rename(target, saved); await mkdir(target); await writeFile(join(target, 'unknown'), 'keep');
    assert.equal(await removeOwnedProfile(target, identity), false);
    assert.equal(await readFile(join(target, 'unknown'), 'utf8'), 'keep');
    assert.equal(await readFile(join(saved, 'original'), 'utf8'), 'original');
    await rename(target, join(root, 'foreign')); await symlink(saved, target);
    assert.equal(await removeOwnedProfile(target, identity), false);
    assert.equal(await readFile(join(saved, 'original'), 'utf8'), 'original');
    assert.equal(await removeOwnedProfile(saved, identity), true);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('failed or interrupted checks retain their profile for investigation', () => {
  const safe = { stopped: true, completed: true, fatalError: null, checks: [{ passed: true }, { skipped: true }], errors: [] };
  assert.equal(canRemoveProfile(safe), true);
  for (const change of [{ stopped: false }, { completed: false }, { fatalError: 'failed' },
    { checks: [{ passed: false }] }, { errors: ['cleanup failed'] }]) {
    assert.equal(canRemoveProfile({ ...safe, ...change }), false);
  }
});
