import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import test from 'node:test';
import { createWallpaperApplicator } from '../wallpaper/apply.js';
import { bootstrapStartup } from '../extension/bootstrap.mjs';

const VALUE = { image: 'data:image/png;base64,AA==', strength: 37, surface: 'rgb(10, 20, 30)' };

function fixture({ deferDigest = false } = {}) {
  const root = { querySelector() { return {}; } };
  const host = {
    document: { body: {}, documentElement: {}, getElementById(id) { return id === 'root' ? root : null; } },
    atob: globalThis.atob,
    crypto: webcrypto,
  };
  let finishDigest;
  if (deferDigest) host.crypto = { subtle: { digest: (...args) => new Promise((resolve, reject) => {
    finishDigest = () => webcrypto.subtle.digest(...args).then(resolve, reject);
  }) } };
  const observation = Object.freeze({ kind: 'observed', documentToken: 'page:1', workspaceEpoch: 1,
    shell: root, activeMain: {}, layoutAncestors: [], knownPaintPlanes: [], coverage: { messaging: 'unknown' } });
  let current = observation;
  const adapter = {
    workspaceContract: 'codex-active-workspace/v1',
    watchWorkspace() { return {current:()=>true,dispose(){}}; },
    observeWorkspace() { return current; },
    isWorkspaceCurrent(value) { return value === current && current.kind === 'observed'; },
  };
  const calls = [];
  const apply = createWallpaperApplicator(value => {
    calls.push(value);
    return { applied: true, imageDecoded: true };
  }, { version: '1', css: '', pageAdapter: adapter }, host);
  return { apply, calls, observation, adapter, host,
    replace(value) { current = value; }, finishDigest() { assert.equal(typeof finishDigest, 'function'); finishDigest(); } };
}

test('workspace observation survives preparation as the same renderer input', async () => {
  const scene = fixture();
  const result = await scene.apply(VALUE);
  assert.equal(result.applied, true);
  assert.equal(scene.calls.length, 1);
  assert.equal(scene.calls[0].workspaceObservation, scene.observation);
  assert.equal(scene.calls[0].pageAdapter, scene.adapter);
});

test('workspace replacement during image hashing prevents renderer installation', async () => {
  const scene = fixture({ deferDigest: true });
  const pending = scene.apply(VALUE);
  await Promise.resolve();
  scene.replace(Object.freeze({ ...scene.observation, workspaceEpoch: 2, activeMain: {} }));
  scene.finishDigest();
  const result = await pending;
  assert.equal(result.applied, false);
  assert.equal(scene.calls.length, 0);
});

test('ambiguous active workspace cannot fall through to a cached shell', async () => {
  const scene = fixture();
  scene.replace(Object.freeze({ kind: 'ambiguous', candidateCount: 2 }));
  const result = await scene.apply(VALUE);
  assert.equal(result.applied, false);
  assert.equal(scene.calls.length, 0);
});

for (const kind of ['unsupported', 'pending-invalid']) {
  test(`Codex ${kind} refuses legacy shell fallback`, async () => {
    const scene = fixture();
    scene.replace({ kind });
    assert.equal((await scene.apply(VALUE)).applied, false);
    assert.equal(scene.calls.length, 0);
  });
}

test('a throwing Codex observation refuses legacy shell fallback', async () => {
  const scene = fixture();
  scene.adapter.observeWorkspace = () => { throw new Error('host changed'); };
  assert.equal((await scene.apply(VALUE)).applied, false);
  assert.equal(scene.calls.length, 0);
});

test('the first observed workspace is leased synchronously before any microtask', async () => {
  const scene = fixture();
  let leased = false;
  let disposed = 0;
  scene.adapter.watchWorkspace = () => {
    leased = true;
    return { current: () => true, dispose: () => { disposed += 1; } };
  };
  const pending = scene.apply(VALUE);
  assert.equal(leased, true);
  assert.equal((await pending).applied, true);
  assert.equal(disposed, 1);
});

for (const defect of ['observeWorkspace','isWorkspaceCurrent','watchWorkspace','label-only','unknown-label','empty-label','null-label','getter-label','getter-function','inherited-label','inherited-function','inherited-all']) {
  test(`bootstrap and applicator refuse declared ${defect} without invoking getters or legacy rendering`, async () => {
    const scene=fixture(); let adapter={...scene.adapter}; let getters=0;
    if(['observeWorkspace','isWorkspaceCurrent','watchWorkspace'].includes(defect))delete adapter[defect];
    if(defect==='label-only')adapter={workspaceContract:'codex-active-workspace/v1'};
    if(defect==='unknown-label')adapter.workspaceContract='future-unknown';
    if(defect==='empty-label')adapter.workspaceContract='';
    if(defect==='null-label')adapter.workspaceContract=null;
    if(defect==='getter-label')Object.defineProperty(adapter,'workspaceContract',{get(){getters++;return 'codex-active-workspace/v1';}});
    if(defect==='getter-function')Object.defineProperty(adapter,'observeWorkspace',{get(){getters++;return scene.adapter.observeWorkspace;}});
    if(defect==='inherited-label'){delete adapter.workspaceContract;Object.setPrototypeOf(adapter,{workspaceContract:'codex-active-workspace/v1'});}
    if(defect==='inherited-function'){delete adapter.watchWorkspace;Object.setPrototypeOf(adapter,{watchWorkspace:scene.adapter.watchWorkspace});}
    if(defect==='inherited-all')adapter=Object.create(scene.adapter);
    const animation=()=>{};let renders=0;
    bootstrapStartup({installStartup:()=>{},installAnimation:animation,createLocalization:()=>{},createImageSettings:()=>{},
      createWallpaperApplicator,installRenderer:()=>{renders++;return {applied:true};},version:'1',css:'',assets:{},host:scene.host,pageAdapter:adapter});
    assert.equal((await animation.applyWallpaper(VALUE)).applied,false);
    assert.equal(renders,0);
    assert.equal(getters,0);
  });
}
