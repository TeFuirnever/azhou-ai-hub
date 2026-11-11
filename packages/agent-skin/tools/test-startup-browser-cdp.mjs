import assert from 'node:assert/strict';

export class CDP {
  constructor(socket) {
    this.socket = socket;
    this.nextID = 1;
    this.pending = new Map();
    this.eventWaiters = new Set();
    this.closed = false;
    socket.addEventListener('message', event => {
      let packet;
      try { packet = JSON.parse(event.data); } catch { return; }
      if (!packet || typeof packet !== 'object') return;
      if (packet.method) {
        for (const waiter of this.eventWaiters) {
          if (waiter.method !== packet.method) continue;
          try {
            if (waiter.predicate(packet.params)) waiter.finish(null, packet.params);
          } catch (error) { waiter.finish(error, undefined, true); }
        }
        return;
      }
      if (!packet.id) return;
      const pending = this.pending.get(packet.id);
      if (pending) pending.finish(packet.error ? new Error(packet.error.message) : null, packet.result);
    });
    socket.addEventListener('close', () => {
      this.closed = true;
      for (const pending of this.pending.values()) pending.finish(new Error('Fixture CDP closed'));
      for (const waiter of this.eventWaiters) waiter.finish(new Error('Fixture CDP closed'));
    });
  }

  static async open(address, expectedPort) {
    const url = new URL(address);
    assert.equal(url.protocol, 'ws:');
    assert.equal(url.hostname, '127.0.0.1');
    assert.equal(Number(url.port), expectedPort);
    assert.ok(url.pathname.startsWith('/devtools/page/'));
    const socket = new WebSocket(address);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { socket.close(); reject(new Error('Fixture WebSocket timeout')); }, 5000);
      socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Fixture WebSocket failed')); }, { once: true });
    });
    return new CDP(socket);
  }

  call(method, params = {}) {
    if (this.closed) return Promise.reject(new Error('Fixture CDP closed'));
    const id = this.nextID++;
    return new Promise((resolve, reject) => {
      const finish = (error, result, failed = Boolean(error)) => {
        if (!this.pending.delete(id)) return;
        clearTimeout(timer);
        if (failed) reject(error); else resolve(result);
      };
      const timer = setTimeout(() => finish(new Error('Fixture CDP timeout: ' + method)), 12000);
      this.pending.set(id, { finish });
      try { this.socket.send(JSON.stringify({ id, method, params })); }
      catch (error) { finish(error, undefined, true); }
    });
  }

  waitForEvent(method, predicate = () => true, timeoutMs = 10000) {
    let cancel;
    const promise = new Promise((resolve, reject) => {
      const waiter = { method, predicate, timer: null, finish: null };
      waiter.finish = (error, result, failed = Boolean(error)) => {
        if (!this.eventWaiters.delete(waiter)) return;
        clearTimeout(waiter.timer);
        if (failed) reject(error); else resolve(result);
      };
      cancel = () => waiter.finish(new Error('Fixture event wait cancelled'));
      this.eventWaiters.add(waiter);
      waiter.timer = setTimeout(() => waiter.finish(new Error('Timed out waiting for CDP event ' + method)), timeoutMs);
      if (this.closed) waiter.finish(new Error('Fixture CDP closed'));
    });
    promise.catch(() => {});
    promise.cancel = cancel;
    return promise;
  }

  async evaluate(expression) {
    const result = await this.call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, timeout: 10000 });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  }

  close() { this.socket.close(); }
}

export async function navigateWithLoad(cdp, url) {
  const loaded = cdp.waitForEvent('Page.loadEventFired');
  try {
    const navigation = cdp.call('Page.navigate', { url }).then(result => {
      assert.ok(!result.errorText, result.errorText);
      return result;
    });
    const [result] = await Promise.all([navigation, loaded]);
    return result;
  } finally { loaded.cancel(); }
}
