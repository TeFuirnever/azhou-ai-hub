/*
 * C source contract for tools/build-startup.py:
 *   extract exactly the top-level installAnimation function below and place it
 *   inside the trusted startup installer expression. Do not include the local
 *   preview adapter at the end of this file.
 *
 * Its only runtime inputs are the explicit PageController environment, SEND,
 * and frameSpec.assets = { avatar: PNG data URL, artwork: PNG data URL,
 * contours: [[[x, y], ...]], introTitle, introCaption, artworkSubtitle }.
 * It has no imports, ambient globals, host-page access, eval, or test switch.
 */
function installAnimation(
  window, document, location, performance, indexedDB, Image, Path2D, URL,
  requestAnimationFrame, cancelAnimationFrame, setTimeout, clearTimeout,
  module, SEND, frameSpec, createImageSettingsFactory, createLocalizationFactory,
) {
  'use strict';

  const WIDTH = 1536;
  const HEIGHT = 1024;
  const DURATION = 12000;
  const IDENTITY_RELEASE_MS = 4740;
  const TILE = 48;
  const MAX_PATHS = 1200;
  const MAX_POINTS = 300000;
  const READY_REASON = 'asset-invalid';
  const DATA_URL_PREFIX = 'data:image/png;base64,';
  const PROGRESS = [
    [0, 0], [0.12, 0.06], [0.35, 0.41], [0.56, 0.76],
    [0.66, 0.924], [0.72, 0.97], [0.77, 1], [1, 1],
  ];
  const FINAL_PROGRESS_PLATEAU_MS = DURATION * PROGRESS[PROGRESS.length - 2][0];
  let assets = frameSpec && frameSpec.assets;
  const defaultAssets = assets;
  const rootAppearance = frameSpec?.appearance || {};
  const nativeAppearance = window.__agentSkinAppearance || {};
  const initialLocale = normalizeLocale(rootAppearance.locale
    || nativeAppearance.locale || window.navigator?.language || document.documentElement?.lang);
  let localization = null;
  try {
    if (typeof createLocalizationFactory === 'function') {
      localization = createLocalizationFactory({ locale: initialLocale, themeConfig: assets?.themeConfig });
    }
  } catch {}
  let locale = initialLocale;
  const initialTheme = ['light', 'dark'].includes(rootAppearance.theme) ? rootAppearance.theme
    : ['light', 'dark'].includes(nativeAppearance.theme) ? nativeAppearance.theme
      : document.documentElement?.dataset?.theme === 'light' ? 'light' : 'dark';
  const defaultColors = initialTheme === 'light' ? {
    surface: '#ffffff', text: '#202123', muted: '#65666c', border: '#dedee3',
  } : {
    surface: '#10121c', text: '#fff8ef',
    muted: 'rgba(255, 248, 239, .72)', border: 'rgba(255, 248, 239, .18)',
  };
  const appearance = {
    locale,
    theme: initialTheme,
    colors: { ...defaultColors, ...sanitizeColors(rootAppearance.colors) },
  };
  function t(key, params = {}) {
    try {
      const translated = localization?.t?.(key, params);
      if (typeof translated === 'string' && translated !== key) return translated;
    } catch {}
    return String(key);
  }
  function normalizeLocale(value) {
    return typeof value === 'string' && /^zh(?:-|$)/i.test(value) ? 'zh-CN' : 'en';
  }
  function sanitizeColors(colors) {
    const result = {};
    for (const key of ['surface', 'text', 'muted', 'border']) {
      const value = colors?.[key];
      if (typeof value !== 'string' || value.length > 100 || /[;{}]/.test(value)) continue;
      const color = value.trim();
      if (!color) continue;
      if (window.CSS?.supports && !window.CSS.supports('color', color)) continue;
      result[key] = color;
    }
    return result;
  }
  const nativeHandler = Boolean(window.webkit?.messageHandlers?.launcher);
  const nativePreviewMode = nativeHandler && window.__agentSkinNativeMode === 'preview';
  const browserPreviewMode = location?.protocol === 'file:' && !nativeHandler;
  const isLocalPreview = frameSpec?.intent !== 'play'
    && Boolean(document.getElementById('timeline') && document.getElementById('preview-controls'))
    && (nativePreviewMode || browserPreviewMode);
  const nativePreview = isLocalPreview && nativeHandler;
  let titleUsesDefault = typeof assets?.introTitle !== 'string';
  let captionUsesDefault = typeof assets?.introCaption !== 'string';
  let subtitleUsesDefault = typeof assets?.artworkSubtitle !== 'string';
  let title = titleUsesDefault ? t('animation.title.default') : assets.introTitle;
  let caption = captionUsesDefault ? t('animation.caption.default') : assets.introCaption;
  let subtitle = subtitleUsesDefault ? t('animation.subtitle.default') : assets.artworkSubtitle;
  let subtitleLines = [];
  let subtitleFontSize = 39;
  let subtitleLineHeight = 36;
  let subtitlePanelX = 160;
  let subtitlePanelWidth = 1216;
  let subtitleTextWidth = 1120;
  let identitySafeWidth = 1330;
  let identityLayoutKey = '';
  let identityRenderedLayoutKey = '';
  let identityLayoutGeneration = 0;
  function createStageLabels() {
    return {
      pulse: t('animation.stage.pulse'), identity: t('animation.stage.identity'),
      dispersing: t('animation.stage.dispersing'), scattered: t('animation.stage.scattered'),
      drawing: t('animation.stage.drawing'), colorize: t('animation.stage.colorize'),
      portrait: t('animation.stage.portrait'), shutter: t('animation.stage.shutter'),
      complete: t('animation.stage.complete'),
    };
  }
  let STAGE_LABELS = createStageLabels();
  let rawAvatar = typeof assets?.avatar === 'string' ? assets.avatar : assets?.avatar?.dataURL;
  let rawArtwork = typeof assets?.artwork === 'string' ? assets.artwork : assets?.artwork?.dataURL;
  let contours = assets?.contours || assets?.artwork?.contours;
  const existingStage = document.querySelector('[data-agent-skin-stage]');

  let imageSettings = null;
  let settingsPreview = null;
  try {
    if (typeof createImageSettingsFactory === 'function') {
      imageSettings = createImageSettingsFactory({
        document, Image, URL, indexedDB, performance, setTimeout, clearTimeout,
        localization, appearanceAvatar: frameSpec?.assets?.entryAvatar,
        themeConfig: assets?.themeConfig,
        getAppearance: () => ({ ...appearance, reducedMotion: reduced,
          source: frameSpec?.intent === 'preview' ? 'preview' : 'official' }),
      });
    }
  } catch {}

  let root = existingStage;
  let canvas;
  let context;
  let skipButton;
  let stageText;
  let progressText;
  let timeline;
  let elapsedText;
  let pauseButton;
  let replayButton;
  let artworkImage = null;
  let avatarImage = null;
  let artworkBitmap = null;
  let avatarBitmap = null;
  let identityCanvas = null;
  let identityContext = null;
  let identityBitmap = null;
  let identityBitmapOwned = false;
  let lineCanvas = null;
  let lineContext = null;
  let cachedPaths = [];
  let pathFragments = [];
  let pathFragmentSpan = 18;
  let particles = [];
  let resizeObserver = null;
  let pixelRatioQuery = null;
  let pixelRatioListener = null;
  let mediaQuery = null;
  let mediaListener = null;
  let rafId = 0;
  const timeoutIds = new Set();
  let generation = 0;
  let seekRequestGeneration = 0;
  let elapsed = 0;
  let origin = 0;
  let lastFrame = 0;
  let lastUI = -1000;
  let lastStage = '';
  let loaded = false;
  let preparing = false;
  let disposed = false;
  let complete = false;
  let skipped = false;
  let played = false;
  let readySent = false;
  let startAfterPrepare = false;
  let reduced = false;
  let settingsLoadReason = '';
  let errorDetail = '';
  let scale = 1;
  let offsetX = 0;
  let offsetY = 0;
  let visibleLogicalWidth = WIDTH;
  let layoutKey = '';
  let lastStaticRenderKey = '';
  let appearanceRevision = 0;
  let pixelRatio = 1;
  let lastDuration = 0;
  let lastRAFTime = 0;
  let gapCount = 0;
  let drawCount = 0;
  let sceneRenderCount = 0;
  const gapSamples = new window.Float32Array(2048);
  const drawSamples = new window.Float32Array(2048);
  const releasedImages = new WeakSet();
  const closedBitmaps = new WeakSet();
  const resources = {
    createdImages: 0, releasedImages: 0, liveImages: 0,
    createdBitmaps: 0, releasedBitmaps: 0, liveBitmaps: 0,
    createdCanvases: 0, releasedCanvases: 0, liveCanvases: 0,
    createdPaths: 0, releasedPaths: 0, livePaths: 0,
    createdRAF: 0, cancelledRAF: 0, liveRAF: 0,
    createdObjectURLs: 0, revokedObjectURLs: 0, liveObjectURLs: 0,
  };

  function message(action, details = {}) {
    if (typeof SEND === 'function') {
      return SEND({ type: 'azhou-startup', action, runId: frameSpec?.runId, ...details });
    }
    const handler = window.webkit?.messageHandlers?.launcher;
    if (handler && typeof handler.postMessage === 'function') return handler.postMessage({ action, ...details });
    return undefined;
  }

  function clamp(value, low = 0, high = 1) {
    return Math.max(low, Math.min(high, value));
  }

  function fitSubtitle(visibleLogicalWidth) {
    subtitlePanelWidth = Math.max(260, Math.min(1216, visibleLogicalWidth - 32));
    subtitlePanelX = (WIDTH - subtitlePanelWidth) / 2;
    subtitleTextWidth = Math.max(224, subtitlePanelWidth - 36);
    const maxCharacters = Math.max(8, Math.floor(subtitleTextWidth / 32));
    subtitleLines = [];
    let line = '';
    for (const character of subtitle) {
      const punctuation = /^[，。！？；：、）》」』】]$/u.test(character);
      if (line && line.length + character.length > maxCharacters && punctuation) {
        subtitleLines.push(line + character);
        line = '';
      } else {
        if (line && line.length + character.length > maxCharacters) {
          subtitleLines.push(line);
          line = '';
        }
        line += character;
      }
    }
    if (line) subtitleLines.push(line);
    const narrow = visibleLogicalWidth < 650;
    subtitleFontSize = narrow ? 22 : subtitleLines.length > 1 ? 32 : 39;
    subtitleLineHeight = narrow ? 25 : 36;
  }

  function fitIdentity(visibleLogicalWidth) {
    const nextWidth = Math.max(240, Math.min(1330, visibleLogicalWidth - 48));
    const nextKey = String(Math.round(nextWidth));
    if (nextKey === identityLayoutKey) return false;
    identitySafeWidth = nextWidth;
    identityLayoutKey = nextKey;
    return true;
  }

  function smooth(value) {
    const amount = clamp(value);
    return amount * amount * (3 - 2 * amount);
  }

  function phaseAt(milliseconds) {
    if (milliseconds < 1150) return 'pulse';
    if (milliseconds < 4180) return 'identity';
    if (milliseconds < 4740) return 'dispersing';
    if (milliseconds < 5080) return 'scattered';
    if (milliseconds < 7180) return 'drawing';
    if (milliseconds < 7430) return 'colorize';
    if (milliseconds < 11000) return 'portrait';
    if (milliseconds < DURATION) return 'shutter';
    return 'complete';
  }

  function progressAt(milliseconds) {
    const position = clamp(milliseconds / DURATION);
    for (let index = 1; index < PROGRESS.length; index++) {
      const right = PROGRESS[index];
      if (position > right[0]) continue;
      const left = PROGRESS[index - 1];
      const local = (position - left[0]) / (right[0] - left[0]);
      return left[1] + (right[1] - left[1]) * smooth(local);
    }
    return 1;
  }

  function fixedReason() {
    return { reason: READY_REASON };
  }

  function createElement(tag, parent, attributes = {}) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes)) {
      if (name === 'text') node.textContent = value;
      else if (name === 'class') node.className = value;
      else node.setAttribute(name, value);
    }
    parent.appendChild(node);
    return node;
  }

  function setButtonLabel(button, key, prefix = '') {
    if (!button) return;
    const label = t(key);
    if (button === skipButton) {
      const textNode = Array.from(button.childNodes).find(node => node.nodeType === 3);
      const space = button.querySelector('kbd') ? ' ' : '';
      if (textNode) textNode.nodeValue = prefix + label + space;
      else button.insertBefore(document.createTextNode(prefix + label + space), button.firstChild);
    } else {
      button.textContent = prefix + label;
    }
    button.setAttribute('aria-label', label);
  }

  function refreshLocalizedUI() {
    STAGE_LABELS = createStageLabels();
    if (root) root.setAttribute('aria-label', t('animation.accessibility.root'));
    if (canvas) canvas.setAttribute('aria-label', t('animation.accessibility.canvas'));
    if (stageText) stageText.textContent = STAGE_LABELS[phaseAt(elapsed)];
    if (progressText) {
      progressText.setAttribute('aria-label', t('animation.accessibility.progress'));
      progressText.textContent = t('animation.progress', { percent: Math.round(progressAt(elapsed) * 100) });
    }
    if (skipButton) {
      skipButton.setAttribute('aria-label', t('animation.accessibility.skip'));
      setButtonLabel(skipButton, 'animation.control.skip');
    }
    if (timeline) timeline.setAttribute('aria-label', t('animation.accessibility.timeline'));
    if (elapsedText) elapsedText.textContent = t('animation.elapsed', {
      elapsed: (elapsed / 1000).toFixed(1), duration: (DURATION / 1000).toFixed(1),
    });
    if (pauseButton) setButtonLabel(pauseButton, rafId ? 'animation.control.pause' : 'animation.control.resume');
    if (replayButton) setButtonLabel(replayButton, 'animation.control.replay', '↻ ');
    const previewBrand = document.querySelector('[data-agent-skin-preview-brand]');
    const previewCaption = document.querySelector('[data-agent-skin-preview-caption]');
    if (previewBrand) previewBrand.textContent = t('animation.title.default');
    if (previewCaption) {
      previewCaption.textContent = `${t('animation.preview.title')} · ${t('animation.preview.canvas')}`;
    }
    if (document.title) document.title = `${t('animation.title.default')} · ${t('animation.preview.title')}`;
    if (root) {
      const currentStage = phaseAt(elapsed);
      root.dataset.stage = currentStage;
      lastStage = currentStage;
    }
  }

  function applyAppearanceStyles() {
    const docRoot = document.documentElement;
    if (!docRoot) return;
    docRoot.lang = appearance.locale;
    docRoot.dataset.theme = appearance.theme;
    docRoot.style.colorScheme = appearance.theme;
    for (const key of ['surface', 'text', 'muted', 'border']) {
      docRoot.style.setProperty(`--agent-skin-${key}`, appearance.colors[key]);
    }
    if (root) {
      root.dataset.theme = appearance.theme;
      for (const key of ['surface', 'text', 'muted', 'border']) {
        root.style.setProperty(`--agent-skin-${key}`, appearance.colors[key]);
      }
    }
  }

  function mountDOM() {
    if (!root) {
      root = document.createElement('section');
      root.setAttribute('data-agent-skin-stage', '');
      root.setAttribute('aria-label', t('animation.accessibility.root'));
      root.style.cssText = 'position:fixed;inset:0;overflow:hidden;background:var(--agent-skin-surface,#10121c);color:var(--agent-skin-text,#fff8ef);z-index:2147483647;font:16px/1.4 system-ui,sans-serif';
      document.body.appendChild(root);
    }
    root.dataset.duration = '12';
    root.dataset.prewarmed = 'false';
    root.dataset.coordinateSize = '1536x1024';
    root.dataset.mode = isLocalPreview ? 'preview' : 'launch';
    if (nativeHandler) document.body.classList.add('agent-skin-native');
    canvas = root.querySelector('canvas[data-agent-skin-canvas]');
    if (!canvas) canvas = createElement('canvas', root, {
      'data-agent-skin-canvas': '', 'data-coordinate-size': '1536x1024',
      'role': 'img', 'aria-label': t('animation.accessibility.canvas'),
    });
    canvas.dataset.coordinateSize = '1536x1024';
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block';
    context = canvas.getContext('2d', { alpha: false, desynchronized: true });
    if (!context) throw new Error('canvas-unavailable');

    stageText = root.querySelector('[data-agent-skin-stage-text]');
    if (!stageText) stageText = createElement('span', root, {
      'data-agent-skin-stage-text': '', 'aria-live': 'polite', 'text': t('animation.stage.pulse'),
    });
    stageText.style.cssText = 'position:absolute;left:50%;bottom:8%;transform:translateX(-50%);max-width:82vw;color:var(--agent-skin-text,#fff8ef);text-align:center;letter-spacing:.04em;text-shadow:0 2px 20px #17152d';

    progressText = root.querySelector('[data-agent-skin-progress]');
    if (!progressText) progressText = createElement('span', root, {
      'data-agent-skin-progress': '', 'aria-label': t('animation.accessibility.progress'), 'text': t('animation.progress', { percent: 0 }),
    });
    progressText.style.cssText = 'position:absolute;left:50%;bottom:4%;transform:translateX(-50%);color:var(--agent-skin-muted,#fff8ef);font:12px/1.2 system-ui,sans-serif;opacity:.92';

    skipButton = root.querySelector('[data-agent-skin-skip]');
    if (!skipButton) skipButton = createElement('button', root, {
      'data-agent-skin-skip': '', 'type': 'button', 'aria-label': t('animation.accessibility.skip'), 'text': t('animation.control.skip'),
    });
    skipButton.style.cssText = 'position:absolute;z-index:2;right:24px;top:20px;border:1px solid var(--agent-skin-border,rgba(255,255,255,.4));border-radius:999px;padding:8px 16px;background:var(--agent-skin-surface,#10121c);color:var(--agent-skin-text,#fff8ef);font:14px system-ui,sans-serif;cursor:pointer';

    timeline = isLocalPreview ? document.getElementById('timeline') : null;
    elapsedText = isLocalPreview ? document.getElementById('elapsed') : null;
    pauseButton = isLocalPreview ? document.getElementById('pause') : null;
    replayButton = isLocalPreview ? document.getElementById('replay') : null;
    const controls = document.getElementById('preview-controls');
    if (controls) controls.hidden = !isLocalPreview;
    applyAppearanceStyles();
    refreshLocalizedUI();
  }

  function updateLayout() {
    if (disposed || !canvas || !context) return;
    const rect = root.getBoundingClientRect();
    const width = Math.max(1, rect.width || window.innerWidth || WIDTH);
    const height = Math.max(1, rect.height || window.innerHeight || HEIGHT);
    const nextPixelRatio = Math.max(1, Number(window.devicePixelRatio) || 1);
    const pixelRatioChanged = pixelRatio !== nextPixelRatio;
    pixelRatio = nextPixelRatio;
    if (pixelRatioChanged) observePixelRatio(true);
    const backingWidth = Math.max(1, Math.ceil(width * pixelRatio));
    const backingHeight = Math.max(1, Math.ceil(height * pixelRatio));
    if (canvas.width !== backingWidth || canvas.height !== backingHeight) {
      canvas.width = backingWidth;
      canvas.height = backingHeight;
    }
    scale = Math.max(width / WIDTH, height / HEIGHT);
    offsetX = (width - WIDTH * scale) / 2;
    offsetY = (height - HEIGHT * scale) / 2;
    const nextVisibleLogicalWidth = Math.min(WIDTH, width / scale);
    visibleLogicalWidth = nextVisibleLogicalWidth;
    fitSubtitle(nextVisibleLogicalWidth);
    const identityLayoutChanged = fitIdentity(nextVisibleLogicalWidth);
    const nextLayoutKey = [width, height, pixelRatio, scale, offsetX, offsetY, nextVisibleLogicalWidth]
      .map(value => Number(value).toFixed(3)).join(':');
    if (nextLayoutKey !== layoutKey) {
      layoutKey = nextLayoutKey;
      lastStaticRenderKey = '';
    }
    if (loaded && identityLayoutChanged) {
      seekRequestGeneration++;
      renderIdentityBitmap(generation).catch(() => {});
    }
    if (loaded) drawAt(elapsed, false);
  }

  function installLayoutObserver() {
    if (typeof window.ResizeObserver === 'function') {
      resizeObserver = new window.ResizeObserver(updateLayout);
      try { resizeObserver.observe(root, { box: 'device-pixel-content-box' }); }
      catch { resizeObserver.observe(root); }
    }
    window.addEventListener('resize', updateLayout);
    window.visualViewport?.addEventListener('resize', updateLayout);
    observePixelRatio();
  }

  function observePixelRatio(rebind = false) {
    if (typeof window.matchMedia !== 'function') return;
    if (pixelRatioQuery && pixelRatioListener && !rebind) return;
    if (pixelRatioQuery && pixelRatioListener) {
      if (typeof pixelRatioQuery.removeEventListener === 'function') pixelRatioQuery.removeEventListener('change', pixelRatioListener);
      else if (typeof pixelRatioQuery.removeListener === 'function') pixelRatioQuery.removeListener(pixelRatioListener);
      pixelRatioQuery = null;
      pixelRatioListener = null;
    }
    const ratio = Math.max(1, Number(window.devicePixelRatio) || 1);
    const query = window.matchMedia(`(resolution: ${ratio}dppx)`);
    const changed = () => {
      if (pixelRatioQuery !== query) return;
      updateLayout();
      if (pixelRatioQuery === query) observePixelRatio(true);
    };
    pixelRatioQuery = query;
    pixelRatioListener = changed;
    if (typeof query.addEventListener === 'function') query.addEventListener('change', changed);
    else if (typeof query.addListener === 'function') query.addListener(changed);
  }

  function sortedStats(samples, count) {
    if (!count) return null;
    const values = [];
    for (let index = 0; index < count; index++) values.push(samples[index]);
    values.sort((a, b) => a - b);
    return {
      count,
      median: values[Math.floor(values.length * 0.5)],
      p95: values[Math.floor(values.length * 0.95)],
      max: values[values.length - 1],
    };
  }

  function report() {
    return {
      elapsed: elapsed / 1000,
      duration: DURATION / 1000,
      completed: complete,
      skipped,
      reduced,
      stage: phaseAt(elapsed),
      animationProgress: progressAt(elapsed),
      viewport: { width: canvas?.clientWidth || 0, height: canvas?.clientHeight || 0, dpr: pixelRatio },
      coordinateSize: { width: WIDTH, height: HEIGHT },
      resources: { ...resources, framesPending: rafId ? 1 : 0 },
      jsFrame: {
        sceneRenderCount,
        rafIntervalMs: sortedStats(gapSamples, gapCount),
        renderSubmissionMs: sortedStats(drawSamples, drawCount),
        scope: 'JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing',
      },
    };
  }

  function updateUI(milliseconds) {
    const stage = phaseAt(milliseconds);
    if (stage !== lastStage) {
      lastStage = stage;
      root.dataset.stage = stage;
      stageText.textContent = STAGE_LABELS[stage];
    }
    if (milliseconds - lastUI >= 60 || milliseconds === 0 || milliseconds === DURATION) {
      const progress = Math.round(progressAt(milliseconds) * 100);
      if (progressText) progressText.textContent = t('animation.progress', { percent: progress });
      if (elapsedText) elapsedText.textContent = t('animation.elapsed', {
        elapsed: (milliseconds / 1000).toFixed(1), duration: '12.0',
      });
      if (timeline) timeline.value = String(milliseconds / 1000);
      lastUI = milliseconds;
    }
  }

  function setWorldTransform() {
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = appearance.colors.surface;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.setTransform(pixelRatio * scale, 0, 0, pixelRatio * scale,
      pixelRatio * offsetX, pixelRatio * offsetY);
  }

  function drawPulse(milliseconds) {
    const pulse = reduced ? 0.5 : 0.25 + 0.75 * (0.5 + 0.5 * Math.sin(milliseconds / 180));
    context.strokeStyle = appearance.colors.text;
    context.globalAlpha = 0.18 + pulse * 0.3;
    context.lineWidth = 3;
    context.beginPath();
    context.arc(768, 442, 166 + pulse * 18, 0, Math.PI * 2);
    context.stroke();
    context.globalAlpha = 1;
    context.fillStyle = appearance.colors.text;
    context.font = '600 22px system-ui, sans-serif';
    context.textAlign = 'center';
    context.fillText(t('animation.title.default'), 768, 720);
  }

  function drawIdentity(alpha = 1) {
    const source = identityBitmap || identityCanvas;
    if (!source) return;
    context.globalAlpha = alpha;
    context.drawImage(source, 0, 0, WIDTH, HEIGHT);
    context.globalAlpha = 1;
  }

  function drawIdentityFragments(amount, scattered = false) {
    const source = identityBitmap || identityCanvas;
    if (!source) return;
    const progress = smooth(amount);
    context.globalAlpha = 1;
    for (let index = 0; index < particles.length; index++) {
      const item = particles[index];
      const drift = scattered ? 1 : progress;
      const x = item.sx + (item.scatterX - item.sx) * drift;
      const y = item.sy + (item.scatterY - item.sy) * drift;
      const opacity = scattered ? 0.95 : 1 - progress * 0.08;
      context.globalAlpha = opacity;
      context.drawImage(source, item.sx, item.sy, item.sw, item.sh, x, y, item.sw, item.sh);
    }
    context.globalAlpha = 1;
  }

  function drawReducedDispersal(amount) {
    const progress = smooth(amount);
    const source = identityBitmap || identityCanvas;
    if (source) {
      context.globalAlpha = 1 - progress;
      context.drawImage(source, 0, 0, WIDTH, HEIGHT);
    }
    drawPathFragments(1, true, progress);
    context.globalAlpha = 1;
  }

  function drawPathFragments(amount, staticOnly = false, alpha = 1) {
    const progress = clamp(amount);
    const front = 1.5 * progress - 0.25;
    const arrivalBand = clamp(pathFragmentSpan / WIDTH, 0.01, 0.12);
    context.strokeStyle = appearance.colors.text;
    context.lineWidth = 2.4;
    context.lineJoin = 'round';
    context.lineCap = 'round';
    for (let index = 0; index < pathFragments.length; index++) {
      const item = pathFragments[index];
      const localProgress = staticOnly ? 1 : smooth((front - item.centerX / WIDTH + arrivalBand) / (2 * arrivalBand));
      const x = staticOnly ? item.centerX : item.scatterX + (item.centerX - item.scatterX) * localProgress;
      const y = staticOnly ? item.centerY : item.scatterY + (item.centerY - item.scatterY) * localProgress;
      context.globalAlpha = alpha;
      context.save();
      context.translate(x, y);
      context.rotate(staticOnly ? 0 : item.rotation * (1 - localProgress));
      context.translate(-item.centerX, -item.centerY);
      context.stroke(item.path);
      context.restore();
    }
    context.globalAlpha = 1;
  }

  function drawArtwork(alpha = 1) {
    if (!artworkBitmap) return;
    context.globalAlpha = alpha;
    context.drawImage(artworkBitmap, 0, 0, WIDTH, HEIGHT);
    context.globalAlpha = 1;
  }

  function drawPortrait(milliseconds) {
    drawArtwork(1);
    context.fillStyle = 'rgba(18, 18, 32, .16)';
    context.fillRect(0, 0, WIDTH, HEIGHT);
    const progress = reduced ? progressAt(7430) : progressAt(milliseconds);
    context.fillStyle = appearance.colors.surface;
    context.globalAlpha = 0.88;
    context.fillRect(subtitlePanelX, 794, subtitlePanelWidth, 174);
    context.globalAlpha = 1;
    context.fillStyle = appearance.colors.text;
    context.textAlign = 'center';
    context.font = `600 ${subtitleFontSize}px system-ui, sans-serif`;
    const blockHeight = subtitleLines.length * subtitleLineHeight;
    const firstBaseline = 830 + Math.max(0, (122 - blockHeight) / 2) + subtitleFontSize;
    for (let index = 0; index < subtitleLines.length; index++) {
      context.fillText(subtitleLines[index], WIDTH / 2, firstBaseline + index * subtitleLineHeight, subtitleTextWidth);
    }
    const progressWidth = Math.min(756, subtitlePanelWidth * 0.65);
    const progressX = (WIDTH - progressWidth) / 2;
    context.fillStyle = appearance.colors.border;
    context.fillRect(progressX, 807, progressWidth, 4);
    context.fillStyle = appearance.colors.text;
    context.fillRect(progressX, 807, progressWidth * progress, 4);
  }

  function renderScene(milliseconds) {
    const phase = phaseAt(milliseconds);
    setWorldTransform();
    if (phase === 'pulse') {
      drawPulse(milliseconds);
    } else if (phase === 'identity') {
      drawIdentity(smooth((milliseconds - 1150) / 500));
    } else if (phase === 'dispersing') {
      const amount = (milliseconds - 4180) / 560;
      if (reduced) drawReducedDispersal(amount);
      else drawIdentityFragments(amount);
    } else if (phase === 'scattered') {
      if (reduced) drawPathFragments(1, true);
      else drawPathFragments(0);
    } else if (phase === 'drawing') {
      if (reduced) {
        const opacity = 0.78 + smooth((milliseconds - 5080) / 2100) * 0.22;
        drawPathFragments(1, true, opacity);
      } else {
        drawPathFragments((milliseconds - 5080) / 2100);
      }
    } else if (phase === 'colorize') {
      if (lineCanvas) context.drawImage(lineCanvas, 0, 0);
      drawArtwork(smooth((milliseconds - 7180) / 250));
    } else if (phase === 'portrait') {
      drawPortrait(milliseconds);
    } else {
      drawPortrait(milliseconds);
      const shutter = smooth((milliseconds - 11000) / 1000);
      context.fillStyle = appearance.colors.surface;
      if (reduced) {
        context.globalAlpha = shutter;
        context.fillRect(0, 0, WIDTH, HEIGHT);
        context.globalAlpha = 1;
      } else {
        context.fillRect(0, 0, WIDTH * shutter * 0.5, HEIGHT);
        context.fillRect(WIDTH * (1 - shutter * 0.5), 0, WIDTH * shutter * 0.5, HEIGHT);
      }
    }
  }

  function staticFrameKey(milliseconds) {
    const stage = phaseAt(milliseconds);
    const isStatic = (stage === 'pulse' && reduced)
      || (stage === 'identity' && milliseconds >= 1650)
      || stage === 'scattered'
      || (stage === 'portrait' && (reduced || milliseconds >= FINAL_PROGRESS_PLATEAU_MS));
    return isStatic
      ? `${stage}:${reduced ? 'reduced' : 'full'}:${appearanceRevision}:${layoutKey}`
      : '';
  }

  function drawAt(milliseconds, playbackFrame) {
    if (!context || disposed) return;
    elapsed = clamp(milliseconds, 0, DURATION);
    const stableKey = staticFrameKey(elapsed);
    if (!stableKey || stableKey !== lastStaticRenderKey) {
      const started = performance.now();
      renderScene(elapsed);
      sceneRenderCount++;
      const spent = Math.max(0, performance.now() - started);
      if (drawCount < drawSamples.length) drawSamples[drawCount++] = spent;
      lastStaticRenderKey = stableKey;
    }
    updateUI(elapsed);
    if (elapsed >= IDENTITY_RELEASE_MS) {
      seekRequestGeneration++;
      releaseIdentityBitmap();
    }
  }

  function stopClock() {
    if (!rafId) return;
    cancelAnimationFrame(rafId);
    rafId = 0;
    resources.cancelledRAF++;
    resources.liveRAF = 0;
  }

  function finish(isSkipped = false) {
    if (disposed || complete) return false;
    seekRequestGeneration++;
    if (isSkipped && preparing && !loaded) {
      generation++;
      preparing = false;
      startAfterPrepare = false;
    }
    stopClock();
    elapsed = DURATION;
    skipped = Boolean(isSkipped);
    complete = true;
    played = true;
    drawAt(DURATION, true);
    root.dataset.completed = 'true';
    root.classList.add('finished');
    const finalReport = report();
    releaseSceneResources();
    message('complete', { skipped, report: finalReport });
    return true;
  }

  function tick(now) {
    rafId = 0;
    resources.liveRAF = 0;
    if (disposed || complete || !loaded) return;
    const current = Number.isFinite(now) ? now : performance.now();
    elapsed = clamp(current - origin, 0, DURATION);
    if (lastRAFTime) {
      const gap = current - lastRAFTime;
      if (gapCount < gapSamples.length) gapSamples[gapCount++] = gap;
    }
    lastRAFTime = current;
    drawAt(elapsed, true);
    if (elapsed >= DURATION) {
      finish(false);
      return;
    }
    rafId = requestAnimationFrame(tick);
    resources.createdRAF++;
    resources.liveRAF = 1;
  }

  function startClock() {
    if (disposed || complete || !loaded || rafId) return false;
    played = true;
    origin = performance.now() - elapsed;
    lastRAFTime = 0;
    rafId = requestAnimationFrame(tick);
    resources.createdRAF++;
    resources.liveRAF = 1;
    root.dataset.playing = 'true';
    if (pauseButton) setButtonLabel(pauseButton, 'animation.control.pause');
    return true;
  }

  function pause() {
    if (disposed || !rafId) return false;
    stopClock();
    root.dataset.playing = 'false';
    if (pauseButton) setButtonLabel(pauseButton, 'animation.control.resume');
    return true;
  }

  function releaseIdentityBitmap() {
    const value = identityBitmap;
    if (!value) return;
    identityBitmap = null;
    if (identityBitmapOwned && typeof value.close === 'function') {
      value.close();
      resources.releasedBitmaps++;
      resources.liveBitmaps--;
    }
    identityBitmapOwned = false;
  }

  function closeBitmap(value) {
    if (!value || typeof value.close !== 'function' || closedBitmaps.has(value)) return;
    closedBitmaps.add(value);
    value.close();
    resources.releasedBitmaps++;
    resources.liveBitmaps--;
  }

  function releaseImage(value) {
    if (!value || releasedImages.has(value)) return;
    releasedImages.add(value);
    try { value.src = ''; } catch {}
    resources.releasedImages++;
    resources.liveImages--;
  }

  function clearCanvas(value) {
    if (!value) return;
    value.width = 0;
    value.height = 0;
    resources.releasedCanvases++;
    resources.liveCanvases--;
  }

  function releaseSceneResources() {
    releaseIdentityBitmap();
    closeBitmap(avatarBitmap);
    closeBitmap(artworkBitmap);
    avatarBitmap = null;
    artworkBitmap = null;
    if (avatarImage) releaseImage(avatarImage);
    if (artworkImage) releaseImage(artworkImage);
    avatarImage = null;
    artworkImage = null;
    clearCanvas(identityCanvas);
    clearCanvas(lineCanvas);
    identityCanvas = null;
    identityContext = null;
    lineCanvas = null;
    lineContext = null;
    resources.releasedPaths += cachedPaths.length;
    resources.livePaths -= cachedPaths.length;
    resources.releasedPaths += pathFragments.length;
    resources.livePaths -= pathFragments.length;
    cachedPaths.length = 0;
    pathFragments.length = 0;
    particles.length = 0;
    loaded = false;
  }

  function timeoutPromise(promise, milliseconds, generationAtStart, releaseLateValue) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const timeout = setTimeout(() => {
        if (settled) return;
        settled = true;
        timeoutIds.delete(timeout);
        reject(new Error('operation-timeout'));
      }, milliseconds);
      timeoutIds.add(timeout);
      Promise.resolve(promise).then(value => {
        if (settled) { releaseLateValue?.(value); return; }
        settled = true;
        clearTimeout(timeout);
        timeoutIds.delete(timeout);
        if (generationAtStart !== generation || disposed) {
          releaseLateValue?.(value);
          reject(new Error('operation-cancelled'));
        }
        else resolve(value);
      }, error => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        timeoutIds.delete(timeout);
        reject(error);
      });
    });
  }

  function decodeImage(source, expectedWidth, expectedHeight, generationAtStart) {
    const limit = expectedWidth === 512 ? 2 * 1024 * 1024 : 12 * 1024 * 1024;
    if (typeof source !== 'string' || !source.startsWith(DATA_URL_PREFIX) || source.length > limit) {
      return Promise.reject(new Error('asset-invalid'));
    }
    const image = new Image();
    resources.createdImages++;
    resources.liveImages++;
    image.src = source;
    const decoded = typeof image.decode === 'function'
      ? image.decode()
      : new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = () => reject(new Error('asset-invalid'));
      });
    return timeoutPromise(decoded, 4000, generationAtStart).then(() => {
      if (image.naturalWidth !== expectedWidth || image.naturalHeight !== expectedHeight) {
        releaseImage(image);
        throw new Error('asset-invalid');
      }
      return image;
    }, error => {
      releaseImage(image);
      throw error;
    });
  }

  function makeBitmap(source, generationAtStart) {
    if (typeof window.createImageBitmap !== 'function') return Promise.resolve(source);
    let operation;
    try { operation = window.createImageBitmap(source); }
    catch { return Promise.reject(new Error('asset-invalid')); }
    return timeoutPromise(operation, 10000, generationAtStart, bitmap => {
      if (typeof bitmap?.close !== 'function') return;
      resources.createdBitmaps++;
      resources.liveBitmaps++;
      closeBitmap(bitmap);
    }).then(bitmap => {
      resources.createdBitmaps++;
      resources.liveBitmaps++;
      return bitmap;
    });
  }

  function validateContours() {
    if (!Array.isArray(contours) || contours.length < 1 || contours.length > MAX_PATHS) throw new Error('asset-invalid');
    let pointCount = 0;
    let length = 0;
    for (let pathIndex = 0; pathIndex < contours.length; pathIndex++) {
      const points = contours[pathIndex];
      if (!Array.isArray(points) || points.length < 2) throw new Error('asset-invalid');
      pointCount += points.length;
      if (pointCount > MAX_POINTS) throw new Error('asset-invalid');
      let previousX = 0;
      let previousY = 0;
      for (let pointIndex = 0; pointIndex < points.length; pointIndex++) {
        const point = points[pointIndex];
        const x = Array.isArray(point) ? point[0] : point?.x;
        const y = Array.isArray(point) ? point[1] : point?.y;
        if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || x > WIDTH || y < 0 || y > HEIGHT) {
          throw new Error('asset-invalid');
        }
        if (pointIndex) length += Math.hypot(x - previousX, y - previousY);
        previousX = x;
        previousY = y;
      }
    }
    if (!(length > 0)) throw new Error('asset-invalid');
    return { pointCount, length };
  }

  function pointXY(point) {
    return Array.isArray(point) ? point : [point.x, point.y];
  }

  function preparePaths(stats) {
    lineCanvas = document.createElement('canvas');
    lineCanvas.width = WIDTH;
    lineCanvas.height = HEIGHT;
    resources.createdCanvases++;
    resources.liveCanvases++;
    lineContext = lineCanvas.getContext('2d', { alpha: true });
    if (!lineContext) throw new Error('asset-invalid');
    redrawLineCanvas();
  }

  function redrawLineCanvas() {
    if (!lineContext) return;
    for (let pathIndex = 0; pathIndex < contours.length; pathIndex++) {
      const points = contours[pathIndex];
      const path = new Path2D();
      const first = pointXY(points[0]);
      path.moveTo(first[0], first[1]);
      for (let pointIndex = 1; pointIndex < points.length; pointIndex++) {
        const current = pointXY(points[pointIndex]);
        path.lineTo(current[0], current[1]);
      }
      cachedPaths.push(path);
      resources.createdPaths++;
      resources.livePaths++;
    }
    lineContext.clearRect(0, 0, WIDTH, HEIGHT);
    lineContext.lineWidth = 2.4;
    lineContext.lineJoin = 'round';
    lineContext.lineCap = 'round';
    lineContext.strokeStyle = appearance.colors.text;
    for (let index = 0; index < cachedPaths.length; index++) lineContext.stroke(cachedPaths[index]);
    resources.releasedPaths += cachedPaths.length;
    resources.livePaths -= cachedPaths.length;
    cachedPaths.length = 0;
  }

  function seedUnit(index, salt) {
    let value = (0x51f15e + Math.imul(index + 1, 0x45d9f3b) + Math.imul(salt + 3, 0x27d4eb2d)) | 0;
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
    value ^= value >>> 16;
    return (value >>> 0) / 4294967296;
  }

  function finalizePathFragment(fragment) {
    if (!fragment || fragment.length <= 0 || fragment.points.length < 2) return;
    const midpoint = fragment.length / 2;
    let distance = 0;
    let centerX = fragment.points[0][0];
    let centerY = fragment.points[0][1];
    for (let index = 1; index < fragment.points.length; index++) {
      const from = fragment.points[index - 1];
      const to = fragment.points[index];
      const segmentLength = Math.hypot(to[0] - from[0], to[1] - from[1]);
      if (distance + segmentLength >= midpoint) {
        const fraction = segmentLength ? (midpoint - distance) / segmentLength : 0;
        centerX = from[0] + (to[0] - from[0]) * fraction;
        centerY = from[1] + (to[1] - from[1]) * fraction;
        break;
      }
      distance += segmentLength;
      centerX = to[0];
      centerY = to[1];
    }
    const index = pathFragments.length;
    const tile = particles[index % particles.length];
    if (!tile) throw new Error('asset-invalid');
    pathFragments.push({
      path: fragment.path,
      centerX,
      centerY,
      scatterX: tile.scatterX,
      scatterY: tile.scatterY,
      rotation: (seedUnit(index, 2) - 0.5) * 1.6,
    });
    resources.createdPaths++;
    resources.livePaths++;
  }

  function preparePathFragments(stats) {
    if (!particles.length) throw new Error('asset-invalid');
    const span = pathFragmentSpan = Math.max(18, stats.length / 1400);
    for (let pathIndex = 0; pathIndex < contours.length; pathIndex++) {
      const points = contours[pathIndex];
      let fragment = null;
      for (let pointIndex = 1; pointIndex < points.length; pointIndex++) {
        const from = pointXY(points[pointIndex - 1]);
        const to = pointXY(points[pointIndex]);
        const dx = to[0] - from[0];
        const dy = to[1] - from[1];
        const segmentLength = Math.hypot(dx, dy);
        if (!(segmentLength > 0)) continue;
        let consumed = 0;
        while (consumed < segmentLength) {
          const startX = from[0] + dx * (consumed / segmentLength);
          const startY = from[1] + dy * (consumed / segmentLength);
          if (!fragment) {
            const path = new Path2D();
            path.moveTo(startX, startY);
            fragment = { path, points: [[startX, startY]], length: 0 };
          }
          const remainingInFragment = span - fragment.length;
          const stepLength = Math.min(remainingInFragment, segmentLength - consumed);
          consumed += stepLength;
          fragment.length += stepLength;
          const endX = from[0] + dx * (consumed / segmentLength);
          const endY = from[1] + dy * (consumed / segmentLength);
          fragment.path.lineTo(endX, endY);
          fragment.points.push([endX, endY]);
          if (fragment.length >= span - 1e-6) {
            finalizePathFragment(fragment);
            fragment = null;
          }
        }
      }
      finalizePathFragment(fragment);
    }
    if (!pathFragments.length) throw new Error('asset-invalid');
  }

  function drawIdentityLayout() {
    if (!identityCanvas) {
      identityCanvas = document.createElement('canvas');
      identityCanvas.width = WIDTH;
      identityCanvas.height = HEIGHT;
      resources.createdCanvases++;
      resources.liveCanvases++;
      identityContext = identityCanvas.getContext('2d', { alpha: true });
    }
    if (!identityContext) throw new Error('asset-invalid');
    identityContext.clearRect(0, 0, WIDTH, HEIGHT);
    identityContext.save();
    const centerX = WIDTH / 2;
    const centerY = 378;
    const avatarSize = Math.min(512, Math.max(280, identitySafeWidth - 112));
    const avatarRadius = avatarSize / 2 - 14;
    const ringRadius = avatarSize / 2 + 2;
    const haloRadius = avatarSize / 2 + 14;
    identityContext.fillStyle = 'rgba(248, 211, 183, .14)';
    identityContext.beginPath();
    identityContext.arc(centerX, centerY, haloRadius, 0, Math.PI * 2);
    identityContext.fill();
    identityContext.save();
    identityContext.beginPath();
    identityContext.arc(centerX, centerY, avatarRadius, 0, Math.PI * 2);
    identityContext.clip();
    identityContext.drawImage(avatarBitmap, centerX - avatarSize / 2, centerY - avatarSize / 2, avatarSize, avatarSize);
    identityContext.restore();
    identityContext.strokeStyle = appearance.colors.text;
    identityContext.lineWidth = 4;
    identityContext.beginPath();
    identityContext.arc(centerX, centerY, ringRadius, 0, Math.PI * 2);
    identityContext.stroke();

    const textWidth = Math.max(192, identitySafeWidth - 24);
    const titleBaseline = centerY + haloRadius + 112;
    let titleFontSize = 82;
    if (title) {
      identityContext.font = `700 ${titleFontSize}px system-ui, sans-serif`;
      const measuredTitleWidth = identityContext.measureText(title).width;
      if (measuredTitleWidth > textWidth) {
        titleFontSize = Math.max(20, titleFontSize * textWidth / measuredTitleWidth);
      }
      identityContext.textAlign = 'center';
      identityContext.fillStyle = appearance.colors.text;
      identityContext.font = `700 ${titleFontSize}px system-ui, sans-serif`;
      identityContext.fillText(title, centerX, titleBaseline, textWidth);
    }

    if (caption) {
      const captionFontSize = 28;
      const captionLines = [];
      let line = '';
      identityContext.font = `600 ${captionFontSize}px system-ui, sans-serif`;
      for (const character of caption) {
        const candidate = line + character;
        const punctuation = /^[，。！？；：、）》」』】]$/u.test(character);
        if (line && identityContext.measureText(candidate).width > textWidth && punctuation) {
          captionLines.push(line + character);
          line = '';
        } else if (line && identityContext.measureText(candidate).width > textWidth) {
          captionLines.push(line);
          line = character;
        } else {
          line = candidate;
        }
      }
      if (line) captionLines.push(line);
      identityContext.fillStyle = appearance.colors.muted;
      identityContext.textAlign = 'center';
      const firstCaptionBaseline = title
        ? titleBaseline + Math.max(40, Math.min(64, titleFontSize * 0.78))
        : titleBaseline;
      for (let index = 0; index < captionLines.length; index++) {
        identityContext.fillText(captionLines[index], centerX,
          firstCaptionBaseline + index * 36, textWidth);
      }
    }
    identityContext.restore();
  }

  function buildIdentityFragments() {
    particles.length = 0;
    const pixels = identityContext.getImageData(0, 0, WIDTH, HEIGHT).data;
    for (let top = 96; top < 900; top += TILE) {
      for (let left = 96; left < WIDTH - 96; left += TILE) {
        let visible = false;
        for (let y = top; y < Math.min(top + TILE, 900) && !visible; y += 8) {
          for (let x = left; x < Math.min(left + TILE, WIDTH - 96); x += 8) {
            if (pixels[(y * WIDTH + x) * 4 + 3] > 16) { visible = true; break; }
          }
        }
        if (!visible) continue;
        const index = particles.length;
        const scatterX = clamp(left + TILE / 2 + (seedUnit(index, 0) - 0.5) * 390, 0, WIDTH);
        const scatterY = clamp(top + TILE / 2 + (seedUnit(index, 1) - 0.5) * 300, 0, HEIGHT);
        particles.push({
          sx: left, sy: top, sw: Math.min(TILE, WIDTH - left), sh: Math.min(TILE, HEIGHT - top),
          scatterX, scatterY,
        });
      }
    }
    if (!particles.length) throw new Error('asset-invalid');
    for (let index = 0; index < pathFragments.length; index++) {
      const particle = particles[index % particles.length];
      pathFragments[index].scatterX = particle.scatterX;
      pathFragments[index].scatterY = particle.scatterY;
    }

  }

  function renderIdentityBitmap(generationAtStart) {
    drawIdentityLayout();
    buildIdentityFragments();
    identityRenderedLayoutKey = identityLayoutKey;
    const layoutGeneration = ++identityLayoutGeneration;
    releaseIdentityBitmap();
    identityBitmap = identityCanvas;
    identityBitmapOwned = false;
    return makeBitmap(identityCanvas, generationAtStart).then(bitmap => {
      if (generationAtStart !== generation || layoutGeneration !== identityLayoutGeneration
          || identityRenderedLayoutKey !== identityLayoutKey || disposed) {
        if (bitmap !== identityCanvas) closeBitmap(bitmap);
        return false;
      }
      if (identityBitmap && identityBitmap !== identityCanvas) releaseIdentityBitmap();
      identityBitmap = bitmap;
      identityBitmapOwned = bitmap !== identityCanvas;
      if (loaded) drawAt(elapsed, false);
      return true;
    });
  }

  function prepareIdentityBitmap(generationAtStart) {
    return renderIdentityBitmap(generationAtStart);
  }

  function drawReducedDrawing(milliseconds) {
    const opacity = smooth((milliseconds - 5080) / 2100);
    if (lineCanvas) {
      context.globalAlpha = opacity;
      context.drawImage(lineCanvas, 0, 0);
      context.globalAlpha = 1;
    }
  }

  function releaseStaleTimeouts() {
    for (const timeout of timeoutIds) clearTimeout(timeout);
    timeoutIds.clear();
  }

  function applySettingsRecord(record, storedRecord) {
    if (!record || typeof record !== 'object') return;
    assets = record;
    rawAvatar = typeof record.avatar === 'string' ? record.avatar : record.avatar?.dataURL;
    rawArtwork = typeof record.artwork === 'string' ? record.artwork : record.artwork?.dataURL;
    contours = record.contours || record.artwork?.contours;
    const hasExplicitText = key => (settingsLoadReason === '' && typeof storedRecord?.[key] === 'string')
      || typeof defaultAssets?.[key] === 'string';
    titleUsesDefault = !hasExplicitText('introTitle');
    captionUsesDefault = !hasExplicitText('introCaption');
    subtitleUsesDefault = !hasExplicitText('artworkSubtitle');
    title = titleUsesDefault ? t('animation.title.default') : record.introTitle;
    caption = captionUsesDefault ? t('animation.caption.default') : record.introCaption;
    subtitle = subtitleUsesDefault ? t('animation.subtitle.default') : record.artworkSubtitle;
    fitSubtitle(visibleLogicalWidth);
    STAGE_LABELS = createStageLabels();
  }

  function showSettingsFallbackNotice() {
    if (!settingsLoadReason || !root) return;
    const notice = root.querySelector('[data-agent-skin-settings-result]')
      || createElement('div', root, { 'data-agent-skin-settings-result': '', role: 'status' });
    notice.textContent = t('settings.load.unavailable');
    notice.style.cssText = 'position:absolute;z-index:4;right:20px;top:18px;max-width:min(560px,calc(100vw - 40px));padding:10px 14px;border:1px solid var(--agent-skin-border,rgba(255,255,255,.18));border-radius:10px;background:var(--agent-skin-surface,#10121c);color:var(--agent-skin-text,#fff8ef);box-shadow:0 8px 28px #0006;font:14px/1.4 system-ui,sans-serif';
  }

  function clonePreviewAssets(record) {
    if (!record || typeof record !== 'object') return null;
    const cloneContours = values => Array.isArray(values)
      ? values.map(path => Array.isArray(path)
        ? path.map(point => Array.isArray(point) ? [point[0], point[1]] : point) : path)
      : values;
    const cloneAsset = value => value && typeof value === 'object' ? { ...value } : value;
    const assets = {
      ...record,
      avatar: cloneAsset(record.avatar),
      artwork: cloneAsset(record.artwork),
    };
    const contours = record.contours || record.artwork?.contours;
    if (Array.isArray(contours)) assets.contours = cloneContours(contours);
    if (assets.artwork && typeof assets.artwork === 'object' && Array.isArray(assets.artwork.contours)) {
      assets.artwork.contours = cloneContours(assets.artwork.contours);
    }
    return assets;
  }

  function finishSettingsPreview(session, started = false, restoreFocus = true) {
    if (!session || session.closed) return false;
    session.closed = true;
    if (settingsPreview === session) settingsPreview = null;
    if (session.timeout !== null) {
      try { clearTimeout(session.timeout); } catch {}
      session.timeout = null;
    }
    for (const target of session.inertTargets || []) {
      try { target.element.inert = target.inert; } catch {}
    }
    try { session.handle?.dispose(); } catch {}
    try { session.overlay?.remove(); } catch {}
    if (!session.startupSettled) {
      session.startupSettled = true;
      session.resolveStartup(started);
    }
    if (restoreFocus && !disposed && imageSettings?.isSettingsOpen()) {
      try { session.focusTarget?.focus?.(); } catch {}
    }
    return true;
  }

  function startSettingsPreview(draft) {
    if (disposed || !loaded || settingsPreview || !imageSettings?.isSettingsOpen()) return false;
    const dialog = document.body?.querySelector('[data-agent-skin-settings]');
    if (!dialog?.open || typeof document.createElement !== 'function') return false;
    const assets = clonePreviewAssets(draft);
    if (!assets) return false;

    const overlay = document.createElement('div');
    overlay.setAttribute('data-agent-skin-settings-preview', '');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', t('settings.button.previewAnimation'));
    overlay.style.cssText = 'position:fixed;z-index:2147483646;inset:0;overflow:hidden;background:#10121c';
    const iframe = document.createElement('iframe');
    iframe.setAttribute('data-agent-skin-settings-preview-frame', '');
    iframe.setAttribute('title', t('settings.button.previewAnimation'));
    iframe.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;border:0;background:#10121c';
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.setAttribute('data-agent-skin-settings-preview-close', '');
    closeButton.setAttribute('aria-label', t('settings.button.closePreview'));
    closeButton.textContent = t('settings.button.closePreview');
    closeButton.style.cssText = 'position:fixed;z-index:2;top:20px;right:24px;border:1px solid rgba(255,255,255,.4);border-radius:999px;padding:8px 16px;background:#10121c;color:#fff8ef;font:14px system-ui,sans-serif;cursor:pointer';
    overlay.append(iframe, closeButton);

    let resolveStartup;
    const startup = new Promise(resolve => { resolveStartup = resolve; });
    const session = {
      overlay, iframe, closeButton, focusTarget: dialog.querySelector('[data-agent-skin-preview-animation]')
        || document.activeElement,
      inertTargets: Array.from(dialog.children || []).map(element => ({ element, inert: element.inert })),
      handle: null, timeout: null, closed: false, started: false,
      startupSettled: false, resolveStartup,
    };
    settingsPreview = session;
    for (const target of session.inertTargets) target.element.inert = true;
    closeButton.addEventListener('click', () => finishSettingsPreview(session, session.started));
    dialog.appendChild(overlay);
    closeButton.focus?.();

    const onFrameFailure = () => finishSettingsPreview(session, false);
    const onFrameLoad = () => {
      if (session.closed || disposed) { finishSettingsPreview(session, false, false); return; }
      const previewWindow = iframe.contentWindow;
      const previewDocument = iframe.contentDocument || previewWindow?.document;
      if (!previewWindow || !previewDocument?.body) { onFrameFailure(); return; }
      try {
        const sendPreview = payload => {
          if (payload?.action === 'background') return undefined;
          if (payload?.action === 'ready') {
            session.started = true;
            if (session.timeout !== null) {
              try { clearTimeout(session.timeout); } catch {}
              session.timeout = null;
            }
            if (!session.startupSettled) {
              session.startupSettled = true;
              session.resolveStartup(true);
            }
          } else if (payload?.action === 'assetError') finishSettingsPreview(session, false);
          else if (payload?.action === 'complete') finishSettingsPreview(session, session.started);
          return undefined;
        };
        session.handle = installAnimation(
          previewWindow, previewDocument, previewWindow.location, previewWindow.performance,
          previewWindow.indexedDB, previewWindow.Image, previewWindow.Path2D, previewWindow.URL,
          previewWindow.requestAnimationFrame?.bind(previewWindow),
          previewWindow.cancelAnimationFrame?.bind(previewWindow),
          previewWindow.setTimeout?.bind(previewWindow), previewWindow.clearTimeout?.bind(previewWindow),
          undefined, sendPreview,
          {
            runId: `${frameSpec?.runId || 'settings'}-preview`, intent: 'preview',
            protocolVersion: 1, assets,
            appearance: { ...appearance, colors: { ...appearance.colors }, reducedMotion: reduced },
          }, undefined, createLocalizationFactory,
        );
        if (session.closed) { session.handle.dispose(); return; }
        if (!session.handle?.preview?.beginLaunch?.()) onFrameFailure();
      } catch { onFrameFailure(); }
    };
    iframe.addEventListener('load', onFrameLoad, { once: true });
    iframe.addEventListener('error', onFrameFailure, { once: true });
    try {
      iframe.srcdoc = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;overflow:hidden"></body></html>';
      session.timeout = setTimeout(() => finishSettingsPreview(session, false), 10_000);
    } catch { onFrameFailure(); }
    return startup;
  }

  function applySavedWallpaper(saved) {
    if (disposed) return Promise.resolve({ applied: false, reason: 'apply-unavailable' });
    const image = typeof saved?.artwork === 'string' ? saved.artwork : saved?.artwork?.dataURL;
    if (!image) return Promise.resolve({ applied: false, reason: 'asset-invalid' });
    let result;
    try {
      result = message('background', {
        image,
        strength: Number.isInteger(saved?.wallpaperStrength) ? saved.wallpaperStrength : 42,
      });
    } catch {
      return Promise.resolve({ applied: false, reason: 'apply-failed' });
    }
    return Promise.resolve(result).then(value => {
      if (value?.reason === 'disabled') return { ...value, applied: true };
      if (typeof value?.applied === 'boolean') return value;
      return { applied: false, reason: 'apply-unavailable' };
    }, () => ({ applied: false, reason: 'apply-failed' }));
  }

  async function prepare(currentGeneration) {
    if (disposed || currentGeneration !== generation) return;
    preparing = true;
    if (imageSettings) {
      try {
        const loadedSettings = await imageSettings.load(defaultAssets);
        if (disposed || currentGeneration !== generation) return;
        settingsLoadReason = typeof loadedSettings?.reason === 'string' ? loadedSettings.reason : '';
        applySettingsRecord(loadedSettings.settings, loadedSettings.baseline);
      } catch {
        if (disposed || currentGeneration !== generation) return;
        settingsLoadReason = 'settings-unavailable';
        applySettingsRecord(defaultAssets);
      }
    }
    const stats = validateContours();
    const decodeResults = await Promise.allSettled([
      decodeImage(rawAvatar, 512, 512, currentGeneration),
      decodeImage(rawArtwork, WIDTH, HEIGHT, currentGeneration),
    ]);
    const decoded = decodeResults.map(result => result.status === 'fulfilled' ? result.value : null);
    const decodeFailure = decodeResults.find(result => result.status === 'rejected');
    if (decodeFailure) {
      for (const image of decoded) releaseImage(image);
      throw decodeFailure.reason;
    }
    if (disposed || currentGeneration !== generation) {
      releaseImage(decoded[0]);
      releaseImage(decoded[1]);
      return;
    }
    avatarImage = decoded[0];
    artworkImage = decoded[1];
    const bitmapResults = await Promise.allSettled([
      makeBitmap(avatarImage, currentGeneration),
      makeBitmap(artworkImage, currentGeneration),
    ]);
    const images = bitmapResults.map(result => result.status === 'fulfilled' ? result.value : null);
    const bitmapFailure = bitmapResults.find(result => result.status === 'rejected');
    if (bitmapFailure) {
      for (let index = 0; index < bitmapResults.length; index++) {
        const result = bitmapResults[index];
        if (result.status === 'fulfilled' && result.value !== decoded[index]) closeBitmap(result.value);
        releaseImage(decoded[index]);
      }
      avatarImage = null;
      artworkImage = null;
      throw bitmapFailure.reason;
    }
    if (disposed || currentGeneration !== generation) {
      if (images[0] !== avatarImage) closeBitmap(images[0]); else releaseImage(images[0]);
      if (images[1] !== artworkImage) closeBitmap(images[1]); else releaseImage(images[1]);
      return;
    }
    avatarBitmap = images[0];
    artworkBitmap = images[1];
    if (avatarBitmap !== avatarImage) { releaseImage(avatarImage); avatarImage = null; }
    if (artworkBitmap !== artworkImage) { releaseImage(artworkImage); artworkImage = null; }
    const lineAppearanceRevision = appearanceRevision;
    preparePaths(stats);
    let preparedAppearanceRevision;
    do {
      preparedAppearanceRevision = appearanceRevision;
      await prepareIdentityBitmap(currentGeneration);
      if (disposed || currentGeneration !== generation) return;
    } while (identityRenderedLayoutKey !== identityLayoutKey
      || preparedAppearanceRevision !== appearanceRevision);
    if (disposed || currentGeneration !== generation) return;
    if (lineAppearanceRevision !== appearanceRevision) redrawLineCanvas();
    preparePathFragments(stats);
    loaded = true;
    preparing = false;
    releaseStaleTimeouts();
    updateLayout();
    drawAt(elapsed, false);
    root.dataset.prewarmed = 'true';
    showSettingsFallbackNotice();
    if (!readySent) {
      readySent = true;
      message('ready', { duration: DURATION, locale: localization?.locale || locale });
    }
    if (frameSpec?.intent === 'play') {
      try {
        message('background', {
          image: rawArtwork,
          strength: Number.isInteger(assets?.wallpaperStrength) ? assets.wallpaperStrength : 42,
        });
      } catch {}
    }
    if (frameSpec?.intent === 'settings') openSettingsPanel();
    if (frameSpec?.intent === 'play' || startAfterPrepare || (isLocalPreview && !nativePreview)) startClock();
  }

  function beginPrepare() {
    if (preparing || loaded || disposed) return;
    const currentGeneration = ++generation;
    preparing = true;
    Promise.resolve().then(() => prepare(currentGeneration)).catch(() => {
      if (disposed || currentGeneration !== generation) return;
      preparing = false;
      releaseStaleTimeouts();
      releaseSceneResources();
      message('assetError', fixedReason());
    });
  }

  function seek(seconds) {
    if (disposed || !loaded) return false;
    const requestGeneration = ++seekRequestGeneration;
    pause();
    const target = clamp(Number(seconds) * 1000, 0, DURATION);
    if (target < IDENTITY_RELEASE_MS && !identityBitmap && identityCanvas) {
      const currentGeneration = generation;
      const layoutGeneration = identityLayoutGeneration;
      makeBitmap(identityCanvas, currentGeneration).then(bitmap => {
        if (disposed || currentGeneration !== generation || requestGeneration !== seekRequestGeneration
            || elapsed >= IDENTITY_RELEASE_MS || layoutGeneration !== identityLayoutGeneration) {
          if (bitmap !== identityCanvas) closeBitmap(bitmap);
          return;
        }
        if (identityBitmap && identityBitmap !== identityCanvas) releaseIdentityBitmap();
        identityBitmap = bitmap;
        identityBitmapOwned = bitmap !== identityCanvas;
        lastStaticRenderKey = '';
        drawAt(elapsed, false);
      }).catch(() => {});
    }
    elapsed = target;
    complete = false;
    skipped = false;
    root.dataset.completed = 'false';
    drawAt(elapsed, false);
    return true;
  }

  function replay() {
    if (disposed) return false;
    seekRequestGeneration++;
    if (loaded && !played && !complete && elapsed === 0) {
      startClock();
      return true;
    }
    if (preparing) { startAfterPrepare = true; return true; }
    pause();
    releaseSceneResources();
    complete = false;
    skipped = false;
    played = false;
    elapsed = 0;
    lastUI = -1000;
    lastStage = '';
    gapCount = 0;
    drawCount = 0;
    sceneRenderCount = 0;
    lastRAFTime = 0;
    startAfterPrepare = true;
    root.dataset.completed = 'false';
    root.classList.remove('finished');
    root.dataset.prewarmed = 'false';
    beginPrepare();
    return true;
  }

  function beginLaunch() {
    if (disposed || complete) return false;
    document.body.classList.add('agent-skin-native-launch');
    root.dataset.mode = 'launch';
    startAfterPrepare = true;
    return startClock() || preparing;
  }

  function promoteLaunch() {
    if (disposed || complete) return false;
    document.body.classList.add('agent-skin-native-launch');
    root.dataset.mode = 'launch';
    if (pauseButton) pauseButton.disabled = true;
    if (timeline) timeline.disabled = true;
    return true;
  }

  function showError(text) {
    errorDetail = text === undefined || text === null ? '' : String(text);
    const panel = root.querySelector('[data-agent-skin-error]')
      || createElement('div', root, { 'data-agent-skin-error': '', role: 'alert' });
    panel.replaceChildren();
    const heading = createElement('strong', panel, {
      'data-agent-skin-error-title': '', 'text': t('animation.error.title'),
    });
    const body = createElement('div', panel, {
      'data-agent-skin-error-body': '', 'text': errorDetail || t('animation.error.body'),
    });
    heading.style.display = 'block';
    body.style.marginTop = '6px';
    panel.style.cssText = 'position:absolute;z-index:3;left:50%;top:50%;transform:translate(-50%,-50%);max-width:min(700px,90vw);padding:18px 22px;border:1px solid var(--agent-skin-border,rgba(255,255,255,.18));border-radius:12px;background:var(--agent-skin-surface,#10121c);color:var(--agent-skin-text,#fff8ef);text-align:center;box-shadow:0 12px 40px #0008';
  }

  function openSettingsPanel() {
    if (disposed || complete || !loaded || !readySent || !imageSettings
      || frameSpec?.intent === 'preview' || imageSettings.isSettingsOpen()) return false;
    const wasPlaying = rafId !== 0;
    if (wasPlaying) pause();
    const chrome = [skipButton, stageText, progressText];
    const priorHidden = chrome.map(element => element?.hidden);
    const restoreChrome = () => chrome.forEach((element, index) => {
      if (element) element.hidden = priorHidden[index];
    });
    let opened;
    try {
      opened = imageSettings.openSettings({
        onOpen() {
          chrome.forEach(element => { if (element) element.hidden = true; });
          if (frameSpec?.intent === 'play') message('settings-open');
        },
        onPreview(draft) { return startSettingsPreview(draft); },
        onApply(saved) {
          finishSettingsPreview(settingsPreview, settingsPreview?.started, false);
          return applySavedWallpaper(saved);
        },
        onCancel() {
          finishSettingsPreview(settingsPreview, false, false);
          finish(true);
        },
        onSaved() {
          if (disposed) return;
          finishSettingsPreview(settingsPreview, settingsPreview?.started, false);
          stopClock();
          generation++;
          preparing = false;
          releaseSceneResources();
          message('settings-close');
        },
      });
    } catch (error) {
      restoreChrome();
      throw error;
    }
    if (!opened) restoreChrome();
    if (!opened && wasPlaying && !disposed) startClock();
    return opened;
  }

  function onSkip() {
    finish(true);
  }

  function onKeydown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      if (frameSpec?.intent === 'settings' && !readySent) return;
      if (settingsPreview) {
        event.stopImmediatePropagation?.();
        finishSettingsPreview(settingsPreview, settingsPreview.started);
        return;
      }
      if (imageSettings?.isSettingsOpen()) {
        if (imageSettings.isBusy()) {
          event.stopImmediatePropagation?.();
          return;
        }
        imageSettings.cancelSettings();
        return;
      }
      finish(true);
      return;
    }
    if (isLocalPreview && event.code === 'Space'
      && !['BUTTON', 'INPUT', 'TEXTAREA'].includes(event.target?.tagName)) {
      event.preventDefault();
      if (rafId) pause(); else startClock();
    }
  }

  function onTimeline() {
    seek(Number(timeline.value));
  }

  function onPause() {
    if (rafId) pause(); else startClock();
  }

  function setReduced(value) {
    reduced = Boolean(value);
    imageSettings?.refreshAppearance?.();
    if (loaded) drawAt(elapsed, false);
  }

  function redrawIdentityForAppearance() {
    if (!loaded || !identityCanvas || !avatarBitmap) return;
    seekRequestGeneration++;
    identityLayoutGeneration++;
    drawIdentityLayout();
    buildIdentityFragments();
    identityRenderedLayoutKey = identityLayoutKey;
    releaseIdentityBitmap();
    identityBitmap = identityCanvas;
    identityBitmapOwned = false;
  }

  function updateAppearance(nextAppearance) {
    if (disposed || !nextAppearance || typeof nextAppearance !== 'object') return false;
    if (typeof nextAppearance.reducedMotion === 'boolean' && nextAppearance.reducedMotion !== reduced) {
      setReduced(nextAppearance.reducedMotion);
    }
    let changed = false;
    let localeChanged = false;
    if (typeof nextAppearance.locale === 'string') {
      const nextLocale = normalizeLocale(nextAppearance.locale);
      if (nextLocale !== locale) {
        locale = nextLocale;
        appearance.locale = nextLocale;
        try { localization?.setLocale?.(nextLocale); } catch {}
        if (titleUsesDefault) title = t('animation.title.default');
        if (captionUsesDefault) caption = t('animation.caption.default');
        if (subtitleUsesDefault) subtitle = t('animation.subtitle.default');
        fitSubtitle(visibleLogicalWidth);
        STAGE_LABELS = createStageLabels();
        localeChanged = true;
        changed = true;
      }
    }
    if (nextAppearance.theme === 'light' || nextAppearance.theme === 'dark') {
      if (appearance.theme !== nextAppearance.theme) {
        appearance.theme = nextAppearance.theme;
        changed = true;
      }
    }
    const nextColors = sanitizeColors(nextAppearance.colors);
    for (const key of ['surface', 'text', 'muted', 'border']) {
      if (nextColors[key] && nextColors[key] !== appearance.colors[key]) {
        appearance.colors[key] = nextColors[key];
        changed = true;
      }
    }
    applyAppearanceStyles();
    refreshLocalizedUI();
    if (settingsPreview && !settingsPreview.closed) {
      const previewLabel = t('settings.button.previewAnimation');
      const closeLabel = t('settings.button.closePreview');
      settingsPreview.overlay.setAttribute('aria-label', previewLabel);
      settingsPreview.iframe.setAttribute('title', previewLabel);
      settingsPreview.closeButton.setAttribute('aria-label', closeLabel);
      settingsPreview.closeButton.textContent = closeLabel;
      try { settingsPreview.handle?.updateAppearance(nextAppearance); } catch {}
    }
    imageSettings?.refreshAppearance?.();
    if (changed) {
      appearanceRevision++;
      lastStaticRenderKey = '';
      if (loaded) {
        if (localeChanged || nextColors.text || nextColors.muted) redrawIdentityForAppearance();
        if (nextColors.text) redrawLineCanvas();
        drawAt(elapsed, false);
      }
      if (root?.querySelector('[data-agent-skin-settings-result]')) showSettingsFallbackNotice();
      if (errorDetail || root?.querySelector('[data-agent-skin-error]')) showError(errorDetail);
    }
    return true;
  }

  function onMotionChange(event) {
    setReduced(event.matches);
  }

  function dispose() {
    if (disposed) return false;
    disposed = true;
    finishSettingsPreview(settingsPreview, false, false);
    generation++;
    seekRequestGeneration++;
    stopClock();
    releaseStaleTimeouts();
    skipButton?.removeEventListener('click', onSkip);
    timeline?.removeEventListener('input', onTimeline);
    pauseButton?.removeEventListener('click', onPause);
    replayButton?.removeEventListener('click', replay);
    window.removeEventListener('keydown', onKeydown, true);
    if (mediaQuery && mediaListener) {
      if (typeof mediaQuery.removeEventListener === 'function') mediaQuery.removeEventListener('change', mediaListener);
      else if (typeof mediaQuery.removeListener === 'function') mediaQuery.removeListener(mediaListener);
    }
    if (pixelRatioQuery && pixelRatioListener) {
      if (typeof pixelRatioQuery.removeEventListener === 'function') pixelRatioQuery.removeEventListener('change', pixelRatioListener);
      else if (typeof pixelRatioQuery.removeListener === 'function') pixelRatioQuery.removeListener(pixelRatioListener);
    }
    resizeObserver?.disconnect();
    window.removeEventListener('resize', updateLayout);
    window.visualViewport?.removeEventListener('resize', updateLayout);
    releaseSceneResources();
    try { imageSettings?.dispose(); } catch {}
    return true;
  }

  function drawAtPhase(milliseconds) {
    drawAt(milliseconds, false);
    return phaseAt(milliseconds);
  }

  function buildHandle() {
    const preview = {
      replay, seek, pause, resume: startClock, skip: onSkip, setReduced, report,
      beginLaunch, promoteLaunch,
      waiting() { if (stageText) stageText.textContent = t('animation.waiting'); },
      updateAppearance,
      error: showError,
    };
    return {
      dispose,
      openSettings: openSettingsPanel,
      updateAppearance,
      preview,
    };
  }

  if (!localization || typeof localization.t !== 'function') {
    message('assetError', { reason: 'localization-unavailable' });
    try { imageSettings?.dispose(); } catch {}
    return { dispose: () => false };
  }

  try {
    mountDOM();
    installLayoutObserver();
    skipButton.addEventListener('click', onSkip);
    window.addEventListener('keydown', onKeydown, true);
    if (timeline) timeline.addEventListener('input', onTimeline);
    if (pauseButton) pauseButton.addEventListener('click', onPause);
    if (replayButton) replayButton.addEventListener('click', replay);
    mediaQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    reduced = mediaQuery?.matches === true;
    if (mediaQuery) {
      mediaListener = onMotionChange;
      if (typeof mediaQuery.addEventListener === 'function') mediaQuery.addEventListener('change', mediaListener);
      else if (typeof mediaQuery.addListener === 'function') mediaQuery.addListener(mediaListener);
    }
    updateLayout();
  } catch {
    message('assetError', fixedReason());
    return { dispose: () => false };
  }

  const handle = buildHandle();
  if (nativeHandler || isLocalPreview) window.launcherUI = handle.preview;
  beginPrepare();
  return handle;
}

/* Local preview adapter. Ticket 05 extracts only installAnimation above. */
if (typeof window !== 'undefined' && typeof document !== 'undefined'
  && document.getElementById('preview-controls') && document.getElementById('timeline')) {
  const environment = window;
  const sendPreview = message => {
    const handler = environment.webkit?.messageHandlers?.launcher;
    if (handler && typeof handler.postMessage === 'function') handler.postMessage(message);
  };
  const settings = environment.AGENT_SKIN_ASSETS || null;
  const localHandle = installAnimation(
    environment, document, environment.location, environment.performance, environment.indexedDB,
    environment.Image, environment.Path2D, environment.URL,
    environment.requestAnimationFrame.bind(environment), environment.cancelAnimationFrame.bind(environment),
    environment.setTimeout.bind(environment), environment.clearTimeout.bind(environment),
    undefined, sendPreview,
    Object.freeze({ runId: 'local-preview', intent: 'preview', protocolVersion: 1, assets: settings }),
    environment.createImageSettings, environment.createLocalization,
  );
  if (!environment.webkit?.messageHandlers?.launcher) {
    environment.launcherUI = Object.assign(localHandle.preview, { dispose: localHandle.dispose });
  }
}
