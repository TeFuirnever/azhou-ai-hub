import test from 'node:test';
import assert from 'node:assert/strict';
import { createDSHPageAdapter } from '../extension/hosts/dsh.mjs';
function host(overrides = {}) {
  let nonce = 0;
  const h = { location: { href: 'http://127.0.0.1:55747/' },
    crypto: { randomUUID: () => 'dsh-nonce-' + (++nonce) },
    __ModuleLoader__: { load() {} }, __DSH_BOOT__: { web: true },
    document: { documentElement: { lang: 'en' }, body: { hasAttribute: () => false } },
    indexedDB: { own: true }, CSS: { supports: () => true }, getComputedStyle: () => ({ getPropertyValue: () => '' }),
    matchMedia: () => ({ matches: false }) };
  h.top = h;return Object.assign(h, overrides);
}
test('structural identify accepts the boot graph and caches one token per href', () => {
  const h = host();const a = createDSHPageAdapter(h);
  assert.equal(a.identify(h).kind, 'matched');assert.equal(a.identify(h).documentToken, 'dsh-nonce-1');
  assert.equal(a.identify(h).documentToken, 'dsh-nonce-1');
  h.location.href = 'dsh-app://host/window/main';
  assert.equal(a.identify(h).documentToken, 'dsh-nonce-2');
  assert.equal(a.identify().kind, 'matched');
  assert.equal(a.identify(host({ location: { href: 'https://attacker.example/' } })).kind, 'matched');
});
test('identify rejects non-top windows and missing boot-graph parts, never URLs', () => {
  const a = createDSHPageAdapter(host());
  const child = host();child.top = {};assert.equal(a.identify(child).kind, 'unmatched');
  const noLoader = host();delete noLoader.__ModuleLoader__;assert.equal(a.identify(noLoader).kind, 'unmatched');
  const badLoader = host();badLoader.__ModuleLoader__ = { load: 'not-a-function' };assert.equal(a.identify(badLoader).kind, 'unmatched');
  const noBoot = host();delete noBoot.__DSH_BOOT__;assert.equal(a.identify(noBoot).kind, 'unmatched');
  const inherited = Object.create(host());inherited.top = inherited;assert.equal(a.identify(inherited).kind, 'unmatched');
  const accessor = host();delete accessor.__DSH_BOOT__;
  Object.defineProperty(accessor, '__DSH_BOOT__', { configurable: true, get() { return true; } });
  assert.equal(a.identify(accessor).kind, 'unmatched');
  const noBody = host();noBody.document = { documentElement: {}, body: null };assert.equal(a.identify(noBody).kind, 'unmatched');
  const hostile = { get top() { throw new Error('cross-origin'); } };
  assert.deepEqual(a.identify(hostile), { kind: 'unmatched', reason: 'page-unsupported' });
});
test('namespace is explicit, immutable, DSH-only, with no DB open on construction', () => {
  const h = host();h.indexedDB = { open() { throw Error('must not open'); } };
  const a = createDSHPageAdapter(h);const e = a.settingsEnvironment();
  assert.equal(e.indexedDB, h.indexedDB);
  assert.deepEqual(e.settingsNamespace, { databaseName: 'azhou-dsh-startup', databaseVersion: 1,
    storeName: 'settings', settingsKey: 'images' });
  assert(Object.isFrozen(e));assert(Object.isFrozen(e.settingsNamespace));
  const other = { indexedDB: { alien: true } };assert.equal(a.settingsEnvironment(other).indexedDB, other.indexedDB);
  assert(!('controllerMetadata' in a));assert.equal(a.controllerOwner, 'azhou-dsh-startup');
});
test('cleanup forwards validated resources and refuses the rest', () => {
  const resource = { key: 'dsh', dispose() {} };
  assert.equal(createDSHPageAdapter(host()).registerCleanup(resource), false);
  const seen = [];const a = createDSHPageAdapter(host(), {}, { registerCleanup: r => seen.push(r) });
  assert.equal(a.registerCleanup({ key: 'bad' }), false);assert.equal(a.registerCleanup(resource), true);
  assert.deepEqual(seen, [resource]);
});
test('appearance reads DSH tokens, dark body attribute, zh locale, reduced motion', () => {
  const dark = { '--dsw-alias-bg-base': '#0d1117', '--dsw-alias-label-primary': '#e6edf3',
    '--dsw-alias-label-secondary': '#8b949e', '--dsw-alias-border-l3': '#30363d' };
  const h = host();h.document.documentElement.lang = 'zh-CN';
  h.document.body = { hasAttribute: name => name === 'data-ds-dark-theme' };
  h.matchMedia = query => ({ matches: query.includes('reduced-motion') });
  h.getComputedStyle = () => ({ getPropertyValue: token => dark[token] || '' });
  const appearance = createDSHPageAdapter(h).observeAppearance();
  assert.equal(appearance.theme, 'dark');assert.equal(appearance.locale, 'zh-CN');
  assert.deepEqual(appearance.colors, { surface: '#0d1117', text: '#e6edf3', muted: '#8b949e', border: '#30363d' });
  assert.equal(appearance.reducedMotion, true);
  assert(Object.isFrozen(appearance));assert(Object.isFrozen(appearance.colors));
  // DSH writes --dsw-* tokens inline on document.body; a palette published only
  // on the body must win over an empty documentElement read.
  const bodyScoped = host();
  bodyScoped.document.body = { hasAttribute: () => true };
  bodyScoped.getComputedStyle = element => ({ getPropertyValue: token =>
    element === bodyScoped.document.body ? (dark[token] || '') : '' });
  assert.equal(createDSHPageAdapter(bodyScoped).observeAppearance().colors.surface, '#0d1117');
});
test('appearance sanitizes tokens, falls back hardcoded, and defaults light', () => {
  const h = host();
  h.getComputedStyle = () => ({ getPropertyValue: token => token === '--dsw-alias-label-primary' ? 'javascript:x;{}' : '' });
  const appearance = createDSHPageAdapter(h).observeAppearance();
  assert.equal(appearance.theme, 'light');assert.equal(appearance.locale, 'en');
  assert.deepEqual(appearance.colors, { surface: '#f8f8f8', text: '#111111', border: '#777777' });
  assert.equal(appearance.reducedMotion, false);
  const noAttr = host();noAttr.document.body = {};
  noAttr.matchMedia = query => ({ matches: query.includes('prefers-color-scheme') });
  assert.equal(createDSHPageAdapter(noAttr).observeAppearance().theme, 'dark');
  const nav = host();nav.document.documentElement.lang = '';nav.navigator = { language: 'zh-TW' };
  assert.equal(createDSHPageAdapter(nav).observeAppearance().locale, 'zh-CN');
});
test('appearanceText keeps the shared message keys verbatim', () => {
  const a = createDSHPageAdapter(host());
  const en = a.appearanceText(null, { locale: 'en' });
  assert.equal(en.t('openAppearance'), 'Open appearance settings');
  assert.equal(en.t('appearance.wallpaper.failure.retry'), 'Retry wallpaper');
  assert.equal(en.t('appearance.wallpaper.failure.close'), 'Dismiss notice');
  const zh = a.appearanceText(null, { locale: 'zh-CN' });
  assert.equal(zh.t('overlayLabel'), '阿舟启动动画');assert.equal(zh.t('missing'), 'missing');
  const made = { t: key => 'factory:' + key };
  assert.equal(a.appearanceText(() => made, { locale: 'en' }), made);
});
class Element {
  constructor(tag = 'div') { this.tag = tag;this.children = [];this.attrs = {};this.events = new Map();
    this.style = { setProperty(key, value) { this[key] = value; } };this.isConnected = true;
    this.rect = { left: 0, right: 200, top: 0, bottom: 30, width: 200, height: 30 }; }
  setAttribute(key, value) { this.attrs[key] = value; }getAttribute(key) { return this.attrs[key]; }
  hasAttribute(key) { return key in this.attrs; }
  append(...nodes) { for (const node of nodes) this.appendChild(node); }
  appendChild(node) { if (node.parentElement) node.remove();this.children.push(node);node.parentElement = this;return node; }
  remove() { if (this.parentElement) { this.parentElement.children = this.parentElement.children.filter(node => node !== this);this.parentElement = null; } }
  attachShadow() { this.shadowRoot = new Element('shadow');return this.shadowRoot; }
  contains(node) { return this === node || this.children.some(child => child.contains(node)); }
  addEventListener(key, value) { this.events.set(key, value); }removeEventListener(key) { this.events.delete(key); }
  getBoundingClientRect() { return this.rect; }
  closest() { return this.inDialog ? { role: 'dialog' } : null; }
}
function dom() {
  const column = new Element('div');column.rect = { left: 0, right: 240, top: 0, bottom: 700, width: 240, height: 700 };
  const slot = new Element('div');column.appendChild(slot);
  const root = new Element('html');root.lang = 'en';
  const main = new Element('main');
  const selectors = { '[data-slot="sidebar.footer.action"]': () => [slot], '[class*="sidebarCol"]': () => [column],
    '[data-slot="main"]': () => [main] };
  const document = { documentElement: root, body: new Element('body'), createElement: tag => new Element(tag),
    querySelectorAll: selector => (selectors[selector] ? selectors[selector]() : []) };
  const timers = new Map();let nextId = 1;const cleared = [];
  const observers = [];let disconnected = 0;const warnings = [];
  const h = { ...host(), document,
    setTimeout: fn => { const id = nextId++;timers.set(id, fn);return id; },
    clearTimeout: id => { timers.delete(id);cleared.push(id); },
    addEventListener() {}, removeEventListener() {}, console: { warn: message => warnings.push(message) },
    MutationObserver: class { constructor(callback) { this.callback = callback;observers.push(this); }
      observe(target, options) { this.target = target;this.options = options; }
      disconnect() { disconnected += 1; } } };
  h.top = h;
  return { h, column, slot, main, selectors, observers, warnings, timers, cleared,
    get disconnected() { return disconnected; },
    flush() { const pending = [...timers.entries()];for (const [id, fn] of pending) { timers.delete(id);fn(); } } };
}
test('entry mounts into the stable column and honors the full handle contract', () => {
  const d = dom();const a = createDSHPageAdapter(d.h);const appearance = a.observeAppearance();
  let opened = 0, retried = 0, dismissed = 0;
  const e = a.mountEntry(d.h.document, () => opened++, {}, null, appearance, d.h, () => retried++, () => dismissed++);
  assert.equal(d.observers.length, 1);assert.equal(d.observers[0].target, d.h.document.body);
  assert.deepEqual(d.observers[0].options, { childList: true, subtree: true, attributes: true,
    attributeFilter: ['data-slot', 'data-phase', 'data-ds-dark-theme', 'class', 'hidden', 'aria-hidden', 'role'] });
  assert.equal(d.column.children.includes(e.element), false);
  e.update(true);
  assert.equal(e.element.parentElement, d.column);assert.notEqual(e.element.parentElement, d.slot);
  assert.equal(d.column.children.at(-1), e.element);assert.equal(e.element.style.display, 'inline-flex');
  assert.equal(e.element.style['--entry-bg'], '#f8f8f8');
  e.button.events.get('click')();assert.equal(opened, 1);
  e.setWallpaperFailure({ retrying: true });
  const recovery = e.element.shadowRoot.children[2];
  assert.equal(recovery.hidden, false);assert.equal(recovery.children[0].disabled, true);
  d.flush();
  recovery.children[0].events.get('click')();assert.equal(retried, 1);
  recovery.children[1].events.get('click')();assert.equal(dismissed, 1);assert.equal(recovery.hidden, true);
  e.setWallpaperFailure(null);assert.equal(recovery.hidden, true);
  e.update(false);assert.equal(e.element.style.display, 'none');assert.equal(e.button.disabled, true);
  e.update(true);assert.equal(e.element.style.display, 'inline-flex');assert.equal(e.button.disabled, false);
  e.remove();e.remove();
  assert.equal(d.disconnected, 1);assert.equal(d.column.children.includes(e.element), false);
  assert.equal(e.button.events.size, 0);assert.equal(recovery.children[0].events.size, 0);
  d.flush();assert.equal(d.timers.size, 0);
});
test('adapter observer re-appends after a container swap and refreshes appearance', () => {
  const d = dom();const a = createDSHPageAdapter(d.h);
  const e = a.mountEntry(d.h.document, () => {}, {}, null, a.observeAppearance(), d.h, () => {}, () => {});
  e.update(true);assert.equal(e.element.parentElement, d.column);
  const next = new Element('div');next.rect = { left: 0, right: 240, top: 0, bottom: 700, width: 240, height: 700 };
  d.slot.remove();d.selectors['[data-slot="sidebar.footer.action"]'] = () => [];
  d.selectors['[class*="sidebarCol"]'] = () => [next];
  d.observers[0].callback([{ target: d.h.document.body }]);d.flush();
  assert.equal(e.element.parentElement, next);assert.equal(e.element.style.display, 'inline-flex');
  d.h.document.body.setAttribute('data-ds-dark-theme', 'true');
  d.observers[0].callback([{ target: d.h.document.body }]);d.flush();
  assert.equal(e.element.style['--entry-bg'], '#161616');
  d.observers[0].callback([{ target: e.element }]);assert.equal(d.timers.size, 0);
  e.remove();e.remove();assert.equal(d.disconnected, 1);
});
test('entry hides gracefully with at most one diagnostic when no sane container', () => {
  const d = dom();d.selectors['[data-slot="sidebar.footer.action"]'] = () => [];
  d.selectors['[class*="sidebarCol"]'] = () => [new Element(), new Element()];
  const a = createDSHPageAdapter(d.h);
  const e = a.mountEntry(d.h.document, () => {}, {}, null, a.observeAppearance(), d.h, () => {}, () => {});
  e.update(true);assert.equal(e.element.style.display, 'none');assert.equal(d.warnings.length, 1);
  assert.match(d.warnings[0], /sidebar column/);
  e.update(true);assert.equal(d.warnings.length, 1);
  e.update(false);assert.equal(d.warnings.length, 1);
  e.remove();
});
test('column falls back to the unique sidebarCol when the slot is detached', () => {
  const d = dom();d.slot.remove();d.selectors['[data-slot="sidebar.footer.action"]'] = () => [d.slot];
  const a = createDSHPageAdapter(d.h);
  const e = a.mountEntry(d.h.document, () => {}, {}, null, a.observeAppearance(), d.h, () => {}, () => {});
  e.update(true);assert.equal(e.element.parentElement, d.column);
  e.element.rect = { left: 0, right: 999, top: 0, bottom: 30, width: 999, height: 30 };
  e.update(true);assert.equal(e.element.style.display, 'none');assert.equal(d.warnings.length, 1);
  e.remove();
});
test('one adapter observer serves multiple entries and releases after the last remove', () => {
  const d = dom();const a = createDSHPageAdapter(d.h);const appearance = a.observeAppearance();
  const first = a.mountEntry(d.h.document, () => {}, {}, null, appearance, d.h, () => {}, () => {});
  const second = a.mountEntry(d.h.document, () => {}, {}, null, appearance, d.h, () => {}, () => {});
  assert.equal(d.observers.length, 1);
  first.update(true);second.update(true);
  assert.deepEqual(d.column.children.slice(-2), [first.element, second.element]);
  first.remove();assert.equal(d.disconnected, 0);
  second.remove();second.remove();assert.equal(d.disconnected, 1);
});
test('entry works without a host MutationObserver', () => {
  const d = dom();delete d.h.MutationObserver;
  const a = createDSHPageAdapter(d.h);
  const e = a.mountEntry(d.h.document, () => {}, {}, null, a.observeAppearance(), d.h, () => {}, () => {});
  e.update(true);assert.equal(e.element.parentElement, d.column);
  e.remove();assert.equal(d.disconnected, 0);
});
test('wallpaper ports admit only the unique connected main surface', () => {
  const h = host();
  const main = new Element('main');
  const dialogMain = new Element('main');dialogMain.inDialog = true;
  const stale = new Element('main');stale.isConnected = false;
  const decoy = new Element('section');
  const mains = [main, dialogMain, stale];
  h.document.querySelectorAll = selector => selector === '[data-slot="main"]' ? [...mains]
    : (selector === '[data-slot="shell-frame"]' ? [decoy] : []);
  const a = createDSHPageAdapter(h);
  assert.equal(a.wallpaper.validPage(h), true);
  assert.equal(a.wallpaper.shellState(() => false), 'cancelled');
  assert.equal(a.wallpaper.shellState(() => true), 'ready');
  assert.deepEqual(a.wallpaper.surfaces(h), [main]);
  mains.push(new Element('main'));
  assert.equal(a.wallpaper.shellState(() => true), null);assert.deepEqual(a.wallpaper.surfaces(h), []);
  mains.length = 0;
  assert.equal(a.wallpaper.shellState(() => true), null);assert.deepEqual(a.wallpaper.surfaces(h), []);
  delete h.__DSH_BOOT__;
  assert.equal(a.wallpaper.validPage(h), false);
  assert.equal(a.wallpaper.shellState(() => true), null);assert.deepEqual(a.wallpaper.surfaces(h), []);
});
test('wallpaper group is frozen, atomic, and keyed to the dsh marker', () => {
  const a = createDSHPageAdapter(host());
  assert(Object.isFrozen(a));assert(Object.isFrozen(a.controllerWallpaper));assert(Object.isFrozen(a.wallpaper));
  assert(Object.isFrozen(a.wallpaper.attributes));
  assert.deepEqual(a.controllerWallpaper, { owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: false });
  for (const member of ['validPage', 'shellState', 'surfaces']) assert.equal(typeof a.wallpaper[member], 'function');
  assert.equal(typeof a.wallpaper.css, 'string');assert.equal(typeof a.wallpaper.scope, 'string');
  assert.equal(a.wallpaper.attributes.surfaceMarker, 'data-azhou-dsh-wallpaper-surface');
  assert.deepEqual(a.wallpaper.attributes.observeFilter,
    ['data-slot', 'data-phase', 'data-ds-dark-theme', 'hidden', 'aria-hidden', 'class', 'style']);
  assert(a.wallpaper.css.includes('[data-azhou-dsh-wallpaper-surface="active"]'));
  assert(a.wallpaper.css.includes('[data-slot="root"] > *') && a.wallpaper.css.includes('[data-phase]'));
  assert(a.wallpaper.css.includes('background-color:transparent!important'));
  assert.equal(a.wallpaper.scope,
    'decoded image, viewport cover, unique validated DSH main surface; deeper layers separate');
});
