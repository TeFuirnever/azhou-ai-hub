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
  contains(node) {
    return this === node || this.children.some(child => child.contains(node))
      || Object.values(this.selectors).some(nodes => nodes.includes(node));
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
  const backgroundSelector = footerSelector + ' > :is([class^="_background_"],[class*=" _background_"])'
    + ',' + footerSelector + ' > [aria-hidden="true"].pointer-events-none:is([class^="background-"],[class*=" background-"])';
  const fadeSelector = stickySelector + ' > :is([class^="_background_"],[class*=" _background_"]):is([class^="_fade_"],[class*=" _fade_"])'
    + ',' + stickySelector + ' > [aria-hidden="true"].pointer-events-none:is([class^="background-"],[class*=" background-"]):is([class^="fade-"],[class*=" fade-"])';
  const topSelector = '[data-app-shell-main-surface] :is([class^="_MainContentTopFade_"],[class*=" _MainContentTopFade_"])';
  const scrollUnknownSelector = '[data-app-shell-main-surface] .thread-scroll-container :is(:is([class^="_background_"],[class*=" _background_"]),:is([class^="_fade_"],[class*=" _fade_"]),:is([class^="background-"],[class*=" background-"]),:is([class^="fade-"],[class*=" fade-"]))';
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
      if (node.getAttribute?.('data-azhou-theme-readability') === objectURL && activeStyle?.textContent.includes('data-azhou-theme-readability')) return {backgroundColor:'#202024',backgroundImage:`linear-gradient(red,blue), url("${objectURL}")`,backgroundSize:'100% 100%, cover'};
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

test('uncommitted image resources are released on unexpected synchronous failures', async t => {
  await t.test('image construction failure releases the allocated URL', async () => onPage({}, async page => {
    globalThis.Image = function Image() { throw new Error('injected image construction failure'); };
    await assert.rejects(installRenderer(page.payload), /injected image construction failure/);
    assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
  }));
  await t.test('invalid prior baseline preserves the controller and releases the new URL', async () => onPage({}, async page => {
    const previous = { owner: 'azhou.codex-startup-animation', version: '0.9.0', status() {}, dispose() {},
      __azhouWallpaperBaseline_071: { attribute: null, properties: {} } };
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: previous });
    await assert.rejects(installRenderer(page.payload));
    assert.equal(globalThis.__azhouWallpaper, previous);
    assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
    assert.equal(page.image.src, '');
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
  }));
  await t.test('style construction failure leaves a working controller attached', async () => onPage({}, async page => {
    let disposals = 0;
    const previous = { owner: 'azhou.codex-startup-animation', version: '0.9.0', status() { return { applied: true }; }, dispose() { disposals++; } };
    Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: previous });
    const oldStyle = page.document.createElement('style');
    oldStyle.id = STYLE_ID;
    oldStyle.setAttribute('data-azhou-owner', previous.owner);
    page.head.appendChild(oldStyle);
    const create = page.document.createElement;
    page.document.createElement = function(tag) {
      if (tag === 'style') throw new Error('injected style construction failure');
      return create.call(this, tag);
    };
    await assert.rejects(installRenderer(page.payload), /injected style construction failure/);
    assert.equal(globalThis.__azhouWallpaper, previous);
    assert.equal(disposals, 0);
    assert.equal(oldStyle.isConnected, true);
    assert.equal(oldStyle.id, STYLE_ID);
    assert.equal(oldStyle.disabled, false);
    assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
  }));
  await t.test('style construction failure releases the URL and preserves host state', async () => onPage({}, async page => {
    const create = page.document.createElement;
    page.document.createElement = function(tag) {
      if (tag === 'style') throw new Error('injected style construction failure');
      return create.call(this, tag);
    };
    await assert.rejects(installRenderer(page.payload), /injected style construction failure/);
    assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
    assert.equal(page.image.src, '');
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
  }));
});

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

test('surface update refuses stale page and controller ownership', async t => {
  for (const kind of ['document-root', 'app-replaced', 'app-detached', 'controller-replaced', 'controller-accessor']) {
    await t.test(kind, async () => onPage({}, async page => {
      await installRenderer(page.payload);
      const api = globalThis.__azhouWallpaper;
      const oldValue = page.root.style.getPropertyValue(PROPERTY_SURFACE);
      const originalGet = page.document.getElementById;
      const foreign = { owner: 'foreign' };
      try {
        if (kind === 'document-root') page.document.documentElement = new Node('foreign-html');
        if (kind === 'app-replaced') page.document.getElementById = id => id === 'root' ? new Node('foreign-app') : originalGet.call(page.document, id);
        if (kind === 'app-detached') page.applicationRoot.isConnected = false;
        if (kind === 'controller-replaced') globalThis.__azhouWallpaper = foreign;
        if (kind === 'controller-accessor') Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, get() { throw new Error('foreign getter'); } });
        const result = api.updateSurface('rgb(40, 50, 60)');
        assert.deepEqual({ result, value: page.root.style.getPropertyValue(PROPERTY_SURFACE) },
          { result: false, value: oldValue });
        if (kind === 'controller-replaced') assert.equal(globalThis.__azhouWallpaper, foreign);
      } finally {
        page.document.documentElement = page.root;
        page.document.getElementById = originalGet;
        page.applicationRoot.isConnected = true;
        Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: api });
        api.dispose();
      }
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

test('native and bitmap decoders settle once under interleaving', async t => {
  await t.test('native success still wins after an invalid bitmap', async () => onPage({ bitmap: 'reject', timeout: 'controlled' }, async page => {
    let resolveNative;
    page.image.decode = () => { page.image.complete = true; return new Promise(resolve => { resolveNative = resolve; }); };
    const installation = installRenderer(page.payload);
    assert.equal(await page.waitForTimer(250), true);
    page.fireTimer(250);
    await Promise.resolve();
    resolveNative();
    assert.equal((await installation).applied, true);
    assert.equal(page.bitmapOperations.length, 1);
    assert.equal(page.timers.size, 0);
    globalThis.__azhouWallpaper.dispose();
  }));
  await t.test('fallback success survives a later native rejection', async () => onPage({ bitmap: 'ok', timeout: 'controlled' }, async page => {
    let rejectNative;
    page.image.decode = () => { page.image.complete = true; return new Promise((_resolve, reject) => { rejectNative = reject; }); };
    const installation = installRenderer(page.payload);
    assert.equal(await page.waitForTimer(250), true);
    page.fireTimer(250);
    assert.equal((await installation).applied, true);
    rejectNative(new Error('late native failure'));
    await Promise.resolve();
    assert.equal(globalThis.__azhouWallpaper.status().applied, true);
    assert.equal(page.timers.size, 0);
    globalThis.__azhouWallpaper.dispose();
  }));
  await t.test('late native success after timeout cannot install', async () => onPage({ timeout: 'controlled' }, async page => {
    let resolveNative;
    page.image.decode = () => { page.image.complete = true; return new Promise(resolve => { resolveNative = resolve; }); };
    const installation = installRenderer(page.payload);
    assert.equal(await page.waitForTimer(4000), true);
    page.fireTimer(4000);
    await assert.rejects(installation, { code: 'image-decode-timeout' });
    resolveNative();
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
    assert.equal(page.revoked.length, 1);
    assert.equal(page.timers.size, 0);
  }));
  await t.test('synchronous native decoder throw is sanitized', async () => onPage({ timeout: 'controlled' }, async page => {
    page.image.decode = () => { throw new Error('decoder detail'); };
    await assert.rejects(installRenderer(page.payload), { code: 'image-decode-failed' });
    assert.equal(page.revoked.length, 1);
    assert.equal(page.timers.size, 0);
  }));
  for (const nativeOutcome of ['success', 'failure']) {
    await t.test('late bitmap closes after native ' + nativeOutcome, async () => onPage({ bitmap: 'pending', timeout: 'controlled' }, async page => {
      let resolveNative, rejectNative;
      page.image.decode = () => { page.image.complete = true; return new Promise((resolve, reject) => { resolveNative = resolve; rejectNative = reject; }); };
      const installation = installRenderer(page.payload);
      assert.equal(await page.waitForTimer(250), true);
      page.fireTimer(250);
      assert.equal(page.bitmapOperations.length, 1);
      if (nativeOutcome === 'success') {
        resolveNative();
        assert.equal((await installation).applied, true);
      } else {
        rejectNative(new Error('native failure'));
        await assert.rejects(installation, { code: 'image-decode-failed' });
      }
      const bitmap = { width: page.image.naturalWidth, height: page.image.naturalHeight,
        closed: false, close() { this.closed = true; } };
      page.bitmapOperations[0].resolve(bitmap);
      await Promise.resolve();
      await Promise.resolve();
      assert.equal(bitmap.closed, true);
      assert.equal(page.timers.size, 0);
      if (nativeOutcome === 'success') globalThis.__azhouWallpaper.dispose();
      assert.equal(page.revoked.length, 1);
    }));
  }
});

test('decode and page identity are checked again after the image resolves', async t => {
  await t.test('surface remains the validated value if the caller changes it during decode', async () => onPage({}, async page => {
    const payload = { ...page.payload };
    page.image.decode = async () => {
      payload.surface = 'not-a-color';
      page.image.complete = true;
    };
    await installRenderer(payload);
    assert.equal(page.root.style.getPropertyValue(PROPERTY_SURFACE), '#10121c');
    globalThis.__azhouWallpaper.dispose();
  }));
  await t.test('validated style and digest survive mutation during decode', async () => onPage({}, async page => {
    const payload = { ...page.payload, strength: 42 };
    page.image.decode = async () => {
      payload.css = CSS + '@import url(https://example.invalid/foreign.css);';
      payload.strength = 999;
      payload.imageSHA256 = 'b'.repeat(64);
      page.image.complete = true;
    };
    const result = await installRenderer(payload);
    assert.equal(page.styleElements.find(style => style.isConnected).textContent, CSS);
    assert.equal(result.imageSHA256, HASH);
    assert.ok(page.root.style.getPropertyValue(PROPERTY_WASH).includes('var(--azhou-base) 76%'));
    globalThis.__azhouWallpaper.dispose();
  }));
  await t.test('the validated digest remains fixed for the controller lifetime', async () => onPage({}, async page => {
    const payload = { ...page.payload };
    page.image.decode = async () => { payload.imageSHA256 = 'b'.repeat(64); page.image.complete = true; };
    const result = await installRenderer(payload);
    assert.equal(result.imageSHA256, HASH);
    payload.imageSHA256 = 'c'.repeat(64);
    assert.equal(globalThis.__azhouWallpaper.status().imageSHA256, HASH);
    assert.equal(globalThis.__azhouWallpaper.dispose().imageSHA256, HASH);
  }));
  await t.test('the validated strength remains fixed during decode', async () => onPage({}, async page => {
    const payload = { ...page.payload, strength: 42 };
    page.image.decode = async () => { payload.strength = 999; page.image.complete = true; };
    await installRenderer(payload);
    assert.ok(page.root.style.getPropertyValue(PROPERTY_WASH).includes('var(--azhou-base) 76%'));
    globalThis.__azhouWallpaper.dispose();
  }));
  await t.test('the original cancellation callback remains authoritative during decode', async () => onPage({}, async page => {
    let current = true;
    const payload = { ...page.payload, isCurrent: () => current };
    page.image.decode = async () => { current = false; payload.isCurrent = () => true; page.image.complete = true; };
    await assert.rejects(installRenderer(payload), { code: 'page-changed-during-decode' });
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
  }));
  await t.test('preview permission remains bound to the initial request', async () => onPage({
    url: 'http://127.0.0.1/wallpaper/preview.html', preview: true,
  }, async page => {
    const payload = { ...page.payload };
    page.image.decode = async () => { payload.preview = false; page.image.complete = true; };
    assert.equal((await installRenderer(payload)).applied, true);
    globalThis.__azhouWallpaper.dispose();
  }));
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
    const selector = '[data-app-shell-main-surface] .thread-scroll-container :is(:is([class^="_background_"],[class*=" _background_"]),:is([class^="_fade_"],[class*=" _fade_"]),:is([class^="background-"],[class*=" background-"]),:is([class^="fade-"],[class*=" fade-"]))';
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


function syntheticWallpaperPorts({ validPage = () => true, shellState = () => 'ready', surfaces }) {
  return Object.freeze({
    validPage, shellState, surfaces,
    attributes: Object.freeze({ surfaceMarker: 'data-azhou-synthetic-wallpaper-surface',
      observeFilter: ['data-testid', 'hidden', 'aria-hidden', 'class', 'style'] }),
    css: '\nhtml[data-azhou-wallpaper="active"] #root[data-azhou-synthetic-wallpaper-surface="active"],html[data-azhou-wallpaper="active"] #root main[data-azhou-synthetic-wallpaper-surface="active"]{background-color:transparent!important;background-image:none!important}',
    scope: 'decoded image, viewport cover, unique validated host main and root surfaces; deeper content layers and visual inspection are separate',
  });
}

test('an adapter without the complete wallpaper ports group is refused atomically', async () => {
  for (const wallpaper of [undefined, Object.freeze({ css: 'main{background:transparent}' })]) {
    await onPage({ url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' }, async page => {
      const adapter = Object.freeze({ controllerWallpaper: Object.freeze({ owner: 'azhou.synthetic-startup-animation' }),
        ...(wallpaper ? { wallpaper } : {}) });
      await assert.rejects(installRenderer({ ...page.payload, pageAdapter: adapter }), { code: 'invalid-host-adapter' });
      assert.equal(page.styleElements.length, 0);
    });
  }
});


test('A host adapter renderer uses only its validated main surface and restores owned attributes', async () => {
  const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
  try {
    const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
    main.tagName = 'MAIN';fixture.applicationRoot.contains = node => node === main;
    const adapter = Object.freeze({ controllerWallpaper: Object.freeze({ owner: 'azhou.synthetic-startup-animation' }),
      wallpaper: syntheticWallpaperPorts({ surfaces: () => [main] }) });
    const payload = { ...fixture.payload, pageAdapter: adapter };
    assert.equal((await installRenderer(payload)).applied, true);
    assert.equal(globalThis.__azhouWallpaper.owner, 'azhou.synthetic-startup-animation');
    assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'active');
    assert.equal((await installRenderer(payload)).applied, true);
    globalThis.__azhouWallpaper.dispose();
    assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), null);
    assert.equal(fixture.applicationRoot.getAttribute('data-azhou-synthetic-wallpaper-surface'), null);
  } finally { fixture.restore(); }
});

test('Host adapter capabilities stay bound during image decoding', async t => {
  for (const field of ['css', 'validPage', 'shellState', 'surfaces']) {
    await t.test(field, async () => {
      const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
      try {
        const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
        main.tagName = 'MAIN'; fixture.applicationRoot.contains = node => node === main;
        const ports = { ...syntheticWallpaperPorts({ surfaces: () => [main] }) };
        const originalCSS = ports.css, originalScope = ports.scope;
        const adapter = { controllerWallpaper: { owner: 'azhou.synthetic-startup-animation' }, wallpaper: ports };
        const decode = fixture.image.decode;
        fixture.image.decode = async function () {
          await decode.call(this);
          if (field === 'css') { ports.css = '@import url(https://example.invalid/foreign.css);'; ports.scope = 'changed'; }
          if (field === 'validPage') ports.validPage = () => false;
          if (field === 'shellState') ports.shellState = () => 'unsupported';
          if (field === 'surfaces') ports.surfaces = () => [];
        };
        const result = await installRenderer({ ...fixture.payload, pageAdapter: adapter });
        assert.equal(result.applied, true);
        assert.equal(result.verificationScope, originalScope);
        assert.equal(fixture.styleElements.find(style => style.isConnected).textContent, CSS + originalCSS);
        globalThis.__azhouWallpaper.dispose();
      } finally { fixture.restore(); }
    });
  }
});

test('bound adapter methods retain their receiver and recheck current page state', async () => {
  const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
  try {
    const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
    main.tagName = 'MAIN'; fixture.applicationRoot.contains = node => node === main;
    let pageAllowed = true;
    const ports = { ...syntheticWallpaperPorts({ surfaces: () => [main] }) };
    ports.validPage = function () { assert.equal(this, ports); return pageAllowed; };
    ports.shellState = function () { assert.equal(this, ports); return 'ready'; };
    ports.surfaces = function () { assert.equal(this, ports); return [main]; };
    for (const operation of [ports.validPage, ports.shellState, ports.surfaces]) operation.call = () => { throw new Error('not the callable operation'); };
    const decode = fixture.image.decode;
    fixture.image.decode = async function () { await decode.call(this); pageAllowed = false; };
    const adapter = { controllerWallpaper: { owner: 'azhou.synthetic-startup-animation' }, wallpaper: ports };
    await assert.rejects(installRenderer({ ...fixture.payload, pageAdapter: adapter }), { code: 'page-changed-during-decode' });
    assert.equal(fixture.styleElements.filter(style => style.isConnected).length, 0);
  } finally { fixture.restore(); }
});

test('A host adapter refuses protected, ambiguous or foreign-marked surfaces before styling', async () => {
  for (const mode of ['protected', 'ambiguous', 'foreign']) {
    const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
    try {
      const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
      main.tagName = 'MAIN';main.protected = mode === 'protected';fixture.applicationRoot.contains = node => node === main;
      if (mode === 'foreign') main.setAttribute('data-azhou-synthetic-wallpaper-surface', 'foreign');
      const adapter = Object.freeze({ controllerWallpaper: Object.freeze({ owner: 'azhou.synthetic-startup-animation' }),
        wallpaper: syntheticWallpaperPorts({ surfaces: () => mode === 'ambiguous' ? [main, main] : [main] }) });
      await assert.rejects(installRenderer({ ...fixture.payload, pageAdapter: adapter }), /unsupported-shell|namespace-conflict/);
      assert.equal(fixture.styleElements.length, 0);
      if (mode === 'foreign') assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'foreign');
    } finally { fixture.restore(); }
  }
});


test('A host adapter does not overwrite a surface marker changed during decode or before replacement', async () => {
  for (const mode of ['during-decode', 'replacement']) {
    const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
    try {
      const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
      main.tagName = 'MAIN';fixture.applicationRoot.contains = node => node === main;
      const adapter = Object.freeze({ controllerWallpaper: Object.freeze({ owner: 'azhou.synthetic-startup-animation' }),
        wallpaper: syntheticWallpaperPorts({ surfaces: () => [main] }) });
      const payload = { ...fixture.payload, pageAdapter: adapter };
      let previous;
      if (mode === 'replacement') {
        await installRenderer(payload);previous = globalThis.__azhouWallpaper;
        main.setAttribute('data-azhou-synthetic-wallpaper-surface', 'foreign');
      } else {
        const decode = fixture.image.decode;
        fixture.image.decode = async function () { await decode.call(this);main.setAttribute('data-azhou-synthetic-wallpaper-surface', 'foreign'); };
      }
      await assert.rejects(installRenderer(payload), /namespace-conflict|namespace-changed-during-decode/);
      assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'foreign');
      assert.equal(globalThis.__azhouWallpaper, previous);
      if (previous) previous.dispose();
      assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'foreign');
    } finally { fixture.restore(); }
  }
});

test('replacement hook throwing before side effects keeps the previous wallpaper usable', async () => onPage({}, async page => {
  const oldStyle = page.document.createElement('style'); oldStyle.id = STYLE_ID;
  oldStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(oldStyle);
  const old = { owner: 'azhou.codex-startup-animation', version: '0.9.0', dispose() {}, status() { return { applied: true }; } };
  Object.defineProperty(old, '__azhouWallpaperRelease_071', { value() { throw new Error('release failed before change'); } });
  Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: old });
  await assert.rejects(installRenderer(page.payload), /release failed before change/);
  assert.equal(globalThis.__azhouWallpaper, old);
  assert.equal(oldStyle.id, STYLE_ID);
  assert.equal(oldStyle.disabled, false);
  assert.equal(page.revoked.length, 1);
}));

test('recovered previous controller keeps its original property descriptor', async () => onPage({}, async page => {
  const oldStyle = page.document.createElement('style'); oldStyle.id = STYLE_ID;
  oldStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(oldStyle);
  const old = { owner: 'azhou.codex-startup-animation', version: '0.9.0', dispose() {}, status() { return { applied: true }; } };
  Object.defineProperty(old, '__azhouWallpaperRelease_071', { value() { throw new Error('release failed'); } });
  const before = { configurable: true, writable: true, enumerable: false, value: old };
  Object.defineProperty(globalThis, '__azhouWallpaper', before);
  await assert.rejects(installRenderer(page.payload), /release failed/);
  assert.deepEqual(Object.getOwnPropertyDescriptor(globalThis, '__azhouWallpaper'), before);
}));

test('a failed release restores only a verifiably usable previous controller', async () => {
  for (const mode of ['disposed', 'status-throws', 'style-removed', 'style-mutated', 'foreign-controller']) {
    await onPage({}, async page => {
      const oldStyle = page.document.createElement('style'); oldStyle.id = STYLE_ID;
      oldStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation');
      oldStyle.textContent = 'old owned CSS'; page.head.appendChild(oldStyle);
      const foreign = { foreign: true };
      let oldUsable = true;
      const old = { owner: 'azhou.codex-startup-animation', version: '0.9.0', dispose() {},
        status() { if (mode === 'status-throws') throw new Error('old status unavailable'); return { applied: oldUsable }; } };
      Object.defineProperty(old, '__azhouWallpaperRelease_071', { value() {
        if (mode === 'disposed') oldUsable = false;
        if (mode === 'style-removed') oldStyle.remove();
        if (mode === 'style-mutated') oldStyle.textContent = 'foreign edit';
        if (mode === 'foreign-controller') globalThis.__azhouWallpaper = foreign;
        throw new Error('release interrupted');
      } });
      Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: old });
      await assert.rejects(installRenderer(page.payload), /release interrupted/, mode);
      assert.notEqual(globalThis.__azhouWallpaper, old, mode);
      assert.equal(globalThis.__azhouWallpaper, mode === 'foreign-controller' ? foreign : undefined, mode);
      assert.equal(page.revoked.length, 1, mode);
      if (mode === 'style-mutated') assert.equal(oldStyle.textContent, 'foreign edit');
      if (mode === 'disposed' || mode === 'status-throws') {
        assert.equal(oldStyle.disabled, true, mode);
        assert.equal(oldStyle.id, '', mode);
      }
    });
  }
});

test('a real previous renderer disposed before its style removal fails is not restored', async () => onPage({}, async page => {
  await installRenderer(page.payload);
  const old = globalThis.__azhouWallpaper;
  const oldStyle = page.document.getElementById(STYLE_ID);
  oldStyle.remove = () => { throw new Error('old style removal failed'); };
  await assert.rejects(installRenderer(page.payload), /old style removal failed/);
  assert.equal(old.status().applied, false);
  assert.equal(globalThis.__azhouWallpaper, undefined);
  assert.equal(oldStyle.disabled, true);
  assert.equal(oldStyle.id, '');
  assert.equal(page.revoked.length, 1);
}));


test('recovery does not change an owner installed by the previous status callback', async () => onPage({}, async page => {
  const oldStyle = page.document.createElement('style'); oldStyle.id = STYLE_ID;
  oldStyle.setAttribute('data-azhou-owner', 'azhou.codex-startup-animation'); page.head.appendChild(oldStyle);
  const foreign = { foreign: true };
  const old = { owner: 'azhou.codex-startup-animation', version: '0.9.0', dispose() {},
    status() { globalThis.__azhouWallpaper = foreign; return { applied: false }; } };
  Object.defineProperty(old, '__azhouWallpaperRelease_071', { value() { throw new Error('release interrupted'); } });
  Object.defineProperty(globalThis, '__azhouWallpaper', { configurable: true, writable: true, value: old });
  await assert.rejects(installRenderer(page.payload), /release interrupted/);
  assert.equal(globalThis.__azhouWallpaper, foreign);
  assert.equal(oldStyle.disabled, false);
  assert.equal(oldStyle.id, STYLE_ID);
  assert.equal(page.revoked.length, 1);
}));

test('failed release restores the original values and a working real controller', async () => onPage({}, async page => {
  const fixtureImage = globalThis.Image;
  const fixtureComputedStyle = globalThis.getComputedStyle;
  let created = 0, urls = 0;
  globalThis.Image = function Image() {
    if (created++ === 0) return new fixtureImage();
    return { complete: false, naturalWidth: 2048, naturalHeight: 1024, src: '',
      async decode() { this.complete = true; } };
  };
  globalThis.URL.createObjectURL = () => `blob:recovery-${++urls}`;
  globalThis.getComputedStyle = (node, pseudo) => {
    const computed = fixtureComputedStyle(node, pseudo);
    return node === page.document.body ? { ...computed,
      backgroundImage: `linear-gradient(red,blue), ${page.root.style.getPropertyValue(PROPERTY_IMAGE)}` } : computed;
  };
  await installRenderer(page.payload);
  const real = globalThis.__azhouWallpaper;
  const oldStyle = page.document.getElementById(STYLE_ID);
  const imageBefore = page.root.style.properties.get(PROPERTY_IMAGE);
  const previous = { ...real };
  Object.defineProperty(previous, '__azhouWallpaperBaseline_071', { value: real.__azhouWallpaperBaseline_071 });
  Object.defineProperty(previous, '__azhouWallpaperMarker_090', { value: real.__azhouWallpaperMarker_090 });
  Object.defineProperty(previous, '__azhouWallpaperRelease_071', { value() { throw new Error('release interrupted'); } });
  globalThis.__azhouWallpaper = previous;
  await assert.rejects(installRenderer(page.payload), /release interrupted/);
  assert.equal(globalThis.__azhouWallpaper, previous);
  assert.equal(previous.status().applied, true);
  assert.deepEqual(page.root.style.properties.get(PROPERTY_IMAGE), imageBefore);
  assert.equal(oldStyle.id, STYLE_ID);
  assert.equal(oldStyle.disabled, false);
  assert.deepEqual(page.revoked, ['blob:recovery-2']);
}));

test('Dispose preserves markers on a surface moved outside the original root', async () => {
  const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
  try {
    const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
    main.tagName = 'MAIN'; let inside = true;
    fixture.applicationRoot.contains = node => node === main && inside;
    const adapter = Object.freeze({ controllerWallpaper: Object.freeze({ owner: 'azhou.synthetic-startup-animation' }),
      wallpaper: syntheticWallpaperPorts({ surfaces: () => [main] }) });
    await installRenderer({ ...fixture.payload, pageAdapter: adapter });
    const style = fixture.document.getElementById(STYLE_ID);
    inside = false;
    globalThis.__azhouWallpaper.dispose();
    assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'active');
    assert.equal(fixture.applicationRoot.getAttribute('data-azhou-synthetic-wallpaper-surface'), null);
    assert.equal(style.isConnected, false);
    assert.equal(globalThis.__azhouWallpaper, undefined);
  } finally { fixture.restore(); }
});

test('Dispose leaves markers on a former application root', async () => {
  const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
  try {
    const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
    main.tagName = 'MAIN'; fixture.applicationRoot.contains = node => node === main;
    const adapter = Object.freeze({ controllerWallpaper: Object.freeze({ owner: 'azhou.synthetic-startup-animation' }),
      wallpaper: syntheticWallpaperPorts({ surfaces: () => [main] }) });
    await installRenderer({ ...fixture.payload, pageAdapter: adapter });
    const oldLookup = fixture.document.getElementById;
    const foreignRoot = new Node('replacement-root');
    fixture.document.getElementById = id => id === 'root' ? foreignRoot : oldLookup(id);
    globalThis.__azhouWallpaper.dispose();
    assert.equal(fixture.applicationRoot.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'active');
    assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'active');
    assert.equal(foreignRoot.getAttribute('data-azhou-synthetic-wallpaper-surface'), null);
    assert.equal(globalThis.__azhouWallpaper, undefined);
  } finally { fixture.restore(); }
});

test('dispose does not restore styles on a former document root', async () => onPage({}, async page => {
  await installRenderer(page.payload);
  const oldRoot = page.root;
  const image = oldRoot.style.getPropertyValue(PROPERTY_IMAGE);
  const foreignRoot = new Node('replacement-html');
  page.document.documentElement = foreignRoot;
  globalThis.__azhouWallpaper.dispose();
  assert.equal(oldRoot.getAttribute(ATTRIBUTE), 'active');
  assert.equal(oldRoot.style.getPropertyValue(PROPERTY_IMAGE), image);
  assert.equal(foreignRoot.getAttribute(ATTRIBUTE), null);
  assert.equal(globalThis.__azhouWallpaper, undefined);
}));

test('Dispose preserves a detached recorded surface', async () => {
  const fixture = createPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' });
  try {
    const main = fixture.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
    main.tagName = 'MAIN'; fixture.applicationRoot.contains = node => node === main;
    const adapter = Object.freeze({ controllerWallpaper: Object.freeze({ owner: 'azhou.synthetic-startup-animation' }),
      wallpaper: syntheticWallpaperPorts({ surfaces: () => [main] }) });
    await installRenderer({ ...fixture.payload, pageAdapter: adapter });
    main.isConnected = false;
    globalThis.__azhouWallpaper.dispose();
    assert.equal(main.getAttribute('data-azhou-synthetic-wallpaper-surface'), 'active');
    assert.equal(fixture.applicationRoot.getAttribute('data-azhou-synthetic-wallpaper-surface'), null);
    assert.equal(globalThis.__azhouWallpaper, undefined);
  } finally { fixture.restore(); }
});

test('an incumbent that fully disposes during decode is refused, not silently replaced', async () => {
  await onPage({}, async page => {
    await installRenderer(page.payload);
    const incumbent = globalThis.__azhouWallpaper;
    const decode = page.image.decode;
    page.image.decode = async function () {
      await incumbent.dispose();
      await decode.call(this);
    };
    await assert.rejects(installRenderer(page.payload), { code: 'namespace-changed-during-decode' });
    assert.equal(Object.hasOwn(globalThis, '__azhouWallpaper'), false, 'the disposed incumbent is not revived');
    assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
    assert.equal(page.root.style.getPropertyValue(PROPERTY_SURFACE), '');
    assert.equal(page.revoked.length, 2, 'each attempt releases its own Blob URL');
  });
});

async function onObservedPage(operation) {
  return onPage({}, async page => {
    const { createCodexPageAdapter } = await import('../extension/codex-page-adapter.mjs');
    const { createWallpaperApplicator } = await import('../wallpaper/apply.js');
    const { bootstrapStartup } = await import('../extension/bootstrap.mjs');
    const observers = [];
    let imageCount=0;
    globalThis.Image=function(){if(imageCount++===0)return page.image;return {src:'',complete:false,naturalWidth:page.image.naturalWidth,naturalHeight:page.image.naturalHeight,async decode(){this.complete=true;}};};
    const saved = new Map(['MutationObserver', 'ResizeObserver'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
    class Observer {
      constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
      observe() {}
      takeRecords() { const records = this.records ?? []; this.records = []; return records; }
      disconnect() { this.disconnected = true; }
      trigger(records) { this.callback(records); }
    }
    globalThis.MutationObserver = Observer;
    globalThis.ResizeObserver = Observer;
    const surfaces = page.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'];
    const [frame, main, pageSurface] = surfaces;
    page.root.appendChild(page.applicationRoot);
    page.applicationRoot.appendChild(frame);
    frame.appendChild(main);
    main.appendChild(pageSurface);
    for (const [node, attribute] of [[frame, 'data-app-shell-frame'], [main, 'data-app-shell-main-surface'], [pageSurface, 'data-app-shell-page-surface']]) node.setAttribute(attribute, '');
    const nodes = [page.root, page.applicationRoot, ...surfaces];
    for (const node of nodes) {
      Object.defineProperty(node, 'parentElement', { get() { return this.parentNode; } });
      node.matches = selector => [...node.attributes.keys()].some(attribute => selector.includes(`[${attribute}]`));
      node.closest = function(selector) {
        for (let current = this; current; current = current.parentNode) if (current.matches?.(selector)) return current;
        return null;
      };
      node.getClientRects = () => node.styles.display === 'none' ? [] : [{ width: 800, height: 600 }];
      node.getBoundingClientRect = () => ({x:0,y:0,width:800,height:600});
    }
    const originalQuery = page.applicationRoot.querySelectorAll.bind(page.applicationRoot);
    page.applicationRoot.querySelectorAll = selector => selector === '[data-app-shell-main-surface]'
      ? [main] : originalQuery(selector);
    main.querySelectorAll = selector => selector === '[data-app-shell-page-surface]' ? [pageSurface] : [];
    const adapter = createCodexPageAdapter(globalThis);
    const installAnimation = () => {};
    bootstrapStartup({ installStartup: () => {}, installAnimation, createLocalization: () => {}, createImageSettings: () => {},
      createWallpaperApplicator, installRenderer, version: '0.9.0', css: CSS, assets: {}, host: globalThis, pageAdapter: adapter });
    try { return await operation({ ...page, adapter, observers, main, frame, apply: installAnimation.applyWallpaper,
      payload: { ...page.payload, pageAdapter: adapter, workspaceObservation: adapter.observeWorkspace() } }); }
    finally {
      globalThis.__azhouWallpaper?.dispose();
      for (const [key, descriptor] of saved) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    }
  });
}

test('real Codex adapter through bootstrap and applicator reaches renderer with observed scope', async () => onObservedPage(async page => {
  const result = await page.apply({ image: GOOD_IMAGE, strength: 37, surface: '#10121c' });
  assert.equal(result.applied, true);
  assert.equal(result.coverage.shell, 'observed');
  assert.equal(result.coverage.messaging, 'unknown');
  assert.equal(result.fullCoverage, false);
  assert.ok(result.matchedSurfaces >= 3);
  assert.ok(page.main.getAttribute('data-azhou-wallpaper-plane'));
  assert.equal(page.observers.filter(observer => !observer.disconnected).length, 2);
}));

test('passive wallpaper observation leaves queued workspace changes undelivered', async () => onObservedPage(async page => {
  await installRenderer(page.payload);
  const controller = globalThis.__azhouWallpaper;
  const sidebar = page.frame;
  const query = page.applicationRoot.querySelectorAll.bind(page.applicationRoot);
  page.applicationRoot.querySelectorAll = selector => selector === '#app-shell-sidebar' ? [sidebar] : query(selector);
  const before = controller.observeSurfaces();
  assert.deepEqual(before, {
    bodyBackground: 'matched', sidebarBackground: 'clear', dotCentralBackground: 'unverified',
    dotCentralMarker: 'unverified',
  });
  sidebar.styles.backgroundColor = 'rgb(24, 24, 24)';
  page.main.styles.display = 'none';
  const pending = [{ type: 'attributes', target: page.main, attributeName: 'style' }];
  page.observers[0].records = pending;
  const after = controller.observeSurfaces();
  assert.deepEqual(after, { ...before, sidebarBackground: 'painted' });
  assert.equal(page.observers[0].records, pending);
  assert.equal(globalThis.__azhouWallpaper, controller);
  assert.ok(page.main.getAttribute('data-azhou-wallpaper-plane'));
}));

test('observed workspace lost during decode cannot write styles or markers', async () => onObservedPage(async page => {
  const decode = page.image.decode;
  page.image.decode = async () => { await decode(); page.main.styles.display = 'none'; };
  await assert.rejects(installRenderer(page.payload), /page-changed-during-decode/);
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), null);
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
  assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
}));

test('observed invalidation releases markers observers URL and activation before reporting disposed', async () => onObservedPage(async page => {
  await installRenderer(page.payload);
  const controller = globalThis.__azhouWallpaper;
  page.main.styles.display = 'none';
  page.observers[0].trigger([{ type: 'attributes', target: page.main, attributeName: 'style' }]);
  await Promise.resolve();
  assert.equal(controller.status().applied, false);
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), null);
  assert.ok(page.observers.every(observer => observer.disconnected));
  assert.equal(page.styleElements.filter(style => style.isConnected).length, 0);
  assert.equal(page.image.src, '');
  assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
}));

test('observed status drains queued invalidation and retires owned paint before observer delivery', async () => onObservedPage(async page => {
  await installRenderer(page.payload);
  const controller = globalThis.__azhouWallpaper;
  const mutation = page.observers[0];
  const sheet = page.styleElements.find(style => style.id === STYLE_ID && style.isConnected);
  const scene = page.main.getAttribute('data-azhou-wallpaper-plane');
  assert.ok(sheet && scene);
  assert.equal(controller.status().applied, true);

  // A structural host class change queues an invalidation without hiding or
  // removing the fixture. Deliberately leave the observer callback undelivered.
  page.main.setAttribute('class', 'fixture-host-inactive');
  const queued = [{ type: 'attributes', target: page.main, attributeName: 'class', oldValue: null }];
  mutation.records = queued;
  assert.equal(mutation.records, queued);
  assert.equal(globalThis.__azhouWallpaper, controller);
  assert.equal(sheet.isConnected, true);
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'active');
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), scene);
  assert.deepEqual(page.revoked, []);

  const status = controller.status();
  assert.equal(status.applied, false);
  assert.equal(status.reason, 'disposed');
  assert.deepEqual(mutation.records, []);
  assert.equal(globalThis.__azhouWallpaper, undefined);
  assert.equal(sheet.isConnected, false);
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), null);
  assert.equal(page.main.getAttribute('class'), 'fixture-host-inactive');
  assert.deepEqual(page.revoked, [scene]);
}));

test('own transparent paint changes do not retire the observed controller', async () => onObservedPage(async page => {
  await installRenderer(page.payload);
  const controller = globalThis.__azhouWallpaper;
  page.main.styles.backgroundColor = 'transparent';
  page.observers[0].trigger();
  await Promise.resolve();
  assert.equal(globalThis.__azhouWallpaper, controller);
  assert.equal(controller.status().applied, true);
  assert.equal(page.revoked.length, 0);
}));

test('late observer from A cannot undo B with identical tint and surface values', async () => onObservedPage(async page => {
  let serial = 0;
  globalThis.URL.createObjectURL = () => `blob:observed-${++serial}`;
  const originalStyle = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (node, pseudo) => {
    const computed = originalStyle(node, pseudo);
    return node === page.document.body ? { ...computed, backgroundImage: `linear-gradient(red,blue), ${page.root.style.getPropertyValue(PROPERTY_IMAGE)}` } : computed;
  };
  globalThis.Image = function() { return { complete: false, naturalWidth: 100, naturalHeight: 100, src: '', async decode() { this.complete = true; } }; };
  await installRenderer(page.payload);
  const first = globalThis.__azhouWallpaper;
  const late = page.observers[0];
  await installRenderer(page.payload);
  const second = globalThis.__azhouWallpaper;
  const secondMarker = page.main.getAttribute('data-azhou-wallpaper-plane');
  late.trigger();
  await Promise.resolve();
  first.dispose();
  assert.equal(globalThis.__azhouWallpaper, second);
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), secondMarker);
  assert.equal(second.status().applied, true);
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'active');
  assert.deepEqual(page.revoked, ['blob:observed-1']);
}));

test('remove and reattach before a mutation batch is delivered still cancels decode', async () => onObservedPage(async page => {
  const decode = page.image.decode;
  page.image.decode = async () => {
    await decode();
    page.observers[0].trigger([{ type: 'childList', target: page.frame, removedNodes: [page.main] }]);
  };
  await assert.rejects(installRenderer(page.payload), /page-changed-during-decode/);
  assert.equal(page.main.isConnected, true, 'the final DOM has already returned to A');
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), null);
  assert.ok(page.observers.every(observer => observer.disconnected));
}));

test('message child changes and owned root style writes do not invalidate workspace', async () => onObservedPage(async page => {
  await installRenderer(page.payload);
  const controller = globalThis.__azhouWallpaper;
  page.observers[0].trigger([{ type: 'childList', target: page.main, removedNodes: [new Node('message')] },
    { type: 'attributes', target: page.root, attributeName: 'style' },
    { type: 'attributes', target: page.main, attributeName: 'data-azhou-wallpaper-plane' }]);
  assert.equal(controller.status().applied, true);
  assert.equal(globalThis.__azhouWallpaper, controller);
}));

test('a throwing observer disposer does not prevent remaining resources from release', async () => onObservedPage(async page => {
  await installRenderer(page.payload);
  page.observers[0].disconnect = () => { throw new Error('injected observer disposal'); };
  globalThis.__azhouWallpaper.dispose();
  assert.equal(page.observers[1].disconnected, true);
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), null);
  assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
}));

test('observer setup failure releases its sibling observer and decoded lease', async () => onObservedPage(async page => {
  globalThis.ResizeObserver = class { constructor() { throw new Error('injected resize setup'); } };
  await assert.rejects(installRenderer(page.payload), /injected resize setup/);
  assert.equal(page.observers[0].disconnected, true);
  assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
  assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
}));

test('foreign plane marker is not overwritten', async () => onObservedPage(async page => {
  page.main.setAttribute('data-azhou-wallpaper-plane', 'another-owner');
  await assert.rejects(installRenderer(page.payload), /namespace-conflict/);
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), 'another-owner');
  assert.deepEqual(page.revoked, ['blob:wallpaper-1']);
  assert.ok(page.observers.every(observer => observer.disconnected));
}));

for (const defect of ['empty planes', 'unsupported observation', 'missing watcher', 'throwing current', 'unknown contract', 'inherited contract', 'contract accessor']) {
  test(`production Codex ${defect} cannot enter legacy rendering`, async () => onObservedPage(async page => {
    const payload = { ...page.payload, pageAdapter: { ...page.adapter } };
    if (defect === 'empty planes') payload.workspaceObservation = { ...payload.workspaceObservation, knownPaintPlanes: [] };
    if (defect === 'unsupported observation') payload.workspaceObservation = { kind: 'unsupported' };
    if (defect === 'missing watcher') delete payload.pageAdapter.watchWorkspace;
    if (defect === 'throwing current') payload.pageAdapter.isWorkspaceCurrent = () => { throw new Error('unknown host'); };
    if (defect === 'unknown contract') payload.pageAdapter.workspaceContract = 'future-unknown';
    if (defect === 'inherited contract') { delete payload.pageAdapter.workspaceContract; Object.setPrototypeOf(payload.pageAdapter, {workspaceContract:'codex-active-workspace/v1'}); }
    if (defect === 'contract accessor') Object.defineProperty(payload.pageAdapter,'workspaceContract',{get(){throw Error('must not invoke');}});
    await assert.rejects(installRenderer(payload));
    assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'), null);
    assert.equal(page.root.getAttribute(ATTRIBUTE), 'baseline');
    assert.equal(page.observers.filter(observer => !observer.disconnected).length, 0);
  }));
}

for (const value of [0,30,100]) test('theme readability uses one scene with a bounded color-only mask at '+value, async () => {
  await onObservedPage(async page => {
    await installRenderer({...page.payload, themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value}}}});
    const wash = document.documentElement.style.getPropertyValue(PROPERTY_WASH);
    assert.ok(wash.startsWith('url("data:image/svg+xml,'));
    const svg=decodeURIComponent(JSON.parse(wash.slice(4,-1)).split(',')[1]);
    assert.ok(svg.includes('viewBox="0 0 1512 889"'));
    assert.ok(svg.includes('x="0" y="0" width="800" height="600"'));
    assert.ok(svg.includes('fill-opacity="'+((100-value)/100)+'"'));
    assert.ok(!svg.includes('<image'), 'mask never embeds artwork');
    assert.doesNotMatch(svg, /<(?:script|foreignObject)|(?:href|src)\s*=|url\((?!#)/i, 'mask has no active or external resources');
    assert.deepEqual([...new Set([...svg.matchAll(/<([A-Za-z]+)/g)].map(match=>match[1]))].sort(),['defs','linearGradient','mask','rect','stop','svg']);
    assert.ok(svg.includes('linearGradient'), 'outside treatment retains legacy ramp');
    assert.equal(globalThis.__azhouWallpaper.status().themeApplied,true);
  });
});
test('theme refuses missing named surface capability without claiming applied', async () => {
  await onPage({}, async page => {
    await assert.rejects(installRenderer({...page.payload,themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'follow'}}}}), /theme-surface-unsupported/);
  });
});

 test('theme to legacy handover removes only prior theme marker and old cleanup cannot retire successor', async () => onObservedPage(async page => {
  globalThis.Image = function () { return {src:'', complete:false, naturalWidth:page.image.naturalWidth, naturalHeight:page.image.naturalHeight, async decode(){this.complete=true;}}; };
  const themeState={schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value:30}}};
  await installRenderer({...page.payload,themeState});
  const prior=globalThis.__azhouWallpaper;
  assert.equal(page.main.getAttribute('data-azhou-theme-readability'),null);
  assert.ok(page.root.style.getPropertyValue(PROPERTY_WASH).includes('data:image/svg+xml'));
  await installRenderer({...page.payload,workspaceObservation:page.adapter.observeWorkspace()});
  const next=globalThis.__azhouWallpaper;
  assert.notEqual(next,prior);
  assert.equal(page.main.getAttribute('data-azhou-theme-readability'),null);
  prior.dispose();
  assert.equal(next.status().applied,true);
  next.dispose();
  assert.equal(page.main.getAttribute('data-azhou-wallpaper-plane'),null);
  assert.equal(page.main.getAttribute('data-azhou-theme-readability'),null);
}));

test('legacy workspace adapters without complete theme geometry stay usable but cannot admit themes',async()=>onObservedPage(async page=>{
  const old={...page.adapter};delete old.readThemeGeometry;
  await installRenderer({...page.payload,pageAdapter:old});
  const incumbent=globalThis.__azhouWallpaper;
  await assert.rejects(installRenderer({...page.payload,pageAdapter:old,themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'follow'}}}}),/theme-surface-unsupported/);
  assert.equal(globalThis.__azhouWallpaper,incumbent);assert.equal(incumbent.status().applied,true);
}));

function controlledThemeImages(page) {
  const masks=[];
  globalThis.Image=function(){
    this.src='';this.complete=false;this.naturalWidth=page.image.naturalWidth;this.naturalHeight=page.image.naturalHeight;
    this.decode=()=>{
      if(!this.src.startsWith('data:image/svg+xml,')){this.complete=true;return Promise.resolve();}
      return new Promise((resolve,reject)=>masks.push({image:this,resolve:()=>{this.complete=true;resolve();},reject}));
    };
  };
  return masks;
}
const activeTheme={schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value:30}}};
async function settleMicrotasks(){for(let i=0;i<12;i++)await Promise.resolve();}

test('theme geometry decodes under the original owner and stale work cannot replace a newer mask',async()=>onObservedPage(async page=>{
  const masks=controlledThemeImages(page);
  const pending=installRenderer({...page.payload,themeState:activeTheme});await settleMicrotasks();
  assert.equal(masks.length,1);masks[0].resolve();await pending;
  const owner=globalThis.__azhouWallpaper;
  let y=20;page.main.getBoundingClientRect=()=>({x:0,y,width:800,height:600});
  page.observers[1].trigger([]);await settleMicrotasks();
  assert.equal(owner.status().themePending,true);assert.equal(owner.status().fallbackApplied,true);
  assert.ok(page.root.style.getPropertyValue(PROPERTY_WASH).includes('90deg'));
  assert.equal(masks.length,2);
  y=30;page.observers[1].trigger([]);await settleMicrotasks();
  assert.equal(masks[1].image.src,'');assert.equal(masks.length,3);
  masks[1].resolve();await settleMicrotasks();assert.equal(owner.status().themePending,true);
  masks[2].resolve();await settleMicrotasks();
  assert.equal(globalThis.__azhouWallpaper,owner);assert.equal(owner.status().themeApplied,true);
  const svg=decodeURIComponent(JSON.parse(page.root.style.getPropertyValue(PROPERTY_WASH).slice(4,-1)).split(',')[1]);
  assert.ok(svg.includes('y="30"'));
  y=40;page.observers[1].trigger([]);await settleMicrotasks();
  owner.dispose();masks[3].resolve();await settleMicrotasks();
  assert.equal(globalThis.__azhouWallpaper,undefined);assert.equal(page.root.getAttribute(ATTRIBUTE),'baseline');
  assert.ok(masks.every(mask=>mask.image.src===''));
  assert.equal(page.revoked.length,1,'mask images do not allocate another scene Blob URL');
}));

test('a runtime mask decode failure leaves the legacy treatment usable and reports theme failure',async()=>onObservedPage(async page=>{
  const masks=controlledThemeImages(page);const pending=installRenderer({...page.payload,themeState:activeTheme});
  await settleMicrotasks();masks[0].resolve();await pending;
  const owner=globalThis.__azhouWallpaper;
  page.main.getBoundingClientRect=()=>({x:0,y:10,width:800,height:600});page.observers[1].trigger([]);await settleMicrotasks();
  masks[1].reject(Error('synthetic CSP'));await settleMicrotasks();
  const status=owner.status();assert.equal(status.themeApplied,false);assert.equal(status.themePending,false);
  assert.equal(status.themeFailure,'theme-mask-decode-failed');assert.equal(status.fallbackApplied,true);
  assert.equal(globalThis.__azhouWallpaper,owner);assert.ok(page.root.style.getPropertyValue(PROPERTY_WASH).includes('90deg'));
}));

test('appearance updates rebuild the color-only mask and do not overwrite a foreign wash',async()=>onObservedPage(async page=>{
  const masks=controlledThemeImages(page);const pending=installRenderer({...page.payload,themeState:activeTheme});
  await settleMicrotasks();masks[0].resolve();await pending;
  const owner=globalThis.__azhouWallpaper;assert.equal(owner.updateSurface('#eeeeee'),true);
  await settleMicrotasks();assert.equal(masks.length,2);masks[1].resolve();await settleMicrotasks();
  assert.ok(decodeURIComponent(page.root.style.getPropertyValue(PROPERTY_WASH)).includes('#eeeeee'));
  page.root.style.setProperty(PROPERTY_WASH,'host-wash','important');
  page.main.getBoundingClientRect=()=>({x:0,y:10,width:800,height:600});page.observers[1].trigger([]);await settleMicrotasks();
  assert.equal(owner.status().themeFailure,'theme-owner-lost');assert.equal(masks.length,2);
  owner.dispose();assert.equal(page.root.style.getPropertyValue(PROPERTY_WASH),'host-wash');
  assert.equal(page.root.style.getPropertyPriority(PROPERTY_WASH),'important');
}));

test('initial mask decode cannot mutate the page after its geometry becomes stale',async()=>onObservedPage(async page=>{
  const masks=controlledThemeImages(page);const pending=installRenderer({...page.payload,themeState:activeTheme});
  await settleMicrotasks();page.main.getBoundingClientRect=()=>({x:0,y:25,width:800,height:600});
  masks[0].resolve();await assert.rejects(pending,/theme-mask-stale/);
  assert.equal(page.root.getAttribute(ATTRIBUTE),'baseline');assert.equal(globalThis.__azhouWallpaper,undefined);
  assert.equal(page.revoked.length,1);
}));

test('theme mask uses the existing decode anti-hang ceiling and releases a timed-out attempt',async()=>onObservedPage(async page=>{
  const originalSet=globalThis.setTimeout,originalClear=globalThis.clearTimeout, timers=new Map();let next=0;
  globalThis.setTimeout=(callback,delay)=>{const id=++next;timers.set(id,{callback,delay});return id;};
  globalThis.clearTimeout=id=>timers.delete(id);
  try{
    const masks=controlledThemeImages(page),pending=installRenderer({...page.payload,themeState:activeTheme});
    await settleMicrotasks();assert.equal(masks.length,1);
    const deadline=[...timers.values()].find(timer=>timer.delay===4000);assert.ok(deadline);
    deadline.callback();await assert.rejects(pending,/theme-mask-decode-timeout/);
    assert.equal(masks[0].image.src,'');assert.equal(timers.size,0);assert.equal(page.revoked.length,1);
    assert.equal(page.root.getAttribute(ATTRIBUTE),'baseline');
  }finally{globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear;}
}));

test('a half-upgraded workspace watcher cannot silently admit a theme without its geometry callback',async()=>onObservedPage(async page=>{
  const old={...page.adapter,watchWorkspace:()=>({current:()=>true,dispose(){}})};
  await installRenderer({...page.payload,pageAdapter:old});const incumbent=globalThis.__azhouWallpaper;
  await assert.rejects(installRenderer({...page.payload,pageAdapter:old,themeState:activeTheme}),/theme-surface-unsupported/);
  assert.equal(globalThis.__azhouWallpaper,incumbent);assert.equal(incumbent.status().applied,true);
}));

test('aborting initial theme decode immediately releases images timers and listener without harming a successor',async()=>onObservedPage(async page=>{
  const originalSet=globalThis.setTimeout,originalClear=globalThis.clearTimeout,timers=new Map();let next=0;
  globalThis.setTimeout=(callback,delay)=>{const id=++next;timers.set(id,{callback,delay});return id;};
  globalThis.clearTimeout=id=>timers.delete(id);
  const abort=new AbortController(),listeners=new Set();
  const signal={get aborted(){return abort.signal.aborted;},addEventListener(type,fn,options){listeners.add(fn);abort.signal.addEventListener(type,fn,options);},removeEventListener(type,fn){listeners.delete(fn);abort.signal.removeEventListener(type,fn);}};
  try{
    const masks=controlledThemeImages(page),pending=installRenderer({...page.payload,themeState:activeTheme,signal});
    await settleMicrotasks();assert.equal(masks.length,1);assert.equal(listeners.size,1);
    const rejected=assert.rejects(pending,/theme-mask-cancelled/);abort.abort();
    assert.equal(masks[0].image.src,'');assert.equal(timers.size,0,'release does not wait for the deadline');
    await rejected;assert.equal(listeners.size,0);assert.equal(page.revoked.length,1);
    await installRenderer(page.payload);const successor=globalThis.__azhouWallpaper;
    masks[0].resolve();await settleMicrotasks();abort.abort();
    assert.equal(globalThis.__azhouWallpaper,successor);assert.equal(successor.status().applied,true);
  }finally{globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear;}
}));

test('decode admission reports the fixed actual workspace lease before scene decoding', async () => {
  await onObservedPage(async page => {
    let notice, deliveries=0, callerChecks=0;
    const strictCurrent=()=>{callerChecks++;return true;};
    const decode=page.image.decode.bind(page.image);
    page.image.decode=async function(){
      assert.equal(deliveries,1,'admission occurs before the actual scene decode');
      assert.equal(notice.contract,'codex-workspace-decode/v1');
      assert.equal(notice.documentToken,page.payload.workspaceObservation.documentToken);
      assert.equal(notice.workspaceEpoch,page.payload.workspaceObservation.workspaceEpoch);
      const before=callerChecks;assert.equal(notice.current(),true);
      assert.equal(callerChecks,before,'workspace lease validity must not call the caller isCurrent');
      await decode();
    };
    const result=await installRenderer({...page.payload,isCurrent:strictCurrent,onDecodeAdmitted:value=>{notice=value;deliveries++;}});
    assert.equal(result.applied,true);assert.equal(notice.current(),true);
    globalThis.__azhouWallpaper.dispose();assert.equal(notice.current(),false);
  });
});

function transactionScene(page) {
  let urls = 0;
  globalThis.URL.createObjectURL = () => `blob:transaction-${++urls}`;
  const computed = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (node, pseudo) => node === page.document.body
    ? { ...computed(node, pseudo), backgroundImage: `linear-gradient(red,blue), ${page.root.style.getPropertyValue(PROPERTY_IMAGE)}` }
    : computed(node, pseudo);
}

test('reversible activation retains incumbent resources until finalize and rollback restores them', async () => onObservedPage(async page => {
  transactionScene(page);
  await installRenderer(page.payload);
  const previous = globalThis.__azhouWallpaper;
  const previousSheet = page.document.getElementById(STYLE_ID);
  const previousImage = page.root.style.getPropertyValue(PROPERTY_IMAGE);
  const result = await installRenderer({ ...page.payload, transactional: true });
  const candidate = globalThis.__azhouWallpaper;
  assert.equal(result.applied, true);
  assert.equal(typeof result.transaction?.rollback, 'function');
  assert.equal(previousSheet.isConnected, true);
  assert.equal(previousSheet.disabled, true);
  assert.deepEqual(page.revoked, []);
  assert.equal(result.transaction.current(), true);
  assert.equal(result.transaction.rollback(), true);
  assert.equal(globalThis.__azhouWallpaper, previous);
  assert.equal(previous.status().applied, true);
  assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE), previousImage);
  assert.equal(previousSheet.disabled, false);
  assert.deepEqual(page.revoked, ['blob:transaction-2']);
  assert.equal(result.transaction.rollback(), true, 'rollback is idempotent');
  assert.equal(result.transaction.finalize(), false);
  assert.equal(candidate.status().applied, false);
}));

test('reversible finalize releases only incumbent and a late rollback cannot retire the winner', async () => onObservedPage(async page => {
  transactionScene(page);
  await installRenderer(page.payload);
  const previousSheet = page.document.getElementById(STYLE_ID);
  const result = await installRenderer({ ...page.payload, transactional: true });
  const winner = globalThis.__azhouWallpaper;
  assert.equal(typeof result.transaction?.finalize, 'function');
  assert.equal(result.transaction.finalize(), true);
  assert.equal(result.transaction.finalize(), true);
  assert.equal(previousSheet.isConnected, false);
  assert.deepEqual(page.revoked, ['blob:transaction-1']);
  assert.equal(result.transaction.rollback(), false);
  assert.equal(globalThis.__azhouWallpaper, winner);
  assert.equal(winner.status().applied, true);
}));

test('aborting reversible activation restores incumbent before returning and releases the candidate', async () => onObservedPage(async page => {
  transactionScene(page);
  await installRenderer(page.payload);
  const previous = globalThis.__azhouWallpaper;
  const abort = new AbortController();
  const result = await installRenderer({ ...page.payload, transactional: true, signal: abort.signal });
  assert.equal(typeof result.transaction?.rollback, 'function');
  abort.abort();
  assert.equal(globalThis.__azhouWallpaper, previous);
  assert.equal(previous.status().applied, true);
  assert.deepEqual(page.revoked, ['blob:transaction-2']);
  assert.equal(result.transaction.current(), false);
}));

test('a retired literal main paint request cannot change an active owner', async () => onObservedPage(async page => {
  transactionScene(page);
  await installRenderer({...page.payload,strength:42});
  const previous = globalThis.__azhouWallpaper;
  const sheet = page.document.getElementById(STYLE_ID);
  const wash = page.root.style.getPropertyValue(PROPERTY_WASH);
  const mainPaint = {profile:'codex-main-literal-paint/v1',rgba:[10,20,30,.4],backgroundImage:'none',sourceDeclarationCount:1};
  const inherited = Object.assign(Object.create({mainPaint}), page.payload);
  const accessor = Object.defineProperty({...page.payload}, 'mainPaint', {
    get() { assert.fail('retired field must never be read'); },
  });
  for (const offered of [{...page.payload, mainPaint}, inherited, accessor]) {
    await assert.rejects(installRenderer(offered), error => {
      assert.equal(error.code, 'main-paint-unsupported');
      assert.equal(error.cause, undefined);
      return true;
    });
    assert.equal(globalThis.__azhouWallpaper, previous);
    assert.equal(page.document.getElementById(STYLE_ID), sheet);
    assert.equal(page.root.style.getPropertyValue(PROPERTY_WASH), wash);
    assert.equal(page.main.getAttribute('data-azhou-dream-main'), null);
    assert.deepEqual(page.revoked, []);
  }
}));

test('ordinary DSH renderer transactions still use the v2 lease for apply, rollback and disable', async () =>
  onPage({ shell: false, url: 'file:///Applications/SyntheticHost.app/Contents/Resources/app.asar/out/renderer/index.html' }, async page => {
    // Separate Image instances are required to keep the suspended owner's decode alive.
    globalThis.Image = function() {
      return {src:'',complete:false,naturalWidth:page.image.naturalWidth,naturalHeight:page.image.naturalHeight,
        async decode() { this.complete = true; }};
    };
    transactionScene(page);
    const main = page.applicationRoot.selectors['[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]'][1];
    main.tagName = 'MAIN';
    page.applicationRoot.contains = node => node === main;
    const leases = [];
    const adapter = {
      controllerWallpaper: {owner:'azhou.dsh-startup-animation'},
      wallpaper: syntheticWallpaperPorts({surfaces:() => [main]}),
      themeSelectionContract:'dsh-owned-main-paint/v2',
      captureThemeSurface() {
        let current = true;
        let notify;
        const lease = {
          current:() => current,
          watch(callback) { notify = callback; return true; },
          dispose() { current = false; },
          invalidate() { current = false; notify?.(); },
        };
        leases.push(lease);
        return lease;
      },
    };
    const p = {...page.payload,pageAdapter:adapter,strength:42};
    const owner = () => globalThis.__azhouWallpaper;
    const sheet = () => page.document.getElementById(STYLE_ID);
    const wash = () => page.root.style.getPropertyValue(PROPERTY_WASH);
    await installRenderer(p);
    const prior = owner(), priorSheet = sheet(), priorWash = wash();
    assert.equal(leases.length,0,'ordinary non-transactional renderer is unchanged');

    const prepare = strength => installRenderer({...p,strength,transactional:true});
    const candidate = await prepare(67);
    assert.equal(candidate.transaction.current(),true);
    assert.notEqual(owner(),prior);
    assert.notEqual(sheet(),priorSheet);
    assert.notEqual(wash(),priorWash);
    assert.equal(candidate.transaction.rollback(),true);
    assert.equal(leases[0].current(),false);
    assert.equal(owner(),prior);
    assert.equal(sheet(),priorSheet);
    assert.equal(wash(),priorWash);

    const replacement = await prepare(67);
    const next = owner();
    assert.equal(replacement.transaction.finalize(),true);
    assert.equal(owner(),next);
    assert.equal(leases[1].current(),true);
    leases[1].invalidate();
    assert.equal(owner(),undefined);
    assert.equal(sheet(),null);

    const disabled = await prepare(0);
    assert.equal(disabled.transaction.current(),true);
    assert.equal(disabled.transaction.finalize(),true);
    assert.equal(disabled.transaction.finalize(),true);
    assert.equal(leases[2].current(),false);
    const stale = await prepare(0);
    leases[3].invalidate();
    assert.equal(stale.transaction.current(),false);
    assert.equal(stale.transaction.finalize(),false);
    assert.equal(owner(),undefined);
    assert.equal(sheet(),null);
  }));

test('rollback preserves an already rendered bundled mask rather than starting a lossy asynchronous refresh',async()=>onObservedPage(async page=>{
  transactionScene(page);
  await installRenderer({...page.payload,themeState:activeTheme});
  const previous=globalThis.__azhouWallpaper;const wash=page.root.style.getPropertyValue(PROPERTY_WASH);
  const candidate=await installRenderer({...page.payload,transactional:true});
  assert.equal(candidate.transaction.rollback(),true);
  assert.equal(globalThis.__azhouWallpaper,previous);
  assert.equal(previous.status().themeApplied,true);
  assert.equal(page.root.style.getPropertyValue(PROPERTY_WASH),wash);
}));
test('pending activation cannot be replaced and late rollback preserves a foreign winner',async()=>onObservedPage(async page=>{
  transactionScene(page);await installRenderer(page.payload);
  const candidate=await installRenderer({...page.payload,transactional:true});
  await assert.rejects(installRenderer({...page.payload,transactional:true}),{code:'activation-in-progress'});
  const foreign={owner:'foreign',dispose(){}};globalThis.__azhouWallpaper=foreign;
  page.root.style.setProperty(PROPERTY_IMAGE,'foreign scene');
  assert.equal(candidate.transaction.rollback(),false);
  assert.equal(globalThis.__azhouWallpaper,foreign);assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE),'foreign scene');
  assert.deepEqual([...page.revoked].sort(),['blob:transaction-1','blob:transaction-2']);
}));
test('workspace loss while candidate is active restores native baseline, not an invalid incumbent',async()=>onObservedPage(async page=>{
  transactionScene(page);await installRenderer(page.payload);
  const candidate=await installRenderer({...page.payload,transactional:true});
  page.main.styles.display='none';
  for(const observer of [...page.observers])if(!observer.disconnected)observer.trigger([{type:'attributes',target:page.main,attributeName:'style'}]);
  assert.equal(candidate.transaction.current(),false);
  candidate.transaction.rollback();
  assert.equal(globalThis.__azhouWallpaper,undefined);
  assert.equal(page.root.getAttribute(ATTRIBUTE),'baseline');
  assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE),'');
  assert.equal(page.observers.filter(o=>!o.disconnected).length,0);
  assert.deepEqual([...page.revoked].sort(),['blob:transaction-1','blob:transaction-2']);
}));

for(const outcome of ['finalize','rollback','abort'])test('transactional strength zero retains incumbent until commit and then '+outcome,async()=>onObservedPage(async page=>{
  transactionScene(page);await installRenderer(page.payload);
  const previous=globalThis.__azhouWallpaper,previousSheet=page.document.getElementById(STYLE_ID);
  const image=page.root.style.getPropertyValue(PROPERTY_IMAGE);const abort=new AbortController();
  const disabled=await installRenderer({...page.payload,strength:0,transactional:true,signal:abort.signal});
  assert.equal(disabled.disabled,true,'Zero strength is an explicit disabled candidate, not another wallpaper');
  assert.equal(disabled.applied,true);assert.equal(disabled.transaction.current(),true);
  assert.equal(globalThis.__azhouWallpaper,previous);assert.equal(previous.status().applied,true);
  assert.equal(previousSheet.disabled,false);assert.deepEqual(page.revoked,[]);
  assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE),image);
  if(outcome==='finalize'){
    assert.equal(disabled.transaction.finalize(),true);assert.equal(disabled.transaction.finalize(),true);
    assert.equal(globalThis.__azhouWallpaper,undefined);assert.equal(previousSheet.isConnected,false);
    assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE),'');assert.equal(page.root.getAttribute(ATTRIBUTE),'baseline');
    assert.deepEqual(page.revoked,['blob:transaction-1']);assert.equal(disabled.transaction.rollback(),false);
  }else{
    if(outcome==='abort')abort.abort();else assert.equal(disabled.transaction.rollback(),true);
    assert.equal(disabled.transaction.rollback(),true);assert.equal(disabled.transaction.finalize(),false);
    assert.equal(globalThis.__azhouWallpaper,previous);assert.equal(previous.status().applied,true);assert.deepEqual(page.revoked,[]);
  }
}));

test('disabled receipt with no incumbent allocates no scene and cannot finalize over a newer owner',async()=>onObservedPage(async page=>{
  transactionScene(page);
  const disabled=await installRenderer({...page.payload,strength:0,transactional:true});
  assert.equal(disabled.disabled,true);assert.equal(globalThis.__azhouWallpaper,undefined);assert.deepEqual(page.revoked,[]);
  await installRenderer(page.payload);const newer=globalThis.__azhouWallpaper;
  assert.equal(disabled.transaction.finalize(),false);assert.equal(globalThis.__azhouWallpaper,newer);assert.equal(newer.status().applied,true);
}));
test('late disabled rollback cannot touch a foreign winner or revive a directly disposed owner',async()=>{
  for(const mode of ['foreign','dispose'])await onObservedPage(async page=>{
    transactionScene(page);await installRenderer(page.payload);const old=globalThis.__azhouWallpaper;
    const disabled=await installRenderer({...page.payload,strength:0,transactional:true});
    if(mode==='foreign'){
      const foreign={owner:'foreign',dispose(){}};globalThis.__azhouWallpaper=foreign;page.root.style.setProperty(PROPERTY_IMAGE,'foreign scene');
      assert.equal(disabled.transaction.rollback(),false);assert.equal(globalThis.__azhouWallpaper,foreign);assert.equal(page.root.style.getPropertyValue(PROPERTY_IMAGE),'foreign scene');
    }else{
      old.dispose();assert.equal(disabled.transaction.rollback(),false);assert.equal(disabled.transaction.finalize(),false);
      assert.equal(globalThis.__azhouWallpaper,undefined);assert.equal(page.root.getAttribute(ATTRIBUTE),'baseline');
    }
    assert.deepEqual(page.revoked,['blob:transaction-1']);
  });
});

for(const defect of ['aborted','stale','unknown-theme'])test('disabled preparation rejects '+defect+' before touching an owner',async()=>onObservedPage(async page=>{
  const abort=new AbortController();if(defect==='aborted')abort.abort();
  const value={...page.payload,strength:0,transactional:true,signal:abort.signal,
    ...(defect==='stale'?{isCurrent:()=>false}:{}),...(defect==='unknown-theme'?{themeState:{schemaVersion:99}}:{})};
  await assert.rejects(installRenderer(value),{code:defect==='unknown-theme'?'theme-surface-unsupported':'operation-cancelled'});
  assert.equal(globalThis.__azhouWallpaper,undefined);assert.deepEqual(page.revoked,[]);
}));
