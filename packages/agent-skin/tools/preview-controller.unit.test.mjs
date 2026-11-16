import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

/* preview-controller.js runs its whole lifecycle at import time (payload fetch,
   controller construction, initial apply), so the module may be imported only
   once per node --test process: the coverage lcov report emits one record per
   distinct module URL and tools/test-unit-coverage.py refuses duplicates.
   The interactive suites below share that single successful load, while every
   scenario whose outcome is decided during loading (rejections, alternate
   materials) re-executes this very file as a child process with
   PREVIEW_CONTROLLER_CHILD set; the child installs the same mock host, imports
   the controller once and reports the observable outcome as JSON.

   The page mock follows tools/wallpaper-renderer.unit.test.mjs: selector-keyed
   shell nodes, a style-element registry, and a body whose computed
   --azhou-style-ready is derived from the connected stylesheet text, so
   replacing the ready token with "blocked" really deactivates the sheet. */

const SOURCE_PATH = join(dirname(fileURLToPath(import.meta.url)), '..', 'wallpaper', 'preview-controller.js');
const CONTROLLER_URL = pathToFileURL(SOURCE_PATH).href;
const PREVIEW_URL = 'http://127.0.0.1:4173/wallpaper/preview.html';
const WALLPAPER_CSS = 'html[data-azhou-wallpaper="active"] body{--azhou-style-ready: ready;background-color:transparent}';
const STYLE_ID = 'azhou-wallpaper-style';
const PROPERTY_IMAGE = '--azhou-wallpaper-image';
const PNG_BYTES = Uint8Array.of(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3, 4, 5, 6);
const PNG_SHA256 = createHash('sha256').update(PNG_BYTES).digest('hex');
const PNG_DATA_URL = 'data:image/png;base64,' + Buffer.from(PNG_BYTES).toString('base64');
const INVALID_BYTES = Uint8Array.of(105, 110, 118, 97, 108, 105, 100);

const generatedLayer = prefix => ':is([class^="' + prefix + '"],[class*=" ' + prefix + '"])';
const FRAME_SELECTOR = '[data-app-shell-frame]';
const MAIN_SELECTOR = '[data-app-shell-main-surface],[data-app-shell-page-surface]';
const SURFACE_SELECTOR = '[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]';
const WORKSPACE_SELECTOR = '[data-app-shell-main-surface] :is([class^="_WorkspaceContent_"],[class*=" _WorkspaceContent_"])';
const THREAD_FOOTER_SELECTOR = '[data-app-shell-main-surface] [data-thread-scroll-footer]';
const FOOTER_COMBINED_SELECTOR = THREAD_FOOTER_SELECTOR
  + ',' + THREAD_FOOTER_SELECTOR + ' > ' + generatedLayer('_background_')
  + ',' + THREAD_FOOTER_SELECTOR + ' > [aria-hidden="true"].pointer-events-none' + generatedLayer('background-');
const STICKY_SHADE_SELECTOR = '[data-app-shell-main-surface] .thread-scroll-container .pointer-events-none.sticky.bottom-0';
const FADE_SELECTOR = STICKY_SHADE_SELECTOR + ' > ' + generatedLayer('_background_') + generatedLayer('_fade_')
  + ',' + STICKY_SHADE_SELECTOR + ' > [aria-hidden="true"].pointer-events-none' + generatedLayer('background-') + generatedLayer('fade-');
const TOP_FADE_SELECTOR = '[data-app-shell-main-surface] ' + generatedLayer('_MainContentTopFade_');

class StyleDeclaration {
  constructor() { this.properties = new Map(); }
  setProperty(name, value, priority = '') { this.properties.set(name, [String(value), priority]); }
  getPropertyValue(name) { return this.properties.get(name)?.[0] ?? ''; }
  getPropertyPriority(name) { return this.properties.get(name)?.[1] ?? ''; }
  removeProperty(name) { const value = this.getPropertyValue(name); this.properties.delete(name); return value; }
  get cssText() {
    return [...this.properties].map(([name, [value, priority]]) =>
      name + ':' + value + (priority ? ' !' + priority : '') + ';').join('');
  }
  set cssText(text) {
    this.properties.clear();
    for (const match of String(text).matchAll(/([-\w]+)\s*:\s*([^;]*?)\s*(?:!\s*(important)\s*)?(?:;|$)/g)) {
      this.properties.set(match[1], [match[2], match[3] ?? '']);
    }
  }
}

class FixtureNode {
  constructor(name, styles = {}) {
    this.name = name;
    this.styles = styles;
    this.attributes = new Map();
    this.style = new StyleDeclaration();
    this.dataset = {};
    this.children = [];
    this.parentNode = null;
    this.connected = true;
    this.textContent = '';
    this.disabled = false;
  }
  get isConnected() { return this.connected && (!this.parentNode || this.parentNode.isConnected); }
  set isConnected(value) { this.connected = value; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); }
  appendChild(child) { this.children.push(child); child.parentNode = this; child.connected = this.isConnected; return child; }
  remove() {
    this.connected = false;
    if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(item => item !== this);
    this.parentNode = null;
  }
  closest() { return null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  getClientRects() { return [{}]; }
}

function sceneNode(name, style = {}) {
  return new FixtureNode(name, {
    display: 'block', visibility: 'visible', opacity: '1', content: 'none',
    backgroundColor: 'transparent', backgroundImage: 'none', boxShadow: 'none',
    filter: 'none', backdropFilter: 'none', webkitBackdropFilter: 'none',
    maskImage: 'none', webkitMaskImage: 'none', position: 'static', pointerEvents: 'auto',
    ...style,
  });
}

function createPreviewPage({ href, imageOk = true, cssOk = true, imageBytes = PNG_BYTES,
  cssText = WALLPAPER_CSS, composerTransparent = false, readerFails = false, imageBase = 'private' } = {}) {
  const url = href ?? PREVIEW_URL;
  const filename = new URL(url).searchParams.get('image') || 'wallpaper-scene-q-v3.png';
  const fetchCalls = [];
  const revoked = [];
  const blobs = new Map();
  const styleElements = [];
  const images = [];
  let objectCounter = 0;
  let decodeGate = null;

  class TestBlob {
    constructor(parts, options = {}) {
      this.type = options.type ?? '';
      this.bytes = Buffer.concat(parts.map(part => {
        if (ArrayBuffer.isView(part)) return Buffer.from(part.buffer, part.byteOffset, part.byteLength);
        if (part instanceof ArrayBuffer) return Buffer.from(part);
        return Buffer.from(part);
      }));
    }
  }
  class TestURL extends URL {
    static createObjectURL(blob) {
      const address = 'blob:wallpaper-' + (++objectCounter);
      blobs.set(address, blob);
      return address;
    }
    static revokeObjectURL(value) { revoked.push(value); }
  }
  class TestFileReader {
    readAsDataURL(blob) {
      if (readerFails) {
        this.error = new Error('fixture read failure');
        this.onerror?.();
        return;
      }
      this.result = 'data:' + blob.type + ';base64,' + blob.bytes.toString('base64');
      this.onload?.();
    }
  }
  const fixtureFetch = target => {
    fetchCalls.push(String(target));
    if (target === './wallpaper.css') {
      return Promise.resolve({ ok: cssOk, text: () => Promise.resolve(cssText) });
    }
    if (target === '../assets/' + imageBase + '/' + encodeURIComponent(filename)) {
      return Promise.resolve({ ok: imageOk, arrayBuffer: () => Promise.resolve(imageBytes.slice().buffer) });
    }
    return Promise.resolve({ ok: false, text: () => Promise.resolve(''), arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)) });
  };
  const FixtureImage = function Image() {
    const element = {
      complete: false, naturalWidth: 2048, naturalHeight: 1024, _src: '',
      async decode() {
        if (decodeGate) { const gate = decodeGate; decodeGate = null; await gate.promise; }
        const blob = blobs.get(element._src);
        const decodable = !!blob && blob.bytes.length >= 4
          && PNG_BYTES.slice(0, 4).every((byte, index) => blob.bytes[index] === byte);
        element.complete = true;
        if (!decodable) throw new Error('decoder detail');
      },
    };
    Object.defineProperty(element, 'src', {
      get() { return element._src; },
      set(value) { element._src = value; if (!value) element.complete = false; },
    });
    images.push(element);
    return element;
  };

  const root = new FixtureNode('html');
  root.setAttribute('data-azhou-wallpaper', 'baseline');
  const body = sceneNode('body');
  const head = new FixtureNode('head');
  const frameNode = sceneNode('frame');
  frameNode.setAttribute('data-app-shell-frame', '');
  const mainNode = sceneNode('main');
  mainNode.setAttribute('data-app-shell-main-surface', 'default');
  const pageSurface = sceneNode('page');
  pageSurface.setAttribute('data-app-shell-page-surface', 'true');
  const workspace = sceneNode('workspace');
  const footer = sceneNode('footer');
  footer.setAttribute('data-thread-scroll-footer', 'true');
  const plate = sceneNode('footer-plate');
  footer.appendChild(plate);
  const sticky = sceneNode('sticky-shade');
  const fade = sceneNode('footer-fade');
  sticky.appendChild(fade);
  const topFade = sceneNode('top-fade');
  const composer = sceneNode('composer', { backgroundColor: composerTransparent ? 'rgba(30, 30, 34, 0)' : 'rgb(48, 48, 55)' });
  const applicationRoot = new FixtureNode('app-root');
  applicationRoot.querySelector = selector => {
    if (selector === FRAME_SELECTOR) return frameNode.getAttribute('data-app-shell-frame') !== null ? frameNode : null;
    if (selector === MAIN_SELECTOR) return mainNode;
    return null;
  };
  applicationRoot.querySelectorAll = selector => {
    if (selector === SURFACE_SELECTOR) return [frameNode, mainNode, pageSurface];
    if (selector === WORKSPACE_SELECTOR) return [workspace];
    if (selector === THREAD_FOOTER_SELECTOR) return [footer];
    if (selector === FOOTER_COMBINED_SELECTOR) return [footer, plate];
    if (selector === FADE_SELECTOR) return [fade];
    if (selector === TOP_FADE_SELECTOR) return [topFade];
    if (selector === STICKY_SHADE_SELECTOR) return [sticky];
    return [];
  };
  const makeButton = id => ({ id, textContent: '', onclick: null, disabled: false });
  const buttons = { theme: makeButton('theme'), apply: makeButton('apply'), restore: makeButton('restore'), checks: makeButton('checks') };
  const statusEl = { textContent: '' };
  const elementsById = new Map([['result', statusEl], ...Object.values(buttons).map(button => [button.id, button])]);
  const document = {
    body, head, documentElement: root,
    getElementById(id) {
      if (id === 'root') return applicationRoot;
      if (id === STYLE_ID) return styleElements.find(item => item.isConnected && item.id === STYLE_ID) || null;
      return elementsById.get(id) ?? null;
    },
    createElement(tag) {
      const element = new FixtureNode(tag);
      element.isConnected = false;
      if (tag === 'style') {
        let id = '';
        Object.defineProperty(element, 'id', { get() { return id; }, set(value) { id = String(value); } });
        const removeAttribute = element.removeAttribute.bind(element);
        element.removeAttribute = key => { if (key === 'id') id = ''; else removeAttribute(key); };
        styleElements.push(element);
      }
      return element;
    },
    querySelector(selector) {
      if (selector === '.composer') return composer;
      if (selector === FRAME_SELECTOR) return frameNode.getAttribute('data-app-shell-frame') !== null ? frameNode : null;
      return null;
    },
    querySelectorAll(selector) {
      return selector === '#' + STYLE_ID ? styleElements.filter(item => item.isConnected && item.id === STYLE_ID) : [];
    },
  };
  function getComputedStyle(node, pseudo) {
    if (node === body) {
      const sheet = styleElements.find(item => item.isConnected && item.id === STYLE_ID && !item.disabled);
      const ready = sheet ? sheet.textContent.match(/--azhou-style-ready:\s*([A-Za-z-]+)/)?.[1] ?? '' : '';
      return {
        backgroundColor: 'transparent',
        backgroundImage: sheet ? 'linear-gradient(red,blue), ' + root.style.getPropertyValue(PROPERTY_IMAGE) : 'none',
        backgroundSize: 'auto, cover', backgroundAttachment: 'fixed, fixed', backgroundPosition: 'center, center',
        getPropertyValue: name => name === '--azhou-style-ready' ? ' ' + ready + ' ' : '',
      };
    }
    if (node === applicationRoot) return { backgroundColor: 'transparent', backgroundImage: 'none' };
    if (node === workspace && pseudo === '::before') {
      return { display: 'none', content: 'none', backgroundColor: 'transparent', backgroundImage: 'none' };
    }
    return node.styles;
  }
  const window = {};
  window.top = window;

  const priorWallpaper = Object.getOwnPropertyDescriptor(globalThis, '__azhouWallpaper');
  if (priorWallpaper) delete globalThis.__azhouWallpaper;
  delete globalThis.__wallpaperFixture;
  delete globalThis.__wallpaperFixtureError;
  const globals = {
    document, location: { href: url }, fetch: fixtureFetch, FileReader: TestFileReader, Blob: TestBlob,
    URL: TestURL, Image: FixtureImage, getComputedStyle, window,
    CSS: { supports: (kind, value) => kind === 'color'
      && /^(?:#[\da-f]{3,8}|(?:rgb|rgba|hsl|hsla)\([^)]*\)|transparent|currentcolor)$/i.test(String(value).trim()) },
    innerWidth: 1512, innerHeight: 889, devicePixelRatio: 2,
  };
  const saved = new Map();
  for (const key of Object.keys(globals)) {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    globalThis[key] = globals[key];
  }
  return {
    document, root, head, applicationRoot, frameNode, composer, buttons, statusEl,
    styleElements, fetchCalls, revoked, images,
    holdNextDecode() {
      let release;
      const promise = new Promise(resolve => { release = resolve; });
      decodeGate = { promise };
      return () => release();
    },
    restore() {
      for (const [key, descriptor] of saved) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
      if (priorWallpaper) Object.defineProperty(globalThis, '__azhouWallpaper', priorWallpaper);
      else delete globalThis.__azhouWallpaper;
      delete globalThis.__wallpaperFixture;
      delete globalThis.__wallpaperFixtureError;
    },
  };
}

const CHILD_SCENARIOS = {
  'name-traversal': { href: PREVIEW_URL + '?image=../assets/private/evil.png' },
  'name-extension': { href: PREVIEW_URL + '?image=scene.gif' },
  'scene-missing': { href: PREVIEW_URL + '?image=missing.png', imageOk: false },
  'css-missing': { cssOk: false },
  'reader-failure': { readerFails: true },
  'initial-failure': { imageBytes: INVALID_BYTES },
  'payload-webp': { href: PREVIEW_URL + '?image=scene.webp' },
  'library-fallback': { imageBase: 'azhou' },
};

if (process.env.PREVIEW_CONTROLLER_CHILD) {
  const page = createPreviewPage(CHILD_SCENARIOS[process.env.PREVIEW_CONTROLLER_CHILD] ?? {});
  try {
    await import(CONTROLLER_URL);
    const controller = globalThis.__wallpaperFixture;
    const payload = controller?.payload;
    process.stdout.write('@@RESULT@@' + JSON.stringify({
      fixtureError: globalThis.__wallpaperFixtureError ?? null,
      statusText: page.statusEl.textContent,
      fetchCalls: page.fetchCalls,
      fixtureMounted: controller !== undefined,
      handlersBound: page.buttons.apply.onclick !== null,
      payload: payload && { ...payload },
      wallpaperApplied: globalThis.__azhouWallpaper?.status().applied ?? null,
    }));
  } catch (error) {
    process.stdout.write('@@RESULT@@' + JSON.stringify({ crash: error.message }));
  }
} else {

const runChildScenario = name => {
  const child = spawnSync(process.execPath, [fileURLToPath(import.meta.url)], {
    encoding: 'utf8',
    env: { ...process.env, PREVIEW_CONTROLLER_CHILD: name },
  });
  assert.equal(child.status, 0, 'child scenario ' + name + ' must exit cleanly\n' + child.stderr);
  const marker = child.stdout.lastIndexOf('@@RESULT@@');
  assert.notEqual(marker, -1, 'child scenario ' + name + ' reported no outcome\n' + child.stdout + child.stderr);
  return JSON.parse(child.stdout.slice(marker + '@@RESULT@@'.length));
};

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 200; attempt++) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.fail('condition did not become true');
}

test('loading-time rejections and alternate materials run against a fresh child page', async t => {
  await t.test('path traversal in the image parameter', async () => {
    const result = runChildScenario('name-traversal');
    assert.equal(result.fixtureError, '无效的本地素材文件名');
    assert.equal(result.statusText, '无效的本地素材文件名');
    assert.equal(result.fixtureMounted, false);
    assert.deepEqual(result.fetchCalls, [], 'no request leaves the page for a rejected name');
    assert.equal(result.handlersBound, false);
  });
  await t.test('unsupported material extension', async () => {
    const result = runChildScenario('name-extension');
    assert.equal(result.fixtureError, '无效的本地素材文件名');
    assert.deepEqual(result.fetchCalls, []);
  });
  await t.test('missing local scene', async () => {
    const result = runChildScenario('scene-missing');
    assert.equal(result.fixtureError, '缺少本地阿舟素材：missing.png');
    assert.equal(result.statusText, '缺少本地阿舟素材：missing.png');
    assert.deepEqual([...result.fetchCalls].sort(),
      ['../assets/private/missing.png', '../assets/azhou/missing.png', './wallpaper.css'].sort());
  });
  await t.test('unreadable wallpaper stylesheet', async () => {
    const result = runChildScenario('css-missing');
    assert.equal(result.fixtureError, '无法读取壁纸样式');
    assert.deepEqual([...result.fetchCalls].sort(),
      ['../assets/private/wallpaper-scene-q-v3.png', './wallpaper.css'].sort());
  });
  await t.test('material bytes that cannot be read as a data URL', async () => {
    const result = runChildScenario('reader-failure');
    assert.equal(result.fixtureError, 'fixture read failure');
    assert.equal(result.fixtureMounted, false);
  });
  await t.test('failed initial apply surfaces the fixture error but keeps the controller', async () => {
    const result = runChildScenario('initial-failure');
    assert.equal(result.fixtureError, 'AZHOU_WALLPAPER: image-decode-failed');
    assert.equal(result.statusText, 'AZHOU_WALLPAPER: image-decode-failed');
    assert.equal(result.fixtureMounted, true);
    assert.equal(result.handlersBound, true);
  });
  await t.test('explicit webp material', async () => {
    const result = runChildScenario('payload-webp');
    assert.equal(result.fixtureError, null);
    assert.match(result.payload.image, /^data:image\/webp;base64,/);
    assert.deepEqual(result.fetchCalls.filter(call => call.startsWith('../assets/private/')), ['../assets/private/scene.webp']);
    assert.equal(result.wallpaperApplied, true);
  });
  await t.test('without a local overlay the published library serves the image', async () => {
    const result = runChildScenario('library-fallback');
    assert.equal(result.fixtureError, null);
    assert.deepEqual(result.fetchCalls.filter(call => call.startsWith('../assets/')),
      ['../assets/private/wallpaper-scene-q-v3.png', '../assets/azhou/wallpaper-scene-q-v3.png']);
    assert.equal(result.wallpaperApplied, true);
  });
});

test('the fixture controller drives one shared mock host through its full behavior', async t => {
  const page = createPreviewPage({});
  try {
    await import(CONTROLLER_URL);

    await t.test('the loaded payload digests the fetched bytes and the initial apply lands', async () => {
      assert.equal(globalThis.__wallpaperFixtureError, undefined);
      assert.notEqual(globalThis.__wallpaperFixture, undefined);
      const payload = globalThis.__wallpaperFixture.payload;
      assert.deepEqual(Object.keys(payload).sort(), ['css', 'image', 'imageSHA256', 'preview', 'version']);
      assert.equal(payload.version, '0.9.0');
      assert.equal(payload.preview, true);
      assert.equal(payload.css, WALLPAPER_CSS);
      assert.equal(payload.image, PNG_DATA_URL);
      assert.equal(payload.imageSHA256, PNG_SHA256);
      assert.deepEqual([...page.fetchCalls].sort(),
        ['../assets/private/wallpaper-scene-q-v3.png', './wallpaper.css'].sort());
      assert.equal(globalThis.__azhouWallpaper.status().applied, true);
      assert.match(page.statusEl.textContent, /"applied": true/);
    });

    await t.test('the theme button toggles the host dataset and its own label', async () => {
      page.buttons.theme.onclick();
      assert.equal(page.root.dataset.theme, 'light');
      assert.equal(page.buttons.theme.textContent, '深色');
      page.buttons.theme.onclick();
      assert.equal(page.root.dataset.theme, 'dark');
      assert.equal(page.buttons.theme.textContent, '浅色');
    });

    await t.test('a failed apply that is still current reports its error message', async () => {
      page.frameNode.removeAttribute('data-app-shell-frame');
      page.buttons.apply.onclick();
      await waitFor(() => page.statusEl.textContent.includes('AZHOU_WALLPAPER'));
      assert.equal(page.statusEl.textContent, 'AZHOU_WALLPAPER: unsupported-shell-no-surfaces');
      page.frameNode.setAttribute('data-app-shell-frame', '');
    });

    await t.test('a superseded apply never overwrites the report of the newest generation', async () => {
      const release = page.holdNextDecode();
      page.buttons.apply.onclick();
      page.buttons.apply.onclick();
      await waitFor(() => /"applied": true/.test(page.statusEl.textContent));
      release();
      await new Promise(resolve => setImmediate(resolve));
      await new Promise(resolve => setImmediate(resolve));
      assert.match(page.statusEl.textContent, /"applied": true/);
      assert.doesNotMatch(page.statusEl.textContent, /AZHOU_WALLPAPER/,
        'the stale generation must not surface its cancellation error');
      assert.equal(globalThis.__azhouWallpaper.status().applied, true);
      assert.equal(page.revoked.length, 2,
        'the replaced incumbent and the stale attempt release their blob URLs');
    });

    await t.test('restore disposes the installed controller and stays idempotent', async () => {
      assert.equal(page.styleElements.filter(item => item.isConnected && item.id === STYLE_ID).length, 1);
      page.buttons.restore.onclick();
      assert.equal(page.statusEl.textContent, '已恢复模拟宿主底色');
      assert.equal(globalThis.__azhouWallpaper, undefined);
      assert.equal(page.root.getAttribute('data-azhou-wallpaper'), 'baseline');
      assert.equal(page.styleElements.filter(item => item.isConnected && item.id === STYLE_ID).length, 0);
      page.buttons.restore.onclick();
      assert.equal(page.statusEl.textContent, '已恢复模拟宿主底色', 'a second restore finds no controller and stays quiet');
    });

    await t.test('runChecks walks the full verification script and re-enables every button', async () => {
      const disabledTrail = [];
      let current = false;
      Object.defineProperty(page.buttons.checks, 'disabled', {
        get() { return current; },
        set(value) { current = value; disabledTrail.push(value); },
      });
      const summary = await globalThis.__wallpaperFixture.runChecks();
      assert.equal(summary.passed, true);
      assert.deepEqual(summary.checks, ['背景与宿主表面匹配', '图片覆盖固定视口', '输入区域保持不透明',
        '重复应用不会累积样式', '更新失败保留原壁纸', '重复恢复保留原始属性', '缺少宿主锚点时拒绝',
        '坏图和无效样式均被拒绝并回滚']);
      assert.equal(summary.limitations.length, 4);
      assert.match(page.statusEl.textContent, /"passed": true/);
      assert.deepEqual(disabledTrail, [true, false], 'buttons are disabled for the whole script and restored in finally');
      for (const button of Object.values(page.buttons)) assert.equal(button.disabled, false);
      assert.equal(globalThis.__azhouWallpaper.status().applied, true, 'a fresh apply closes the check run');
      assert.equal(page.frameNode.getAttribute('data-app-shell-frame'), '', 'the shell anchor is restored');
      assert.equal(page.styleElements.filter(item => item.isConnected && item.id === STYLE_ID).length, 1);
    });

    await t.test('a failing check still restores buttons and host state through finally', async () => {
      page.composer.styles.backgroundColor = 'rgba(30, 30, 34, 0)';
      const disabledTrail = [];
      let current = false;
      Object.defineProperty(page.buttons.checks, 'disabled', {
        get() { return current; },
        set(value) { current = value; disabledTrail.push(value); },
      });
      page.buttons.checks.onclick();
      await waitFor(() => /"passed": false/.test(page.statusEl.textContent));
      assert.match(page.statusEl.textContent, /输入区域意外透明/);
      assert.deepEqual(disabledTrail, [true, false], 'the failing path also restores the buttons');
      assert.equal(globalThis.__azhouWallpaper, undefined, 'the inner finally released the controller');
      assert.equal(page.root.getAttribute('data-azhou-wallpaper'), 'baseline');
      assert.equal(page.root.style.cssText, '',
        'the inner finally restores the empty inline style snapshot taken before the checks');
      page.composer.styles.backgroundColor = 'rgb(48, 48, 55)';
    });
  } finally {
    page.restore();
  }
});

}
