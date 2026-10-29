import assert from 'node:assert/strict';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import test from 'node:test';

const SOURCE_PATH = join(dirname(fileURLToPath(import.meta.url)), '..', 'wallpaper', 'renderer.js');
const { installRenderer } = await import(pathToFileURL(SOURCE_PATH));
const CSS = '[data-azhou-wallpaper="active"]{--azhou-style-ready:ready}';
const HASH = 'a'.repeat(64);
const GOOD_IMAGE = 'data:image/png;base64,AA==';
const PROPERTY_IMAGE = '--azhou-wallpaper-image';
const PROPERTY_WASH = '--azhou-wallpaper-wash';
const PROPERTY_SURFACE = '--azhou-wallpaper-surface';
const ATTRIBUTE = 'data-azhou-wallpaper';
const STYLE_ID = 'azhou-wallpaper-style';

class StyleDeclaration {
  constructor() { this.properties = new Map(); }
  setProperty(name, value, priority = '') { this.properties.set(name, [String(value), priority]); }
  getPropertyValue(name) { return this.properties.get(name)?.[0] || ''; }
  getPropertyPriority(name) { return this.properties.get(name)?.[1] || ''; }
  removeProperty(name) { const value = this.getPropertyValue(name); this.properties.delete(name); return value; }
}

class Node {
  constructor(name, { style = {}, selectors = {}, protected: isProtected = false } = {}) {
    this.name = name;
    this.styles = style;
    this.selectors = selectors;
    this.protected = isProtected;
    this.attributes = new Map();
    this.style = new StyleDeclaration();
    this.children = [];
    this.parentNode = null;
    this.connected = true;
  }
  get isConnected() { return this.connected && (!this.parentNode || this.parentNode.isConnected); }
  set isConnected(value) { this.connected = value; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  appendChild(child) { this.children.push(child); child.parentNode = this; child.connected = this.isConnected; return child; }
  remove() {
    this.connected = false;
    if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(item => item !== this);
    this.parentNode = null;
  }
  closest() { return this.protected ? this : null; }
  querySelector(selector) {
    return this.selectors[selector]?.[0] || this.children.find(child => child.closest?.(selector)) || null;
  }
  querySelectorAll(selector) { return this.selectors[selector] || this.children.filter(child => child.closest?.(selector)); }
  getClientRects() { return this.styles.rects === 0 ? [] : [{}]; }
}

function sceneNode(name, style = {}, extra = {}) {
  return new Node(name, { style: {
    display: 'block', visibility: 'visible', opacity: '1', content: 'none',
    backgroundColor: 'transparent', backgroundImage: 'none', boxShadow: 'none',
    filter: 'none', backdropFilter: 'none', webkitBackdropFilter: 'none',
    maskImage: 'none', webkitMaskImage: 'none', position: 'static', pointerEvents: 'auto',
    ...style,
  }, ...extra });
}

function createPage({ route = '/', url = 'app://-/index.html?initialRoute=%2F', preview = false,
  decode = 'ok', bitmap = 'absent', width = 2048, height = 1024, effective = true, connected = true,
  current = true, namespaceDuringDecode, styleDuringDecode, decorations = {}, shell = true,
  originalAttribute = null, originalImage = '', originalWash = '', originalSurface = '',
  pixelReadable = true, timeout = false } = {}) {
  const revoked = [];
  const bitmapOperations = [];
  let drawCount = 0, pixelReadCount = 0;
  const timers = new Map();
  let nextTimer = 1;
  const prior = Object.getOwnPropertyDescriptor(globalThis, '__azhouWallpaper');
  if (prior) delete globalThis.__azhouWallpaper;
  let objectURL = '';
  class TestURL extends URL {
    static createObjectURL() { objectURL = `blob:wallpaper-${revoked.length + 1}`; return objectURL; }
    static revokeObjectURL(value) { revoked.push(value); }
  }
  const root = new Node('html');
  root.setAttribute(ATTRIBUTE, originalAttribute ?? 'baseline');
  root.style.setProperty(PROPERTY_IMAGE, originalImage, originalImage ? 'important' : '');
  root.style.setProperty(PROPERTY_WASH, originalWash, originalWash ? 'important' : '');
  root.style.setProperty(PROPERTY_SURFACE, originalSurface, originalSurface ? 'important' : '');
  const body = sceneNode('body');
  const frame = sceneNode('frame');
  const main = sceneNode('main');
  const page = sceneNode('page');
  const workspace = sceneNode('workspace');
  const footer = sceneNode('footer');
  const fade = sceneNode('footer-fade');
  const topFade = sceneNode('top-fade');
  const sticky = sceneNode('sticky');
  const unknownFooter = decorations.unknownFooter || null;
  const unknownSticky = decorations.unknownSticky || null;
  const unknownScroll = decorations.unknownScroll || null;
  const frameSelector = '[data-app-shell-frame]';
  const mainSelector = '[data-app-shell-main-surface],[data-app-shell-page-surface]';
  const surfaceSelector = '[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]';
  const workspaceSelector = '[data-app-shell-main-surface] :is([class^="_WorkspaceContent_"],[class*=" _WorkspaceContent_"])';
  const footerSelector = '[data-app-shell-main-surface] [data-thread-scroll-footer]';
  const stickySelector = '[data-app-shell-main-surface] .thread-scroll-container .pointer-events-none.sticky.bottom-0';
  const backgroundSelector = footerSelector + ' > :is([class^="_background_"],[class*=" _background_"])';
  const fadeSelector = stickySelector + ' > :is([class^="_background_"],[class*=" _background_"]):is([class^="_fade_"],[class*=" _fade_"])';
  const topSelector = '[data-app-shell-main-surface] :is([class^="_MainContentTopFade_"],[class*=" _MainContentTopFade_"])';
  const scrollUnknownSelector = '[data-app-shell-main-surface] .thread-scroll-container :is(:is([class^="_background_"],[class*=" _background_"]),:is([class^="_fade_"],[class*=" _fade_"]))';
  const appSelectors = {
    [surfaceSelector]: [frame, main, page],
    [workspaceSelector]: [workspace],
    [footerSelector + ',' + backgroundSelector]: [footer],
    [fadeSelector]: [fade],
    [topSelector]: [topFade],
    [stickySelector]: [sticky],
    [scrollUnknownSelector]: unknownScroll ? [unknownScroll] : [],
  };
  if (unknownFooter) appSelectors[footerSelector] = [footer];
  if (unknownSticky) appSelectors[stickySelector] = [sticky];
  if (unknownFooter) { footer.children.push(unknownFooter); unknownFooter.parentNode = footer; }
  if (unknownSticky) { sticky.children.push(unknownSticky); unknownSticky.parentNode = sticky; }
  const applicationRoot = new Node('app-root', { selectors: appSelectors });
  applicationRoot.isConnected = connected;
  applicationRoot.querySelector = selector => {
    if (selector === frameSelector) return shell ? frame : null;
    if (selector === mainSelector) return shell ? main : null;
    return applicationRoot.selectors[selector]?.[0] || null;
  };
  applicationRoot.querySelectorAll = selector => {
    if (selector === surfaceSelector) return [frame, main, page];
    if (selector === workspaceSelector) return [workspace];
    if (selector === footerSelector + ',' + backgroundSelector) return [footer];
    if (selector === fadeSelector) return [fade];
    if (selector === topSelector) return [topFade];
    if (selector === stickySelector) return unknownSticky ? [sticky] : [];
    if (selector === footerSelector) return unknownFooter ? [footer] : [];
    if (selector === scrollUnknownSelector) return applicationRoot.selectors[selector] || (unknownScroll ? [unknownScroll] : []);
    return [];
  };
  const head = new Node('head');
  const styleElements = [];
  const document = {
    body, head, documentElement: root,
    getElementById(id) {
      if (id === 'root') return applicationRoot;
      return styleElements.find(element => element.id === id && element.isConnected) || null;
    },
    createElement(name) {
      const element = new Node(name);
      element.isConnected = false;
      element.id = '';
      element.disabled = false;
      element.textContent = '';
      if (name === 'canvas') {
        element.width = 0;
        element.height = 0;
        element.getContext = () => ({
          drawImage() { drawCount++; },
          getImageData() {
            pixelReadCount++;
            return { data: pixelReadable ? Uint8ClampedArray.of(12, 34, 56, 255) : Uint8ClampedArray.of(12, 34, 56) };
          },
        });
      }
      if (name === 'style') {
        element.setAttribute('data-azhou-owner', '');
        Object.defineProperty(element, 'id', {
          get() { return element.attributes.get('__id') || ''; },
          set(value) { if (value) element.attributes.set('__id', value); else element.attributes.delete('__id'); },
        });
        const set = element.setAttribute.bind(element);
        element.setAttribute = (key, value) => { set(key, value); if (key === 'data-azhou-owner') element.owner = String(value); };
        const get = element.getAttribute.bind(element);
        element.getAttribute = key => key === 'data-azhou-owner' ? (element.owner ?? get(key)) : get(key);
        const removeAttribute = element.removeAttribute.bind(element);
        element.removeAttribute = key => { if (key === 'id') element.id = ''; else removeAttribute(key); };
        const remove = element.remove.bind(element);
        element.remove = () => { remove(); };
        styleElements.push(element);
      }
      return element;
    },
    querySelectorAll(selector) {
      if (selector === '#' + STYLE_ID) return styleElements.filter(element => element.isConnected && element.id === STYLE_ID);
      return [];
    },
  };
  const image = {
    complete: false, naturalWidth: width, naturalHeight: height, src: '',
    async decode() {
      if (namespaceDuringDecode) Object.defineProperty(globalThis, '__azhouWallpaper', {
        configurable: true, writable: true, value: namespaceDuringDecode,
      });
      if (styleDuringDecode) document.head.appendChild(styleDuringDecode);
      if (decode === 'reject') { image.complete = true; throw new Error('decoder detail'); }
      if (decode === 'timeout') return new Promise(() => {});
      if (decode === 'pending') {
        image.complete = true;
        return new Promise(() => {});
      }
      if (decode === 'empty') { image.naturalWidth = 0; return; }
      image.complete = true;
    },
  };
  Object.defineProperty(image, 'src', {
    get() { return image._src || ''; },
    set(value) { image._src = value; if (!value) image.complete = false; },
  });
  const window = {};
  window.top = window;
  if (bitmap !== 'absent') {
    window.createImageBitmap = source => {
      const operation = { source, bitmap: null };
      bitmapOperations.push(operation);
      if (bitmap === 'reject') return Promise.reject(new Error('bitmap decoder detail'));
      if (bitmap === 'pending') return new Promise(resolve => {
        operation.resolve = value => { operation.bitmap = value; resolve(value); };
      });
      const value = { width: bitmap === 'wrong-dimensions' ? source.naturalWidth - 1 : source.naturalWidth,
        height: source.naturalHeight, closed: false, close() { this.closed = true; } };
      operation.bitmap = value;
      return Promise.resolve(value);
    };
  }
  const globals = { window, document, location: { href: url }, URL: TestURL, Image: function Image() { return image; },
    createImageBitmap: window.createImageBitmap,
    CSS: { supports: (kind, value) => kind === 'color'
      && /^(?:#[\da-f]{3,8}|(?:rgb|rgba|hsl|hsla)\([^)]*\)|transparent|currentcolor)$/i.test(String(value).trim()) },
    getComputedStyle(node, pseudo) {
      const activeStyle = styleElements.find(element => element.isConnected && element.id === STYLE_ID && !element.disabled);
      if (node === body) return {
        backgroundColor: 'transparent', backgroundImage: effective && activeStyle ? `linear-gradient(red,blue), url("${objectURL}")` : 'none',
        backgroundSize: effective ? 'auto, cover' : 'auto', backgroundAttachment: effective ? 'fixed, fixed' : 'scroll',
        backgroundPosition: 'center, center',
        getPropertyValue: name => name === '--azhou-style-ready' && effective && activeStyle ? ' ready ' : '',
      };
      if (node === applicationRoot) return { backgroundColor: 'transparent', backgroundImage: 'none' };
      if (node === workspace && pseudo === '::before') return { display: 'none', content: 'none', backgroundColor: 'transparent', backgroundImage: 'none' };
      return node.styles;
    },
    innerWidth: 1512, innerHeight: 889,
  };
  const saved = new Map();
  for (const [key, value] of Object.entries({ ...globals, innerWidth: 1512, devicePixelRatio: 2 })) {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    globalThis[key] = value;
  }
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  if (timeout === 'controlled') {
    globalThis.setTimeout = (callback, delay = 0) => {
      const id = nextTimer++;
      timers.set(id, { callback, delay });
      return id;
    };
    globalThis.clearTimeout = id => timers.delete(id);
  } else if (timeout) {
    globalThis.setTimeout = callback => { queueMicrotask(callback); return 1; };
    globalThis.clearTimeout = () => {};
  }
  function restore() {
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
    if (prior) Object.defineProperty(globalThis, '__azhouWallpaper', prior);
    else delete globalThis.__azhouWallpaper;
  }
  return { document, root, applicationRoot, head, styleElements, image, revoked, restore,
    bitmapOperations, timers,
    get drawCount() { return drawCount; }, get pixelReadCount() { return pixelReadCount; },
    fireTimer(delay) {
      const entry = [...timers.entries()].find(([_id, timer]) => timer.delay === delay);
      if (!entry) return false;
      timers.delete(entry[0]);
      entry[1].callback();
      return true;
    },
    async waitForTimer(delay) {
      for (let attempt = 0; attempt < 20; attempt++) {
        if ([...timers.values()].some(timer => timer.delay === delay)) return true;
        await Promise.resolve();
      }
      return false;
    },
    payload: { version: '0.9.0', preview, css: CSS, image: GOOD_IMAGE, imageSHA256: HASH, surface: '#10121c' },
    setPageConnected(value) { applicationRoot.isConnected = value; } };
}

async function onPage(options, operation) {
  const page = createPage(options);
  try { return await operation(page); } finally { page.restore(); }
}

test('the renderer applies one decoded local scene, reports a stable receipt, and restores the host baseline', async () => {
  await onPage({ originalAttribute: 'host', originalImage: 'url(host-image)', originalWash: 'host-wash',
    originalSurface: '#fafafa' }, async page => {
    const result = await installRenderer({ ...page.payload, strength: 0 });
    assert.equal(result.applied, true);
    assert.equal(result.imageDecoded, true);
    assert.equal(result.image.displayMode, 'cover');
    assert.equal(result.image.devicePixelRatio, 2);
    assert.equal(result.washMatched, true);
    assert.equal(result.persistentAnimation, false);
    assert.equal(globalThis.__azhouWallpaper.status().applied, true);
    const api = globalThis.__azhouWallpaper;
    assert.equal(page.root.style.getPropertyValue(PROPERTY_SURFACE), '#10121c');
    assert.equal(api.updateSurface('rgb(10, 20, 30)'), true);
    assert.equal(api.updateSurface('not-a-color'), false, 'invalid updates never reach the host CSS variable');
    assert.equal(page.root.style.getPropertyValue(PROPERTY_SURFACE), 'rgb(10, 20, 30)');
    const disposed = api.dispose();
    assert.equal(disposed.reason, 'disposed');
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'host');
    assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE), 'url(host-image)');
    assert.equal(page.root.style.getPropertyPriority(PROPERTY_IMAGE), 'important');
    assert.equal(page.root.style.getPropertyValue(PROPERTY_WASH), 'host-wash');
    assert.equal(page.root.style.getPropertyValue(PROPERTY_SURFACE), '#fafafa');
    assert.equal(page.root.style.getPropertyPriority(PROPERTY_SURFACE), 'important');
    assert.equal(page.revoked.length, 1);
    assert.equal(globalThis.__azhouWallpaper, undefined);
  });
});

test('surface updates preserve host-owned values or priorities through disposal', async t => {
  for (const scenario of [
    { name: 'host changes the value', value: 'rgb(100, 110, 120)', priority: 'important' },
    { name: 'host changes only the priority', value: '#10121c', priority: 'important' },
  ]) {
    await t.test(scenario.name, async () => onPage({}, async page => {
      await installRenderer(page.payload);
      const api = globalThis.__azhouWallpaper;
      page.root.style.setProperty(PROPERTY_SURFACE, scenario.value, scenario.priority);

      assert.equal(api.updateSurface('rgb(40, 50, 60)'), false);
      assert.deepEqual(page.root.style.properties.get(PROPERTY_SURFACE), [scenario.value, scenario.priority]);
      api.dispose();
      assert.deepEqual(page.root.style.properties.get(PROPERTY_SURFACE), [scenario.value, scenario.priority]);
    }));
  }
});

test('the renderer rejects unsupported pages, payloads, image bytes, and shells before installation', async t => {
  await t.test('untrusted iframe', async () => onPage({}, async page => {
    globalThis.window.top = {};
    await assert.rejects(installRenderer(page.payload), { code: 'unexpected-page' });
  }));
  await t.test('untrusted route', async () => onPage({ url: 'app://-/index.html?initialRoute=%2Fquick-chat' }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'unexpected-page' });
  }));
  await t.test('malformed CSS, surface and strength', async () => onPage({}, async page => {
    await assert.rejects(installRenderer({ ...page.payload, css: '@import url(https://example.test/x);' }), { code: 'invalid-local-payload' });
    await assert.rejects(installRenderer({ ...page.payload, surface: 'not-a-color' }), { code: 'invalid-local-payload' });
    await assert.rejects(installRenderer({ ...page.payload, strength: 76 }), { code: 'invalid-local-payload' });
  }));
  await t.test('non-base64 image', async () => onPage({}, async page => {
    await assert.rejects(installRenderer({ ...page.payload, image: 'https://example.test/scene.png' }), { code: 'invalid-local-image' });
  }));
  await t.test('missing shell', async () => onPage({ shell: false }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'unsupported-shell-no-surfaces' });
  }));
  await t.test('foreign namespace', async () => onPage({}, async page => {
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, value: { owner: 'other' } });
    await assert.rejects(installRenderer(page.payload), { code: 'namespace-conflict' });
  }));
  await t.test('foreign style id', async () => onPage({}, async page => {
    const style = page.document.createElement('style'); style.id = STYLE_ID;
    style.setAttribute('data-azhou-owner', 'other'); page.head.appendChild(style);
    await assert.rejects(installRenderer(page.payload), { code: 'style-id-conflict' });
  }));
});

test('a complete image with a pending decode can be confirmed from a pixel-checked bitmap', async () => {
  await onPage({ decode: 'pending', bitmap: 'ok', timeout: 'controlled' }, async page => {
    const installation = installRenderer(page.payload);
    assert.equal(await page.waitForTimer(250), true, 'the bounded bitmap verification is scheduled');
    assert.equal(page.fireTimer(250), true);
    const result = await installation;
    assert.equal(result.applied, true);
    assert.equal(page.bitmapOperations.length, 1);
    assert.equal(page.bitmapOperations[0].bitmap.closed, true, 'the validation bitmap is closed before install');
    assert.equal(page.drawCount, 1, 'the bitmap is drawn to a scratch canvas');
    assert.equal(page.pixelReadCount, 1, 'the scratch pixel is read back before install');
    assert.equal(page.timers.size, 0, 'the four-second timer is cleared after bitmap verification');
    globalThis.__azhouWallpaper.dispose();
    assert.equal(page.revoked.length, 1, 'the installed image URL remains owned until dispose');
  });
});

test('invalid or unavailable bitmap evidence cannot replace native image decoding', async t => {
  const scenarios = [
    { name: 'a rejected native image is not accepted from a synthetic bitmap', decode: 'reject', bitmap: 'ok',
      expected: 'image-decode-failed', fallback: false },
    { name: 'a rejected bitmap remains bounded by the existing decode timeout', decode: 'pending', bitmap: 'reject',
      expected: 'image-decode-timeout', fallback: true },
    { name: 'a dimension mismatch remains bounded by the existing decode timeout', decode: 'pending', bitmap: 'wrong-dimensions',
      expected: 'image-decode-timeout', fallback: true },
    { name: 'pixels that cannot be read back are not accepted', decode: 'pending', bitmap: 'ok', pixelReadable: false,
      expected: 'image-decode-timeout', fallback: true },
    { name: 'an incomplete image is not accepted from a bitmap', decode: 'timeout', bitmap: 'ok',
      expected: 'image-decode-timeout', fallback: true, bitmapCalls: 0 },
    { name: 'no createImageBitmap keeps the existing decode timeout', decode: 'pending', bitmap: 'absent',
      expected: 'image-decode-timeout', fallback: false },
  ];
  for (const scenario of scenarios) {
    await t.test(scenario.name, async () => onPage({ decode: scenario.decode, bitmap: scenario.bitmap,
      pixelReadable: scenario.pixelReadable, timeout: 'controlled' }, async page => {
      const installation = installRenderer(page.payload);
      if (scenario.fallback) {
        assert.equal(await page.waitForTimer(250), true);
        assert.equal(page.fireTimer(250), true);
        await Promise.resolve();
      } else if (scenario.decode === 'reject') {
        await assert.rejects(installation, { code: scenario.expected });
      }
      if (scenario.decode !== 'reject') {
        assert.equal(await page.waitForTimer(4000), true);
        assert.equal(page.fireTimer(4000), true);
        await assert.rejects(installation, { code: scenario.expected });
      }
      assert.equal(page.bitmapOperations.length, scenario.bitmapCalls ?? (scenario.fallback ? 1 : 0));
      assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
      assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline', 'validation does not take style ownership');
      assert.equal(page.revoked.length, 1, 'failed validation revokes its Blob URL');
      assert.equal(page.image.src, '', 'failed validation clears the image source');
      if (scenario.bitmap === 'wrong-dimensions') assert.equal(page.bitmapOperations[0].bitmap.closed, true);
      if (scenario.pixelReadable === false) {
        assert.equal(page.bitmapOperations[0].bitmap.closed, true);
        assert.equal(page.drawCount, 1);
        assert.equal(page.pixelReadCount, 1);
      }
      assert.equal(page.timers.size, 0, 'decode and fallback timers are released');
    }));
  }
});

test('a bitmap that completes after decode timeout is closed without taking ownership', async () => {
  await onPage({ decode: 'pending', bitmap: 'pending', timeout: 'controlled' }, async page => {
    const installation = installRenderer(page.payload);
    assert.equal(await page.waitForTimer(250), true);
    assert.equal(page.fireTimer(250), true);
    assert.equal(page.bitmapOperations.length, 1);
    assert.equal(await page.waitForTimer(4000), true);
    assert.equal(page.fireTimer(4000), true);
    await assert.rejects(installation, { code: 'image-decode-timeout' });
    assert.equal(page.revoked.length, 1);
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);

    const bitmap = { width: page.image.naturalWidth, height: page.image.naturalHeight,
      closed: false, close() { this.closed = true; } };
    page.bitmapOperations[0].resolve(bitmap);
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(bitmap.closed, true, 'a late bitmap is closed after the timeout already failed');
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
    assert.equal(page.revoked.length, 1, 'late completion does not change URL ownership');
  });
});

test('a canceled page closes a pending validation bitmap before any style commit', async () => {
  await onPage({ decode: 'pending', bitmap: 'pending', timeout: 'controlled' }, async page => {
    let current = true;
    const installation = installRenderer({ ...page.payload, isCurrent: () => current });
    assert.equal(await page.waitForTimer(250), true);
    assert.equal(page.fireTimer(250), true);
    assert.equal(page.bitmapOperations.length, 1);
    current = false;

    const bitmap = { width: page.image.naturalWidth, height: page.image.naturalHeight,
      closed: false, close() { this.closed = true; } };
    page.bitmapOperations[0].resolve(bitmap);
    await assert.rejects(installation, { code: 'page-changed-during-decode' });
    assert.equal(bitmap.closed, true, 'the validation bitmap is closed before cancellation returns');
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
    assert.equal(page.root.style.getPropertyValue(PROPERTY_SURFACE), '');
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
    assert.equal(page.revoked.length, 1);
    assert.equal(page.image.src, '');
  });
});

test('decode and page identity are checked again after the image resolves', async t => {
  await t.test('invalid base64', async () => onPage({}, async page => {
    await assert.rejects(installRenderer({ ...page.payload, image: 'data:image/png;base64,====' }), { code: 'invalid-local-image' });
  }));
  await t.test('decoder failure is sanitized and releases the blob', async () => onPage({ decode: 'reject' }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'image-decode-failed' });
    assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
    assert.equal(page.image.src, '');
  }));
  await t.test('decoded image has dimensions', async () => onPage({ decode: 'empty' }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'image-decode-failed' });
  }));
  await t.test('page generation was canceled', async () => onPage({ current: false }, async page => {
    const payload = { ...page.payload, isCurrent: () => false };
    await assert.rejects(installRenderer(payload), { code: 'page-changed-during-decode' });
  }));
  await t.test('application root disappeared', async () => onPage({ connected: false }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'page-changed-during-decode' });
  }));
  await t.test('namespace changed to an unknown owner during decode', async () => onPage({ namespaceDuringDecode: { owner: 'other' } }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'namespace-changed-during-decode' });
  }));
  await t.test('another valid installation wins while decoding', async () => onPage({ namespaceDuringDecode: {
    owner: 'azhou.codex-startup-animation', version: '0.7.1', dispose() {}, status() { return {}; },
  } }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'namespace-changed-during-decode' });
  }));
  await t.test('a foreign style appeared during decode', async () => onPage({}, async page => {
    const style = page.document.createElement('style'); style.id = STYLE_ID;
    style.setAttribute('data-azhou-owner', 'other');
    const payload = { ...page.payload, isCurrent: () => true };
    page.image.decode = async () => { page.head.appendChild(style); page.image.complete = true; };
    await assert.rejects(installRenderer(payload), { code: 'style-id-conflict-after-decode' });
  }));
  await t.test('image decode timeout is bounded', async () => onPage({ decode: 'timeout', timeout: true }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'image-decode-timeout' });
    assert.equal(page.revoked.length, 1);
  }));
});

test('preview mode permits only its explicit local fixture routes', async t => {
  await t.test('loopback HTTP preview', async () => onPage({ url: 'http://127.0.0.1:4173/wallpaper/preview.html' }, async page => {
    const result = await installRenderer({ ...page.payload, preview: true });
    assert.equal(result.applied, true);
    globalThis.__azhouWallpaper.dispose();
  }));
  await t.test('file preview path', async () => onPage({ url: 'file:///tmp/wallpaper/preview.html' }, async page => {
    const result = await installRenderer({ ...page.payload, preview: true });
    assert.equal(result.applied, true);
    globalThis.__azhouWallpaper.dispose();
  }));
});

test('the renderer rolls back ineffective styles and disposes only values it still owns', async t => {
  await t.test('CSS was not effective', async () => onPage({ effective: false }, async page => {
    await assert.rejects(installRenderer(page.payload), { code: 'styles-not-effective' });
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
    assert.equal(page.revoked.length, 1);
  }));
  await t.test('host edits survive dispose', async () => onPage({}, async page => {
    await installRenderer(page.payload);
    page.root.style.setProperty(PROPERTY_IMAGE, 'host-edited-image');
    page.root.setAttribute(ATTRIBUTE, 'host-edited');
    globalThis.__azhouWallpaper.dispose();
    assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE), 'host-edited-image');
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'host-edited');
  }));
  await t.test('replacing a current renderer transfers its original baseline', async () => onPage({}, async page => {
    await installRenderer(page.payload);
    const firstAPI = globalThis.__azhouWallpaper;
    const second = await installRenderer({ ...page.payload, strength: 12 });
    assert.equal(second.applied, true);
    assert.equal(firstAPI.status().reason, 'disposed');
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 1);
    globalThis.__azhouWallpaper.dispose();
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
  }));
  await t.test('legacy owner without replacement release hook', async () => onPage({}, async page => {
    const legacyStyle = page.document.createElement('style'); legacyStyle.id = STYLE_ID;
    legacyStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(legacyStyle);
    let disposed = false;
    const legacy = { owner: 'azhou.codex-startup-animation', version: '0.7.1',
      dispose() { disposed = true; }, status() { return {}; } };
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: legacy });
    const result = await installRenderer(page.payload);
    assert.equal(result.applied, true);
    assert.equal(disposed, true);
    globalThis.__azhouWallpaper.dispose();
  }));
  await t.test('legacy replacement preserves an absent surface baseline through replacement and dispose', async () => onPage({}, async page => {
    const legacyStyle = page.document.createElement('style'); legacyStyle.id = STYLE_ID;
    legacyStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(legacyStyle);
    const legacy = { owner: 'azhou.codex-startup-animation', version: '0.7.1', dispose() {}, status() { return {}; } };
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: legacy });

    await installRenderer(page.payload);
    await installRenderer({ ...page.payload, strength: 12 });
    globalThis.__azhouWallpaper.dispose();

    assert.equal(page.root.style.getPropertyValue(PROPERTY_SURFACE), '');
    assert.equal(page.root.style.getPropertyPriority(PROPERTY_SURFACE), '');
    assert.equal(page.root.style.properties.has(PROPERTY_SURFACE), false);
  }));
  await t.test('legacy replacement preserves an important surface baseline through replacement and dispose', async () => onPage({ originalSurface: '#fafafa' }, async page => {
    const legacyStyle = page.document.createElement('style'); legacyStyle.id = STYLE_ID;
    legacyStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(legacyStyle);
    const legacy = { owner: 'azhou.codex-startup-animation', version: '0.7.1', dispose() {}, status() { return {}; } };
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: legacy });

    await installRenderer(page.payload);
    await installRenderer({ ...page.payload, strength: 12 });
    globalThis.__azhouWallpaper.dispose();

    assert.deepEqual(page.root.style.properties.get(PROPERTY_SURFACE), ['#fafafa', 'important']);
  }));
  await t.test('legacy replacement preserves a later host surface edit on dispose', async () => onPage({ originalSurface: '#fafafa' }, async page => {
    const legacyStyle = page.document.createElement('style'); legacyStyle.id = STYLE_ID;
    legacyStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(legacyStyle);
    const legacy = { owner: 'azhou.codex-startup-animation', version: '0.7.1', dispose() {}, status() { return {}; } };
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: legacy });

    await installRenderer(page.payload);
    page.root.style.setProperty(PROPERTY_SURFACE, '#host-surface', 'important');
    globalThis.__azhouWallpaper.dispose();

    assert.deepEqual(page.root.style.properties.get(PROPERTY_SURFACE), ['#host-surface', 'important']);
  }));
  await t.test('failed replacement restores the suspended legacy stylesheet', async () => onPage({ effective: false }, async page => {
    const legacyStyle = page.document.createElement('style'); legacyStyle.id = STYLE_ID;
    legacyStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(legacyStyle);
    const legacy = { owner: 'azhou.codex-startup-animation', version: '0.7.1', dispose() {}, status() { return {}; } };
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: legacy });
    await assert.rejects(installRenderer(page.payload), { code: 'styles-not-effective' });
    assert.equal(legacyStyle.id, STYLE_ID);
    assert.equal(legacyStyle.disabled, false);
  }));
});

test('decorative diagnostics skip protected, hidden, and noninteractive nodes while reporting unknown layers', async () => {
  const unknownSticky = sceneNode('unknown sticky', {
    position: 'absolute', pointerEvents: 'none', backgroundColor: 'rgb(1, 2, 3)',
  });
  const unknownFooter = sceneNode('unknown footer', {
    position: 'fixed', pointerEvents: 'none', boxShadow: '0 0 8px black',
  });
  const unknownScroll = sceneNode('unknown scroll', {
    position: 'sticky', pointerEvents: 'none', filter: 'blur(2px)',
  });
  const protectedDecoration = sceneNode('protected decoration', { position: 'absolute', pointerEvents: 'none',
    backgroundColor: 'red' }, { protected: true });
  const hidden = sceneNode('hidden', { display: 'none', backgroundColor: 'red' });
  const invisible = sceneNode('invisible', { visibility: 'hidden', backgroundColor: 'red' });
  const zeroOpacity = sceneNode('zero opacity', { opacity: '0', backgroundColor: 'red' });
  const noRect = sceneNode('no rect', { rects: 0, backgroundColor: 'red' });
  const transparentFunction = sceneNode('transparent color function', { backgroundColor: 'color(srgb 1 0 0 / 0)' });
  await onPage({ decorations: { unknownSticky, unknownFooter, unknownScroll } }, async page => {
    const selector = '[data-app-shell-main-surface] .thread-scroll-container :is(:is([class^="_background_"],[class*=" _background_"]),:is([class^="_fade_"],[class*=" _fade_"]))';
    page.applicationRoot.selectors[selector] = [unknownScroll, protectedDecoration, hidden, invisible, zeroOpacity, noRect, transparentFunction];
    await assert.rejects(installRenderer(page.payload), error => {
      assert.equal(error.code, 'styles-not-effective');
      assert.match(error.message, /unmatched-footer-decoration/);
      assert.match(error.message, /unmatched-scroll-decoration/);
      assert.match(error.message, /unmatched-sticky-decoration/);
      return true;
    });
  });
});
