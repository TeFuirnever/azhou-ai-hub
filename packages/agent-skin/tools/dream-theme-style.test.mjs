import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { mapDreamTheme, DREAM_PAINT_PROFILE } from '../dream-theme-style.mjs';
import { parseSafeCssAst } from '../vendor/dream-safe-css-ast.mjs';
import { validateSafeCss } from '../vendor/dream-safe-css-validator.mjs';

const main = '[data-ds-part="main"]';
const theme = {schemaVersion: 1, id: 'dream.demo', name: '<b>Display only</b>', image: 'background.png'};
const css = value => `${main}{background-color:${value};}`;
const expected = [
  ['#123', [17, 34, 51, 1]], ['#1234', [17, 34, 51, 68 / 255]],
  ['#123456', [18, 52, 86, 1]], ['#12345680', [18, 52, 86, 128 / 255]],
  ['TrAnSpArEnT', [0, 0, 0, 0]], ['RGB(255, 0, 1)', [255, 0, 1, 1]],
  ['rgba(100%, 25%, 0%, 50%)', [255, 63.75, 0, 0.5]],
  ['rgba(0,0,0,.25)', [0, 0, 0, 0.25]],
];
assert.equal(DREAM_PAINT_PROFILE, 'codex-main-literal-paint/v1');
for (const [literal, rgba] of expected) {
  const result = mapDreamTheme(theme, css(literal));
  assert.deepEqual(result, {profile: DREAM_PAINT_PROFILE, ruleCount: 1, declarationCount: 1,
    steps: [{rgba, backgroundImage: 'none'}]});
  assert(Object.isFrozen(result) && Object.isFrozen(result.steps) && Object.isFrozen(result.steps[0].rgba));
  assert(!JSON.stringify(result).includes('data-ds-part'));
}
const ordered = mapDreamTheme(theme, css('#fff') + css('transparent') + css('#123'));
assert.deepEqual(ordered.steps.map(step => step.rgba), [[255,255,255,1], [0,0,0,0], [17,34,51,1]]);
assert.equal(ordered.ruleCount, 3);
assert.equal(ordered.declarationCount, 3);
for (const source of [
  `${main}{background-color:#fff;color:#fff;}`, css('#fff') + '[data-ds-part="sidebar"]{background-color:#000;}',
  '[data-ds-part="main"]:hover{background-color:#fff;}', css('currentColor'),
  css('var(--ds-theme-color-background)'), `${main}{opacity:1;}`, `${main}{background-image:none;}`,
]) assert.throws(() => mapDreamTheme(theme, source), undefined, source);
for (const key of ['appearance', 'art', 'colors', 'tagline', 'promoUrl']) {
  assert.throws(() => mapDreamTheme({...theme, [key]: key === 'appearance' ? 'auto' : {}}, css('#fff')));
}
for (const invalid of [null, {}, {...theme, id:'BAD'}, {...theme, image:'portal-hero.png'}, {...theme, extra:true}]) {
  assert.throws(() => mapDreamTheme(invalid, css('#fff')));
}
const invalidCss = ['', 'body{background-color:#fff;}', css('rgb(256,0,0)'), css('url(x)'), css('#fff!important')];
for (const source of invalidCss) {
  assert.throws(() => validateSafeCss(source));
  assert.throws(() => parseSafeCssAst(source));
  assert.throws(() => mapDreamTheme(theme, source));
}
const vendor = await readFile(new URL('../vendor/dream-safe-css-validator.mjs', import.meta.url));
const derived = await readFile(new URL('../vendor/dream-safe-css-ast.mjs', import.meta.url));
const patch = Buffer.from('\nexport { parseSafeCss as parseSafeCssAst };\n');
assert(derived.equals(Buffer.concat([vendor, patch])));
assert.equal(createHash('sha256').update(vendor).digest('hex'), '98a626655a4167ba0bbbff5eab96e78de7a5a74371e4a4ff6d8ac15211e5b24e');
const generator = spawnSync('python3', ['-B', new URL('./derive-dream-safe-css-ast.py', import.meta.url).pathname, '--check'], {encoding:'utf8'});
assert.equal(generator.status, 0, generator.stderr);
console.log('Dream AST derivation and total ordered literal main-paint profile passed');
