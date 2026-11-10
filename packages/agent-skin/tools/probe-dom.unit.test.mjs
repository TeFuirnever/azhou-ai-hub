import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';
import {
  DEFAULT_RECEIPT, PROBE_KIND, PROBE_SCHEMA, READ_EXPRESSIONS,
  defaultReceiptPath, evaluateReadonly, httpGetJson, main, openCdp,
  parseReceipt, probeDom, readReceipt, rendererPages,
} from './probe_dom.mjs';

const receipt = { port: 4321, pid: 98, launchTime: 182.5, executableSHA256: 'a'.repeat(64) };
const rendererUrl = 'file:///Applications/ZCode.app/Contents/Resources/app/out/renderer/index.html?locale=en#home';

async function withServer(respond, operation) {
  const server = createServer(respond);
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  try { return await operation(server.address().port); }
  finally { await new Promise(resolve => server.close(resolve)); }
}

class FixtureSocket {
  static instances = [];
  static values = [];
  constructor(url) {
    this.url = url;
    this.closed = false;
    this.listeners = new Map();
    FixtureSocket.instances.push(this);
    queueMicrotask(() => this.emit('open', {}));
  }
  addEventListener(name, callback) {
    const listeners = this.listeners.get(name) || [];
    listeners.push(callback);
    this.listeners.set(name, listeners);
  }
  emit(name, event) {
    for (const listener of this.listeners.get(name) || []) listener(event);
  }
  send(raw) {
    const { id } = JSON.parse(raw);
    const next = FixtureSocket.values.shift();
    if (next === 'timeout') return;
    if (next === 'invalid-message') {
      queueMicrotask(() => this.emit('message', { data: 'not json' }));
      return;
    }
    const response = next instanceof Error
      ? { id, error: { message: next.message } }
      : { id, result: { result: { value: next } } };
    queueMicrotask(() => this.emit('message', { data: JSON.stringify(response) }));
  }
  close() { this.closed = true; }
}

async function withSocket(values, run) {
  const original = globalThis.WebSocket;
  FixtureSocket.instances = [];
  FixtureSocket.values = [...values];
  globalThis.WebSocket = FixtureSocket;
  try { return await run(); }
  finally { globalThis.WebSocket = original; }
}

test('receipt data validates strict identity and never defaults to an unknown HOME', async () => {
  assert.equal(defaultReceiptPath('/fixture'), '/fixture/' + DEFAULT_RECEIPT);
  assert.throws(() => defaultReceiptPath(''), /receipt-path-unknown-home/);
  assert.deepEqual(parseReceipt(JSON.stringify(receipt)), receipt);
  for (const invalid of ['garbage', 'null', '[]', '{}']) {
    assert.throws(() => parseReceipt(invalid));
  }
  for (const [field, value] of [
    ['port', 0], ['port', 65536], ['pid', 0],
    ['launchTime', Number.POSITIVE_INFINITY], ['executableSHA256', 'x'],
  ]) {
    assert.throws(() => parseReceipt(JSON.stringify({ ...receipt, [field]: value })));
  }
  const directory = await mkdtemp(join(tmpdir(), 'zcode-probe-receipt-'));
  try {
    const file = join(directory, 'receipt.json');
    await writeFile(file, JSON.stringify(receipt));
    assert.deepEqual(readReceipt(file), { ...receipt, path: file });
    assert.throws(() => readReceipt(join(directory, 'absent')), /receipt-unreadable/);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('renderer discovery excludes other pages and ignores locale query/hash', () => {
  assert.deepEqual(rendererPages(null), []);
  assert.deepEqual(rendererPages([{ type: 'other', url: rendererUrl }, { type: 'page', url: 'https://example.org/' }]), []);
  assert.equal(rendererPages([{ type: 'page', url: rendererUrl }]).length, 1);
});

test('read-only expressions traverse the open shadow root and inspect wallpaper surfaces', () => {
  const dimensions = { x: 3.6, y: 9.4, width: 240.2, height: 48.5 };
  const button = { getAttribute: key => key === 'title' ? 'Appearance' : 'Open Appearance' };
  const avatar = { complete: true, naturalWidth: 48, naturalHeight: 48, getAttribute: () => 'data:image/png;base64,AAAA' };
  const label = { textContent: '阿舟' };
  const chip = {
    shadowRoot: { querySelector: selector => selector === 'button' ? button : selector === '.lbl' ? label : avatar },
    getBoundingClientRect: () => dimensions, getAttribute: () => 'mounted', closest: () => ({}),
  };
  const root = { tagName: 'DIV', getBoundingClientRect: () => dimensions, getAttribute: () => 'yes' };
  const pane = { tagName: 'MAIN', getBoundingClientRect: () => dimensions, getAttribute: () => 'yes' };
  const document = {
    querySelector: () => chip,
    querySelectorAll: selector => selector === 'aside[data-testid="sidebar"]' ? [root] : [root, pane],
    getElementById: () => root,
    documentElement: { getAttribute: () => 'active' },
    visibilityState: 'visible',
  };
  const result = runInNewContext(READ_EXPRESSIONS.entryChip, { document });
  assert.equal(result.shadowRoot, true);
  assert.equal(result.label, '阿舟');
  assert.equal(result.avatar.srcKind, 'data-url');
  assert.equal(result.visible, true);
  assert.equal(result.inSidebar, true);
  const surfaces = runInNewContext(READ_EXPRESSIONS.wallpaperSurfaces, { document });
  assert.deepEqual(Array.from(surfaces, item => item.role), ['root', 'main']);
  assert.equal(runInNewContext(READ_EXPRESSIONS.documentWallpaper, { document }), 'active');
});

test('HTTP target list resolves valid JSON and rejects malformed JSON', async () => {
  await withServer((request, response) => {
    response.setHeader('Content-Type', 'application/json');
    response.end(request.url === '/valid' ? '[{"type":"page"}]' : 'invalid');
  }, async port => {
    assert.equal((await httpGetJson('127.0.0.1', port, '/valid', 500))[0].type, 'page');
    await assert.rejects(() => httpGetJson('127.0.0.1', port, '/broken', 500), /targets-not-json/);
  });
});

test('CDP query resolves values and reports remote errors or bounded timeouts', async () => {
  await withSocket([{ key: 'present' }, new Error('denied'), 'timeout'], async () => {
    const cdp = openCdp('ws://fixture', 20);
    await cdp.opened;
    assert.deepEqual(await evaluateReadonly(cdp, 'true'), { key: 'present' });
    await assert.rejects(() => evaluateReadonly(cdp, 'false'), /cdp-error/);
    await assert.rejects(() => cdp.call('Runtime.evaluate'), /cdp-timeout/);
    cdp.close();
    assert.equal(FixtureSocket.instances[0].closed, true);
  });
  await assert.rejects(() => evaluateReadonly({ call: async () => ({ exceptionDetails: {} }) }, 'document.body'), /evaluate-failed/);
});

test('full read-only probe binds the receipt port to a unique renderer and closes CDP', async () => {
  await withServer((_request, response) => {
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify([{ id: 'renderer-1', type: 'page', url: rendererUrl, webSocketDebuggerUrl: 'ws://fixture' }]));
  }, async port => {
    await withSocket([[{ role: 'root' }, { role: 'main' }], 'active', { found: true, shadowRoot: true }], async () => {
      const probed = await probeDom({ port, timeoutMs: 500 });
      assert.equal(probed.kind, PROBE_KIND);
      assert.equal(probed.schema, PROBE_SCHEMA);
      assert.equal(probed.port, port);
      assert.equal(probed.page.receiptPath, null);
      assert.equal(probed.wallpaper.documentElement, 'active');
      assert.equal(probed.entry.shadowRoot, true);
      assert.equal(FixtureSocket.instances[0].closed, true);
    });
  });
  await withServer((_request, response) => response.end('[]'), async port => {
    await assert.rejects(() => probeDom({ port, timeoutMs: 500 }), /renderer-page-not-unique:0/);
  });
});

test('CLI denies malformed arguments before probing any host', async () => {
  assert.equal(await main(['node', 'probe', '--receipt']), 2);
  assert.equal(await main(['node', 'probe', '--port', 'NaN']), 2);
  assert.equal(await main(['node', 'probe', '--unknown', 'x']), 2);
});
