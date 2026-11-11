// Offline acceptance harness unit and E2E-slice checks. The E2E slice replays
// the 2026-11-06 round-7 failure shape end to end: an ephemeral /json endpoint
// whose main page URL carries ?locale=en-GB, consumed through the same
// http->parse->match path the supervisor capture used.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { colorAlpha, ensureDir, mainPageTargets, parseTargets, singleMainPage, stripUrlForMatch, wallpaperBlockers } from './acceptance-harness.mjs';

const RENDERER = 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html';

test('stripUrlForMatch removes query and fragment in one pass', () => {
  assert.equal(stripUrlForMatch(RENDERER + '?locale=en-GB'), RENDERER);
  assert.equal(stripUrlForMatch(RENDERER + '#anchor'), RENDERER);
  assert.equal(stripUrlForMatch(RENDERER + '?locale=en-GB#anchor'), RENDERER);
  assert.equal(stripUrlForMatch(RENDERER), RENDERER);
  assert.equal(stripUrlForMatch(1234), '1234');
});

test('parseTargets passes arrays through and rejects non-JSON with the stable code', () => {
  assert.deepEqual(parseTargets('[]'), []);
  assert.deepEqual(parseTargets(JSON.stringify([{ type: 'page' }])), [{ type: 'page' }]);
  assert.throws(() => parseTargets('<html>502</html>'), /targets-not-json/);
});

test('mainPageTargets matches the query-string renderer URL and ignores the rest', () => {
  const targets = [
    { type: 'page', url: RENDERER + '?locale=en-GB' },
    { type: 'page', url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/other.html?locale=zh' },
    { type: 'iframe', url: RENDERER },
    { type: 'worker', url: RENDERER + '?lang=en' },
    { type: 'page' },
    null,
    'not-a-target',
  ];
  const pages = mainPageTargets(targets);
  assert.equal(pages.length, 1);
  assert.equal(pages[0].url, RENDERER + '?locale=en-GB');
  assert.deepEqual(mainPageTargets('not-an-array'), []);
});

test('singleMainPage returns the page or throws the supervisor error contract', () => {
  const one = [{ type: 'page', url: RENDERER }];
  assert.equal(singleMainPage(one).type, 'page');
  assert.throws(() => singleMainPage([]), /main-page-not-unique:0/);
  const two = [{ type: 'page', url: RENDERER }, { type: 'page', url: RENDERER + '?locale=zh' }];
  assert.throws(() => singleMainPage(two), /main-page-not-unique:2/);
});

test('ensureDir creates 0o700 and tolerates an existing directory', () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'acceptance-harness-'));
  const fresh = path.join(base, 'a', 'b');
  ensureDir(fresh);
  assert.equal(fs.statSync(fresh).mode & 0o777, 0o700);
  ensureDir(fresh);
  ensureDir(base);
  fs.rmSync(base, { recursive: true, force: true });
});

test('colorAlpha parses rgb/rgba and reports null for non-colors', () => {
  assert.equal(colorAlpha('rgb(22, 22, 22)'), 1);
  assert.equal(colorAlpha('rgba(0, 0, 0, 0)'), 0);
  assert.equal(colorAlpha('rgba(255, 255, 255, 0.05)'), 0.05);
  assert.equal(colorAlpha('transparent'), null);
  assert.equal(colorAlpha(undefined), null);
});

test('wallpaperBlockers flags opaque non-main layers and tolerates malformed input', () => {
  const section = { tag: 'SECTION', bg: 'rgb(22, 22, 22)' };
  const composer = { tag: 'DIV', bg: 'rgb(43, 43, 43)' };
  const transparent = { tag: 'DIV', bg: 'rgba(0, 0, 0, 0)' };
  const faint = { tag: 'DIV', bg: 'rgba(255, 255, 255, 0.05)' };
  const main = { tag: 'MAIN', bg: 'rgb(22, 22, 22)' };
  assert.deepEqual(wallpaperBlockers([composer, transparent, faint, section]), [composer, section]);
  assert.deepEqual(wallpaperBlockers([main]), [], 'main itself is marker-controlled, never a blocker');
  assert.deepEqual(wallpaperBlockers('garbage'), []);
  assert.deepEqual(wallpaperBlockers([null, 7]), []);
});

test('E2E slice: /json with ?locale=en-GB resolves through http to one main page', async () => {
  const body = JSON.stringify([
    { type: 'page', url: RENDERER + '?locale=en-GB', webSocketDebuggerUrl: 'ws://127.0.0.1:1/devtools/page/x' },
    { type: 'browser', url: 'file://' },
  ]);
  const server = http.createServer((_req, res) => { res.setHeader('content-type', 'application/json'); res.end(body); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  try {
    const fetched = await new Promise((resolve, reject) => {
      const req = http.get({ host: '127.0.0.1', port, path: '/json', timeout: 4000 }, res => {
        let raw = '';
        res.setEncoding('utf8');
        res.on('data', chunk => { raw += chunk; });
        res.on('end', () => resolve(raw));
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('targets-timeout')); });
    });
    const page = singleMainPage(parseTargets(fetched));
    assert.equal(page.webSocketDebuggerUrl, 'ws://127.0.0.1:1/devtools/page/x');
  } finally {
    server.close();
  }
});
