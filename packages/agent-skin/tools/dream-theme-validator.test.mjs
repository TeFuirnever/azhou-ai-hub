import assert from 'node:assert/strict';
import { Readable } from 'node:stream';
import { validateOfficialTheme, codePointLength } from '../vendor/dream-theme-validator.mjs';

const colorKeys = ['background', 'panel', 'panelAlt', 'accent', 'accentAlt', 'secondary', 'highlight', 'text', 'muted', 'line'];
const copyKeys = ['brandSubtitle', 'tagline', 'projectPrefix', 'projectLabel', 'statusText', 'quote', 'promoTitle', 'promoSub'];
const minimal = {schemaVersion: 1, id: 'demo', name: 'Dream', image: 'background.png'};
const full = {...minimal, ...Object.fromEntries(copyKeys.map(key => [key, '🦊'.repeat(120)])),
  promoUrl: 'data retained without navigation', appearance: 'auto',
  art: {focusX: 0, focusY: 1, safeArea: 'right', taskMode: 'ambient'},
  colors: Object.fromEntries(colorKeys.map(key => [key, '#123456']))};
assert.equal(codePointLength('🦊'), 1);
assert.equal(validateOfficialTheme(minimal), minimal);
assert.equal(validateOfficialTheme(full), full);
for (const image of ['background.png', 'background.jpg', 'background.webp']) validateOfficialTheme({...minimal, image});
for (const appearance of ['auto', 'light', 'dark']) validateOfficialTheme({...minimal, appearance});
for (const safeArea of ['left', 'right', 'none']) validateOfficialTheme({...minimal, art: {safeArea}});
for (const taskMode of ['ambient', 'full', 'off']) validateOfficialTheme({...minimal, art: {taskMode}});
validateOfficialTheme({...full, name: ' ', colors: {...full.colors, text: 'rgb(999, 0, 0)'}});
const invalid = [null, [], {}, {...minimal, extra: true}, {...minimal, schemaVersion: true},
  {...minimal, id: 'A'}, {...minimal, id: 'a'.repeat(65)}, {...minimal, name: ''}, {...minimal, name: 'x'.repeat(81)},
  {...minimal, image: 'background.jpeg'}, {...minimal, image: 'portal-hero.png'}, {...minimal, tagline: 'x'.repeat(121)},
  {...minimal, quote: '\0'}, {...minimal, promoUrl: 'x'.repeat(513)}, {...minimal, appearance: 'system'},
  {...minimal, art: []}, {...minimal, art: {extra: 1}}, {...minimal, art: {focusX: true}},
  {...minimal, art: {focusY: NaN}}, {...minimal, art: {focusX: -0.01}}, {...minimal, art: {focusY: 1.01}},
  {...minimal, art: {safeArea: 'center'}}, {...minimal, art: {taskMode: 'on'}},
  {...minimal, colors: {}}, {...full, colors: {...full.colors, extra: '#fff'}},
  {...full, colors: {...full.colors, text: 'var(--text)'}}, {...minimal, name: 1}];
for (const theme of invalid) assert.throws(() => validateOfficialTheme(theme));

const stdin = Object.getOwnPropertyDescriptor(process, 'stdin');
const write = process.stdout.write;
let output = '';
try {
  Object.defineProperty(process, 'stdin', {configurable: true, value: Readable.from([Buffer.from(JSON.stringify(full))])});
  process.stdout.write = chunk => {output += chunk; return true;};
  await import('./reference-official-theme.mjs');
} finally {
  Object.defineProperty(process, 'stdin', stdin);
  process.stdout.write = write;
}
assert.deepEqual(JSON.parse(output), {schema: 'azhou-agent-skin.reference-official-theme.v1',
  contract: 'codex-dream-official-theme/6fc42df4', status: 'passed', reasons: []});
console.log('Pinned official theme contract and bounded adapter passed');
