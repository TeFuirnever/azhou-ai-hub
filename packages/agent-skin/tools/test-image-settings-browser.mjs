#!/usr/bin/env node
// Uses an isolated headless Chrome and test-generated image pixels only.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CHROME_DEFAULT = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const MAX_INPUT_BYTES = 31_457_280;
const options = { chrome: CHROME_DEFAULT };
for (let index = 2; index < process.argv.length; index++) {
  const key = process.argv[index];
  if (key === '--help') {
    console.log('node tools/test-image-settings-browser.mjs [--chrome /path/to/Chrome]');
    process.exit(0);
  }
  if (key !== '--chrome' || !process.argv[index + 1]) throw new Error('Unknown or missing argument: ' + key);
  options.chrome = process.argv[++index];
}
options.chrome = resolve(options.chrome);

async function until(operation, milliseconds, label) {
  const deadline = Date.now() + milliseconds;
  let lastError;
  do {
    try {
      const value = await operation();
      if (value) return value;
    } catch (error) { lastError = error; }
    await delay(40);
  } while (Date.now() < deadline);
  throw new Error('Timed out waiting for ' + label + (lastError ? ': ' + String(lastError.message || lastError) : ''));
}

class CDP {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    socket.addEventListener('message', event => {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      message.error ? pending.reject(new Error(message.error.message)) : pending.resolve(message.result);
    });
    socket.addEventListener('close', () => {
      for (const pending of this.pending.values()) {
        clearTimeout(pending.timer);
        pending.reject(new Error('Chrome DevTools socket closed'));
      }
      this.pending.clear();
    });
  }
  static async open(address) {
    const socket = new WebSocket(address);
    await new Promise((resolveOpen, reject) => {
      const timer = setTimeout(() => { socket.close(); reject(new Error('Chrome DevTools connection timed out')); }, 5000);
      socket.addEventListener('open', () => { clearTimeout(timer); resolveOpen(); }, { once: true });
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Chrome DevTools connection failed')); }, { once: true });
    });
    return new CDP(socket);
  }
  call(method, params = {}, timeoutMs = 100_000) {
    const id = this.nextId++;
    return new Promise((resolveCall, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('Chrome DevTools request timed out: ' + method));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolveCall, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.call('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      timeout: 90_000,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.result?.description || result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    }
    return result.result?.value;
  }
  close() { this.socket.close(); }
}

function browserChecks(maxInputBytes) {
  return (async () => {
    const frame = document.createElement('iframe');
    frame.width = '800';
    frame.height = '820';
    frame.setAttribute('frameborder', '0');
    const frameLoaded = new Promise(resolve => { frame.addEventListener('load', resolve, { once: true }); });
    frame.src = 'about:blank';
    document.body.append(frame);
    await frameLoaded;
    const child = frame.contentWindow;
    const childDocument = frame.contentDocument;
    childDocument.documentElement.lang = 'zh-CN';
    childDocument.documentElement.style.colorScheme = 'dark';
    childDocument.documentElement.setAttribute('data-azhou-wallpaper', 'active');
    const wallpaperStylesheet = childDocument.createElement('link');
    wallpaperStylesheet.rel = 'stylesheet';
    wallpaperStylesheet.href = new URL('/wallpaper.css', document.location.href).href;
    childDocument.head.appendChild(wallpaperStylesheet);
    await new Promise((resolve, reject) => {
      wallpaperStylesheet.addEventListener('load', resolve, { once: true });
      wallpaperStylesheet.addEventListener('error', reject, { once: true });
    });
    childDocument.documentElement.style.setProperty('--agent-skin-surface', 'rgb(18, 24, 36)');
    childDocument.documentElement.style.setProperty('--agent-skin-text', 'rgb(238, 240, 245)');
    childDocument.documentElement.style.setProperty('--agent-skin-muted', 'rgb(176, 186, 204)');
    childDocument.documentElement.style.setProperty('--agent-skin-border', 'rgb(92, 108, 132)');
    let currentAppearance = { locale: 'zh-CN', theme: 'dark', colors: {
      surface: 'rgb(18, 24, 36)', text: 'rgb(238, 240, 245)',
      muted: 'rgb(176, 186, 204)', border: 'rgb(92, 108, 132)',
    } };
    const localization = createLocalization({ locale: childDocument.documentElement.lang });
    const appearanceAvatarCanvas = childDocument.createElement('canvas');
    appearanceAvatarCanvas.width = 8;
    appearanceAvatarCanvas.height = 8;
    appearanceAvatarCanvas.getContext('2d').fillRect(0, 0, 8, 8);
    const appearanceAvatar = appearanceAvatarCanvas.toDataURL('image/png');
    const created = [];
    const revoked = [];
    const urlApi = {
      createObjectURL(blob) {
        const url = child.URL.createObjectURL(blob);
        created.push(url);
        return url;
      },
      revokeObjectURL(url) {
        revoked.push(url);
        child.URL.revokeObjectURL(url);
      },
    };
    const api = createImageSettings({
      document: childDocument,
      Image: child.Image,
      URL: urlApi,
      indexedDB: child.indexedDB,
      localization,
      appearanceAvatar,
      getAppearance: () => currentAppearance,
      setTimeout: child.setTimeout.bind(child),
      clearTimeout: child.clearTimeout.bind(child),
      performance: child.performance,
    });
    const canvasFor = (width, height, paint) => {
      const canvas = childDocument.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      paint(canvas.getContext('2d'));
      return canvas;
    };
    const pngHeader = (width, height) => {
      const bytes = new child.Uint8Array(24);
      bytes.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
        0, 0, 0, 13, 0x49, 0x48, 0x44, 0x52]);
      new child.DataView(bytes.buffer).setUint32(16, width, false);
      new child.DataView(bytes.buffer).setUint32(20, height, false);
      return bytes;
    };
    const directPagePreflightFile = new child.File([pngHeader(24_000, 2_001)],
      'direct-page-over-pixels.png', { type: 'image/png' });
    const directPageReaderAvailable = typeof globalThis.AGENT_SKIN_READ_RAW_DIMENSIONS === 'function';
    const directPagePreflight = await api.importImage(directPagePreflightFile, 'avatar').then(
      () => ({ causeCode: '', createdURLs: created.length }),
      error => ({ causeCode: error.causeCode || '', createdURLs: created.length }),
    );
    if (!directPageReaderAvailable || directPagePreflight.causeCode !== 'image-too-large'
      || directPagePreflight.createdURLs !== 0) {
      throw new Error('direct page did not make the same raw-dimension parser available before first import: '
        + JSON.stringify({ directPageReaderAvailable, directPagePreflight }));
    }
    const blobFor = (canvas, type) => new Promise((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Chrome could not encode a synthetic ' + type)), type, 0.95);
    });
    const fileFor = async (canvas, type, name) => new child.File([await blobFor(canvas, type)], name, { type });
    const readPixel = async (dataURL, x, y) => {
      const image = new child.Image();
      image.src = dataURL;
      await image.decode();
      const canvas = childDocument.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context.drawImage(image, 0, 0);
      return Array.from(context.getImageData(x, y, 1, 1).data);
    };

    const formatCanvas = canvasFor(80, 60, context => {
      context.fillStyle = '#1557a0';
      context.fillRect(0, 0, 80, 60);
      context.fillStyle = '#f0c419';
      context.fillRect(20, 10, 40, 40);
    });
    const formats = [];
    for (const type of ['image/png', 'image/jpeg', 'image/webp']) {
      const result = await api.importImage(await fileFor(formatCanvas, type, 'synthetic.' + type.slice(6)), 'avatar');
      formats.push({ type, dimensions: [result.width, result.height], png: result.dataURL.startsWith('data:image/png;base64,'), byteCount: result.bytes === result.dataURL.length });
    }

    const cropCanvas = canvasFor(800, 400, context => {
      context.fillStyle = '#f00000';
      context.fillRect(0, 0, 400, 400);
      context.fillStyle = '#0000f0';
      context.fillRect(400, 0, 400, 400);
    });
    const crop = await api.importImage(await fileFor(cropCanvas, 'image/png', 'crop.png'), 'avatar');
    const cropLeft = await readPixel(crop.dataURL, 128, 256);
    const cropRight = await readPixel(crop.dataURL, 384, 256);

    const portraitCanvas = canvasFor(400, 800, context => {
      context.fillStyle = '#f00000';
      context.fillRect(0, 0, 400, 400);
      context.fillStyle = '#0000f0';
      context.fillRect(0, 400, 400, 400);
    });
    const portrait = await api.importImage(await fileFor(portraitCanvas, 'image/png', 'portrait.png'), 'avatar');
    const portraitTop = await readPixel(portrait.dataURL, 256, 128);
    const portraitBottom = await readPixel(portrait.dataURL, 256, 384);

    const squareCanvas = canvasFor(120, 120, context => {
      context.fillStyle = '#f00000';
      context.fillRect(0, 0, 60, 120);
      context.fillStyle = '#0000f0';
      context.fillRect(60, 0, 60, 120);
    });
    const square = await api.importImage(await fileFor(squareCanvas, 'image/png', 'square.png'), 'avatar');
    const squareLeft = await readPixel(square.dataURL, 128, 256);
    const squareRight = await readPixel(square.dataURL, 384, 256);

    const alphaCanvas = canvasFor(200, 100, context => {
      context.clearRect(0, 0, 200, 100);
      context.fillStyle = '#00ff40';
      context.fillRect(80, 30, 40, 40);
    });
    const alpha = await api.importImage(await fileFor(alphaCanvas, 'image/png', 'alpha.png'), 'avatar');
    const transparentCorner = await readPixel(alpha.dataURL, 8, 8);

    const artCanvas = canvasFor(800, 400, context => {
      context.fillStyle = '#1b3f60';
      context.fillRect(0, 0, 800, 400);
      context.fillStyle = '#ffe000';
      context.fillRect(390, 0, 20, 400);
    });
    const art = await api.importImage(await fileFor(artCanvas, 'image/png', 'artwork.png'), 'artwork');
    const artCenter = await readPixel(art.dataURL, 768, 512);
    const contourRegistration = art.contours.flat().some(([x, y]) => Math.abs(x - 768) < 32 && y > 100 && y < 900);

    const flatCanvas = canvasFor(128, 128, context => {
      context.fillStyle = '#373737';
      context.fillRect(0, 0, 128, 128);
    });
    let flatReason = '';
    try { await api.importImage(await fileFor(flatCanvas, 'image/png', 'flat.png'), 'artwork'); }
    catch (error) { flatReason = error.reason || ''; }

    const smallPng = await blobFor(cropCanvas, 'image/png');
    const padding = new Uint8Array(maxInputBytes - smallPng.size);
    const boundaryFile = new child.File([smallPng, padding], 'exact-30-mib.png', { type: 'image/png' });
    const boundary = await api.importImage(boundaryFile, 'avatar');

    const defaults = {
      avatar: crop.dataURL,
      artwork: art.dataURL,
      contours: art.contours,
      introTitle: 'Generated base',
      introCaption: '',
      artworkSubtitle: 'Generated fixture only',
      wallpaperStrength: 42,
    };
    const initiallyLoaded = await api.load(defaults);
    const waitFor = async (predicate, label) => {
      const deadline = Date.now() + 10_000;
      while (Date.now() < deadline) {
        const value = predicate();
        if (value) return value;
        await new Promise(resolve => child.setTimeout(resolve, 25));
      }
      throw new Error('Timed out waiting for ' + label);
    };
    let previewedDraft = null;
    let previewResult = null;
    let committedByApply = null;
    let savedCallbackCount = 0;
    let applyCalls = 0;
    api.openSettings({
      onPreview(value) { previewedDraft = value; return { started: true }; },
      async onApply(value) {
        applyCalls++;
        committedByApply = value;
        return applyCalls === 1
          ? { applied: false, reason: 'wallpaper-unsupported' }
          : { applied: true, reason: '' };
      },
      onSaved() { savedCallbackCount++; },
    });
    const settingsDialog = childDocument.querySelector('dialog[data-agent-skin-settings]');
    const settingsStatus = settingsDialog.querySelector('[data-agent-skin-settings-status]');
    const avatarInput = settingsDialog.querySelector('[data-agent-skin-image-input="avatar"]');
    const selectImage = file => {
      const transfer = new child.DataTransfer();
      transfer.items.add(file);
      avatarInput.files = transfer.files;
      avatarInput.dispatchEvent(new child.Event('change', { bubbles: true }));
    };
    const importErrors = [];
    const assertImportError = async (file, expectedText) => {
      selectImage(file);
      const message = await waitFor(() => settingsStatus.getAttribute('role') === 'alert'
        && settingsStatus.textContent.includes(expectedText) ? settingsStatus.textContent : '', expectedText);
      importErrors.push(message);
      return message;
    };
    const emptyFile = new child.File([], 'empty.png', { type: 'image/png' });
    await assertImportError(emptyFile, '启动头像文件为空');
    await assertImportError(new child.File([boundaryFile, 'x'], 'over-limit.png', { type: 'image/png' }),
      '启动头像超过 30 MiB');
    const oversizedHeader = pngHeader(24_000, 2_001);
    const preflightFile = new child.File([oversizedHeader], 'over-pixels.png', { type: 'image/png' });
    await assertImportError(preflightFile, '启动头像原始像素超过 48 MP');
    await assertImportError(new child.File([smallPng], 'forged.jpg', { type: 'image/jpeg' }),
      '启动头像的文件类型声明与实际内容不符');
    await assertImportError(new child.File([Uint8Array.of(1, 2, 3, 4, 5, 6, 7, 8)], 'unsupported.png',
      { type: 'image/png' }), '启动头像内容不是受支持');
    await assertImportError(new child.File([pngHeader(1, 1)], 'broken.png', { type: 'image/png' }),
      '启动头像无法解码');
    localization.setLocale('en');
    const localizedImportError = settingsStatus.textContent;
    if (!localizedImportError.includes('Startup portrait') || !localizedImportError.includes('could not be decoded')) {
      throw new Error('image import alert did not re-localize the field, cause and recovery action: '
        + localizedImportError);
    }
    const cancelledFile = new child.File([smallPng], 'cancelled.png', { type: 'image/png' });
    selectImage(cancelledFile);
    const cancelledImport = api.cancelImport();
    await waitFor(() => settingsStatus.getAttribute('role') === 'status' && !settingsStatus.textContent
      ? true : '', 'cancelled import status to clear');
    const cancelStatus = { cancelled: cancelledImport, role: settingsStatus.getAttribute('role'), text: settingsStatus.textContent };
    selectImage(new child.File([smallPng], 'recovered.png', { type: 'image/png' }));
    await waitFor(() => settingsStatus.getAttribute('role') === 'status'
      && settingsStatus.textContent.includes('Image ready to save') ? true : '', 'valid image recovery');
    localization.setLocale('zh-CN');
    const importRecovery = {
      errors: importErrors,
      localizedError: localizedImportError,
      cancelStatus,
      recoveredStatus: settingsStatus.textContent,
      saveEnabled: !settingsDialog.querySelector('footer button:last-child').disabled,
    };
    const settingsTabs = [...settingsDialog.querySelectorAll('[role="tab"][data-agent-skin-settings-tab]')]
      .map(tab => tab.getAttribute('data-agent-skin-settings-tab'));
    const workspacePreview = settingsDialog.querySelector('[data-agent-skin-workspace-preview]');
    const workspacePreviewImage = settingsDialog.querySelector('[data-agent-skin-workspace-preview-image]');
    const workspacePreviewCaption = workspacePreview?.querySelector('figcaption');
    const workspacePreviewSurface = workspacePreview?.querySelector(':scope > div');
    const workspacePreviewWash = settingsDialog.querySelector('[data-agent-skin-workspace-preview-wash]');
    const strengthInput = settingsDialog.querySelector('input[type="range"]');
    const textInputs = [...settingsDialog.querySelectorAll('input[type="text"]')];
    const titleInput = textInputs[0];
    const captionInput = textInputs[1];
    const subtitleInput = settingsDialog.querySelector('textarea');
    titleInput.value = 'T'.repeat(16);
    titleInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    captionInput.value = 'C'.repeat(48);
    captionInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    subtitleInput.value = '';
    subtitleInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    const legalTextInputs = {
      title: { valueLength: titleInput.value.length, maxLength: titleInput.maxLength },
      caption: { valueLength: captionInput.value.length, maxLength: captionInput.maxLength },
      subtitle: { valueLength: subtitleInput.value.length, maxLength: subtitleInput.maxLength },
    };
    const rectOf = element => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom,
        width: rect.width, height: rect.height };
    };
    const measurePreviewAt = async (width, height) => {
      frame.width = String(width);
      frame.height = String(height);
      await new Promise(resolve => child.requestAnimationFrame(() => child.requestAnimationFrame(resolve)));
      return {
        viewport: { width: child.innerWidth, height: child.innerHeight },
        preview: { ...rectOf(workspacePreview), clientWidth: workspacePreview.clientWidth,
          clientHeight: workspacePreview.clientHeight, scrollWidth: workspacePreview.scrollWidth,
          scrollHeight: workspacePreview.scrollHeight },
        image: rectOf(workspacePreviewImage),
        caption: rectOf(workspacePreviewCaption),
        dialog: rectOf(settingsDialog),
      };
    };
    const workspacePreviewGeometry = [];
    // A 390 CSS-pixel viewport is the responsive layout available at 200% zoom
    // in a 780-pixel-wide window; retain additional wider and shorter cases.
    for (const [width, height] of [[1512, 889], [800, 820], [640, 480], [390, 320]]) {
      workspacePreviewGeometry.push(await measurePreviewAt(width, height));
    }
    const zoomEquivalentGeometry = workspacePreviewGeometry.at(-1);
    const appearancePreviewMatrix = [];
    for (const [theme, colors] of [
      ['dark', { surface: 'rgb(18, 24, 36)', text: 'rgb(238, 240, 245)',
        muted: 'rgb(176, 186, 204)', border: 'rgb(92, 108, 132)' }],
      ['light', { surface: 'rgb(248, 250, 252)', text: 'rgb(23, 32, 51)',
        muted: 'rgb(83, 97, 118)', border: 'rgb(203, 213, 225)' }],
    ]) {
      const surface = colors.surface;
      currentAppearance = { locale: 'zh-CN', theme, colors };
      childDocument.documentElement.dataset.theme = theme;
      childDocument.documentElement.style.setProperty('--agent-skin-surface', surface);
      for (const [width, height] of [[1512, 889], [800, 820]]) {
        frame.width = String(width);
        frame.height = String(height);
        await new Promise(resolve => child.requestAnimationFrame(() => child.requestAnimationFrame(resolve)));
        api.refreshAppearance();
        for (const strength of [0, 42, 75]) {
          strengthInput.value = String(strength);
          strengthInput.dispatchEvent(new child.Event('input', { bubbles: true }));
          const imageStyle = child.getComputedStyle(workspacePreviewImage);
          const washStyle = child.getComputedStyle(workspacePreviewWash);
          const previewSurfaceStyle = child.getComputedStyle(workspacePreviewSurface);
          appearancePreviewMatrix.push({
            theme, surface, viewport: { width: child.innerWidth, height: child.innerHeight }, strength,
            imageVisible: !workspacePreviewImage.hidden && imageStyle.display !== 'none'
              && imageStyle.visibility !== 'hidden',
            imagePosition: imageStyle.objectPosition,
            washVisible: washStyle.display !== 'none' && washStyle.visibility !== 'hidden',
            wash: workspacePreviewWash.style.backgroundImage,
            previewSurface: previewSurfaceStyle.backgroundColor,
          });
        }
      }
    }
    const appearancePreviewFailures = appearancePreviewMatrix.flatMap(state => {
      const expectedPosition = state.viewport.width / state.viewport.height <= 6 / 5 ? '88% 50%' : '60% 50%';
      const failures = [];
      if (state.imageVisible !== (state.strength > 0)) failures.push('image visibility');
      if (state.washVisible !== (state.strength > 0)) failures.push('wash visibility');
      if (state.imagePosition !== expectedPosition) failures.push('crop position expected ' + expectedPosition);
      if (state.previewSurface !== state.surface) failures.push('resolved surface');
      if (state.strength > 0 && !state.wash.includes(state.surface)) failures.push('wash surface');
      return failures.map(failure => ({ theme: state.theme, viewport: state.viewport,
        strength: state.strength, failure, imageVisible: state.imageVisible,
        washVisible: state.washVisible, imagePosition: state.imagePosition,
        previewSurface: state.previewSurface, wash: state.wash }));
    });
    if (appearancePreviewFailures.length) {
      throw new Error('Background draft preview must follow resolved surface, 0/42/75 closure, and 60%/88% viewport crop: '
        + JSON.stringify(appearancePreviewFailures));
    }
    const surfaceCases = [
      { name: 'dark-conflicting-tokens', theme: 'dark', app: 'rgb(10, 20, 30)', color: 'rgb(200, 210, 220)', expected: 'rgb(10, 20, 30)' },
      { name: 'light-missing-tokens', theme: 'light', expected: 'rgb(255, 255, 255)' },
      { name: 'dark-invalid-tokens', theme: 'dark', app: 'not-a-color', color: 'also-not-a-color',
        appearanceSurface: 'not-a-color', expected: 'rgb(16, 18, 28)' },
      { name: 'light-invalid-tokens', theme: 'light', app: 'not-a-color', color: 'also-not-a-color',
        appearanceSurface: 'not-a-color', expected: 'rgb(255, 255, 255)' },
      { name: 'dark-invalid-app-token', theme: 'dark', app: 'not-a-color', color: 'rgb(200, 210, 220)', expected: 'rgb(200, 210, 220)' },
    ];
    const surfaceComparison = [];
    for (const state of surfaceCases) {
      const root = childDocument.documentElement;
      root.dataset.theme = state.theme;
      root.style.removeProperty('--app-color-background-surface');
      root.style.removeProperty('--color-surface');
      if (state.app) root.style.setProperty('--app-color-background-surface', state.app);
      if (state.color) root.style.setProperty('--color-surface', state.color);
      // This is the resolved value the host controller passes to the wallpaper renderer.
      root.style.setProperty('--azhou-wallpaper-surface', state.expected);
      currentAppearance = {
        locale: 'zh-CN', theme: state.theme,
        colors: { surface: state.appearanceSurface ?? state.expected },
      };
      api.refreshAppearance();
      surfaceComparison.push({
        name: state.name,
        expected: state.expected,
        preview: child.getComputedStyle(workspacePreviewSurface).backgroundColor,
        production: child.getComputedStyle(childDocument.body).backgroundColor,
      });
    }
    const surfaceComparisonFailures = surfaceComparison.filter(state =>
      state.preview !== state.expected || state.production !== state.expected);
    if (surfaceComparisonFailures.length) {
      throw new Error('The production wallpaper stylesheet and draft preview must use the same validated surface: '
        + JSON.stringify(surfaceComparisonFailures));
    }
    currentAppearance = { locale: 'zh-CN', theme: 'dark', colors: {
      surface: 'rgb(18, 24, 36)', text: 'rgb(238, 240, 245)',
      muted: 'rgb(176, 186, 204)', border: 'rgb(92, 108, 132)',
    } };
    childDocument.documentElement.dataset.theme = 'dark';
    childDocument.documentElement.style.setProperty('--agent-skin-surface', 'rgb(18, 24, 36)');
    api.refreshAppearance();
    frame.width = '800';
    frame.height = '820';
    await new Promise(resolve => child.requestAnimationFrame(() => child.requestAnimationFrame(resolve)));
    const animationPreviewButton = settingsDialog.querySelector('[data-agent-skin-preview-animation]');
    titleInput.value = 'Local draft';
    titleInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    strengthInput.value = '18';
    strengthInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    settingsDialog.querySelector('[data-agent-skin-settings-tab="startup"]')?.click();
    if (!animationPreviewButton) throw new Error('startup section does not expose the animation preview action');
    animationPreviewButton.click();
    await waitFor(() => previewedDraft,
      'draft animation preview callback (' + settingsDialog.querySelector('[data-agent-skin-settings-status]')?.textContent + ')');
    previewResult = {
      title: previewedDraft.introTitle,
      strength: previewedDraft.wallpaperStrength,
      settingsOpen: api.isSettingsOpen(),
      currentTitle: initiallyLoaded.settings.introTitle,
      previewImage: workspacePreviewImage?.getAttribute('src'),
      previewWash: settingsDialog.querySelector('[data-agent-skin-workspace-preview-wash]')?.style.backgroundImage,
    };
    const cropCaptionZh = workspacePreviewCaption?.textContent;
    localization.setLocale('en');
    const cropCaptionEn = workspacePreviewCaption?.textContent;
    const inputStyle = child.getComputedStyle(titleInput);
    const restoreButton = settingsDialog.querySelector('footer button');
    const buttonStyle = child.getComputedStyle(restoreButton);
    const saveButton = settingsDialog.querySelector('footer button:last-child');
    const saveStyle = child.getComputedStyle(saveButton);
    const identityAvatar = settingsDialog.querySelector('[data-agent-skin-appearance-avatar]');
    const appearance = {
      locale: localization.locale,
      dialogCount: childDocument.querySelectorAll('dialog[data-agent-skin-settings]').length,
      title: settingsDialog.querySelector('#agent-skin-settings-title').textContent,
      appearanceAvatar: Boolean(identityAvatar?.src.startsWith('data:image/png;base64,')),
      appearanceAvatarAlt: identityAvatar?.getAttribute('alt'),
      fieldLabel: titleInput.closest('label')?.textContent.trim(),
      draftValue: titleInput.value,
      colorScheme: child.getComputedStyle(settingsDialog).colorScheme,
      surface: child.getComputedStyle(settingsDialog).backgroundColor,
      inputSurface: inputStyle.backgroundColor,
      inputText: inputStyle.color,
      inputBorder: inputStyle.borderTopColor,
      buttonSurface: buttonStyle.backgroundColor,
      buttonText: buttonStyle.color,
      buttonBorder: buttonStyle.borderTopColor,
      saveSurface: saveStyle.backgroundColor,
      saveText: saveStyle.color,
    };
    api.cancelSettings();
    const afterPreviewCancel = await api.load(defaults);
    api.openSettings({
      onApply: async value => {
        applyCalls++;
        committedByApply = value;
        return applyCalls === 1
          ? { applied: false, reason: 'wallpaper-unsupported' }
          : { applied: true, reason: '' };
      },
      onSaved() { savedCallbackCount++; },
    });
    const applyDialog = childDocument.querySelector('dialog[data-agent-skin-settings]');
    const applyTitle = applyDialog.querySelector('input[type="text"]');
    applyTitle.value = 'Apply draft';
    applyTitle.dispatchEvent(new child.Event('input', { bubbles: true }));
    const applyStrength = applyDialog.querySelector('input[type="range"]');
    applyStrength.value = '27';
    applyStrength.dispatchEvent(new child.Event('input', { bubbles: true }));
    applyDialog.querySelector('footer button:last-child').click();
    await waitFor(() => applyDialog.querySelector('[role="alert"]')?.textContent,
      'post-save background failure stays visible');
    const afterApplyFailure = {
      settingsOpen: api.isSettingsOpen(),
      status: applyDialog.querySelector('[role="alert"]')?.textContent,
      savedValue: committedByApply?.introTitle,
      savedCallbackCount,
      retryButton: [...applyDialog.querySelectorAll('button')]
        .find(button => /retry|重试/i.test(button.textContent.trim())),
    };
    afterApplyFailure.retryButton?.click();
    await waitFor(() => savedCallbackCount === 1 && !api.isSettingsOpen(),
      'retry applies the committed settings and closes once');
    const initialCandidate = {
      schemaVersion: 1,
      avatar: crop.dataURL,
      artwork: art.dataURL,
      contours: art.contours,
      introTitle: 'Saved fixture',
      introCaption: '',
      artworkSubtitle: 'Generated fixture only',
      wallpaperStrength: 27,
    };
    const initialCommit = await api.save(initialCandidate);

    const secondPage = childDocument.createElement('iframe');
    const secondPageLoaded = new Promise(resolve => secondPage.addEventListener('load', resolve, { once: true }));
    secondPage.src = 'about:blank';
    childDocument.body.append(secondPage);
    await secondPageLoaded;
    const secondWindow = secondPage.contentWindow;
    const secondDocument = secondPage.contentDocument;
    const secondAPI = createImageSettings({
      document: secondDocument,
      Image: secondWindow.Image,
      URL: secondWindow.URL,
      indexedDB: secondWindow.indexedDB,
      localization,
      setTimeout: secondWindow.setTimeout.bind(secondWindow),
      clearTimeout: secondWindow.clearTimeout.bind(secondWindow),
      performance: secondWindow.performance,
    });
    const secondPageBaseline = await secondAPI.load(defaults);
    if (!api.openSettings() || !secondAPI.openSettings()) {
      throw new Error('both settings pages must open for the conflict regression');
    }
    const pageATitle = settingsDialog.querySelector('input[type="text"]');
    const pageAConflictSave = settingsDialog.querySelector('footer button:last-child');
    const pageBDialog = secondDocument.querySelector('dialog[data-agent-skin-settings]');
    const pageBTitle = pageBDialog.querySelector('input[type="text"]');
    const pageBSave = pageBDialog.querySelector('footer button:last-child');
    const pageBStatus = pageBDialog.querySelector('[data-agent-skin-settings-status]');
    pageATitle.value = 'Page A wins';
    pageATitle.dispatchEvent(new child.Event('input', { bubbles: true }));
    pageBTitle.value = 'Page B draft';
    pageBTitle.dispatchEvent(new secondWindow.Event('input', { bubbles: true }));
    pageAConflictSave.click();
    await waitFor(() => !api.isSettingsOpen(), 'first page settings commit');
    const winningCommit = await api.load(defaults);
    pageBSave.click();
    await waitFor(() => pageBStatus.getAttribute('role') === 'alert' ? pageBStatus.textContent : '',
      'stale page shows the conflict recovery message');
    const conflictStatus = pageBStatus.textContent;
    const conflictDraft = pageBTitle.value;
    if (conflictDraft !== 'Page B draft' || !/Closing discards.*Copy.*Reopen.*new value/i.test(conflictStatus)) {
      throw new Error('conflict keeps a copyable draft and accurately describes close/reopen recovery: '
        + JSON.stringify({ conflictDraft, conflictStatus }));
    }
    if (!secondAPI.isSettingsOpen()) throw new Error('the stale settings page remains open for copying');
    secondAPI.cancelSettings();
    if (!secondAPI.dispose()) throw new Error('the stale page releases its settings runtime after close');
    const reopenedAPI = createImageSettings({
      document: secondDocument,
      Image: secondWindow.Image,
      URL: secondWindow.URL,
      indexedDB: secondWindow.indexedDB,
      localization,
      setTimeout: secondWindow.setTimeout.bind(secondWindow),
      clearTimeout: secondWindow.clearTimeout.bind(secondWindow),
      performance: secondWindow.performance,
    });
    const reloaded = await reopenedAPI.load(defaults);
    if (reloaded.settings.introTitle !== 'Page A wins' || !reopenedAPI.openSettings()) {
      throw new Error('reopening settings reads the value committed by the other page');
    }
    const reopenedDialog = secondDocument.querySelector('dialog[data-agent-skin-settings]');
    const reopenedTitle = reopenedDialog.querySelector('input[type="text"]');
    if (reopenedTitle.value !== 'Page A wins') throw new Error('reopened input does not show the external winner');
    reopenedAPI.cancelSettings();
    reopenedAPI.dispose();
    secondPage.remove();
    const versionchange = await new Promise((resolve, reject) => {
      const request = child.indexedDB.open('azhou-codex-startup', 2);
      let blocked = false;
      let oldVersion = null;
      const timer = child.setTimeout(() => reject(new Error('versionchange close timed out')), 5000);
      request.onblocked = () => { blocked = true; };
      request.onupgradeneeded = event => { oldVersion = event.oldVersion; };
      request.onerror = () => { child.clearTimeout(timer); reject(request.error || new Error('versionchange upgrade failed')); };
      request.onsuccess = () => {
        child.clearTimeout(timer);
        const db = request.result;
        const result = { blocked, oldVersion, version: db.version };
        db.close();
        resolve(result);
      };
    });
    frame.width = '1512';
    frame.height = '889';
    localization.setLocale('zh-CN');
    if (!api.openSettings()) throw new Error('could not reopen settings for the layout screenshot');
    settingsDialog.querySelector('[data-agent-skin-settings-tab="workspace"]')?.click();
    await new Promise(resolve => child.requestAnimationFrame(() => child.requestAnimationFrame(resolve)));
    const screenshotGeometry = {
      viewport: { width: child.innerWidth, height: child.innerHeight },
      preview: { ...rectOf(workspacePreview), clientWidth: workspacePreview.clientWidth,
        clientHeight: workspacePreview.clientHeight, scrollWidth: workspacePreview.scrollWidth,
        scrollHeight: workspacePreview.scrollHeight },
      image: rectOf(workspacePreviewImage),
      caption: rectOf(workspacePreviewCaption),
      dialog: rectOf(settingsDialog),
    };
    const zeroStrengthValue = settingsDialog.querySelector('[data-agent-skin-wallpaper-strength-value]');
    strengthInput.value = '0';
    strengthInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    const zeroStrength = {
      visibleValue: zeroStrengthValue.textContent,
      accessibleValue: strengthInput.getAttribute('aria-valuetext'),
      valueIsAdjacent: zeroStrengthValue.parentElement === strengthInput.parentElement,
    };
    const strengthRowLabel = strengthInput.closest('label');
    const strengthLabelAssociation = {
      controlIsSlider: strengthRowLabel?.control === strengthInput,
      sliderLabelCount: strengthInput.labels?.length || 0,
    };
    strengthInput.value = '42';
    strengthInput.dispatchEvent(new child.Event('input', { bubbles: true }));
    const artworkAction = settingsDialog.querySelector('[data-agent-skin-image-action="artwork"]');
    const sectionHeadings = settingsDialog.querySelectorAll('h3').length;
    const tabPanelsNamed = [...settingsDialog.querySelectorAll('[role="tab"]')].every(tab => {
      const panel = settingsDialog.querySelector('#' + tab.getAttribute('aria-controls'));
      return panel?.getAttribute('aria-labelledby') === tab.id;
    });
    const startupNote = [...settingsDialog.querySelectorAll('p')]
      .map(element => element.textContent.trim())
      .find(text => text.includes('保存后用于下次启动')) || '';
    const settingsUi = {
      headingCount: settingsDialog.querySelectorAll('h2').length,
      sectionHeadingCount: sectionHeadings,
      tabPanelsNamed,
      restoreLabel: restoreButton?.textContent,
      artworkButtonLabel: artworkAction?.textContent,
      artworkButtonAriaLabel: artworkAction?.getAttribute('aria-label'),
      startupNote,
      zeroStrength,
      strengthLabelAssociation,
      legalTextInputs,
    };
    return {
      formats,
      directPagePreflight: { readerAvailable: directPageReaderAvailable, ...directPagePreflight },
      previewWorkflow: {
        settingsTabs,
        hasWorkspacePreview: Boolean(workspacePreview),
        importRecovery,
      workspacePreviewGeometry,
        zoomEquivalentGeometry,
        screenshotGeometry,
        settingsUi,
        hasAnimationPreview: Boolean(animationPreviewButton),
        previewResult,
        appearancePreviewMatrix,
        surfaceComparison,
        cropCaptionZh,
        cropCaptionEn,
        titleAfterCancel: afterPreviewCancel.settings.introTitle,
        applyCalls,
        savedCallbackCount,
        committedTitle: committedByApply?.introTitle,
        failure: afterApplyFailure.status,
        settingsOpenAfterFailure: afterApplyFailure.settingsOpen,
      },
      cropLeft,
      cropRight,
      portraitTop,
      portraitBottom,
      squareLeft,
      squareRight,
      transparentCorner,
      artCenter,
      contourRegistration,
      flatReason,
      boundarySize: boundaryFile.size,
      boundaryDimensions: [boundary.width, boundary.height],
      revokedCount: revoked.length,
      createdCount: created.length,
      idleCancelResult: api.cancelImport(),
      appearance,
      storage: {
        initialReason: initiallyLoaded.reason,
        initialBaseline: initiallyLoaded.baseline,
        initialTitle: initialCommit.introTitle,
        hasAppearanceAvatar: Object.hasOwn(initialCommit, 'appearanceAvatar'),
        secondPageLoadedTitle: secondPageBaseline.settings.introTitle,
        winningTitle: winningCommit.settings.introTitle,
        conflictReason: conflictStatus ? 'settings-conflict' : '',
        conflictStatus,
        conflictDraft,
        reopenedTitle: reopenedTitle.value,
        reloadedTitle: reloaded.settings.introTitle,
        reloadedBaselineTitle: reloaded.baseline?.introTitle,
        versionchange,
      },
    };
  })();
}

let server;
let chrome;
let cdp;
let profile;

async function cleanup() {
  try { cdp?.close(); } catch {}
  if (chrome && chrome.exitCode === null && chrome.signalCode === null) {
    const exited = new Promise(resolveExit => chrome.once('exit', resolveExit));
    chrome.kill('SIGTERM');
    await Promise.race([exited, delay(2000)]);
    if (chrome.exitCode === null && chrome.signalCode === null) {
      chrome.kill('SIGKILL');
      await Promise.race([exited, delay(1000)]);
    }
  }
  if (server) {
    server.closeAllConnections();
    await new Promise(resolveClose => server.close(resolveClose));
  }
  if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 4, retryDelay: 100 });
}

try {
  assert.equal(typeof WebSocket, 'function', 'Node 22 or newer is required for the built-in WebSocket');
  const imageSettings = await readFile(join(PACKAGE_ROOT, 'image-settings.js'));
  const imageMetadataReader = await readFile(join(PACKAGE_ROOT, 'image-metadata-reader.js'));
  const localizationSource = await readFile(join(PACKAGE_ROOT, 'localization.js'));
  const wallpaperCss = await readFile(join(PACKAGE_ROOT, 'wallpaper', 'wallpaper.css'));
  const indexHtml = await readFile(join(PACKAGE_ROOT, 'index.html'), 'utf8');
  const csp = indexHtml.match(/http-equiv="Content-Security-Policy"\s+content="([^"]+)"/i)?.[1] || '';
  const readerTag = '<script src="image-metadata-reader.js" defer></script>';
  const settingsTag = '<script src="image-settings.js" defer></script>';
  assert.match(csp, /(?:^|;\s*)script-src 'self'(?:;|$)/,
    'the direct page permits the same-origin classic metadata reader');
  assert.match(csp, /(?:^|;\s*)img-src 'self' blob: data:(?:;|$)/,
    'the direct page permits the object URL used to decode a selected file');
  assert.ok(indexHtml.indexOf(readerTag) >= 0 && indexHtml.indexOf(readerTag) < indexHtml.indexOf(settingsTag),
    'the direct page loads the classic metadata reader before the deferred settings script');
  const html = '<!doctype html><html><head><meta charset="utf-8"><title>image settings fixture</title></head><body>'
    + '<script src="/localization.js" defer></script><script src="/image-metadata-reader.js" defer></script>'
    + '<script src="/image-settings.js" defer></script><script src="/image-metadata-order-probe.js" defer></script>'
    + '</body></html>';
  const orderProbe = "window.imageSettingsReady = typeof createImageSettings === 'function' "
    + "&& typeof createLocalization === 'function'; window.imageMetadataReady = "
    + "typeof window.AGENT_SKIN_READ_RAW_DIMENSIONS === 'function';";
  server = createServer((request, response) => {
    if (request.url === '/image-settings.js') {
      response.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      response.end(imageSettings);
    } else if (request.url === '/image-metadata-reader.js') {
      response.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      response.end(imageMetadataReader);
    } else if (request.url === '/image-metadata-order-probe.js') {
      response.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      response.end(orderProbe);
    } else if (request.url === '/localization.js') {
      response.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      response.end(localizationSource);
    } else if (request.url === '/wallpaper.css') {
      response.writeHead(200, { 'content-type': 'text/css; charset=utf-8', 'cache-control': 'no-store' });
      response.end(wallpaperCss);
    } else if (request.url === '/' || request.url === '/index.html') {
      response.setHeader('content-security-policy',
        csp);
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
      response.end(html);
    } else {
      response.writeHead(404);
      response.end();
    }
  });
  await new Promise((resolveListen, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolveListen);
  });
  const origin = 'http://127.0.0.1:' + server.address().port;
  profile = await mkdtemp(join(tmpdir(), 'agent-skin-image-settings-chrome-'));
  chrome = spawn(options.chrome, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-extensions', '--window-size=1536,920', '--remote-debugging-port=0',
    '--remote-allow-origins=*', '--user-data-dir=' + profile, 'about:blank',
  ], { stdio: 'ignore' });
  chrome.once('error', error => { throw error; });
  const activePortFile = await until(async () => {
    try { return await readFile(join(profile, 'DevToolsActivePort'), 'utf8'); }
    catch { return null; }
  }, 15_000, 'Chrome DevTools port');
  const port = Number(activePortFile.split('\n')[0]);
  const target = await until(async () => {
    const response = await fetch('http://127.0.0.1:' + port + '/json/list');
    if (!response.ok) return null;
    const targets = await response.json();
    return targets.find(item => item.type === 'page' && item.webSocketDebuggerUrl);
  }, 10_000, 'isolated Chrome page');
  cdp = await CDP.open(target.webSocketDebuggerUrl);
  await cdp.call('Runtime.enable');
  await cdp.call('Page.enable');
  await cdp.call('Page.navigate', { url: origin + '/' });
  await until(() => cdp.evaluate('window.imageSettingsReady === true'), 10_000, 'image settings source load');
  await until(() => cdp.evaluate('window.imageMetadataReady === true'), 10_000,
    'classic metadata reader before deferred image settings script');
  const expression = '(' + browserChecks.toString() + ')(' + MAX_INPUT_BYTES + ')';
  const result = await cdp.evaluate(expression);
  await cdp.call('Accessibility.enable');
  const frameTree = await cdp.call('Page.getFrameTree');
  const settingsFrameId = frameTree.frameTree.childFrames?.[0]?.frame?.id;
  assert.ok(settingsFrameId, 'the real settings iframe is available for AX inspection');
  const settingsAXTree = await cdp.call('Accessibility.getFullAXTree', { frameId: settingsFrameId });
  const strengthAXNode = settingsAXTree.nodes.find(node => node.role?.value === 'slider');
  assert.deepEqual({
    dom: result.previewWorkflow.settingsUi.strengthLabelAssociation,
    accessibleName: strengthAXNode?.name?.value || '',
  }, {
    dom: { controlIsSlider: true, sliderLabelCount: 1 },
    accessibleName: '背景强度（0–75）',
  }, 'the real slider label association and Chromium AX tree expose its visible name');

  assert.deepEqual(result.formats.map(item => item.type), ['image/png', 'image/jpeg', 'image/webp']);
  assert.deepEqual(result.directPagePreflight,
    { readerAvailable: true, causeCode: 'image-too-large', createdURLs: 0 },
    'the direct page must load its classic metadata reader before the first import and reject from its header');
  for (const item of result.formats) {
    assert.deepEqual(item.dimensions, [512, 512]);
    assert.equal(item.png, true);
    assert.equal(item.byteCount, true);
  }
  assert.ok(result.cropLeft[0] > result.cropLeft[2], 'left side of the center crop stays red');
  assert.ok(result.cropRight[2] > result.cropRight[0], 'right side of the center crop stays blue');
  assert.ok(result.portraitTop[0] > result.portraitTop[2], 'top of the portrait crop stays red');
  assert.ok(result.portraitBottom[2] > result.portraitBottom[0], 'bottom of the portrait crop stays blue');
  assert.ok(result.squareLeft[0] > result.squareLeft[2], 'left side of a square source stays red');
  assert.ok(result.squareRight[2] > result.squareRight[0], 'right side of a square source stays blue');
  assert.deepEqual(result.transparentCorner, [16, 17, 20, 255]);
  assert.deepEqual(result.artCenter.slice(0, 3), [255, 224, 0]);
  assert.equal(result.contourRegistration, true);
  assert.equal(result.flatReason, 'asset-invalid');
  assert.equal(result.boundarySize, MAX_INPUT_BYTES);
  assert.deepEqual(result.boundaryDimensions, [512, 512]);
  assert.equal(result.revokedCount, result.createdCount);
  assert.equal(result.idleCancelResult, false);
  assert.deepEqual(result.previewWorkflow.settingsTabs, ['workspace', 'startup', 'about']);
  assert.equal(result.previewWorkflow.hasWorkspacePreview, true);
  assert.equal(result.previewWorkflow.hasAnimationPreview, true);
  assert.equal(result.previewWorkflow.importRecovery.errors.length, 6,
    'the settings alert covers empty, byte, pixel, MIME, format and decoder errors');
  assert.equal(result.previewWorkflow.importRecovery.errors.every(message => message.includes('启动头像')
    && /请选择|换一张/.test(message)), true,
  'each localized error names the affected field and a recovery action');
  assert.match(result.previewWorkflow.importRecovery.localizedError, /Startup portrait.*could not be decoded.*Choose/,
    'the cause and recovery action follow the selected UI locale');
  assert.deepEqual(result.previewWorkflow.importRecovery.cancelStatus,
    { cancelled: true, role: 'status', text: '' },
    'canceling an import clears the alert instead of presenting a damaged-image error');
  assert.match(result.previewWorkflow.importRecovery.recoveredStatus, /图片已准备/,
    'a valid replacement returns the field to its ready state');
  assert.equal(result.previewWorkflow.importRecovery.saveEnabled, true,
    'a recovered selection leaves the save action available');
  assert.equal(result.previewWorkflow.cropCaptionZh.includes('裁切'), true,
    'Chinese preview caption explains that the thumbnail crop may differ');
  assert.equal(result.previewWorkflow.cropCaptionEn.toLowerCase().includes('crop'), true,
    'English preview caption explains that the thumbnail crop may differ');
  assert.ok(result.previewWorkflow.surfaceComparison.length >= 5,
    'surface preview matches the actual production stylesheet across token and theme fallback cases');
  for (const geometry of [...result.previewWorkflow.workspacePreviewGeometry, result.previewWorkflow.screenshotGeometry]) {
    assert.ok(geometry.preview.height <= 240, 'workspace preview stays under the compact 240px cap');
    assert.ok(geometry.caption.height <= 60, 'preview caption stays at text height');
    assert.ok(geometry.image.height > 0, 'image area keeps the remaining preview height');
    assert.ok(Math.abs(geometry.preview.height - geometry.image.height - geometry.caption.height - 2) <= 1,
      'image area and caption account for the preview height without a stretched caption');
    assert.ok(geometry.preview.scrollWidth <= geometry.preview.clientWidth
      && geometry.preview.scrollHeight <= geometry.preview.clientHeight,
    'workspace preview does not overflow at medium or small viewport sizes');
    assert.ok(geometry.dialog.x >= 0 && geometry.dialog.y >= 0
      && geometry.dialog.right <= geometry.viewport.width && geometry.dialog.bottom <= geometry.viewport.height,
    'settings dialog remains within its viewport');
  }
  assert.equal(result.previewWorkflow.zoomEquivalentGeometry.viewport.width, 390,
    '200% zoom on a 780px window uses the tested 390 CSS-pixel layout viewport');
  assert.deepEqual(result.previewWorkflow.settingsUi, {
    headingCount: 1,
    sectionHeadingCount: 0,
    tabPanelsNamed: true,
    restoreLabel: '恢复全部默认',
    artworkButtonLabel: '选择背景图片',
    artworkButtonAriaLabel: null,
    startupNote: '保存后用于下次启动；预览不会保存草稿。',
    zeroStrength: { visibleValue: '关闭', accessibleValue: '关闭', valueIsAdjacent: true },
    strengthLabelAssociation: { controlIsSlider: true, sliderLabelCount: 1 },
    legalTextInputs: {
      title: { valueLength: 16, maxLength: 16 },
      caption: { valueLength: 48, maxLength: 48 },
      subtitle: { valueLength: 0, maxLength: 60 },
    },
  });
  assert.deepEqual({ title: result.previewWorkflow.previewResult.title,
    strength: result.previewWorkflow.previewResult.strength,
    settingsOpen: result.previewWorkflow.previewResult.settingsOpen,
    currentTitle: result.previewWorkflow.previewResult.currentTitle }, {
    title: 'Local draft', strength: 18, settingsOpen: true, currentTitle: 'Generated base',
  });
  assert.ok(result.previewWorkflow.previewResult.previewImage?.startsWith('data:image/png;base64,'));
  const expectedWashStops = [
    '90%, transparent 10%) 0%', '92%, transparent 8%) 22%', '95%, transparent 5%) 36%',
    '93%, transparent 7%) 62%', '87%, transparent 13%) 73%', '72%, transparent 28%) 87%',
    '70%, transparent 30%) 100%',
  ];
  assert.ok(result.previewWorkflow.previewResult.previewWash?.startsWith('linear-gradient(90deg,'),
    'workspace preview uses the same layered wash treatment as the wallpaper');
  for (const stop of expectedWashStops) {
    assert.ok(result.previewWorkflow.previewResult.previewWash.includes(stop),
      'wallpaper strength 18 produces the expected preview wash stop ' + stop);
  }
  assert.equal(result.previewWorkflow.titleAfterCancel, 'Generated base',
    'previewing a modified draft never persists it');
  assert.equal(result.previewWorkflow.settingsOpenAfterFailure, true,
    'workspace application failure leaves the saved result visible in settings');
  assert.ok(/saved|background/i.test(result.previewWorkflow.failure));
  assert.equal(result.previewWorkflow.applyCalls, 2,
    'retry reapplies the committed settings without a second settings save');
  assert.equal(result.previewWorkflow.savedCallbackCount, 1,
    'the final close callback runs once after the retry succeeds');
  assert.equal(result.previewWorkflow.committedTitle, 'Apply draft');
  assert.deepEqual(result.appearance, {
    locale: 'en',
    dialogCount: 1,
    title: 'Azhou · Theme & Appearance',
    appearanceAvatar: true,
    appearanceAvatarAlt: '',
    fieldLabel: 'Startup title (up to 16 characters)',
    draftValue: 'Local draft',
    colorScheme: 'dark',
    surface: 'rgb(18, 24, 36)',
    inputSurface: 'rgb(18, 24, 36)',
    inputText: 'rgb(238, 240, 245)',
    inputBorder: 'rgb(92, 108, 132)',
    buttonSurface: 'rgb(18, 24, 36)',
    buttonText: 'rgb(238, 240, 245)',
    buttonBorder: 'rgb(92, 108, 132)',
    saveSurface: 'rgb(238, 240, 245)',
    saveText: 'rgb(18, 24, 36)',
  });
  assert.equal(result.storage.initialReason, '');
  assert.equal(result.storage.initialBaseline, undefined);
  assert.equal(result.storage.initialTitle, 'Saved fixture');
  assert.equal(result.storage.hasAppearanceAvatar, false);
  assert.equal(result.storage.secondPageLoadedTitle, 'Saved fixture');
  assert.equal(result.storage.winningTitle, 'Page A wins');
  assert.equal(result.storage.conflictReason, 'settings-conflict');
  assert.equal(result.storage.conflictDraft, 'Page B draft', 'the second page leaves its text available to copy');
  assert.match(result.storage.conflictStatus, /Closing discards.*Copy.*Reopen.*new value/i);
  assert.equal(result.storage.reopenedTitle, 'Page A wins', 'a new settings runtime reads the winning value');
  assert.equal(result.storage.reloadedTitle, 'Page A wins');
  assert.equal(result.storage.reloadedBaselineTitle, 'Page A wins');
  assert.equal(result.storage.versionchange.blocked, false,
    'the settings connection closes on versionchange so the newer open can proceed');
  assert.equal(result.storage.versionchange.oldVersion, 1);
  assert.equal(result.storage.versionchange.version, 2);
  const screenshotPath = join(PACKAGE_ROOT, '.build', 'startup-generated-browser-evidence',
    'appearance-settings-preview-compact.png');
  await mkdir(dirname(screenshotPath), { recursive: true });
  const screenshot = await cdp.call('Page.captureScreenshot', {
    format: 'png', fromSurface: true, captureBeyondViewport: true,
  });
  await writeFile(screenshotPath, Buffer.from(screenshot.data, 'base64'));
  const previewCommand = await readFile(join(PACKAGE_ROOT, '预览动画.command'), 'utf8');
  assert.ok(previewCommand.includes('cd "$(dirname "$0")"')
    && previewCommand.includes('open "$PWD/index.html"'),
  'the supported native preview command opens this same local index.html');
  const directPreviewURL = pathToFileURL(join(PACKAGE_ROOT, 'index.html')).href;
  await cdp.call('Page.navigate', { url: directPreviewURL });
  await until(() => cdp.evaluate('document.readyState === "complete" && typeof createImageSettings === "function"'),
    10_000, 'actual file:// index page and preview scripts');
  const directFilePreview = await cdp.evaluate(`(async () => {
    const allocated = [];
    const url = {
      createObjectURL(file) { allocated.push(file); return URL.createObjectURL(file); },
      revokeObjectURL(value) { URL.revokeObjectURL(value); },
    };
    const api = createImageSettings({ document, Image, URL: url,
      setTimeout: window.setTimeout.bind(window), clearTimeout: window.clearTimeout.bind(window), performance });
    const header = new Uint8Array(24);
    header.set([137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82]);
    new DataView(header.buffer).setUint32(16, 24000, false);
    new DataView(header.buffer).setUint32(20, 2001, false);
    const file = new File([header], 'over-limit.png', { type: 'image/png' });
    const outcome = await api.importImage(file, 'avatar').then(
      () => ({ reason: '', causeCode: '' }),
      error => ({ reason: error.reason || '', causeCode: error.causeCode || '' }),
    );
    api.dispose();
    return {
      protocol: location.protocol,
      readerAvailable: typeof globalThis.AGENT_SKIN_READ_RAW_DIMENSIONS === 'function',
      outcome,
      objectURLs: allocated.length,
    };
  })()`);
  assert.equal(directFilePreview.protocol, 'file:');
  assert.deepEqual(directFilePreview, {
    protocol: 'file:', readerAvailable: true,
    outcome: { reason: 'asset-invalid', causeCode: 'image-too-large' }, objectURLs: 0,
  }, 'the actual file preview must reject an oversized PNG before creating an object URL');
  console.log(JSON.stringify({
    status: 'PASS',
    scope: 'same-origin HTTP and file:// classic image parser loading, actual local preview preflight, synthetic image import recovery, host-locale settings and theme tokens, real IndexedDB save/reload, two-page conflict and versionchange close',
    formats: result.formats.map(item => item.type),
    boundaryBytes: result.boundarySize,
    objectURLsReleased: result.revokedCount + '/' + result.createdCount,
    workspacePreviewGeometry: result.previewWorkflow.workspacePreviewGeometry,
    screenshotGeometry: result.previewWorkflow.screenshotGeometry,
    settingsScreenshot: screenshotPath,
    storage: result.storage,
  }, null, 2));
} catch (error) {
  console.error(error.stack || String(error));
  process.exitCode = 1;
} finally {
  await cleanup();
}
