const GLOBAL_NAME = '__azhouStartup';
const WALLPAPER_GLOBAL = '__azhouWallpaper';
const OWNER = 'azhou-codex-startup';
const VERSION = 1;
const LEGACY_WALLPAPER_OWNER = 'azhou.codex-startup-animation';
const LEGACY_WALLPAPER_VERSION = '0.7.1';
const PAGE_REASON = 'page-unsupported';
const ASSET_REASON = 'asset-invalid';
const FIXED_PAGE_REASONS = new Set(['asset-invalid', 'storage-unavailable']);
const BACKGROUND_DATA_URL = /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/;
const WALLPAPER_STATUS_FIELDS = [
  'backgroundMatched', 'washMatched', 'coverMatched', 'fixedViewport', 'matchedSurfaces', 'transparentSurfaces',
  'rootClear', 'workspaceBackgroundClear', 'footerSurfaces', 'footerBackgroundClear',
  'footerFadeSurfaces', 'footerFadeClear', 'topFadeSurfaces', 'topFadeClear',
  'decorationEffectsClear', 'unsupportedDecorations', 'verificationScope',
];
let nextRunId = 1;

function dataProperty(object, name) {
  if (!object || (typeof object !== 'object' && typeof object !== 'function')) return undefined;
  const descriptor = Object.getOwnPropertyDescriptor(object, name);
  return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
}

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
  const descriptor = Object.getOwnPropertyDescriptor(host, GLOBAL_NAME);
  if (!descriptor) return { present: false };
  if (!Object.hasOwn(descriptor, 'value') || !descriptor.value || typeof descriptor.value !== 'object') {
    return { present: true, owned: false };
  }
  const api = descriptor.value;
  return {
    present: true,
    owned: dataProperty(api, 'owner') === OWNER
      && dataProperty(api, 'version') === VERSION
      && typeof dataProperty(api, 'status') === 'function'
      && typeof dataProperty(api, 'openSettings') === 'function'
      && typeof dataProperty(api, 'dispose') === 'function',
  };
}

function wallpaperRecord(host) {
  const descriptor = Object.getOwnPropertyDescriptor(host, WALLPAPER_GLOBAL);
  if (!descriptor) return { present: false, supported: false, api: null };
  if (!Object.hasOwn(descriptor, 'value') || !descriptor.value || typeof descriptor.value !== 'object') {
    return { present: true, supported: false, api: null };
  }
  const api = descriptor.value;
  const supported = dataProperty(api, 'owner') === LEGACY_WALLPAPER_OWNER
    && dataProperty(api, 'version') === LEGACY_WALLPAPER_VERSION
    && typeof dataProperty(api, 'status') === 'function'
    && typeof dataProperty(api, 'dispose') === 'function';
  return { present: true, supported, api: supported ? api : null };
}

function shortcut(event) {
  return event?.metaKey === true && event?.altKey === true
    && typeof event.key === 'string' && event.key.toLowerCase() === 'b';
}

function mountOverlay(host, payload, runId, intent, assets, receive) {
  const document = host.document;
  if (!document?.documentElement || typeof document.createElement !== 'function' || !document.body) {
    throw new TypeError('startup overlay host is unavailable');
  }
  const frame = document.createElement('iframe');
  frame.setAttribute('title', 'Agent Skin startup');
  frame.setAttribute('aria-label', 'Agent Skin startup overlay');
  frame.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:2147483647;background:transparent';
  frame.src = 'about:blank';
  const parent = typeof document.body.appendChild === 'function' ? document.body : document.documentElement;
  parent.appendChild(frame);
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
  const frameSpec = Object.freeze({ runId, intent, protocolVersion: 1, assets });
  const SEND = (data) => receive({ source: frame.contentWindow, data });
  return {
    element: frame,
    contentWindow,
    start() {
      return payload(
        environment.window, environment.document, environment.location,
        environment.performance, environment.indexedDB, environment.Image,
        environment.Path2D, environment.URL, environment.requestAnimationFrame,
        environment.cancelAnimationFrame, environment.setTimeout, environment.clearTimeout,
        undefined, SEND, frameSpec,
      );
    },
    remove: () => frame.remove(),
  };
}

class PageController {
  constructor(host, payload) {
    this.host = host;
    this.document = host.document;
    this.payload = payload;
    this.assets = dataProperty(payload, 'assets') ?? null;
    this.wallpaperApply = dataProperty(payload, 'applyWallpaper');
    this.frame = null;
    this.frameHandle = null;
    this.wallpaperAPI = null;
    this.installed = false;
    this.disposed = false;
    this.watchdog = null;
    this.bodyObserver = null;
    this.savedFocus = this.document?.activeElement ?? null;
    this.intent = 'play';
    this.state = {
      phase: 'loading',
      runId: 0,
      ready: false,
      completed: false,
      overlay: false,
      reason: '',
      wallpaper: { applied: false, reason: '', imageDecoded: false },
      completion: null,
    };
    this.onMessage = (event) => this.#receive(event);
    this.onParentKeydown = (event) => {
      if (!shortcut(event)) return;
      if (this.state.phase === 'settings') {
        event.preventDefault?.();
        return;
      }
      if (this.#openSettings()) event.preventDefault?.();
    };
    this.onFrameKeydown = (event) => {
      if (!shortcut(event)) return;
      if (this.#openSettings()) event.preventDefault?.();
    };
    this.api = Object.freeze({
      owner: OWNER,
      version: VERSION,
      install: (nextPayload) => this.#install(nextPayload),
      status: () => this.#status(),
      openSettings: () => this.#openSettings(),
      dispose: () => this.#dispose(),
    });
  }

  #install(payload) {
    if (this.disposed || this.installed || payload !== this.payload || typeof payload !== 'function') {
      return this.disposed || this.installed
        ? { installed: false, alreadyActive: false, reason: 'owner-conflict' }
        : { installed: false, alreadyActive: false, reason: ASSET_REASON };
    }
    const wallpaper = wallpaperRecord(this.host);
    if (wallpaper.present && !wallpaper.supported) {
      return { installed: false, alreadyActive: false, reason: 'owner-conflict' };
    }
    this.wallpaperAPI = wallpaper.api;
    this.installed = true;
    this.host.addEventListener('keydown', this.onParentKeydown);
    if (!this.#beginRun('play')) {
      this.host.removeEventListener('keydown', this.onParentKeydown);
      this.installed = false;
      return { installed: false, alreadyActive: false, reason: PAGE_REASON };
    }
    return { installed: true, alreadyActive: false };
  }

  #beginRun(intent) {
    if (this.disposed) return false;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    this.#stopFrame();
    this.intent = intent;
    this.state.phase = 'loading';
    this.state.runId = nextRunId++;
    this.state.ready = false;
    this.state.completed = false;
    this.state.overlay = true;
    this.state.reason = '';
    this.state.completion = null;
    const runId = this.state.runId;
    this.host.addEventListener('message', this.onMessage);
    this.watchdog = this.host.setTimeout(() => this.expire(runId), 25_000);
    if (this.document?.body) {
      this.#mountRun(runId);
      return this.state.phase !== 'failed';
    }
    return this.#waitForBody(runId);
  }

  #waitForBody(runId) {
    const MutationObserver = this.host.MutationObserver;
    if (typeof MutationObserver !== 'function' || !this.document?.documentElement) {
      this.#fail(PAGE_REASON, runId);
      return false;
    }
    try {
      this.bodyObserver = new MutationObserver(() => {
        if (!this.#isLoading(runId) || !this.document.body) return;
        this.#disconnectBodyObserver();
        this.#mountRun(runId);
      });
      this.bodyObserver.observe(this.document.documentElement, { childList: true, subtree: true });
      if (this.document.body) {
        this.#disconnectBodyObserver();
        this.#mountRun(runId);
      }
      return this.state.phase !== 'failed';
    } catch {
      this.#fail(PAGE_REASON, runId);
      return false;
    }
  }

  #mountRun(runId) {
    if (!this.#isLoading(runId) || !this.document.body) return;
    try {
      this.frame = mountOverlay(this.host, this.payload, runId, this.intent, this.assets, this.onMessage);
      this.frame.contentWindow.addEventListener('keydown', this.onFrameKeydown);
      const instance = this.frame.start();
      if (instance && typeof instance.then === 'function') {
        Promise.resolve(instance).then(
          (handle) => this.#acceptFrameHandle(handle, runId),
          () => this.#fail(ASSET_REASON, runId),
        );
      } else {
        this.#acceptFrameHandle(instance, runId);
      }
    } catch {
      this.#fail(ASSET_REASON, runId);
    }
  }

  #acceptFrameHandle(handle, runId) {
    if (!this.#isCurrentFrame(runId)) {
      try { handle?.dispose?.(); } catch {}
      return;
    }
    if (handle && typeof handle === 'object') this.frameHandle = handle;
  }

  #isLoading(runId) {
    return !this.disposed && runId === this.state.runId && this.state.phase === 'loading';
  }

  #isCurrentFrame(runId, frame = this.frame) {
    return !this.disposed && runId === this.state.runId && frame !== null
      && frame === this.frame && !['complete', 'failed', 'timeout', 'disposed'].includes(this.state.phase);
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
      this.state.phase = this.intent === 'play' ? 'playing' : 'settings';
      if (this.intent === 'settings') this.#clearWatchdog();
      return;
    }
    if (message.action === 'complete') {
      const phase = this.state.phase;
      const settingsCancel = phase === 'settings' && message.skipped === true;
      const playCompletion = this.intent === 'play' && ['loading', 'playing'].includes(phase)
        && typeof message.skipped === 'boolean' && (message.skipped || this.state.ready);
      if (!settingsCancel && !playCompletion) return;
      this.state.phase = 'complete';
      this.state.completed = true;
      this.state.overlay = false;
      this.state.completion = settingsCancel
        ? { cause: 'settings-cancel', beforeReady: false }
        : { cause: message.skipped ? 'skip' : 'natural', beforeReady: !this.state.ready };
      this.#clearWatchdog();
      this.host.removeEventListener('message', this.onMessage);
      this.#stopFrame();
      return;
    }
    if (message.action === 'assetError') {
      if (this.state.phase !== 'loading' || !FIXED_PAGE_REASONS.has(message.reason)) return;
      this.#fail(message.reason);
      return;
    }
    if (message.action === 'settings-open') {
      if (this.state.ready && this.state.phase === 'playing') {
        this.state.phase = 'settings';
        this.#clearWatchdog();
      }
      return;
    }
    if (message.action === 'settings-close') {
      if (this.state.ready && this.state.phase === 'settings') this.#beginRun('play');
      return;
    }
    if (message.action === 'background') {
      if (['loading', 'playing', 'settings'].includes(this.state.phase)) {
        this.#applyWallpaper(message, this.state.runId, this.frame);
      }
      return;
    }
    if (message.action === 'restore') this.#dispose();
  }

  async #applyWallpaper(message, runId, frame) {
    if (typeof message.image !== 'string' || message.image.length > 16 * 1024 * 1024
      || !BACKGROUND_DATA_URL.test(message.image) || !Number.isInteger(message.strength)
      || message.strength < 0 || message.strength > 75) {
      this.state.wallpaper = { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
      return;
    }
    if (message.strength === 0) {
      this.#disposeWallpaper();
      this.state.wallpaper = { applied: false, reason: 'disabled', imageDecoded: false };
      return;
    }
    if (typeof this.wallpaperApply !== 'function') {
      this.state.wallpaper = { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
      return;
    }
    const isCurrent = () => this.#isCurrentFrame(runId, frame);
    try {
      await this.wallpaperApply(Object.freeze({ image: message.image, strength: message.strength }), isCurrent);
      if (!isCurrent()) return;
      const current = wallpaperRecord(this.host);
      if (!current.supported) {
        this.state.wallpaper = { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
        return;
      }
      this.wallpaperAPI = current.api;
      this.state.wallpaper = this.#wallpaperStatus(current.api);
      if (!this.state.wallpaper.applied && !this.state.wallpaper.reason) {
        this.state.wallpaper.reason = 'wallpaper-unsupported';
      }
    } catch {
      if (isCurrent()) this.state.wallpaper = { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
    }
  }

  #wallpaperStatus(api) {
    const status = dataProperty(api, 'status');
    try {
      const value = status.call(api);
      if (!value || typeof value !== 'object' || typeof value.applied !== 'boolean') {
        return { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
      }
      const result = {
        applied: value.applied,
        reason: typeof value.reason === 'string' ? value.reason : (value.applied ? '' : 'wallpaper-unsupported'),
        imageDecoded: value.imageDecoded === true,
      };
      for (const field of WALLPAPER_STATUS_FIELDS) {
        const fieldValue = value[field];
        if (typeof fieldValue === 'boolean' || (Number.isSafeInteger(fieldValue) && fieldValue >= 0)
          || (typeof fieldValue === 'string' && field !== 'verificationScope')
          || (Array.isArray(fieldValue) && fieldValue.every((item) => typeof item === 'string'))) {
          result[field] = Array.isArray(fieldValue) ? [...fieldValue] : fieldValue;
        }
      }
      return result;
    } catch {
      return { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
    }
  }

  #refreshWallpaper() {
    const current = wallpaperRecord(this.host);
    if (!current.present) {
      if (this.state.wallpaper.applied) {
        this.state.wallpaper = { applied: false, reason: 'not-installed', imageDecoded: false };
      }
      return;
    }
    if (!current.supported || current.api !== this.wallpaperAPI) {
      this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
      return;
    }
    this.state.wallpaper = this.#wallpaperStatus(current.api);
  }

  #fail(reason, runId = this.state.runId) {
    if (this.disposed || runId !== this.state.runId || ['complete', 'failed', 'timeout', 'disposed'].includes(this.state.phase)) return;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    this.state.phase = 'failed';
    this.state.overlay = false;
    this.state.reason = reason;
    this.host.removeEventListener('message', this.onMessage);
    this.#stopFrame();
  }

  expire(runId) {
    if (this.disposed || runId !== this.state.runId || !['loading', 'playing'].includes(this.state.phase)) return false;
    this.watchdog = null;
    this.#disconnectBodyObserver();
    this.state.phase = 'timeout';
    this.state.overlay = false;
    this.state.reason = 'overlay-timeout';
    this.host.removeEventListener('message', this.onMessage);
    this.#stopFrame();
    return true;
  }

  #clearWatchdog() {
    if (this.watchdog === null) return;
    this.host.clearTimeout(this.watchdog);
    this.watchdog = null;
  }

  #disconnectBodyObserver() {
    const observer = this.bodyObserver;
    this.bodyObserver = null;
    try { observer?.disconnect(); } catch {}
  }

  #restoreFocus(frame) {
    const ownedFocus = this.document?.activeElement === frame.element;
    const pageBlurred = typeof this.document?.hasFocus === 'function' && !this.document.hasFocus();
    if ((ownedFocus || pageBlurred) && this.savedFocus?.isConnected && typeof this.savedFocus.focus === 'function') {
      try { this.savedFocus.focus(); } catch {}
    }
  }

  #stopFrame() {
    const frame = this.frame;
    const handle = this.frameHandle;
    this.frame = null;
    this.frameHandle = null;
    if (!frame) return;
    this.#restoreFocus(frame);
    try { frame.contentWindow.removeEventListener('keydown', this.onFrameKeydown); } catch {}
    try { handle?.dispose?.(); } catch {}
    try { frame.remove(); } catch {}
  }

  #invokeFrameSettings() {
    const openSettings = dataProperty(this.frameHandle, 'openSettings');
    if (this.disposed || this.state.phase !== 'playing' || !this.state.ready || typeof openSettings !== 'function') return false;
    try {
      const result = openSettings.call(this.frameHandle);
      if (result && typeof result.then === 'function') Promise.resolve(result).catch(() => {});
      return result !== false;
    } catch {
      return false;
    }
  }

  #openSettings() {
    if (this.disposed || !this.installed) return false;
    if (this.state.phase === 'complete') return this.#beginRun('settings');
    if (this.state.phase === 'settings') return false;
    if (this.state.phase === 'playing') return this.#invokeFrameSettings();
    return false;
  }

  #status() {
    this.#refreshWallpaper();
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

  #disposeWallpaper() {
    const current = wallpaperRecord(this.host);
    if (!current.supported || !this.wallpaperAPI || current.api !== this.wallpaperAPI) return;
    try { dataProperty(current.api, 'dispose').call(current.api); } catch {}
    this.wallpaperAPI = null;
  }

  #dispose() {
    if (this.disposed) return { disposed: true };
    this.disposed = true;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    this.state.phase = 'disposed';
    this.state.overlay = false;
    this.host.removeEventListener('message', this.onMessage);
    this.host.removeEventListener('keydown', this.onParentKeydown);
    this.#stopFrame();
    this.#disposeWallpaper();
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
  if (typeof payload !== 'function') return { installed: false, alreadyActive: false, reason: ASSET_REASON };
  const controller = new PageController(host, payload);
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
