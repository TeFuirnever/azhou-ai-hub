const GLOBAL_NAME = '__azhouStartup';
const OWNER = 'azhou-codex-startup';
const VERSION = 1;
const PAGE_REASON = 'page-unsupported';
const ASSET_REASON = 'asset-invalid';
const FIXED_PAGE_REASONS = new Set(['asset-invalid', 'storage-unavailable']);
let nextRunId = 1;

function isMainPage(host) {
  try {
    const url = new URL(host.location.href);
    if (url.protocol !== 'app:' || url.hostname !== '-' || url.pathname !== '/index.html'
      || url.username || url.password || url.port) return false;
    const route = url.searchParams.get('initialRoute') ?? '/';
    return !/(avatar|quick.?chat|detached|mini|popover|notification)/i.test(route);
  } catch {
    return false;
  }
}

function existingController(host) {
  const global = Object.getOwnPropertyDescriptor(host, GLOBAL_NAME);
  if (!global) return { present: false };
  if (!Object.hasOwn(global, 'value') || !global.value || typeof global.value !== 'object') {
    return { present: true, owned: false };
  }
  const api = global.value;
  const owner = Object.getOwnPropertyDescriptor(api, 'owner')?.value;
  const version = Object.getOwnPropertyDescriptor(api, 'version')?.value;
  const status = Object.getOwnPropertyDescriptor(api, 'status')?.value;
  return { present: true, owned: owner === OWNER && version === VERSION && typeof status === 'function' };
}

function mountOverlay(host, payload, runId, receive) {
  const document = host.document;
  if (!document?.documentElement || typeof document.createElement !== 'function') {
    throw new TypeError('startup overlay host is unavailable');
  }
  const frame = document.createElement('iframe');
  frame.setAttribute('title', 'Agent Skin startup');
  frame.setAttribute('aria-label', 'Agent Skin startup overlay');
  frame.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:2147483647;background:transparent';
  frame.src = 'about:blank';
  document.documentElement.appendChild(frame);
  const contentWindow = frame.contentWindow;
  if (!contentWindow) {
    frame.remove();
    throw new TypeError('startup overlay frame is unavailable');
  }
  const bind = (name) => typeof contentWindow[name] === 'function'
    ? contentWindow[name].bind(contentWindow)
    : contentWindow[name];
  const environment = Object.freeze({
    window: contentWindow,
    document: contentWindow.document,
    location: contentWindow.location,
    performance: contentWindow.performance,
    indexedDB: contentWindow.indexedDB,
    Image: contentWindow.Image,
    Path2D: contentWindow.Path2D,
    URL: contentWindow.URL ?? URL,
    requestAnimationFrame: bind('requestAnimationFrame'),
    cancelAnimationFrame: bind('cancelAnimationFrame'),
    setTimeout: bind('setTimeout'),
    clearTimeout: bind('clearTimeout'),
  });
  const frameSpec = Object.freeze({ runId, intent: 'play', protocolVersion: 1 });
  const SEND = (data) => receive({ source: frame.contentWindow, data });
  return {
    contentWindow,
    start() {
      try {
        // The single trusted install expression compiles this callable in the
        // page realm; invoke it directly with the iframe's explicit bindings.
        const pending = payload(
          environment.window, environment.document, environment.location,
          environment.performance, environment.indexedDB, environment.Image,
          environment.Path2D, environment.URL, environment.requestAnimationFrame,
          environment.cancelAnimationFrame, environment.setTimeout, environment.clearTimeout,
          undefined, SEND, frameSpec,
        );
        if (pending && typeof pending.then === 'function') {
          Promise.resolve(pending).catch(() => SEND({
            type: 'azhou-startup', action: 'assetError', runId, reason: ASSET_REASON,
          }));
        }
      } catch {
        SEND({ type: 'azhou-startup', action: 'assetError', runId, reason: ASSET_REASON });
      }
    },
    remove: () => frame.remove(),
  };
}

class PageController {
  constructor(host) {
    this.host = host;
    this.frame = null;
    this.installed = false;
    this.disposed = false;
    this.watchdog = null;
    this.state = {
      phase: 'loading',
      runId: nextRunId++,
      ready: false,
      completed: false,
      overlay: false,
      reason: '',
      wallpaper: { applied: false, reason: '', imageDecoded: false },
      completion: null,
    };
    this.onMessage = (event) => this.#receive(event);
    this.api = Object.freeze({
      owner: OWNER,
      version: VERSION,
      install: (payload) => this.#install(payload),
      status: () => this.#status(),
      openSettings: () => this.#openSettings(),
      dispose: () => this.#dispose(),
    });
  }

  #install(payload) {
    if (this.disposed) return { installed: false, alreadyActive: false, reason: 'owner-conflict' };
    if (this.installed) return { installed: true, alreadyActive: true };
    if (typeof payload !== 'function') {
      this.#fail(ASSET_REASON);
      return { installed: false, alreadyActive: false, reason: ASSET_REASON };
    }
    try {
      this.host.addEventListener('message', this.onMessage);
      this.frame = mountOverlay(this.host, payload, this.state.runId, this.onMessage);
      if (!this.frame?.contentWindow || typeof this.frame.remove !== 'function') {
        throw new TypeError('startup overlay mount is invalid');
      }
      this.installed = true;
      this.state.overlay = true;
      this.watchdog = this.host.setTimeout(() => this.#timeout(), 25_000);
      this.frame.start();
      return { installed: true, alreadyActive: false };
    } catch {
      this.#fail(ASSET_REASON);
      this.#removeFrame();
      this.host.removeEventListener('message', this.onMessage);
      return { installed: false, alreadyActive: false, reason: ASSET_REASON };
    }
  }

  #receive(event) {
    if (this.disposed || !this.frame || event.source !== this.frame.contentWindow) return;
    const message = event.data;
    if (!message || typeof message !== 'object' || Array.isArray(message)
      || message.type !== 'azhou-startup' || !Number.isSafeInteger(message.runId)
      || message.runId !== this.state.runId || typeof message.action !== 'string') return;

    if (message.action === 'ready') {
      if (this.state.phase !== 'loading' || this.state.ready) return;
      this.state.ready = true;
      this.state.phase = 'playing';
      return;
    }
    if (message.action === 'complete') {
      if (!['loading', 'playing'].includes(this.state.phase) || typeof message.skipped !== 'boolean') return;
      if (!message.skipped && !this.state.ready) return;
      this.state.phase = 'complete';
      this.state.completed = true;
      this.state.overlay = false;
      this.state.completion = { cause: message.skipped ? 'skip' : 'natural', beforeReady: !this.state.ready };
      this.#clearWatchdog();
      this.host.removeEventListener('message', this.onMessage);
      this.#removeFrame();
      return;
    }
    if (message.action === 'assetError') {
      if (this.state.phase !== 'loading' || !FIXED_PAGE_REASONS.has(message.reason)) return;
      this.#fail(message.reason);
      this.#removeFrame();
      return;
    }
    if (message.action === 'restore') this.#dispose();
  }

  #fail(reason) {
    this.#clearWatchdog();
    this.state.phase = 'failed';
    this.state.overlay = false;
    this.state.reason = reason;
    this.host.removeEventListener('message', this.onMessage);
  }

  #timeout() {
    if (this.disposed || this.state.completed || !this.state.overlay) return;
    this.watchdog = null;
    this.state.phase = 'timeout';
    this.state.overlay = false;
    this.state.reason = 'overlay-timeout';
    this.host.removeEventListener('message', this.onMessage);
    this.#removeFrame();
  }

  #clearWatchdog() {
    if (this.watchdog === null) return;
    this.host.clearTimeout(this.watchdog);
    this.watchdog = null;
  }

  #status() {
    return {
      owner: OWNER,
      version: VERSION,
      phase: this.state.phase,
      runId: this.state.runId,
      ready: this.state.ready,
      completed: this.state.completed,
      overlay: this.state.overlay,
      reason: this.state.reason,
      wallpaper: { ...this.state.wallpaper },
      completion: this.state.completion ? { ...this.state.completion } : null,
    };
  }

  #openSettings() {
    if (this.disposed || this.state.phase === 'loading' || this.state.phase === 'complete'
      || this.state.phase === 'failed' || this.state.phase === 'timeout') return false;
    return false;
  }

  #removeFrame() {
    const frame = this.frame;
    this.frame = null;
    if (frame) frame.remove();
  }

  #dispose() {
    if (this.disposed) return { disposed: true };
    this.disposed = true;
    this.#clearWatchdog();
    this.state.phase = 'disposed';
    this.state.overlay = false;
    this.host.removeEventListener('message', this.onMessage);
    this.#removeFrame();
    const current = Object.getOwnPropertyDescriptor(this.host, GLOBAL_NAME);
    if (current && Object.hasOwn(current, 'value') && current.value === this.api) {
      delete this.host[GLOBAL_NAME];
    }
    return { disposed: true };
  }
}

export function installStartup(payload, host = globalThis) {
  if (!host || !isMainPage(host)) return { installed: false, alreadyActive: false, reason: PAGE_REASON };
  const current = existingController(host);
  if (current.present) {
    return current.owned
      ? { installed: true, alreadyActive: true }
      : { installed: false, alreadyActive: false, reason: 'owner-conflict' };
  }
  const controller = new PageController(host);
  try {
    Object.defineProperty(host, GLOBAL_NAME, {
      value: controller.api, configurable: true, enumerable: false, writable: false,
    });
  } catch {
    return { installed: false, alreadyActive: false, reason: 'owner-conflict' };
  }
  const result = controller.api.install(payload);
  if (!result.installed) controller.api.dispose();
  return result;
}
