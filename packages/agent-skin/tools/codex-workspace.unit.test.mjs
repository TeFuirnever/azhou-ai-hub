import assert from 'node:assert/strict';
import test from 'node:test';
import { webcrypto } from 'node:crypto';
import { createWallpaperApplicator } from '../wallpaper/apply.js';
import { createCodexPageAdapter } from '../extension/codex-page-adapter.mjs';

function scene() {
  class Element {
    constructor(role, attributes = []) {
      this.role = role;
      this.attributes = new Set(attributes);
      this.children = [];
      this.parentElement = null;
      this.isConnected = true;
      this.hidden = false;
      this.style = { display: 'block', visibility: 'visible', opacity: '1', backgroundColor: 'rgb(24,24,24)' };
    }
    append(child) { child.parentElement = this; this.children.push(child); return child; }
    contains(node) { return this === node || this.children.some(child => child.contains(node)); }
    matches(selector) {
      return [...this.attributes].some(attribute => selector.includes(`[${attribute}]`));
    }
    closest(selector) {
      for (let node = this; node; node = node.parentElement) {
        if (node.matches(selector) || node.role === 'protected' && selector.includes('dialog')) return node;
      }
      return null;
    }
    getClientRects() { return this.style.display === 'contents' || this.style.display === 'none' ? [] : [{ width: 500, height: 600 }]; }
    querySelectorAll(selector) {
      const descendants = this.children.flatMap(child => [child, ...child.querySelectorAll('*')]);
      if (selector === '*') return descendants;
      return descendants.filter(node => node.matches(selector) || (selector.includes('.workspace > main.thread-pane')
        && node.role === 'thread' && node.parentElement.role === 'workspace'));
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
  }
  const html = new Element('html');
  const shell = html.append(new Element('root'));
  const frame = shell.append(new Element('frame', ['data-app-shell-frame']));
  const cached = frame.append(new Element('cached', ['data-app-shell-main-surface']));
  cached.style.display = 'none';
  const main = frame.append(new Element('main', ['data-app-shell-main-surface']));
  const page = main.append(new Element('page', ['data-app-shell-page-surface']));
  page.style.display = 'contents';
  const workspace = page.append(new Element('workspace'));
  const thread = workspace.append(new Element('thread'));
  const document = { body: {}, documentElement: html, getElementById(id) { return id === 'root' ? shell : null; } };
  const host = { document, location: { href: 'app://-/index.html' }, getComputedStyle(node) { return node.style; } };
  return { host, shell, frame, cached, main, page, thread, adapter: createCodexPageAdapter(host) };
}

test('active workspace skips a hidden cached first main and retains the visible inner paint plane', () => {
  const f = scene();
  const observed = f.adapter.observeWorkspace();
  assert.equal(observed.kind, 'observed');
  assert.equal(observed.activeMain, f.main);
  assert.ok(observed.knownPaintPlanes.some(plane => plane.node === f.thread && plane.kind === 'surface'));
  assert.ok(!observed.knownPaintPlanes.some(plane => plane.node === f.cached));
  assert.equal(observed.coverage.messaging, 'observed');
  assert.equal(observed.coverage.auxiliary, 'unknown');
  assert.equal(f.adapter.observeWorkspace(), observed);
});

test('a display contents ancestor does not hide its visible messaging descendant', () => {
  const f = scene();
  const observed = f.adapter.observeWorkspace();
  assert.ok(observed.knownPaintPlanes.some(plane => plane.node === f.thread));
  assert.ok(!observed.knownPaintPlanes.some(plane => plane.node === f.page));
});

test('two visible mains reject ambiguity rather than selecting a larger one', () => {
  const f = scene();
  f.cached.style.display = 'block';
  assert.deepEqual(f.adapter.observeWorkspace(), { kind: 'ambiguous', candidateCount: 2 });
});

test('observed same-document A to B to A retires both previous workspace identities', () => {
  const f = scene();
  const first = f.adapter.observeWorkspace();
  f.main.hidden = true;
  f.cached.style.display = 'block';
  const second = f.adapter.observeWorkspace();
  f.main.hidden = false;
  f.cached.style.display = 'none';
  const third = f.adapter.observeWorkspace();
  assert.equal(first.documentToken, third.documentToken);
  assert.equal(new Set([first.workspaceEpoch, second.workspaceEpoch, third.workspaceEpoch]).size, 3);
  assert.equal(f.adapter.isWorkspaceCurrent(first), false);
  assert.equal(f.adapter.isWorkspaceCurrent(third), true);
});

test('unknown messaging coverage is not promoted by an empty match', () => {
  const f = scene();
  f.thread.isConnected = false;
  const observed = f.adapter.observeWorkspace();
  assert.equal(observed.kind, 'observed');
  assert.equal(observed.coverage.messaging, 'unknown');
  assert.ok(observed.knownPaintPlanes.length > 0);
});

test('skin transparency does not change structural workspace identity', () => {
  const f = scene();
  const observed = f.adapter.observeWorkspace();
  f.thread.style.backgroundColor = 'transparent';
  assert.equal(f.adapter.observeWorkspace(), observed);
});

test('unavailable layout retires the prior observation without throwing', () => {
  const f = scene();
  const observed = f.adapter.observeWorkspace();
  f.host.getComputedStyle = () => { throw new Error('style unavailable'); };
  assert.deepEqual(f.adapter.observeWorkspace(), { kind: 'unsupported', reason: 'observation-unavailable' });
  assert.equal(f.adapter.isWorkspaceCurrent(observed), false);
});

for (const attribute of ['hidden', 'style', 'class']) {
  test(`a hidden known paint plane becoming visible through ${attribute} invalidates its old coverage`, () => {
    const f = scene();
    f.thread.style.display = 'none';
    const matches = f.thread.matches.bind(f.thread);
    f.thread.matches = selector => selector.includes('main.thread-pane') || matches(selector);
    let callback;
    f.host.MutationObserver = class { constructor(fn) { callback = fn; } observe() {} disconnect() {} takeRecords() { return []; } };
    const initial = f.adapter.observeWorkspace();
    assert.equal(initial.coverage.messaging, 'unknown');
    let invalidated = 0;
    const lease = f.adapter.watchWorkspace(initial, () => { invalidated += 1; });
    f.thread.style.display = 'block';
    callback([{ type: 'attributes', target: f.thread, attributeName: attribute }]);
    assert.equal(invalidated, 1, 'mutation delivery must invalidate without an explicit status read');
    assert.equal(lease.current(), false);
    lease.dispose();
  });
}

test('pending main geometry becoming visible wakes applicator without a mutation or timeout', async () => {
  const f = scene();
  let visible = false;
  f.main.getClientRects = () => visible ? [{width:500,height:600}] : [];
  const resizes = [];
  const mutations = [];
  const timers = [];
  f.host.crypto = webcrypto; f.host.atob = globalThis.atob;
  f.host.setTimeout = callback => { timers.push(callback); return callback; };
  f.host.clearTimeout = () => {};
  f.host.MutationObserver = class { constructor(callback) { this.callback=callback; mutations.push(this); } observe() {} disconnect() { this.closed=true; } takeRecords() { return []; } };
  f.host.ResizeObserver = class { constructor(callback) { this.callback=callback; this.targets=[]; resizes.push(this); } observe(node) { this.targets.push(node); } disconnect() { this.closed=true; } };
  let renders = 0;
  const apply = createWallpaperApplicator(() => { renders++; return {applied:true}; }, {version:'1',css:'',pageAdapter:f.adapter}, f.host);
  const pending = apply({image:'data:image/png;base64,AA==',strength:37,surface:'#222'});
  const resize = resizes.find(observer => observer.targets.includes(f.main));
  assert.ok(resize, 'a recognized zero-sized main, not just the root, is observed');
  visible = true;
  resize.callback([]);
  assert.equal((await pending).applied, true);
  assert.equal(renders, 1);
  assert.ok([...resizes,...mutations].every(observer => observer.closed));
});

test('active coverage watches known zero-sized paint candidates for geometry-only reveal', () => {
  const f = scene();
  let visible = false;
  f.thread.getClientRects = () => visible ? [{width:100,height:100}] : [];
  const resizes = [];
  f.host.MutationObserver = class { observe() {} disconnect() {} takeRecords() { return []; } };
  f.host.ResizeObserver = class { constructor(callback) { this.callback=callback; this.targets=[]; resizes.push(this); } observe(node) { this.targets.push(node); } disconnect() {} };
  let invalidated = false;
  const lease = f.adapter.watchWorkspace(f.adapter.observeWorkspace(), () => { invalidated=true; });
  const resize = resizes.find(observer => observer.targets.includes(f.thread));
  assert.ok(resize, 'known non-painted candidate retains only an observation lease');
  visible = true; resize.callback([]);
  assert.equal(invalidated, true);
  lease.dispose();
});

for (const boundary of ['abort', 'timeout', 'resize-setup-failure', 'throwing-disconnect']) {
  test(`pending geometry wait releases independent resources after ${boundary}`, async () => {
    const f=scene(); f.main.getClientRects=()=>[];
    f.host.crypto=webcrypto; f.host.atob=globalThis.atob;
    const observers=[],listeners=new Map(),timers=[];
    for(const [target,label] of [[f.host,'host'],[f.host.document,'document']]) {
      target.addEventListener=(name,callback)=>listeners.set(label+':'+name,callback);
      target.removeEventListener=name=>listeners.delete(label+':'+name);
    }
    f.host.setTimeout=callback=>{const timer={callback,cleared:false};timers.push(timer);return timer;};
    f.host.clearTimeout=timer=>{timer.cleared=true;};
    f.host.MutationObserver=class {constructor(){observers.push(this);}observe(){}disconnect(){this.closed=true;if(boundary==='throwing-disconnect')throw Error('disconnect fault');}};
    f.host.ResizeObserver=class {constructor(){observers.push(this);}observe(){if(boundary==='resize-setup-failure')throw Error('resize unavailable');}disconnect(){this.closed=true;}};
    const abort=new AbortController();let renders=0;
    const apply=createWallpaperApplicator(()=>{renders++;return {applied:true};},{version:'1',css:'',pageAdapter:f.adapter},f.host);
    const pending=apply({image:'data:image/png;base64,AA==',strength:37,surface:'#222'},()=>true,abort.signal);
    if(boundary==='timeout')timers[0].callback();
    else if(boundary!=='resize-setup-failure') {
      assert.ok(listeners.has('document:visibilitychange'));
      assert.ok(!listeners.has('host:visibilitychange'));
      abort.abort();
    }
    assert.equal((await pending).applied,false);
    assert.equal(renders,0);
    assert.ok(observers.every(observer=>observer.closed));
    assert.equal(listeners.size,0);
    assert.ok(timers.every(timer=>timer.cleared));
  });
}
