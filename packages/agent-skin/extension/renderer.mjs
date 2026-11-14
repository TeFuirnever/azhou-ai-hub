const GLOBAL_NAME = '__azhouStartup';
const WALLPAPER_GLOBAL = '__azhouWallpaper';
const OWNER = 'azhou-codex-startup';
const DSH_OWNER = 'azhou-dsh-startup';
const DSH_GATE_OWNER = 'azhou-dsh-startup-gate-v1';
const VERSION = 1;
// Frozen installed-state identity inherited from codex-startup-animation;
// installed wallpaper controllers still answer to this exact owner string.
const LEGACY_WALLPAPER_OWNER = 'azhou.codex-startup-animation';
const WALLPAPER_VERSIONS = new Set(['0.7.1', '0.8.0', '0.9.0']);
// The controller-owner allowlist is the anti-hijack boundary for the startup
// global; it stays explicit here and is never derived from adapters.
const CONTROLLER_OWNERS = new Set(['azhou-codex-startup', 'azhou-dsh-startup']);
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
const SETTINGS_SNAPSHOT_MAX_BYTES = 24 * 1024 * 1024 + 4 * 1024;
const SETTINGS_SNAPSHOT_CHUNK_BYTES = 64 * 1024;
const SETTINGS_SNAPSHOT_TIMEOUT_MS = 30_000;
const SETTINGS_SNAPSHOT_RUN_NONCE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
let nextRunId = 1;

function dataProperty(object, name) {
  if (!object || (typeof object !== 'object' && typeof object !== 'function')) return undefined;
  const descriptor = Object.getOwnPropertyDescriptor(object, name);
  return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
}

function encodeBase64(bytes) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let output = '';
  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index];
    const hasSecond = index + 1 < bytes.length;
    const hasThird = index + 2 < bytes.length;
    const second = hasSecond ? bytes[index + 1] : 0;
    const third = hasThird ? bytes[index + 2] : 0;
    output += alphabet[first >> 2]
      + alphabet[((first & 3) << 4) | (second >> 4)]
      + (hasSecond ? alphabet[((second & 15) << 2) | (third >> 6)] : '=')
      + (hasThird ? alphabet[third & 63] : '=');
  }
  return output;
}

function encodedSnapshotByteLength(byteLength) {
  const fullChunks = Math.floor(byteLength / SETTINGS_SNAPSHOT_CHUNK_BYTES);
  const remainder = byteLength % SETTINGS_SNAPSHOT_CHUNK_BYTES;
  const fullChunkLength = 4 * Math.ceil(SETTINGS_SNAPSHOT_CHUNK_BYTES / 3);
  return fullChunks * fullChunkLength + (remainder ? 4 * Math.ceil(remainder / 3) : 0);
}

function monotonicNow(host) {
  const performance = host?.performance ?? globalThis.performance;
  if (!performance || typeof performance.now !== 'function') return null;
  try {
    const value = performance.now.call(performance);
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
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

function controllerMetadataSnapshot(source) {
  const values = Object.fromEntries(['controllerInstanceID', 'createdByOperationID', 'payloadSHA256', 'documentToken']
    .map(key => [key, dataProperty(source, key)]));
  const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
  if (typeof values.controllerInstanceID !== 'string' || values.controllerInstanceID.length !== 36 || !uuid.test(values.controllerInstanceID)
      || typeof values.createdByOperationID !== 'string' || values.createdByOperationID.length !== 36 || !uuid.test(values.createdByOperationID)
      || typeof values.payloadSHA256 !== 'string' || values.payloadSHA256.length !== 64 || !/^[a-f0-9]{64}$/.test(values.payloadSHA256)
      || typeof values.documentToken !== 'string' || !values.documentToken || values.documentToken.length > 256) return null;
  return Object.freeze(values);
}

function existingController(host, owner = OWNER) {
  const descriptor = Object.getOwnPropertyDescriptor(host, GLOBAL_NAME);
  if (!descriptor) return { present: false };
  if (!Object.hasOwn(descriptor, 'value') || !descriptor.value || typeof descriptor.value !== 'object') {
    return { present: true, owned: false };
  }
  const api = descriptor.value;
  return {
    present: true,
    owned: dataProperty(api, 'owner') === owner
      && dataProperty(api, 'version') === VERSION
      && typeof dataProperty(api, 'status') === 'function'
      && typeof dataProperty(api, 'openSettings') === 'function'
      && typeof dataProperty(api, 'dispose') === 'function',
  };
}

function dshStartupGate(host) {
  const gate = dataProperty(host, '__azhouDshStartupGate');
  return dataProperty(gate, 'owner') === DSH_GATE_OWNER
    && ['claim', 'ready', 'release', 'onExpire'].every(name => typeof dataProperty(gate, name) === 'function')
    ? gate : null;
}

function wallpaperRecord(host, owner = LEGACY_WALLPAPER_OWNER) {
  const descriptor = Object.getOwnPropertyDescriptor(host, WALLPAPER_GLOBAL);
  if (!descriptor) return { present: false, supported: false, api: null };
  if (!Object.hasOwn(descriptor, 'value') || !descriptor.value || typeof descriptor.value !== 'object') {
    return { present: true, supported: false, api: null };
  }
  const api = descriptor.value;
  const supported = dataProperty(api, 'owner') === owner
    && WALLPAPER_VERSIONS.has(dataProperty(api, 'version'))
    && typeof dataProperty(api, 'status') === 'function'
    && typeof dataProperty(api, 'dispose') === 'function';
  return { present: true, supported, api: supported ? api : null };
}

// Shared panel construction for the startup overlay and the settings-section
// embed: one frame document, one environment binding, one message channel.
// Only the mounting parent, the frame styling and the accessibility label
// differ; the overlay's full-viewport behavior is pinned by its tests.
function buildPanel(host, payload, runId, intent, assets, receive, appearance, pageAdapter,
  controllerMetadata, parent, cssText, labelKey = 'overlayLabel', externalStartGate = false) {
  const document = host.document;
  if (!document?.documentElement || typeof document.createElement !== 'function' || !document.body) {
    throw new TypeError('startup overlay host is unavailable');
  }
  const frame = document.createElement('iframe');
  const text = pageAdapter.appearanceText(dataProperty(payload, 'createLocalization'), appearance);
  frame.setAttribute('title', text.t(labelKey));
  frame.setAttribute('aria-label', text.t(labelKey));
  frame.style.cssText = cssText;
  frame.src = 'about:blank';
  if (controllerMetadata) frame.setAttribute('data-agent-skin-controller-instance', controllerMetadata.controllerInstanceID);
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
    ...pageAdapter.settingsEnvironment(contentWindow),
    Image: contentWindow.Image,
    Path2D: contentWindow.Path2D,
    URL: contentWindow.URL ?? URL,
    requestAnimationFrame: bind('requestAnimationFrame'),
    cancelAnimationFrame: bind('cancelAnimationFrame'),
    setTimeout: bind('setTimeout'),
    clearTimeout: bind('clearTimeout'),
  });
  const settingsFactory = dataProperty(payload, 'createImageSettings');
  // Preserve the exact legacy factory when no host namespace was supplied.
  const createSettings = environment.settingsNamespace === undefined || typeof settingsFactory !== 'function'
    ? settingsFactory : input => settingsFactory({ ...input, settingsNamespace: environment.settingsNamespace });
  const frameSpec = Object.freeze({ runId, intent, protocolVersion: 1, assets, appearance, externalStartGate });
  // Preserve the result so the settings panel can report wallpaper failures.
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
        undefined, SEND, frameSpec, createSettings, dataProperty(payload, 'createLocalization'),
      );
    },
    remove: () => frame.remove(),
  };
}

function mountOverlay(host, payload, runId, intent, assets, receive, appearance, pageAdapter,
  controllerMetadata, externalStartGate = false) {
  const parent = typeof host.document?.body?.appendChild === 'function'
    ? host.document.body : host.document?.documentElement;
  const zIndex = externalStartGate ? '2147483646' : '2147483647';
  return buildPanel(host, payload, runId, intent, assets, receive, appearance, pageAdapter, controllerMetadata,
    parent, `position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:${zIndex};background:transparent`,
    'overlayLabel', externalStartGate);
}

// Settings-section embed: the same panel document placed inside a host-provided
// element. The host modal owns Esc, the backdrop and the viewport, so the frame
// only fills its container — no fixed positioning, no takeover of its own.
function mountSettingsPanel(host, payload, runId, assets, receive, appearance, pageAdapter,
  controllerMetadata, target) {
  return buildPanel(host, payload, runId, 'settings', assets, receive, appearance, pageAdapter, controllerMetadata,
    target, 'display:block;width:100%;height:100%;border:0;background:transparent', 'appearanceLabel');
}

function panelDisconnected({ element, contentWindow }) {
  return element.isConnected === false || element.contentWindow !== contentWindow;
}

function observePanelConnection(host, { element }, checkConnection) {
  if (!element.ownerDocument || typeof host.MutationObserver !== 'function') return null;
  const observer = new host.MutationObserver(checkConnection);
  // Track the panel's ancestors without observing unrelated subtree changes.
  for (let parent = element.parentNode; parent; parent = parent.parentNode) {
    observer.observe(parent, { childList: true });
  }
  return observer;
}

// The settings embed is only exercised by adapter-driven hosts whose adapter
// declares the atomic wallpaper ports group; adapters without it (Codex) keep
// the overlay as their only settings UX and the method stays inert.
function settingsEmbedAdmitted(pageAdapter) {
  const ports = dataProperty(pageAdapter, 'wallpaper');
  return !!ports && typeof ports === 'object'
    && typeof dataProperty(ports, 'validPage') === 'function'
    && typeof dataProperty(ports, 'surfaces') === 'function';
}

class PageController {
  constructor(host, payload, pageAdapter, owner, metadata, identification, playbackOwner) {
    this.owner = owner;
    this.playbackOwner = playbackOwner;
    this.startupGate = null;
    this.startupGateUnsubscribe = null;
    this.wallpaperOwner = dataProperty(dataProperty(pageAdapter, 'controllerWallpaper'), 'owner')
      ?? LEGACY_WALLPAPER_OWNER;
    this.metadata = metadata;
    this.host = host;
    this.document = host.document;
    this.payload = payload;
    this.pageAdapter = pageAdapter;
    this.documentToken = dataProperty(identification, 'documentToken');
    this.assets = dataProperty(payload, 'assets') ?? null;
    this.wallpaperApply = dataProperty(payload, 'applyWallpaper');
    this.frame = null;
    this.frameHandle = null;
    this.frameObserver = null;
    this.wallpaperAPI = null;
    this.wallpaperGeneration = 0;
    this.wallpaperRequest = null;
    this.wallpaperDisabled = false;
    this.wallpaperRetryPromise = null;
    this.wallpaperRetryCancel = null;
    this.startupWallpaperFailure = null;
    this.startupWallpaperNoticeDismissed = false;
    this.installed = false;
    this.disposed = false;
    this.watchdog = null;
    this.bodyObserver = null;
    this.modalIsolation = null;
    this.appearanceEntry = null;
    this.appearanceObserver = null;
    this.settingsEmbedAdmitted = settingsEmbedAdmitted(pageAdapter);
    this.settingsEmbeds = new Set();
    this.settingsSnapshot = null;
    this.settingsSnapshotRunID = 0;
    this.dshWallpaperPreparation = null;
    this.pageHidden = false;
    this.motionQuery = null;
    this.onMotionChange = () => this.#updateAppearance();
    this.onPageHide = () => {
      this.pageHidden = true;
      this.#clearSettingsSnapshot();
      if (this.playbackOwner === 'dsh-gated') this.#cancelDSHWallpaperPreparation();
    };
    this.onPageShow = () => { this.pageHidden = false; };
    this.appearance = this.pageAdapter.observeAppearance(host);
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
    this.api = Object.freeze({
      owner: this.owner,
      version: VERSION,
      ...this.metadata,
      install: (nextPayload) => this.#install(nextPayload),
      status: () => this.#status(),
      beginSettingsSnapshot: (request) => this.#beginSettingsSnapshot(request),
      prepareWorkspace: (request) => this.#prepareWorkspace(request),
      cancelWorkspace: (request) => this.#cancelWorkspace(request),
      readSettingsSnapshotChunk: (request) => this.#readSettingsSnapshotChunk(request),
      disposeSettingsSnapshot: (request) => this.#disposeSettingsSnapshot(request),
      openSettings: () => this.#openSettings(),
      mountSettings: (target, options) => this.#mountSettings(target, options),
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
    const wallpaper = wallpaperRecord(this.host, this.wallpaperOwner);
    if (wallpaper.present && !wallpaper.supported) {
      return { installed: false, alreadyActive: false, reason: 'owner-conflict' };
    }
    this.wallpaperAPI = wallpaper.api;
    if (this.playbackOwner === 'dsh-gated') this.startupGate = dshStartupGate(this.host);
    this.installed = true;
    this.host.addEventListener('pagehide', this.onPageHide);
    this.host.addEventListener('pageshow', this.onPageShow);
    this.#observeAppearance();
    if (!this.#beginRun(['native', 'dsh-gated'].includes(this.playbackOwner) ? 'prepare' : 'play')) {
      this.installed = false;
      return { installed: false, alreadyActive: false, reason: PAGE_REASON };
    }
    let claimed = false;
    try {
      if (this.playbackOwner === 'dsh-gated') {
        claimed = dataProperty(this.startupGate, 'claim')?.call(this.startupGate) === true;
      }
    } catch {}
    if (claimed) {
      if (this.#beginRun('play')) this.#watchStartupGateExpiry(this.state.runId);
    } else if (this.playbackOwner === 'dsh-gated') this.#prepareDSHWallpaper();
    return { installed: true, alreadyActive: false };
  }

  #watchStartupGateExpiry(runId) {
    const onExpire = dataProperty(this.startupGate, 'onExpire');
    if (typeof onExpire !== 'function') return false;
    const handleExpire = () => {
      if (this.disposed || runId !== this.state.runId || !['loading', 'playing'].includes(this.state.phase)) return;
      this.#fail('startup-gate-expired', runId);
    };
    let unsubscribe;
    try { unsubscribe = onExpire.call(this.startupGate, handleExpire); } catch {}
    if (typeof unsubscribe === 'function') this.startupGateUnsubscribe = unsubscribe;
    if (this.disposed || runId !== this.state.runId || !['loading', 'playing'].includes(this.state.phase)) {
      this.#unsubscribeStartupGateExpiry();
    }
    return typeof unsubscribe === 'function';
  }

  #beginRun(intent) {
    if (this.disposed) return false;
    this.#clearSettingsSnapshot();
    this.nativeWorkspace?.cancel?.();
    this.nativeWorkspace = null;
    this.#cancelDSHWallpaperPreparation();
    this.settingsSnapshotRunID = 0;
    if (intent === 'play') {
      this.startupWallpaperFailure = null;
      this.startupWallpaperNoticeDismissed = false;
    }
    this.wallpaperRetryCancel?.();
    this.wallpaperGeneration += 1;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    const focused = this.document?.activeElement === this.appearanceEntry?.element
      ? this.appearanceEntry.button : this.document?.activeElement;
    this.#rememberFocus(focused);
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
    if (intent === 'settings') this.#isolateHostPage();
    const runId = this.state.runId;
    if (intent === 'prepare') {
      this.state.phase = 'prepared';
      this.state.overlay = false;
      if (!this.document?.body) {
        this.#fail(PAGE_REASON, runId);
        return false;
      }
      try {
        if (!this.appearanceEntry) {
          this.appearanceEntry = this.pageAdapter.mountEntry(this.document, () => this.#openSettings(),
            this.assets, dataProperty(this.payload, 'createLocalization'), this.appearance, this.host,
            () => this.#retryWallpaper(), () => { this.startupWallpaperNoticeDismissed = true; });
        }
        const entryElement = dataProperty(this.appearanceEntry, 'element');
        if (!entryElement && this.playbackOwner !== 'dsh-gated') throw new TypeError('appearance entry unavailable');
        if (this.metadata && typeof entryElement.setAttribute === 'function') {
          entryElement.setAttribute('data-agent-skin-controller-instance', this.metadata.controllerInstanceID);
        }
        const revealEntry = dataProperty(this.appearanceEntry, 'update');
        if (typeof revealEntry === 'function') revealEntry.call(this.appearanceEntry, true);
        this.#refreshWallpaper();
        return true;
      } catch {
        this.#fail(ASSET_REASON, runId);
        return false;
      }
    }
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
      if (!this.appearanceEntry) this.appearanceEntry = this.pageAdapter.mountEntry(this.document, () => this.#openSettings(),
        this.assets, dataProperty(this.payload, 'createLocalization'), this.appearance, this.host,
        () => this.#retryWallpaper(), () => { this.startupWallpaperNoticeDismissed = true; });
      const entryElement = dataProperty(this.appearanceEntry, 'element');
      if (this.metadata && typeof entryElement?.setAttribute === 'function') {
        entryElement.setAttribute('data-agent-skin-controller-instance', this.metadata.controllerInstanceID);
      }
      this.frame = mountOverlay(
        this.host, this.payload, runId, this.intent, this.assets, this.onMessage, this.appearance,
        this.pageAdapter, this.metadata, this.playbackOwner === 'dsh-gated' && this.intent === 'play',
      );
      this.frameObserver = observePanelConnection(this.host, this.frame, () => this.#checkFrameConnection());
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
    const appearance = this.pageAdapter.observeAppearance(this.host);
    const surfaceChanged = appearance.colors.surface !== this.appearance?.colors.surface;
    this.appearance = appearance;
    const updateWallpaperSurface = dataProperty(this.wallpaperAPI, 'updateSurface');
    if (surfaceChanged && typeof updateWallpaperSurface === 'function') {
      try { updateWallpaperSurface.call(this.wallpaperAPI, this.appearance.colors.surface); } catch {}
    }
    this.appearanceEntry?.setAppearance(this.appearance);
    const text = this.pageAdapter.appearanceText(dataProperty(this.payload, 'createLocalization'), this.appearance);
    this.frame?.element.setAttribute('title', text.t('overlayLabel'));
    this.frame?.element.setAttribute('aria-label', text.t('overlayLabel'));
    const update = dataProperty(this.frameHandle, 'updateAppearance');
    if (typeof update === 'function') {
      try { update.call(this.frameHandle, this.appearance); } catch {}
    }
    for (const mount of this.settingsEmbeds) {
      mount.frame?.element.setAttribute('title', text.t('appearanceLabel'));
      mount.frame?.element.setAttribute('aria-label', text.t('appearanceLabel'));
      const embedUpdate = dataProperty(mount.handle, 'updateAppearance');
      if (typeof embedUpdate === 'function') {
        try { embedUpdate.call(mount.handle, this.appearance); } catch {}
      }
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

  #snapshotFailure(reason) {
    return { ok: false, reason };
  }

  #snapshotPageIsCurrent(runId, allowTerminalRecovery = false) {
    if (this.disposed || !this.installed || this.pageHidden || runId !== this.state.runId
      || (!['loading', 'playing', 'settings', 'complete', 'prepared'].includes(this.state.phase)
        && !(allowTerminalRecovery && ['failed', 'timeout'].includes(this.state.phase)))
      || this.host.document !== this.document || !this.#ownsStartupController()) return false;
    const identify = dataProperty(this.pageAdapter, 'identify');
    if (typeof identify !== 'function') return false;
    try {
      const identification = identify.call(this.pageAdapter, this.host);
      return dataProperty(identification, 'kind') === 'matched'
        && dataProperty(identification, 'documentToken') === this.documentToken;
    } catch {
      return false;
    }
  }

  #snapshotEntryIsCurrent(entry) {
    if (!entry || entry.cancelled || this.settingsSnapshot !== entry) return false;
    const now = monotonicNow(this.host);
    if (now === null || now >= entry.expiresAt) {
      this.#clearSettingsSnapshot(entry, 'snapshot-timeout');
      return false;
    }
    return this.settingsSnapshot === entry
      && entry.owner === this.owner && entry.controller === this.api
      && entry.document === this.document && entry.documentToken === this.documentToken
      && this.#snapshotPageIsCurrent(entry.runId);
  }

  #disposeSnapshotSettings(entry) {
    const settings = entry?.settingsAPI;
    entry.settingsAPI = null;
    const dispose = dataProperty(settings, 'dispose');
    if (typeof dispose === 'function') {
      try { dispose.call(settings); } catch {}
    }
  }

  #clearSettingsSnapshot(expectedEntry, reason = 'snapshot-cancelled', settledResult) {
    const entry = expectedEntry ?? this.settingsSnapshot;
    if (!entry || (this.settingsSnapshot !== entry && !entry.cancelled)) return false;
    if (this.settingsSnapshot === entry) this.settingsSnapshot = null;
    entry.cancelled = true;
    entry.cancelResult = settledResult ?? this.#snapshotFailure(reason);
    if (entry.timer !== null) {
      try { this.host.clearTimeout(entry.timer); } catch {}
      entry.timer = null;
    }
    const resolveTimeout = entry.resolveTimeout;
    entry.resolveTimeout = null;
    try { resolveTimeout?.(entry.cancelResult); } catch {}
    if (entry.bytes) entry.bytes.fill(0);
    entry.bytes = null;
    entry.descriptor = null;
    entry.promise = null;
    this.#disposeSnapshotSettings(entry);
    return true;
  }

  #beginSettingsSnapshot(request) {
    const owner = dataProperty(request, 'owner');
    const runId = dataProperty(request, 'runId');
    const runNonce = dataProperty(request, 'runNonce');
    if (owner !== this.owner || !Number.isSafeInteger(runId) || runId !== this.state.runId
      || typeof runNonce !== 'string' || !SETTINGS_SNAPSHOT_RUN_NONCE.test(runNonce)) {
      return Promise.resolve(this.#snapshotFailure('snapshot-request-invalid'));
    }
    if (!this.#snapshotPageIsCurrent(runId)) {
      this.#clearSettingsSnapshot();
      return Promise.resolve(this.#snapshotFailure('snapshot-stale'));
    }

    const current = this.settingsSnapshot;
    if (current) {
      if (!this.#snapshotEntryIsCurrent(current)) {
        return Promise.resolve(current.cancelResult ?? this.#snapshotFailure('snapshot-stale'));
      }
      if (current.runId === runId && current.runNonce === runNonce) {
        return current.promise ?? Promise.resolve(current.descriptor
          ?? this.#snapshotFailure('snapshot-unavailable'));
      }
      return Promise.resolve(this.#snapshotFailure('snapshot-busy'));
    }
    if (this.settingsSnapshotRunID === runId) {
      return Promise.resolve(this.#snapshotFailure('snapshot-already-used'));
    }

    this.settingsSnapshotRunID = runId;
    const startedAt = monotonicNow(this.host);
    if (startedAt === null) return Promise.resolve(this.#snapshotFailure('snapshot-unavailable'));
    const entry = {
      owner: this.owner,
      runId,
      runNonce,
      snapshotID: `${runId}:${runNonce}`,
      controller: this.api,
      document: this.document,
      documentToken: this.documentToken,
      settingsAPI: null,
      bytes: null,
      status: null,
      sha256: '',
      nextIndex: 0,
      nextOffset: 0,
      descriptor: null,
      promise: null,
      cancelled: false,
      cancelResult: null,
      timer: null,
      resolveTimeout: null,
      expiresAt: startedAt + SETTINGS_SNAPSHOT_TIMEOUT_MS,
    };
    this.settingsSnapshot = entry;
    const timeoutPromise = new Promise(resolve => { entry.resolveTimeout = resolve; });
    try {
      entry.timer = this.host.setTimeout(() => {
        this.#clearSettingsSnapshot(entry, 'snapshot-timeout');
      }, SETTINGS_SNAPSHOT_TIMEOUT_MS);
    } catch {
      this.#clearSettingsSnapshot(entry, 'snapshot-unavailable');
      return Promise.resolve(entry.cancelResult);
    }
    const loadPromise = this.#loadSettingsSnapshot(entry);
    entry.promise = Promise.race([loadPromise, timeoutPromise]).then(
      result => {
        if (entry.cancelled) return entry.cancelResult ?? result;
        if (!this.#snapshotEntryIsCurrent(entry)) {
          const stale = this.#snapshotFailure('snapshot-stale');
          this.#clearSettingsSnapshot(entry, 'snapshot-stale', stale);
          return stale;
        }
        if (result.ok) entry.descriptor = result;
        else this.#clearSettingsSnapshot(entry, result.reason ?? 'snapshot-unavailable', result);
        entry.promise = null;
        return result;
      }, () => {
        const failure = this.#snapshotFailure('snapshot-unavailable');
        this.#clearSettingsSnapshot(entry, 'snapshot-unavailable', failure);
        return failure;
      },
    );
    return entry.promise;
  }

  #snapshotSettingsAPI(appearance) {
    const createSettings = dataProperty(this.payload, 'createImageSettings');
    const settingsEnvironment = dataProperty(this.pageAdapter, 'settingsEnvironment');
    if (typeof createSettings !== 'function' || typeof settingsEnvironment !== 'function') {
      throw new TypeError('settings unavailable');
    }
    const injected = settingsEnvironment.call(this.pageAdapter, this.host);
    if (!injected || typeof injected !== 'object') throw new TypeError('settings unavailable');
    const createLocalization = dataProperty(this.payload, 'createLocalization');
    const localization = typeof createLocalization === 'function'
      ? createLocalization({ locale: appearance.locale, themeConfig: this.assets?.themeConfig }) : null;
    const factoryInput = {
      document: this.document,
      Image: this.host.Image,
      URL: this.host.URL ?? URL,
      indexedDB: dataProperty(injected, 'indexedDB'),
      performance: this.host.performance,
      setTimeout: typeof this.host.setTimeout === 'function' ? this.host.setTimeout.bind(this.host) : undefined,
      clearTimeout: typeof this.host.clearTimeout === 'function' ? this.host.clearTimeout.bind(this.host) : undefined,
      localization,
      appearanceAvatar: this.assets?.entryAvatar,
      themeConfig: this.assets?.themeConfig,
      getAppearance: () => ({ ...appearance, source: 'official' }),
    };
    const namespace = dataProperty(injected, 'settingsNamespace');
    const settingsAPI = namespace === undefined
      ? createSettings(factoryInput) : createSettings({ ...factoryInput, settingsNamespace: namespace });
    if (!settingsAPI || typeof settingsAPI !== 'object') throw new TypeError('settings unavailable');
    return settingsAPI;
  }

  #prepareWorkspace(request) {
    const runId = dataProperty(request, 'runId');
    const nonce = dataProperty(request, 'runNonce');
    const expiresAt = dataProperty(request, 'expiresAt');
    const startedAt = monotonicNow(this.host);
    if (startedAt === null || typeof expiresAt !== 'number' || !Number.isFinite(expiresAt)
      || expiresAt <= startedAt) return this.#snapshotFailure('snapshot-timeout');
    if (this.playbackOwner !== 'native' || this.state.phase !== 'prepared'
      || dataProperty(request, 'owner') !== this.owner || runId !== this.state.runId
      || typeof nonce !== 'string' || !SETTINGS_SNAPSHOT_RUN_NONCE.test(nonce)
      || !this.#snapshotPageIsCurrent(runId)) return this.#snapshotFailure('snapshot-stale');
    if (this.nativeWorkspace) return this.nativeWorkspace.nonce === nonce
      ? { ok: true, accepted: true } : this.#snapshotFailure('owner-conflict');
    const operation = { nonce, runId, active: true, settingsAPI: null, timer: null, result: null,
      expiresAt: Math.min(expiresAt, startedAt + WALLPAPER_RETRY_TIMEOUT_MS), cancelled: false };
    this.nativeWorkspace = operation;
    const current = () => operation.active && this.nativeWorkspace === operation
      && monotonicNow(this.host) !== null && monotonicNow(this.host) < operation.expiresAt
      && this.state.phase === 'prepared' && this.#snapshotPageIsCurrent(runId);
    const finish = () => {
      if (operation.active && !operation.result && monotonicNow(this.host) >= operation.expiresAt) {
        operation.result = { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
      }
      operation.active = false;
      if (operation.timer !== null) this.host.clearTimeout(operation.timer);
      try { operation.settingsAPI?.dispose?.(); } catch {}
      operation.settingsAPI = null;
    };
    operation.cancel = () => {
      if (!operation.active) return;
      this.wallpaperGeneration += 1;
      operation.cancelled = true;
      operation.result = this.#setWallpaperFailure('apply-failed');
      finish();
    };
    operation.timer = this.host.setTimeout(() => {
      if (operation.active && this.nativeWorkspace === operation) {
        this.wallpaperGeneration += 1;
        operation.result = this.#setWallpaperFailure('apply-failed');
      }
      finish();
    }, operation.expiresAt - startedAt);
    Promise.resolve().then(async () => {
      if (!current()) return;
      const settingsAPI = this.#snapshotSettingsAPI(this.pageAdapter.observeAppearance(this.host));
      operation.settingsAPI = settingsAPI;
      const result = await settingsAPI.loadSnapshot(this.assets);
      if (!current()) return;
      if (!['valid', 'missing'].includes(dataProperty(result, 'status'))) {
        operation.result = this.#setWallpaperFailure('apply-failed', 'storage-unavailable');
        return;
      }
      const settings = dataProperty(result, 'settings');
      const resultWallpaper = await this.#applyWallpaper({ image: dataProperty(settings, 'artwork'),
        strength: dataProperty(settings, 'wallpaperStrength') }, runId, null);
      if (current()) operation.result = resultWallpaper;
    }).catch(() => {
      if (current()) operation.result = this.#setWallpaperFailure('apply-failed');
    }).finally(finish);
    return { ok: true, accepted: true };
  }

  #cancelWorkspace(request) {
    const operation = this.nativeWorkspace;
    if (this.playbackOwner !== 'native' || dataProperty(request, 'owner') !== this.owner
      || dataProperty(request, 'runId') !== this.state.runId
      || !this.#snapshotPageIsCurrent(this.state.runId)
      || !operation || operation.runId !== this.state.runId
      || dataProperty(request, 'runNonce') !== operation.nonce) return this.#snapshotFailure('snapshot-stale');
    operation.cancel();
    return { ok: true, cancelled: operation.cancelled };
  }

  #cancelDSHWallpaperPreparation() {
    const operation = this.dshWallpaperPreparation;
    if (!operation?.active) return false;
    operation.cancelled = true;
    operation.finish();
    return true;
  }

  #prepareDSHWallpaper(recovery = false) {
    const phase = this.state.phase;
    const earlyExit = this.intent === 'play' && !this.state.ready
      && (['failed', 'timeout'].includes(phase)
        || (phase === 'complete' && this.state.completion?.cause === 'skip'
          && this.state.completion?.beforeReady === true));
    const admitted = recovery ? earlyExit : phase === 'prepared' && this.intent === 'prepare';
    if (this.playbackOwner !== 'dsh-gated' || this.disposed || !admitted || this.dshWallpaperPreparation
      || (recovery && (this.state.wallpaper.applied || this.wallpaperRequest))) return false;
    const createSettings = dataProperty(this.payload, 'createImageSettings');
    if (typeof createSettings !== 'function' || typeof this.wallpaperApply !== 'function') return false;
    const startedAt = monotonicNow(this.host);
    const AbortControllerCtor = this.host.AbortController
      ?? (typeof AbortController === 'function' ? AbortController : null);
    if (startedAt === null || typeof this.host.setTimeout !== 'function'
      || typeof this.host.clearTimeout !== 'function'
      || typeof AbortControllerCtor !== 'function') return false;
    let abortController;
    try { abortController = new AbortControllerCtor(); } catch { return false; }
    const operation = {
      identity: Symbol('dsh-wallpaper-prepare'),
      runId: this.state.runId,
      phase,
      intent: this.intent,
      recovery,
      expiresAt: startedAt + WALLPAPER_RETRY_TIMEOUT_MS,
      active: true,
      cancelled: false,
      settingsAPI: null,
      abortController,
      timer: null,
      finish: null,
    };
    this.dshWallpaperPreparation = operation;
    const ownerCurrent = () => operation.active && this.dshWallpaperPreparation === operation
      && operation.identity === this.dshWallpaperPreparation?.identity
      && this.playbackOwner === 'dsh-gated' && this.state.phase === operation.phase
      && this.intent === operation.intent && this.state.runId === operation.runId
      && (!operation.recovery || (!this.state.ready && !this.state.wallpaper.applied))
      && this.#snapshotPageIsCurrent(operation.runId, operation.recovery);
    const current = () => ownerCurrent() && monotonicNow(this.host) !== null
      && monotonicNow(this.host) < operation.expiresAt;
    operation.finish = () => {
      if (!operation.active) return;
      const now = monotonicNow(this.host);
      if (!operation.cancelled && ownerCurrent() && now !== null && now >= operation.expiresAt) {
        this.#setWallpaperFailure('retry-timeout');
      }
      operation.active = false;
      if (operation.timer !== null) this.host.clearTimeout(operation.timer);
      operation.timer = null;
      try { operation.abortController.abort(); } catch {}
      try { operation.settingsAPI?.dispose?.(); } catch {}
      operation.settingsAPI = null;
      if (this.dshWallpaperPreparation === operation) this.dshWallpaperPreparation = null;
      this.#updateStartupWallpaperNotice();
    };
    operation.timer = this.host.setTimeout(() => {
      if (current()) this.#setWallpaperFailure('retry-timeout');
      operation.finish();
    }, operation.expiresAt - startedAt);
    Promise.resolve().then(async () => {
      if (!current()) return;
      const settingsAPI = this.#snapshotSettingsAPI(this.pageAdapter.observeAppearance(this.host));
      operation.settingsAPI = settingsAPI;
      const result = await settingsAPI.loadSnapshot(this.assets);
      if (!current()) return;
      if (!['valid', 'missing'].includes(dataProperty(result, 'status'))) {
        this.#setWallpaperFailure('apply-failed', 'storage-unavailable');
        return;
      }
      const settings = dataProperty(result, 'settings');
      await this.#applyWallpaper({ image: dataProperty(settings, 'artwork'),
        strength: dataProperty(settings, 'wallpaperStrength') }, operation.runId, null,
      false, null, operation);
    }).catch(() => {
      if (current()) this.#setWallpaperFailure('apply-failed');
    }).finally(() => operation.finish());
    return true;
  }

  async #loadSettingsSnapshot(entry) {
    let snapshot = null;
    let localBytes = null;
    try {
      const appearance = this.pageAdapter.observeAppearance(this.host);
      const snapshotAppearance = Object.freeze({
        locale: dataProperty(appearance, 'locale'), theme: dataProperty(appearance, 'theme'),
      });
      if (!['en', 'zh-CN'].includes(snapshotAppearance.locale)
        || !['light', 'dark'].includes(snapshotAppearance.theme)) return this.#snapshotFailure('snapshot-invalid');
      const settingsAPI = this.#snapshotSettingsAPI(appearance);
      entry.settingsAPI = settingsAPI;
      if (!this.#snapshotEntryIsCurrent(entry)) return this.#snapshotFailure('snapshot-stale');
      const loadSnapshot = dataProperty(settingsAPI, 'loadSnapshot');
      if (typeof loadSnapshot !== 'function') return this.#snapshotFailure('snapshot-unavailable');
      snapshot = await loadSnapshot.call(settingsAPI, this.assets);
      if (!this.#snapshotEntryIsCurrent(entry)) return this.#snapshotFailure('snapshot-stale');

      const status = dataProperty(snapshot, 'status');
      if (status === 'failure') {
        const reason = dataProperty(snapshot, 'reason');
        const stableReason = typeof reason === 'string' && /^[a-z0-9-]{1,64}$/.test(reason)
          ? reason : 'read-failed';
        return this.#snapshotFailure(stableReason.startsWith('settings-')
          ? stableReason : `settings-${stableReason}`);
      }
      if (status !== 'missing' && status !== 'valid') return this.#snapshotFailure('snapshot-invalid');
      const source = dataProperty(snapshot, 'settings');
      const sourceText = dataProperty(snapshot, 'explicitText');
      if (!source || typeof source !== 'object' || !sourceText || typeof sourceText !== 'object') {
        return this.#snapshotFailure('snapshot-invalid');
      }
      const settings = Object.freeze({
        schemaVersion: dataProperty(source, 'schemaVersion'),
        avatar: dataProperty(source, 'avatar'),
        artwork: dataProperty(source, 'artwork'),
        contours: dataProperty(source, 'contours'),
        introTitle: dataProperty(source, 'introTitle'),
        introCaption: dataProperty(source, 'introCaption'),
        artworkSubtitle: dataProperty(source, 'artworkSubtitle'),
        wallpaperStrength: dataProperty(source, 'wallpaperStrength'),
      });
      const explicitText = Object.freeze({
        introTitle: dataProperty(sourceText, 'introTitle'),
        introCaption: dataProperty(sourceText, 'introCaption'),
        artworkSubtitle: dataProperty(sourceText, 'artworkSubtitle'),
      });
      if (settings.schemaVersion !== 1 || typeof settings.avatar !== 'string'
        || settings.avatar.length > 2 * 1024 * 1024
        || !/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(settings.avatar)
        || typeof settings.artwork !== 'string' || settings.artwork.length > 12 * 1024 * 1024
        || !/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(settings.artwork)
        || !Array.isArray(settings.contours) || settings.contours.length > 1200
        || typeof settings.introTitle !== 'string' || settings.introTitle.length > 16
        || typeof settings.introCaption !== 'string' || settings.introCaption.length > 48
        || typeof settings.artworkSubtitle !== 'string' || settings.artworkSubtitle.length > 60
        || !Number.isInteger(settings.wallpaperStrength) || settings.wallpaperStrength < 0
        || settings.wallpaperStrength > 75
        || Object.values(explicitText).some(value => typeof value !== 'boolean')) {
        return this.#snapshotFailure('snapshot-invalid');
      }
      const serialized = JSON.stringify({ status, settings, explicitText, appearance: snapshotAppearance });
      if (typeof serialized !== 'string' || serialized.length > SETTINGS_SNAPSHOT_MAX_BYTES) {
        return this.#snapshotFailure('snapshot-too-large');
      }
      const Encoder = this.host.TextEncoder ?? globalThis.TextEncoder;
      if (typeof Encoder !== 'function') return this.#snapshotFailure('snapshot-unavailable');
      localBytes = new Encoder().encode(serialized);
      snapshot = null;
      if (localBytes.byteLength > SETTINGS_SNAPSHOT_MAX_BYTES) return this.#snapshotFailure('snapshot-too-large');
      if (!this.#snapshotEntryIsCurrent(entry)) return this.#snapshotFailure('snapshot-stale');
      const cryptoObject = this.host.crypto ?? globalThis.crypto;
      const subtle = cryptoObject?.subtle;
      if (!subtle || typeof subtle.digest !== 'function') return this.#snapshotFailure('snapshot-unavailable');
      const digestBytes = localBytes;
      entry.bytes = digestBytes;
      localBytes = null;
      const digest = new Uint8Array(await subtle.digest('SHA-256', digestBytes));
      if (!this.#snapshotEntryIsCurrent(entry)) return this.#snapshotFailure('snapshot-stale');
      const sha256 = Array.from(digest, value => value.toString(16).padStart(2, '0')).join('');
      entry.status = status;
      entry.sha256 = sha256;
      this.#disposeSnapshotSettings(entry);
      return {
        ok: true,
        owner: entry.owner,
        runId: entry.runId,
        runNonce: entry.runNonce,
        snapshotID: entry.snapshotID,
        status: entry.status,
        byteLength: entry.bytes.byteLength,
        encodedByteLength: encodedSnapshotByteLength(entry.bytes.byteLength),
        chunkSize: SETTINGS_SNAPSHOT_CHUNK_BYTES,
        chunkCount: Math.ceil(entry.bytes.byteLength / SETTINGS_SNAPSHOT_CHUNK_BYTES),
        digestAlgorithm: 'sha-256',
        sha256: entry.sha256,
      };
    } catch {
      return this.#snapshotFailure('snapshot-unavailable');
    } finally {
      snapshot = null;
      if (localBytes) localBytes.fill(0);
      this.#disposeSnapshotSettings(entry);
    }
  }

  #readSettingsSnapshotChunk(request) {
    const owner = dataProperty(request, 'owner');
    const runId = dataProperty(request, 'runId');
    const runNonce = dataProperty(request, 'runNonce');
    const snapshotID = dataProperty(request, 'snapshotID');
    const index = dataProperty(request, 'index');
    const offset = dataProperty(request, 'offset');
    const entry = this.settingsSnapshot;
    if (!entry || owner !== entry.owner || runId !== entry.runId || runNonce !== entry.runNonce
      || snapshotID !== entry.snapshotID) return this.#snapshotFailure('snapshot-not-found');
    if (!this.#snapshotEntryIsCurrent(entry)) {
      if (!entry.cancelled) this.#clearSettingsSnapshot(entry, 'snapshot-stale');
      return entry.cancelResult ?? this.#snapshotFailure('snapshot-stale');
    }
    if (!entry.descriptor) return this.#snapshotFailure('snapshot-not-ready');
    if (!entry.bytes || !Number.isSafeInteger(index) || !Number.isSafeInteger(offset)) {
      return this.#snapshotFailure('snapshot-not-ready');
    }
    if (index !== entry.nextIndex || offset !== entry.nextOffset) {
      this.#clearSettingsSnapshot(entry);
      return this.#snapshotFailure('snapshot-order-invalid');
    }
    const byteLength = Math.min(SETTINGS_SNAPSHOT_CHUNK_BYTES, entry.bytes.byteLength - offset);
    if (byteLength <= 0) {
      this.#clearSettingsSnapshot(entry);
      return this.#snapshotFailure('snapshot-order-invalid');
    }
    const dataBase64 = encodeBase64(entry.bytes.subarray(offset, offset + byteLength));
    const result = {
      ok: true,
      owner: entry.owner,
      runId: entry.runId,
      runNonce: entry.runNonce,
      snapshotID: entry.snapshotID,
      index,
      offset,
      byteLength,
      totalBytes: entry.bytes.byteLength,
      chunkCount: Math.ceil(entry.bytes.byteLength / SETTINGS_SNAPSHOT_CHUNK_BYTES),
      status: entry.status,
      digestAlgorithm: 'sha-256',
      sha256: entry.sha256,
      dataBase64,
    };
    entry.nextIndex += 1;
    entry.nextOffset += byteLength;
    if (entry.nextOffset === entry.bytes.byteLength) this.#clearSettingsSnapshot(entry);
    return result;
  }

  #disposeSettingsSnapshot(request) {
    const owner = dataProperty(request, 'owner');
    const runId = dataProperty(request, 'runId');
    const runNonce = dataProperty(request, 'runNonce');
    const snapshotID = dataProperty(request, 'snapshotID');
    if (owner !== this.owner || !Number.isSafeInteger(runId) || runId !== this.state.runId
      || typeof runNonce !== 'string' || !SETTINGS_SNAPSHOT_RUN_NONCE.test(runNonce)) {
      return this.#snapshotFailure('snapshot-request-invalid');
    }
    const entry = this.settingsSnapshot;
    if (entry && (entry.owner !== owner || entry.runId !== runId || entry.runNonce !== runNonce
      || (snapshotID !== undefined && entry.snapshotID !== snapshotID))) {
      return this.#snapshotFailure('snapshot-not-found');
    }
    if (entry) this.#clearSettingsSnapshot(entry);
    return { ok: true, disposed: !!entry };
  }

  #rememberFocus(focused = this.document?.activeElement) {
    if (focused === this.appearanceEntry?.element) focused = this.appearanceEntry.button;
    if (focused !== this.frame?.element && focused?.isConnected && typeof focused.focus === 'function') {
      this.savedFocus = focused;
    }
  }

  #focusOverlayFrame() {
    const frame = this.frame?.element;
    if (!frame || this.document?.activeElement === frame || typeof frame.focus !== 'function') return;
    try { frame.focus({ preventScroll: true }); }
    catch { try { frame.focus(); } catch {} }
  }

  #isolateHostPage() {
    if (this.modalIsolation) return;
    const body = this.document?.body;
    if (!body) return;

    const owner = { body, targets: new Map(), childObserver: null, inertObserver: null };
    this.modalIsolation = owner;
    const setOwnedInert = (element, value) => {
      const state = owner.targets.get(element);
      if (!state) return;
      const before = Boolean(element.inert);
      element.inert = value;
      if (before !== Boolean(element.inert) && element.isConnected) state.pendingOwnedWrites++;
    };
    const lockNode = node => {
      if (!node || node.nodeType !== 1) return;
      const frame = this.frame?.element;
      if (node === frame || (frame && typeof node.contains === 'function' && node.contains(frame))) return;
      let state = owner.targets.get(node);
      if (state) {
        state.restoreInert = Boolean(node.inert);
        state.ownsInert = false;
      } else {
        state = { restoreInert: Boolean(node.inert), pendingOwnedWrites: 0, ownsInert: false };
        owner.targets.set(node, state);
      }
      if (!state.restoreInert) {
        setOwnedInert(node, true);
        state.ownsInert = true;
      }
    };
    const processMutations = records => {
      if (records.some(record => record.type === 'childList')) {
        const pendingInert = owner.inertObserver?.takeRecords?.() || [];
        if (pendingInert.length) processMutations(pendingInert);
      }
      const reassert = new Set();
      for (const record of records) {
        if (record.type === 'attributes') {
          const state = owner.targets.get(record.target);
          if (!state) continue;
          if (state.pendingOwnedWrites > 0) {
            state.pendingOwnedWrites--;
            continue;
          }
          state.restoreInert = Boolean(record.target.inert);
          state.ownsInert = false;
          if (!state.restoreInert) reassert.add(record.target);
        } else if (record.type === 'childList' && record.target === body) {
          for (const node of record.removedNodes) {
            if (!node || node.nodeType !== 1) continue;
            const state = owner.targets.get(node);
            if (!state) continue;
            if (state.ownsInert && node.inert === true) setOwnedInert(node, state.restoreInert);
            state.ownsInert = false;
          }
          for (const node of record.addedNodes) lockNode(node);
        }
      }
      for (const element of reassert) {
        if (this.modalIsolation === owner && element.parentNode === body && !element.inert) {
          setOwnedInert(element, true);
          const state = owner.targets.get(element);
          if (state) state.ownsInert = true;
        }
      }
    };

    const MutationObserver = this.host.MutationObserver;
    if (typeof MutationObserver === 'function') {
      owner.childObserver = new MutationObserver(processMutations);
      owner.childObserver.observe(body, { childList: true });
      if (this.document.documentElement) {
        owner.inertObserver = new MutationObserver(processMutations);
        owner.inertObserver.observe(this.document.documentElement, {
          attributes: true, attributeFilter: ['inert'], subtree: true,
        });
      }
    }
    for (const node of Array.from(body.children || [])) lockNode(node);
  }

  #releaseHostPage() {
    const owner = this.modalIsolation;
    if (!owner) return;
    if (owner.inertObserver) {
      for (const record of owner.inertObserver.takeRecords?.() || []) {
        if (record.type !== 'attributes') continue;
        const state = owner.targets.get(record.target);
        if (!state) continue;
        if (state.pendingOwnedWrites > 0) state.pendingOwnedWrites--;
        else state.restoreInert = Boolean(record.target.inert);
      }
    }
    owner.childObserver?.disconnect();
    owner.inertObserver?.disconnect();
    this.modalIsolation = null;
    for (const [element, state] of owner.targets) {
      if (state.ownsInert && element.inert === true) element.inert = state.restoreInert;
    }
  }

  #isCurrentFrame(runId, frame = this.frame) {
    return !this.disposed && runId === this.state.runId && frame !== null
      && frame === this.frame && !['complete', 'failed', 'timeout', 'disposed'].includes(this.state.phase);
  }

  #checkFrameConnection() {
    const frame = this.frame;
    if (frame && panelDisconnected(frame)) {
      this.state.ready = false;
      this.#fail('startup-interrupted');
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
      this.state.phase = this.intent === 'play' ? 'playing' : 'settings';
      if (this.playbackOwner === 'dsh-gated' && this.intent === 'play') {
        const gateReady = dataProperty(this.startupGate, 'ready');
        const preview = dataProperty(this.frameHandle, 'preview');
        const beginLaunch = dataProperty(preview, 'beginLaunch');
        let revealed = false;
        try {
          revealed = typeof gateReady === 'function' && gateReady.call(this.startupGate) === true
            && typeof beginLaunch === 'function' && beginLaunch.call(preview) === true;
        } catch {}
        if (!revealed) {
          this.#fail('startup-gate-expired', message.runId);
          return;
        }
      }
      if (this.intent === 'settings') this.#focusOverlayFrame();
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
      this.#releaseStartupGate();
      this.#stopFrameAndRevealEntry();
      this.#updateStartupWallpaperNotice();
      this.#clearWatchdog();
      this.host.removeEventListener('message', this.onMessage);
      if (this.playbackOwner === 'dsh-gated' && this.intent === 'play'
        && this.state.completion?.cause === 'skip' && this.state.completion.beforeReady) {
        this.#prepareDSHWallpaper(true);
      }
      return;
    }
    if (message.action === 'assetError') {
      if (this.state.phase !== 'loading' || !FIXED_PAGE_REASONS.has(message.reason)) return;
      this.#fail(message.reason);
      return;
    }
    if (message.action === 'settings-open') {
      if (this.state.ready && this.state.phase === 'playing') {
        this.#isolateHostPage();
        this.#focusOverlayFrame();
        this.state.phase = 'settings';
        this.#clearWatchdog();
      }
      return;
    }
    if (message.action === 'settings-close') {
      if (this.state.ready && this.state.phase === 'settings') {
        this.state.phase = 'complete';
        this.state.completed = true;
        this.state.overlay = false;
        this.state.completion = { cause: 'settings-save', beforeReady: false };
        this.#stopFrameAndRevealEntry();
        this.#updateStartupWallpaperNotice();
        this.#clearWatchdog();
        this.host.removeEventListener('message', this.onMessage);
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

  #isDSHPrepared() {
    return this.playbackOwner === 'dsh-gated' && this.state.phase === 'prepared' && this.intent === 'prepare';
  }

  #canRetryStartupWallpaper() {
    return (this.state.phase === 'complete' && this.state.completed)
      || (this.#isDSHPrepared() && !this.dshWallpaperPreparation?.active);
  }

  #isCurrentRetry(runId, generation) {
    return !this.disposed && generation === this.wallpaperGeneration && runId === this.state.runId
      && this.#canRetryStartupWallpaper() && this.#ownsStartupController();
  }

  // Embed-sourced wallpaper applies stay current while the controller owns the
  // global, even after the embed itself is disposed — the same grace the
  // overlay's completed playback and settings-save paths get.
  #isSettingsEmbed(runId, embed) {
    return this.settingsEmbedAdmitted && !this.disposed && !!embed
      && runId === embed.runId && this.#ownsStartupController();
  }

  #setWallpaperFailure(code, reason = 'wallpaper-unsupported', imageDecoded = false) {
    const result = { applied: false, reason, imageDecoded };
    const failure = wallpaperFailure({ failureCode: code });
    if (failure) Object.assign(result, failure);
    this.state.wallpaper = result;
    if (this.intent === 'play' || this.#isDSHPrepared()) {
      this.startupWallpaperFailure = failure && this.wallpaperRequest && !this.wallpaperDisabled
        ? { ...result } : null;
      if (!this.wallpaperRetryPromise) this.startupWallpaperNoticeDismissed = false;
    }
    this.#updateStartupWallpaperNotice();
    return { ...result };
  }

  #updateStartupWallpaperNotice(announcementKey) {
    const cause = this.state.completion?.cause;
    const visible = !this.disposed && !this.startupWallpaperNoticeDismissed
      && !!this.startupWallpaperFailure && !!this.wallpaperRequest && !this.wallpaperDisabled
      && (this.#isDSHPrepared() ? !this.dshWallpaperPreparation?.active
        : this.state.phase === 'complete' && this.state.completed
          && ['natural', 'skip', 'settings-cancel'].includes(cause));
    this.appearanceEntry?.setWallpaperFailure(visible ? this.startupWallpaperFailure : null,
      announcementKey);
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
    if (!this.#canRetryStartupWallpaper()) {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'busy'));
    }
    if (this.wallpaperDisabled || this.state.wallpaper.reason === 'disabled') {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'disabled'));
    }
    if (!this.wallpaperRequest) return Promise.resolve(this.#retryResult(false, previousFailure, 'no-request'));

    const current = wallpaperRecord(this.host, this.wallpaperOwner);
    if ((current.present && (!current.supported || current.api !== this.wallpaperAPI))
      || (!current.present && this.wallpaperAPI)) {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'unknown-owner'));
    }
    this.#refreshWallpaper();
    if (this.state.wallpaper.applied) {
      const hadFailure = !!this.startupWallpaperFailure;
      this.startupWallpaperFailure = null;
      this.#updateStartupWallpaperNotice(hadFailure ? 'applied' : undefined);
      return Promise.resolve(this.#retryResult(false, null, 'already-applied'));
    }

    this.startupWallpaperNoticeDismissed = false;
    this.#updateStartupWallpaperNotice('retrying');
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

  async #applyWallpaper(message, runId, frame, retry = false, embed = null, dshPreparation = null) {
    if (this.dshWallpaperPreparation?.active && dshPreparation !== this.dshWallpaperPreparation) {
      this.#cancelDSHWallpaperPreparation();
    }
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
      this.startupWallpaperFailure = null;
      this.#updateStartupWallpaperNotice();
      return { ...this.state.wallpaper };
    }
    if (!retry) {
      this.wallpaperRequest = { image: message.image, strength: message.strength };
      this.wallpaperDisabled = false;
    }
    // The workspace may mount after the overlay closes. Skip, replacement and
    // disposal still cancel work, while completed playback or saving can finish.
    const isCurrent = () => generation === this.wallpaperGeneration
      && (retry ? this.#isCurrentRetry(runId, generation)
        : embed ? this.#isSettingsEmbed(runId, embed)
          : dshPreparation ? (this.playbackOwner === 'dsh-gated' && this.state.phase === dshPreparation.phase
            && dshPreparation.active && this.dshWallpaperPreparation === dshPreparation
            && this.intent === dshPreparation.intent && this.state.runId === dshPreparation.runId
            && (!dshPreparation.recovery || (!this.state.ready && !this.state.wallpaper.applied))
            && monotonicNow(this.host) !== null && monotonicNow(this.host) < dshPreparation.expiresAt
            && this.#snapshotPageIsCurrent(runId, dshPreparation.recovery))
            : (this.playbackOwner === 'native' && this.state.phase === 'prepared'
              && this.nativeWorkspace?.active && monotonicNow(this.host) !== null
              && monotonicNow(this.host) < this.nativeWorkspace.expiresAt && this.#snapshotPageIsCurrent(runId))
              || this.#isCurrentFrame(runId, frame) || (!this.disposed && runId === this.state.runId
              && this.state.phase === 'complete' && ['natural', 'settings-save'].includes(this.state.completion?.cause)
              && this.#ownsStartupController()));
    if (typeof this.wallpaperApply !== 'function') {
      if (isCurrent()) return this.#setWallpaperFailure('apply-unavailable');
      return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
    }
    try {
      this.appearance = this.pageAdapter.observeAppearance(this.host);
      const request = Object.freeze({
        image: message.image, strength: message.strength, surface: this.appearance.colors.surface,
      });
      const result = dshPreparation
        ? await this.wallpaperApply(request, isCurrent, dshPreparation.abortController.signal)
        : await this.wallpaperApply(request, isCurrent);
      if (!isCurrent()) return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
      if (dataProperty(result, 'applied') === false) {
        const reason = wallpaperReason(result);
        const failure = wallpaperFailure(result) ?? wallpaperFailure({ failureCode: 'apply-failed' });
        const current = wallpaperRecord(this.host, this.wallpaperOwner);
        if (current.present && !current.supported) {
          this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
          if (this.intent === 'play' || this.#isDSHPrepared()) this.startupWallpaperFailure = null;
          this.#updateStartupWallpaperNotice();
          return { ...this.state.wallpaper };
        }
        if (current.supported) this.wallpaperAPI = current.api;
        const imageDecoded = dataProperty(result, 'imageDecoded') === true;
        return this.#setWallpaperFailure(failure.failureCode, reason, imageDecoded);
      }
      const current = wallpaperRecord(this.host, this.wallpaperOwner);
      if (!current.supported) {
        if (current.present) {
          this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
          if (this.intent === 'play' || this.#isDSHPrepared()) this.startupWallpaperFailure = null;
          this.#updateStartupWallpaperNotice();
          return { ...this.state.wallpaper };
        }
        return this.#setWallpaperFailure('apply-unavailable');
      }
      this.wallpaperAPI = current.api;
      this.appearance = this.pageAdapter.observeAppearance(this.host);
      const updateWallpaperSurface = dataProperty(current.api, 'updateSurface');
      if (typeof updateWallpaperSurface === 'function') {
        try { updateWallpaperSurface.call(current.api, this.appearance.colors.surface); } catch {}
      }
      this.state.wallpaper = this.#wallpaperStatus(current.api);
      if (!this.state.wallpaper.applied && !this.state.wallpaper.reason) {
        this.state.wallpaper.reason = 'wallpaper-unsupported';
      }
      if (this.state.wallpaper.applied) {
        const hadStartupFailure = !!this.startupWallpaperFailure;
        this.startupWallpaperFailure = null;
        this.#updateStartupWallpaperNotice(retry && hadStartupFailure && this.#canRetryStartupWallpaper()
          ? 'applied' : undefined);
      } else {
        if (this.intent === 'play' || this.#isDSHPrepared()) {
          const failure = wallpaperFailure(this.state.wallpaper);
          this.startupWallpaperFailure = failure && this.wallpaperRequest && !this.wallpaperDisabled
            ? { ...this.state.wallpaper } : null;
        }
        this.#updateStartupWallpaperNotice();
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
    const current = wallpaperRecord(this.host, this.wallpaperOwner);
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
    this.#clearSettingsSnapshot();
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    this.state.phase = 'failed';
    this.state.overlay = false;
    this.state.reason = reason;
    this.host.removeEventListener('message', this.onMessage);
    this.#releaseStartupGate();
    this.#stopFrame();
    if (this.playbackOwner === 'dsh-gated' && this.intent === 'play' && !this.state.ready) {
      this.#prepareDSHWallpaper(true);
    }
  }

  #releaseStartupGate() {
    this.#unsubscribeStartupGateExpiry();
    const release = dataProperty(this.startupGate, 'release');
    if (typeof release !== 'function') return;
    try { release.call(this.startupGate); } catch {}
  }

  #unsubscribeStartupGateExpiry() {
    const unsubscribe = this.startupGateUnsubscribe;
    this.startupGateUnsubscribe = null;
    try { unsubscribe?.(); } catch {}
  }

  expire(runId) {
    if (this.disposed || runId !== this.state.runId || !['loading', 'playing'].includes(this.state.phase)) return false;
    this.#clearSettingsSnapshot();
    const recoverable = this.state.phase === 'playing' && this.state.ready;
    this.watchdog = null;
    this.#disconnectBodyObserver();
    this.state.phase = 'timeout';
    this.state.overlay = false;
    this.state.reason = 'overlay-timeout';
    this.host.removeEventListener('message', this.onMessage);
    this.#releaseStartupGate();
    // A prepared run can still expose settings when playback stalls. Its timeout
    // remains authoritative; revealing the entry does not complete that run.
    if (recoverable) this.#stopFrameAndRevealEntry();
    else this.#stopFrame();
    if (!this.state.ready) this.#prepareDSHWallpaper(true);
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

  #restoreFocus(frame, ownedFocus = this.document?.activeElement === frame?.element) {
    if (!ownedFocus) return;
    const candidates = [this.savedFocus, this.appearanceEntry?.button];
    try {
      const selectors = 'button:not([disabled]),a[href],input:not([disabled]):not([type="hidden"]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';
      candidates.push(...Array.from(this.document.querySelectorAll(selectors)));
    } catch {}
    for (const candidate of new Set(candidates)) {
      if (!candidate?.isConnected || candidate.inert || candidate.disabled
        || typeof candidate.focus !== 'function' || candidate.hidden) continue;
      try {
        const style = this.host.getComputedStyle?.(candidate);
        if (style?.display === 'none' || style?.visibility === 'hidden'
          || (typeof candidate.getClientRects === 'function' && candidate.getClientRects().length === 0)) continue;
      } catch {}
      try { candidate.focus(); } catch { continue; }
      const root = candidate.getRootNode?.();
      if (this.document.activeElement === candidate
        || (root?.host === this.document.activeElement && root.activeElement === candidate)) return;
    }
  }

  // Remove this controller's overlay frame without touching keyboard focus.
  // Whether the frame still owned document focus is captured before removal,
  // because removing the element moves focus to the body.
  #teardownFrame() {
    const frame = this.frame;
    const handle = this.frameHandle;
    const ownedFocus = Boolean(frame) && this.document?.activeElement === frame.element;
    this.frame = null;
    this.frameHandle = null;
    this.frameObserver?.disconnect();
    this.frameObserver = null;
    this.#releaseHostPage();
    if (!frame) return { frame: null, ownedFocus: false };
    try { handle?.dispose?.(); } catch {}
    try { frame.remove(); } catch {}
    return { frame, ownedFocus };
  }

  #stopFrame() {
    const { frame, ownedFocus } = this.#teardownFrame();
    this.#restoreFocus(frame, ownedFocus);
  }

  // Completion ordering: remove this controller's own overlay, then reveal the
  // appearance entry, then restore focus. The entry's page adapter hides the
  // entry while a full-viewport layer covers every host control, and this
  // controller's overlay is exactly such a layer until it is removed. Restoring
  // focus last keeps a saved entry-button focus from being skipped for being
  // hidden at the moment the overlay closes.
  #stopFrameAndRevealEntry() {
    const { frame, ownedFocus } = this.#teardownFrame();
    this.appearanceEntry?.update(true);
    this.#restoreFocus(frame, ownedFocus);
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
    const readyTimeout = this.state.phase === 'timeout'
      && this.state.reason === 'overlay-timeout' && this.state.ready;
    if (this.state.phase === 'complete' || this.state.phase === 'prepared' || readyTimeout) {
      return this.#beginRun('settings');
    }
    if (this.state.phase === 'settings') return false;
    if (this.state.phase === 'playing') {
      this.#rememberFocus();
      return this.#invokeFrameSettings();
    }
    return false;
  }

  // Settings-section embed for host settings pages (DSH): mounts the same panel
  // document into a caller-owned element with its own run id, message listener
  // and lifecycle, entirely separate from the startup overlay run state.
  // Returns null on any host gate; otherwise an idempotent disposer.
  #mountSettings(target, options) {
    if (!this.settingsEmbedAdmitted || this.disposed || !this.installed) return null;
    if (!target || typeof target.appendChild !== 'function') return null;
    this.#cancelDSHWallpaperPreparation();
    const mount = {
      alive: true, runId: nextRunId++, frame: null, handle: null,
      onClose: options && typeof options.onClose === 'function' ? options.onClose : null,
    };
    mount.listener = (event) => {
      if (!mount.alive || event.source !== mount.frame?.contentWindow) return;
      this.#receiveSettingsMessage(mount, event);
    };
    try {
      mount.frame = mountSettingsPanel(this.host, this.payload, mount.runId, this.assets,
        (event) => this.#receiveSettingsMessage(mount, event),
        this.appearance, this.pageAdapter, this.metadata, target);
      mount.observer = observePanelConnection(this.host, mount.frame, () => {
        if (mount.alive && panelDisconnected(mount.frame)) this.#closeSettingsEmbed(mount);
      });
    } catch {
      this.#disposeSettingsEmbed(mount);
      return null;
    }
    this.settingsEmbeds.add(mount);
    this.host.addEventListener('message', mount.listener);
    const started = mount.frame.start();
    if (started && typeof started.then === 'function') {
      Promise.resolve(started).then(handle => {
        if (!mount.alive) { try { handle?.dispose?.(); } catch {} return; }
        mount.handle = handle;
      }, () => {});
    } else if (started && typeof started === 'object') {
      mount.handle = started;
    }
    return () => this.#disposeSettingsEmbed(mount);
  }

  #receiveSettingsMessage(mount, event) {
    if (mount.frame && event.source !== mount.frame.contentWindow) return;
    const message = event.data;
    if (!message || typeof message !== 'object' || Array.isArray(message)
      || message.type !== 'azhou-startup' || message.runId !== mount.runId
      || typeof message.action !== 'string') return;
    if (message.action === 'ready') return; // handshake only; the panel owns its UI state
    if (message.action === 'background') {
      return this.#applyWallpaper(message, mount.runId, null, false, mount);
    }
    // The embed releases its panel even if the host does not close the modal.
    if (message.action === 'assetError' || message.action === 'settings-close'
        || (message.action === 'complete' && message.skipped === true)) {
      this.#closeSettingsEmbed(mount);
    }
  }

  #closeSettingsEmbed(mount) {
    const close = mount.onClose;
    this.#disposeSettingsEmbed(mount);
    try { close?.(); } catch {}
  }

  #disposeSettingsEmbed(mount) {
    if (!mount || !mount.alive) return;
    mount.alive = false;
    this.settingsEmbeds.delete(mount);
    mount.observer?.disconnect();
    mount.observer = null;
    this.host.removeEventListener('message', mount.listener);
    const frame = mount.frame;
    const handle = mount.handle;
    mount.frame = null;
    mount.handle = null;
    try { handle?.dispose?.(); } catch {}
    try { frame?.remove(); } catch {}
  }

  #status() {
    this.#checkFrameConnection();
    this.#refreshWallpaper();
    const status = {
      owner: this.owner,
      version: VERSION,
      ...this.metadata,
      phase: this.state.phase,
      runId: this.state.runId,
      ready: this.state.ready,
      completed: this.state.completed,
      overlay: this.state.overlay,
      reason: this.state.reason,
      wallpaper: { ...this.state.wallpaper },
      completion: this.state.completion ? { ...this.state.completion } : null,
    };
    if (this.playbackOwner === 'native') {
      status.playbackOwner = 'native';
      status.prepared = this.state.phase === 'prepared';
      const operation = this.nativeWorkspace;
      if (status.prepared) {
        const currentOperation = operation?.runId === this.state.runId ? operation : null;
        status.wallpaper = currentOperation?.result ? { ...currentOperation.result }
          : { applied: false, reason: '', imageDecoded: false };
        if (status.wallpaper.applied && !this.state.wallpaper.applied) {
          status.wallpaper = { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
        }
        status.workspace = currentOperation ? { runId: currentOperation.runId, runNonce: currentOperation.nonce,
          phase: currentOperation.cancelled ? 'cancelled' : currentOperation.result ? 'complete' : 'pending' } : null;
      }
      status.wallpaperDisposition = status.wallpaper.applied ? 'applied'
        : status.wallpaper.reason === 'disabled' ? 'disabled'
          : status.wallpaper.reason || status.wallpaper.failureCode ? 'degraded' : 'pending';
    }
    return status;
  }

  #disposeWallpaper() {
    const current = wallpaperRecord(this.host, this.wallpaperOwner);
    if (!current.supported || !this.wallpaperAPI || current.api !== this.wallpaperAPI) return;
    try { dataProperty(current.api, 'dispose').call(current.api); } catch {}
    this.wallpaperAPI = null;
  }

  #dispose() {
    if (this.disposed) return { disposed: true };
    this.disposed = true;
    this.nativeWorkspace?.cancel?.();
    this.nativeWorkspace = null;
    this.#cancelDSHWallpaperPreparation();
    this.#clearSettingsSnapshot();
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
    this.host.removeEventListener('pagehide', this.onPageHide);
    this.host.removeEventListener('pageshow', this.onPageShow);
    this.#releaseStartupGate();
    for (const mount of [...this.settingsEmbeds]) this.#disposeSettingsEmbed(mount);
    this.settingsEmbeds.clear();
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

export function installStartup(payload, host = globalThis, pageAdapter, playbackOwner = 'page') {
  // The host page strategy lives in the explicitly passed page adapter. Without a
  // bound adapter the controller cannot identify the page and refuses before any
  // DOM, database or global work.
  if (!host || !pageAdapter || typeof pageAdapter !== 'object'
      || typeof pageAdapter.identify !== 'function') {
    return { installed: false, alreadyActive: false, reason: PAGE_REASON };
  }
  const identification = pageAdapter.identify(host);
  if (!identification || identification.kind !== 'matched') {
    return { installed: false, alreadyActive: false, reason: PAGE_REASON };
  }
  if (!['page', 'native', 'dsh-gated'].includes(playbackOwner)) {
    return { installed: false, alreadyActive: false, reason: 'playback-owner-invalid' };
  }
  const ownerDescriptor = Object.getOwnPropertyDescriptor(pageAdapter, 'controllerOwner');
  const owner = ownerDescriptor ? dataProperty(pageAdapter, 'controllerOwner') : OWNER;
  if (!CONTROLLER_OWNERS.has(owner)) {
    return { installed: false, alreadyActive: false, reason: 'owner-conflict' };
  }
  if ((playbackOwner === 'native' && owner !== OWNER)
      || (playbackOwner === 'dsh-gated' && owner !== DSH_OWNER)) {
    return { installed: false, alreadyActive: false, reason: 'playback-owner-invalid' };
  }
  let metadata;
  if (dataProperty(dataProperty(pageAdapter, 'controllerWallpaper'), 'requiresControllerMetadata') === true) {
    metadata = controllerMetadataSnapshot(dataProperty(pageAdapter, 'controllerMetadata'));
    if (!metadata) return { installed: false, alreadyActive: false, reason: 'controller-metadata-invalid' };
  }
  const current = existingController(host, owner);
  if (current.present) {
    return current.owned
      ? { installed: true, alreadyActive: true }
      : { installed: false, alreadyActive: false, reason: 'owner-conflict' };
  }
  if (typeof payload !== 'function') return { installed: false, alreadyActive: false, reason: ASSET_REASON };
  const controller = new PageController(host, payload, pageAdapter, owner, metadata, identification, playbackOwner);
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
