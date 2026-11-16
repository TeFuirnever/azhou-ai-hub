import assert from 'node:assert/strict';
import test from 'node:test';
import { createCodexPageAdapter } from '../extension/codex-page-adapter.mjs';

const page = () => ({ document: {}, location: { href: 'app://-/index.html?initialRoute=%2F' } });
const token = (adapter, host) => {
  const result = adapter.identify(host);
  assert.equal(result.kind, 'matched');
  assert.equal(typeof result.documentToken, 'string');
  assert.ok(result.documentToken.length > 0);
  return result.documentToken;
};

test('the current observed page retains its identity', () => {
  const host = page();
  const adapter = createCodexPageAdapter(host);
  assert.equal(token(adapter, host), token(adapter, host));
});

test('observed A to B to A navigation does not revive A identity', () => {
  const host = page();
  const adapter = createCodexPageAdapter(host);
  const first = token(adapter, host);
  host.location.href = 'app://-/index.html?initialRoute=%2Fthread';
  const second = token(adapter, host);
  host.location.href = 'app://-/index.html?initialRoute=%2F';
  const third = token(adapter, host);
  assert.equal(new Set([first, second, third]).size, 3);
  assert.equal(token(adapter, host), third);
});

for (const href of ['not a url', 'app://-/index.html?initialRoute=%2Favatar',
  'app://-/index.html?initialRoute=%2Fmini', 'app://-/index.html?initialRoute=%2Fdetached']) {
  test(`observing unsupported page ${href} retires the prior identity`, () => {
    const host = page();
    const adapter = createCodexPageAdapter(host);
    const first = token(adapter, host);
    host.location.href = href;
    assert.deepEqual(adapter.identify(host), { kind: 'unmatched', reason: 'page-unsupported' });
    host.location.href = 'app://-/index.html?initialRoute=%2F';
    assert.notEqual(token(adapter, host), first);
  });
}

test('replacement Document at the same URL receives a new identity', () => {
  const host = page();
  const adapter = createCodexPageAdapter(host);
  const first = token(adapter, host);
  const original = host.document;
  host.document = {};
  const second = token(adapter, host);
  host.document = original;
  assert.equal(new Set([first, second, token(adapter, host)]).size, 3);
});

test('replacement host with the same Document and URL receives a new identity', () => {
  const host = page();
  const adapter = createCodexPageAdapter(host);
  const replacement = { ...host };
  const first = token(adapter, host);
  const second = token(adapter, replacement);
  assert.equal(new Set([first, second, token(adapter, host)]).size, 3);
});

test('construction does not read the host or register observers', () => {
  const host = new Proxy({}, { get() { throw new Error('unexpected host access'); } });
  assert.ok(createCodexPageAdapter(host));
});

for (const unavailable of [null, { get location() { throw new Error('page unavailable'); } },
  { location: { href: 'app://-/index.html' }, get document() { throw new Error('document unavailable'); } }]) {
  test('an unavailable observation retires identity without throwing', () => {
    const host = page();
    const adapter = createCodexPageAdapter(host);
    const first = token(adapter, host);
    assert.deepEqual(adapter.identify(unavailable), { kind: 'unmatched', reason: 'page-unsupported' });
    assert.notEqual(token(adapter, host), first);
  });
}
