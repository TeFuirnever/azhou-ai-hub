import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { fileURLToPath } from 'node:url';

const sourcePath = fileURLToPath(new URL('../extension/hosts/dsh-startup-gate.js', import.meta.url));
const source = readFileSync(sourcePath, 'utf8');

function environment({ style = {}, rect, hidden = false, withRoot = true, hitTestForeign = false,
  colorScheme = 'dark', bodyTheme = null, bodyColors = {}, matchMediaAvailable = true,
  matchMediaDark = colorScheme === 'dark', cssSupports = true, cssAvailable = true } = {}) {
  const timers = new Map();
  const frames = new Map();
  const listeners = new Map();
  let nextTimer = 1;
  let nextFrame = 1;
  const root = {
    children: [],
    appendChild(element) {
      element.parentNode?.removeChild?.(element);
      element.parentNode = this;
      this.children.push(element);
      return element;
    },
    removeChild(element) {
      const index = this.children.indexOf(element);
      if (index >= 0) this.children.splice(index, 1);
      element.parentNode = null;
      return element;
    },
  };
  const body = bodyTheme === null ? null : { hasAttribute(name) {
    return name === 'data-ds-dark-theme' && bodyTheme === 'dark';
  } };
  const document = {
    hidden,
    visibilityState: hidden ? 'hidden' : 'visible',
    ...(body ? { body } : {}),
    ...(withRoot ? { documentElement: root } : {}),
    elementFromPoint() { return hitTestForeign ? { tagName: 'DIALOG' } : root.children.at(-1); },
    createElement(tag) {
      assert.equal(tag, 'div');
      return {
        style: {},
        attributes: new Map(),
        setAttribute(name, value) { this.attributes.set(name, value); },
        getBoundingClientRect() {
          return rect ?? { left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600 };
        },
        remove() { this.parentNode?.removeChild(this); this.removed = true; },
      };
    },
  };
  const host = {
    document,
    innerWidth: 800,
    innerHeight: 600,
    ...(cssAvailable ? { CSS: { supports(property, value) {
      return cssSupports && property === 'color'
        && /^(?:#[\da-f]{3,8}|(?:rgb|rgba|hsl|hsla|color)\([^)]*\)|transparent|currentcolor)$/i
          .test(String(value).trim());
    } } } : {}),
    getComputedStyle(element) {
      const background = element?.style?.backgroundColor;
      const hex = /^#([\da-f]{6})$/i.exec(background ?? '');
      const backgroundColor = background === '#f8f8f8' ? 'rgb(248, 248, 248)'
        : background === '#10121c' ? 'rgba(16, 18, 28, 1)'
          : hex ? `rgb(${Number.parseInt(hex[1].slice(0, 2), 16)}, ${Number.parseInt(hex[1].slice(2, 4), 16)}, ${Number.parseInt(hex[1].slice(4, 6), 16)})`
            : background === 'transparent' ? 'rgba(0, 0, 0, 0)'
              : /^rgba?\(/i.test(background ?? '') ? background : 'rgba(16, 18, 28, 1)';
      return {
        position: element?.style?.position,
        display: element?.style?.display || 'block',
        visibility: element?.style?.visibility || 'visible',
        pointerEvents: element?.style?.pointerEvents,
        zIndex: element?.style?.zIndex,
        opacity: '1',
        backgroundColor,
        colorScheme,
        getPropertyValue(name) {
          if (element === body) return bodyColors[name] ?? '';
          return name === 'color-scheme' ? colorScheme ?? '' : '';
        },
        ...style,
      };
    },
    setTimeout(callback, delay) {
      const id = nextTimer++;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    requestAnimationFrame(callback) {
      const id = nextFrame++;
      frames.set(id, callback);
      return id;
    },
    cancelAnimationFrame(id) { frames.delete(id); },
    addEventListener(type, callback) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(callback);
    },
    removeEventListener(type, callback) { listeners.get(type)?.delete(callback); },
    ...(matchMediaAvailable ? { matchMedia(query) {
      assert.equal(query, '(prefers-color-scheme: dark)');
      return { matches: matchMediaDark };
    } } : {}),
  };
  return {
    host, document, root, timers, frames, listeners,
    run() { runInNewContext(source, host, { filename: sourcePath }); },
    fireTimer(delay) {
      const entry = [...timers].find(([, value]) => value.delay === delay);
      assert.ok(entry, `expected a ${delay}ms timer`);
      timers.delete(entry[0]);
      entry[1].callback();
    },
    fireFrame() {
      const entry = frames.entries().next().value;
      assert.ok(entry, 'expected a pending animation frame');
      frames.delete(entry[0]);
      entry[1]();
    },
    pagehide() { for (const callback of listeners.get('pagehide') ?? []) callback(); },
  };
}

test('valid DSH cover publishes one immutable gate and reveals only after ready', () => {
  const env = environment();
  env.run();
  const gate = env.host.__azhouDshStartupGate;
  assert.equal(gate.owner, 'azhou-dsh-startup-gate-v1');
  assert.equal(gate.status(), 'waiting');
  assert.equal(env.root.children.length, 1);
  assert.equal(env.root.children[0].style.zIndex, '2147483647', 'gate owns the highest CSS layer');
  assert.equal(env.document.__azhouDshStartupGateDocumentLatch.owner, gate.owner);
  assert.equal(Object.getOwnPropertyDescriptor(env.document, '__azhouDshStartupGateDocumentLatch').configurable, false);
  assert.equal(Object.getOwnPropertyDescriptor(env.host, '__azhouDshStartupGate').configurable, false);
  let expirations = 0;
  gate.onExpire(() => { expirations += 1; });

  assert.equal(gate.claim(), true);
  assert.equal(gate.claim(), false, 'same document cannot claim twice');
  assert.equal(gate.status(), 'claimed');
  assert.equal(gate.ready(), true);
  assert.equal(gate.ready(), false, 'ready is one-shot');
  assert.equal(env.root.children.length, 1, 'cover stays in place until its reveal frame');
  assert.equal(gate.status(), 'revealing');
  env.fireFrame();
  assert.equal(gate.status(), 'released');
  assert.equal(expirations, 0, 'normal ready and release do not report a gate failure');
  assert.equal(env.root.children.length, 0);
  env.run();
  assert.equal(env.host.__azhouDshStartupGate, gate, 'duplicate/HMR injection cannot replace the document gate');
  assert.equal(env.root.children.length, 0);
});

test('cover uses DSH surface color, theme signals, and a dark fallback', () => {
  const cases = [
    ['valid DSH surface token wins', { bodyTheme: 'light', bodyColors: { '--dsw-alias-bg-base': '#0d1117' } }, '#0d1117'],
    ['invalid DSH surface token falls back to the body theme',
      { bodyTheme: 'light', bodyColors: { '--dsw-alias-bg-base': 'url(evil)' }, colorScheme: 'dark' }, '#f8f8f8'],
    ['CSS unavailable falls back to the body theme',
      { bodyTheme: 'dark', bodyColors: { '--dsw-alias-bg-base': '#f8f8f8' }, cssAvailable: false }, '#10121c'],
    ['light color scheme', { colorScheme: 'light' }, '#f8f8f8'],
    ['dark color scheme', { colorScheme: 'dark' }, '#10121c'],
    ['DSH dark body marker overrides light preference', { bodyTheme: 'dark', colorScheme: 'light' }, '#10121c'],
    ['DSH light body state overrides dark preference', { bodyTheme: 'light', colorScheme: 'dark' }, '#f8f8f8'],
    ['system color scheme follows matchMedia',
      { colorScheme: 'light dark', matchMediaDark: true }, '#10121c'],
    ['matchMedia selects light when color scheme is unavailable',
      { colorScheme: null, matchMediaDark: false }, '#f8f8f8'],
    ['no theme capability uses safe fallback', { colorScheme: null, matchMediaAvailable: false }, '#10121c'],
  ];
  for (const [label, options, expected] of cases) {
    const env = environment(options);
    env.run();
    const cover = env.root.children[0];
    assert.equal(cover.style.backgroundColor, expected, label);
    const computed = env.host.getComputedStyle(cover).backgroundColor;
    const computedColor = /^rgba?\((.*)\)$/i.exec(computed)?.[1].split(/[\s,/]+/).filter(Boolean) ?? [];
    const alpha = computedColor.length === 4 ? computedColor[3] : computedColor.length === 3 ? '1' : '';
    assert.equal(Number(alpha), 1, `${label} produces an opaque computed background`);
  }
});

test('transparent DSH surface tokens fall back to an opaque theme color without disturbing the one-shot gate', () => {
  for (const token of ['transparent', 'rgba(16, 18, 28, 0)', 'rgba(16, 18, 28, 0.5)',
    'rgb(16 18 28 / 50%)', 'color(srgb 0 0 0 / .5)', '#00000000', '#0008']) {
    const env = environment({ bodyTheme: 'light', bodyColors: { '--dsw-alias-bg-base': token }, colorScheme: 'dark' });
    env.run();
    const gate = env.host.__azhouDshStartupGate;
    const cover = env.root.children[0];
    assert.ok(gate, `${token} keeps a valid gate available`);
    assert.equal(cover.style.backgroundColor, '#f8f8f8', `${token} falls back to the DSH light theme`);
    assert.equal(env.host.getComputedStyle(cover).backgroundColor, 'rgb(248, 248, 248)',
      `${token} yields a computed opaque cover`);
    assert.equal(cover.style.zIndex, '2147483647', `${token} keeps the cover above the gated iframe`);
    assert.equal(gate.claim(), true, `${token} permits one playback claim`);
    assert.equal(gate.claim(), false, `${token} cannot claim the same document twice`);
    assert.equal(gate.release(), true);
    assert.equal(gate.status(), 'expired');
    assert.equal(env.root.children.length, 0);
  }
});

test('expired, released, and page-hidden gates cannot claim or play late', () => {
  const env = environment();
  env.run();
  const gate = env.host.__azhouDshStartupGate;
  env.fireTimer(8_000);
  assert.equal(gate.status(), 'expired');
  assert.equal(gate.claim(), false);
  assert.equal(env.root.children.length, 0);
  env.run();
  assert.equal(env.host.__azhouDshStartupGate, gate, 'expired document latch prevents a late reinjection claim');
  assert.equal(gate.claim(), false);

  const pageHidden = environment();
  pageHidden.run();
  const second = pageHidden.host.__azhouDshStartupGate;
  assert.equal(second.claim(), true);
  pageHidden.pagehide();
  assert.equal(second.status(), 'expired');
  assert.equal(pageHidden.root.children.length, 0);
  assert.equal(second.ready(), false);
});

test('CSP-invalid, undersized, hidden, and rootless documents fail open permanently', () => {
  for (const [label, options] of [
    ['inline style rejected', { style: { position: 'static' } }],
    ['computed background remains transparent after style application',
      { style: { backgroundColor: 'rgba(16, 18, 28, 0)' } }],
    ['undersized cover', { rect: { left: 0, top: 0, right: 20, bottom: 20, width: 20, height: 20 } }],
    ['top-layer obstruction', { hitTestForeign: true }],
    ['hidden document', { hidden: true }],
    ['documentElement unavailable', { withRoot: false }],
  ]) {
    const env = environment(options);
    env.run();
    assert.equal(env.host.__azhouDshStartupGate, undefined, `${label} does not publish a claimable gate`);
    assert.ok(Object.getOwnPropertyDescriptor(env.document, '__azhouDshStartupGateDocumentLatch'),
      `${label} is terminal for this document`);
    env.run();
    assert.equal(env.root.children.length, 0, `${label} cannot retry after HMR or duplicate injection`);
  }
});

test('gate watchdog expires a claimed renderer that never reports ready', () => {
  const env = environment();
  env.run();
  const gate = env.host.__azhouDshStartupGate;
  let expirations = 0;
  gate.onExpire(() => { expirations += 1; });
  assert.equal(gate.claim(), true);
  env.fireTimer(12_000);
  assert.equal(gate.status(), 'expired');
  assert.equal(expirations, 1, 'claimed watchdog notifies the owning renderer once');
  assert.equal(gate.ready(), false);
  assert.equal(env.root.children.length, 0);
});
