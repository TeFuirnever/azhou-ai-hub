import assert from 'node:assert/strict';
import test from 'node:test';
import { CDP, navigateWithLoad } from './test-startup-browser-cdp.mjs';

class Socket {
  constructor() { this.handlers = new Map(); this.sent = []; }
  addEventListener(type, handler) {
    const list = this.handlers.get(type) || [];
    list.push(handler); this.handlers.set(type, list);
  }
  emit(type, value = {}) { for (const handler of this.handlers.get(type) || []) handler(value); }
  send(value) { this.sent.push(JSON.parse(value)); }
  close() { this.emit('close'); }
  message(value) { this.emit('message', { data: JSON.stringify(value) }); }
}

test('CDP resolves matching requests out of order and reports remote errors', async () => {
  const socket = new Socket(), cdp = new CDP(socket);
  const first = cdp.call('first'), second = cdp.call('second'), third = cdp.call('third');
  socket.message({ id: 2, result: { value: 2 } });
  socket.message({ id: 1, result: { value: 1 } });
  socket.message({ id: 3, error: { message: 'remote failure' } });
  assert.deepEqual(await first, { value: 1 });
  assert.deepEqual(await second, { value: 2 });
  await assert.rejects(third, /remote failure/);
  assert.equal(cdp.pending.size, 0);
});

test('send failures settle immediately, including falsy throws', async () => {
  const socket = new Socket(), cdp = new CDP(socket);
  socket.send = () => { throw new Error('send failed'); };
  await assert.rejects(cdp.call('first'), /send failed/);
  socket.send = () => { throw null; };
  assert.equal(await cdp.call('second').then(() => 'resolved', error => error), null);
  assert.equal(cdp.pending.size, 0);
});

test('connection close rejects requests and event waits without retained timers', async () => {
  const socket = new Socket(), cdp = new CDP(socket);
  const pending = cdp.call('pending'), waiting = cdp.waitForEvent('Page.loadEventFired');
  socket.close();
  await assert.rejects(pending, /CDP closed/);
  await assert.rejects(waiting, /CDP closed/);
  await assert.rejects(cdp.call('after'), /CDP closed/);
  await assert.rejects(cdp.waitForEvent('after'), /CDP closed/);
  assert.equal(cdp.pending.size, 0);
  assert.equal(cdp.eventWaiters.size, 0);
});

test('event predicates, cancellation and timeout release their waiters', async () => {
  const socket = new Socket(), cdp = new CDP(socket);
  const match = cdp.waitForEvent('event', value => value?.ready === true);
  socket.message({ method: 'event', params: { ready: false } });
  socket.message({ method: 'event', params: { ready: true } });
  assert.deepEqual(await match, { ready: true });
  const invalid = cdp.waitForEvent('bad', () => { throw null; });
  socket.message({ method: 'bad', params: {} });
  assert.equal(await invalid.then(() => 'resolved', error => error), null);
  const cancelled = cdp.waitForEvent('cancel');
  cancelled.cancel(); cancelled.cancel();
  await assert.rejects(cancelled, /cancelled/);
  await assert.rejects(cdp.waitForEvent('timeout', () => true, 5), /Timed out/);
  assert.equal(cdp.eventWaiters.size, 0);
});

test('navigation waits for load and cancels the waiter when navigation fails', async () => {
  const socket = new Socket(), cdp = new CDP(socket);
  const success = navigateWithLoad(cdp, 'http://127.0.0.1/');
  socket.message({ id: 1, result: {} });
  socket.message({ method: 'Page.loadEventFired', params: {} });
  await success;
  const failure = navigateWithLoad(cdp, 'http://127.0.0.1/fail');
  socket.message({ id: 2, result: { errorText: 'navigation failed' } });
  await assert.rejects(failure, /navigation failed/);
  assert.equal(cdp.eventWaiters.size, 0);
  assert.equal(cdp.pending.size, 0);
});

test('open rejects non-loopback and non-page websocket addresses', async () => {
  await assert.rejects(CDP.open('ws://localhost:1234/devtools/page/a', 1234));
  await assert.rejects(CDP.open('ws://127.0.0.1:1234/devtools/browser/a', 1234));
  await assert.rejects(CDP.open('wss://127.0.0.1:1234/devtools/page/a', 1234));
});
