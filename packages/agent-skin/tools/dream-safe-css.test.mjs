import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import * as vendor from '../vendor/dream-safe-css-validator.mjs';

const policy = JSON.parse(await readFile(new URL('../vendor/dream-safe-css-policy.json', import.meta.url)));
assert.deepEqual(vendor.SAFE_CSS_CONTRACT, policy);
const selector = '[data-ds-part="main"]';
const basic = `${selector}{color:#fff;}`;
const four = 'color:#fff;background-color:#000;opacity:1;gap:0;';
const value = `rgb(0,0,${' '.repeat(502)}0)`;
assert.equal(value.length, 512);
const cases = [
  [basic, null],
  [basic + ' '.repeat(262144 - basic.length), null],
  [basic + ' '.repeat(262145 - basic.length), 'limit/bytes'],
  [basic.repeat(128), null],
  [basic.repeat(129), 'limit/rules'],
  [`${selector}{${four}}`.repeat(128), null],
  [`${selector}{${four}font-size:12px;}` + `${selector}{${four}}`.repeat(127), 'limit/declarations'],
  [`${selector}{color:${value};}`, null],
  [`${selector}{color:${value.replace('0)', ' 0)')};}`, 'limit/value'],
  ['@import "https://example.invalid";', 'syntax/rule'],
  [`${selector}{color:url(https://example.invalid);}`, 'value/unsupported'],
  ['body{color:#fff;}', 'selector/unsupported'],
  [`${selector},${selector}{color:#fff;}`, 'selector/list'],
  [`${selector}::before{color:#fff;}`, 'selector/unsupported'],
  [`${selector}{color:var(--unknown);}`, 'value/unsupported'],
  [`${selector}{color:#fff;color:#000;}`, 'property/duplicate'],
  [`/*comment*/${basic}`, 'syntax/comment'],
  [`${selector}{color:#fff!important;}`, 'value/token'],
  ['\\62ody{color:#fff;}', 'syntax/escape'],
  ['\ufeff' + basic, 'syntax/control'],
];
const modules = [vendor];
if (process.argv[2]) modules.push(await import(process.argv[2]));
for (const module of modules) {
  assert.deepEqual(module.SAFE_CSS_CONTRACT, policy);
  for (const [source, code] of cases) {
    if (code === null) assert.equal(module.validateSafeCss(source).status, 'validated');
    else assert.throws(() => module.validateSafeCss(source), error => error.code === code);
  }
}
console.log(`Safe CSS contract and ${cases.length} corpus cases passed for ${modules.length} source(s)`);
