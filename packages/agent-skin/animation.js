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
  module, SEND, frameSpec,
) {
  'use strict';

  const WIDTH = 1536;
  const HEIGHT = 1024;
  const DURATION = 12000;
  const IDENTITY_RELEASE_MS = 5080;
  const TILE = 48;
  const MAX_PATHS = 1200;
  const MAX_POINTS = 300000;
  const READY_REASON = 'asset-invalid';
  const DATA_URL_PREFIX = 'data:image/png;base64,';
  const PROGRESS = [
    [0, 0], [0.12, 0.06], [0.35, 0.41], [0.56, 0.76],
    [0.66, 0.924], [0.72, 0.97], [0.77, 1], [1, 1],
  ];
  const assets = frameSpec && frameSpec.assets;
  const nativeHandler = Boolean(window.webkit?.messageHandlers?.launcher);
  const nativePreviewMode = nativeHandler && window.__agentSkinNativeMode === 'preview';
  const browserPreviewMode = location?.protocol === 'file:' && !nativeHandler;
  const isLocalPreview = frameSpec?.intent !== 'play'
    && Boolean(document.getElementById('timeline') && document.getElementById('preview-controls'))
    && (nativePreviewMode || browserPreviewMode);
  const nativePreview = isLocalPreview && nativeHandler;
  const title = typeof assets?.introTitle === 'string' ? assets.introTitle : '阿舟的 Agent 实验室';
  const caption = typeof assets?.introCaption === 'string' ? assets.introCaption : 'AZHOU / AGENT LAB';
  const subtitle = typeof assets?.artworkSubtitle === 'string' ? assets.artworkSubtitle : '和阿舟一起，把想法做出来。';
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
  const STAGE_LABELS = {
    pulse: '实验室正在亮起来', identity: '阿舟正在准备工作台', dispersing: '头像与文字散成线稿',
    scattered: '线稿正在汇聚', drawing: '阿舟和背景正在显现', colorize: '同一幅画面正在上色',
    portrait: subtitle, shutter: '动画即将结束', complete: '已结束',
  };
  const rawAvatar = typeof assets?.avatar === 'string' ? assets.avatar : assets?.avatar?.dataURL;
  const rawArtwork = typeof assets?.artwork === 'string' ? assets.artwork : assets?.artwork?.dataURL;
  const contours = assets?.contours || assets?.artwork?.contours;
  const existingStage = document.querySelector('[data-agent-skin-stage]');

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
  let particles = [];
  let particleTargets = [];
  let resizeObserver = null;
  let pixelRatioQuery = null;
  let pixelRatioListener = null;
  let mediaQuery = null;
  let mediaListener = null;
  let rafId = 0;
  const timeoutIds = new Set();
  let generation = 0;
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
  let scale = 1;
  let offsetX = 0;
  let offsetY = 0;
  let pixelRatio = 1;
  let lastDuration = 0;
  let lastRAFTime = 0;
  let gapCount = 0;
  let drawCount = 0;
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
      SEND({ type: 'azhou-startup', action, runId: frameSpec?.runId, ...details });
      return;
    }
    const handler = window.webkit?.messageHandlers?.launcher;
    if (handler && typeof handler.postMessage === 'function') handler.postMessage({ action, ...details });
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

  function mountDOM() {
    if (!root) {
      root = document.createElement('section');
      root.setAttribute('data-agent-skin-stage', '');
      root.setAttribute('aria-label', 'Agent Skin 启动动画');
      root.style.cssText = 'position:fixed;inset:0;overflow:hidden;background:#10121c;color:#fff8ef;z-index:2147483647;font:16px/1.4 system-ui,sans-serif';
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
      'role': 'img', 'aria-label': '阿舟头像与同一背景线稿构成的启动动画',
    });
    canvas.dataset.coordinateSize = '1536x1024';
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block';
    context = canvas.getContext('2d', { alpha: false, desynchronized: true });
    if (!context) throw new Error('canvas-unavailable');

    stageText = root.querySelector('[data-agent-skin-stage-text]');
    if (!stageText) stageText = createElement('span', root, {
      'data-agent-skin-stage-text': '', 'aria-live': 'polite', 'text': '实验室正在亮起来',
    });
    stageText.style.cssText = 'position:absolute;left:50%;bottom:8%;transform:translateX(-50%);max-width:82vw;color:#fff8ef;text-align:center;letter-spacing:.04em;text-shadow:0 2px 20px #17152d';

    progressText = root.querySelector('[data-agent-skin-progress]');
    if (!progressText) progressText = createElement('span', root, {
      'data-agent-skin-progress': '', 'aria-label': '动画进度', 'text': '动画进度 0%',
    });
    progressText.style.cssText = 'position:absolute;left:50%;bottom:4%;transform:translateX(-50%);color:#fff8ef;font:12px/1.2 system-ui,sans-serif;opacity:.82';

    skipButton = root.querySelector('[data-agent-skin-skip]');
    if (!skipButton) skipButton = createElement('button', root, {
      'data-agent-skin-skip': '', 'type': 'button', 'aria-label': '跳过动画', 'text': '跳过',
    });
    skipButton.style.cssText = 'position:absolute;z-index:2;right:24px;top:20px;border:1px solid #ffffff66;border-radius:999px;padding:8px 16px;background:#18192b99;color:#fff8ef;font:14px system-ui,sans-serif;cursor:pointer';

    timeline = isLocalPreview ? document.getElementById('timeline') : null;
    elapsedText = isLocalPreview ? document.getElementById('elapsed') : null;
    pauseButton = isLocalPreview ? document.getElementById('pause') : null;
    replayButton = isLocalPreview ? document.getElementById('replay') : null;
    const controls = document.getElementById('preview-controls');
    if (controls) controls.hidden = !isLocalPreview;
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
    const visibleLogicalWidth = Math.min(WIDTH, width / scale);
    fitSubtitle(visibleLogicalWidth);
    const identityLayoutChanged = fitIdentity(visibleLogicalWidth);
    if (loaded && identityLayoutChanged) renderIdentityBitmap(generation).catch(() => {});
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
      if (progressText) progressText.textContent = `动画进度 ${progress}%`;
      if (elapsedText) elapsedText.textContent = `${(milliseconds / 1000).toFixed(1)} / 12.0 秒`;
      if (timeline) timeline.value = String(milliseconds / 1000);
      lastUI = milliseconds;
    }
  }

  function setWorldTransform() {
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = '#10121c';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.setTransform(pixelRatio * scale, 0, 0, pixelRatio * scale,
      pixelRatio * offsetX, pixelRatio * offsetY);
  }

  function drawPulse(milliseconds) {
    const pulse = 0.25 + 0.75 * (0.5 + 0.5 * Math.sin(milliseconds / 180));
    context.strokeStyle = 'rgb(251 216 178)';
    context.globalAlpha = 0.18 + pulse * 0.3;
    context.lineWidth = 3;
    context.beginPath();
    context.arc(768, 442, 166 + pulse * 18, 0, Math.PI * 2);
    context.stroke();
    context.globalAlpha = 1;
    context.fillStyle = 'rgba(255, 248, 239, .85)';
    context.font = '600 22px system-ui, sans-serif';
    context.textAlign = 'center';
    context.fillText('AGENT SKIN', 768, 720);
  }

  function drawIdentity(alpha = 1) {
    if (!identityBitmap) return;
    context.globalAlpha = alpha;
    context.drawImage(identityBitmap, 0, 0, WIDTH, HEIGHT);
    context.globalAlpha = 1;
  }

  function drawIdentityFragments(amount, scattered = false) {
    if (!identityBitmap) return;
    const progress = smooth(amount);
    context.globalAlpha = 1;
    for (let index = 0; index < particles.length; index++) {
      const item = particles[index];
      const drift = scattered ? 1 : progress;
      const x = item.sx + (item.scatterX - item.sx) * drift;
      const y = item.sy + (item.scatterY - item.sy) * drift;
      const opacity = scattered ? 0.95 : 1 - progress * 0.08;
      context.globalAlpha = opacity;
      context.drawImage(identityBitmap, item.sx, item.sy, item.sw, item.sh, x, y, item.sw, item.sh);
    }
    context.globalAlpha = 1;
  }

  function drawShardsIntoPaths(amount, milliseconds) {
    const progress = smooth(amount);
    if (lineCanvas) {
      context.save();
      context.beginPath();
      context.rect(0, 0, WIDTH * clamp(1.5 * progress - 0.25), HEIGHT);
      context.clip();
      context.drawImage(lineCanvas, 0, 0);
      context.restore();
    }
    context.fillStyle = 'rgba(255, 248, 239, .88)';
    for (let index = 0; index < particleTargets.length; index++) {
      const item = particleTargets[index];
      const x = item.scatterX + (item.x - item.scatterX) * progress;
      const y = item.scatterY + (item.y - item.scatterY) * progress;
      const radius = 1.6 + smooth(1 - Math.abs(progress - 0.7)) * 1.8;
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
    }
    if (!reduced && progress > 0 && progress < 1) {
      const front = WIDTH * clamp(1.5 * progress - 0.25);
      context.fillStyle = 'rgba(255, 218, 176, .9)';
      context.beginPath();
      context.arc(front, HEIGHT * 0.5 + Math.sin(milliseconds / 190) * 170, 7, 0, Math.PI * 2);
      context.fill();
    }
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
    const progress = progressAt(milliseconds);
    context.fillStyle = 'rgba(16, 18, 28, .76)';
    context.fillRect(subtitlePanelX, 794, subtitlePanelWidth, 174);
    context.fillStyle = '#fff8ef';
    context.textAlign = 'center';
    context.font = `600 ${subtitleFontSize}px system-ui, sans-serif`;
    const blockHeight = subtitleLines.length * subtitleLineHeight;
    const firstBaseline = 830 + Math.max(0, (122 - blockHeight) / 2) + subtitleFontSize;
    for (let index = 0; index < subtitleLines.length; index++) {
      context.fillText(subtitleLines[index], WIDTH / 2, firstBaseline + index * subtitleLineHeight, subtitleTextWidth);
    }
    const progressWidth = Math.min(756, subtitlePanelWidth * 0.65);
    const progressX = (WIDTH - progressWidth) / 2;
    context.fillStyle = 'rgba(255, 248, 239, .28)';
    context.fillRect(progressX, 807, progressWidth, 4);
    context.fillStyle = '#fff0d5';
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
      drawIdentityFragments(amount);
    } else if (phase === 'scattered') {
      drawIdentityFragments(1, true);
    } else if (phase === 'drawing') {
      if (reduced) {
        context.globalAlpha = smooth((milliseconds - 5080) / 2100);
        if (lineCanvas) context.drawImage(lineCanvas, 0, 0);
        context.globalAlpha = 1;
      } else {
        drawShardsIntoPaths((milliseconds - 5080) / 2100, milliseconds);
      }
    } else if (phase === 'colorize') {
      if (lineCanvas) context.drawImage(lineCanvas, 0, 0);
      drawArtwork(smooth((milliseconds - 7180) / 250));
    } else if (phase === 'portrait') {
      drawPortrait(milliseconds);
    } else {
      drawPortrait(milliseconds);
      const shutter = smooth((milliseconds - 11000) / 1000);
      context.fillStyle = '#10121c';
      context.fillRect(0, 0, WIDTH * shutter * 0.5, HEIGHT);
      context.fillRect(WIDTH * (1 - shutter * 0.5), 0, WIDTH * shutter * 0.5, HEIGHT);
    }
    updateUI(milliseconds);
  }

  function drawAt(milliseconds, playbackFrame) {
    if (!context || disposed) return;
    const started = performance.now();
    elapsed = clamp(milliseconds, 0, DURATION);
    renderScene(elapsed);
    const spent = Math.max(0, performance.now() - started);
    if (drawCount < drawSamples.length) drawSamples[drawCount++] = spent;
    if (playbackFrame && elapsed >= IDENTITY_RELEASE_MS) releaseIdentityBitmap();
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
    if (pauseButton) pauseButton.textContent = '暂停';
    return true;
  }

  function pause() {
    if (disposed || !rafId) return false;
    stopClock();
    root.dataset.playing = 'false';
    if (pauseButton) pauseButton.textContent = '继续';
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
    cachedPaths.length = 0;
    particles.length = 0;
    particleTargets.length = 0;
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
    const span = Math.max(18, stats.length / 1400);
    let nextSample = span;
    let walked = 0;
    for (let pathIndex = 0; pathIndex < contours.length; pathIndex++) {
      const points = contours[pathIndex];
      const path = new Path2D();
      const first = pointXY(points[0]);
      path.moveTo(first[0], first[1]);
      let previousX = first[0];
      let previousY = first[1];
      for (let pointIndex = 1; pointIndex < points.length; pointIndex++) {
        const current = pointXY(points[pointIndex]);
        const currentX = current[0];
        const currentY = current[1];
        path.lineTo(currentX, currentY);
        const segmentLength = Math.hypot(currentX - previousX, currentY - previousY);
        if (segmentLength > 0) {
          while (walked + segmentLength >= nextSample) {
            const fraction = (nextSample - walked) / segmentLength;
            particleTargets.push({
              x: previousX + (currentX - previousX) * fraction,
              y: previousY + (currentY - previousY) * fraction,
            });
            nextSample += span;
          }
        }
        walked += segmentLength;
        previousX = currentX;
        previousY = currentY;
      }
      particleTargets.push({ x: previousX, y: previousY });
      cachedPaths.push(path);
      resources.createdPaths++;
      resources.livePaths++;
    }
    lineCanvas = document.createElement('canvas');
    lineCanvas.width = WIDTH;
    lineCanvas.height = HEIGHT;
    resources.createdCanvases++;
    resources.liveCanvases++;
    lineContext = lineCanvas.getContext('2d', { alpha: true });
    if (!lineContext) throw new Error('asset-invalid');
    lineContext.clearRect(0, 0, WIDTH, HEIGHT);
    lineContext.lineWidth = 2.4;
    lineContext.lineJoin = 'round';
    lineContext.lineCap = 'round';
    lineContext.strokeStyle = 'rgba(255, 248, 239, .92)';
    for (let index = 0; index < cachedPaths.length; index++) lineContext.stroke(cachedPaths[index]);
    if (!particleTargets.length) throw new Error('asset-invalid');
  }

  function seedUnit(index, salt) {
    let value = (0x51f15e + Math.imul(index + 1, 0x45d9f3b) + Math.imul(salt + 3, 0x27d4eb2d)) | 0;
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
    value ^= value >>> 16;
    return (value >>> 0) / 4294967296;
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
    identityContext.strokeStyle = 'rgba(255, 246, 226, .9)';
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
      identityContext.fillStyle = '#fff8ef';
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
      identityContext.fillStyle = 'rgba(255, 248, 239, .76)';
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
        const target = particleTargets[index % particleTargets.length];
        particles.push({
          sx: left, sy: top, sw: Math.min(TILE, WIDTH - left), sh: Math.min(TILE, HEIGHT - top),
          scatterX, scatterY, targetX: target.x, targetY: target.y,
        });
      }
    }
    if (!particles.length) throw new Error('asset-invalid');
    for (let index = 0; index < particleTargets.length; index++) {
      const particle = particles[index % particles.length];
      particleTargets[index].scatterX = particle.scatterX;
      particleTargets[index].scatterY = particle.scatterY;
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

  async function prepare(currentGeneration) {
    if (disposed || currentGeneration !== generation) return;
    preparing = true;
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
    preparePaths(stats);
    do {
      await prepareIdentityBitmap(currentGeneration);
      if (disposed || currentGeneration !== generation) return;
    } while (identityRenderedLayoutKey !== identityLayoutKey);
    if (disposed || currentGeneration !== generation) return;
    loaded = true;
    preparing = false;
    releaseStaleTimeouts();
    updateLayout();
    drawAt(elapsed, false);
    root.dataset.prewarmed = 'true';
    if (!readySent) {
      readySent = true;
      message('ready', { duration: DURATION });
    }
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
    pause();
    const target = clamp(Number(seconds) * 1000, 0, DURATION);
    if (target < IDENTITY_RELEASE_MS && !identityBitmap && identityCanvas) {
      const currentGeneration = generation;
      makeBitmap(identityCanvas, currentGeneration).then(bitmap => {
        if (disposed || currentGeneration !== generation) {
          if (bitmap !== identityCanvas) closeBitmap(bitmap);
          return;
        }
        identityBitmap = bitmap;
        identityBitmapOwned = bitmap !== identityCanvas;
        elapsed = target;
        complete = false;
        skipped = false;
        drawAt(elapsed, false);
      }).catch(() => {});
      return true;
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
    const panel = root.querySelector('[data-agent-skin-error]')
      || createElement('div', root, { 'data-agent-skin-error': '', role: 'alert' });
    panel.textContent = String(text || '动画准备失败。');
    panel.style.cssText = 'position:absolute;z-index:3;left:50%;top:50%;transform:translate(-50%,-50%);max-width:min(700px,90vw);padding:18px 22px;border:1px solid #ffffff38;border-radius:12px;background:#18192bee;color:#fff8ef;text-align:center;box-shadow:0 12px 40px #0008';
  }

  function onSkip() {
    finish(true);
  }

  function onKeydown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
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
    if (loaded) drawAt(elapsed, false);
  }

  function onMotionChange(event) {
    setReduced(event.matches);
  }

  function dispose() {
    if (disposed) return false;
    disposed = true;
    generation++;
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
      waiting() { if (stageText) stageText.textContent = '仍在等待 Codex 启动…'; },
      error: showError,
    };
    return {
      dispose,
      preview,
    };
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
  );
  if (!environment.webkit?.messageHandlers?.launcher) {
    environment.launcherUI = Object.assign(localHandle.preview, { dispose: localHandle.dispose });
  }
}
