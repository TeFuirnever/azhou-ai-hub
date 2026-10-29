import assert from 'node:assert/strict';
import test from 'node:test';
import { validateCheckSelection } from './startup-browser-selection.mjs';

const homeNavCheck = 'appearance entry follows Your dot in the real Home nav and survives narrow layout and remount';
const generatedOnlyCheck = 'generated startup wallpaper failure is visible near the appearance entry';

test('valid plus unknown selection reports the missing name', () => {
  const result = validateCheckSelection([homeNavCheck, 'unknown check'], new Set([homeNavCheck]));

  assert.deepEqual(result, { valid: false, missingChecks: ['unknown check'] });
});

test('unknown-only selection fails with its missing name', () => {
  const result = validateCheckSelection(['unknown check'], new Set([homeNavCheck]));

  assert.deepEqual(result, { valid: false, missingChecks: ['unknown check'] });
});

test('check unavailable in the current mode is missing', () => {
  const baseModeChecks = new Set([homeNavCheck]);
  const generatedModeChecks = new Set([...baseModeChecks, generatedOnlyCheck]);

  assert.deepEqual(validateCheckSelection([generatedOnlyCheck], baseModeChecks), {
    valid: false,
    missingChecks: [generatedOnlyCheck],
  });
  assert.deepEqual(validateCheckSelection([generatedOnlyCheck], generatedModeChecks), {
    valid: true,
    missingChecks: [],
  });
});

test('valid-only selection passes', () => {
  assert.deepEqual(validateCheckSelection([homeNavCheck], new Set([homeNavCheck])), {
    valid: true,
    missingChecks: [],
  });
});
