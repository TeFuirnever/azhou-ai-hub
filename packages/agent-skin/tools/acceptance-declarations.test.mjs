// Behavior-level contract for explicit L4/L5 host observation declarations.
// These are synthetic validation tests, not evidence that a real host was run.
import assert from 'node:assert/strict';
import test from 'node:test';
import { ACCEPTANCE_DECLARATION_FACTS, acceptanceDeclarations } from './acceptance-harness.mjs';

const run = {
  runID: 'rc42-zcode-real-run',
  startedAt: '2026-11-10T09:00:00Z',
  endedAt: '2026-11-10T09:12:00Z',
  evidenceIDs: ['rc42-appearance', 'rc42-settings'],
};
const observe = (fact, overrides = {}) => ({
  runID: run.runID,
  fact,
  outcome: 'observed',
  observedAt: '2026-11-10T09:05:00Z',
  evidenceID: fact === 'ownedAppearanceSurface' ? 'rc42-appearance' : 'rc42-settings',
  ...overrides,
});
const valid = () => [observe('ownedAppearanceSurface'), observe('persistentSettings')];

test('only matching run observations can produce explicit declarations', () => {
  assert.deepEqual(ACCEPTANCE_DECLARATION_FACTS, ['ownedAppearanceSurface', 'persistentSettings']);
  assert.deepEqual(acceptanceDeclarations(run, valid()),
    { ownedAppearanceSurface: true, persistentSettings: true });
  assert.deepEqual(acceptanceDeclarations(run, [
    ...valid(), observe('wallpaper', { evidenceID: 'rc42-wallpaper' }),
    observe('persistentSettings', { observedAt: '2026-11-10T09:11:59Z' }),
  ]), { ownedAppearanceSurface: true, persistentSettings: true });
});

test('missing, failed or unknown capability observations refuse', () => {
  assert.throws(() => acceptanceDeclarations(run, [observe('persistentSettings')]),
    /ownedAppearanceSurface-not-observed/);
  assert.throws(() => acceptanceDeclarations(run, [observe('ownedAppearanceSurface')]),
    /persistentSettings-not-observed/);
  for (const fact of ACCEPTANCE_DECLARATION_FACTS) {
    for (const outcome of ['failed', 'refused', 'unverified']) {
      assert.throws(() => acceptanceDeclarations(run,
        [...valid(), observe(fact, { outcome })]), /outcome-not-observed/);
    }
  }
  assert.throws(() => acceptanceDeclarations(run, [
    observe('ownedAppearanceSurface', { outcome: 'maybe' }),
    observe('persistentSettings'),
  ]), /outcome-invalid/);
  assert.throws(() => acceptanceDeclarations(run, [
    observe('ownedAppearanceSurface', { outcome: '' }),
    observe('persistentSettings'),
  ]), /outcome-invalid/);
});

test('foreign, stale, future, and unbound evidence refuse', () => {
  const samples = [
    [{ runID: 'other-run' }, /foreign-run/],
    [{ observedAt: '2026-11-08T09:05:00Z' }, /outside-window/],
    [{ observedAt: '2026-11-10T09:12:01Z' }, /outside-window/],
    [{ evidenceID: 'not-allowed' }, /evidence-unbound/],
    [{ evidenceID: '' }, /evidence-unbound/],
  ];
  for (const [changes, reason] of samples) {
    assert.throws(() => acceptanceDeclarations(run,
      [observe('ownedAppearanceSurface', changes), observe('persistentSettings')]), reason);
  }
});

test('malformed run metadata refuses rather than accepting truthy defaults', () => {
  const cases = [null, [], 'run', {}, { ...run, runID: '' },
    { ...run, startedAt: '2026-11-10T09:13:00Z' },
    { ...run, startedAt: 'bad' }, { ...run, endedAt: '' },
    { ...run, evidenceIDs: [] }, { ...run, evidenceIDs: ['rc42-appearance'] },
  ];
  for (const bad of cases) {
    assert.throws(() => acceptanceDeclarations(bad, valid()), /run-invalid|evidence-unbound/);
  }
});

test('malformed observations and holes cannot bypass validation', () => {
  for (const value of [null, {}, 'not-array']) {
    assert.throws(() => acceptanceDeclarations(run, value), /observations-not-array/);
  }
  const sparse = valid();
  sparse.length = 3;
  assert.throws(() => acceptanceDeclarations(run, sparse), /malformed/);
  for (const malformed of [null, 7, [], {}, { ...observe('ownedAppearanceSurface'), fact: '' },
    { ...observe('ownedAppearanceSurface'), outcome: 4 },
    { ...observe('ownedAppearanceSurface'), observedAt: 'yesterday' }]) {
    assert.throws(() => acceptanceDeclarations(run, [malformed, ...valid()]),
      /malformed|fact-invalid|outcome-invalid|observedAt-invalid/);
  }
});

test('invalid ISO date and loosely parsed dates refuse', () => {
  for (const when of ['2026-11-10 09:05:00Z', '2026-02-30T09:05:00Z',
    '2026-11-10T09:05:00', '2026-11-10T09:05:00+08:00']) {
    assert.throws(() => acceptanceDeclarations(run,
      [observe('ownedAppearanceSurface', { observedAt: when }), observe('persistentSettings')]),
      /observedAt-invalid/);
  }
  assert.throws(() => acceptanceDeclarations({ ...run, startedAt: '2026-02-30T09:00:00Z' }, valid()),
    /run-invalid/);
});

test('unknown facts remain valid contextual observations without satisfying a missing capability', () => {
  assert.throws(() => acceptanceDeclarations(run, [
    observe('wallpaper', { evidenceID: 'rc42-wallpaper' }), observe('persistentSettings'),
  ]), /ownedAppearanceSurface-not-observed/);
  assert.deepEqual(acceptanceDeclarations(run, [...valid(), observe('wallpaper', {
    evidenceID: 'rc42-wallpaper', outcome: 'failed',
  })]), { ownedAppearanceSurface: true, persistentSettings: true });
});
