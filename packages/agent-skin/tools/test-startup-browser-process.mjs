import { lstat, rm } from 'node:fs/promises';

async function waitFor(promise, ms) {
  let timer;
  try { await Promise.race([promise, new Promise(resolve => { timer = setTimeout(resolve, ms); })]); }
  finally { clearTimeout(timer); }
}

export function trackOwnedChild(child) {
  const state = { exited: false, closed: false, spawnFailed: false };
  let resolveExit, resolveClose;
  const exited = new Promise(resolve => { resolveExit = resolve; });
  const closed = new Promise(resolve => { resolveClose = resolve; });
  child.once('exit', () => { state.exited = true; resolveExit(); });
  child.once('close', () => { state.closed = true; resolveClose(); });
  child.once('error', () => { if (child.pid === undefined) state.spawnFailed = true; });
  let stopping, stopEvidence;
  return {
    state,
    get stopEvidence() { return stopEvidence; },
    stop({ termMs = 2000, killMs = 1000, closeMs = 30000 } = {}) {
      if (stopping) return stopping;
      stopping = (async () => {
        let term = 'not-attempted', kill = 'not-attempted', stdio = 'not-needed';
        try {
          if (!state.exited && !state.spawnFailed) {
            term = 'signal-error';
            child.kill('SIGTERM');
            await waitFor(exited, termMs);
            term = state.exited ? 'observed-exit' : 'deadline';
          }
          if (!state.exited && !state.spawnFailed) {
            kill = 'signal-error';
            child.kill('SIGKILL');
            await waitFor(exited, killMs);
            kill = state.exited ? 'observed-exit' : 'deadline';
          }
          // A dead browser is not a closed pipe: Chrome helper processes inherit
          // the stderr pipe and can outlive the exited browser by ~25s (measured
          // on a native-transport run holding the page socket). Only runs whose
          // child died with the pipe still open reach this wait, and past closeMs
          // the unconfirmed pipe keeps cleanup fail-closed.
          if (state.exited && !state.closed && !state.spawnFailed) {
            await waitFor(closed, closeMs);
            stdio = state.closed ? 'observed-close' : 'deadline';
          }
          return (state.exited && state.closed) || (state.spawnFailed && child.pid === undefined);
        } finally {
          stopEvidence = Object.freeze({ ...state, term, kill, stdio, termMs, killMs, closeMs });
        }
      })();
      return stopping;
    },
  };
}

export async function profileIdentity(profile) {
  const info = await lstat(profile);
  if (!info.isDirectory() || info.isSymbolicLink()) throw new Error('Fixture profile is not a directory');
  return { device: info.dev, inode: info.ino };
}

export async function removeOwnedProfile(profile, expected) {
  if (!profile || !expected) return false;
  let observed;
  try { observed = await profileIdentity(profile); } catch { return false; }
  if (observed.device !== expected.device || observed.inode !== expected.inode) return false;
  await rm(profile, { recursive: true, force: false, maxRetries: 4, retryDelay: 100 });
  return true;
}

export function canRemoveProfile({ stopped, completed, fatalError, checks, errors }) {
  return stopped && completed && !fatalError && errors.length === 0
    && checks.every(item => item.passed || item.skipped);
}
