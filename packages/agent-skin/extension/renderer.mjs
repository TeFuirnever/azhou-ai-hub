const GLOBAL_NAME = '__azhouStartup';
const WALLPAPER_GLOBAL = '__azhouWallpaper';
const OWNER = 'azhou-codex-startup';
const VERSION = 1;
const LEGACY_WALLPAPER_OWNER = 'azhou.codex-startup-animation';
const WALLPAPER_VERSIONS = new Set(['0.7.1', '0.8.0', '0.9.0']);
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
const WALLPAPER_FAILURE_STAGES = Object.freeze({
  'shell-timeout': 'shell',
  'shell-unsupported': 'shell',
  'invalid-local-payload': 'input',
  'invalid-local-image': 'input',
  'image-decode-failed': 'decode',
  'image-decode-timeout': 'decode',
  'unsupported-shell-no-surfaces': 'surfaces',
  'page-changed-during-decode': 'page',
  'styles-not-effective': 'styles',
  'styles-not-effective-after-replacement': 'styles',
  'namespace-conflict': 'namespace',
  'namespace-changed-during-decode': 'namespace',
  'style-id-conflict': 'style',
  'style-id-conflict-after-decode': 'style',
  'apply-unavailable': 'apply',
  'apply-failed': 'apply',
  'retry-timeout': 'apply',
});
const WALLPAPER_RETRY_TIMEOUT_MS = 10_000;
let nextRunId = 1;

function dataProperty(object, name) {
  if (!object || (typeof object !== 'object' && typeof object !== 'function')) return undefined;
  const descriptor = Object.getOwnPropertyDescriptor(object, name);
  return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
}

function wallpaperFailure(value) {
  try {
    const raw = dataProperty(value, 'failureCode') ?? dataProperty(value, 'code');
    if (typeof raw !== 'string' || !Object.hasOwn(WALLPAPER_FAILURE_STAGES, raw)) return null;
    return { failureStage: WALLPAPER_FAILURE_STAGES[raw], failureCode: raw };
  } catch {
    return null;
  }
}

function wallpaperReason(value, fallback = 'wallpaper-unsupported') {
  try {
    const reason = dataProperty(value, 'reason');
    return ['wallpaper-unsupported', 'disabled', 'operation-cancelled', 'owner-conflict', 'not-installed'].includes(reason)
      ? reason : fallback;
  } catch {
    return fallback;
  }
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
    && WALLPAPER_VERSIONS.has(dataProperty(api, 'version'))
    && typeof dataProperty(api, 'status') === 'function'
    && typeof dataProperty(api, 'dispose') === 'function';
  return { present: true, supported, api: supported ? api : null };
}

// Official settings are reflected on the host root. Read only these attributes
// and color tokens; never read or maintain a competing preference store.
function hostAppearance(host) {
  const root = host.document.documentElement;
  const locale = /^zh(?:-|$)/i.test(root.lang || host.navigator?.language || 'zh-CN') ? 'zh-CN' : 'en';
  let style;
  try { style = host.getComputedStyle?.(root); } catch {}
  const theme = root.dataset?.theme === 'dark' || (!root.dataset?.theme && style?.colorScheme === 'dark')
    ? 'dark' : 'light';
  const colors = {};
  for (const [key, tokens] of Object.entries({
    surface: ['--app-color-background-surface', '--color-surface'],
    text: ['--app-color-text-foreground', '--color-text', '--color-text-primary'],
    muted: ['--app-color-text-foreground-secondary', '--color-text-secondary'],
    border: ['--app-color-border', '--color-border'],
  })) {
    const value = tokens.map(token => style?.getPropertyValue?.(token)?.trim()).find(Boolean);
    if (value) colors[key] = value;
  }
  const reducedMotion = typeof host.matchMedia === 'function'
    ? host.matchMedia('(prefers-reduced-motion: reduce)').matches : undefined;
  return Object.freeze({ locale, theme, colors: Object.freeze(colors), reducedMotion });
}

function appearanceText(factory, appearance, themeConfig) {
  if (typeof factory === 'function') return factory({ locale: appearance.locale, themeConfig });
  // Minimal payloads remain supported without a localization factory.
  return { t: key => ({ characterName: 'Azhou', openAppearance: 'Open appearance settings',
    appearanceLabel: 'Azhou appearance settings', overlayLabel: 'Azhou startup animation' })[key] };
}

function mountAppearanceEntry(document, openSettings, assets, factory, appearance, host) {
  const element = document.createElement('div');
  element.setAttribute('data-agent-skin-entry', 'appearance');
  element.style.cssText = 'all:initial;position:fixed;left:10px;bottom:72px;z-index:2147483646;display:none';
  const shadow = element.attachShadow({ mode: 'open' });
  const button = document.createElement('button');
  // Match the animation's CSSOM path: a host may reject inline <style> blocks.
  // System colors keep this owned control readable in either color scheme.
  button.style.cssText = 'all:initial;visibility:inherit;box-sizing:border-box;display:flex;align-items:center;gap:7px;cursor:pointer;min-height:44px;padding:5px 9px 5px 5px;border:1px solid var(--app-color-border,var(--color-border,transparent));border-radius:14px;background:var(--app-color-background-surface,var(--color-surface,Canvas));color:var(--app-color-text-foreground,var(--color-text,CanvasText));box-shadow:0 2px 8px #0002;font:12px/18px -apple-system,BlinkMacSystemFont,sans-serif;white-space:nowrap;outline:2px solid transparent;outline-offset:3px';
  button.type = 'button';
  button.style.minWidth = '44px';
  const avatar = assets?.entryAvatar;
  let hasAvatar = false;
  if (typeof avatar === 'string' && avatar.length <= 2 * 1024 * 1024
    && /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(avatar)) {
    const image = document.createElement('img');
    image.src = avatar;
    image.setAttribute('alt', '');
    image.style.cssText = 'display:block;width:32px;height:32px;border-radius:10px;object-fit:cover;flex:none';
    button.appendChild(image);
    hasAvatar = true;
  }
  const label = document.createElement('span');
  button.appendChild(label);
  let position = () => {};
  const setAppearance = value => {
    const text = appearanceText(factory, value, assets?.themeConfig);
    label.textContent = text.t('characterName');
    button.title = text.t('openAppearance');
    button.setAttribute('aria-label', text.t('appearanceLabel'));
    button.style.colorScheme = value.theme;
    element.setAttribute('lang', value.locale);
    position();
  };
  setAppearance(appearance);
  button.setAttribute('aria-haspopup', 'dialog');
  const onFocus = () => { button.style.outlineColor = '#9670bb'; };
  const onBlur = () => { button.style.outlineColor = 'transparent'; };
  button.addEventListener('click', openSettings);
  button.addEventListener('focus', onFocus);
  button.addEventListener('blur', onBlur);
  shadow.appendChild(button);
  element.style.display = 'none';
  document.documentElement.appendChild(element);
  const page = document.documentElement.ownerDocument ?? document;
  let observer, pending, relevantControls = [];
  position = () => {
    if (element.style.display === 'none' || typeof page.querySelectorAll !== 'function'
      || typeof element.getBoundingClientRect !== 'function') return;
    label.style.display = '';
    let rect = element.getBoundingClientRect();
    const height = document.documentElement.clientHeight;
    const width = document.documentElement.clientWidth;
    if (!rect.width || !rect.height || !height) return;
    const controls = Array.from(page.querySelectorAll('button, a[href], [role="button"], input, textarea, select'))
      .map(control => ({ control, bounds: control.getBoundingClientRect() }))
      .filter(({ bounds }) => bounds.width > 0 && bounds.height > 0 && bounds.top < height && bounds.bottom > 0);
    relevantControls = controls.filter(({ bounds }) => bounds.left < 10 + rect.width
      || bounds.right > width - rect.width - 10).map(({ control }) => control);
    const findPosition = left => {
      const bounds = controls.map(item => item.bounds).filter(other => other.left < left + rect.width && other.right > left);
      const desired = height - 72 - rect.height;
      const candidates = [desired, ...bounds.flatMap(other => [other.top - rect.height - 8, other.bottom + 8])];
      const available = candidates.filter(top => top >= 8 && top + rect.height <= height - 8
        && bounds.every(other => top + rect.height + 8 <= other.top || top >= other.bottom + 8));
      if (!available.length) return null;
      return { left, top: available.reduce((best, candidate) =>
        Math.abs(candidate - desired) < Math.abs(best - desired) ? candidate : best) };
    };
    let placement = findPosition(10);
    if (!placement) {
      label.style.display = hasAvatar ? 'none' : '';
      rect = element.getBoundingClientRect();
      const left = Math.max(10, width - rect.width - 10);
      const columns = [left, ...controls.flatMap(({ bounds }) => [bounds.right + 8, bounds.left - rect.width - 8])];
      for (const column of columns) {
        if (column < 10 || column + rect.width > width - 10) continue;
        placement = findPosition(column);
        if (placement) break;
      }
    }
    element.style.visibility = 'visible';
    if (!placement) return;
    element.style.left = `${placement.left}px`;
    const bottom = `${height - placement.top - rect.height}px`;
    if (element.style.bottom !== bottom) element.style.bottom = bottom;
  };
  const schedule = () => {
    if (pending !== undefined || element.style.display === 'none') return;
    pending = host.setTimeout(() => { pending = undefined; position(); }, 80);
  };
  const touchesEntryColumn = node => {
    if (typeof node?.getBoundingClientRect !== 'function') return false;
    const target = node.getBoundingClientRect(), entry = element.getBoundingClientRect();
    return target.width > 0 && ((target.left < entry.right && target.right > entry.left)
      || (target.left < 10 + entry.width && target.right > 10));
  };
  const onScroll = event => { if (event.target === page || touchesEntryColumn(event.target)) schedule(); };
  if (typeof page.querySelectorAll === 'function' && typeof host.MutationObserver === 'function') {
    observer = new host.MutationObserver(records => {
      if (records.some(record => record.target !== element && (touchesEntryColumn(record.target)
        || relevantControls.some(control => record.target === control || record.target.contains?.(control))))) schedule();
    });
    observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true,
      attributeFilter: ['class', 'style', 'hidden', 'aria-hidden'] });
    host.addEventListener?.('resize', schedule);
    host.addEventListener?.('scroll', onScroll, true);
  }
  return {
    element, button, setAppearance,
    update(visible) { element.style.display = visible ? 'block' : 'none'; button.disabled = !visible; if (visible) position(); },
    remove() {
      observer?.disconnect();
      if (pending !== undefined) host.clearTimeout(pending);
      host.removeEventListener?.('resize', schedule);
      host.removeEventListener?.('scroll', onScroll, true);
      button.removeEventListener('click', openSettings);
      button.removeEventListener('focus', onFocus);
      button.removeEventListener('blur', onBlur);
      element.remove();
    },
  };
}

function mountOverlay(host, payload, runId, intent, assets, receive, settingsCommitted, appearance) {
  const document = host.document;
  if (!document?.documentElement || typeof document.createElement !== 'function' || !document.body) {
    throw new TypeError('startup overlay host is unavailable');
  }
  const frame = document.createElement('iframe');
  const text = appearanceText(dataProperty(payload, 'createLocalization'), appearance);
  frame.setAttribute('title', text.t('overlayLabel'));
  frame.setAttribute('aria-label', text.t('overlayLabel'));
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
  const frameSpec = Object.freeze({ runId, intent, protocolVersion: 1, assets, appearance,
    settingsCommitted: settingsCommitted === true });
  // Preserve the parent handler result for committed settings saves: the child
  // uses it to report wallpaper-only failure after the IndexedDB commit. The
  // shared handler still enforces the current frame source and runId.
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
        undefined, SEND, frameSpec, dataProperty(payload, 'createImageSettings'), dataProperty(payload, 'createLocalization'),
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
    this.wallpaperGeneration = 0;
    this.wallpaperRequest = null;
    this.wallpaperDisabled = false;
    this.wallpaperRetryPromise = null;
    this.wallpaperRetryCancel = null;
    this.installed = false;
    this.disposed = false;
    this.watchdog = null;
    this.bodyObserver = null;
    this.appearanceEntry = null;
    this.appearanceObserver = null;
    this.motionQuery = null;
    this.onMotionChange = () => this.#updateAppearance();
    this.appearance = hostAppearance(host);
    this.savedFocus = this.document?.activeElement ?? null;
    this.intent = 'play';
    this.settingsCommitPending = false;
    this.frameSettingsCommitted = false;
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
    this.api = Object.freeze({
      owner: OWNER,
      version: VERSION,
      install: (nextPayload) => this.#install(nextPayload),
      status: () => this.#status(),
      openSettings: () => this.#openSettings(),
      retryWallpaper: () => this.#retryWallpaper(),
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
    this.#observeAppearance();
    if (!this.#beginRun('play')) {
      this.installed = false;
      return { installed: false, alreadyActive: false, reason: PAGE_REASON };
    }
    return { installed: true, alreadyActive: false };
  }

  #beginRun(intent) {
    if (this.disposed) return false;
    this.wallpaperRetryCancel?.();
    this.wallpaperGeneration += 1;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    const focused = this.document?.activeElement === this.appearanceEntry?.element
      ? this.appearanceEntry.button : this.document?.activeElement;
    if (focused !== this.frame?.element && focused?.isConnected && typeof focused.focus === 'function') {
      this.savedFocus = focused;
    }
    this.#stopFrame();
    this.intent = intent;
    this.state.phase = 'loading';
    this.state.runId = nextRunId++;
    this.state.ready = false;
    this.state.completed = false;
    this.state.overlay = true;
    this.state.reason = '';
    this.state.completion = null;
    this.appearanceEntry?.update(false);
    const settingsCommitted = intent === 'play' && this.settingsCommitPending;
    this.settingsCommitPending = false;
    this.frameSettingsCommitted = settingsCommitted;
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
      if (!this.appearanceEntry) this.appearanceEntry = mountAppearanceEntry(this.document, () => this.#openSettings(),
        this.assets, dataProperty(this.payload, 'createLocalization'), this.appearance, this.host);
      this.frame = mountOverlay(
        this.host, this.payload, runId, this.intent, this.assets, this.onMessage, this.frameSettingsCommitted, this.appearance,
      );
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
    if (handle && typeof handle === 'object') {
      this.frameHandle = handle;
      this.#updateAppearance();
    }
  }

  #updateAppearance() {
    if (this.disposed) return;
    this.appearance = hostAppearance(this.host);
    this.appearanceEntry?.setAppearance(this.appearance);
    const text = appearanceText(dataProperty(this.payload, 'createLocalization'), this.appearance);
    this.frame?.element.setAttribute('title', text.t('overlayLabel'));
    this.frame?.element.setAttribute('aria-label', text.t('overlayLabel'));
    const update = dataProperty(this.frameHandle, 'updateAppearance');
    if (typeof update === 'function') {
      try { update.call(this.frameHandle, this.appearance); } catch {}
    }
  }

  #observeAppearance() {
    if (typeof this.host.matchMedia === 'function') {
      this.motionQuery = this.host.matchMedia('(prefers-reduced-motion: reduce)');
      this.motionQuery.addEventListener('change', this.onMotionChange);
    }
    const root = this.document.documentElement;
    if (typeof root.getAttribute !== 'function' || typeof this.host.MutationObserver !== 'function') return;
    this.appearanceObserver = new this.host.MutationObserver(() => this.#updateAppearance());
    this.appearanceObserver.observe(root, {
      attributes: true, attributeFilter: ['lang', 'data-theme', 'class', 'style'],
    });
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
      this.appearanceEntry?.update(true);
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
      if (this.state.ready && this.state.phase === 'settings') {
        this.settingsCommitPending = true;
        this.#beginRun('play');
      }
      return;
    }
    if (message.action === 'background') {
      if (['loading', 'playing', 'settings'].includes(this.state.phase)) {
        return this.#applyWallpaper(message, this.state.runId, this.frame);
      }
      return Promise.resolve({ applied: false, reason: 'operation-cancelled', imageDecoded: false });
    }
    if (message.action === 'restore') this.#dispose();
  }

  #ownsStartupController() {
    const descriptor = Object.getOwnPropertyDescriptor(this.host, GLOBAL_NAME);
    return !!descriptor && Object.hasOwn(descriptor, 'value') && descriptor.value === this.api;
  }

  #isCurrentRetry(runId, generation) {
    return !this.disposed && generation === this.wallpaperGeneration && runId === this.state.runId
      && this.state.phase === 'complete' && this.state.completed && this.#ownsStartupController();
  }

  #setWallpaperFailure(code, reason = 'wallpaper-unsupported', imageDecoded = false) {
    const result = { applied: false, reason, imageDecoded };
    const failure = wallpaperFailure({ failureCode: code });
    if (failure) Object.assign(result, failure);
    this.state.wallpaper = result;
    return { ...result };
  }

  #retryResult(retried, previousFailure, reason) {
    const result = {
      retried,
      wallpaper: { ...this.state.wallpaper },
      previousFailure: previousFailure ? { ...previousFailure } : null,
    };
    if (reason) result.reason = reason;
    return result;
  }

  #previousWallpaperFailure() {
    const current = this.state.wallpaper;
    if (!current.failureCode && current.reason !== 'wallpaper-unsupported') return null;
    const result = { reason: wallpaperReason(current) };
    const failure = wallpaperFailure(current);
    if (failure) Object.assign(result, failure);
    return result;
  }

  #retryWallpaper() {
    const previousFailure = this.#previousWallpaperFailure();
    if (this.disposed) return Promise.resolve(this.#retryResult(false, previousFailure, 'disposed'));
    if (this.wallpaperRetryPromise) return this.wallpaperRetryPromise;
    if (!this.#ownsStartupController()) return Promise.resolve(this.#retryResult(false, previousFailure, 'unknown-owner'));
    if (this.state.phase !== 'complete' || !this.state.completed) {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'busy'));
    }
    if (this.wallpaperDisabled || this.state.wallpaper.reason === 'disabled') {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'disabled'));
    }
    if (!this.wallpaperRequest) return Promise.resolve(this.#retryResult(false, previousFailure, 'no-request'));

    const current = wallpaperRecord(this.host);
    if ((current.present && (!current.supported || current.api !== this.wallpaperAPI))
      || (!current.present && this.wallpaperAPI)) {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'unknown-owner'));
    }
    this.#refreshWallpaper();
    if (this.state.wallpaper.applied) {
      return Promise.resolve(this.#retryResult(false, null, 'already-applied'));
    }

    const runId = this.state.runId;
    const request = { ...this.wallpaperRequest };
    let operation;
    try {
      operation = this.#applyWallpaper(request, runId, null, true);
    } catch {
      operation = Promise.resolve(this.#setWallpaperFailure('apply-failed'));
    }
    const generation = this.wallpaperGeneration;
    let timer = null;
    const timeout = new Promise(resolve => {
      timer = this.host.setTimeout(() => resolve({ timedOut: true }), WALLPAPER_RETRY_TIMEOUT_MS);
    });
    let cancelRetry;
    const cancellation = new Promise(resolve => {
      cancelRetry = () => resolve({ cancelled: true });
    });
    const work = Promise.resolve(operation).then(
      wallpaper => ({ wallpaper }),
      () => ({ wallpaper: this.#isCurrentRetry(runId, generation)
        ? this.#setWallpaperFailure('apply-failed') : { ...this.state.wallpaper } }),
    );
    const bounded = Promise.race([work, timeout, cancellation]).then(result => {
      if (result.cancelled) return this.#retryResult(false, previousFailure, 'operation-cancelled');
      if (result.timedOut) {
        if (!this.#isCurrentRetry(runId, generation)) {
          return this.#retryResult(false, previousFailure, 'operation-cancelled');
        }
        this.wallpaperGeneration += 1;
        this.#setWallpaperFailure('retry-timeout');
        return this.#retryResult(true, previousFailure, 'timeout');
      }
      if (!this.#isCurrentRetry(runId, generation)) {
        return this.#retryResult(false, previousFailure, 'operation-cancelled');
      }
      return this.#retryResult(true, previousFailure);
    }).finally(() => {
      if (timer !== null) this.host.clearTimeout(timer);
      if (this.wallpaperRetryCancel === cancelRetry) this.wallpaperRetryCancel = null;
    });
    this.wallpaperRetryPromise = bounded;
    this.wallpaperRetryCancel = cancelRetry;
    const release = () => {
      if (this.wallpaperRetryPromise === bounded) this.wallpaperRetryPromise = null;
    };
    work.then(release, release);
    return bounded;
  }

  async #applyWallpaper(message, runId, frame, retry = false) {
    const generation = ++this.wallpaperGeneration;
    if (typeof message.image !== 'string' || message.image.length > 16 * 1024 * 1024
      || !BACKGROUND_DATA_URL.test(message.image) || !Number.isInteger(message.strength)
      || message.strength < 0 || message.strength > 75) {
      if (!retry) {
        this.wallpaperRequest = null;
        this.wallpaperDisabled = false;
      }
      return this.#setWallpaperFailure('invalid-local-payload');
    }
    if (message.strength === 0) {
      if (!retry) {
        this.wallpaperRequest = null;
        this.wallpaperDisabled = true;
      }
      this.#disposeWallpaper();
      this.state.wallpaper = { applied: false, reason: 'disabled', imageDecoded: false };
      return { ...this.state.wallpaper };
    }
    if (!retry) {
      this.wallpaperRequest = { image: message.image, strength: message.strength };
      this.wallpaperDisabled = false;
    }
    // The workspace may mount after the animation finishes. Natural completion
    // removes only the overlay; skip, replacement and disposal still cancel work.
    const isCurrent = () => generation === this.wallpaperGeneration
      && (retry ? this.#isCurrentRetry(runId, generation)
        : this.#isCurrentFrame(runId, frame) || (!this.disposed && runId === this.state.runId
          && this.state.phase === 'complete' && this.state.completion?.cause === 'natural'
          && this.#ownsStartupController()));
    if (typeof this.wallpaperApply !== 'function') {
      if (isCurrent()) return this.#setWallpaperFailure('apply-unavailable');
      return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
    }
    try {
      const result = await this.wallpaperApply(Object.freeze({ image: message.image, strength: message.strength }), isCurrent);
      if (!isCurrent()) return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
      if (dataProperty(result, 'applied') === false) {
        const reason = wallpaperReason(result);
        const failure = wallpaperFailure(result) ?? wallpaperFailure({ failureCode: 'apply-failed' });
        const current = wallpaperRecord(this.host);
        if (current.present && !current.supported) {
          this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
          return { ...this.state.wallpaper };
        }
        if (current.supported) this.wallpaperAPI = current.api;
        const imageDecoded = dataProperty(result, 'imageDecoded') === true;
        return this.#setWallpaperFailure(failure.failureCode, reason, imageDecoded);
      }
      const current = wallpaperRecord(this.host);
      if (!current.supported) {
        if (current.present) {
          this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
          return { ...this.state.wallpaper };
        }
        return this.#setWallpaperFailure('apply-unavailable');
      }
      this.wallpaperAPI = current.api;
      this.state.wallpaper = this.#wallpaperStatus(current.api);
      if (!this.state.wallpaper.applied && !this.state.wallpaper.reason) {
        this.state.wallpaper.reason = 'wallpaper-unsupported';
      }
    } catch (error) {
      if (isCurrent()) {
        const failure = wallpaperFailure(error) ?? wallpaperFailure({ failureCode: 'apply-failed' });
        return this.#setWallpaperFailure(failure.failureCode);
      }
    }
    return { ...this.state.wallpaper };
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
        reason: value.applied ? '' : wallpaperReason(value),
        imageDecoded: value.imageDecoded === true,
      };
      const failure = !value.applied ? wallpaperFailure(value) : null;
      if (failure) Object.assign(result, failure);
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
    const status = this.#wallpaperStatus(current.api);
    if (!status.failureCode && this.state.wallpaper.failureCode) {
      const previousFailure = wallpaperFailure(this.state.wallpaper);
      if (previousFailure) {
        status.applied = false;
        status.reason = wallpaperReason(this.state.wallpaper);
        status.imageDecoded = this.state.wallpaper.imageDecoded === true;
        Object.assign(status, previousFailure);
      }
    }
    this.state.wallpaper = status;
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
    if (ownedFocus && this.savedFocus?.isConnected && typeof this.savedFocus.focus === 'function') {
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
    this.wallpaperRetryCancel?.();
    this.wallpaperGeneration += 1;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    this.state.phase = 'disposed';
    this.appearanceObserver?.disconnect();
    this.appearanceObserver = null;
    this.motionQuery?.removeEventListener('change', this.onMotionChange);
    this.motionQuery = null;
    this.state.overlay = false;
    this.host.removeEventListener('message', this.onMessage);
    this.#stopFrame();
    this.#disposeWallpaper();
    this.appearanceEntry?.remove();
    this.appearanceEntry = null;
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
