#!/usr/bin/env node
// Isolated synthetic-host browser checks. This runner owns only its temporary Chrome profile.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { createServer } from 'node:http';
import { access, copyFile, mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { validateCheckSelection } from './startup-browser-selection.mjs';
import {sourceCheckpoint,executionCheckpoint,validateRegistration,sealCollection,claimOutput,assertOutputOwner} from './theme-measurement-evidence.mjs';
import { CDP, navigateWithLoad } from './test-startup-browser-cdp.mjs';
import { canRemoveProfile, profileIdentity, removeOwnedProfile, trackOwnedChild } from './test-startup-browser-process.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const packageMetadata = JSON.parse(await readFile(join(ROOT, 'hub-package.json'), 'utf8'));
const options = {
  chrome: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  out: join(ROOT, '.build/startup-browser-evidence'),
  generatedPayload: null,
  only: [],
};
for (let index = 2; index < process.argv.length; index++) {
  const key = process.argv[index];
  if (key === '--help') {
    console.log('node tools/test-startup-browser.mjs [--chrome /path/to/Chrome] [--out /path/to/evidence] [--generated-payload /path/to/install.js] [--only <exact check name>]');
    process.exit(0);
  }
  if (!['--chrome', '--out', '--generated-payload', '--only', '--theme-protocol', '--theme-execution-binding', '--measurement-preflight'].includes(key) || !process.argv[index + 1]) throw new Error('Unknown or missing argument: ' + key);
  const value = process.argv[++index];
  if (key === '--only') options.only.push(value);
  else if (key === '--generated-payload') options.generatedPayload = value;
  else if (key === '--theme-protocol') options.themeProtocol = value;
  else if (key === '--theme-execution-binding') options.executionBinding = value;
  else if (key === '--measurement-preflight') { assert.equal(value,'true'); options.measurementPreflight=true; }
  else options[key.slice(2)] = value;
}
options.chrome = resolve(options.chrome);
options.out = resolve(options.out);
if (options.generatedPayload) options.generatedPayload = resolve(options.generatedPayload);
const measurementOutput=options.themeProtocol?await claimOutput(options.out):null;
const themeProtocol = options.themeProtocol ? JSON.parse(await readFile(resolve(options.themeProtocol),'utf8')) : null;
if(themeProtocol){
  assert.equal(themeProtocol.schema,1);assert.ok(['train','holdout'].includes(themeProtocol.phase));
  assert.equal(themeProtocol.framesPerT,6);assert.equal(themeProtocol.conditions.length,4);
  assert.deepEqual([...themeProtocol.transparencies].sort((a,b)=>a-b),[0,15,57,85,100]);
  for(const condition of themeProtocol.conditions){assert.ok(Number.isInteger(condition.width)&&condition.width>700&&condition.width<1200);assert.ok(Number.isInteger(condition.height)&&condition.height>500&&condition.height<900);assert.ok([1.5,2].includes(condition.dpr));assert.ok([0.9,1.1].includes(condition.zoom));assert.match(condition.color,/^#[0-9a-f]{6}$/);}
}
const measurementStartedAt=new Date().toISOString();
let measurementRoot=null,measurementBefore=null;
async function checkpointMeasurement(){
  if(options.generatedPayload){
    assert.ok(options.executionBinding,'generated measurement requires wrapper execution binding');
    return executionCheckpoint(options.executionBinding,ROOT,measurementRoot,options.generatedPayload);
  }
  assert.ok(!options.executionBinding,'execution binding requires generated payload');
  return sourceCheckpoint(resolve(ROOT,'../..'),measurementRoot);
}
if(themeProtocol){try{measurementRoot=await validateRegistration(themeProtocol,measurementStartedAt);measurementBefore=await checkpointMeasurement();}
catch(error){await assertOutputOwner(measurementOutput);await writeFile(join(options.out,'measurement-preflight-failure.json'),JSON.stringify({startedAt:measurementStartedAt,error:String(error),phase:themeProtocol.phase},null,2),{flag:'wx'});throw error;}}
if(options.measurementPreflight){
  assert.ok(themeProtocol&&options.generatedPayload,'preflight requires generated measurement');
  const after=await checkpointMeasurement();
  assert.deepEqual(after.execution,measurementBefore.execution,'execution drift');
  await assertOutputOwner(measurementOutput);
  await writeFile(join(options.out,'measurement-preflight.json'),JSON.stringify({status:'preflight-only',browserStarted:false,before:measurementBefore,after},null,2),{flag:'wx'});
  await sealCollection(options.out);
  process.exit(0);
}
const onlyChecks = options.only.length ? new Set(options.only) : null;
const availableChecks = new Set();

async function observedThemeStructure(transparency) {
  const fail = message => { throw new Error('theme structure: '+message); };
  const root=document.documentElement,body=document.body;
  const wash=root.style.getPropertyValue('--azhou-wallpaper-wash');
  if(!wash.startsWith('url("data:image/svg+xml,'))fail('not a local color mask');
  let uri;try{uri=JSON.parse(wash.slice(4,-1));}catch{fail('invalid CSS URL');}
  const source=decodeURIComponent(uri.slice(uri.indexOf(',')+1));
  if(/<!|<\?/.test(source))fail('declarations are forbidden');
  const doc=new DOMParser().parseFromString(source,'image/svg+xml');
  if(doc.querySelector('parsererror'))fail('invalid XML');
  const svg=doc.documentElement;
  const attributes=(node,tag,names)=>{
    if(!node||node.localName!==tag||node.namespaceURI!=='http://www.w3.org/2000/svg')fail('unexpected node '+tag);
    if([...node.attributes].map(a=>a.name).sort().join('|')!==[...names].sort().join('|'))fail('unexpected attributes '+tag);
    if([...node.childNodes].some(n=>n.nodeType!==1&&(n.nodeType!==3||n.textContent.trim())))fail('unexpected child node');
    return Object.fromEntries([...node.attributes].map(a=>[a.name,a.value]).sort((a,b)=>a[0].localeCompare(b[0])));
  };
  const sa=attributes(svg,'svg',['xmlns','width','height','viewBox']);
  if(sa.xmlns!=='http://www.w3.org/2000/svg'||Number(sa.width)!==innerWidth||Number(sa.height)!==innerHeight||sa.viewBox!=='0 0 '+innerWidth+' '+innerHeight)fail('viewport changed');
  if(svg.children.length!==3)fail('root child count');
  const [defs,outside,local]=svg.children;attributes(defs,'defs',[]);if(defs.children.length!==2)fail('defs child count');
  const [gradient,mask]=defs.children;const ga=attributes(gradient,'linearGradient',['id']);if(ga.id!=='g')fail('gradient ID');
  if(gradient.children.length!==7)fail('gradient stop count');
  const stops=[...gradient.children].map(n=>{const a=attributes(n,'stop',['offset','stop-color','stop-opacity']);if(n.children.length||!Number.isFinite(Number(a['stop-opacity']))||Number(a['stop-opacity'])<0||Number(a['stop-opacity'])>1)fail('invalid gradient stop');return a;});
  const ma=attributes(mask,'mask',['id']);if(ma.id!=='m'||mask.children.length!==2)fail('mask shape');
  const white=attributes(mask.children[0],'rect',['width','height','fill']);if(white.width!=='100%'||white.height!=='100%'||white.fill!=='white')fail('outer mask');
  const hole=attributes(mask.children[1],'rect',['x','y','width','height','fill']);if(hole.fill!=='black')fail('hole fill');
  const oa=attributes(outside,'rect',['width','height','fill','mask']);if(oa.width!=='100%'||oa.height!=='100%'||oa.fill!=='url(#g)'||oa.mask!=='url(#m)')fail('outside treatment');
  const la=attributes(local,'rect',['x','y','width','height','fill','fill-opacity']);
  const main=document.querySelector('[data-app-shell-main-surface]'),bounds=main.getBoundingClientRect();
  for(const name of ['x','y','width','height'])if(!Number.isFinite(bounds[name])||Number(hole[name])!==bounds[name]||Number(la[name])!==bounds[name])fail('workspace geometry '+name);
  if([outside,local,...mask.children].some(n=>n.children.length))fail('nested paint');
  if(!Number.isFinite(transparency)||Number(la['fill-opacity'])!==(100-transparency)/100)fail('local alpha');
  if(stops.some(stop=>stop['stop-color']!==la.fill))fail('color mismatch');
  const image=root.style.getPropertyValue('--azhou-wallpaper-image');
  let scene;try{scene=JSON.parse(image.slice(4,-1));}catch{fail('scene URL');}if(!scene.startsWith('blob:'))fail('not an owned local scene');
  const bytes=await(await fetch(scene)).arrayBuffer();
  const sceneDigest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
  const computed=getComputedStyle(body);
  const backgroundImage=computed.backgroundImage.replace(uri,'[color-mask]').replace(scene,'[scene:'+sceneDigest+']');
  const invariant={svg:sa,gradient:ga,stops,mask:ma,white,hole,outside:oa,local:{...la,'fill-opacity':'[authorized-local-alpha]'},sceneDigest,
    paint:{backgroundImage,size:computed.backgroundSize,position:computed.backgroundPosition,attachment:computed.backgroundAttachment,repeat:computed.backgroundRepeat}};
  return {invariant,alpha:Number(la['fill-opacity']),wash,sceneDigest};
}

const report = {
  schema: 1,
  scope: 'actual PageController and wallpaper renderer in an isolated headless Chrome with a local synthetic Codex-like page',
  startedAt: new Date().toISOString(),
  checks: [],
  screenshots: [],
  limitations: [
    'The legacy wallpaper is a synthetic ownership and disposal model; image decoding, real legacy CSS and visual behavior are not represented.',
    'The app:// page identity is supplied through a local host adapter; no Codex process, profile, transport or user content is accessed.',
    'The wallpaper fixture uses one generated-in-test PNG pixel. The animation fixture separately generates synthetic PNGs and contours; it does not validate private or branded source art.',
    'The cold-start wallpaper check withholds and reinserts the synthetic shell in this local host; it models delayed shell mount timing but does not establish official Codex mount timing.',
    'CSP results cover the renderer after local module loading; they do not prove the official app permits the production script evaluation.',
    'Animation screenshots use an isolated Chrome file page and do not validate native WKWebView presentation or real host identity.',
    'JavaScript rAF and canvas-submission timings exclude GPU, compositor, presentation and system-memory timing.',
  ],
};
let server;
let chrome;
let profile;
let cdp;
let cleanupPromise;
let chromeOwner;
let profileOwner;
let suiteCompleted = false;
let chromeError = '';

function safeError(error) {
  return String(error?.message || error).replace(/data:image\/[^\s"']+/g, '[fixture image omitted]').slice(0, 1200);
}

async function until(operation, milliseconds = 10000, label = 'condition') {
  const deadline = Date.now() + milliseconds;
  let last;
  do {
    try {
      const value = await operation();
      if (value) return value;
    } catch (error) { last = error; }
    await delay(60);
  } while (Date.now() < deadline);
  throw new Error('Timed out waiting for ' + label + (last ? ': ' + safeError(last) : ''));
}

// Scope the witness to this synthetic startup, including its transient same-origin frames.
async function withColdStartupVideoProbe(cdp, operation) {
  await cdp.call('Network.enable');
  let registration;
  let videoRequest;
  let watcherError;
  const videoDestination = headers => Object.entries(headers ?? {}).some(([name, value]) =>
    name.toLowerCase() === 'sec-fetch-dest' && value === 'video');
  const watchers = [
    cdp.waitForEvent('Network.requestWillBeSent', ({ request }) => videoDestination(request?.headers), 120000),
    cdp.waitForEvent('Network.requestWillBeSentExtraInfo', ({ headers }) => videoDestination(headers), 120000),
  ];
  for (const watcher of watchers) {
    watcher.then(() => { videoRequest = true; }, error => { watcherError = error; });
  }
  try {
    registration = await cdp.call('Page.addScriptToEvaluateOnNewDocument', { source: `(() => {
      if (window === window.top) window.__fixtureStartupVideoEvidence = new Set();
      const record = kind => {
        try { window.top.__fixtureStartupVideoEvidence.add(kind); } catch {}
      };
      document.addEventListener('loadstart', event => {
        if (event.target instanceof HTMLVideoElement) record('video-load');
      }, true);
      new MutationObserver(records => {
        for (const { addedNodes } of records) for (const node of addedNodes) {
          if (node instanceof HTMLVideoElement || node.querySelector?.('video')) record('video-attachment');
        }
      }).observe(document, { childList: true, subtree: true });
    })()` });
    return await operation(async () => {
      const observed = await cdp.evaluate('[...window.__fixtureStartupVideoEvidence].sort()');
      if (watcherError) throw watcherError;
      if (videoRequest) observed.push('video-request');
      assert.deepEqual(observed, [], 'unconfigured startup must not attach or request video');
      return observed;
    });
  } finally {
    for (const watcher of watchers) watcher.cancel();
    await Promise.all([
      cdp.call('Network.disable'),
      ...(registration ? [cdp.call('Page.removeScriptToEvaluateOnNewDocument', registration)] : []),
    ]);
  }
}

async function check(name, operation) {
  availableChecks.add(name);
  if (onlyChecks && !onlyChecks.has(name)) {
    report.checks.push({ name, skipped: true });
    return null;
  }
  const started = Date.now();
  try {
    const details = await operation();
    report.checks.push({ name, passed: true, elapsedMs: Date.now() - started, details });
    return details;
  } catch (error) {
    report.checks.push({ name, passed: false, elapsedMs: Date.now() - started, error: safeError(error?.stack || error) });
    return null;
  }
}

async function dispatchTab(shiftKey = false) {
  const key = {
    key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 48,
    modifiers: shiftKey ? 8 : 0,
  };
  await cdp.call('Input.dispatchKeyEvent', { ...key, type: 'rawKeyDown' });
  await cdp.call('Input.dispatchKeyEvent', { ...key, type: 'keyUp' });
}

async function dispatchEnter() {
  const key = { key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 36 };
  await cdp.call('Input.dispatchKeyEvent', { ...key, type: 'rawKeyDown' });
  await cdp.call('Input.dispatchKeyEvent', { ...key, type: 'char', text: '\r', unmodifiedText: '\r' });
  await cdp.call('Input.dispatchKeyEvent', { ...key, type: 'keyUp' });
}

// Walk the generated settings panel's Tab boundary from each edge for two full
// rounds per direction, keeping the host-composer probe and focus-visibility
// guarantees of the inline normal-editing walk. Used for the import-error and
// preview-return states, whose containment shares the same dialog scope.
async function walkGeneratedSettingsTabs() {
  const boundaries = [];
  const trace = [];
  let textareaReached = null;
  for (const shiftKey of [false, true]) {
    const boundary = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
      const dialog=doc?.querySelector('[data-agent-skin-settings]');
      const controls=[...dialog.querySelectorAll('button,input,textarea,select,[tabindex]')]
        .filter(item=>item.tabIndex>=0&&!item.disabled&&item.type!=='hidden'
          &&getComputedStyle(item).display!=='none'&&getComputedStyle(item).visibility!=='hidden'
          &&item.getClientRects().length>0);
      const control=controls.at(${shiftKey ? 0 : -1});
      control?.focus();
      return control&&doc.activeElement===control?{count:controls.length,
        edge:control.getAttribute('aria-label')||control.tagName}:false;
    })()`);
    assert.ok(boundary, 'generated settings dialog exposes a focusable control at each Tab boundary');
    boundaries.push({ shiftKey, ...boundary });
    for (let index = 0; index < boundary.count * 2 + 1; index++) {
      await dispatchTab(shiftKey);
      const focus = await cdp.evaluate(`(()=>{
        const input=document.querySelector('.composer textarea')||document.querySelector('textarea');
        const frame=document.querySelector('iframe[aria-label]');
        const selected=frame?.contentDocument?.activeElement;
        const style=selected?frame.contentWindow.getComputedStyle(selected):null;
        return {value:input?.value,hostTextareaFocused:document.activeElement===input,
          hostFrameFocused:document.activeElement===frame,
          parentFocus:document.activeElement?.tagName+'#'+(document.activeElement?.id||''),
          dialogFocus:frame?.contentDocument?.activeElement?.tagName+'#'
            +(frame?.contentDocument?.activeElement?.id||''),
          focusVisible:selected?.matches(':focus-visible'),outlineStyle:style?.outlineStyle,outlineWidth:style?.outlineWidth};
      })()`);
      if (focus.hostFrameFocused && focus.focusVisible) {
        assert.ok(focus.outlineStyle !== 'none' && parseFloat(focus.outlineWidth) >= 3,
          'keyboard focus remains visible in the generated settings payload: ' + JSON.stringify(focus));
      }
      if (!focus.hostFrameFocused && trace.length < 4) trace.push({ shiftKey, index, ...focus });
      if (focus.hostTextareaFocused) {
        textareaReached = { shiftKey, index, parentFocus: focus.parentFocus };
        await cdp.call('Input.insertText', { text: 'focus-leak' });
        break;
      }
    }
    if (textareaReached) break;
  }
  return { boundaries, trace, textareaReached };
}

function settingsFocusHitEvidence(active, dialog, footer, doc, win) {
  const box=active.getBoundingClientRect(),originalPoint={x:box.left+box.width/2,y:box.top+box.height/2};
  const originalTarget=doc.elementFromPoint(originalPoint.x,originalPoint.y);
  const panel=active.matches('section[role="tabpanel"]');
  let point=originalPoint,visibleRect=null;
  if(panel) {
    const bounds=dialog.getBoundingClientRect(),bottom=footer.getBoundingClientRect().top;
    visibleRect={left:Math.max(box.left,bounds.left+dialog.clientLeft,0),top:Math.max(box.top,bounds.top+dialog.clientTop,0),
      right:Math.min(box.right,bounds.left+dialog.clientLeft+dialog.clientWidth,win.innerWidth),
      bottom:Math.min(box.bottom,bounds.top+dialog.clientTop+dialog.clientHeight,win.innerHeight,bottom)};
    point={x:(visibleRect.left+visibleRect.right)/2,y:(visibleRect.top+visibleRect.bottom)/2};
  }
  const nonempty=!visibleRect||(visibleRect.right>visibleRect.left&&visibleRect.bottom>visibleRect.top);
  const target=nonempty?doc.elementFromPoint(point.x,point.y):null;
  return {hit:!!active.getClientRects().length&&nonempty&&(target===active||active.contains(target)),
    scope:panel?'visible-tabpanel':'control-center',originalPoint,originalTarget:originalTarget?.tagName??null,
    point,visibleRect,target:target?.tagName??null,footerTarget:!!target&&footer.contains(target)};
}

function cleanup() {
  if (cleanupPromise) return cleanupPromise;
  cleanupPromise = (async () => {
    const errors = [];
    try { cdp?.close(); } catch (error) { errors.push(error); }
    let stopped = !chrome;
    if (chromeOwner) {
      try { stopped = await chromeOwner.stop(); } catch (error) { errors.push(error); }
    }
    if (server?.listening) {
      try { server.closeAllConnections(); } catch (error) { errors.push(error); }
      try { await new Promise((resolveClose, reject) => server.close(error => error ? reject(error) : resolveClose())); }
      catch (error) { errors.push(error); }
    }
    let removed = false;
    if (profile && canRemoveProfile({ stopped, completed: suiteCompleted, fatalError: report.fatalError,
      checks: report.checks, errors })) {
      try { removed = await removeOwnedProfile(profile, profileOwner); } catch (error) { errors.push(error); }
    }
    report.cleanup = {
      ownChromeStopped: stopped,
      temporaryProfileRemoved: removed,
      profilePath: profile && !removed ? profile : null,
      errors: errors.map(safeError),
      serverClosed: !server?.listening,
    };
    if (!stopped || (profile && !removed) || errors.length) {
      throw new Error('Fixture cleanup incomplete; inspect the retained or partially removed profile: '
        + errors.map(safeError).join('; '));
    }
  })();
  return cleanupPromise;
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => cleanup().finally(() => process.exit(signal === 'SIGINT' ? 130 : 143)));
}

try {
  assert.equal(typeof WebSocket, 'function', 'Use Node 22+ with its built-in WebSocket');
  await access(options.chrome);
  if(measurementOutput)await assertOutputOwner(measurementOutput);
  else await mkdir(options.out, { recursive: true });
  const [preview, wallpaperCSS, wallpaperRenderer, controllerRenderer, codexPageAdapterSource, imageSettingsSource, localizationSource, legacyWallpaperCSS,
    legacyWallpaperRenderer, helperExpressionJSON, generatedPayloadSource] = await Promise.all([
    readFile(join(ROOT, 'wallpaper/preview.html'), 'utf8'),
    readFile(join(ROOT, 'wallpaper/wallpaper.css'), 'utf8'),
    readFile(join(ROOT, 'wallpaper/renderer.js'), 'utf8'),
    readFile(join(ROOT, 'extension/renderer.mjs'), 'utf8'),
    readFile(join(ROOT, 'extension/codex-page-adapter.mjs'), 'utf8'),
    readFile(join(ROOT, 'image-settings.js'), 'utf8'),
    readFile(join(ROOT, 'localization.js'), 'utf8'),
    Promise.resolve('/* synthetic fixture */'),
    readFile(join(ROOT, 'tools/test-synthetic-legacy-wallpaper.mjs'), 'utf8'),
    readFile(join(ROOT, '.build/startup-helper-expressions.json'), 'utf8'),
    options.generatedPayload ? readFile(options.generatedPayload, 'utf8') : Promise.resolve(null),
  ]);
  const generatedPayloadRoute = generatedPayloadSource === null ? null : `(() => {
    const host = globalThis.__agentSkinFixtureHost;
    globalThis.__generatedPayloadResult = (function(window, location, document, globalThis) {
      return ${generatedPayloadSource};
    }).call(host, host, host.location, document, host);
  })();`;
  if (generatedPayloadSource !== null) {
    assert.ok(generatedPayloadRoute.includes(generatedPayloadSource),
      'the app-route realm adapter embeds the unmodified generated payload source');
  }
  const helperExpressions = JSON.parse(helperExpressionJSON);
  assert.deepEqual(Object.keys(helperExpressions).sort(), ['applyGuardSource', 'restoreSource', 'retrySource', 'statusSource']);
  assert.ok(Object.values(helperExpressions).every(value => typeof value === 'string' && value.length > 0));
  const scriptStart = preview.lastIndexOf('<script type="module" src="./preview-controller.js">');
  const scriptEnd = preview.indexOf('</script>', scriptStart) + '</script>'.length;
  assert.ok(scriptStart >= 0 && scriptEnd > scriptStart, 'The local preview fixture has a replaceable module entry');
  const fixtureHTML = preview.slice(0, scriptStart)
    + '<script src="/localization.js"></script><script src="/image-settings.js"></script><script src="/animation.js"></script><script type="module" src="/fixture.js"></script>'
    + preview.slice(scriptEnd);
  const homeNavFixtureMarkup = String.raw`
    <div data-fixture-boxless-ancestor style="display:contents">
    <nav aria-label="Home" role="navigation" data-fixture-home-nav style="display:flex;flex-direction:column;width:100%;height:100%;min-height:0;overflow:hidden">
      <div class="fixture-nav-header" style="flex:none;padding:12px 8px 8px">
        <div class="group/nav-list" data-fixture-nav-list style="display:flex;flex-direction:column;gap:4px;width:100%">
          <button type="button" class="sidebar-item" data-fixture-new-chat style="width:100%;min-height:32px;padding:5px 10px;text-align:left">New chat</button>
          <button type="button" class="sidebar-item" data-fixture-your-dot style="width:100%;min-height:32px;padding:5px 10px;text-align:left"><div>Your dot</div></button>
        </div>
      </div>
      <div class="fixture-nav-scroll" style="flex:1;min-height:0;overflow:auto;padding:4px 8px">
        <section class="group/nav-section">
          <div class="group/nav-section-title">
            <button type="button" class="group/section-toggle" role="button" aria-expanded="true" style="width:100%;text-align:left">
              <span>Pinned</span>
            </button>
          </div>
        </section>
      </div>
      <div class="fixture-nav-footer" data-fixture-nav-footer style="flex:none;display:flex;flex-direction:column;gap:6px;padding:8px;border-top:1px solid var(--line)">
        <button id="fixture-download-update" type="button" style="width:100%;text-align:left">Download update</button>
        <button id="fixture-profile" type="button" style="width:100%;text-align:left">Profile</button>
      </div>
    </nav></div>`;
  const pixelBytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC', 'base64');
  const pixelImage = 'data:image/png;base64,' + pixelBytes.toString('base64');
  const imageSHA256 = createHash('sha256').update(pixelBytes).digest('hex');
  const animationAvatarSVG = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><defs><linearGradient id="a" x2="1" y2="1"><stop stop-color="#f6b36b"/><stop offset="1" stop-color="#d86684"/></linearGradient></defs><rect width="512" height="512" fill="url(#a)"/><circle cx="256" cy="256" r="188" fill="#f7d4ad"/><path d="M91 258Q77 73 252 61Q423 75 422 259L378 192Q317 254 153 207Z" fill="#392d4b"/><ellipse cx="196" cy="265" rx="14" ry="20" fill="#31283d"/><ellipse cx="308" cy="265" rx="14" ry="20" fill="#31283d"/><path d="M206 338Q256 380 306 338" fill="none" stroke="#a54f61" stroke-width="13" stroke-linecap="round"/><path d="M140 466Q256 382 372 466" fill="#e3778d"/></svg>';
  const animationArtworkSVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024"><defs><linearGradient id="b" x2="0" y2="1"><stop stop-color="#d9a7d6"/><stop offset=".58" stop-color="#f4d39e"/><stop offset="1" stop-color="#423c64"/></linearGradient></defs><rect width="1536" height="1024" fill="url(#b)"/><circle cx="1210" cy="190" r="110" fill="#fff0bd"/><path d="M0 700L240 390L452 690L700 300L988 710L1220 420L1536 720V1024H0Z" fill="#837aa5"/><path d="M0 812Q270 690 560 820T1110 800T1536 770V1024H0Z" fill="#514e7d"/><path d="M145 860L420 550L640 860M806 826L1070 504L1358 838" fill="none" stroke="#fff6dd" stroke-width="16"/><g fill="#fff8e8"><circle cx="250" cy="170" r="8"/><circle cx="650" cy="120" r="6"/><circle cx="930" cy="220" r="7"/><circle cx="1400" cy="330" r="8"/></g></svg>';
  const animationContourFixture = [
    [[145, 860], [420, 550], [640, 860]],
    [[806, 826], [1070, 504], [1358, 838]],
    [[0, 700], [240, 390], [452, 690], [700, 300], [988, 710], [1220, 420], [1536, 720]],
  ];
  const fixtureModule = `
    import { installStartup } from '/extension/renderer.mjs';
    import { createCodexPageAdapter } from '/extension/codex-page-adapter.mjs';
    import { installRenderer } from '/wallpaper/renderer.js';
    import { installRenderer as installLegacyWallpaper } from '/legacy/wallpaper/renderer.js';
    const pageAdapter = createCodexPageAdapter(window);
    const outerWindow = window;
    const url = new URL(location.href);
    if (url.searchParams.has('initial-light-theme')) document.documentElement.dataset.theme = 'light';
    if (url.searchParams.has('home-nav-fixture')) {
      const sidebar = document.querySelector('.sidebar');
      const shell = document.querySelector('[data-app-shell-frame]');
      const markup = ${JSON.stringify(homeNavFixtureMarkup)};
      sidebar.style.cssText = 'padding:0;display:flex;flex-direction:column;width:100%;height:100%;min-height:0;overflow:hidden';
      shell.style.gridTemplateColumns = '232px minmax(0,1fr)';
      sidebar.innerHTML = markup;
      outerWindow.__fixtureHomeNavRemountCount = 0;
      outerWindow.__fixturePriorHomeNav = null;
      sidebar.querySelector('nav[aria-label="Home"]')?.setAttribute('data-fixture-nav-instance', '0');
      outerWindow.__fixtureRemountHomeNav = () => {
        const current = document.querySelector('nav[aria-label="Home"][role="navigation"]');
        if (!current) return false;
        const template = document.createElement('template');
        template.innerHTML = markup;
        const next = template.content.firstElementChild;
        outerWindow.__fixturePriorHomeNav = current;
        outerWindow.__fixtureHomeNavRemountCount++;
        next.querySelector('nav').setAttribute('data-fixture-nav-instance', String(outerWindow.__fixtureHomeNavRemountCount));
        current.parentElement.replaceWith(next);
        return true;
      };
      outerWindow.__fixtureSetHomeNavWidth = width => {
        const value = Number(width);
        if (!Number.isInteger(value) || value < 140 || value > 280) return false;
        shell.style.gridTemplateColumns = value + 'px minmax(0,1fr)';
        sidebar.style.flexBasis = value + 'px';
        window.dispatchEvent(new Event('resize'));
        return true;
      };
    }
    const nativeMutationObserver = window.MutationObserver;
    let failFirstWallpaperShellObserver = url.searchParams.has('fail-first-wallpaper-shell-observer');
    const trackedMutationObservers = [];
    const mutationObserverState = new WeakMap();
    window.MutationObserver = class extends nativeMutationObserver {
      constructor(callback) {
        super(callback);
        mutationObserverState.set(this, { active: false, disconnectCalls: 0, kind: 'unclassified' });
        trackedMutationObservers.push(this);
      }
      observe(target, options) {
        const state = mutationObserverState.get(this);
        const attributesOnly = options?.attributes === true && options?.childList !== true;
        const wallpaperShellWait = options?.childList === true && options?.subtree === true
          && options?.attributeFilter?.includes('data-app-shell-frame') && options?.attributeOldValue !== true;
        const workspaceActive = options?.attributeOldValue === true && options?.attributeFilter?.includes('data-app-shell-main-surface');
        state.kind = workspaceActive ? 'workspace-active' : wallpaperShellWait ? 'wallpaper-shell-wait'
          : attributesOnly ? 'appearance-attributes-only' : 'other';
        if (wallpaperShellWait && failFirstWallpaperShellObserver) {
          failFirstWallpaperShellObserver = false;
          state.active = false;
          throw new Error('synthetic first wallpaper shell observer is unavailable');
        }
        state.active = true;
        return super.observe(target, options);
      }
      disconnect() {
        const state = mutationObserverState.get(this);
        state.active = false;
        state.disconnectCalls++;
        return super.disconnect();
      }
    };
    let bodyAvailable = !url.searchParams.has('hold-body');
    const heldShell = url.searchParams.has('hold-shell')
      ? document.querySelector('[data-app-shell-frame]') : null;
    const heldShellFragment = document.createDocumentFragment();
    if (heldShell) heldShellFragment.appendChild(heldShell);
    if (url.searchParams.has('focus-case')) {
      // The wallpaper shell is absent, but the host must have a usable control
      // before the Appearance fallback and its recovery actions are exposed.
      const control = document.createElement('button');
      control.id = 'theme';
      control.textContent = 'Host control';
      control.style.cssText = 'position:fixed;top:20px;left:80px;z-index:1';
      document.getElementById('root').appendChild(control);
    }
    const initialWallpaperStrength = url.searchParams.has('no-initial-wallpaper') ? 0 : 42;
    if (url.searchParams.get('legacy-wash') === 'host-important') {
      document.documentElement.style.setProperty('--azhou-wallpaper-wash', 'host-wash', 'important');
    }
    if (url.searchParams.get('legacy-surface') === 'host-important') {
      document.documentElement.style.setProperty('--azhou-wallpaper-surface', '#fafafa', 'important');
    }
    const hostDocument = {
      get documentElement() { return document.documentElement; },
      get body() { return bodyAvailable ? document.body : undefined; },
      get activeElement() { return document.activeElement; },
      hasFocus: document.hasFocus.bind(document),
      createElement: document.createElement.bind(document),
      addEventListener: document.addEventListener.bind(document),
      removeEventListener: document.removeEventListener.bind(document),
      getElementById: document.getElementById.bind(document),
    };
    let host;
    host = url.searchParams.has('generated-payload')
      ? new Proxy(window, { get(target, name) {
        if (['window', 'self', 'top', 'globalThis'].includes(name)) return host;
        if (name === 'location') return new URL('app://-/index.html?initialRoute=%2F');
        if (name === 'document') return hostDocument;
        const value = Reflect.get(target, name, target);
        return ['addEventListener', 'removeEventListener', 'setTimeout', 'clearTimeout', 'getComputedStyle', 'matchMedia', 'atob', 'createImageBitmap'].includes(name)
          && typeof value === 'function' ? value.bind(target) : value;
      } })
      : {
        location: new URL('app://-/index.html?initialRoute=%2F'), document: hostDocument,
        MutationObserver, addEventListener: window.addEventListener.bind(window),
        removeEventListener: window.removeEventListener.bind(window),
        getComputedStyle: window.getComputedStyle.bind(window),
        matchMedia: window.matchMedia.bind(window),
        setTimeout: window.setTimeout.bind(window), clearTimeout: window.clearTimeout.bind(window),
      };
    if (url.searchParams.has('manual-startup-timeout')) {
      // Expose the actual controller watchdog only in this synthetic host. Keep
      // its production delay and callback; tests advance this one timer boundary.
      const schedule = host.setTimeout;
      host.setTimeout = (callback, milliseconds, ...args) => {
        const timer = schedule(callback, milliseconds, ...args);
        if (milliseconds === 25_000) outerWindow.__fixtureStartupWatchdog = {
          milliseconds,
          fire() { outerWindow.clearTimeout(timer); callback(...args); },
        };
        return timer;
      };
    }
    let generatedInstallResult;
    if (url.searchParams.has('generated-payload')) {
      globalThis.__agentSkinFixtureHost = host;
      outerWindow.__fixtureAssetInvalidErrors = [];
      outerWindow.__fixtureRejectedSettlements = [];
      outerWindow.__fixtureImageOperations = [];
      const nativeAppendChild = Node.prototype.appendChild;
      Node.prototype.appendChild = function (node) {
        const result = nativeAppendChild.call(this, node);
        if (node?.tagName !== 'IFRAME' || !node.hasAttribute('aria-label')) return result;
        const frameWindow = node.contentWindow;
        if (!frameWindow?.HTMLImageElement) return result;
        const originalDecode = frameWindow.HTMLImageElement.prototype.decode;
        if (typeof originalDecode === 'function') {
          frameWindow.HTMLImageElement.prototype.decode = function () {
            const startedAt = performance.now();
            const image = this;
            const operation = { operation: 'image.decode', outcome: 'pending', length: image.src.length,
              complete: image.complete, width: image.naturalWidth, height: image.naturalHeight };
            outerWindow.__fixtureImageOperations.push(operation);
            const pendingTimer = outerWindow.setTimeout(() => {
              if (operation.outcome === 'pending') operation.pendingAtMs = performance.now() - startedAt;
            }, 3500);
            return originalDecode.call(image).then(value => {
              outerWindow.clearTimeout(pendingTimer);
              Object.assign(operation, { outcome: 'resolved', complete: image.complete,
                width: image.naturalWidth, height: image.naturalHeight, elapsedMs: performance.now() - startedAt });
              return value;
            }, error => {
              outerWindow.clearTimeout(pendingTimer);
              Object.assign(operation, { outcome: 'rejected', complete: image.complete,
                width: image.naturalWidth, height: image.naturalHeight,
                error: String(error?.message || error), elapsedMs: performance.now() - startedAt });
              throw error;
            });
          };
        }
        if (typeof frameWindow.createImageBitmap === 'function') {
          const originalBitmap = frameWindow.createImageBitmap.bind(frameWindow);
          frameWindow.createImageBitmap = (...args) => {
            const startedAt = performance.now();
            const operation = { operation: 'createImageBitmap', outcome: 'pending' };
            outerWindow.__fixtureImageOperations.push(operation);
            const pendingTimer = outerWindow.setTimeout(() => {
              if (operation.outcome === 'pending') operation.pendingAtMs = performance.now() - startedAt;
            }, 9500);
            return originalBitmap(...args).then(bitmap => {
              outerWindow.clearTimeout(pendingTimer);
              Object.assign(operation, { outcome: 'resolved', width: bitmap.width, height: bitmap.height,
                elapsedMs: performance.now() - startedAt });
              return bitmap;
            }, error => {
              outerWindow.clearTimeout(pendingTimer);
              Object.assign(operation, { outcome: 'rejected', error: String(error?.message || error),
                elapsedMs: performance.now() - startedAt });
              throw error;
            });
          };
        }
        return result;
      };
      const nativeError = window.Error;
      window.Error = new Proxy(nativeError, { construct(target, args, newTarget) {
        const error = Reflect.construct(target, args, newTarget);
        if (outerWindow.__fixtureAssetInvalidErrors.length < 20) {
          outerWindow.__fixtureAssetInvalidErrors.push({ message: String(args[0] ?? ''), stack: String(error.stack || error) });
        }
        return error;
      } });
      const nativeAllSettled = window.Promise.allSettled.bind(window.Promise);
      window.Promise.allSettled = values => nativeAllSettled(values).then(results => {
        const errors = results.filter(result => result.status === 'rejected').map(result => ({
          name: String(result.reason?.name || ''), message: String(result.reason?.message || result.reason),
          stack: String(result.reason?.stack || ''),
        }));
        if (errors.length) outerWindow.__fixtureRejectedSettlements.push(...errors.slice(0, 20));
        return results;
      });
      const script = document.createElement('script');
      script.src = '/generated-startup.js';
      await new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = () => reject(new Error('builder-generated startup payload failed to load'));
        document.head.appendChild(script);
      });
      generatedInstallResult = globalThis.__generatedPayloadResult;
    }
    const frameSpecs = [];
    const animationRuns = [];
    const senders = new Map();
    const wallpaper = { version: '0.9.0', preview: true, image: ${JSON.stringify(pixelImage)},
      imageSHA256: ${JSON.stringify(imageSHA256)}, css: await fetch('/wallpaper.css').then(response => response.text()), strength: initialWallpaperStrength };
    const legacyWallpaper = { ...wallpaper, version: '0.7.1', css: await fetch('/legacy-wallpaper.css').then(response => response.text()) };
    const fixturePayload = function (frameWindow, frameDocument, _location, _performance, _indexedDB,
      _Image, _Path2D, _URL, requestAnimationFrame, _cancelAnimationFrame, _setTimeout, _clearTimeout,
      _module, SEND, frameSpec) {
      frameSpecs.push({ runId: frameSpec.runId, intent: frameSpec.intent, protocolVersion: frameSpec.protocolVersion,
        appearance: frameSpec.appearance,
        hasWallpaper: frameSpec.assets?.wallpaper === ${JSON.stringify(pixelImage)} });
      senders.set(frameSpec.runId, SEND);
      const overlay = frameDocument.createElement('div');
      overlay.setAttribute('data-startup-fixture-overlay', String(frameSpec.runId));
      overlay.setAttribute('aria-label', 'Synthetic Agent Skin ' + frameSpec.intent);
      overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;background:transparent';
      frameDocument.body.appendChild(overlay);
      if (frameSpec.intent === 'settings') {
        const settingsInput = frameDocument.createElement('input');
        settingsInput.id = 'startup-fixture-settings-input';
        settingsInput.setAttribute('aria-label', 'Synthetic settings input');
        frameDocument.body.appendChild(settingsInput);
      }
      requestAnimationFrame(() => {
        if (!url.searchParams.has('legacy')) {
          SEND({ type: 'azhou-startup', action: 'background', runId: frameSpec.runId,
            image: frameSpec.assets.wallpaper, strength: initialWallpaperStrength });
        }
        SEND({ type: 'azhou-startup', action: 'ready', runId: frameSpec.runId });
      });
      return {
        openSettings() {
          if (frameSpec.intent !== 'play') return false;
          SEND({ type: 'azhou-startup', action: 'settings-open', runId: frameSpec.runId });
          return true;
        },
        dispose() { overlay.remove(); },
      };
    };
    const installActualAnimation = function (...args) {
      const frameSpec = args[14];
      const frameWindow = args[0];
      frameSpecs.push({ runId: frameSpec.runId, intent: frameSpec.intent, protocolVersion: frameSpec.protocolVersion,
        appearance: frameSpec.appearance, hasWallpaper: frameSpec.assets?.wallpaper === ${JSON.stringify(pixelImage)} });
      const contextPrototype = frameWindow.CanvasRenderingContext2D?.prototype;
      if (contextPrototype && !frameWindow.__fixtureAnimationTextDraws) {
        const originalFillText = contextPrototype.fillText;
        Object.defineProperty(frameWindow, '__fixtureAnimationTextDraws', { value: [], configurable: true });
        contextPrototype.fillText = function (text, ...rest) {
          const value = String(text);
          if (['Synthetic agent', 'SYNTHETIC / TEST', 'Generated fixture only'].includes(value)) {
            frameWindow.__fixtureAnimationTextDraws.push(value);
          }
          return originalFillText.call(this, text, ...rest);
        };
      }
      if (url.searchParams.has('hold-identity-bitmap')) {
        const createBitmap = frameWindow.createImageBitmap.bind(frameWindow);
        let requests = 0;
        let releaseHeldBitmap = null;
        frameWindow.createImageBitmap = source => {
          const request = ++requests;
          outerWindow.__fixtureIdentityBitmapRequests = requests;
          return createBitmap(source).then(bitmap => {
            if (request !== 3) return bitmap;
            outerWindow.__fixtureIdentityBitmapPending = true;
            return new Promise(resolve => {
              releaseHeldBitmap = () => resolve(bitmap);
              outerWindow.__releaseFixtureIdentityBitmap = () => {
                if (!releaseHeldBitmap) return false;
                const release = releaseHeldBitmap;
                releaseHeldBitmap = null;
                outerWindow.__fixtureIdentityBitmapPending = false;
                release();
                return true;
              };
            });
          });
        };
      }
      const handle = window.installAnimation(...args);
      const run = { runId: frameSpec.runId, intent: frameSpec.intent,
        settingsCommitted: frameSpec.settingsCommitted === true, appearance: frameSpec.appearance };
      if (url.searchParams.has('natural-settings-replay')) {
        const samplePreviewReport = handle.preview.report;
        run.sampleDisposedResources = () => ({
          sampledAt: outerWindow.performance.now(),
          report: samplePreviewReport(),
        });
        const dispose = handle.dispose;
        handle.dispose = () => {
          return dispose();
        };
      } else {
        run.assets = frameSpec.assets;
        run.handle = handle;
      }
      animationRuns.push(run);
      return handle;
    };
    const payload = url.searchParams.has('animation')
      ? (url.searchParams.has('animation-hold') ? function (...args) {
        const frameWindow = args[0];
        const createBitmap = frameWindow.createImageBitmap.bind(frameWindow);
        frameWindow.__fixtureHeldBitmapRequests = 0;
        frameWindow.__fixtureHeldBitmapReleases = 0;
        frameWindow.createImageBitmap = source => {
          frameWindow.__fixtureHeldBitmapRequests++;
          return createBitmap(source).then(bitmap => new Promise(resolve => {
            outerWindow.setTimeout(() => resolve({
              width: bitmap.width,
              height: bitmap.height,
              close() { frameWindow.__fixtureHeldBitmapReleases++; bitmap.close(); },
            }), 800);
          }));
        };
        outerWindow.__animationPendingFrame = frameWindow;
        return installActualAnimation(...args);
      } : installActualAnimation)
      : fixturePayload;
    if (url.searchParams.has('animation') && typeof payload !== 'function') {
      throw new Error('animation installer is not exposed by the canonical source');
    }
    let animationAvatar = '', animationArtwork = '';
    if (url.searchParams.has('animation')) {
      const normalize = async (svg, width, height) => {
        const image = new Image();
        image.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
        await image.decode();
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        canvas.getContext('2d').drawImage(image, 0, 0, width, height);
        return canvas.toDataURL('image/png');
      };
      animationAvatar = await normalize(${JSON.stringify(animationAvatarSVG)}, 512, 512);
      animationArtwork = await normalize(${JSON.stringify(animationArtworkSVG)}, 1536, 1024);
    }
    payload.assets = Object.freeze(url.searchParams.has('animation')
      ? { wallpaper: ${JSON.stringify(pixelImage)}, wallpaperStrength: initialWallpaperStrength,
          avatar: animationAvatar, artwork: animationArtwork,
          ...(url.searchParams.has('entry-avatar') ? { entryAvatar: ${JSON.stringify(pixelImage)} } : {}),
          contours: ${JSON.stringify(animationContourFixture)}, introTitle: 'Synthetic agent',
          introCaption: 'SYNTHETIC / TEST', artworkSubtitle: 'Generated fixture only' }
      : { wallpaper: ${JSON.stringify(pixelImage)},
          ...(url.searchParams.has('entry-avatar') ? { entryAvatar: ${JSON.stringify(pixelImage)} } : {}) });
    payload.createLocalization = window.createLocalization;
    if (url.searchParams.has('animation')) {
      const createSettings = window.createImageSettings;
      if (url.searchParams.has('settings-open-pending')) {
        payload.createImageSettings = environment => createSettings({ ...environment, indexedDB: {
          open() { outerWindow.__fixtureIDBStage = 'open'; return {}; },
        } });
      } else if (url.searchParams.has('settings-get-pending')) {
        const database = {
          objectStoreNames: { contains: name => name === 'settings' },
          transaction() {
            const transaction = {
              aborted: false,
              objectStore() { return { get() { outerWindow.__fixtureIDBStage = 'get'; return {}; } }; },
              abort() {
                if (transaction.aborted) return;
                transaction.aborted = true;
                outerWindow.__fixtureIDBAbortCount = (outerWindow.__fixtureIDBAbortCount || 0) + 1;
                queueMicrotask(() => transaction.onabort?.({ target: transaction }));
              },
            };
            return transaction;
          },
          close() {},
        };
        payload.createImageSettings = environment => createSettings({ ...environment, indexedDB: {
          open() {
            outerWindow.__fixtureIDBStage = 'open';
            const request = { result: database };
            queueMicrotask(() => request.onsuccess?.({ target: request }));
            return request;
          },
        } });
      } else if (url.searchParams.has('settings-blocked')) {
        payload.createImageSettings = environment => createSettings({ ...environment, indexedDB: {
          open() { const request = {}; queueMicrotask(() => request.onblocked?.({ target: request })); return request; },
        } });
      } else payload.createImageSettings = createSettings;
    }
    let wallpaperApplications = 0;
    payload.applyWallpaper = async (background, isCurrent) => {
      wallpaperApplications++;
      outerWindow.__fixtureWallpaperApplications = wallpaperApplications;
      if (url.searchParams.has('wallpaper-fail') && wallpaperApplications === 1) {
        throw new Error('synthetic wallpaper failure');
      }
      if (url.searchParams.get('wallpaper-hold') === String(wallpaperApplications)) {
        await new Promise(resolve => { outerWindow.__releaseFixtureWallpaper = resolve; });
        if (!isCurrent()) return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
      }
      const state = await installRenderer({ ...wallpaper, image: background.image,
        strength: background.strength, isCurrent });
      const api = window.__azhouWallpaper;
      if (api) Object.defineProperty(host, '__azhouWallpaper', { value: api, configurable: true, writable: true });
      return state;
    };
    const unknownDecoration = document.createElement('div');
    unknownDecoration.id = 'fixture-unknown';
    unknownDecoration.style.cssText = 'position:fixed;right:12px;top:80px;width:18px;height:18px;pointer-events:none;background-image:linear-gradient(red,blue)';
    document.getElementById('root').appendChild(unknownDecoration);
    if (url.searchParams.has('hold-decode') || url.searchParams.has('hold-mask-decode')) {
      const original = HTMLImageElement.prototype.decode;
      const decodeGates = [], pendingGates = new Set();
      HTMLImageElement.prototype.decode = function () {
        if (url.searchParams.has('hold-mask-decode') && !this.src.startsWith('data:image/svg+xml,')) return original.call(this);
        return original.call(this).then(() => new Promise(resolve => {
          const index = decodeGates.length;
          decodeGates.push({ resolve, source: this.src });
          outerWindow.__decodeGateSources = decodeGates.map(gate => gate.source);
          pendingGates.add(index);
          outerWindow.__decodeGateCount = decodeGates.length;
          outerWindow.__decodePending = pendingGates.size > 0;
        }));
      };
      outerWindow.__releaseDecodeAt = index => {
        decodeGates[index]?.resolve();
        pendingGates.delete(index);
        outerWindow.__decodePending = pendingGates.size > 0;
        if (!pendingGates.size) HTMLImageElement.prototype.decode = original;
      };
      outerWindow.__releaseDecode = () => outerWindow.__releaseDecodeAt(0);
      const createURL = URL.createObjectURL.bind(URL), revokeURL = URL.revokeObjectURL.bind(URL), urls = new Set();
      URL.createObjectURL = value => { const result = createURL(value); urls.add(result); outerWindow.__fixtureBlobCount = urls.size; return result; };
      URL.revokeObjectURL = value => { urls.delete(value); outerWindow.__fixtureBlobCount = urls.size; return revokeURL(value); };
    }
    let legacyWallpaperAPI;
    if (url.searchParams.has('legacy')) {
      try {
        await installLegacyWallpaper(legacyWallpaper);
        legacyWallpaperAPI = window.__azhouWallpaper;
        Object.defineProperty(host, '__azhouWallpaper', { value: legacyWallpaperAPI, configurable: true, writable: true });
        outerWindow.__legacyWallpaperAPI = legacyWallpaperAPI;
      } catch (error) { outerWindow.__legacyWallpaperError = String(error?.message || error); }
    }
    const result = url.searchParams.has('legacy-only')
      ? { installed: false, alreadyActive: false, reason: 'fixture-no-controller' }
      : installStartup(payload, host, pageAdapter);
    outerWindow.__fixtureHost = host;
    outerWindow.__startupAPI = host.__azhouStartup;
    outerWindow.__startupInstallResult = generatedInstallResult || result;
    outerWindow.__startupFrameSpecs = frameSpecs;
    outerWindow.__startupAnimationRuns = animationRuns;
    outerWindow.__startupFixtureSend = (runId, message) => senders.get(runId)?.(message);
    outerWindow.__releaseBody = () => {
      bodyAvailable = true;
      const marker = document.createElement('span');
      marker.hidden = true;
      marker.dataset.bodyGate = 'open';
      document.documentElement.appendChild(marker);
      queueMicrotask(() => marker.remove());
    };
    outerWindow.__releaseShell = () => {
      if (heldShellFragment.childNodes.length) document.getElementById('root').appendChild(heldShellFragment);
      return !!document.querySelector('[data-app-shell-frame]');
    };
    outerWindow.__fixtureMutationObserverStats = () => {
      const states = trackedMutationObservers.map(observer => mutationObserverState.get(observer));
      const summarize = kind => {
        const selected = states.filter(state => state.kind === kind);
        return { created: selected.length, active: selected.filter(state => state.active).length,
          disconnectCalls: selected.reduce((total, state) => total + state.disconnectCalls, 0) };
      };
      return { created: states.length, active: states.filter(state => state.active).length,
        disconnectCalls: states.reduce((total, state) => total + state.disconnectCalls, 0),
        wallpaperShellWait: summarize('wallpaper-shell-wait'),
        workspaceActive: summarize('workspace-active'),
        appearanceAttributesOnly: summarize('appearance-attributes-only') };
    };
    outerWindow.__startupSurfaceBefore = (() => {
      const read = selector => { const node = document.querySelector(selector); return node ? getComputedStyle(node).backgroundColor : ''; };
      return { composer: read('.composer'), code: read('pre'), menu: read('[role="menu"]'), unknown: read('#fixture-unknown') };
    })();
  `;
  const routes = new Map([
    ['/fixture.html', ['text/html; charset=utf-8', fixtureHTML]],
    ['/csp-style.html', ['text/html; charset=utf-8', fixtureHTML]],
    ['/csp-blob.html', ['text/html; charset=utf-8', fixtureHTML]],
    ['/csp-theme-data.html', ['text/html; charset=utf-8', fixtureHTML]],
    ['/fixture.js', ['text/javascript; charset=utf-8', fixtureModule]],
    ['/animation.js', ['text/javascript; charset=utf-8', await readFile(join(ROOT, 'animation.js'), 'utf8')]],
    ['/image-settings.js', ['text/javascript; charset=utf-8', imageSettingsSource]],
    ['/localization.js', ['text/javascript; charset=utf-8', localizationSource]],
    ['/wallpaper.css', ['text/css; charset=utf-8', wallpaperCSS]],
    ['/legacy-wallpaper.css', ['text/css; charset=utf-8', legacyWallpaperCSS]],
    ['/wallpaper/renderer.js', ['text/javascript; charset=utf-8', wallpaperRenderer]],
    ['/workspace-renderer.mjs', ['text/javascript; charset=utf-8', `export function createObservedRenderer(host) { return (function(window, location, document, globalThis, Image, setTimeout, clearTimeout) { ${wallpaperRenderer.replace('export async function', 'async function')} return installRenderer; })(host, host.location, host.document, host, host.Image, host.setTimeout.bind(host), host.clearTimeout.bind(host)); }`]],
    ['/wallpaper/apply.js', ['text/javascript; charset=utf-8', await readFile(join(ROOT, 'wallpaper/apply.js'), 'utf8')]],
    ['/extension/bootstrap.mjs', ['text/javascript; charset=utf-8', await readFile(join(ROOT, 'extension/bootstrap.mjs'), 'utf8')]],
    ['/legacy/wallpaper/renderer.js', ['text/javascript; charset=utf-8', legacyWallpaperRenderer]],
    ['/extension/renderer.mjs', ['text/javascript; charset=utf-8', controllerRenderer]],
    ['/extension/codex-page-adapter.mjs', ['text/javascript; charset=utf-8', codexPageAdapterSource]],
    ['/extension/hosts/dsh.mjs', ['text/javascript; charset=utf-8', await readFile(join(ROOT, 'extension/hosts/dsh.mjs'), 'utf8')]],
  ]);
  if (generatedPayloadRoute !== null) {
    routes.set('/generated-startup.js', ['text/javascript; charset=utf-8', generatedPayloadRoute]);
  }
  server = createServer((request, response) => {
    const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
    const route = routes.get(pathname);
    if (!route) { response.writeHead(404); response.end('Unknown fixture route'); return; }
    response.setHeader('Content-Type', route[0]);
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    if (pathname === '/csp-theme-data.html') {
      response.setHeader('Content-Security-Policy',"default-src 'none'; img-src 'self' blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; object-src 'none'");
    } else if (pathname === '/csp-style.html') {
      response.setHeader('Content-Security-Policy', "default-src 'none'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; object-src 'none'");
    } else if (pathname === '/csp-blob.html') {
      response.setHeader('Content-Security-Policy', "default-src 'none'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; object-src 'none'");
    }
    response.end(route[1]);
  });
  await new Promise((resolveListen, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveListen); });
  const origin = 'http://127.0.0.1:' + server.address().port;
  profile = await mkdtemp(join(tmpdir(), 'azhou-startup-browser-'));
  profileOwner = await profileIdentity(profile);
  const animationPreviewDir = join(profile, 'agent-skin-preview');
  const animationDefaultsDir = join(animationPreviewDir, 'assets/defaults');
  await mkdir(animationDefaultsDir, { recursive: true });
  await Promise.all([
    copyFile(join(ROOT, 'index.html'), join(animationPreviewDir, 'index.html')),
    copyFile(join(ROOT, 'style.css'), join(animationPreviewDir, 'style.css')),
    copyFile(join(ROOT, 'animation.js'), join(animationPreviewDir, 'animation.js')),
    copyFile(join(ROOT, 'localization.js'), join(animationPreviewDir, 'localization.js')),
    copyFile(join(ROOT, 'image-settings.js'), join(animationPreviewDir, 'image-settings.js')),
  ]);
  const maximumSubtitle = '和阿舟一起，把复杂问题拆清楚；再整理线索、验证方法、修正错误，把每个想法一步步做成可以复用的真实结果。并分享可复用成果。';
  assert.equal(maximumSubtitle.length, 60, 'the synthetic subtitle fixture reaches the 60 UTF-16 code-unit limit');
  const maximumIntroTitle = '阿舟陪你把复杂问题拆清楚再做吧！';
  const maximumIntroCaption = '帮助你梳理线索、拆解任务、验证假设、记录过程，并把可复用的方法应用到项目中，留下清楚可靠的结果。';
  assert.equal(maximumIntroTitle.length, 16, 'the synthetic intro title fixture reaches the 16 UTF-16 code-unit limit');
  assert.equal(maximumIntroCaption.length, 48, 'the synthetic intro caption fixture reaches the 48 UTF-16 code-unit limit');
  const syntheticDefaults = `
    (() => {
      function png(width, height, paint) {
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        paint(canvas.getContext('2d'));
        return canvas.toDataURL('image/png');
      }
      const avatar = png(512, 512, ctx => {
        const gradient = ctx.createLinearGradient(0, 0, 512, 512);
        gradient.addColorStop(0, '#f5bc82'); gradient.addColorStop(1, '#bf607d');
        ctx.fillStyle = gradient; ctx.fillRect(0, 0, 512, 512);
        ctx.fillStyle = '#342b42'; ctx.beginPath(); ctx.ellipse(256, 242, 178, 194, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#f8d9bd'; ctx.beginPath(); ctx.ellipse(256, 266, 142, 166, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#352d43'; ctx.beginPath(); ctx.ellipse(207, 258, 10, 17, 0, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.ellipse(305, 258, 10, 17, 0, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#a54f61'; ctx.lineWidth = 10; ctx.lineCap = 'round'; ctx.beginPath(); ctx.arc(256, 313, 39, .3, Math.PI - .3); ctx.stroke();
        ctx.fillStyle = '#e3778d'; ctx.beginPath(); ctx.ellipse(256, 468, 142, 58, 0, Math.PI, 0); ctx.fill();
      });
      const artwork = png(1536, 1024, ctx => {
        const gradient = ctx.createLinearGradient(0, 0, 0, 1024);
        gradient.addColorStop(0, '#d9a7d6'); gradient.addColorStop(.58, '#f4d39e'); gradient.addColorStop(1, '#423c64');
        ctx.fillStyle = gradient; ctx.fillRect(0, 0, 1536, 1024);
        ctx.fillStyle = '#fff0bd'; ctx.beginPath(); ctx.arc(1210, 190, 110, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#837aa5'; ctx.beginPath(); ctx.moveTo(0, 700); ctx.lineTo(240, 390); ctx.lineTo(452, 690); ctx.lineTo(700, 300); ctx.lineTo(988, 710); ctx.lineTo(1220, 420); ctx.lineTo(1536, 720); ctx.lineTo(1536, 1024); ctx.lineTo(0, 1024); ctx.fill();
        ctx.fillStyle = '#514e7d'; ctx.beginPath(); ctx.moveTo(0, 812); ctx.quadraticCurveTo(270, 690, 560, 820); ctx.quadraticCurveTo(830, 930, 1110, 800); ctx.quadraticCurveTo(1320, 720, 1536, 770); ctx.lineTo(1536, 1024); ctx.lineTo(0, 1024); ctx.fill();
        ctx.strokeStyle = '#fff6dd'; ctx.lineWidth = 16; ctx.beginPath(); ctx.moveTo(145, 860); ctx.lineTo(420, 550); ctx.lineTo(640, 860); ctx.moveTo(806, 826); ctx.lineTo(1070, 504); ctx.lineTo(1358, 838); ctx.stroke();
        ctx.fillStyle = '#fff8e8'; for (const [x, y, r] of [[250, 170, 8], [650, 120, 6], [930, 220, 7], [1400, 330, 8]]) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
      });
      window.AGENT_SKIN_ASSETS = {
        avatar, artwork,
        contours: [
          [[145, 860], [420, 550], [640, 860]],
          [[806, 826], [1070, 504], [1358, 838]],
          [[0, 700], [240, 390], [452, 690], [700, 300], [988, 710], [1220, 420], [1536, 720]],
          [[0, 812], [270, 690], [560, 820], [830, 930], [1110, 800], [1320, 720], [1536, 770]],
        ],
        introTitle: 'Synthetic agent', introCaption: 'SYNTHETIC / TEST', artworkSubtitle: ${JSON.stringify(maximumSubtitle)},
      };
    })();
  `;
  await writeFile(join(animationDefaultsDir, 'contours.js'), syntheticDefaults, 'utf8');
  const identityVariants = [
    { name: 'english', title: 'Synthetic agent', caption: 'SYNTHETIC / TEST' },
    { name: 'maximum-chinese', title: maximumIntroTitle, caption: maximumIntroCaption },
    { name: 'empty', title: '', caption: '' },
  ];
  for (const variant of identityVariants) {
    const variantDir = join(profile, 'agent-skin-preview-identity-' + variant.name);
    const variantDefaultsDir = join(variantDir, 'assets/defaults');
    await mkdir(variantDefaultsDir, { recursive: true });
    await Promise.all([
      copyFile(join(ROOT, 'index.html'), join(variantDir, 'index.html')),
      copyFile(join(ROOT, 'style.css'), join(variantDir, 'style.css')),
      copyFile(join(ROOT, 'animation.js'), join(variantDir, 'animation.js')),
      copyFile(join(ROOT, 'localization.js'), join(variantDir, 'localization.js')),
      copyFile(join(ROOT, 'image-settings.js'), join(variantDir, 'image-settings.js')),
    ]);
    const identityDefaults = syntheticDefaults.replace(
      "introTitle: 'Synthetic agent', introCaption: 'SYNTHETIC / TEST'",
      'introTitle: ' + JSON.stringify(variant.title) + ', introCaption: ' + JSON.stringify(variant.caption),
    );
    assert.notEqual(identityDefaults, syntheticDefaults);
    await writeFile(join(variantDefaultsDir, 'contours.js'), identityDefaults, 'utf8');
    variant.dir = variantDir;
  }
  const upperPreviewDir = join(profile, 'agent-skin-preview-upper');
  const upperDefaultsDir = join(upperPreviewDir, 'assets/defaults');
  await mkdir(upperDefaultsDir, { recursive: true });
  await Promise.all([
    copyFile(join(ROOT, 'index.html'), join(upperPreviewDir, 'index.html')),
    copyFile(join(ROOT, 'style.css'), join(upperPreviewDir, 'style.css')),
    copyFile(join(ROOT, 'animation.js'), join(upperPreviewDir, 'animation.js')),
    copyFile(join(ROOT, 'localization.js'), join(upperPreviewDir, 'localization.js')),
    copyFile(join(ROOT, 'image-settings.js'), join(upperPreviewDir, 'image-settings.js')),
  ]);
  const upperDefaults = `
    (() => {
      function png(width, height, seed) {
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        const context = canvas.getContext('2d'); const image = context.createImageData(width, height);
        let value = seed >>> 0;
        for (let offset = 0; offset < image.data.length; offset += 4) {
          value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
          image.data[offset] = value >>> 24;
          value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
          image.data[offset + 1] = value >>> 24;
          value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
          image.data[offset + 2] = value >>> 24;
          image.data[offset + 3] = 255;
        }
        context.putImageData(image, 0, 0);
        return canvas.toDataURL('image/png');
      }
      const contours = [];
      for (let pathIndex = 0; pathIndex < 1200; pathIndex++) {
        const points = [];
        for (let pointIndex = 0; pointIndex < 250; pointIndex++) {
          points.push([
            (pathIndex * 73 + pointIndex * 17 + 13) % 1537,
            (pathIndex * 41 + pointIndex * 29 + 7) % 1025,
          ]);
        }
        contours.push(points);
      }
      window.AGENT_SKIN_ASSETS = {
        avatar: png(512, 512, 0x31840c0f), artwork: png(1536, 1024, 0x5eed1234), contours,
        introTitle: 'Synthetic upper-bound agent', introCaption: 'SYNTHETIC / RESOURCE TEST',
        artworkSubtitle: ${JSON.stringify(maximumSubtitle)},
      };
    })();
  `;
  await writeFile(join(upperDefaultsDir, 'contours.js'), upperDefaults, 'utf8');
  chrome = spawn(options.chrome, [
    '--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
    '--disable-default-apps', '--disable-sync', '--disable-extensions', '--disable-component-update', '--no-pings',
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', '--user-data-dir=' + profile,
    '--window-size=1512,889', 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  chromeOwner = trackOwnedChild(chrome);
  chrome.on('error', error => { chromeError = safeError(error); });
  chrome.stderr.on('data', chunk => { chromeError = (chromeError + chunk.toString()).slice(-4000); });
  const debugPort = await until(async () => {
    if (chrome.exitCode !== null || chrome.signalCode !== null) throw new Error('Own Chrome exited: ' + chromeError);
    const file = await readFile(join(profile, 'DevToolsActivePort'), 'utf8');
    const port = Number(file.split('\n')[0]);
    assert.ok(port > 0 && port < 65536);
    return port;
  }, 15000, 'isolated Chrome DevToolsActivePort');
  const endpoint = 'http://127.0.0.1:' + debugPort;
  const fetchJSON = async path => {
    const response = await fetch(endpoint + path, { signal: AbortSignal.timeout(2000) });
    assert.ok(response.ok);
    return response.json();
  };
  const browser = await fetchJSON('/json/version');
  const page = await until(async () => (await fetchJSON('/json/list')).find(target => target.type === 'page' && target.url === 'about:blank'), 5000, 'isolated blank page');
  cdp = await CDP.open(page.webSocketDebuggerUrl, debugPort);
  await cdp.call('Page.enable');
  await cdp.call('Runtime.enable');
  report.environment = {
    node: process.version,
    platform: process.platform,
    chromeExecutable: options.chrome,
    chromePID: chrome.pid,
    browser: browser.Browser,
    protocolVersion: browser['Protocol-Version'],
    isolatedTemporaryProfile: true,
    debugPortPolicy: 'port 0 was used only by this disposable fixture; this is not a claim about the official app',
  };

  async function navigate(path) {
    await navigateWithLoad(cdp, origin + path);
    const expectedURL = origin + path;
    await until(() => cdp.evaluate(`document.readyState === 'complete' && location.href === ${JSON.stringify(expectedURL)}`),
      10000, 'synthetic host page load');
    await until(() => cdp.evaluate('window.__startupInstallResult !== undefined'), 10000, 'real PageController install');
  }
  async function navigateFreshRecoveryFixture(path) {
    await navigateWithLoad(cdp, 'about:blank');
    await cdp.call('Storage.clearDataForOrigin', { origin, storageTypes: 'indexeddb' });
    await navigate(path);
  }
  async function awaitGeneratedReady(label) {
    try {
      const outcome = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready?state
          :state?.phase==='failed'?{__startupFailed:true,state}:false;
      })()`), 20000, label);
      if (outcome?.__startupFailed) {
        throw new Error('generated startup failed before ready: ' + JSON.stringify(outcome.state));
      }
      return outcome;
    } catch (error) {
      const state = await cdp.evaluate(`(async()=>{
        const controller=window.__startupAPI?.status();
        const frame=document.querySelector('iframe[aria-label]');
        let settingsRecord=null;
        try {
          const databases=await indexedDB.databases();
          if(databases.some(database=>database.name==='azhou-codex-startup')) {
            const db=await new Promise((resolve,reject)=>{
              const request=indexedDB.open('azhou-codex-startup');
              request.onsuccess=()=>resolve(request.result);
              request.onerror=()=>reject(request.error);
            });
            settingsRecord=await new Promise((resolve,reject)=>{
              const request=db.transaction('settings','readonly').objectStore('settings').get('images');
              request.onsuccess=()=>resolve(request.result?{
                schemaVersion:request.result.schemaVersion,
                avatarLength:typeof request.result.avatar==='string'?request.result.avatar.length:null,
                artworkLength:typeof request.result.artwork==='string'?request.result.artwork.length:null,
                contourPaths:Array.isArray(request.result.contours)?request.result.contours.length:null,
                contourPoints:Array.isArray(request.result.contours)?request.result.contours.reduce((sum,path)=>sum+(Array.isArray(path)?path.length:0),0):null,
              }:null);
              request.onerror=()=>reject(request.error);
            });
            db.close();
          }
        } catch (error) { settingsRecord={readError:String(error?.message||error)}; }
        return {url:location.href,phase:controller?.phase,reason:controller?.reason,settingsRecord,
          assetErrors:window.__fixtureAssetInvalidErrors.map(error=>error.message),
          rejectedSettlements:window.__fixtureRejectedSettlements.map(({name,message,stack})=>({name,message,
            stack:stack.split(String.fromCharCode(10)).slice(0,2).join(' | ')})),
          imageOperations:window.__fixtureImageOperations};
      })()`);
      throw new Error(error.message + '; generated fixture state=' + JSON.stringify(state));
    }
  }
  async function animationPixelEvidence() {
    return cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const run=window.__startupAnimationRuns?.at(-1);
      const animationDocument=frame?.contentDocument||document;
      const canvas=animationDocument.querySelector('canvas[data-agent-skin-canvas]');
      const report=run?.handle?.preview?.report?.()||window.launcherUI?.report?.();
      if(!canvas||!report)return false;
      const context=canvas.getContext('2d'),image=context.getImageData(0,0,canvas.width,canvas.height),data=image.data;
      const viewport=report.viewport,scale=Math.max(viewport.width/1536,viewport.height/1024);
      const offsetX=(viewport.width-1536*scale)/2,offsetY=(viewport.height-1024*scale)/2;
      const ratioX=canvas.width/viewport.width,ratioY=canvas.height/viewport.height;
      const pixelAt=(x,y)=>{
        const px=Math.max(0,Math.min(canvas.width-1,Math.floor((x*scale+offsetX)*ratioX)));
        const py=Math.max(0,Math.min(canvas.height-1,Math.floor((y*scale+offsetY)*ratioY)));
        const index=(py*canvas.width+px)*4;
        return [data[index],data[index+1],data[index+2],data[index+3]];
      };
      const identity={dark:0,light:0};
      for(let y=680;y<870;y+=3)for(let x=180;x<1356;x+=3){
        const [r,g,b,a]=pixelAt(x,y),luma=.2126*r+.7152*g+.0722*b;
        if(a>200&&luma<110)identity.dark++;
        if(a>200&&luma>215)identity.light++;
      }
      const segments=[
        [[145,860],[420,550]],[[420,550],[640,860]],
        [[806,826],[1070,504]],[[1070,504],[1358,838]],
        [[0,700],[240,390]],[[240,390],[452,690]],[[452,690],[700,300]],
        [[700,300],[988,710]],[[988,710],[1220,420]],[[1220,420],[1536,720]],
      ];
      const line={dark:0,light:0},seen=new Set();
      for(const [[x1,y1],[x2,y2]] of segments){
        const dx=x2-x1,dy=y2-y1,length=Math.hypot(dx,dy),steps=Math.ceil(length/3);
        const nx=-dy/length,ny=dx/length;
        for(let step=2;step<steps-2;step++){
          const t=step/steps,x=x1+dx*t,y=y1+dy*t;
          for(const offset of [-1,0,1]){
            const [r,g,b,a]=pixelAt(x+nx*offset,y+ny*offset),luma=.2126*r+.7152*g+.0722*b;
            const key=[Math.round((x+nx*offset)*scale),Math.round((y+ny*offset)*scale)].join(':');
            if(seen.has(key))continue;
            seen.add(key);
            if(a>200&&luma<160)line.dark++;
            if(a>200&&luma>170)line.light++;
          }
        }
      }
      return {stage:report.stage,elapsed:report.elapsed,sceneRenderCount:report.jsFrame.sceneRenderCount,
        surface:pixelAt(8,8),identity,line,resources:report.resources};
    })()`);
  }
  async function evaluateNativeHelper(name, { startup = 'actual', wallpaper = 'actual' } = {}) {
    const source = helperExpressions[name];
    assert.equal(typeof source, 'string', 'native helper expression is emitted by the compiled Swift test target');
    const binding = (kind, name) => {
      if (kind === 'none') return 'undefined';
      if (kind === 'unknown') return "({ owner: 'fixture-unknown-owner' })";
      if (kind === 'failed' && name === 'startup') return `({owner:'azhou-codex-startup',version:1,
        status:()=>({owner:'azhou-codex-startup',version:1,phase:'complete',runId:1,ready:true,
          completed:true,overlay:false,completion:null,
          wallpaper:{applied:false,failureCode:'image-decode-failed'}})})`;
      if (kind !== 'actual') throw new Error('Unknown native helper binding: ' + kind);
      return name === 'startup'
        ? 'actualWindow.__fixtureHost?.__azhouStartup'
        : '(actualWindow.__azhouWallpaper || actualWindow.__fixtureHost?.__azhouWallpaper)';
    };
    const expression = `(()=>{
      const actualWindow=document.defaultView;
      const window={};window.top=window;
      const location=new URL('app://-/index.html?initialRoute=%2F');
      const globalThis={};
      const startup=${binding(startup, 'startup')};
      const wallpaper=${binding(wallpaper, 'wallpaper')};
      if(startup!==undefined)Object.defineProperty(globalThis,'__azhouStartup',{value:startup,configurable:true});
      if(wallpaper!==undefined)Object.defineProperty(globalThis,'__azhouWallpaper',{value:wallpaper,configurable:true});
      return (${source});
    })()`;
    return cdp.evaluate(expression);
  }
  async function screenshot(name) {
    await cdp.call('Page.bringToFront');
    await cdp.evaluate('new Promise(resolve => { let settled = false; const settle = () => { if (settled) return; settled = true; resolve(); }; requestAnimationFrame(() => requestAnimationFrame(settle)); setTimeout(settle, 300); })');
    const viewport = await cdp.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,theme:document.documentElement.dataset.theme})');
    const result = await cdp.call('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
    const bytes = Buffer.from(result.data, 'base64');
    assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    const pixels = { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
    await writeFile(join(options.out, name), bytes);
    const detail = { file: name, ...viewport, pixels };
    report.screenshots.push(detail);
    return detail;
  }
  async function appearanceEntryMetrics() {
    return cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const shadow=entry?.shadowRoot,button=shadow?.querySelector('button');
      if(!entry||!button)return null;
      const rect=button.getBoundingClientRect(),x=rect.left+rect.width/2,y=rect.top+rect.height/2;
      const target=document.elementFromPoint(x,y),shadowTarget=shadow.elementFromPoint?.(x,y);
      const avatar=button.querySelector('img'),avatarStyle=avatar&&getComputedStyle(avatar);
      const nameLabel=button.querySelector('span'),nameStyle=nameLabel&&getComputedStyle(nameLabel);
      const input=document.querySelector('textarea'),menu=document.querySelector('[role="menu"]');
      const inputRect=input?.getBoundingClientRect(),menuRect=menu?.getBoundingClientRect();
      const rectData=value=>value&&({x:value.x,y:value.y,width:value.width,height:value.height});
      const overlap=value=>{
        if(!value)return null;
        const left=Math.max(rect.left,value.left),top=Math.max(rect.top,value.top);
        const right=Math.min(rect.right,value.right),bottom=Math.min(rect.bottom,value.bottom);
        const width=Math.max(0,right-left),height=Math.max(0,bottom-top);
        const point=width&&height?{x:left+width/2,y:top+height/2}:null;
        const pageTarget=point&&document.elementFromPoint(point.x,point.y);
        const buttonTarget=point&&shadow.elementFromPoint?.(point.x,point.y);
        return {x:left,y:top,width,height,area:width*height,
          coveredByEntry:pageTarget===entry,coveredByButton:buttonTarget===button,
          hit:pageTarget?.tagName?.toLowerCase()||null};
      };
      const inputTarget=inputRect&&document.elementFromPoint(inputRect.left+Math.min(8,inputRect.width/2),
        inputRect.top+Math.min(8,inputRect.height/2));
      const menuTarget=menuRect&&document.elementFromPoint(menuRect.left+menuRect.width/2,menuRect.top+menuRect.height/2);
      const composer=document.querySelector('.composer'),sidebar=document.querySelector('.sidebar');
      const composerLabel=composer?.querySelector('footer span'),sendButton=composer?.querySelector('footer button');
      const entryStyle=getComputedStyle(entry),buttonStyle=getComputedStyle(button);
      return {display:entryStyle.display,position:entryStyle.position,left:entryStyle.left,bottom:entryStyle.bottom,
        buttonPosition:buttonStyle.position,padding:buttonStyle.padding,rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
        buttonText:button.textContent,buttonAriaLabel:button.getAttribute('aria-label'),
        avatar:avatar?{width:avatar.getBoundingClientRect().width,height:avatar.getBoundingClientRect().height,
          display:avatarStyle.display,borderRadius:avatarStyle.borderRadius,objectFit:avatarStyle.objectFit}:null,
        nameLabel:nameLabel?{text:nameLabel.textContent,fontSize:nameStyle.fontSize,lineHeight:nameStyle.lineHeight}:null,
        entryHit:target===entry,buttonHit:!!button&&(shadowTarget===button||button.contains(shadowTarget)),documentFocus:document.activeElement===entry,
        shadowFocus:shadow.activeElement===button,
        viewport:{width:innerWidth,height:innerHeight},
        sidebarRect:rectData(sidebar?.getBoundingClientRect()),composerRect:rectData(composer?.getBoundingClientRect()),
        inputRect:rectData(inputRect),inputOverlap:overlap(inputRect),composerOverlap:overlap(composer?.getBoundingClientRect()),
        composerLabelRect:rectData(composerLabel?.getBoundingClientRect()),composerLabelOverlap:overlap(composerLabel?.getBoundingClientRect()),
        sendButtonRect:rectData(sendButton?.getBoundingClientRect()),sendButtonOverlap:overlap(sendButton?.getBoundingClientRect()),
        inputHit:!!input&&(inputTarget===input||input.contains(inputTarget)),
        menuRect:rectData(menuRect),menuOverlap:overlap(menuRect),
        menuHit:!!menu&&(menuTarget===menu||menu.contains(menuTarget))};
    })()`);
  }
  async function waitForAppearanceEntry(label) {
    return until(async () => {
      const entry = await appearanceEntryMetrics();
      return entry?.display === 'block' && entry.buttonHit ? entry : false;
    }, 5000, label);
  }
  async function clickAppearanceEntry() {
    const point = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const button=entry?.shadowRoot?.querySelector('button');
      if(!button)return false;
      const rect=button.getBoundingClientRect();
      const x=rect.left+rect.width/2,y=rect.top+rect.height/2,hit=document.elementFromPoint(x,y);
      return {x,y,rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},hit:{tag:hit?.tagName,id:hit?.id,entry:hit===entry},buttonHit:entry.shadowRoot.elementFromPoint(x,y)===button};
    })()`);
    if (!point) return false;
    await cdp.call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x, y: point.y });
    await cdp.call('Input.dispatchMouseEvent', { type: 'mousePressed', x: point.x, y: point.y, button: 'left', clickCount: 1 });
    const focused = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const button=entry?.shadowRoot?.querySelector('button');
      return !!button&&document.activeElement===entry&&entry.shadowRoot.activeElement===button;
    })()`);
    await cdp.call('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x, y: point.y, button: 'left', clickCount: 1 });
    return { focused, point, after: await cdp.evaluate(`(()=>{const e=document.querySelector('[data-agent-skin-entry="appearance"]'),b=e?.shadowRoot?.querySelector('button'),r=b?.getBoundingClientRect();return {active:document.activeElement?.tagName,activeID:document.activeElement?.id,rect:r?{x:r.x,y:r.y,width:r.width,height:r.height}:null};})()`), state: await cdp.evaluate('window.__startupAPI.status()') };
  }

  const initialLightCheck = 'initial light appearance draws readable identity and cached path pixels from theme-only host state';
  if (!onlyChecks || onlyChecks.has(initialLightCheck)) {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&initial-light-theme=1');
  }
  await check(initialLightCheck, async () => {
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status(),frame=document.querySelector('iframe[aria-label]');
      const spec=window.__startupFrameSpecs?.at(-1),run=window.__startupAnimationRuns?.at(-1);
      return state?.phase==='playing'&&state.ready&&frame&&run?.handle?.preview?.report?.()
        ?{theme:spec.appearance.theme,colors:spec.appearance.colors,phase:state.phase}:false;
    })()`), 15000, 'theme-only light host and actual animation are ready');
    assert.equal(ready.theme, 'light');
    assert.equal(ready.colors.text, undefined, 'the synthetic host supplies no explicit text color token');
    assert.equal(ready.colors.muted, undefined, 'the synthetic host supplies no explicit muted color token');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.pause()');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(2.2)');
    const identity = await animationPixelEvidence();
    assert.equal(identity.stage, 'identity');
    assert.ok(identity.surface[0] > 220 && identity.surface[1] > 220,
      'theme-only light appearance keeps the rendered canvas surface light: ' + JSON.stringify(identity.surface));
    assert.ok(identity.identity.dark > 40,
      'the initial light identity title and caption contain dark rendered pixels: ' + JSON.stringify(identity.identity));
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(7.25)');
    const line = await animationPixelEvidence();
    assert.equal(line.stage, 'colorize');
    assert.ok(line.line.dark > 10,
      'the cached contour strokes use a dark color on the initial light host: ' + JSON.stringify(line.line));
    return { hostAppearance: ready, identity: { surface: identity.surface, pixels: identity.identity },
      colorize: { surface: line.surface, contourPixels: line.line } };
  });

  const darkToLightCheck = 'live dark-to-light host changes redraw identity and cached contour pixels';
  if (!onlyChecks || onlyChecks.has(darkToLightCheck)) {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  }
  await check(darkToLightCheck, async () => {
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status(),run=window.__startupAnimationRuns?.at(-1);
      return state?.phase==='playing'&&state.ready&&run?.handle?.preview?.report?.()?state:false;
    })()`), 15000, 'dark host animation is ready before changing appearance');
    await cdp.evaluate(`(()=>{
      const preview=window.__startupAnimationRuns.at(-1).handle.preview;
      preview.pause();preview.seek(2.2);
    })()`);
    const darkIdentity = await animationPixelEvidence();
    assert.equal(darkIdentity.stage, 'identity');
    assert.ok(darkIdentity.surface[0] < 100 && darkIdentity.identity.light > 40,
      'the dark identity frame has a dark surface and visible light title/caption: ' + JSON.stringify(darkIdentity));

    await cdp.evaluate(`(()=>{
      const root=document.documentElement;
      root.lang='en';root.dataset.theme='light';
      root.style.setProperty('--color-text','#202123');
      root.style.setProperty('--color-text-secondary','#65666c');
      root.style.setProperty('--color-border','#dedee3');
    })()`);
    const updated = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),root=document.documentElement;
      return root.lang==='en'&&root.dataset.theme==='light'&&frame?.title==='Azhou startup animation'
        ?{locale:root.lang,theme:root.dataset.theme,title:frame.title}:false;
    })()`), 3000, 'host appearance observer applies English light settings');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(2.2)');
    const lightIdentity = await animationPixelEvidence();
    assert.equal(lightIdentity.stage, 'identity');
    assert.ok(lightIdentity.surface[0] > 220 && lightIdentity.identity.dark > 40,
      'identity title and caption redraw in dark ink on the light host: ' + JSON.stringify(lightIdentity));
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(7.25)');
    const lightLine = await animationPixelEvidence();
    assert.equal(lightLine.stage, 'colorize');
    assert.ok(lightLine.line.dark > 10,
      'cached contour strokes are rebuilt with dark ink after the host theme change: ' + JSON.stringify(lightLine.line));
    return { runId: ready.runId, updated, dark: { surface: darkIdentity.surface, identity: darkIdentity.identity },
      light: { identity: { surface: lightIdentity.surface, pixels: lightIdentity.identity },
        colorize: { surface: lightLine.surface, contourPixels: lightLine.line } } };
  });

  const darkToLightMissingTextCheck = 'dark-to-light appearance resets missing text token to the light fallback';
  if (!onlyChecks || onlyChecks.has(darkToLightMissingTextCheck)) {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  }
  await check(darkToLightMissingTextCheck, async () => {
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status(),frame=document.querySelector('iframe[aria-label]');
      return state?.phase==='playing'&&state.ready&&frame?.contentDocument?.documentElement
        ?{theme:frame.contentDocument.documentElement.dataset.theme,runId:state.runId}:false;
    })()`), 15000, 'dark animation is ready before the missing-token theme change');
    assert.equal(ready.theme, 'dark');
    await cdp.evaluate(`(()=>{
      const preview=window.__startupAnimationRuns.at(-1).handle.preview;
      preview.pause();preview.seek(2.2);
    })()`);
    const darkIdentity = await animationPixelEvidence();
    assert.ok(darkIdentity.identity.light > 40,
      'the dark-theme identity starts with its readable light fallback: ' + JSON.stringify(darkIdentity.identity));

    await cdp.evaluate(`(()=>{
      const root=document.documentElement;
      root.dataset.theme='light';
      root.style.setProperty('--color-surface','#ffffff');
      for(const token of ['--color-text','--color-text-primary','--app-color-text-foreground',
        '--color-text-secondary','--app-color-text-foreground-secondary','--color-border','--app-color-border']) {
        root.style.removeProperty(token);
      }
    })()`);
    await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      return frame?.contentDocument?.documentElement?.dataset.theme==='light';
    })()`), 3000, 'the active animation receives the light theme without text tokens');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(2.2)');
    const lightIdentity = await animationPixelEvidence();
    assert.ok(lightIdentity.surface[0] > 220 && lightIdentity.surface[1] > 220,
      'the appearance surface follows the light theme: ' + JSON.stringify(lightIdentity.surface));
    assert.ok(lightIdentity.identity.dark > 40,
      'missing text tokens use the complete light fallback after a dark-to-light change: '
        + JSON.stringify(lightIdentity.identity));
    return { ready, dark: darkIdentity.identity, light: { surface: lightIdentity.surface,
      identity: lightIdentity.identity } };
  });

  const delayedAppearanceCheck = 'appearance update during identity bitmap preparation redraws identity and cached contours';
  if (!onlyChecks || onlyChecks.has(delayedAppearanceCheck)) {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&hold-identity-bitmap=1');
  }
  await check(delayedAppearanceCheck, async () => {
    const pending = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return window.__fixtureIdentityBitmapPending
        ?{state,requests:window.__fixtureIdentityBitmapRequests}:false;
    })()`), 15000, 'the third createImageBitmap request for identity is held during preparation');
    assert.equal(pending.requests, 3, 'the first two image bitmaps complete and only identity remains pending');
    assert.equal(pending.state.phase, 'loading');
    assert.equal(pending.state.ready, false);
    await cdp.evaluate(`(()=>{
      const root=document.documentElement;
      root.lang='en';root.dataset.theme='light';
      root.style.setProperty('--color-text','#202123');
      root.style.setProperty('--color-text-secondary','#65666c');
      root.style.setProperty('--color-border','#dedee3');
    })()`);
    const updated = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),root=document.documentElement;
      return root.lang==='en'&&root.dataset.theme==='light'&&frame?.title==='Azhou startup animation'
        ?{locale:root.lang,theme:root.dataset.theme,title:frame.title}:false;
    })()`), 3000, 'host appearance changes while the identity bitmap is pending');
    assert.equal(await cdp.evaluate('window.__releaseFixtureIdentityBitmap()'), true,
      'the delayed identity bitmap can be released after the host appearance update');
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'preparation retries with the latest host appearance');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.pause()');
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(2.2)');
    const identity = await animationPixelEvidence();
    assert.equal(identity.stage, 'identity');
    assert.ok(identity.surface[0] > 220 && identity.identity.dark > 40,
      'the retried identity bitmap uses the latest light text colors: ' + JSON.stringify(identity));
    await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.seek(7.25)');
    const line = await animationPixelEvidence();
    assert.equal(line.stage, 'colorize');
    assert.ok(line.line.dark > 10,
      'the cached contour canvas uses the latest light text color: ' + JSON.stringify(line.line));
    return { heldRequest: pending.requests, updated, ready: { runId: ready.runId, locale: ready.locale, theme: ready.theme },
      identity: { surface: identity.surface, pixels: identity.identity }, colorize: { surface: line.surface, contourPixels: line.line } };
  });

  await navigate('/fixture.html');
  const normalReady = await until(() => cdp.evaluate(`(()=>{
    const state=window.__startupAPI?.status();
    return state?.phase==='playing' && state.ready && state.wallpaper?.applied ? state : false;
  })()`), 15000, 'ready page and verified static wallpaper');
  await check('real controller and wallpaper renderer apply one decoded scene with a valid CSS sentinel', async () => {
    const state = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(state.owner, 'azhou-codex-startup');
    assert.equal(state.version, 1);
    assert.equal(state.phase, 'playing');
    assert.equal(state.wallpaper.imageDecoded, true);
    assert.equal(state.wallpaper.backgroundMatched, true);
    assert.equal(state.wallpaper.coverMatched, true);
    assert.equal(state.wallpaper.washMatched, true);
    assert.equal(state.wallpaper.unsupportedDecorations.length, 0);
    const details = await cdp.evaluate(`(()=>{
      const read=selector=>{const node=document.querySelector(selector);return node?getComputedStyle(node).backgroundColor:'';};
      const frame=document.querySelector('iframe[aria-label]');
      const unknown=document.querySelector('#fixture-unknown');
      return {frameCount:document.querySelectorAll('iframe[aria-label]').length,
        frameEvalCount:0,styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        unknownBefore:window.__startupSurfaceBefore.unknown,unknownAfter:getComputedStyle(unknown).backgroundImage,
        surfaces:{composerBefore:window.__startupSurfaceBefore.composer,composerAfter:read('.composer'),
          codeBefore:window.__startupSurfaceBefore.code,codeAfter:read('pre'),
          menuBefore:window.__startupSurfaceBefore.menu,menuAfter:read('[role="menu"]')},
        frameIntent:window.__startupFrameSpecs[0].intent,frameRunId:window.__startupFrameSpecs[0].runId,
        frameSpecAssets:window.__startupFrameSpecs[0].hasWallpaper};
    })()`);
    assert.equal(details.frameCount, 1);
    assert.equal(details.styleCount, 1);
    assert.equal(details.frameIntent, 'play');
    assert.equal(details.frameSpecAssets, true);
    assert.equal(details.unknownAfter, 'linear-gradient(rgb(255, 0, 0), rgb(0, 0, 255))');
    assert.equal(details.surfaces.composerAfter, details.surfaces.composerBefore);
    assert.equal(details.surfaces.codeAfter, details.surfaces.codeBefore);
    assert.equal(details.surfaces.menuAfter, details.surfaces.menuBefore);
    return { state, details };
  });
  await check('compiled native helper status and apply guard execute against the live fixture API objects', async () => {
    const before = await cdp.evaluate(`({runId:window.__startupAPI.status().runId,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length})`);
    const status = await evaluateNativeHelper('statusSource');
    const failedRequest = await evaluateNativeHelper('statusSource', { startup: 'failed' });
    assert.equal(failedRequest.applied, false, 'a retained old wallpaper cannot certify the failed latest request');
    assert.equal(failedRequest.failureCode, 'image-decode-failed');
    assert.equal(status.applied, true);
    assert.equal(status.startup.installed, true);
    assert.equal(status.startup.owner, 'azhou-codex-startup');
    assert.equal(status.startup.phase, 'playing');
    const active = await evaluateNativeHelper('applyGuardSource');
    assert.deepEqual(active, { state: 'startup-active', applied: false });
    const unknownStartup = await evaluateNativeHelper('applyGuardSource', { startup: 'unknown', wallpaper: 'none' });
    assert.deepEqual(unknownStartup, { state: 'owner-conflict', applied: false });
    const unknownWallpaper = await evaluateNativeHelper('applyGuardSource', { startup: 'none', wallpaper: 'unknown' });
    assert.deepEqual(unknownWallpaper, { state: 'owner-conflict', applied: false });
    const after = await cdp.evaluate(`({runId:window.__startupAPI.status().runId,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length})`);
    assert.deepEqual(after, before, 'status and apply guards are read-only');
    return { status, active, unknownStartup, unknownWallpaper, before, after };
  });
  await check('deep and light synthetic host screenshots preserve controls and unknown decoration', async () => {
    const shots = [];
    for (const [theme, file] of [['dark', 'startup-wallpaper-dark.png'], ['light', 'startup-wallpaper-light.png']]) {
      await cdp.evaluate('document.documentElement.dataset.theme=' + JSON.stringify(theme));
      const state = await cdp.evaluate('window.__startupAPI.status()');
      assert.equal(state.wallpaper.applied, true);
      shots.push(await screenshot(file));
    }
    return shots;
  });
  await check('PageController settings save closes the draft without replay and keeps API focus behavior', async () => {
    const before = await cdp.evaluate('window.__startupAPI.status()');
    const opened = await cdp.evaluate(`(()=>{
      const accepted=window.__startupAPI.openSettings();
      return {accepted,count:document.querySelectorAll('iframe[aria-label]').length,
        state:window.__startupAPI.status()};
    })()`);
    assert.equal(opened.accepted, true);
    assert.equal(opened.count, 1);
    assert.equal(opened.state.phase, 'settings');
    assert.equal(opened.state.runId, before.runId);
    await cdp.evaluate(`window.__startupFixtureSend(${before.runId},{type:'azhou-startup',action:'settings-close',runId:${before.runId}})`);
    const saved = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='complete'&&state.completion?.cause==='settings-save'?state:false;
    })()`), 5000, 'settings save completes the existing run');
    assert.equal(saved.runId, before.runId, 'saving does not allocate another animation run');
    assert.equal(await cdp.evaluate('window.__startupFrameSpecs.length'), 1,
      'saving does not mount a playback frame');
    assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0,
      'saving closes and releases the settings frame');
    const inputOpen = await cdp.evaluate(`(()=>{
      const input=document.querySelector('textarea');input.focus();
      const accepted=window.__startupAPI.openSettings();
      return {accepted,inputFocused:document.activeElement===input,state:window.__startupAPI.status()};
    })()`);
    assert.equal(inputOpen.inputFocused, true);
    assert.equal(inputOpen.accepted, true);
    const apiSettings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='settings'&&state.ready&&state.runId>${saved.runId}?state:false;
    })()`), 10000, 'host input opens a settings-intent run through the PageController API');
    await cdp.evaluate(`window.__startupFixtureSend(${apiSettings.runId},{type:'azhou-startup',action:'complete',runId:${apiSettings.runId},skipped:true})`);
    await until(() => cdp.evaluate('window.__startupAPI.status().phase === "complete"'), 3000,
      'cancel the API-opened settings run');
    const apiFocusRestored = await cdp.evaluate(`(()=>{
      const input=document.querySelector('textarea');return document.activeElement===input;
    })()`);
    assert.equal(apiFocusRestored, true, 'API-opened settings returns focus to the previously focused host input');
    return { before: { runId: before.runId, phase: before.phase }, saved: { runId: saved.runId, phase: saved.phase },
      apiSettings: { runId: apiSettings.runId, phase: apiSettings.phase }, apiFocusRestored };
  });
  await check('complete exposes the appearance button, opens settings, and cancellation restores focus without replay', async () => {
    const play = await cdp.evaluate('window.__startupAPI.status()');
    await cdp.evaluate(`window.__startupFixtureSend(${play.runId},{type:'azhou-startup',action:'complete',runId:${play.runId},skipped:false})`);
    assert.equal((await cdp.evaluate('window.__startupAPI.status()')).phase, 'complete');
    assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0);
    assert.equal(await cdp.evaluate(`(()=>{const input=document.querySelector('textarea');input.focus();return document.activeElement===input;})()`), true,
      'the host composer remains focusable before opening settings');
    const entry = await waitForAppearanceEntry('appearance entry is ready after completing playback');
    assert.equal(entry.display, 'block');
    assert.equal(entry.position, 'fixed');
    assert.equal(entry.buttonPosition, 'static');
    assert.equal(entry.left, '10px');
    assert.equal(entry.bottom, '72px');
    assert.ok(entry.rect.width >= 44 && entry.rect.width <= 80,
      'the synthetic appearance button stays compact without an avatar: ' + JSON.stringify(entry.rect));
    assert.equal(entry.padding, '5px 9px 5px 5px');
    assert.equal(entry.buttonText, '阿舟外观');
    assert.equal(entry.buttonAriaLabel, '阿舟外观');
    assert.equal(entry.entryHit, true, 'the appearance entry receives its own hit target');
    assert.equal(entry.buttonHit, true, 'the appearance button receives its shadow hit target');
    assert.equal(entry.inputHit, true, 'the host composer remains independently hit-testable');
    assert.equal(entry.menuHit, true, 'the host menu remains independently hit-testable');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
    await screenshot('appearance-entry-dark.png');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
    await screenshot('appearance-entry-light.png');
    const opened = await clickAppearanceEntry();
    assert.equal(opened.focused, true, 'a real appearance click focuses the entry button');
    assert.ok(['loading', 'settings'].includes(opened.state.phase), 'the click starts opening settings');
    const settings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='settings'&&state.ready?state:false;
    })()`), 10000, 'appearance button settings-intent ready');
    const spec = await cdp.evaluate('window.__startupFrameSpecs.at(-1)');
    assert.equal(spec.intent, 'settings');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
    await screenshot('appearance-settings-dark.png');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
    await screenshot('appearance-settings-light.png');
    assert.equal(await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      frame.contentDocument.querySelector('#startup-fixture-settings-input').focus();
      return document.activeElement===frame;
    })()`), true, 'the visible settings input can receive focus inside its iframe');
    await cdp.evaluate(`window.__startupFixtureSend(${settings.runId},{type:'azhou-startup',action:'complete',runId:${settings.runId},skipped:true})`);
    const cancelled = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(cancelled.phase, 'complete');
    assert.deepEqual(cancelled.completion, { cause: 'settings-cancel', beforeReady: false });
    const focusAfterButtonCancel = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const button=entry?.shadowRoot?.querySelector('button');
      return {visible:entry?.style.display==='block',documentFocus:document.activeElement===entry,
        shadowFocus:entry?.shadowRoot?.activeElement===button};
    })()`);
    assert.deepEqual(focusAfterButtonCancel, { visible: true, documentFocus: true, shadowFocus: true });

    const reopen = await clickAppearanceEntry();
    assert.equal(reopen.focused, true);
    const secondSettings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='settings'&&state.ready?state:false;
    })()`), 10000, 'second settings-intent ready');
    const isolatedHostFocus = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const input=frame.contentDocument.querySelector('#startup-fixture-settings-input');
      const theme=document.querySelector('#theme');
      input.focus();theme.focus();
      return {frameFocused:document.activeElement===frame,inputFocused:frame.contentDocument.activeElement===input,
        themeFocused:document.activeElement===theme};
    })()`);
    assert.deepEqual(isolatedHostFocus, { frameFocused: true, inputFocused: true, themeFocused: false },
      'the host remains outside the keyboard focus boundary while settings are open');
    await cdp.evaluate(`window.__startupFixtureSend(${secondSettings.runId},{type:'azhou-startup',action:'complete',runId:${secondSettings.runId},skipped:true})`);
    const finalFocus = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const button=entry?.shadowRoot?.querySelector('button');
      return {documentFocus:document.activeElement===entry,shadowFocus:entry?.shadowRoot?.activeElement===button};
    })()`);
    assert.deepEqual(finalFocus, { documentFocus: true, shadowFocus: true },
      'closing settings returns focus to the visible appearance entry');
    return { settings: { runId: settings.runId, phase: settings.phase }, completion: cancelled.completion,
      restoredHostFocus: true, isolatedHostFocus, finalFocus };
  });
  async function verifySidebarUpdatePlacement() {
    const state = await cdp.evaluate('window.__startupAPI.status()');
    if (state.phase === 'playing') {
      await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'complete',runId:${state.runId},skipped:false})`);
      await until(() => cdp.evaluate('window.__startupAPI.status().phase === "complete"'), 3000, 'entry is visible');
    }
    try {
      await cdp.evaluate(`(()=>{
        const update=document.createElement('button');
        update.id='fixture-download-update';update.textContent='Download update';
        update.style.cssText='position:fixed;left:28px;bottom:80px;width:48px;height:48px;z-index:100';
        const profile=document.createElement('button');
        profile.id='fixture-profile';profile.textContent='Profile';
        profile.style.cssText='position:fixed;left:28px;bottom:8px;width:48px;height:48px;z-index:100';
        document.querySelector('.sidebar').appendChild(update);
        document.querySelector('.sidebar').appendChild(profile);
      })()`);
      const readResult = () => cdp.evaluate(`(()=>{
        const update=document.querySelector('#fixture-download-update'),r=update.getBoundingClientRect();
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),e=entry.getBoundingClientRect();
        const width=Math.max(0,Math.min(e.right,r.right)-Math.max(e.left,r.left));
        const height=Math.max(0,Math.min(e.bottom,r.bottom)-Math.max(e.top,r.top));
        const profile=document.querySelector('#fixture-profile'),p=profile.getBoundingClientRect();
        const profileArea=Math.max(0,Math.min(e.right,p.right)-Math.max(e.left,p.left))
          *Math.max(0,Math.min(e.bottom,p.bottom)-Math.max(e.top,p.top));
        return {area:width*height,profileArea,hit:document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===update,
          profileHit:document.elementFromPoint(p.left+p.width/2,p.top+p.height/2)===profile,
          update:{x:r.x,y:r.y,width:r.width,height:r.height},entry:{x:e.x,y:e.y,width:e.width,height:e.height}};
      })()`);
      let lastResult;
      let result;
      try {
        result = await until(async () => {
          lastResult = await readResult();
          return lastResult.area === 0 && lastResult.profileArea === 0 && lastResult.hit && lastResult.profileHit ? lastResult : false;
        }, 1500, 'appearance entry moves away from the update button');
      } catch (error) {
        throw new Error(safeError(error) + ': ' + JSON.stringify(lastResult));
      }
      assert.equal(result.area, 0, 'appearance must not cover the update control: '+JSON.stringify(result));
      assert.equal(result.hit, true, 'update control must remain clickable');
      assert.equal(result.profileHit, true, 'profile control must remain clickable');
      await screenshot('appearance-entry-update-and-profile.png');
      return result;
    } finally {
      await cdp.evaluate("document.querySelector('#fixture-download-update')?.remove();document.querySelector('#fixture-profile')?.remove()");
    }
  }
  await check('appearance entry does not cover a sidebar update button', verifySidebarUpdatePlacement);

  await check('generated Escape keeps Appearance hidden until host UI is ready', async () => {
    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&hold-shell=1&generated-payload=1');
    const run = await awaitGeneratedReady('generated animation ready while the app shell is held back');
    const beforeEscape = await cdp.evaluate(`(()=>({
      state:window.__startupAPI.status(),
      shell:!!document.querySelector('[data-app-shell-frame]'),
      pageSurface:!!document.querySelector('[data-app-shell-page-surface]'),
      homeNav:!!document.querySelector('nav[aria-label="Home"]'),
    }))()`);
    assert.equal(beforeEscape.shell, false, 'the synthetic app shell is not mounted before Escape');
    assert.equal(beforeEscape.homeNav, false, 'Home navigation has not appeared before Escape');
    assert.equal(await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      if(!frame?.contentWindow)return false;
      frame.contentWindow.dispatchEvent(new KeyboardEvent('keydown',{
        key:'Escape',code:'Escape',bubbles:true,cancelable:true,
      }));
      return true;
    })()`), true, 'dispatch Escape into the startup animation iframe');
    const completed = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='complete'&&!document.querySelector('iframe[aria-label]')?state:false;
    })()`), 10000, 'generated startup completes after Escape');
    assert.equal(completed.completion?.cause, 'skip');
    const early = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      if(!entry)return null;
      const rect=entry.getBoundingClientRect(), style=getComputedStyle(entry);
      return {visible:style.display!=='none'&&rect.width>0&&rect.height>0,
        display:style.display,position:style.position,left:style.left,top:style.top,bottom:style.bottom,
        rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
        viewport:{width:innerWidth,height:innerHeight},
        shell:!!document.querySelector('[data-app-shell-frame]')};
    })()`);
    assert.ok(early, 'the Appearance entry is mounted before the app shell');
    assert.equal(early.visible, false,
      'Escape while only the startup splash is present must not reveal Appearance at the lower left: '
      + JSON.stringify(early));

    const availableControl = await cdp.evaluate(`(()=>{
      const root=document.getElementById('root')||document.body;
      const button=document.createElement('button');button.type='button';button.setAttribute('data-fixture-loading-control','');
      button.style.cssText='position:fixed;left:300px;top:300px;width:120px;height:40px;z-index:1';
      button.textContent='Host control';root.appendChild(button);
      return {button:true,hit:document.elementFromPoint(360,320)===button};
    })()`);
    assert.deepEqual(availableControl, { button: true, hit: true },
      'an exposed page control makes the fallback available after the animation is skipped');
    await until(() => cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),rect=entry?.getBoundingClientRect();
      return entry?.style.display==='block'&&rect?.width>0&&rect?.height>0;
    })()`), 3000, 'the visible host control restores Appearance');

    const coveredControl = await cdp.evaluate(`(()=>{
      const button=document.querySelector('[data-fixture-loading-control]');
      if(!button)return false;
      const overlay=document.createElement('div');overlay.setAttribute('data-fixture-loading-overlay','');
      overlay.style.cssText='position:fixed;inset:0;z-index:2147483647;background:transparent';
      document.documentElement.appendChild(overlay);
      return {overlay:true,covered:document.elementFromPoint(360,320)===overlay};
    })()`);
    assert.deepEqual(coveredControl, { overlay: true, covered: true },
      'a visible host control can remain underneath the loading overlay');
    const remainsHiddenUnderOverlay = await until(() => cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const rect=entry?.getBoundingClientRect();
      return !!entry&&getComputedStyle(entry).display==='none'&&(!rect||rect.width===0||rect.height===0);
    })()`), 3000, 'Appearance yields when the loading overlay covers a positive-size host control');
    assert.ok(remainsHiddenUnderOverlay, 'positive-size controls covered by the loading overlay must not reveal Appearance');
    assert.equal(await cdp.evaluate(`(()=>{
      document.querySelector('[data-fixture-loading-overlay]')?.remove();
      return document.elementFromPoint(360,320)===document.querySelector('[data-fixture-loading-control]');
    })()`), true, 'the host control becomes hit-testable when the overlay is removed');
    const recoveredUnderlay = await until(() => cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const rect=entry?.getBoundingClientRect();
      return !!entry&&getComputedStyle(entry).display!=='none'&&rect?.width>0&&rect?.height>0;
    })()`), 3000, 'Appearance recovers after the loading overlay is removed');
    assert.ok(recoveredUnderlay, 'the removed overlay triggers a fresh readiness check');
    await cdp.evaluate(`document.querySelector('[data-fixture-loading-control]')?.remove()`);
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]')?.style.display==='none'`),
      3000, 'removing the last visible host control hides the fallback again');

    const fallback = await cdp.evaluate(`(()=>{
      if(!window.__releaseShell())return false;
      const shell=document.querySelector('[data-app-shell-frame]');
      if(!shell)return false;
      const composer=shell.querySelector('.composer');
      if(!composer)return false;
      shell.querySelectorAll('button,a[href],[role="button"],input,textarea,select').forEach(node=>node.remove());
      composer.removeAttribute('data-composer-layout');
      composer.replaceChildren();
      const wrapper=document.createElement('div');
      wrapper.setAttribute('data-fixture-editor-wrapper','');
      wrapper.style.cssText='position:fixed;left:220px;bottom:20px;width:500px;height:60px;opacity:0;z-index:10';
      const editor=document.createElement('div');
      editor.setAttribute('role','textbox');
      editor.setAttribute('contenteditable','true');
      editor.setAttribute('aria-label','Synthetic editor');
      editor.style.cssText='width:100%;height:100%';
      wrapper.appendChild(editor);
      composer.appendChild(wrapper);
      shell.removeAttribute('data-app-shell-frame');
      shell.querySelector('[data-app-shell-main-surface]')?.removeAttribute('data-app-shell-main-surface');
      shell.querySelector('[data-app-shell-page-surface]')?.removeAttribute('data-app-shell-page-surface');
      return {released:true,
        shellMarkers:!!shell.matches('[data-app-shell-frame]'),
        pageControls:shell.querySelectorAll('[role="textbox"],[contenteditable="true"]').length,
        priorControls:shell.querySelectorAll('button,a[href],[role="button"],input,textarea,select').length};
    })()`);
    assert.equal(fallback?.released, true, 'the synthetic host page becomes available with only a hidden editor control');
    assert.equal(fallback.priorControls, 0, 'no legacy button/input selector can drive readiness during this check');
    assert.equal(fallback.pageControls, 1, 'only the generic role textbox/contenteditable remains in the app root');
    await delay(140);
    const stillHidden = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      if(!entry)return null;
      const rect=entry.getBoundingClientRect();
      return {visible:getComputedStyle(entry).display!=='none'&&rect.width>0&&rect.height>0,
        parent:entry.parentElement?.tagName,position:getComputedStyle(entry).position};
    })()`);
    assert.ok(stillHidden, 'the delayed shell is present in the DOM');
    assert.equal(stillHidden.visible, false,
      'the fallback remains hidden while its editor ancestor is still opacity zero: ' + JSON.stringify(stillHidden));
    assert.equal(await cdp.evaluate(`(()=>{
      const wrapper=document.querySelector('[data-fixture-editor-wrapper]');
      if(!wrapper)return false;
      wrapper.style.opacity='1';
      return true;
    })()`), true, 'reveal the host editor ancestor outside the fallback column');
    const readyFallback = await until(() => cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const nav=document.querySelector('nav[aria-label="Home"]');
      if(!entry||nav&&!nav.hidden)return false;
      const rect=entry.getBoundingClientRect(), style=getComputedStyle(entry);
      if(style.display==='none'||!rect.width||!rect.height||style.position!=='fixed')return false;
      return {position:style.position,parent:entry.parentElement?.tagName,
        rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
        metrics:(()=>{
          const composer=document.querySelector('.composer')?.getBoundingClientRect();
          const x=Math.max(0,Math.min(rect.right,composer?.right||0)-Math.max(rect.left,composer?.left||0));
          const y=Math.max(0,Math.min(rect.bottom,composer?.bottom||0)-Math.max(rect.top,composer?.top||0));
          return {composerOverlapArea:x*y};
        })()};
    })()`), 5000, 'a usable host page restores fallback when Home navigation is unavailable');
    assert.equal(readyFallback.parent, 'HTML', 'the fallback stays in the page layer outside the hidden sidebar');
    assert.equal(readyFallback.metrics.composerOverlapArea, 0,
      'the restored fallback must avoid the visible composer: ' + JSON.stringify(readyFallback));

    const relocated = await cdp.evaluate(`(()=>{
      const sidebar=document.querySelector('.sidebar');
      if(!sidebar||sidebar.querySelector('nav[aria-label="Home"]'))return false;
      const nav=document.createElement('nav');
      nav.setAttribute('aria-label','Home');
      nav.setAttribute('role','navigation');
      nav.style.cssText='display:flex;flex-direction:column;width:100%;height:100%;min-height:0;overflow:hidden';
      const header=document.createElement('div');
      header.style.cssText='flex:none;padding:12px 8px 8px';
      const list=document.createElement('div');
      list.className='group/nav-list';
      list.style.cssText='display:flex;flex-direction:column;gap:4px;width:100%';
      for(const label of ['New chat','Your dot']){
        const button=document.createElement('button');
        button.type='button';button.className='sidebar-item';button.textContent=label;
        button.style.cssText='width:100%;min-height:32px';list.appendChild(button);
      }
      header.appendChild(list);nav.appendChild(header);sidebar.appendChild(nav);
      return true;
    })()`);
    assert.equal(relocated, true, 'mount Home navigation after testing the fallback recovery');
    const after = await until(() => cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const nav=document.querySelector('nav[aria-label="Home"]');
      const dot=Array.from(nav?.querySelectorAll('button,a[href]')||[])
        .find(node=>node.textContent.trim()==='Your dot');
      if(!entry||!dot||entry.parentElement!==dot.parentElement||entry.previousElementSibling!==dot)return false;
      const rect=entry.getBoundingClientRect(), style=getComputedStyle(entry);
      return {visible:style.display!=='none',position:style.position,parentIsList:true,
        afterYourDot:entry.previousElementSibling===dot,
        rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height}};
    })()`), 5000, 'Appearance returns to Your dot when Home navigation becomes available');
    assert.equal(after.visible, true);
    assert.equal(after.position, 'static');
    assert.equal(after.afterYourDot, true, 'the recovered entry follows Your dot: ' + JSON.stringify(after));
    return { runId: run.runId, completion: completed.completion, early, fallback: readyFallback, recovered: after };
  });
  await navigate('/fixture.html?home-nav-fixture=1' + (options.generatedPayload ? '&generated-payload=1' : ''));
  await check('appearance entry follows Your dot inside grouped list wrappers', async () => {
    const run = await awaitGeneratedReady('wrapped Home navigation fixture startup is ready');
    assert.equal(await cdp.evaluate(`(() => {
      const list=document.querySelector('[data-fixture-nav-list]');
      if(!list)return false;
      for(const button of [...list.querySelectorAll(':scope > button')]){
        const group=document.createElement('div');group.setAttribute('role','list');
        const row=document.createElement('div');row.setAttribute('role','listitem');
        const wrapper=document.createElement('div');wrapper.style.overflow='hidden';
        list.insertBefore(group,button);group.appendChild(row);row.appendChild(wrapper);wrapper.appendChild(button);
      }
      return true;
    })()`), true);
    if (options.generatedPayload) {
      assert.equal(await cdp.evaluate(`(()=>{
        const button=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;button.click();return true;
      })()`), true);
    } else {
      await cdp.evaluate(`window.__startupFixtureSend(${run.runId},
        {type:'azhou-startup',action:'complete',runId:${run.runId},skipped:false})`);
    }
    await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='complete'`), 10000, 'startup completes');
    await delay(200);
    const result=await cdp.evaluate(`(() => {
      const dot=document.querySelector('[data-fixture-your-dot]');
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const row=dot?.closest('[role="listitem"]');
      const dotRect=dot?.getBoundingClientRect(), entryRect=entry?.getBoundingClientRect();
      return {inNavigation:!!entry?.closest('nav'), followsDot:row?.nextElementSibling===entry,
        afterDotGeometrically:!!dotRect&&!!entryRect&&entryRect.top>=dotRect.bottom-1,
        position:entry?getComputedStyle(entry).position:null};
    })()`);
    assert.deepEqual(result, {inNavigation:true,followsDot:true,afterDotGeometrically:true,position:'static'});
    assert.equal(await cdp.evaluate(`(()=>{
      const dot=document.querySelector('[data-fixture-your-dot]');
      const group=dot.closest('[role="list"]'), duplicate=group.cloneNode(true);
      duplicate.setAttribute('data-fixture-duplicate-dot','');
      duplicate.querySelector('[data-agent-skin-entry]')?.remove();
      group.parentElement.appendChild(duplicate); return true;
    })()`), true);
    await until(() => cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      return entry && !entry.closest('nav') && getComputedStyle(entry).position==='fixed';
    })()`), 5000, 'ambiguous visible wrapped targets fall back');
    assert.equal(await cdp.evaluate(`(()=>{document.querySelector('[data-fixture-duplicate-dot]').remove();return true})()`), true);
    await until(() => cdp.evaluate(`(()=>{
      const dot=document.querySelector('[data-fixture-your-dot]');
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      return !!entry && dot?.closest('[role="listitem"]')?.nextElementSibling===entry;
    })()`), 5000, 'entry returns after the duplicate disappears');
    assert.equal(await cdp.evaluate(`(()=>{
      const dot=document.querySelector('[data-fixture-your-dot]');
      const group=dot.closest('[role="list"]'), replacement=group.cloneNode(true);
      replacement.querySelector('[data-agent-skin-entry]')?.remove();
      group.replaceWith(replacement); return true;
    })()`), true);
    await until(() => cdp.evaluate(`(()=>{
      const dot=document.querySelector('[data-fixture-your-dot]');
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      return !!entry && dot?.closest('[role="listitem"]')?.nextElementSibling===entry;
    })()`), 5000, 'entry reanchors after wrapped list replacement');
    assert.equal(await cdp.evaluate(`(()=>{
      const dot=document.querySelector('[data-fixture-your-dot]');
      const list=dot.closest('[role="list"]');
      const newChat=document.querySelector('[data-fixture-new-chat]');
      const newChatRow=newChat.closest('[role="listitem"]');
      const oldList=newChatRow.parentElement;
      list.insertBefore(newChatRow,list.firstChild); oldList.remove(); return true;
    })()`), true);
    await until(() => cdp.evaluate(`(()=>{
      const dot=document.querySelector('[data-fixture-your-dot]');
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      return !!entry && dot?.closest('[role="listitem"]')?.nextElementSibling===entry;
    })()`), 5000, 'entry remains after Your dot when multiple rows share one list');
    const clicked=await clickAppearanceEntry();
    assert.equal(clicked?.focused, true, 'the wrapped navigation entry is visible and clickable');
    await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='settings'`), 10000,
      'the wrapped navigation entry opens settings');
    return result;
  });
  await navigate('/fixture.html?home-nav-fixture=1' + (options.generatedPayload ? '&generated-payload=1' : ''));
  await check('appearance entry follows Your dot in the real Home nav and survives narrow layout and remount', async () => {
    const initialRun = await awaitGeneratedReady('Home navigation fixture startup is ready');
    if (options.generatedPayload) {
      assert.equal(await cdp.evaluate(`(()=>{
        const button=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;button.click();return true;
      })()`), true, 'the generated animation exposes its skip control');
    } else {
      await cdp.evaluate(`window.__startupFixtureSend(${initialRun.runId},
        {type:'azhou-startup',action:'complete',runId:${initialRun.runId},skipped:false})`);
    }
    const completed = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='complete'&&!document.querySelector('iframe[aria-label]')?state:false;
    })()`), 10000, 'the appearance entry becomes available after startup completion');
    const inspect = () => cdp.evaluate(`(()=>{
      const nav=document.querySelector('nav[aria-label="Home"][role="navigation"]');
      const list=nav?.querySelector(':scope > :first-child > [class~="group/nav-list"]');
      const dot=list?.querySelector('button[data-fixture-your-dot]');
      const newChat=list?.querySelector('button[data-fixture-new-chat]');
      const scroll=nav?.children[1];
      const section=scroll?.querySelector('section[class~="group/nav-section"]');
      const title=section?.querySelector('div[class~="group/nav-section-title"]');
      const toggle=title?.querySelector('button[class~="group/section-toggle"]');
      const pinned=toggle?.querySelector(':scope > span');
      const entries=[...document.querySelectorAll('[data-agent-skin-entry="appearance"]')],entry=entries[0];
      const rect=node=>node?.getBoundingClientRect?.();
      const data=r=>r?{x:r.x,y:r.y,width:r.width,height:r.height}:null;
      const intersects=(a,b)=>!!a&&!!b&&Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))
        *Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top))>0;
      const entryRect=rect(entry),dotRect=rect(dot),listRect=rect(list);
      const boxlessAncestor=nav?.parentElement?.matches('[data-fixture-boxless-ancestor]')?nav.parentElement:null;
      const boxlessRect=rect(boxlessAncestor);
      const download=document.querySelector('#fixture-download-update'),profile=document.querySelector('#fixture-profile');
      const hit=node=>{const r=rect(node);if(!r)return false;const target=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return target===node||node.contains(target);};
      const follows=(before,after)=>!!before&&!!after&&!!(before.compareDocumentPosition(after)&Node.DOCUMENT_POSITION_FOLLOWING);
      return {navLabel:nav?.getAttribute('aria-label')||null,navRole:nav?.getAttribute('role')||null,
        navWidth:nav?.getBoundingClientRect().width||0,listUnderHeader:!!list&&list.parentElement===nav.firstElementChild,
        boxlessAncestor:boxlessAncestor?{display:getComputedStyle(boxlessAncestor).display,
          width:boxlessRect?.width??null,height:boxlessRect?.height??null}:null,
        yourDot:dot?{tag:dot.tagName,type:dot.type,sidebarItem:dot.classList.contains('sidebar-item'),
          href:dot.hasAttribute('href'),ariaLabel:dot.hasAttribute('aria-label'),role:dot.hasAttribute('role'),text:dot.textContent.trim()}:null,
        newChatPrecedesYourDot:!!newChat&&dot?.previousElementSibling===newChat,
        pinnedInSeparateScroll:!!scroll&&scroll.tagName==='DIV'&&scroll!==nav.firstElementChild
          &&section?.classList.contains('group/nav-section')===true
          &&title?.classList.contains('group/nav-section-title')===true
          &&toggle?.classList.contains('group/section-toggle')===true&&toggle?.getAttribute('role')==='button'
          &&toggle?.getAttribute('aria-expanded')==='true'&&pinned?.textContent.trim()==='Pinned',
        entryCount:entries.length,parentIsNavList:!!entry&&entry.parentElement===list,
        position:entry?getComputedStyle(entry).position:null,
        afterYourDot:dot?.nextElementSibling===entry,beforePinned:follows(entry,pinned),
        rowOrder:Array.from(list?.children||[]).map(node=>node.hasAttribute('data-fixture-new-chat')?'New chat'
          :node.hasAttribute('data-fixture-your-dot')?'Your dot':node.matches?.('[data-agent-skin-entry="appearance"]')?'appearance':'other'),
        entryRect:data(entryRect),dotRect:data(dotRect),listRect:data(listRect),
        followsDotGeometrically:!!entryRect&&!!dotRect&&entryRect.top>=dotRect.bottom-1,
        fillsNavList:!!entryRect&&!!listRect&&Math.abs(entryRect.width-listRect.width)<1,
        footer:{noOverlap:!!entryRect&&!intersects(entryRect,rect(download))&&!intersects(entryRect,rect(profile)),
          downloadHit:hit(download),profileHit:hit(profile)},
        remountCount:window.__fixtureHomeNavRemountCount||0,
        priorNavDetached:!!window.__fixturePriorHomeNav&&!window.__fixturePriorHomeNav.isConnected,
        navInstance:nav?.getAttribute('data-fixture-nav-instance')||null};
    })()`);
    const assertFlow = (value, phase) => {
      assert.equal(value.navLabel, 'Home', phase + ': Home nav');
      assert.equal(value.navRole, 'navigation', phase + ': navigation role');
      assert.equal(value.listUnderHeader, true, phase + ': group/nav-list is directly under the nav header');
      assert.deepEqual(value.boxlessAncestor, { display: 'contents', width: 0, height: 0 },
        phase + ': fixture ancestor is boxless');
      assert.deepEqual(value.yourDot, { tag: 'BUTTON', type: 'button', sidebarItem: true,
        href: false, ariaLabel: false, role: false, text: 'Your dot' }, phase + ': exact Your dot control shape');
      assert.ok(value.dotRect?.width > 0 && value.dotRect?.height > 0,
        phase + ': Your dot has a non-zero layout box');
      assert.equal(value.newChatPrecedesYourDot, true, phase + ': New chat precedes Your dot');
      assert.equal(value.pinnedInSeparateScroll, true, phase + ': Pinned is in a separate scroll section');
      assert.equal(value.entryCount, 1, phase + ': exactly one appearance entry');
      assert.equal(value.parentIsNavList, true,
        phase + ': entry is a normal-flow child of the Home nav-list; ' + JSON.stringify(value));
      assert.equal(value.position, 'static', phase + ': entry is in normal flow');
      assert.equal(value.afterYourDot, true, phase + ': entry follows Your dot in row order');
      assert.equal(value.beforePinned, true, phase + ': entry precedes Pinned in document order');
      assert.equal(value.rowOrder.join(','), 'New chat,Your dot,appearance', phase + ': visible nav row order');
      assert.equal(value.followsDotGeometrically, true, phase + ': entry follows Your dot geometrically');
      assert.equal(value.fillsNavList, true, phase + ': entry uses the sidebar nav-list width');
      assert.deepEqual(value.footer, { noOverlap: true, downloadHit: true, profileHit: true },
        phase + ': bottom Download update and Profile remain visible and clickable');
    };
    const initial = await inspect();
    assertFlow(initial, 'initial Home nav');
    assert.ok(initial.entryRect.y - (initial.dotRect.y + initial.dotRect.height) >= 6,
      'appearance has visible spacing below Your dot');

    await cdp.evaluate(`(()=>{
      const badge=document.createElement('span');
      badge.dataset.fixtureUnread=''; badge.textContent='11 unread message';
      document.querySelector('[data-fixture-your-dot]').appendChild(badge);
    })()`);
    await delay(250);
    const unread = await until(async () => {
      const value = await inspect();
      return value.yourDot?.text === 'Your dot11 unread message' && value.afterYourDot
        && value.position === 'static' ? value : false;
    }, 3000, 'appearance stays in navigation after unread count appears');
    assert.ok(unread.entryRect.y - (unread.dotRect.y + unread.dotRect.height) >= 6);
    await cdp.evaluate("document.querySelector('[data-fixture-unread]').remove()");
    await delay(250);
    const cleared = await until(async () => {
      const value = await inspect();
      return value.yourDot?.text === 'Your dot' && value.afterYourDot && value.position === 'static' ? value : false;
    }, 3000, 'appearance stays in navigation after unread count clears');
    assertFlow(cleared, 'unread cleared');

    assert.equal(await cdp.evaluate('window.__fixtureSetHomeNavWidth(168)'), true);
    const narrow = await until(async () => {
      const value=await inspect();
      return value.navWidth<=168&&value.navWidth>150?value:false;
    }, 3000, 'narrow Home nav layout');
    assertFlow(narrow, 'narrow Home nav');

    const opened = await clickAppearanceEntry();
    if (!opened?.focused) await screenshot('home-nav-click-failure.png');
    assert.equal(opened?.focused, true, 'the appearance control receives a real pointer click: '+JSON.stringify(opened));
    const settings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='settings'&&document.querySelectorAll('iframe[aria-label]').length===1?state:false;
    })()`), 10000, 'the nav entry opens Appearance settings');
    if (options.generatedPayload) {
      await cdp.evaluate(`(()=>document.querySelector('iframe[aria-label]')?.contentWindow
        .dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true})))()`);
    } else {
      await cdp.evaluate(`window.__startupFixtureSend(${settings.runId},
        {type:'azhou-startup',action:'complete',runId:${settings.runId},skipped:true})`);
    }
    const canceled = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='complete'&&!document.querySelector('iframe[aria-label]')?state:false;
    })()`), 5000, 'Appearance settings close before the nav remount');

    assert.equal(await cdp.evaluate('window.__fixtureRemountHomeNav()'), true,
      'the fixture replaces Home navigation with a fresh matching tree');
    const remounted = await until(async () => {
      const value=await inspect();
      return value.remountCount===1&&value.priorNavDetached&&value.parentIsNavList?value:false;
    }, 5000, 'the existing entry moves into the remounted Home nav');
    assertFlow(remounted, 'remounted Home nav');
    assert.equal(remounted.navInstance, '1');
    return { completed: { runId: completed.runId, cause: completed.completion?.cause||null },
      initial, narrow, settings: { runId: settings.runId, phase: settings.phase },
      canceled: { runId: canceled.runId, cause: canceled.completion?.cause||null }, remounted };
  });
  await navigate('/fixture.html');
  await check('appearance entry remains clickable when the sidebar has no safe gap', async () => {
    try {
      let pageState = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();return state.ready?state:false;
      })()`), 5000, 'fresh fallback fixture is ready before completing playback');
      if (pageState.phase === 'playing') {
        await cdp.evaluate(`window.__startupFixtureSend(${pageState.runId},{type:'azhou-startup',action:'complete',runId:${pageState.runId},skipped:false})`);
      } else if (pageState.phase === 'settings') {
        await cdp.evaluate(`window.__startupFixtureSend(${pageState.runId},{type:'azhou-startup',action:'complete',runId:${pageState.runId},skipped:true})`);
      }
      pageState = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();return state.phase==='complete'?state:false;
      })()`), 5000, 'complete page exposes the entry before crowding the sidebar');
      await cdp.evaluate(`(()=>{
        const side=document.querySelector('.sidebar');
        for(let top=0;top<innerHeight;top+=48){
          const item=document.createElement('button');item.dataset.fixtureCrowded='1';
          item.style.cssText='position:fixed;left:10px;top:'+top+'px;width:240px;height:48px;z-index:100';
          item.addEventListener('click',()=>{window.__crowdedClicks=(window.__crowdedClicks||0)+1});
          side.appendChild(item);
        }
      })()`);
      const crowdedEntry = await until(() => cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const button=entry.shadowRoot.querySelector('button'),rect=entry.getBoundingClientRect();
        const shadowTarget=entry.shadowRoot.elementFromPoint?.(rect.left+rect.width/2,rect.top+rect.height/2);
        const blocked=[...document.querySelectorAll('[data-fixture-crowded]')].some(host=>{
          const r=host.getBoundingClientRect();
          return r.left<rect.right&&r.right>rect.left&&r.top<rect.bottom&&r.bottom>rect.top;
        });
        return entry.style.display==='block'&&!blocked&&getComputedStyle(button).visibility==='visible'
          &&document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2)===entry
          ?{left:rect.left,top:rect.top,width:rect.width,height:rect.height,buttonText:button.textContent,
            buttonDisabled:button.disabled,buttonHit:shadowTarget===button||button.contains(shadowTarget),
            state:window.__startupAPI.status()}:false;
      })()`), 3000, 'entry remains clickable without covering crowded host controls');
      assert.equal(crowdedEntry.state.phase, 'complete', 'the entry is tested from a stable completed page');
      assert.equal(crowdedEntry.buttonDisabled, false, 'the left-side fallback button remains enabled when no gap exists');
      assert.equal(crowdedEntry.buttonHit, true, 'the actual shadow button receives the fallback hit target');
      const blockedHostButtons = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const er=entry.getBoundingClientRect();
        return [...document.querySelectorAll('[data-fixture-crowded]')].filter(button=>{
          const r=button.getBoundingClientRect();
          const left=Math.max(r.left,er.left),right=Math.min(r.right,er.right);
          const top=Math.max(r.top,er.top),bottom=Math.min(r.bottom,er.bottom);
          return right>left&&bottom>top&&document.elementFromPoint((left+right)/2,(top+bottom)/2)===entry;
        }).length;
      })()`);
      assert.equal(blockedHostButtons, 0, 'appearance fallback must not intercept host controls');
      const hostPoint = await cdp.evaluate(`(()=>{
        const button=document.querySelector('[data-fixture-crowded]');
        const rect=button.getBoundingClientRect();
        return {x:rect.left+rect.width/2,y:rect.top+rect.height/2};
      })()`);
      await cdp.call('Input.dispatchMouseEvent', { type: 'mousePressed', ...hostPoint, button: 'left', clickCount: 1 });
      await cdp.call('Input.dispatchMouseEvent', { type: 'mouseReleased', ...hostPoint, button: 'left', clickCount: 1 });
      assert.equal(await cdp.evaluate('window.__crowdedClicks'), 1, 'a host button still receives a real pointer click');
      await cdp.evaluate(`(()=>{
        const r=document.querySelector('[data-agent-skin-entry="appearance"]').getBoundingClientRect();
        const container=document.createElement('div');container.dataset.fixtureRightContainer='1';
        container.style.cssText='position:fixed;left:'+r.left+'px;top:'+r.top+'px;width:'+r.width+'px;height:'+r.height+'px;pointer-events:none';
        document.body.appendChild(container);
      })()`);
      await delay(200);
      await cdp.evaluate(`(()=>{
        const host=document.createElement('button');host.dataset.fixtureLateControl='1';
        host.style.cssText='width:100%;height:100%;pointer-events:auto;position:relative;z-index:100';
        document.querySelector('[data-fixture-right-container]').appendChild(host);
      })()`);
      await until(() => cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const host=document.querySelector('[data-fixture-late-control]');
        const e=entry.getBoundingClientRect(),r=host.getBoundingClientRect();
        return entry.style.display==='block'&&(e.right<=r.left||e.left>=r.right||e.bottom<=r.top||e.top>=r.bottom)
          &&document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===host;
      })()`), 3000, 'a later host control in the relocated column remains clickable');
      await screenshot('appearance-entry-crowded-sidebar-visible.png');
      const opened = await clickAppearanceEntry();
      assert.ok(['loading', 'settings'].includes(opened?.state?.phase),
        'real pointer click starts the settings action: ' + JSON.stringify(opened));
      const openingOutcome = await cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const button=entry?.shadowRoot?.querySelector('button');
        return {state:{phase:state.phase,runId:state.runId,ready:state.ready,reason:state.reason},
          buttonDisabled:button?.disabled,entryDisplay:entry?.style.display,
          frameCount:document.querySelectorAll('iframe[aria-label]').length};
      })()`);
      assert.ok(['loading', 'settings'].includes(openingOutcome.state.phase),
        'appearance click starts a settings run with crowded controls present: ' + JSON.stringify(openingOutcome));
      const settings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const frame=document.querySelector('iframe[aria-label]');
        const input=frame?.contentDocument.querySelector('input[aria-label="Synthetic settings input"]');
        const style=input&&frame.contentWindow.getComputedStyle(input);
        const rect=input?.getBoundingClientRect();
        const visible=!!input&&!!rect?.width&&!!rect?.height&&style.display!=='none'
          &&style.visibility==='visible'&&style.opacity!=='0';
        return state.phase==='settings'&&state.ready&&visible&&!input.disabled
          ?{state:{phase:state.phase,runId:state.runId,ready:state.ready},inputVisible:visible,
            inputDisabled:input.disabled,inputLabel:input.getAttribute('aria-label')}:false;
      })()`), 15000, 'left-side fallback entry opens a ready settings run with its visible input').catch(async error => {
        const diagnostic = await cdp.evaluate(`(()=>{
          const state=window.__startupAPI.status(),frames=[...document.querySelectorAll('iframe[aria-label]')];
          const frame=frames.at(-1),doc=frame?.contentDocument,entry=document.querySelector('[data-agent-skin-entry="appearance"]');
          const button=entry?.shadowRoot?.querySelector('button');
          const input=doc?.querySelector('input[aria-label="Synthetic settings input"]');
          return {state:{phase:state.phase,runId:state.runId,ready:state.ready,reason:state.reason},
            frameCount:frames.length,frameTitle:frame?.title,frameReadyState:doc?.readyState,
            settingsInputExists:!!input,settingsInputVisible:!!input&&!!input.getBoundingClientRect().width
              &&!!input.getBoundingClientRect().height,runCount:window.__startupAnimationRuns.length,
            lastSpec:window.__startupFrameSpecs.at(-1)?.intent,
            entryDisplay:entry?.style.display,buttonDisabled:button?.disabled,
            crowdedCount:document.querySelectorAll('[data-fixture-crowded]').length};
        })()`);
        throw new Error(error.message + ': ' + JSON.stringify({
          opened:{focused:opened.focused,state:{phase:opened.state?.phase,runId:opened.state?.runId,
            ready:opened.state?.ready,reason:opened.state?.reason}},openingOutcome,diagnostic}));
      });
      assert.ok(settings.state.runId>0);
      assert.equal(settings.inputLabel,'Synthetic settings input');
      const focusedInput = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const input=frame?.contentDocument.querySelector('input[aria-label="Synthetic settings input"]');
        if(!input||input.disabled)return false;
        input.focus();
        return {focused:frame.contentDocument.activeElement===input,
          visible:!!input.getBoundingClientRect().width&&!!input.getBoundingClientRect().height};
      })()`);
      assert.deepEqual(focusedInput,{focused:true,visible:true},
        'the left-side fallback opens a ready settings input that can receive focus');
      const state=await cdp.evaluate('window.__startupAPI.status()');
      await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'complete',runId:${state.runId},skipped:true})`);
      await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='complete'
        &&!document.querySelector('iframe[aria-label]')`), 5000,
      'settings cancellation removes its covering frame');
      await until(() => cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const rect=entry?.getBoundingClientRect();
        return entry?.style.display==='block'&&rect?.width>0&&rect?.height>0;
      })()`), 3000, 'Appearance returns after the settings frame is removed');
      const afterCancel = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),rect=entry.getBoundingClientRect();
        return {left:rect.left,visible:entry.style.display==='block',
          hit:document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2)===entry};
      })()`);
      assert.equal(afterCancel.visible, true, 'the fallback remains visible after settings closes');
      assert.equal(afterCancel.hit, true, 'the fallback remains clickable after settings closes');
      await cdp.evaluate(`(()=>{
        const cover=document.createElement('button');cover.dataset.fixtureFullCover='1';
        cover.style.cssText='position:fixed;inset:0;width:100vw;height:100vh;z-index:100';
        document.body.appendChild(cover);
      })()`);
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]').style.display==='none'`),
        3000, 'entry yields to host controls when no position is available');
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]').style.contentVisibility='hidden'`);
      await delay(200);
      assert.equal(await cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]').style.display`), 'none',
        'a host control with hidden content can still receive pointer events');
      assert.equal(await cdp.evaluate(`document.elementFromPoint(100,100)===document.querySelector('[data-fixture-full-cover]')`), true);
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]').style.contentVisibility=''`);
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]').style.visibility='hidden'`);
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]').style.display==='block'`),
        3000, 'entry returns when a retained host control becomes invisible');
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]').style.visibility=''`);
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]').style.display==='none'`),
        3000, 'entry yields when the host control becomes visible again');
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]').style.display='none'`);
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]').style.display==='block'`),
        3000, 'entry returns when a retained host control becomes hidden');
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]').style.display=''`);
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]').style.display==='none'`),
        3000, 'entry yields again when the host control returns');
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]').remove()`);
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]').style.display==='block'`),
        3000, 'entry returns when the blocking host control is removed');
      return { crowded: 'host-and-entry-clickable', settingsRunId: settings.state.runId, focusedInput, afterCancel };
    } finally {
      await cdp.evaluate(`document.querySelector('[data-fixture-right-container]')?.remove()`);
      await cdp.evaluate(`document.querySelector('[data-fixture-full-cover]')?.remove()`);
      await cdp.evaluate(`document.querySelectorAll('[data-fixture-crowded]').forEach(item=>item.remove())`);
    }
  });
  await check('appearance entry repositions when sidebar controls scroll', async () => {
    try {
      await cdp.evaluate(`(()=>{
        const scroller=document.createElement('div');scroller.id='fixture-sidebar-scroll';
        scroller.style.cssText='position:fixed;left:10px;bottom:0;width:60px;height:180px;overflow:auto;z-index:100';
        const content=document.createElement('div');content.style.cssText='position:relative;height:400px';
        const item=document.createElement('button');item.id='fixture-scrolled-button';
        item.style.cssText='position:absolute;top:200px;left:8px;width:48px;height:48px';
        content.appendChild(item);scroller.appendChild(content);document.querySelector('.sidebar').appendChild(scroller);
      })()`);
      await cdp.evaluate(`document.querySelector('#fixture-sidebar-scroll').scrollTop=130`);
      await until(() => cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),e=entry.getBoundingClientRect();
        const item=document.querySelector('#fixture-scrolled-button'),r=item.getBoundingClientRect();
        return getComputedStyle(entry).visibility==='hidden'||e.bottom<=r.top||e.top>=r.bottom;
      })()`), 1500, 'entry moves when a sidebar button scrolls into its previous position');
      return { scrolled: true };
    } finally {
      await cdp.evaluate(`document.querySelector('#fixture-sidebar-scroll')?.remove()`);
    }
  });
  await check('appearance entry geometry in collapsed-sidebar narrow viewport', async () => {
    const current = await cdp.evaluate('window.__startupAPI.status()');
    if (current.phase !== 'complete') {
      const ready = await awaitGeneratedReady('startup animation is ready before the narrow-layout check');
      await cdp.evaluate(`window.__startupFixtureSend(${ready.runId},{type:'azhou-startup',action:'complete',runId:${ready.runId},skipped:false})`);
    }
    await until(() => cdp.evaluate(`(()=>window.__startupAPI.status().phase==='complete'
      &&!document.querySelector('iframe[aria-label]'))()`), 5000,
    'complete the animation and remove its covering iframe before checking the collapsed layout');
    const originalStyles = await cdp.evaluate(`(()=>{
      const shell=document.querySelector('[data-app-shell-frame]'),sidebar=document.querySelector('.sidebar');
      return {shell:shell?.getAttribute('style'),sidebar:sidebar?.getAttribute('style')};
    })()`);
    let metrics;
    try {
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 640, height: 720, screenWidth: 640, screenHeight: 720, deviceScaleFactor: 1, mobile: false,
      });
      await cdp.evaluate(`(()=>{
        const shell=document.querySelector('[data-app-shell-frame]'),sidebar=document.querySelector('.sidebar');
        shell.style.gridTemplateColumns='52px minmax(0,1fr)';
        sidebar.style.width='52px';sidebar.style.overflow='hidden';
        const rail=document.createElement('nav');rail.dataset.fixtureCollapsedRail='1';
        rail.style.cssText='position:fixed;left:0;top:44px;bottom:0;width:52px;z-index:10';
        for (const top of [8,65,122,180,240,295]) {
          const button=document.createElement('button');button.setAttribute('aria-label','Rail control');
          button.style.cssText='position:absolute;left:6px;width:40px;height:40px;top:'+top+'px';rail.appendChild(button);
        }
        document.body.appendChild(rail);
        document.querySelector('[role="menu"]').scrollIntoView({block:'center',inline:'nearest'});
      })()`);
      await cdp.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
      await delay(200); // The real entry batches layout updates after host mutations.
      metrics = await until(async () => {
        const value = await appearanceEntryMetrics();
        return value?.viewport.width === 640 && value?.viewport.height === 720
          && value?.rect.height === 44 ? value : false;
      }, 3000, 'the 44px fallback is positioned after the collapsed sidebar settles');
      assert.ok(metrics, 'completed page still exposes the appearance entry');
      assert.equal(metrics.rect.height, 44, 'the compact narrow-viewport appearance button retains a 44px touch target');
      assert.ok(metrics.rect.x >= 0 && metrics.rect.x + metrics.rect.width <= 52,
        'collapsed-sidebar entry must stay within the actual 52px rail and not cover conversation text: '+JSON.stringify(metrics.rect));
      await screenshot('appearance-entry-collapsed-sidebar-640x720.png');
      assert.equal(metrics.entryHit, true, 'the entry host is hit-testable in the collapsed-sidebar viewport');
      assert.equal(metrics.buttonHit, true, 'the shadow button is hit-testable in the collapsed-sidebar viewport: '
        + JSON.stringify({ rect: metrics.rect, viewport: metrics.viewport, entryHit: metrics.entryHit,
          buttonHit: metrics.buttonHit }));
      assert.equal(metrics.inputHit, true, 'the host textarea remains hit-testable in the collapsed-sidebar viewport');
      assert.equal(metrics.menuHit, true, 'the host menu remains hit-testable in the collapsed-sidebar viewport: ' + JSON.stringify({menu:metrics.menuRect, viewport:metrics.viewport, overlap:metrics.menuOverlap}));
      assert.equal(metrics.inputOverlap.area, 0, 'the appearance entry does not overlap the host textarea');
      assert.equal(metrics.menuOverlap.area, 0, 'the appearance entry does not overlap the host menu');
      assert.equal(metrics.composerOverlap.area, 0,
        'appearance entry must not cover the protected composer surface: ' + JSON.stringify({
          button: metrics.rect, composer: metrics.composerRect, overlap: metrics.composerOverlap,
          footerLabel: metrics.composerLabelRect, footerLabelOverlap: metrics.composerLabelOverlap,
          textarea: metrics.inputRect, textareaOverlap: metrics.inputOverlap,
        }));
      return { modeledLayout: { sidebarWidth: 52, viewport: { width: 640, height: 720 } }, ...metrics };
    } finally {
      await cdp.evaluate(`(()=>{
        document.querySelector('[data-fixture-collapsed-rail]')?.remove();
        const shell=document.querySelector('[data-app-shell-frame]'),sidebar=document.querySelector('.sidebar');
        const restore=(node,value)=>value===null?node.removeAttribute('style'):node.setAttribute('style',value);
        if(shell)restore(shell,${JSON.stringify(originalStyles.shell)});
        if(sidebar)restore(sidebar,${JSON.stringify(originalStyles.sidebar)});
      })()`);
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 1512, height: 889, screenWidth: 1512, screenHeight: 889, deviceScaleFactor: 1, mobile: false,
      });
    }
  });
  await check('collapsed rail keeps avatar entry compact and accessible', async () => {
    await navigate('/fixture.html?entry-avatar=1');
    const ready = await awaitGeneratedReady('avatar entry startup is ready');
    await cdp.evaluate(`window.__startupFixtureSend(${ready.runId},{type:'azhou-startup',action:'complete',runId:${ready.runId},skipped:false})`);
    await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='complete'
      &&!document.querySelector('iframe[aria-label]')`), 5000, 'avatar entry startup completes');
    try {
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 640, height: 720, screenWidth: 640, screenHeight: 720, deviceScaleFactor: 1, mobile: false,
      });
      await cdp.evaluate(`(()=>{
        const rail=document.createElement('nav');rail.dataset.fixtureCollapsedRail='1';
        rail.style.cssText='position:fixed;left:0;top:44px;bottom:0;width:52px;z-index:10';
        const button=document.createElement('button');button.setAttribute('aria-label','Rail control');
        button.style.cssText='position:absolute;left:6px;top:8px;width:40px;height:40px';
        rail.appendChild(button);document.body.appendChild(rail);
      })()`);
      await delay(200); // The real entry batches layout updates after host mutations.
      const metrics = await until(async () => {
        const value = await appearanceEntryMetrics();
        return value?.viewport.width === 640 && value?.viewport.height === 720
          && value?.rect.height === 44
          && value?.rect.x >= 0 && value?.rect.x + value?.rect.width <= 52 ? value : false;
      }, 3000, 'the compact avatar entry settles within the rail after the viewport override');
      assert.ok(metrics.avatar, 'the real compact fallback includes an avatar');
      assert.equal(metrics.rect.height, 44);
      assert.ok(metrics.rect.x >= 0 && metrics.rect.x + metrics.rect.width <= 52,
        'avatar entry must remain within the rail: '+JSON.stringify(metrics.rect));
      assert.ok(metrics.buttonAriaLabel && metrics.buttonHit, 'the compact entry remains named and clickable');
      await screenshot('appearance-entry-collapsed-avatar-640x720.png');
      return metrics;
    } finally {
      await cdp.evaluate(`document.querySelector('[data-fixture-collapsed-rail]')?.remove()`);
      await cdp.call('Emulation.setDeviceMetricsOverride', {
        width: 1512, height: 889, screenWidth: 1512, screenHeight: 889, deviceScaleFactor: 1, mobile: false,
      });
    }
  });
  await check('completed page remains editable and wallpaper survives animation completion', async () => {
    const result = await cdp.evaluate(`(()=>{
      const input=document.querySelector('textarea');
      input.focus();input.value='synthetic host input';
      const rect=input.getBoundingClientRect();
      return {focused:document.activeElement===input,hit:document.elementFromPoint(rect.x+8,rect.y+8)===input,
        inputValue:input.value,wallpaper:window.__startupAPI.status().wallpaper.applied,
        frameCount:document.querySelectorAll('iframe[aria-label]').length};
    })()`);
    assert.equal(result.focused, true);
    assert.equal(result.hit, true);
    assert.equal(result.inputValue, 'synthetic host input');
    assert.equal(result.wallpaper, true);
    assert.equal(result.frameCount, 0);
    return await screenshot('startup-after-complete-input.png');
  });
  await check('restore keeps host-edited property, attribute and stylesheet', async () => {
    const result = await cdp.evaluate(`(()=>{
      const root=document.documentElement, style=document.getElementById('azhou-wallpaper-style');
      root.setAttribute('data-azhou-wallpaper','host-later');
      root.style.setProperty('--azhou-wallpaper-image','host-image','important');
      root.style.setProperty('--azhou-wallpaper-wash','host-wash','important');
      style.textContent+='\\n/* host update */';
      window.__startupAPI.dispose();
      return {startup:!!window.__startupAPI.status,installed:Object.hasOwn(window,'__azhouStartup'),
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        attribute:root.getAttribute('data-azhou-wallpaper'),image:root.style.getPropertyValue('--azhou-wallpaper-image'),
        imagePriority:root.style.getPropertyPriority('--azhou-wallpaper-image'),wash:root.style.getPropertyValue('--azhou-wallpaper-wash'),
        washPriority:root.style.getPropertyPriority('--azhou-wallpaper-wash'),styleConnected:style.isConnected,
        styleChanged:style.textContent.includes('host update'),wallpaperGlobal:!!window.__azhouWallpaper};
    })()`);
    assert.deepEqual(result, { startup: true, installed: false, frameCount: 0, attribute: 'host-later',
      image: 'host-image', imagePriority: 'important', wash: 'host-wash', washPriority: 'important',
      styleConnected: true, styleChanged: true, wallpaperGlobal: false });
    return result;
  });

  await navigate('/fixture.html?hold-decode=1&no-initial-wallpaper=1');
  await check('a same-run disable invalidates a real pending wallpaper decode before DOM commit', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI.status();return value.phase==='playing'&&value.ready?value:false;
    })()`), 10000, 'playing with wallpaper initially disabled');
    await cdp.evaluate(`(()=>{window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:42});return true})()`);
    await until(() => cdp.evaluate('window.__decodeGateCount===1'), 10000, 'first real decode gate');
    await cdp.evaluate(`(()=>{window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:0});return true})()`);
    const disabled = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(disabled.wallpaper.applied, false);
    assert.equal(disabled.wallpaper.reason, 'disabled');
    await cdp.evaluate('window.__releaseDecodeAt(0)');
    await until(() => cdp.evaluate('window.__decodePending===false'), 5000, 'stale decode completion');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,150))');
    const after = await cdp.evaluate(`({wallpaper:window.__startupAPI.status().wallpaper,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
      wallpaperGlobal:!!window.__azhouWallpaper})`);
    assert.equal(after.wallpaper.applied, false);
    assert.equal(after.wallpaper.reason, 'disabled');
    assert.equal(after.styleCount, 0);
    assert.equal(after.rootAttribute, null);
    assert.equal(after.wallpaperGlobal, false);
    return { before: { runId: state.runId, phase: state.phase }, disabled, after };
  });

  await navigate('/fixture.html?hold-decode=1&no-initial-wallpaper=1');
  await check('out-of-order nonzero background requests keep the last requested appearance', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI.status();return value.phase==='playing'&&value.ready?value:false;
    })()`), 10000, 'playing with wallpaper initially disabled');
    const sendBackground = strength => cdp.evaluate(`(()=>{window.__startupFixtureSend(${state.runId},{
      type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:${strength}});return true})()`);
    await sendBackground(42);
    await until(() => cdp.evaluate('window.__decodeGateCount===1'), 10000, 'first nonzero decode gate');
    await sendBackground(22);
    await until(() => cdp.evaluate('window.__decodeGateCount===2'), 10000, 'second nonzero decode gate');
    await cdp.evaluate('window.__releaseDecodeAt(1)');
    const latest = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.wallpaper.applied&&state.wallpaper.washMatched?state:false;
    })()`), 10000, 'latest nonzero background commit');
    const committed = await cdp.evaluate(`({wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
      image:document.documentElement.style.getPropertyValue('--azhou-wallpaper-image'),
      wallpaper:window.__azhouWallpaper.status()})`);
    assert.equal(latest.wallpaper.applied, true);
    await cdp.evaluate('window.__releaseDecodeAt(0)');
    await until(() => cdp.evaluate('window.__decodePending===false&&window.__fixtureBlobCount===1'), 5000, 'stale request Blob cleanup');
    const after = await cdp.evaluate(`({wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
      image:document.documentElement.style.getPropertyValue('--azhou-wallpaper-image'),
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      wallpaper:window.__startupAPI.status().wallpaper})`);
    assert.equal(after.wash, committed.wash);
    assert.equal(after.image, committed.image);
    assert.equal(after.styleCount, 1);
    assert.equal(after.wallpaper.applied, true);
    assert.equal(after.wallpaper.washMatched, true);
    return { latestStrength: 22, committed, after };
  });

  await navigate('/fixture.html?legacy=1&legacy-only=1');
  await check('compiled native helpers recognize the synthetic legacy wallpaper without a controller and restore it', async () => {
    const before = await evaluateNativeHelper('statusSource', { startup: 'none' });
    assert.equal(before.applied, true);
    assert.deepEqual(before.startup, { installed: false });
    assert.deepEqual(await evaluateNativeHelper('applyGuardSource', { startup: 'none' }), { state: 'ready', applied: false });
    await cdp.evaluate("window.__fixtureSavedValue='fixture-saved-wallpaper-strength-42'");
    const restored = await evaluateNativeHelper('restoreSource', { startup: 'none' });
    assert.deepEqual(restored, { restored: true, applied: false });
    const after = await cdp.evaluate(`({savedValue:window.__fixtureSavedValue,wallpaper:!!window.__azhouWallpaper,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper')})`);
    assert.deepEqual(after, { savedValue: 'fixture-saved-wallpaper-strength-42', wallpaper: false,
      styleCount: 0, rootAttribute: null });
    return { before, restored, after };
  });

  for (const scenario of [
    { label: 'absent wash baseline', query: '', expectedWash: '', expectedPriority: '' },
    { label: 'host wash important baseline', query: '&legacy-wash=host-important', expectedWash: 'host-wash', expectedPriority: 'important' },
    { label: 'later host wash edit', query: '', editWash: true, expectedWash: 'host-later', expectedPriority: 'important' },
  ]) {
    await navigate('/fixture.html?legacy=1' + scenario.query);
    await check('synthetic legacy wallpaper replacement restores ' + scenario.label, async () => {
      const setup = await cdp.evaluate(`({legacyError:window.__legacyWallpaperError||'',
        legacyApplied:window.__legacyWallpaperAPI?.status().applied===true,controller:typeof window.__startupAPI?.status==='function'})`);
      assert.equal(setup.legacyError, '', JSON.stringify(setup));
      assert.equal(setup.legacyApplied, true, JSON.stringify(setup));
      assert.equal(setup.controller, true, JSON.stringify(setup));
      const state = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status();return value.phase==='playing'&&value.ready?value:false;
      })()`), 10000, 'controller ready after frozen legacy wallpaper takeover');
      assert.equal(await cdp.evaluate('window.__azhouWallpaper===window.__legacyWallpaperAPI'), true,
        'legacy wallpaper remains the active owner until this controlled takeover request');
      await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:42})`);
      const committed = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status(),api=window.__azhouWallpaper;
        return value.wallpaper.applied&&api!==window.__legacyWallpaperAPI
          ?{state:value,owner:api.owner,version:api.version,apiApplied:api.status().applied}:false;
      })()`), 10000, 'candidate wallpaper after legacy dispose');
      assert.equal(committed.state.wallpaper.applied, true);
      assert.equal(committed.owner, 'azhou.codex-startup-animation');
      assert.equal(committed.version, '0.9.0');
      assert.equal(committed.apiApplied, true);
      if (scenario.editWash) await cdp.evaluate("document.documentElement.style.setProperty('--azhou-wallpaper-wash','host-later','important')");
      const beforeRestore = await cdp.evaluate(`({wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
        priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-wash')})`);
      await cdp.evaluate('window.__startupAPI.dispose()');
      const restored = await cdp.evaluate(`({startup:Object.hasOwn(window.__fixtureHost,'__azhouStartup'),
        wallpaper:!!window.__azhouWallpaper,styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
        wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),
        priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-wash')})`);
      assert.deepEqual(restored, { startup: false, wallpaper: false, styleCount: 0, rootAttribute: null,
        wash: scenario.expectedWash, priority: scenario.expectedPriority });
      return { scenario: scenario.label, beforeRestore, restored };
    });
  }

  for (const scenario of [
    { label: 'absent surface baseline', query: '', expectedSurface: '', expectedPriority: '' },
    { label: 'host surface important baseline', query: '&legacy-surface=host-important', expectedSurface: '#fafafa', expectedPriority: 'important' },
  ]) {
    await navigate('/fixture.html?legacy=1' + scenario.query);
    await check('synthetic legacy wallpaper replacement restores ' + scenario.label, async () => {
      const setup = await cdp.evaluate(`({legacyError:window.__legacyWallpaperError||'',
        legacyApplied:window.__legacyWallpaperAPI?.status().applied===true,controller:typeof window.__startupAPI?.status==='function'})`);
      assert.equal(setup.legacyError, '', JSON.stringify(setup));
      assert.equal(setup.legacyApplied, true, JSON.stringify(setup));
      assert.equal(setup.controller, true, JSON.stringify(setup));
      const state = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status();return value.phase==='playing'&&value.ready?value:false;
      })()`), 10000, 'controller ready before legacy surface takeover');
      assert.equal(await cdp.evaluate('window.__azhouWallpaper===window.__legacyWallpaperAPI'), true,
        'legacy wallpaper remains the active owner until this controlled takeover request');
      await cdp.evaluate(`window.__startupFixtureSend(${state.runId},{type:'azhou-startup',action:'background',runId:${state.runId},image:${JSON.stringify(pixelImage)},strength:42})`);
      const committed = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status(),api=window.__azhouWallpaper;
        return value.wallpaper.applied&&api!==window.__legacyWallpaperAPI
          ?{state:value,owner:api.owner,version:api.version,apiApplied:api.status().applied}:false;
      })()`), 10000, 'candidate wallpaper after legacy dispose');
      assert.equal(committed.state.wallpaper.applied, true);
      assert.equal(committed.version, '0.9.0');
      assert.equal(committed.apiApplied, true);
      assert.equal(await cdp.evaluate("document.documentElement.style.getPropertyValue('--azhou-wallpaper-surface')"), '#10121c',
        'the candidate renderer replaces the staged surface with the current host appearance');
      const beforeRestore = await cdp.evaluate(`({surface:document.documentElement.style.getPropertyValue('--azhou-wallpaper-surface'),
        priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-surface')})`);
      await cdp.evaluate('window.__startupAPI.dispose()');
      const restored = await cdp.evaluate(`({startup:Object.hasOwn(window.__fixtureHost,'__azhouStartup'),
        wallpaper:!!window.__azhouWallpaper,styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
        surface:document.documentElement.style.getPropertyValue('--azhou-wallpaper-surface'),
        priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-surface')})`);
      assert.deepEqual(restored, { startup: false, wallpaper: false, styleCount: 0, rootAttribute: null,
        surface: scenario.expectedSurface, priority: scenario.expectedPriority });
      return { scenario: scenario.label, beforeRestore, restored };
    });
  }

  await navigate('/fixture.html?hold-body=1');
  await check('real DOM observer waits for a delayed body and disconnects after mount', async () => {
    const before = await cdp.evaluate(`({phase:window.__startupAPI.status().phase,frames:document.querySelectorAll('iframe[aria-label]').length})`);
    assert.deepEqual(before, { phase: 'loading', frames: 0 });
    await cdp.evaluate('window.__releaseBody()');
    const state = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='playing'&&state.ready?state:false;
    })()`), 10000, 'controller starts after body appears');
    assert.equal(state.overlay, true);
    return { before, state: { phase: state.phase, ready: state.ready, runId: state.runId } };
  });

  await navigate('/fixture.html?hold-decode=1');
  await check('real late image decode after dispose cannot restore wallpaper or revive a run', async () => {
    await until(() => cdp.evaluate('window.__decodePending === true'), 10000, 'real Blob image decode gate');
    const before = await cdp.evaluate('({phase:window.__startupAPI.status().phase,blobCount:window.__fixtureBlobCount})');
    await cdp.evaluate('window.__startupAPI.dispose()');
    await cdp.evaluate('window.__releaseDecode()');
    const after = await until(() => cdp.evaluate(`(()=>({
      blobCount:window.__fixtureBlobCount,wallpaper:!!window.__azhouWallpaper,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      installed:Object.hasOwn(window,'__azhouStartup'),frameCount:document.querySelectorAll('iframe[aria-label]').length
    }))()`), 5000, 'late decode cleanup');
    assert.equal(before.phase, 'playing');
    assert.equal(before.blobCount, 1);
    assert.deepEqual(after, { blobCount: 0, wallpaper: false, styleCount: 0, installed: false, frameCount: 0 });
    return { before, after };
  });

  for (const [path, expectedReason] of [
    ['/csp-style.html', 'wallpaper-unsupported'],
    ['/csp-blob.html', 'wallpaper-unsupported'],
  ]) {
    await navigate(path);
    await check('CSP refusal is visible in wallpaper state: ' + path, async () => {
      const state = await until(() => cdp.evaluate(`(()=>{
        const value=window.__startupAPI.status();
        return value.phase==='playing'&&value.ready&&value.wallpaper?.reason?value:false;
      })()`), 12000, 'CSP wallpaper failure with animation ready');
      assert.equal(state.wallpaper.applied, false);
      assert.equal(state.wallpaper.reason, expectedReason);
      assert.equal(state.ready, true, 'wallpaper failure does not impersonate animation readiness');
      assert.equal(await cdp.evaluate('!!window.__azhouWallpaper'), false);
      assert.equal(await cdp.evaluate('document.querySelectorAll("#azhou-wallpaper-style").length'), 0);
      return { phase: state.phase, ready: state.ready, wallpaper: state.wallpaper };
    });
  }

  await navigate('/fixture.html');
  await check('compiled native restore removes active startup and wallpaper while preserving the saved value', async () => {
    await until(() => cdp.evaluate(`(()=>{const state=window.__startupAPI?.status();return state?.phase==='playing'&&state.ready&&state.wallpaper.applied?state:false;})()`),
      10000, 'active controller and wallpaper for native restore');
    await cdp.evaluate("window.__fixtureSavedValue='fixture-saved-wallpaper-strength-42'");
    const restored = await evaluateNativeHelper('restoreSource');
    assert.deepEqual(restored, { restored: true, applied: false, startup: true });
    const after = await cdp.evaluate(`({savedValue:window.__fixtureSavedValue,
      startup:Object.hasOwn(window.__fixtureHost,'__azhouStartup'),wallpaper:!!window.__azhouWallpaper,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper')})`);
    assert.deepEqual(after, { savedValue: 'fixture-saved-wallpaper-strength-42', startup: false,
      wallpaper: false, frameCount: 0, styleCount: 0, rootAttribute: null });
    return { restored, after };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  await check('the real installer warms both normalized images before ready and skip completes once through the default iframe mount', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI?.status();return value?.phase==='playing'&&value.ready?value:false;
    })()`), 15000, 'animation payload prepared through default iframe mount');
    const beforeSkip = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const doc=frame?.contentDocument,stage=doc?.querySelector('[data-agent-skin-stage]');
      return {frameCount:document.querySelectorAll('iframe[aria-label]').length,
        root:!!stage,prewarmed:stage?.dataset.prewarmed==='true',duration:stage?.dataset.duration,
        canvas:doc?.querySelector('canvas')?.dataset.coordinateSize,
        skip:!!doc?.querySelector('[data-agent-skin-skip]')};
    })()`);
    assert.deepEqual(beforeSkip, { frameCount: 1, root: true, prewarmed: true, duration: '12', canvas: '1536x1024', skip: true });
    await cdp.evaluate(`(()=>{
      const button=document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]');
      button.click();button.click();
    })()`);
    const completed = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI.status();return value.phase==='complete'&&!value.overlay?value:false;
    })()`), 5000, 'idempotent startup skip');
    assert.deepEqual(completed.completion, { cause: 'skip', beforeReady: false });
    assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0);
    return { readyRun: { runId: state.runId, phase: state.phase, ready: state.ready }, beforeSkip, completed: completed.completion };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&wallpaper-fail=1&wallpaper-hold=12');
  await check('real settings UI saves without replay and keeps conflict, preview, apply and disposal behavior', async () => {
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'actual animation play frame prepared with generated assets');
    assert.equal(initial.wallpaper.reason, 'disabled', 'generated defaults disable host wallpaper before settings are saved');
    const initialRun = await cdp.evaluate(`window.__startupAnimationRuns.at(-1)?.runId`);
    assert.equal(initialRun, initial.runId);
    assert.equal(await cdp.evaluate(`window.__startupAnimationRuns.at(-1)?.intent`), 'play');

    const childAPI = await cdp.evaluate(`(()=>{
      const accepted=window.__startupAPI.openSettings();
      const frame=document.querySelector('iframe[aria-label]');
      return {accepted,count:document.querySelectorAll('iframe[aria-label]').length,
        dialog:frame.contentDocument.querySelector('dialog')?.open===true,state:window.__startupAPI.status()};
    })()`);
    assert.equal(childAPI.accepted, true);
    assert.equal(childAPI.count, 1, 'opening through the public API does not replace the run');
    assert.equal(childAPI.dialog, true, 'the actual child settings dialog opens');
    assert.equal(childAPI.state.phase, 'settings');
    assert.equal(childAPI.state.runId, initial.runId);
    const unsavedDraft = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),doc=frame.contentDocument;
      const title=doc.querySelector('input[maxlength="16"]');
      title.value='Discard draft';title.dispatchEvent(new Event('input',{bubbles:true}));
      const strength=doc.querySelector('input[type="range"]');
      strength.value='42';strength.dispatchEvent(new Event('input',{bubbles:true}));
      return {title:title.value,strength:strength.value,hostWallpaper:!!window.__azhouWallpaper,
        wallpaper:window.__startupAPI.status().wallpaper};
    })()`);
    assert.deepEqual(unsavedDraft.wallpaper, { applied: false, reason: 'disabled', imageDecoded: false });
    assert.equal(unsavedDraft.hostWallpaper, false, 'editing the draft cannot apply a host wallpaper');
    const childCancel = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      frame.contentWindow.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true}));
      return window.__startupAPI.status();
    })()`);
    const childCancelled = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='complete'&&state.completion?.cause==='settings-cancel'?state:false;
    })()`), 5000, 'public API settings cancel');
    assert.equal(childCancel.runId, initial.runId);
    assert.deepEqual(childCancelled.completion, { cause: 'settings-cancel', beforeReady: false });
    assert.equal(await cdp.evaluate(`window.__startupAnimationRuns.length`), 1,
      'canceling an in-play draft does not create another animation run');

    const canceledEntry = await waitForAppearanceEntry('appearance entry is ready after canceling settings');
    assert.equal(canceledEntry.display, 'block');
    const appearanceClick = await clickAppearanceEntry();
    assert.equal(appearanceClick.focused, true);
    const settingsRun = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
      return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
    })()`), 15000, 'appearance button launches the actual settings-intent frame and opens its dialog');
    assert.ok(settingsRun.runId > initial.runId);
    assert.equal(await cdp.evaluate('window.__startupAnimationRuns.at(-1).intent'), 'settings');
    const settingsChrome = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      return {skipHidden:doc.querySelector('[data-agent-skin-skip]')?.hidden,
        stageHidden:doc.querySelector('[data-agent-skin-stage-text]')?.hidden,
        progressHidden:doc.querySelector('[data-agent-skin-progress]')?.hidden};
    })()`);
    assert.deepEqual(settingsChrome, { skipHidden: true, stageHidden: true, progressHidden: true },
      'settings intent hides playback-only skip and progress chrome');
    assert.equal(await cdp.evaluate('window.__fixtureWallpaperApplications || 0'), 0,
      'the settings-intent frame does not apply a fallback or draft wallpaper');
    const defaultPanel = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      return {title:doc.querySelector('input[maxlength="16"]').value,
        strength:doc.querySelector('input[type="range"]').value,
        wallpaper:window.__startupAPI.status().wallpaper};
    })()`);
    assert.equal(defaultPanel.title, 'Synthetic agent', 'the canceled draft was not persisted');
    assert.equal(defaultPanel.strength, '0');
    assert.deepEqual(defaultPanel.wallpaper, { applied: false, reason: 'disabled', imageDecoded: false });
    const previewLaunch = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const title=doc.querySelector('input[maxlength="16"]');
      title.value='Local draft';title.dispatchEvent(new Event('input',{bubbles:true}));
      const strength=doc.querySelector('input[type="range"]');
      strength.value='42';strength.dispatchEvent(new Event('input',{bubbles:true}));
      const tab=doc.querySelector('[data-agent-skin-settings-tab="startup"]');
      const launch=doc.querySelector('[data-agent-skin-preview-animation]');
      if(!tab||!launch)return {tabFound:!!tab,launchFound:!!launch};
      tab.click();launch.click();
      return {tabFound:true,launchFound:true};
    })()`);
    assert.deepEqual(previewLaunch, { tabFound: true, launchFound: true },
      'the actual settings page exposes the startup preview action');
    const previewOpen = await until(() => cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
      const preview=overlay?.querySelector('iframe[data-agent-skin-settings-preview-frame]');
      if(!overlay||!preview?.contentDocument?.querySelector('[data-agent-skin-stage]'))return false;
      const close=overlay.querySelector('button[data-agent-skin-settings-preview-close]');
      return {
        open:overlay.hidden!==true,settingsOpen:doc.querySelector('dialog[data-agent-skin-settings]')?.open===true,
        title:doc.querySelector('input[maxlength="16"]')?.value,
        previewStage:!!preview.contentDocument.querySelector('[data-agent-skin-stage]'),
        hasCloseButton:!!close,modal:overlay.getAttribute('role')==='dialog'&&overlay.getAttribute('aria-modal')==='true',
        runCount:window.__startupAnimationRuns.length,state:window.__startupAPI.status()};
    })()`), 15000, 'draft preview opens an isolated animation over settings');
    assert.equal(previewOpen.open, true);
    assert.equal(previewOpen.settingsOpen, true, 'animation preview leaves the settings draft open');
    assert.equal(previewOpen.title, 'Local draft');
    assert.equal(previewOpen.previewStage, true);
    assert.equal(previewOpen.hasCloseButton, true, 'the independent preview exposes a dismiss action');
    assert.equal(previewOpen.modal, true, 'the full-screen animation preview is exposed as a modal dialog');
    assert.equal(previewOpen.runCount, 2, 'draft preview does not create a host startup run');
    assert.equal(previewOpen.state.runId, settingsRun.runId);
    const manualPreviewOpenedAt = Date.now();

    await cdp.call('Page.bringToFront');
    const focusBoundaryBefore = await cdp.evaluate(`(()=>{
      const parentFrame=document.querySelector('iframe[aria-label]');
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const overlay=doc.querySelector('[data-agent-skin-settings-preview]');
      const close=overlay.querySelector('button[data-agent-skin-settings-preview-close]');
      parentFrame.focus();doc.defaultView.focus();
      close.focus();
      return {focusedClose:doc.activeElement===close,hasFocus:doc.hasFocus(),parentActive:document.activeElement===parentFrame};
    })()`);
    assert.equal(focusBoundaryBefore.focusedClose, true,
      'preview close control receives focus when the overlay opens: ' + JSON.stringify(focusBoundaryBefore));
    const tabDispatchStartedAt = Date.now();
    await dispatchTab();
    const forwardTabElapsedMs = Date.now() - tabDispatchStartedAt;
    const afterForwardTab = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const overlay=doc.querySelector('[data-agent-skin-settings-preview]');
      const active=doc.activeElement;
      const buttons=[...doc.querySelector('[data-agent-skin-settings] footer').querySelectorAll('button')];
      return {insideOverlay:!!overlay?.contains(active),isSave:active===buttons.at(-1),
        isCancel:active===buttons.at(-2),insideInert:!!active?.closest?.('[inert]'),tag:active?.tagName,hasFocus:doc.hasFocus(),
        topActiveIsSettingsFrame:document.activeElement===document.querySelector('iframe[aria-label]')};
    })()`);
    assert.equal(afterForwardTab.isSave, false, 'Tab cannot focus the obscured Save control');
    assert.equal(afterForwardTab.isCancel, false, 'Tab cannot focus the obscured Cancel control');
    assert.equal(afterForwardTab.insideInert, false, 'Tab cannot focus any inert setting behind the preview');
    const backwardTabStartedAt = Date.now();
    await dispatchTab(true);
    const backwardTabElapsedMs = Date.now() - backwardTabStartedAt;
    const afterBackwardTab = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const overlay=doc.querySelector('[data-agent-skin-settings-preview]');
      const active=doc.activeElement;
      const buttons=[...doc.querySelector('[data-agent-skin-settings] footer').querySelectorAll('button')];
      return {insideOverlay:!!overlay?.contains(active),isSave:active===buttons.at(-1),
        isCancel:active===buttons.at(-2),insideInert:!!active?.closest?.('[inert]'),tag:active?.tagName,hasFocus:doc.hasFocus(),
        topActiveIsSettingsFrame:document.activeElement===document.querySelector('iframe[aria-label]')};
    })()`);
    assert.equal(afterBackwardTab.isSave, false, 'Shift+Tab cannot focus the obscured Save control');
    assert.equal(afterBackwardTab.isCancel, false, 'Shift+Tab cannot focus the obscured Cancel control');
    assert.equal(afterBackwardTab.insideInert, false, 'Shift+Tab cannot focus any inert setting behind the preview');

    const beforeManualClose = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
      return {overlay:!!overlay?.isConnected,close:!!overlay?.querySelector('button[data-agent-skin-settings-preview-close]')};
    })()`);
    assert.equal(beforeManualClose.overlay && beforeManualClose.close, true,
      'preview remains open through the Tab and Shift+Tab checks ('
        + (Date.now() - manualPreviewOpenedAt) + ' ms): ' + JSON.stringify(beforeManualClose));
    const manualClose = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
      const close=overlay?.querySelector('button[data-agent-skin-settings-preview-close]');
      if(!close)return {clicked:false,overlayOpen:!!overlay?.isConnected};
      close.click();return {clicked:true,overlayOpen:overlay.isConnected};
    })()`);
    assert.equal(manualClose.clicked, true,
      'manual focus test closes its still-open preview after ' + (Date.now() - manualPreviewOpenedAt)
        + ' ms (Tab ' + forwardTabElapsedMs + ' ms, Shift+Tab ' + backwardTabElapsedMs + ' ms): '
        + JSON.stringify(manualClose));
    const previewClosed = await until(() => cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
      const title=doc?.querySelector('input[maxlength="16"]');
      const active=doc?.activeElement;
      return (!overlay||!overlay.isConnected||overlay.hidden===true)
        &&doc.querySelector('dialog[data-agent-skin-settings]')?.open===true
        ?{title:title?.value,focused:active===doc.querySelector('[data-agent-skin-preview-animation]'),
          activeTag:active?.tagName,activeMarker:active?.getAttribute?.('data-agent-skin-preview-animation'),
          activeLabel:active?.getAttribute?.('aria-label'),activeText:active?.textContent?.trim(),
          activeInSettings:!!active?.closest?.('[data-agent-skin-settings]'),activeConnected:active?.isConnected}:false;
    })()`), 5000, 'closing the draft preview returns to settings');
    assert.equal(previewClosed.title, 'Local draft', 'closing preview preserves the unsaved draft');
    assert.equal(previewClosed.focused, true,
      'closing preview returns focus to its launch button: ' + JSON.stringify(previewClosed));

    const naturalPreviewLaunch = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const tab=doc.querySelector('[data-agent-skin-settings-tab="startup"]');
      const launch=doc.querySelector('[data-agent-skin-preview-animation]');
      if(!tab||!launch)return {tabFound:!!tab,launchFound:!!launch};
      tab.click();launch.click();return {tabFound:true,launchFound:true};
    })()`);
    assert.deepEqual(naturalPreviewLaunch, { tabFound: true, launchFound: true });
    const naturalPreviewOpen = await until(() => cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
      const preview=overlay?.querySelector('iframe[data-agent-skin-settings-preview-frame]');
      if(!overlay||!preview?.contentDocument?.querySelector('[data-agent-skin-stage]'))return false;
      return {settingsOpen:doc.querySelector('dialog[data-agent-skin-settings]')?.open===true,
        runCount:window.__startupAnimationRuns.length,state:window.__startupAPI.status()};
    })()`), 15000, 'second draft preview becomes ready for a natural end');
    const naturalPreviewStartedAt = Date.now();
    for (const expectedStage of ['portrait', 'shutter']) {
      const previewLabel = await until(() => cdp.evaluate(`(()=>{
        const settings=document.querySelector('iframe[aria-label]')?.contentDocument;
        const frame=settings?.querySelector('iframe[data-agent-skin-settings-preview-frame]');
        const doc=frame?.contentDocument, stage=doc?.querySelector('[data-agent-skin-stage]');
        const label=doc?.querySelector('[data-agent-skin-stage-text]');
        if(stage?.dataset.stage!==${JSON.stringify(expectedStage)}||!label)return false;
        const progressNode=doc.querySelector('[data-agent-skin-progress]');
        const progress=progressNode?.textContent||'';
        if(stage.dataset.stage==='portrait'&&Number(progress.match(/(\\d+)%/)?.[1]||0)<93)return false;
        const style=frame.contentWindow.getComputedStyle(label);
        return {stage:stage.dataset.stage,opacity:style.opacity,display:style.display,
          live:label.getAttribute('aria-live'),text:label.textContent,progress,
          progressOpacity:frame.contentWindow.getComputedStyle(progressNode).opacity,
          progressRole:progressNode.getAttribute('role'),
          progressValue:progressNode.getAttribute('aria-valuenow')};
      })()`), 15000, `settings preview reaches ${expectedStage}`);
      assert.equal(previewLabel.opacity, '0',
        `${expectedStage} status must not cover the artwork subtitle in the real settings preview`);
      assert.notEqual(previewLabel.display, 'none', 'the live status must remain accessible');
      assert.equal(previewLabel.live, 'polite');
      assert.ok(previewLabel.text);
      assert.equal(previewLabel.progressOpacity, '0', 'numeric progress must not overlap the canvas title');
      assert.equal(previewLabel.progressRole, 'progressbar', 'progress remains available to assistive technology');
      assert.equal(Number(previewLabel.progressValue), Number(previewLabel.progress.match(/(\d+)%/)?.[1]));
    }
    const naturalPreviewClosed = await until(() => cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
      if(overlay?.isConnected&&overlay.hidden!==true)return false;
      const launch=doc?.querySelector('[data-agent-skin-preview-animation]');
      return {settingsOpen:doc?.querySelector('dialog[data-agent-skin-settings]')?.open===true,
        title:doc?.querySelector('input[maxlength="16"]')?.value,
        focused:doc?.activeElement===launch,runCount:window.__startupAnimationRuns.length,
        state:window.__startupAPI.status()};
    })()`), 18000, 'the full-duration animation preview ends naturally');
    const naturalPreviewElapsedMs = Date.now() - naturalPreviewStartedAt;
    assert.ok(naturalPreviewElapsedMs >= 11_000,
      'the second preview must play through its 12-second duration, elapsed ' + naturalPreviewElapsedMs + ' ms');
    assert.ok(naturalPreviewElapsedMs < 18_000,
      'the preview closes after natural completion rather than hanging, elapsed ' + naturalPreviewElapsedMs + ' ms');
    assert.equal(naturalPreviewOpen.settingsOpen, true, 'the natural preview begins over the open settings page');
    assert.equal(naturalPreviewClosed.settingsOpen, true,
      'natural preview completion leaves the parent settings dialog open');
    assert.equal(naturalPreviewClosed.title, 'Local draft',
      'natural preview completion preserves the settings draft');
    assert.equal(naturalPreviewClosed.focused, true,
      'natural preview completion returns focus to the preview action');
    assert.equal(naturalPreviewClosed.runCount, 2,
      'natural preview completion does not create a host startup run');
    assert.equal(naturalPreviewClosed.state.runId, settingsRun.runId,
      'natural preview completion leaves the settings run unchanged');
    assert.equal(await cdp.evaluate('window.__fixtureWallpaperApplications || 0'), 0,
      'naturally completing a preview never applies its draft wallpaper');
    assert.equal(await cdp.evaluate('window.__fixtureWallpaperApplications || 0'), 0,
      'previewing the draft never applies it to the workspace');
    assert.equal(await cdp.evaluate('window.__fixtureWallpaperApplications || 0'), 0,
      'editing an unopened run still has no host wallpaper side effect');

    const externalCommit = await cdp.evaluate(`(async()=>{
      const assets=window.__startupAnimationRuns[0].assets;
      const api=window.createImageSettings({document,Image,URL,indexedDB,performance,
        setTimeout:setTimeout.bind(window),clearTimeout:clearTimeout.bind(window)});
      try{
        const loaded=await api.load(assets);
        const saved=await api.save({...loaded.settings,introTitle:'External',wallpaperStrength:42});
        return {reason:loaded.reason,baseline:loaded.baseline,title:saved.introTitle,strength:saved.wallpaperStrength};
      }finally{api.dispose();}
    })()`);
    assert.equal(externalCommit.reason, '', 'an independent settings save succeeds');
    assert.equal(externalCommit.baseline, undefined, 'the independent save starts from defaults');
    assert.equal(externalCommit.title, 'External', 'the independent save commits its title');
    assert.equal(externalCommit.strength, 42, 'the independent save commits numeric wallpaper strength');
    const conflictSave = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const panel=doc?.querySelector('[data-agent-skin-settings]');
      const footer=panel?.querySelector('footer');
      const buttons=[...footer?.querySelectorAll('button')||[]];
      const save=buttons.find(button=>/保存|Save/i.test(button.textContent.trim()));
      if(!save)return {clicked:false,panel:!!panel,footer:!!footer,labels:buttons.map(button=>button.textContent.trim())};
      save.click();return {clicked:true,label:save.textContent.trim()};
    })()`);
    assert.equal(conflictSave.clicked, true,
      'settings save control is available for the concurrent-update check: ' + JSON.stringify(conflictSave));
    const conflictStatus = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const status=frame?.contentDocument.querySelector('[data-agent-skin-settings-status]');
      return status?.getAttribute('role')==='alert'?status.textContent:false;
    })()`), 10000, 'settings transaction reports a real concurrent update');
    const conflictState = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
      return {state:window.__startupAPI.status(),runCount:window.__startupAnimationRuns.length,
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        dialogOpen:doc?.querySelector('dialog')?.open,
        draftTitle:doc?.querySelector('input[maxlength="16"]')?.value||''};
    })()`);
    assert.equal(conflictState.state.phase, 'settings', 'conflicted settings remain in their settings run');
    assert.equal(conflictState.state.runId, settingsRun.runId, 'conflicted settings do not start a new run');
    assert.equal(conflictState.runCount, 2, 'failed save did not send settings-close or replay');
    assert.equal(conflictState.frameCount, 1, 'conflict keeps one settings frame mounted');
    assert.equal(conflictState.dialogOpen, true, 'conflict keeps the dialog open for correction');
    assert.match(conflictStatus,
      /(?:本页更改尚未保存.*关闭将丢弃.*复制.*重新打开.*新值|This page has unsaved changes.*Closing discards.*Copy.*Reopen settings.*new value)/i,
      'conflict status explains that closing discards the draft, copying preserves text, and reopening reads the external value');
    assert.equal(conflictState.draftTitle, 'Local draft', 'the conflicted draft remains available to copy');

    const conflictCancel = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const buttons=[...doc?.querySelector('[data-agent-skin-settings] footer')?.querySelectorAll('button')||[]];
      const cancel=buttons.find(button=>/取消|Cancel/i.test(button.textContent.trim()));
      if(!cancel)return {clicked:false,labels:buttons.map(button=>button.textContent.trim())};
      cancel.click();return {clicked:true,label:cancel.textContent.trim()};
    })()`);
    assert.equal(conflictCancel.clicked, true,
      'settings Cancel control is available after a conflict: ' + JSON.stringify(conflictCancel));
    const conflictCancelled = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();return state.phase==='complete'&&state.completion?.cause==='settings-cancel'?state:false;
    })()`), 5000, 'cancel after conflict keeps the external record and avoids replay');
    assert.equal(conflictCancelled.runId, settingsRun.runId, 'cancel after conflict closes without replay');

    const retryClick = await clickAppearanceEntry();
    assert.equal(retryClick.focused, true, 'the appearance entry remains focusable after conflict cancellation');
    const retrySettings = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
      return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
    })()`), 15000, 'appearance button reopens settings after the failed baseline is refreshed');
    assert.ok(retrySettings.runId > settingsRun.runId);
    const retryValues = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      return {title:doc.querySelector('input[maxlength="16"]').value,
        strength:doc.querySelector('input[type="range"]').value};
    })()`);
    assert.deepEqual(retryValues, { title: 'External', strength: '42' },
      'reopening discards the stale draft and reads the value committed by the other page');
    await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const title=doc.querySelector('input[maxlength="16"]');
      title.value='Saved title';title.dispatchEvent(new Event('input',{bubbles:true}));
      doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
    })()`);
    const applyFailure = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
      const status=doc?.querySelector('[data-agent-skin-settings-status]');
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      const startupNotice=entry?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-recovery]');
      return status?.textContent.includes('设置已保存，但背景应用失败')?{
        state:window.__startupAPI.status(),runCount:window.__startupAnimationRuns.length,
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        dialogOpen:doc.querySelector('dialog[data-agent-skin-settings]')?.open,
        title:doc.querySelector('input[maxlength="16"]')?.value,
        retry:doc.querySelector('footer button:last-child')?.textContent,
        applications:window.__fixtureWallpaperApplications||0,status:status.textContent,
        startupNoticeDisplay:getComputedStyle(startupNotice).display,entryDisplay:getComputedStyle(entry).display}:false;
    })()`), 15000, 'saved settings report a separate wallpaper application failure');
    assert.equal(applyFailure.state.phase, 'settings');
    assert.equal(applyFailure.state.runId, retrySettings.runId);
    assert.equal(applyFailure.runCount, 3, 'failed application does not replay startup animation');
    assert.equal(applyFailure.frameCount, 1);
    assert.equal(applyFailure.dialogOpen, true);
    assert.equal(applyFailure.title, 'Saved title', 'the committed fields remain visible after apply failure');
    assert.equal(applyFailure.retry, '重试应用');
    assert.equal(applyFailure.applications, 1);
    assert.equal(applyFailure.startupNoticeDisplay, 'none',
      'a settings-save failure stays in the settings panel and does not create a startup recovery notice');
    assert.equal(applyFailure.entryDisplay, 'none', 'the existing entry remains hidden while settings owns the page');

    await cdp.evaluate(`document.querySelector('iframe[aria-label]').contentDocument
      .querySelector('[data-agent-skin-settings] footer button:last-child').click()`);
    const savedRun = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='complete'&&state.completion?.cause==='settings-save'
        &&state.runId===${retrySettings.runId}&&window.__fixtureWallpaperApplications===2
        ?{state,run:window.__startupAnimationRuns.at(-1),frameCount:document.querySelectorAll('iframe[aria-label]').length}:false;
    })()`), 15000, 'retry applies the already-saved workspace background and closes without replay');
    assert.equal(savedRun.frameCount, 0);
    assert.equal(savedRun.run.intent, 'settings');
    assert.equal(savedRun.run.runId, retrySettings.runId);
    assert.equal(savedRun.state.wallpaper.applied, true);
    const startupNoticeAfterSettingsRetry = await cdp.evaluate(`(()=>{
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
      return {entryDisplay:getComputedStyle(entry).display,
        noticeDisplay:getComputedStyle(entry.shadowRoot.querySelector('[data-agent-skin-wallpaper-recovery]')).display};
    })()`);
    assert.deepEqual(startupNoticeAfterSettingsRetry, { entryDisplay: 'block', noticeDisplay: 'none' },
      'a successful settings retry leaves the normal entry and removes any startup failure notice');
    const settingsResources = await cdp.evaluate(`(()=>{
      const run=window.__startupAnimationRuns.find(item=>item.runId===${retrySettings.runId});
      return run.handle.preview.report().resources;
    })()`);
    for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
      assert.equal(settingsResources[resource], 0, 'saved settings release ' + resource + ' on close');
    }

    const persistedValues = await cdp.evaluate(`(async()=>{
      const assets=window.__startupAnimationRuns[0].assets;
      const api=window.createImageSettings({document,Image,URL,indexedDB,performance,
        setTimeout:setTimeout.bind(window),clearTimeout:clearTimeout.bind(window)});
      try { const loaded=await api.load(assets); return {title:loaded.settings.introTitle,strength:loaded.settings.wallpaperStrength}; }
      finally { api.dispose(); }
    })()`);
    assert.deepEqual(persistedValues, { title: 'Saved title', strength: 42 },
      'settings are persisted before wallpaper application succeeds');

    const savedSettingsRuns = [{ runId: savedRun.state.runId, intent: savedRun.run.intent,
      subtitle: 'Generated fixture only', applications: 2 }];
    const isNewSettingsRun = (state, previousRunId) => Number.isSafeInteger(state?.runId)
      && state.runId > previousRunId && ['loading', 'settings'].includes(state.phase);
    for (const phase of ['loading', 'settings', 'complete', 'failed']) {
      assert.equal(isNewSettingsRun({phase, runId: savedRun.state.runId}, savedRun.state.runId), false,
        'no-op and old-run observations cannot satisfy a new settings transition');
    }
    assert.equal(isNewSettingsRun({phase: 'complete', runId: savedRun.state.runId + 1}, savedRun.state.runId), false);
    assert.equal(isNewSettingsRun(null, savedRun.state.runId), false);
    for (const phase of ['loading', 'settings']) {
      assert.equal(isNewSettingsRun({phase, runId: savedRun.state.runId + 1}, savedRun.state.runId), true,
        'a new settings run can already be ready when the click is sampled');
    }
    let currentSettingsRunId = savedRun.state.runId;
    let expectedSubtitle = 'Generated fixture only';
    for (let cycle = 2; cycle <= 10; cycle++) {
      const entryBeforeOpen = await appearanceEntryMetrics();
      assert.equal(entryBeforeOpen?.display, 'block', 'appearance entry remains visible after save ' + cycle);
      assert.equal(entryBeforeOpen?.entryHit, true, 'appearance entry remains hit-testable after save ' + cycle);
      assert.equal(entryBeforeOpen?.buttonHit, true, 'appearance button remains hit-testable after save ' + cycle);
      const openedSettings = await clickAppearanceEntry();
      assert.ok(isNewSettingsRun(openedSettings?.state, currentSettingsRunId),
        'clicking the appearance entry starts a newer loading or already-ready settings run: ' + JSON.stringify(openedSettings));
      const nextSettings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const dialog=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog');
        return state.phase==='settings'&&state.runId>${currentSettingsRunId}&&dialog?.open?state:false;
      })()`), 10000, 'appearance entry opens settings before save ' + cycle);
      const openedValues = await cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        return {state:{phase:state.phase,runId:state.runId},
          title:doc.querySelector('input[maxlength="16"]').value,
          subtitle:doc.querySelector('textarea').value,
          strength:doc.querySelector('input[type="range"]').value};
      })()`);
      assert.deepEqual(openedValues, { state: { phase: 'settings', runId: nextSettings.runId },
        title: 'Saved title', subtitle: expectedSubtitle, strength: '42' },
      'each settings open reloads the committed record');
      const nextSubtitle = 'Generated replay ' + cycle;
      await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        const subtitle=doc.querySelector('textarea');
        subtitle.value=${JSON.stringify(nextSubtitle)};subtitle.dispatchEvent(new Event('input',{bubbles:true}));
        doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
      })()`);
      const nextSave = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='settings-save'
          &&state.runId===${nextSettings.runId}&&window.__fixtureWallpaperApplications===${cycle + 1}
          &&document.querySelectorAll('iframe[aria-label]').length===0
          ?{state,run:window.__startupAnimationRuns.at(-1)}:false;
      })()`), 15000, 'settings save ' + cycle + ' applies background without a playback run');
      assert.equal(nextSave.run.intent, 'settings');
      assert.equal(nextSave.state.runId, nextSettings.runId);
      assert.equal(await cdp.evaluate('window.__startupAnimationRuns.length'), cycle + 2,
        'each settings open creates one settings frame but save creates no playback frame');
      const released = await cdp.evaluate(`(()=>{
        const run=window.__startupAnimationRuns.find(item=>item.runId===${nextSettings.runId});
        return run.handle.preview.report().resources;
      })()`);
      for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
        assert.equal(released[resource], 0, 'settings save ' + cycle + ' releases ' + resource);
      }
      savedSettingsRuns.push({ runId: nextSave.state.runId, intent: nextSave.run.intent,
        subtitle: nextSubtitle, applications: cycle + 1, released });
      currentSettingsRunId = nextSave.state.runId;
      expectedSubtitle = nextSubtitle;
    }
    assert.equal(savedSettingsRuns.length, 10, 'ten settings changes applied without animation replay');
    const lateRun = currentSettingsRunId;
    const lateEntryMetrics = await appearanceEntryMetrics();
    assert.equal(lateEntryMetrics?.display, 'block', 'appearance entry remains visible before the pending-save check');
    assert.equal(lateEntryMetrics?.entryHit, true, 'appearance entry can be clicked before the pending-save check');
    assert.equal(lateEntryMetrics?.buttonHit, true, 'appearance button is the hit target before the pending-save check');
    const lateEntry = await clickAppearanceEntry();
    assert.ok(isNewSettingsRun(lateEntry?.state, lateRun),
      'clicking appearance starts a newer loading or already-ready settings run before the pending-save check');
    const clickedRunId = lateEntry.state.runId;
    const lateSettingsReady = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),dialog=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog');
      return state.phase==='settings'&&state.runId===${clickedRunId}&&dialog?.open?state:false;
    })()`), 10000, 'appearance entry opens settings before the held late background result');
    const lateSettings = lateSettingsReady;
    await cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      if(state.phase!=='settings'||state.runId!==${clickedRunId}||!doc?.querySelector('dialog')?.open)
        throw Error('clicked settings run must still own the open dialog before save');
      const subtitle=doc.querySelector('textarea');
      subtitle.value='Late wallpaper test';subtitle.dispatchEvent(new Event('input',{bubbles:true}));
      doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
    })()`);
    const lateApply = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='settings'&&state.runId===${lateSettings.runId}
        &&window.__fixtureWallpaperApplications===12&&typeof window.__releaseFixtureWallpaper==='function'
        ?{state,run:window.__startupAnimationRuns.at(-1),frameCount:document.querySelectorAll('iframe[aria-label]').length}:false;
    })()`), 15000, 'settings stays open while the saved background application is pending');
    assert.equal(lateApply.run.intent, 'settings');
    assert.equal(lateApply.run.runId, lateSettings.runId);
    assert.equal(lateApply.frameCount, 1);
    assert.equal(lateApply.state.runId, lateSettings.runId);
    assert.equal(await cdp.evaluate('window.__startupAnimationRuns.length'), 13,
      'the pending save does not create a playback animation');
    const secondSettingsResources = await cdp.evaluate(`(()=>{
      const run=window.__startupAnimationRuns.find(item=>item.runId===${lateSettings.runId});
      return run.handle.preview.report().resources;
    })()`);
    assert.equal(secondSettingsResources.liveRAF, 0,
      'the open settings frame does not keep a playback animation running while wallpaper application waits');
    await cdp.evaluate('window.__startupAPI.dispose()');
    await cdp.evaluate('window.__releaseFixtureWallpaper()');
    const afterLate = await cdp.evaluate(`(()=>{
      const held=window.__startupAnimationRuns.find(item=>item.runId===${lateSettings.runId});
      const resources=held.handle.preview.report().resources;
      const frame=document.querySelector('iframe[aria-label]');
      return {installed:Object.hasOwn(window,'__azhouStartup'),frameCount:frame?1:0,
        wallpaper:!!window.__azhouWallpaper,resources};
    })()`);
    assert.equal(afterLate.installed, false);
    assert.equal(afterLate.frameCount, 0);
    assert.equal(afterLate.wallpaper, false);
    for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
      assert.equal(afterLate.resources[resource], 0, 'disposed pending settings release ' + resource);
    }

    await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
    const busyRun = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'fresh actual animation for busy Escape and dispose check');
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    await until(() => cdp.evaluate(`document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog')?.open`),
      5000, 'public settings API opens the actual panel for busy Escape check');
    const busyStart = await cdp.evaluate(`(async()=>{
      const frame=document.querySelector('iframe[aria-label]'),win=frame.contentWindow,doc=frame.contentDocument;
      const proto=win.HTMLImageElement.prototype;
      let owner=proto,descriptor;
      while(owner&&!descriptor){descriptor=Object.getOwnPropertyDescriptor(owner,'src');owner=Object.getPrototypeOf(owner);}
      if(!descriptor?.set)throw new Error('image source setter unavailable in isolated Chrome');
      Object.defineProperty(proto,'src',{configurable:true,enumerable:descriptor.enumerable,
        get:descriptor.get,set(value){
          if(String(value).startsWith('blob:')){win.__heldSettingsDecode={image:this,onload:this.onload};return;}
          return descriptor.set.call(this,value);
        }});
      const canvas=doc.createElement('canvas');canvas.width=64;canvas.height=64;
      const context=canvas.getContext('2d');context.fillStyle='#f6a55a';context.fillRect(0,0,64,64);
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
      const file=new win.File([blob],'generated-busy.png',{type:'image/png'});
      const input=doc.querySelector('input[data-agent-skin-image-input="avatar"]');
      const transfer=new win.DataTransfer();transfer.items.add(file);input.files=transfer.files;
      input.dispatchEvent(new win.Event('change',{bubbles:true}));
      for(let attempt=0;attempt<30&&!win.__heldSettingsDecode;attempt++)
        await new Promise(resolve=>win.setTimeout(resolve,0));
      const disabled=input.disabled,open=doc.querySelector('dialog').open;
      const fileInputs=[...doc.querySelectorAll('input[type="file"]')];
      const footerButtons=[...doc.querySelectorAll('[data-agent-skin-settings] footer button')];
      const save=footerButtons.at(-1),cancel=footerButtons.at(-2);
      save.click();
      const escape=new win.KeyboardEvent('keydown',{key:'Escape',cancelable:true});
      win.dispatchEvent(escape);
      const held=win.__heldSettingsDecode;
      window.__releaseLateSettingsDecode=()=>held?.onload?.call(held.image);
      return {disabled,otherImportDisabled:fileInputs[1]?.disabled===true,saveDisabled:save.disabled,
        cancelDisabled:cancel.disabled,open,escapePrevented:escape.defaultPrevented,held:Boolean(held),
        runId:window.__startupAPI.status().runId};
    })()`);
    assert.equal(busyStart.disabled, true, 'an active import locks settings controls synchronously');
    assert.equal(busyStart.otherImportDisabled, true, 'a second image import is unavailable while busy');
    assert.equal(busyStart.saveDisabled, true, 'save is unavailable while import is busy');
    assert.equal(busyStart.cancelDisabled, true, 'local cancel is unavailable while import is busy');
    assert.equal(busyStart.open, true);
    assert.equal(busyStart.escapePrevented, true);
    assert.equal(busyStart.held, true, 'the generated import decoder is held for the late-callback check');
    assert.equal(busyStart.runId, busyRun.runId);
    const busyStillOpen = await cdp.evaluate(`({phase:window.__startupAPI.status().phase,runId:window.__startupAPI.status().runId,
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      dialogOpen:document.querySelector('iframe[aria-label]').contentDocument.querySelector('dialog')?.open})`);
    assert.equal(busyStillOpen.phase, 'settings');
    assert.equal(busyStillOpen.runId, busyRun.runId);
    assert.equal(busyStillOpen.frameCount, 1);
    assert.equal(busyStillOpen.dialogOpen, true, 'Esc cannot cancel while a child image operation is busy');
    await cdp.evaluate('window.__startupAPI.dispose()');
    const busyResources = await cdp.evaluate('window.__startupAnimationRuns.at(-1).handle.preview.report().resources');
    const lateImportAfterDispose = await cdp.evaluate(`(()=>{
      const invoked=typeof window.__releaseLateSettingsDecode==='function';
      window.__releaseLateSettingsDecode?.();
      const frame=document.querySelector('iframe[aria-label]');
      return {invoked,installed:Object.hasOwn(window,'__azhouStartup'),frameCount:frame?1:0,
        animationRunCount:window.__startupAnimationRuns.length};
    })()`);
    assert.equal(lateImportAfterDispose.invoked, true);
    assert.equal(lateImportAfterDispose.installed, false);
    assert.equal(lateImportAfterDispose.frameCount, 0);
    for (const resource of ['liveImages','liveBitmaps','liveCanvases','livePaths','liveRAF','liveObjectURLs']) {
      assert.equal(busyResources[resource], 0, 'disposed busy-import frame releases ' + resource);
    }
    const lateSettingsImage = { removed: lateImportAfterDispose.frameCount === 0,
      apiRemoved: !lateImportAfterDispose.installed, callbackInvoked: lateImportAfterDispose.invoked };
    assert.equal(lateSettingsImage.removed, true);
    assert.equal(lateSettingsImage.apiRemoved, true);
    return { initialRun: initial.runId, childAPI: { phase: childAPI.state.phase, runId: childAPI.state.runId },
      childCancelled: childCancelled.completion, settingsRun: settingsRun.runId,
      externalCommit, conflict: { status: conflictStatus, runId: conflictState.state.runId,
        runCount: conflictState.runCount }, applyFailure: { status: applyFailure.status,
        retry: applyFailure.retry, saved: true }, savedSettings: { runId: savedRun.state.runId,
        wallpaper: savedRun.state.wallpaper, released: settingsResources },
      persistedValues, savedSettingsRuns, lateRun: lateSettings.runId, afterLate,
      busyEscape: { runId: busyRun.runId, busyStart, stillOpen: busyStillOpen,
        lateSettingsImage, released: busyResources, afterDispose: lateImportAfterDispose },
      preview: { manualClosed: manualClose.clicked, forwardTab: afterForwardTab,
        backwardTab: afterBackwardTab, naturalElapsedMs: naturalPreviewElapsedMs,
        naturalClosed: naturalPreviewClosed.focused },
      pendingSettingsResources: secondSettingsResources };
  });

  await cdp.evaluate('window.__startupAPI?.dispose()');
  await cdp.evaluate(`new Promise((resolve,reject)=>{
    const request=indexedDB.deleteDatabase('azhou-codex-startup');
    request.onsuccess=()=>resolve(true);request.onerror=()=>reject(request.error);
    request.onblocked=()=>reject(new Error('fixture settings database remained open before the default-assets check'));
  })`);
  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  await check('official language and theme update the active animation and draft without adding preferences', async () => {
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      const frame=document.querySelector('iframe[title="阿舟启动动画"]');
      return state?.phase==='playing'&&state.ready&&frame?{state,frameCount:document.querySelectorAll('iframe').length}:false;
    })()`), 15000, 'localized startup frame ready for official appearance changes');
    const before = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="阿舟启动动画"]'),doc=frame.contentDocument;
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),button=entry.shadowRoot.querySelector('button');
      const report=window.__startupAnimationRuns.at(-1).handle.preview.report();
      return {runId:window.__startupAPI.status().runId,frameTitle:frame.title,frameAria:frame.getAttribute('aria-label'),
        frameSpecAppearance:window.__startupAnimationRuns.at(-1).appearance,
        locale:doc.documentElement.lang,theme:doc.documentElement.dataset.theme,
        stageLabel:doc.querySelector('[data-agent-skin-stage]').getAttribute('aria-label'),
        entryText:button.textContent,entryAria:button.getAttribute('aria-label'),
        entryTitle:button.title,report,drawnText:frame.contentWindow.__fixtureAnimationTextDraws||[]};
    })()`);
    assert.equal(before.frameSpecAppearance.locale, 'zh-CN');
    assert.equal(before.locale, 'zh-CN');
    assert.equal(before.theme, 'dark');
    assert.equal(before.frameTitle, '阿舟启动动画');
    assert.equal(before.frameAria, '阿舟启动动画');
    assert.equal(before.stageLabel, '阿舟启动动画');
    assert.equal(before.entryText, '阿舟外观');
    assert.equal(before.entryAria, '阿舟外观');
    assert.equal(before.entryTitle, '打开主题与外观');
    assert.ok(before.drawnText.includes('Synthetic agent'), 'explicit asset title remains in the identity canvas');
    assert.ok(before.drawnText.includes('SYNTHETIC / TEST'), 'explicit asset caption remains in the identity canvas');

    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="阿舟启动动画"]');
      return window.__startupAPI.status().phase==='settings'
        &&frame?.contentDocument.querySelector('[data-agent-skin-settings]')?.open===true;
    })()`), 5000, 'actual settings dialog opens in the current play run');
    const draftBefore = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[title="阿舟启动动画"]').contentDocument;
      const title=doc.querySelector('[data-agent-skin-settings] input[maxlength="16"]');
      const strength=doc.querySelector('[data-agent-skin-settings] input[type="range"]');
      title.value='Draft survives';title.dispatchEvent(new Event('input',{bubbles:true}));
      strength.value='33';strength.dispatchEvent(new Event('input',{bubbles:true}));
      return {title:title.value,strength:strength.value,heading:doc.querySelector('[data-agent-skin-settings] h2').textContent,
        titleLabelText:title.labels?.[0]?.textContent.trim()||'',titleLabelCount:title.labels?.length||0};
    })()`);
    assert.equal(draftBefore.title, 'Draft survives');
    assert.equal(draftBefore.strength, '33');
    assert.equal(draftBefore.heading, '阿舟 · 主题与外观');
    assert.equal(draftBefore.titleLabelText, '启动标题（最多 16 个字符）');
    assert.equal(draftBefore.titleLabelCount, 1, 'the visible title label remains associated with its text input');

    await cdp.evaluate(`(()=>{
      const root=document.documentElement;
      window.__fixtureHost.CSS=window.CSS;
      root.lang='en-US';root.dataset.theme='light';
      root.style.setProperty('--color-surface','#f8fafc');
      root.style.setProperty('--color-text-primary','#172033');
      root.style.setProperty('--color-text-secondary','#536176');
      root.style.setProperty('--color-border','#cbd5e1');
    })()`);
    const updated = await until(() => cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="Azhou startup animation"]'),doc=frame?.contentDocument;
      const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),button=entry?.shadowRoot?.querySelector('button');
      const dialog=doc?.querySelector('[data-agent-skin-settings]'),title=dialog?.querySelector('input[maxlength="16"]');
      const titleLabelText=title?.labels?.[0]?.textContent.trim()||'';
      if(!frame||frame.title!=='Azhou startup animation'||doc.documentElement.lang!=='en'
        ||doc.documentElement.dataset.theme!=='light'||dialog?.querySelector('h2')?.textContent!=='Azhou · Theme & Appearance'
        ||titleLabelText!=='Startup title (up to 16 characters)')return false;
      return {runId:window.__startupAPI.status().runId,phase:window.__startupAPI.status().phase,
        frameCount:document.querySelectorAll('iframe').length,runCount:window.__startupAnimationRuns.length,
        frameTitle:frame.title,frameAria:frame.getAttribute('aria-label'),locale:doc.documentElement.lang,
        theme:doc.documentElement.dataset.theme,colorScheme:doc.documentElement.style.colorScheme,
        stage:window.__startupAnimationRuns.at(-1).handle.preview.report().stage,
        colors:Object.fromEntries(['surface','text','muted','border'].map(key=>[key,
          doc.documentElement.style.getPropertyValue('--agent-skin-'+key)])),
        entryText:button.textContent,entryAria:button.getAttribute('aria-label'),entryTitle:button.title,
        rootAria:doc.querySelector('[data-agent-skin-stage]').getAttribute('aria-label'),
        stageText:doc.querySelector('[data-agent-skin-stage-text]').textContent,
        heading:dialog.querySelector('h2').textContent,title:title.value,strength:dialog.querySelector('input[type="range"]').value,
        titleLabelText,titleLabelCount:title.labels?.length||0,settingsText:dialog.textContent,
        drawnText:frame.contentWindow.__fixtureAnimationTextDraws||[],
        recordKeys:Object.keys(window.__startupAnimationRuns.at(-1).assets).sort()};
    })()`), 5000, 'official host locale/theme observer updates the current overlay and settings draft');
    assert.equal(updated.runId, before.runId);
    assert.equal(updated.phase, 'settings');
    assert.equal(updated.frameCount, 1);
    assert.equal(updated.runCount, 1);
    assert.equal(updated.frameAria, 'Azhou startup animation');
    assert.equal(updated.locale, 'en');
    assert.equal(updated.theme, 'light');
    assert.equal(updated.colorScheme, 'light');
    assert.deepEqual(updated.colors, {
      surface: '#f8fafc', text: '#172033', muted: '#536176', border: '#cbd5e1',
    });
    assert.equal(updated.entryText, 'Azhou Appearance');
    assert.equal(updated.entryAria, 'Azhou Appearance');
    assert.equal(updated.entryTitle, 'Open theme and appearance');
    assert.equal(updated.rootAria, 'Azhou startup animation');
    const englishStages = {
      pulse: 'The lab is lighting up', identity: 'Azhou is setting up the workspace',
      dispersing: 'The portrait and text are spreading into line art',
      scattered: 'The line art is gathering', drawing: 'Azhou and the background are appearing',
      colorize: 'Color is being added to the scene', portrait: 'Azhou is finishing the scene',
      shutter: 'The animation is almost finished', complete: 'Finished',
    };
    assert.equal(updated.stageText, englishStages[updated.stage]);
    assert.equal(updated.heading, 'Azhou · Theme & Appearance');
    assert.equal(updated.title, 'Draft survives');
    assert.equal(updated.strength, '33');
    assert.equal(updated.titleLabelText, 'Startup title (up to 16 characters)');
    assert.equal(updated.titleLabelCount, 1, 'the localized visible label remains associated with its text input');
    assert.ok(updated.drawnText.includes('Synthetic agent'), 'appearance changes preserve and redraw explicit default text');
    const inheritedSettings = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[title="Azhou startup animation"]').contentDocument;
      const value=key=>doc.querySelector('[data-agent-skin-setting-value="'+key+'"]').textContent;
      return {theme:value('theme'),locale:value('locale'),
        sections:[...doc.querySelectorAll('[data-agent-skin-settings-section]')].map(el=>el.dataset.agentSkinSettingsSection),
        preferenceControls:doc.querySelectorAll('select:not([data-agent-skin-theme-choice]):not([data-agent-skin-theme-alpha-mode]):not([data-agent-skin-preset-list]),input[name="theme"],input[name="locale"],input[name="reducedMotion"]').length,
        workspaceThemeControls:doc.querySelectorAll('select[data-agent-skin-theme-choice],select[data-agent-skin-theme-alpha-mode]').length,
        directoryControls:doc.querySelectorAll('select[data-agent-skin-preset-list]').length};
    })()`);
    assert.deepEqual(inheritedSettings, { theme: 'Light', locale: 'en',
      sections: ['workspace', 'startup', 'about'], preferenceControls: 0, workspaceThemeControls: 2, directoryControls: 1 });
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await until(() => cdp.evaluate(`document.querySelector('iframe[title="Azhou startup animation"]').contentDocument
      .querySelector('[data-agent-skin-setting-value="reducedMotion"]').textContent==='On'`), 5000, 'system motion readout')
      .catch(async error => { throw new Error(error.message + ': ' + JSON.stringify(await cdp.evaluate(`({
        outer:matchMedia('(prefers-reduced-motion: reduce)').matches,
        inner:document.querySelector('iframe').contentWindow.matchMedia('(prefers-reduced-motion: reduce)').matches,
        reduced:window.__startupAnimationRuns.at(-1).handle.preview.report().reduced,
        readout:document.querySelector('iframe').contentDocument.querySelector('[data-agent-skin-setting-value="reducedMotion"]').textContent})`))); });
    await cdp.call('Emulation.setEmulatedMedia', { features: [] });
    assert.equal(updated.recordKeys.some(key => key === 'locale' || key === 'theme'), false,
      'appearance preferences are absent from the animation assets record shape');

    const settingsAPI = await cdp.evaluate(`(async()=>{
      const frame=document.querySelector('iframe[title="Azhou startup animation"]');
      const win=frame.contentWindow;
      const api=window.createImageSettings({document:frame.contentDocument,Image:win.Image,URL:win.URL,
        indexedDB:win.indexedDB,performance:win.performance,setTimeout:win.setTimeout.bind(win),
        clearTimeout:win.clearTimeout.bind(win)});
      try{
        const result=await api.load(window.__startupAnimationRuns.at(-1).assets);
        return {keys:Object.keys(result.settings).sort(),baseline:result.baseline};
      }finally{api.dispose();}
    })()`);
    assert.equal(settingsAPI.baseline, undefined);
    assert.equal(settingsAPI.keys.some(key => key === 'locale' || key === 'theme'), false,
      'the IndexedDB settings schema does not persist language or theme preferences');
    await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[title="Azhou startup animation"]');
      [...frame.contentDocument.querySelectorAll('[data-agent-skin-settings] footer button')]
        .find(button=>button.textContent.trim()==='Cancel')?.click();
    })()`);
    const afterCancel = await cdp.evaluate('window.__startupAPI.status()');
    assert.equal(afterCancel.runId, before.runId);
    assert.equal(afterCancel.phase, 'complete');
    return { initial: { runId: before.runId, locale: before.locale, theme: before.theme,
      entryAria: before.entryAria }, updated: { runId: updated.runId, phase: updated.phase,
      locale: updated.locale, theme: updated.theme, colors: updated.colors,
      draft: { title: updated.title, strength: updated.strength }, frameCount: updated.frameCount,
      runCount: updated.runCount }, customText: ['Synthetic agent', 'SYNTHETIC / TEST'],
      settingsKeys: settingsAPI.keys, canceledRunId: afterCancel.runId };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&settings-open-pending=1');
  await check('IDB open and get pending do not open settings from key events and Escape remains safe', async () => {
    const exercisePendingLoad = async kind => {
      if (kind === 'get') await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&settings-get-pending=1');
      const pending = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='loading'&&window.__fixtureIDBStage==='${kind==='open'?'open':'get'}'
          ?{state,stage:window.__fixtureIDBStage}:false;
      })()`), 10000, kind + ' request remains pending during startup load');
      const keys = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const parentEvent=new KeyboardEvent('keydown',{key:'b',metaKey:true,altKey:true,cancelable:true});
        window.dispatchEvent(parentEvent);
        const parentAfter=window.__startupAPI.status();
        const childEvent=new frame.contentWindow.KeyboardEvent('keydown',{key:'b',metaKey:true,altKey:true,cancelable:true});
        frame.contentWindow.dispatchEvent(childEvent);
        const childAfter=window.__startupAPI.status();
        const childDialog=frame.contentDocument.querySelector('dialog');
        const parentEscape=new KeyboardEvent('keydown',{key:'Escape',cancelable:true});
        window.dispatchEvent(parentEscape);
        const parentEscapeAfter=window.__startupAPI.status();
        return {parentPrevented:parentEvent.defaultPrevented,parentRunId:parentAfter.runId,
          parentPhase:parentAfter.phase,childPrevented:childEvent.defaultPrevented,
          childRunId:childAfter.runId,childPhase:childAfter.phase,dialogOpen:childDialog?.open===true,
          frameCount:document.querySelectorAll('iframe[aria-label]').length,
          parentEscapePrevented:parentEscape.defaultPrevented,parentEscapePhase:parentEscapeAfter.phase,
          parentEscapeRunId:parentEscapeAfter.runId};
      })()`);
      assert.equal(keys.parentPrevented, false, 'the parent key event has no settings action before resources are ready');
      assert.equal(keys.parentPhase, 'loading');
      assert.equal(keys.parentRunId, pending.state.runId);
      assert.equal(keys.childPrevented, false, 'the child key event has no settings action');
      assert.equal(keys.childPhase, 'loading');
      assert.equal(keys.childRunId, pending.state.runId);
      assert.equal(keys.dialogOpen, false);
      assert.equal(keys.frameCount, 1);
      assert.equal(keys.parentEscapePrevented, false, 'the parent has no Escape action during a pending load');
      assert.equal(keys.parentEscapePhase, 'loading');
      assert.equal(keys.parentEscapeRunId, pending.state.runId);

      const childEscape = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const event=new frame.contentWindow.KeyboardEvent('keydown',{key:'Escape',cancelable:true});
        frame.contentWindow.dispatchEvent(event);
        return {prevented:event.defaultPrevented,state:window.__startupAPI.status()};
      })()`);
      const ended = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='skip'&&!state.overlay?state:false;
      })()`), 5000, kind + ' child Escape completes the pending run once');
      assert.equal(childEscape.prevented, true);
      assert.equal(ended.runId, pending.state.runId);
      assert.equal(await cdp.evaluate('window.__startupAnimationRuns.length'), 1,
        kind + ' pending load does not start a duplicate run');
      assert.equal(await cdp.evaluate('document.querySelectorAll("iframe[aria-label]").length'), 0);
      if (kind === 'get') {
        await until(() => cdp.evaluate('window.__fixtureIDBAbortCount > 0'), 1000,
          'disposing the pending get aborts its readonly transaction');
      }
      await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,100))');
      const final = await cdp.evaluate(`({state:window.__startupAPI.status(),runs:window.__startupAnimationRuns.length,
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        stage:window.__fixtureIDBStage,aborts:window.__fixtureIDBAbortCount||0})`);
      assert.equal(final.state.phase, 'complete', 'late storage callbacks cannot revive the dismissed run');
      assert.equal(final.runs, 1);
      assert.equal(final.frameCount, 0);
      return { pending, keys, childEscape: { prevented: childEscape.prevented,
        cause: ended.completion, abortCount: final.aborts }, final: final.state.phase };
    };
    const open = await exercisePendingLoad('open');
    const get = await exercisePendingLoad('get');
    return { open, get };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1');
  await check('a top-level page refresh reloads committed settings fields from IndexedDB', async () => {
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'startup play is ready before saving refresh fields');
    const fields = { introTitle: 'Refresh title', introCaption: 'REFRESH / PERSISTED',
      artworkSubtitle: 'Synthetic settings after top-level reload', wallpaperStrength: 19 };
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true,
      'the supported PageController API opens settings during playback');
    await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      const dialog=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('dialog');
      return state.phase==='settings'&&dialog?.open?state:false;
    })()`), 5000, 'settings dialog opens before the committed reload setup');
    await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const textFields=[doc.querySelector('input[maxlength="16"]'),doc.querySelector('input[maxlength="48"]')];
      for(const [control,value] of [[textFields[0],${JSON.stringify(fields.introTitle)}],
        [textFields[1],${JSON.stringify(fields.introCaption)}],
        [doc.querySelector('textarea'),${JSON.stringify(fields.artworkSubtitle)}]]){
        control.value=value;control.dispatchEvent(new Event('input',{bubbles:true}));
      }
      const strength=doc.querySelector('input[type="range"]');strength.value='${fields.wallpaperStrength}';
      strength.dispatchEvent(new Event('input',{bubbles:true}));
      doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
    })()`);
    const saved = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),run=window.__startupAnimationRuns.at(-1);
      return state.phase==='complete'&&state.completion?.cause==='settings-save'
        &&state.runId===${initial.runId}&&document.querySelectorAll('iframe[aria-label]').length===0
        ?{state,run,runCount:window.__startupAnimationRuns.length}:false;
    })()`), 15000, 'the settings transaction commits and closes without a playback replay');
    assert.equal(saved.state.runId, initial.runId, 'saving closes the current settings draft in the same run');
    assert.equal(saved.runCount, 1, 'saving does not create a second startup run');
    assert.equal(saved.run.runId, initial.runId);
    const timeOriginBeforeReload = await cdp.evaluate('performance.timeOrigin');
    await cdp.call('Page.reload', { ignoreCache: true });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'top-level refresh completes');
    await until(() => cdp.evaluate('window.__startupInstallResult !== undefined'), 10000,
      'top-level refresh installs a fresh controller');
    const after = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status(),run=window.__startupAnimationRuns?.at(-1);
      return state?.phase==='playing'&&state.ready&&run?.intent==='play'?{state,run}:false;
    })()`), 15000, 'top-level refresh reloads persisted settings and prepares the startup');
    const timeOriginAfterReload = await cdp.evaluate('performance.timeOrigin');
    assert.notEqual(timeOriginAfterReload, timeOriginBeforeReload, 'Page.reload created a new top-level document');
    assert.equal(await cdp.evaluate('window.__startupAnimationRuns.length'), 1);
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true,
      'the refreshed PageController API opens the actual settings dialog');
    await until(() => cdp.evaluate(`document.querySelector('iframe[aria-label]')
      ?.contentDocument.querySelector('dialog')?.open`), 5000,
    'the refreshed top-level page opens its actual settings dialog for a field readback');
    const reloadedFields = await cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]').contentDocument;
      const textFields=[doc.querySelector('input[maxlength="16"]'),doc.querySelector('input[maxlength="48"]')];
      return {introTitle:textFields[0].value,
        introCaption:textFields[1].value,
        artworkSubtitle:doc.querySelector('textarea').value,
        wallpaperStrength:Number(doc.querySelector('input[type="range"]').value)};
    })()`);
    assert.deepEqual(reloadedFields, fields,
      'the new top-level document reads all committed fields from IndexedDB');
    return { savedWithoutReplay: { runId: saved.state.runId, completion: saved.state.completion,
      runCount: saved.runCount }, afterReload: {
      runId: after.run.runId, intent: after.run.intent, settingsCommitted: after.run.settingsCommitted,
    }, reloadedFields, timeOriginChanged: timeOriginAfterReload !== timeOriginBeforeReload };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&natural-settings-replay=1');
  await check('ten saved settings runs close without replay and release resources', async () => {
    const zeroResourceKeys = ['liveImages', 'liveBitmaps', 'liveCanvases', 'livePaths', 'liveRAF', 'liveObjectURLs'];
    const initial = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='playing'&&state.ready?state:false;
    })()`), 15000, 'actual animation is ready before the first settings save');
    let priorRunId = initial.runId;
    let expectedTitle = null;
    const cycles = [];

    for (let round = 1; round <= 10; round++) {
      let expectedRunId = priorRunId;
      if (round === 1) {
        assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true,
          'the public API opens the first settings draft during playback');
      } else {
        const entry = await waitForAppearanceEntry('appearance entry is ready before settings save ' + round);
        assert.equal(entry?.display, 'block', 'appearance entry is visible before settings save ' + round);
        assert.equal(entry?.entryHit, true, 'appearance entry is clickable before settings save ' + round);
        assert.equal(entry?.buttonHit, true, 'appearance button is clickable before settings save ' + round);
        const opened = await clickAppearanceEntry();
        assert.ok(['loading','settings'].includes(opened?.state?.phase), 'appearance click starts settings run ' + round);
        assert.ok(opened.state.runId > priorRunId, 'settings run ' + round + ' has a new run ID');
        expectedRunId = opened.state.runId;
      }
      const panel = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const frame=document.querySelector('iframe[aria-label]');
        const dialog=frame?.contentDocument.querySelector('dialog');
        const title=frame?.contentDocument.querySelector('input[maxlength="16"]')?.value;
        return state.phase==='settings'&&state.runId===${expectedRunId}&&dialog?.open?{state,title}:false;
      })()`), 10000, 'settings panel opens before save ' + round);
      if (expectedTitle === null) expectedTitle = panel.title;
      else assert.equal(panel.title, expectedTitle, 'settings run ' + round + ' reads the previous committed title');
      const nextTitle = 'Saved run ' + String(round).padStart(2, '0');
      const draft = await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        const title=doc.querySelector('input[maxlength="16"]');
        title.value=${JSON.stringify(nextTitle)};title.dispatchEvent(new Event('input',{bubbles:true}));
        return {value:title.value,buttonLabel:doc.querySelector('[data-agent-skin-settings] footer button:last-child')?.textContent.trim()};
      })()`);
      assert.equal(draft.value, nextTitle);
      assert.ok(/保存|save/i.test(draft.buttonLabel), 'settings exposes a save action without replay wording');
      await cdp.evaluate(`document.querySelector('iframe[aria-label]').contentDocument
        .querySelector('[data-agent-skin-settings] footer button:last-child').click()`);
      const closed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),run=window.__startupAnimationRuns.find(item=>item.runId===${expectedRunId});
        return state.phase==='complete'&&state.completion?.cause==='settings-save'&&state.runId===${expectedRunId}
          &&document.querySelectorAll('iframe[aria-label]').length===0
          ?{state,run,runCount:window.__startupAnimationRuns.length}:false;
      })()`), 15000, 'settings save ' + round + ' closes its draft without a playback replay');
      assert.equal(closed.runCount, round,
        'settings save ' + round + ' does not create another animation run');
      assert.equal(closed.run.runId, expectedRunId);
      assert.equal(closed.run.intent, round === 1 ? 'play' : 'settings');
      const released = await cdp.evaluate(`(()=>{
        const run=window.__startupAnimationRuns.find(item=>item.runId===${expectedRunId});
        return run.sampleDisposedResources().report.resources;
      })()`);
      for (const key of zeroResourceKeys) assert.equal(released[key], 0,
        'settings save ' + round + ' releases ' + key);
      assert.equal(released.framesPending, 0);
      cycles.push({round,runId:expectedRunId,introTitle:nextTitle,
        completion:closed.state.completion,runCount:closed.runCount,released});
      expectedTitle = nextTitle;
      priorRunId = expectedRunId;
    }
    assert.equal(cycles.length, 10);
    const persisted = await cdp.evaluate(`(async()=>{
      const assets=window.__startupAnimationRuns[0].assets;
      const api=window.createImageSettings({document,Image,URL,indexedDB,performance,
        setTimeout:setTimeout.bind(window),clearTimeout:clearTimeout.bind(window)});
      try{const loaded=await api.load(assets);return loaded.settings.introTitle;}
      finally{api.dispose();}
    })()`);
    assert.equal(persisted, expectedTitle, 'the final settings title remains committed in IndexedDB');
    return { firstRunId: cycles[0].runId, lastRunId: cycles.at(-1).runId, cycles, persisted };
  });

  await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&settings-blocked=1');
  await check('an unavailable settings database shows safe fallback status in playback and in the panel', async () => {
    const state = await until(() => cdp.evaluate(`(()=>{
      const value=window.__startupAPI?.status();
      const frame=document.querySelector('iframe[aria-label]');
      return value?.phase==='playing'&&value.ready&&frame?.contentDocument.querySelector('[data-agent-skin-settings-result]')?value:false;
    })()`), 15000, 'normal play shows a non-sensitive settings fallback status');
    const playbackNotice = await cdp.evaluate(`document.querySelector('iframe[aria-label]')
      .contentDocument.querySelector('[data-agent-skin-settings-result]').textContent`);
    const expectedPlaybackNotice = await cdp.evaluate(`window.createLocalization({locale:document.documentElement.lang})
      .t('settings.load.unavailable')`);
    assert.equal(playbackNotice, expectedPlaybackNotice);
    const opened = await cdp.evaluate(`(()=>{
      const frame=document.querySelector('iframe[aria-label]');
      const accepted=window.__startupAPI.openSettings();
      return {accepted,state:window.__startupAPI.status()};
    })()`);
    const panelStatus = await until(() => cdp.evaluate(`(()=>{
      const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
      const status=doc?.querySelector('[data-agent-skin-settings-status][role="alert"]');
      return status?.textContent?status.textContent:false;
    })()`), 5000, 'settings panel explains the unavailable database');
    assert.equal(opened.accepted, true);
    assert.equal(opened.state.phase, 'settings');
    assert.equal(opened.state.runId, state.runId);
    assert.equal(panelStatus, expectedPlaybackNotice,
      'the settings alert uses the same localized fallback message as the playback notice');
    assert.equal(panelStatus.includes('Synthetic'), false, 'status text does not expose stored profile values');
    return { phase: state.phase, runId: state.runId, playbackNotice, panelStatus };
  });

  await check('portrait identity and dispersing layouts keep legal titles and captions inside the registered canvas', async () => {
    try {
      const cases = [];
      for (const variant of identityVariants) {
        await cdp.call('Emulation.setDeviceMetricsOverride', {
          width: 1440, height: 900, screenWidth: 1440, screenHeight: 900,
          deviceScaleFactor: 1, mobile: false,
        });
        await cdp.call('Page.navigate', { url: pathToFileURL(join(variant.dir, 'index.html')).href });
        await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, variant.name + ' identity page load');
        await until(() => cdp.evaluate(`(()=>{
          const root=document.querySelector('[data-agent-skin-stage]');
          return root?.dataset.prewarmed==='true'&&window.launcherUI?.report()?true:false;
        })()`), 15000, variant.name + ' identity assets prewarm');
        await cdp.evaluate('window.launcherUI.pause()');
        await cdp.call('Emulation.setDeviceMetricsOverride', {
          width: 390, height: 844, screenWidth: 390, screenHeight: 844,
          deviceScaleFactor: 1, mobile: false,
        });
        await cdp.evaluate(`window.launcherUI.updateAppearance({locale:'en',theme:'light',colors:{
          surface:'#fafafa',text:'#202020',muted:'#606060',border:'#dddddd'}})`);
        const portrait = await until(() => cdp.evaluate(`(()=>{
          const viewport=window.launcherUI.report().viewport;
          return viewport.width===390&&viewport.height===844?viewport:false;
        })()`), 3000, variant.name + ' responsive portrait relayout');
        await cdp.evaluate('new Promise(resolve => { let settled = false; const settle = () => { if (settled) return; settled = true; resolve(); }; requestAnimationFrame(() => requestAnimationFrame(settle)); setTimeout(settle, 300); })');
        const controls = await cdp.evaluate(`(()=>{
          const bar=document.querySelector('#preview-controls'),rect=bar.getBoundingClientRect();
          const children=['#replay','#pause','#timeline','#elapsed'].map(selector=>{
            const node=document.querySelector(selector),bounds=node.getBoundingClientRect();
            return {selector,left:bounds.left,right:bounds.right,width:bounds.width,
              contained:bounds.left>=rect.left-1&&bounds.right<=rect.right+1};
          });
          return {visible:!bar.hidden,rect:{left:rect.left,right:rect.right,width:rect.width},
            clientWidth:bar.clientWidth,scrollWidth:bar.scrollWidth,children};
        })()`);
        assert.equal(controls.visible,true,'preview controls stay visible in the narrow viewport');
        assert.ok(controls.scrollWidth<=controls.clientWidth,
          'narrow English controls do not overflow their container: '+JSON.stringify(controls));
        assert.ok(controls.children.every(child=>child.contained),
          'every narrow English control stays inside the toolbar: '+JSON.stringify(controls));
        const variantStages = [];
        for (const [seconds, expectedStage] of [[1.65, 'identity'], [4.18, 'dispersing'], [4.74, 'scattered']]) {
          await cdp.evaluate(`window.launcherUI.seek(${seconds})`);
          const state = await cdp.evaluate(`(()=>{
            const canvas=document.querySelector('[data-agent-skin-canvas]');
            const report=window.launcherUI.report();
            const scale=Math.max(innerWidth/1536,innerHeight/1024);
            const offsetX=(innerWidth-1536*scale)/2,offsetY=(innerHeight-1024*scale)/2;
            const inViewport=(x,y)=>x*scale+offsetX>=0&&x*scale+offsetX<innerWidth
              &&y*scale+offsetY>=0&&y*scale+offsetY<innerHeight;
            const samples=[];
            for(let y=64;y<960;y+=8)for(let x=64;x<1472;x+=8){
              const px=Math.round((x*scale+offsetX)*devicePixelRatio),py=Math.round((y*scale+offsetY)*devicePixelRatio);
              if(px<0||py<0||px>=canvas.width||py>=canvas.height)continue;
              const data=canvas.getContext('2d').getImageData(px,py,1,1).data;
              if(data[0]>55||data[1]>55||data[2]>55)samples.push({x,y});
            }
            return {stage:report.stage,progress:report.animationProgress,viewport:report.viewport,
              sampleCount:samples.length,offscreenSamples:samples.filter(point=>!inViewport(point.x,point.y)).length,
              identityTextSamples:samples.filter(point=>point.y>=590&&point.y<850).length,
              crop:{scale,offsetX,offsetY},resources:report.resources};
          })()`);
          const screenshotFile = `identity-${variant.name}-${String(seconds).replace('.', 'p')}s.png`;
          const shot = await screenshot(screenshotFile);
          assert.equal(state.stage, expectedStage, variant.name + ' stage at ' + seconds);
          assert.ok(state.sampleCount > 5, variant.name + ' identity art remains visible at ' + seconds + ': ' + JSON.stringify(state));
          if (seconds === 1.65 && (variant.title || variant.caption)) {
            assert.ok(state.identityTextSamples > 5, variant.name + ' identity text remains visible within the portrait canvas: ' + JSON.stringify(state));
          }
          assert.equal(state.offscreenSamples, 0, variant.name + ' visible identity samples remain inside the portrait viewport: ' + JSON.stringify(state));
          assert.equal(state.resources.liveRAF, 0, variant.name + ' preview remains paused while seeking');
          variantStages.push({ seconds, ...state, screenshot: shot.file });
        }
        cases.push({ name: variant.name, titleCodeUnits: variant.title.length,
          captionCodeUnits: variant.caption.length, portrait, controls, stages: variantStages });
      }
      return { viewport: { width: 390, height: 844, dpr: 1 }, cases };
    } finally {
      await cdp.call('Emulation.clearDeviceMetricsOverride');
    }
  });

  await navigate('/fixture.html?animation=1&animation-hold=1&no-initial-wallpaper=1');
  await check('skip while decoded ImageBitmaps are pending completes before ready and closes late bitmaps', async () => {
    const held = await until(() => cdp.evaluate(`(()=>{
      const frame=window.__animationPendingFrame;
      return frame?.__fixtureHeldBitmapRequests>=2
        ?{requests:frame.__fixtureHeldBitmapRequests,releases:frame.__fixtureHeldBitmapReleases}:false;
    })()`), 10000, 'both real decoded animation bitmaps held before ready');
    const before = await cdp.evaluate(`({state:window.__startupAPI.status(),
      frameCount:document.querySelectorAll('iframe[aria-label]').length})`);
    assert.equal(before.state.phase, 'loading');
    assert.equal(before.state.ready, false);
    assert.equal(before.state.overlay, true);
    assert.equal(before.frameCount, 1);
    assert.equal(held.requests, 2);
    await cdp.evaluate(`(()=>{
      const button=document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]');
      button.click();button.click();
    })()`);
    const completed = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status();
      return state.phase==='complete'&&!state.overlay?state:false;
    })()`), 3000, 'early skip completes and removes the unready overlay');
    assert.equal(completed.ready, false);
    assert.deepEqual(completed.completion, { cause: 'skip', beforeReady: true });
    await until(() => cdp.evaluate('window.__animationPendingFrame.__fixtureHeldBitmapReleases===2'), 3000,
      'stale image bitmap results close after early completion');
    await delay(100);
    const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
      frameCount:document.querySelectorAll('iframe[aria-label]').length,
      requests:window.__animationPendingFrame.__fixtureHeldBitmapRequests,
      releases:window.__animationPendingFrame.__fixtureHeldBitmapReleases})`);
    assert.deepEqual(after.state.completion, completed.completion);
    assert.equal(after.state.ready, false, 'a late decode cannot emit ready after early completion');
    assert.equal(after.frameCount, 0);
    assert.equal(after.requests, after.releases);
    return { before: { phase: before.state.phase, ready: before.state.ready, held },
      completion: completed.completion, after: { phase: after.state.phase, ready: after.state.ready,
        frameCount: after.frameCount, requests: after.requests, releases: after.releases } };
  });

  await cdp.call('Page.addScriptToEvaluateOnNewDocument', { source: `(()=>{
    const prototype=window.MediaQueryList?.prototype;if(!prototype)return;
    const state={added:0,removed:0,active:0,windowResize:0,visualViewportResize:0,queryCount:0};
    const queries=[];
    window.addEventListener('resize',()=>state.windowResize++);
    window.visualViewport?.addEventListener('resize',()=>state.visualViewportResize++);
    Object.defineProperty(window,'__agentSkinResolutionWatch',{value:state,configurable:true});
    const matchMedia=window.matchMedia.bind(window);
    window.matchMedia=function(expression){
      const query=matchMedia(expression);
      if(String(expression).startsWith('(resolution:')){queries.push(query);state.queryCount++;}
      return query;
    };
    state.dispatchLatest=()=>queries.at(-1)?.dispatchEvent(new Event('change'))===true;
    const add=prototype.addEventListener,remove=prototype.removeEventListener;
    prototype.addEventListener=function(type,listener,options){
      if(type==='change'&&this.media?.startsWith('(resolution:')){state.added++;state.active++;}
      return add.call(this,type,listener,options);
    };
    prototype.removeEventListener=function(type,listener,options){
      if(type==='change'&&this.media?.startsWith('(resolution:')){state.removed++;state.active--;}
      return remove.call(this,type,listener,options);
    };
  })()` });
  await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
  await cdp.call('Page.navigate', { url: pathToFileURL(join(animationPreviewDir, 'index.html')).href });
  await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'synthetic Agent Skin preview load');
  const animationReady = await until(() => cdp.evaluate(`(()=>{
    const root=document.querySelector('[data-agent-skin-stage]');
    const report=window.launcherUI?.report();
    return window.launcherUI&&root?.dataset.prewarmed==='true'
      &&report.resources.liveImages+report.resources.liveBitmaps>0
      ?window.launcherUI.report():false;
  })()`), 15000, 'generated animation images prewarm through the local preview shell');
  await cdp.evaluate('window.launcherUI.pause()');

  await check('public preview report confirms static frame reuse and dynamic replay behavior', async () => {
    await cdp.evaluate('window.launcherUI.pause()');
    assert.equal(await cdp.evaluate('window.launcherUI.report().reduced'), false,
      'frame reuse assertions run with full motion explicitly enabled');
    const readReport = () => cdp.evaluate(`(()=>{
      const report=window.launcherUI.report();
      return {elapsed:report.elapsed,stage:report.stage,completed:report.completed,skipped:report.skipped,
        sceneRenderCount:report.jsFrame.sceneRenderCount,resources:report.resources};
    })()`);
    const seekAndRead = async seconds => {
      const result = await cdp.evaluate(`(()=>{
        const accepted=window.launcherUI.seek(${seconds});
        const report=window.launcherUI.report();
        return {accepted,elapsed:report.elapsed,stage:report.stage,
          sceneRenderCount:report.jsFrame.sceneRenderCount};
      })()`);
      assert.equal(result.accepted, true, 'the public preview seek remains available');
      return result;
    };
    // Sample the sequence in one browser task so unrelated async redraws cannot
    // land between a seek and the next frame-count comparison.
    const { initial, samples } = await cdp.evaluate(`(()=>{
      const initial={sceneRenderCount:window.launcherUI.report().jsFrame.sceneRenderCount};
      const samples=[1.8,2.4,3.7,4.8,4.95,5.2,6.2,9.0,9.3,10.8].map(seconds=>{
        const accepted=window.launcherUI.seek(seconds), report=window.launcherUI.report();
        return {accepted,elapsed:report.elapsed,stage:report.stage,sceneRenderCount:report.jsFrame.sceneRenderCount};
      });
      return {initial,samples};
    })()`);
    assert.ok(Number.isInteger(initial.sceneRenderCount), 'public report exposes canvas scene submissions');
    assert.ok(samples.every(sample => sample.accepted), 'all preview seeks remain available');
    const [identityFirst, identitySecond, identityThird, scatteredFirst, scatteredSecond,
      drawingFirst, drawingSecond, portraitBeforePlateau, portraitFirst, portraitSecond] = samples;
    assert.equal(identityFirst.stage, 'identity');
    assert.equal(identitySecond.sceneRenderCount, identityFirst.sceneRenderCount,
      'a static identity frame is submitted once while its stage and layout remain stable');
    assert.equal(identityThird.sceneRenderCount, identityFirst.sceneRenderCount);
    assert.equal(identityFirst.sceneRenderCount - initial.sceneRenderCount, 1);

    assert.equal(scatteredFirst.stage, 'scattered');
    assert.equal(scatteredFirst.sceneRenderCount, identityThird.sceneRenderCount + 1,
      'crossing to another static stage submits its changed frame once');
    assert.equal(scatteredSecond.sceneRenderCount, scatteredFirst.sceneRenderCount);

    assert.equal(drawingFirst.stage, 'drawing');
    assert.equal(drawingSecond.stage, 'drawing');
    assert.equal(drawingFirst.sceneRenderCount, scatteredSecond.sceneRenderCount + 1);
    assert.equal(drawingSecond.sceneRenderCount, drawingFirst.sceneRenderCount + 1,
      'animated drawing continues to submit changed frames');

    assert.equal(portraitBeforePlateau.stage, 'portrait');
    assert.equal(portraitFirst.stage, 'portrait');
    assert.equal(portraitSecond.stage, 'portrait');
    assert.equal(portraitBeforePlateau.sceneRenderCount, drawingSecond.sceneRenderCount + 1,
      'the portrait progress bar continues to render before it reaches 100%');
    assert.equal(portraitFirst.sceneRenderCount, portraitBeforePlateau.sceneRenderCount + 1,
      'the final progress value is rendered when the full-progress plateau begins');
    assert.equal(portraitSecond.sceneRenderCount, portraitFirst.sceneRenderCount,
      'the static full-progress portrait is reused through the end of the stage');

    await seekAndRead(5.5);
    const beforeSkip = await readReport();
    await cdp.evaluate('window.launcherUI.skip()');
    const afterSkip = await readReport();
    assert.equal(afterSkip.completed, true);
    assert.equal(afterSkip.skipped, true);
    assert.equal(afterSkip.stage, 'complete');
    assert.equal(afterSkip.sceneRenderCount, beforeSkip.sceneRenderCount,
      'explicit skip must not redraw a possibly broken final frame before releasing resources');
    for (const key of ['liveImages', 'liveBitmaps', 'liveCanvases', 'livePaths', 'liveRAF']) {
      assert.equal(afterSkip.resources[key], 0, `skip releases ${key}`);
    }

    await cdp.evaluate('window.launcherUI.updateAppearance({locale:"en"})');
    assert.match(await cdp.evaluate('document.getElementById("elapsed").textContent'), /12\.0 \/ 12\.0 s$/,
      'completed previews update time units even after releasing their canvas');

    assert.equal(await cdp.evaluate('window.launcherUI.replay()'), true);
    const replayStarted = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]');
      return root?.dataset.prewarmed==='true'&&root.dataset.playing==='true'
        ?window.launcherUI.report():false;
    })()`), 10000, 'preview replay after explicit skip without final rendering');
    await cdp.evaluate('window.launcherUI.pause()');
    assert.equal(replayStarted.completed, false);
    assert.ok(replayStarted.jsFrame.sceneRenderCount < afterSkip.sceneRenderCount,
      'replay starts a fresh canvas submission count');
    const replayScatterFirst = await seekAndRead(4.8);
    const replayScatterSecond = await seekAndRead(4.95);
    assert.equal(replayScatterFirst.stage, 'scattered');
    assert.equal(replayScatterSecond.sceneRenderCount, replayScatterFirst.sceneRenderCount,
      'static rendering reuse remains active after replay');

    return {
      counts: {
        identity: { submissions: identityFirst.sceneRenderCount - initial.sceneRenderCount, seeks: 3 },
        scattered: { submissions: scatteredSecond.sceneRenderCount - identityThird.sceneRenderCount, seeks: 2 },
        drawing: { submissions: drawingSecond.sceneRenderCount - scatteredSecond.sceneRenderCount, seeks: 2 },
        portrait: { submissions: portraitSecond.sceneRenderCount - drawingSecond.sceneRenderCount, seeks: 3 },
        skip: { noExtraFrameSubmitted: afterSkip.sceneRenderCount === beforeSkip.sceneRenderCount,
          releasedResources: afterSkip.resources },
        replay: { submissions: replayScatterSecond.sceneRenderCount - replayStarted.jsFrame.sceneRenderCount,
          stage: replayScatterSecond.stage },
      },
      measurement: 'sceneRenderCount counts JavaScript 2D-canvas renderScene submissions; it does not measure GPU or presented frames',
    };
  });

  const seekRaceCheck = 'public preview seek restores identity pixels after async backward bitmap resolution';
  let seekHarnessScriptIdentifier = '';
  if (!onlyChecks || onlyChecks.has(seekRaceCheck)) {
    const installedScript = await cdp.call('Page.addScriptToEvaluateOnNewDocument', { source: `(()=>{
      const nativeRAF=window.requestAnimationFrame.bind(window);
      const nativeCancel=window.cancelAnimationFrame.bind(window);
      const nativeBitmap=window.createImageBitmap.bind(window);
      const pendingFrames=new Map(),pendingBitmaps=[];
      let nextFrame=0,holdBitmaps=false;
      window.requestAnimationFrame=callback=>{const id=++nextFrame;pendingFrames.set(id,callback);return id;};
      window.cancelAnimationFrame=id=>{pendingFrames.delete(id);return nativeCancel(id);};
      window.createImageBitmap=(...args)=>holdBitmaps
        ?new Promise((resolve,reject)=>{
          const stableArgs=args.slice();
          if(stableArgs[0] instanceof HTMLCanvasElement){
            const source=stableArgs[0],snapshot=document.createElement('canvas');
            snapshot.width=source.width;snapshot.height=source.height;
            snapshot.getContext('2d').drawImage(source,0,0);
            stableArgs[0]=snapshot;
          }
          pendingBitmaps.push({args:stableArgs,resolve,reject});
        })
        :nativeBitmap(...args);
      window.__agentSkinPublicHarness={pendingFrames,pendingBitmaps,
        runNext(timestamp){const item=pendingFrames.entries().next().value;if(!item)return false;
          pendingFrames.delete(item[0]);item[1](timestamp);return true;},
        hold(){holdBitmaps=true;},
        async resolveBitmap(index){const item=pendingBitmaps[index];if(!item)return false;
          try{item.resolve(await nativeBitmap(...item.args));return true;}catch(error){item.reject(error);throw error;}},
        restore(){window.requestAnimationFrame=nativeRAF;window.cancelAnimationFrame=nativeCancel;window.createImageBitmap=nativeBitmap;},
      };
    })()` });
    seekHarnessScriptIdentifier = installedScript.identifier;
    await cdp.call('Page.navigate', { url: pathToFileURL(join(animationPreviewDir, 'index.html')).href });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'seek-race preview load');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'seek-race preview prewarm');
  }
  await check(seekRaceCheck, async () => {
    const pauseAtScattered = await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.launcherUI.resume();
      const advanced=window.__agentSkinPublicHarness.runNext(performance.now()+5080);
      window.launcherUI.pause();
      return {advanced,report:window.launcherUI.report()};
    })()`);
    assert.equal(pauseAtScattered.advanced, true, 'the actual public handle advances the captured natural frame');
    assert.ok(Math.abs(pauseAtScattered.report.elapsed - 5.08) <= 0.001,
      'the captured natural frame advances within 1 ms of the requested 5.08 seconds: '
        + pauseAtScattered.report.elapsed);
    assert.equal(pauseAtScattered.report.resources.liveBitmaps, 2,
      'natural playback releases the identity bitmap after entering scattered');
    await cdp.evaluate('window.__agentSkinPublicHarness.hold()');
    assert.equal(await cdp.evaluate('window.launcherUI.seek(1)'), true);
    assert.equal(await cdp.evaluate('window.launcherUI.seek(2)'), true);
    assert.equal(await cdp.evaluate('window.launcherUI.seek(8)'), true);
    const pending = await cdp.evaluate(`({count:window.__agentSkinPublicHarness.pendingBitmaps.length,
      elapsed:window.launcherUI.report().elapsed})`);
    assert.equal(pending.count, 2, 'both identity scrubs start a delayed bitmap request');
    assert.equal(pending.elapsed, 8, 'the latest public seek is visible before either bitmap completes');

    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(1)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterSecond = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterSecond.elapsed, 8, 'the newer delayed bitmap cannot overwrite seek(8)');
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterFirst = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterFirst.elapsed, 8, 'the older delayed bitmap cannot overwrite seek(8)');
    assert.equal(afterFirst.resources.liveBitmaps, 2, 'both stale seek bitmaps are closed exactly once');
    assert.equal(await cdp.evaluate('window.launcherUI.dispose()'), true);
    const disposed = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(disposed.elapsed, 8);
    for (const kind of ['Bitmaps', 'Canvases', 'Paths']) assert.equal(disposed.resources['live' + kind], 0);
    assert.equal(disposed.resources.liveRAF, 0);

    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'skip-race preview reload');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'skip-race preview prewarm');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.launcherUI.resume();
      window.__agentSkinPublicHarness.runNext(performance.now()+5080);window.launcherUI.pause();
      window.__agentSkinPublicHarness.hold();window.launcherUI.seek(1);window.launcherUI.skip();
    })()`);
    const skipped = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(skipped.completed, true);
    assert.equal(skipped.skipped, true);
    assert.equal(skipped.resources.liveBitmaps, 0);
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterSkippedLateResult = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterSkippedLateResult.elapsed, 12);
    assert.equal(afterSkippedLateResult.completed, true);
    assert.equal(afterSkippedLateResult.resources.liveBitmaps, 0, 'a late result cannot revive a skipped scene');

    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'dispose-race preview reload');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'dispose-race preview prewarm');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.launcherUI.resume();
      window.__agentSkinPublicHarness.runNext(performance.now()+5080);window.launcherUI.pause();
      window.__agentSkinPublicHarness.hold();window.launcherUI.seek(1);window.launcherUI.dispose();
    })()`);
    const beforeLateDisposeResult = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(beforeLateDisposeResult.resources.liveBitmaps, 0);
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterDisposedLateResult = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(afterDisposedLateResult.resources.liveBitmaps, 0, 'a late disposed result is closed without revival');
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'backward-restore preview reload');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'backward-restore preview prewarm');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();window.__agentSkinPublicHarness.hold();window.launcherUI.seek(6);
    })()`);
    const releasedAtSix = await cdp.evaluate('window.launcherUI.report()');
    assert.equal(releasedAtSix.stage, 'drawing');
    assert.equal(releasedAtSix.resources.liveBitmaps, 2,
      'entering drawing releases only the intermediate identity bitmap');
    await cdp.evaluate('window.launcherUI.seek(2.2)');
    const beforeIdentityBitmap = await animationPixelEvidence();
    assert.equal(beforeIdentityBitmap.stage, 'identity');
    assert.ok(beforeIdentityBitmap.identity.light > 40,
      'the identity canvas draws immediately from its retained canvas while the restored bitmap is pending: '
        + JSON.stringify(beforeIdentityBitmap.identity));
    assert.equal(await cdp.evaluate('window.__agentSkinPublicHarness.pendingBitmaps.length'), 1,
      'the backward seek has one held identity-bitmap request');
    await cdp.evaluate('window.__agentSkinPublicHarness.resolveBitmap(0)');
    await cdp.evaluate('new Promise(resolve=>setTimeout(resolve,0))');
    const afterIdentityBitmap = await animationPixelEvidence();
    assert.equal(afterIdentityBitmap.stage, 'identity');
    assert.equal(afterIdentityBitmap.sceneRenderCount, beforeIdentityBitmap.sceneRenderCount + 1,
      'resolving the restored bitmap invalidates the static key and redraws the identity frame');
    assert.deepEqual(afterIdentityBitmap.identity, beforeIdentityBitmap.identity,
      'the asynchronously restored bitmap preserves the actual rendered identity pixels');
    assert.equal(afterIdentityBitmap.resources.liveBitmaps, 3);
    return { scatteredResources: pauseAtScattered.report.resources, finalElapsed: afterFirst.elapsed,
      disposedResources: disposed.resources, skippedLateResources: afterSkippedLateResult.resources,
      disposedLateResources: afterDisposedLateResult.resources,
      backwardRestore: { releasedResources: releasedAtSix.resources,
        beforeResolution: { sceneRenderCount: beforeIdentityBitmap.sceneRenderCount, pixels: beforeIdentityBitmap.identity },
        afterResolution: { sceneRenderCount: afterIdentityBitmap.sceneRenderCount,
          liveBitmaps: afterIdentityBitmap.resources.liveBitmaps, pixels: afterIdentityBitmap.identity } } };
  });
  if (!onlyChecks || onlyChecks.has(seekRaceCheck)) {
    await cdp.call('Page.removeScriptToEvaluateOnNewDocument', { identifier: seekHarnessScriptIdentifier });
    await cdp.call('Page.navigate', { url: pathToFileURL(join(animationPreviewDir, 'index.html')).href });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'preview restore after seek test');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'preview restore after seek test prewarm');
  }

  await check('reduced motion is static or opacity-only from initial preference and after a phase-four toggle', async () => {
    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'reduced-motion preview load');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
      &&window.launcherUI?.report()?true:false`), 15000, 'reduced-motion preview prewarm');
    const initial = await cdp.evaluate(`({reduced:window.launcherUI.report().reduced,
      playing:document.querySelector('[data-agent-skin-stage]').dataset.playing})`);
    assert.equal(initial.reduced, true, 'the renderer reads the reduced preference before its first playback');
    assert.equal(await cdp.evaluate('window.launcherUI.pause()'), true);
    try {
    const traceAt = async seconds => cdp.evaluate(`(()=>{
      const context=document.querySelector('canvas[data-agent-skin-canvas]').getContext('2d');
      const proto=CanvasRenderingContext2D.prototype, names=['arc','beginPath','clearRect','drawImage','fill','fillRect',
        'fillText','lineTo','moveTo','rect','restore','rotate','save','scale','setTransform','stroke','strokeRect','translate'];
      const originals=new Map(),trace=[];
      for(const name of names){
        const original=proto[name];originals.set(name,original);
        proto[name]=function(...args){
          if(this.canvas?.hasAttribute('data-agent-skin-canvas'))
            trace.push({name,args:args.map(arg=>arg instanceof Path2D?'Path2D':typeof arg==='object'?arg?.constructor?.name:arg)});
          return original.apply(this,args);
        };
      }
      try{
        window.launcherUI.seek(${seconds});
        const shape=trace.map(({name,args})=>[name,args]);
        const report=window.launcherUI.report();
        return {report,shape};
      }finally{for(const [name,original] of originals)proto[name]=original;}
    })()`);
    const compareShape = async (name, first, second) => {
      const a=await traceAt(first),b=await traceAt(second);
      assert.equal(a.report.stage, name, `${name} first sample stage`);
      assert.equal(b.report.stage, name, `${name} second sample stage`);
      assert.equal(a.report.reduced, true);
      assert.equal(b.report.reduced, true);
      if (!a.shape.length || !b.shape.length) {
        assert.equal(b.report.jsFrame.sceneRenderCount, a.report.jsFrame.sceneRenderCount,
          `${name} may reuse an already submitted static frame without issuing new canvas commands`);
        return { stage:name, first, second, commands:Math.max(a.shape.length,b.shape.length), cachedFrameReused:true };
      }
      assert.deepEqual(b.shape,a.shape,`${name} may change opacity while reduced, but not geometry`);
      return { stage:name, first, second, commands:a.shape.length, cachedFrameReused:false };
    };

    const checks=[];
    checks.push(await compareShape('pulse',0.05,0.8));
    checks.push(await compareShape('identity',1.3,3.7));
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced===false'), 2000,
      'reduced-motion preference turns off before the phase-four toggle');
    const normalAtPhaseFour = await cdp.evaluate(`(()=>{
      window.launcherUI.seek(4.2);
      return {stage:window.launcherUI.report().stage,reduced:window.launcherUI.report().reduced};
    })()`);
    assert.deepEqual(normalAtPhaseFour,{stage:'dispersing',reduced:false});
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced===true'), 2000,
      'reduced-motion preference toggles during identity dispersal');
    checks.push(await compareShape('dispersing',4.2,4.68));
    checks.push(await compareShape('scattered',4.75,5.0));
    checks.push(await compareShape('drawing',5.2,6.8));
    checks.push(await compareShape('colorize',7.19,7.4));
    checks.push(await compareShape('portrait',7.5,10.8));
    checks.push(await compareShape('shutter',11.1,11.9));
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced===false'), 2000,
      'reduced-motion preference restores after static render checks');
    return { initialPreferenceBeforePlayback:initial.reduced, phaseFourToggle:normalAtPhaseFour,
      opacityMayVary:true, stages:checks };
    } finally {
      await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
      await cdp.call('Page.navigate', { url: previewURL });
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
        &&window.launcherUI?.report()?true:false`), 15000, 'default preview restored after reduced-motion checks');
    }
  });

  await check('scattered and drawing stages render bounded prewarmed path fragments sampled from identity tiles', async () => {
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    const capture = seconds => cdp.evaluate(`(()=>{
      const proto=CanvasRenderingContext2D.prototype,names=['arc','drawImage','stroke','translate','rotate'];
      const originals=new Map(),state={strokes:0,nonPathStrokes:0,dots:0,drawImages:0,canvasImages:0,translates:[],rotations:[]};
      for(const name of names){
        const original=proto[name];originals.set(name,original);
        proto[name]=function(...args){
          if(this.canvas?.hasAttribute('data-agent-skin-canvas')){
            if(name==='stroke'){if(args[0] instanceof Path2D)state.strokes++;else state.nonPathStrokes++;}
            if(name==='arc')state.dots++;
            if(name==='drawImage'){state.drawImages++;if(args[0] instanceof HTMLCanvasElement)state.canvasImages++;}
            if(name==='translate')state.translates.push(args.slice(0,2));
            if(name==='rotate')state.rotations.push(args[0]);
          }
          return original.apply(this,args);
        };
      }
      try{
        window.launcherUI.seek(${seconds});
        const stageOffset=state.translates.shift();
        return {...state,stageOffset,report:window.launcherUI.report()};
      }
      finally{for(const [name,original]of originals)proto[name]=original;}
    })()`);
    const inspectVariant = async dir => {
      await cdp.call('Page.navigate', { url: pathToFileURL(join(dir, 'index.html')).href });
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
        &&window.launcherUI?.report()?true:false`), 15000, 'fragment fixture prewarm');
      await cdp.evaluate('window.launcherUI.pause()');
      await cdp.evaluate('window.launcherUI.seek(4.73)');
      const beforeRelease = await cdp.evaluate('window.launcherUI.report()');
      const scattered = await capture(4.74);
      assert.equal(scattered.report.stage,'scattered');
      assert.equal(beforeRelease.resources.liveBitmaps,3,'the sampled identity bitmap is alive until the 4.74s boundary');
      assert.equal(scattered.report.resources.liveBitmaps,2,'the identity bitmap is released at the scattered boundary');
      assert.ok(scattered.strokes>=20,'scattered draws individual Path2D line fragments');
      assert.equal(scattered.strokes,scattered.report.resources.livePaths,'each live prewarmed fragment renders as one path');
      assert.equal(scattered.nonPathStrokes,0);
      assert.equal(scattered.dots,0,'fragments use line geometry instead of point dots');
      assert.equal(scattered.drawImages,0,'identity pixels are sampled before 4.74s and no image tiles persist into scattered');
      assert.equal(scattered.rotations.length,scattered.strokes,'each segment has one fixed scatter transform');
      const bounds = await cdp.evaluate(`(()=>{
        const contours=window.AGENT_SKIN_ASSETS.contours;let length=0;
        for(const points of contours)for(let index=1;index<points.length;index++)
          length+=Math.hypot(points[index][0]-points[index-1][0],points[index][1]-points[index-1][1]);
        const span=Math.max(18,length/1400);
        return {length,span,fragments:Math.ceil(length/span)+contours.length};
      })()`);
      assert.ok(scattered.strokes<=bounds.fragments,
        `segment count follows the span=max(18,totalLength/1400) bound: ${JSON.stringify(bounds)}`);
      const drawingStart = await capture(5.08);
      const drawingEnd = await capture(6.8);
      const frontChecks = [5.6,6.2,6.8,7.17].map(seconds=>({seconds,promise:capture(seconds)}));
      const frontFrames = await Promise.all(frontChecks.map(async frame=>({seconds:frame.seconds,...await frame.promise})));
      assert.equal(drawingStart.report.stage,'drawing');
      assert.equal(drawingEnd.report.stage,'drawing');
      assert.equal(drawingStart.strokes,scattered.strokes);
      assert.equal(drawingEnd.strokes,scattered.strokes);
      assert.equal(drawingStart.drawImages,0,'the full line canvas stays cached until the post-transition color stage');
      assert.equal(drawingEnd.drawImages,0);
      for(const frame of frontFrames){
        assert.equal(frame.report.stage,'drawing');
        assert.equal(frame.strokes,scattered.strokes);
        assert.equal(frame.drawImages,0);
      }
      const drawingScreenshot = await screenshot('animation-mid-drawing-' + (dir===animationPreviewDir?'english':'maximum-chinese') + '.png');
      const scatterAnchors = scattered.translates.filter((_,index)=>index%2===0);
      const startAnchors = drawingStart.translates.filter((_,index)=>index%2===0);
      const endAnchors = drawingEnd.translates.filter((_,index)=>index%2===0);
      assert.equal(scatterAnchors.length,scattered.strokes);
      assert.notDeepEqual(startAnchors,endAnchors,'drawing transforms fragments from their scatter anchors toward their path targets');
      assert.deepEqual(startAnchors,scatterAnchors,'the normalized sweep starts with all fragments at their seeded scatter targets');
      const smooth=value=>{const amount=Math.max(0,Math.min(1,value));return amount*amount*(3-2*amount);};
      const expectedAnchorsAt=frame=>{
        const p=Math.max(0,Math.min(1,(frame.seconds-5.08)/2.1));
        const front=1.5*p-0.25;
        return scatterAnchors.map((source,index)=>{
          const centerTranslate=scattered.translates[index*2+1];
          const targetX=-centerTranslate[0],targetY=-centerTranslate[1];
          const band=Math.max(0.01,Math.min(0.12,bounds.span/1536));
          const progress=smooth((front-targetX/1536+band)/(2*band));
          return [source[0]+(targetX-source[0])*progress,source[1]+(targetY-source[1])*progress];
        });
      };
      const verifyFrontFrame=frame=>{
        const actual=frame.translates.filter((_,index)=>index%2===0),expected=expectedAnchorsAt(frame);
        assert.equal(actual.length,expected.length);
        for(let index=0;index<actual.length;index++)for(let axis=0;axis<2;axis++)
          assert.ok(Math.abs(actual[index][axis]-expected[index][axis])<0.02,
            `front controls fragment ${index} at ${frame.seconds}s: ${JSON.stringify({actual:actual[index],expected:expected[index]})}`);
        return actual;
      };
      for(const frame of frontFrames)verifyFrontFrame(frame);
      for(const frame of frontFrames.filter(value=>value.seconds===5.6||value.seconds===6.2)){
        const anchors=verifyFrontFrame(frame);
        let leftProgress=0,leftCount=0,rightProgress=0,rightCount=0;
        for(let index=0;index<scatterAnchors.length;index++){
          const targetX=-scattered.translates[index*2+1][0];
          const start=scatterAnchors[index],target=[targetX,-scattered.translates[index*2+1][1]];
          const total=Math.hypot(target[0]-start[0],target[1]-start[1]);
          const progress=total?Math.min(1,Math.hypot(anchors[index][0]-start[0],anchors[index][1]-start[1])/total):1;
          if(targetX<1536*0.3){leftProgress+=progress;leftCount++;}
          if(targetX>1536*0.7){rightProgress+=progress;rightCount++;}
        }
        assert.ok(leftCount>0&&rightCount>0);
        leftProgress/=leftCount;rightProgress/=rightCount;
        assert.ok(leftProgress>rightProgress,`the prescribed front reaches left targets before right targets at ${frame.seconds}s`);
      }
      const endpoints=frontFrames.find(value=>value.seconds===7.17);
      const finalAnchors=verifyFrontFrame(endpoints);
      const targetAnchors=scatterAnchors.map((_,index)=>[-scattered.translates[index*2+1][0],-scattered.translates[index*2+1][1]]);
      assert.deepEqual(finalAnchors.map(point=>point.map(value=>Math.round(value*100)/100)),
        targetAnchors.map(point=>point.map(value=>Math.round(value*100)/100)),
        'the 1.5*p-0.25 front fully returns every fragment before colorize');
      const colorize = await capture(7.18);
      assert.equal(colorize.report.stage,'colorize');
      assert.equal(colorize.canvasImages,1,'the final contour canvas is used after fragments reach their paths');
      const scatterSignature = scatterAnchors.reduce((hash,point)=>{
        for(const value of point)hash=Math.imul(hash^Math.round(value*100),16777619)>>>0;
        return hash;
      },2166136261);
      return { name:dir===animationPreviewDir?'english':dir.split('-').at(-1),
        bitmaps:{beforeRelease:beforeRelease.resources.liveBitmaps,atRelease:scattered.report.resources.liveBitmaps},
        fragments:scattered.strokes,fragmentBound:bounds.fragments,scatterSignature,scatterCount:scatterAnchors.length,
        scatterAnchors:scatterAnchors.slice(0,24),
        drawingStartAnchors:startAnchors.slice(0,24),drawingEndAnchors:endAnchors.slice(0,24),
        drawingScreenshot:drawingScreenshot.file,lineCanvasImagesAtColorize:colorize.canvasImages };
    };
    try {
      const english = await inspectVariant(animationPreviewDir);
      const chinese = await inspectVariant(identityVariants.find(value=>value.name==='maximum-chinese').dir);
      assert.notEqual(english.scatterSignature,chinese.scatterSignature,
        'scatter positions are sampled from each currently prepared identity canvas');
      return { identityVariants:[english,chinese] };
    } finally {
      await cdp.call('Page.navigate', { url: previewURL });
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'
        &&window.launcherUI?.report()?true:false`), 15000, 'default preview restored after fragment checks');
    }
  });

  await check('one RC3 canvas stays registered at all required times, viewport sizes and DPR values', async () => {
    const expectedStages = new Map([
      [0, 'pulse'], [1.15, 'identity'], [4.18, 'dispersing'], [4.74, 'scattered'],
      [5.08, 'drawing'], [7.18, 'colorize'], [7.43, 'portrait'], [11, 'shutter'], [12, 'complete'],
    ]);
    const subtitle = await cdp.evaluate('window.AGENT_SKIN_ASSETS.artworkSubtitle');
    assert.equal(subtitle.length, 60, 'portrait uses the longest legal subtitle fixture');
    const sizes = [
      { name: 'wide', width: 1440, height: 900 },
      { name: 'compact', width: 980, height: 640 },
      { name: 'portrait', width: 390, height: 844 },
    ];
    const matrix = [];
    for (const size of sizes) {
      for (const dpr of [1, 2]) {
        await cdp.call('Emulation.setDeviceMetricsOverride', {
          width: size.width, height: size.height, screenWidth: size.width, screenHeight: size.height,
          deviceScaleFactor: dpr, mobile: false,
        });
        await cdp.evaluate('new Promise(resolve => { let settled = false; const settle = () => { if (settled) return; settled = true; resolve(); }; requestAnimationFrame(() => requestAnimationFrame(settle)); setTimeout(settle, 300); })');
        let injectedResolutionChange = false;
        const observedDPR = await cdp.evaluate('window.launcherUI.report().viewport.dpr');
        if (observedDPR !== dpr) {
          injectedResolutionChange = await cdp.evaluate('window.__agentSkinResolutionWatch.dispatchLatest()');
          assert.equal(injectedResolutionChange, true, 'the active resolution MediaQueryList receives a change event');
          await cdp.evaluate('new Promise(resolve => { let settled = false; const settle = () => { if (settled) return; settled = true; resolve(); }; requestAnimationFrame(() => requestAnimationFrame(settle)); setTimeout(settle, 300); })');
        }
        const actualViewport = await cdp.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})');
        assert.deepEqual(actualViewport, { width: size.width, height: size.height, dpr },
          `emulated viewport for ${size.name} at DPR ${dpr}`);
        for (const [seconds, expectedStage] of expectedStages) {
          await cdp.evaluate(`window.launcherUI.seek(${seconds})`);
          const state = await cdp.evaluate(`(()=>{
            const root=document.querySelector('[data-agent-skin-stage]');
            const canvas=root.querySelector('canvas[data-agent-skin-canvas]');
            const report=window.launcherUI.report();
            const rect=element=>{const value=element.getBoundingClientRect();return {left:value.left,top:value.top,right:value.right,bottom:value.bottom};};
            return {stage:report.stage,progress:report.animationProgress,viewport:report.viewport,
              backing:{width:canvas.width,height:canvas.height},css:{width:canvas.clientWidth,height:canvas.clientHeight},
              skip:rect(root.querySelector('[data-agent-skin-skip]')),
              controls:rect(document.querySelector('#preview-controls')),
              headerRight:rect(document.querySelector('.preview-heading span:last-child')),
              prewarmed:root.dataset.prewarmed,coordinateSize:canvas.dataset.coordinateSize};
          })()`);
          assert.equal(state.stage, expectedStage, `phase at ${seconds}s`);
          assert.equal(state.prewarmed, 'true');
          assert.equal(state.coordinateSize, '1536x1024');
          assert.equal(state.css.width, size.width, JSON.stringify(state));
          assert.equal(state.css.height, size.height, JSON.stringify(state));
          assert.equal(state.backing.width, size.width * dpr);
          assert.equal(state.backing.height, size.height * dpr);
          const overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
          const layout = JSON.stringify({ size: size.name, dpr, skip: state.skip, controls: state.controls, headerRight: state.headerRight });
          assert.equal(overlaps(state.skip, state.controls), false, `skip remains outside the preview control bar: ${layout}`);
          assert.equal(overlaps(state.skip, state.headerRight), false, `skip remains outside the heading text: ${layout}`);
          matrix.push({ size: size.name, dpr, seconds, injectedResolutionChange, ...state });
          await screenshot(`animation-${size.name}-dpr${dpr}-${String(seconds).replace('.', 'p')}s.png`);
        }
      }
    }

    const samplePixel = async seconds => cdp.evaluate(`(()=>{
      window.launcherUI.seek(${seconds});
      const canvas=document.querySelector('[data-agent-skin-canvas]');
      const context=canvas.getContext('2d');
      const scale=Math.max(innerWidth/1536,innerHeight/1024);
      const x=Math.round((1500*scale+(innerWidth-1536*scale)/2)*devicePixelRatio);
      const y=Math.round((100*scale+(innerHeight-1024*scale)/2)*devicePixelRatio);
      const pixel=context.getImageData(x,y,1,1).data;
      return {stage:window.launcherUI.report().stage,pixel:[pixel[0],pixel[1],pixel[2],pixel[3]]};
    })()`);
    await cdp.call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    await cdp.evaluate('new Promise(resolve => { let settled = false; const settle = () => { if (settled) return; settled = true; resolve(); }; requestAnimationFrame(() => requestAnimationFrame(settle)); setTimeout(settle, 300); })');
    const beforeColor = await samplePixel(7.17);
    const colorizeStart = await samplePixel(7.18);
    const portraitColor = await samplePixel(7.43);
    assert.deepEqual(beforeColor.pixel, [16, 18, 28, 255], 'background pixels remain dark before colorize');
    assert.deepEqual(colorizeStart.pixel, [16, 18, 28, 255], 'colorize starts with zero artwork opacity');
    assert.ok(portraitColor.pixel[0] + portraitColor.pixel[1] + portraitColor.pixel[2] > 360,
      'the same artwork becomes visible only after the colorize interval');
    assert.equal(beforeColor.stage, 'drawing');
    assert.equal(colorizeStart.stage, 'colorize');
    assert.equal(portraitColor.stage, 'portrait');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    const reducedState = await until(() => cdp.evaluate(`window.launcherUI.report().reduced === true
      ?window.launcherUI.report():false`), 2000, 'real browser reduced-motion media change');
    await cdp.evaluate('window.launcherUI.seek(5.7)');
    const reducedDrawing = await cdp.evaluate(`({state:window.launcherUI.report(),
      visibleProgress:document.querySelector('[data-agent-skin-progress]').textContent})`);
    assert.equal(reducedDrawing.state.stage, 'drawing');
    assert.equal(reducedDrawing.state.reduced, true);
    await screenshot('animation-reduced-motion-drawing.png');
    await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await until(() => cdp.evaluate('window.launcherUI.report().reduced === false'), 2000, 'reduced-motion media restoration');
    return { subtitleLength: subtitle.length, screenshotCount: matrix.length, matrix,
      colorRegistration: { beforeColor, colorizeStart, portraitColor }, prewarmed: animationReady.resources };
  });

  await check('DPR watcher rebinds across scale changes and disposal releases its listener and scene resources', async () => {
    const beforeDPR = await cdp.evaluate('window.__agentSkinResolutionWatch');
    assert.equal(beforeDPR.active, 1, 'one resolution listener is bound after the viewport matrix');
    await cdp.call('Emulation.setDeviceMetricsOverride', {
      width: 1440, height: 900, screenWidth: 1440, screenHeight: 900,
      deviceScaleFactor: 2, mobile: false,
    });
    await cdp.evaluate('new Promise(resolve => { let settled = false; const settle = () => { if (settled) return; settled = true; resolve(); }; requestAnimationFrame(() => requestAnimationFrame(settle)); setTimeout(settle, 300); })');
    if (await cdp.evaluate('window.launcherUI.report().viewport.dpr') !== 2) {
      assert.equal(await cdp.evaluate('window.__agentSkinResolutionWatch.dispatchLatest()'), true,
        'the active resolution MediaQueryList receives a change event');
    }
    let rebound;
    try {
      rebound = await until(() => cdp.evaluate(`(()=>{
        const report=window.launcherUI.report(),watch=window.__agentSkinResolutionWatch;
        return report.viewport.dpr===2&&report.resources.liveRAF===0&&watch.active===1&&watch.added>1
          ?{report,watch}:false;
      })()`), 3000, 'resolution observer rebinds at DPR 2');
    } catch (error) {
      const snapshot = await cdp.evaluate(`({report:window.launcherUI.report(),watch:window.__agentSkinResolutionWatch,
        resolution1:matchMedia('(resolution: 1dppx)').matches,resolution2:matchMedia('(resolution: 2dppx)').matches})`);
      throw new Error(`${error.message}; snapshot=${JSON.stringify(snapshot)}`);
    }
    assert.equal(rebound.watch.added, rebound.watch.removed + 1);
    const started = await cdp.evaluate('window.launcherUI.replay()');
    assert.equal(started, true);
    const playing = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]'),state=window.launcherUI.report();
      return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'&&state.elapsed>0?state:false;
    })()`), 10000, 'replay after DPR observer rebind');
    assert.equal(playing.viewport.dpr, 2);
    assert.equal(playing.resources.liveRAF, 1);
    assert.ok(playing.resources.liveBitmaps > 0);
    const disposed = await cdp.evaluate('window.launcherUI.dispose()');
    assert.equal(disposed, true);
    const afterDispose = await cdp.evaluate(`({report:window.launcherUI.report(),watch:window.__agentSkinResolutionWatch})`);
    assert.equal(afterDispose.watch.active, 0);
    assert.equal(afterDispose.watch.added, afterDispose.watch.removed);
    for (const kind of ['Images', 'Bitmaps', 'Canvases', 'Paths']) {
      assert.equal(afterDispose.report.resources['live' + kind], 0, `${kind} are released at disposal`);
    }
    assert.equal(afterDispose.report.resources.liveRAF, 0);
    assert.equal(afterDispose.report.resources.framesPending, 0);
    await delay(120);
    const settled = await cdp.evaluate('window.launcherUI.report()');
    assert.deepEqual(settled.resources, afterDispose.report.resources, 'disposed resources and frame counts stay stable');
    assert.deepEqual(await cdp.evaluate('window.__agentSkinResolutionWatch'), afterDispose.watch);
    const replayAfterDispose = await cdp.evaluate('window.launcherUI.replay()');
    assert.equal(replayAfterDispose, false, 'a disposed preview cannot replay');

    const previewURL = pathToFileURL(join(animationPreviewDir, 'index.html')).href;
    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'preview reload for late bitmap race');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'`),
      10000, 'fresh preview prewarm before late bitmap race');
    await cdp.evaluate(`(()=>{
      window.launcherUI.pause();
      const original=window.createImageBitmap.bind(window),pending=[];
      window.__fixtureOriginalCreateImageBitmap=original;
      window.__fixturePendingBitmaps=pending;
      window.createImageBitmap=source=>new Promise(resolve=>{
        let stableSource=source;
        if(source instanceof HTMLCanvasElement){
          stableSource=document.createElement('canvas');
          stableSource.width=source.width;stableSource.height=source.height;
          stableSource.getContext('2d').drawImage(source,0,0);
        }
        pending.push({source:stableSource,resolve});
      });
      return window.launcherUI.replay();
    })()`);
    await until(() => cdp.evaluate('window.__fixturePendingBitmaps.length===2'),
      10000, 'two replay bitmaps held before identity bitmap preparation');
    await cdp.evaluate(`Promise.all(window.__fixturePendingBitmaps.slice(0,2).map(async item=>{
      item.resolve(await window.__fixtureOriginalCreateImageBitmap(item.source));
    }))`);
    await until(() => cdp.evaluate('window.__fixturePendingBitmaps.length===3'),
      10000, 'identity bitmap held after the replay artwork bitmaps resolve');
    const heldResources = await cdp.evaluate('window.launcherUI.report().resources');
    assert.equal(heldResources.liveBitmaps, 2);
    assert.equal(heldResources.liveRAF, 0);
    assert.equal(await cdp.evaluate('window.launcherUI.dispose()'), true);
    const lateDisposed = await cdp.evaluate(`({report:window.launcherUI.report(),watch:window.__agentSkinResolutionWatch,
      prewarmed:document.querySelector('[data-agent-skin-stage]').dataset.prewarmed,
      playing:document.querySelector('[data-agent-skin-stage]').dataset.playing})`);
    assert.equal(lateDisposed.watch.active, 0);
    assert.equal(lateDisposed.prewarmed, 'false');
    assert.equal(lateDisposed.playing, 'false');
    assert.equal(lateDisposed.report.resources.liveBitmaps, 0);
    assert.equal(lateDisposed.report.resources.liveRAF, 0);
    assert.equal(await cdp.evaluate('window.launcherUI.replay()'), false);
    await cdp.evaluate(`(async()=>{
      const item=window.__fixturePendingBitmaps[2];
      const bitmap=await window.__fixtureOriginalCreateImageBitmap(item.source);
      item.source.width=0;item.source.height=0;item.resolve(bitmap);
    })()`);
    const lateSettled = await until(() => cdp.evaluate(`(()=>{
      const state=window.launcherUI.report(),resources=state.resources;
      return resources.liveBitmaps===0&&resources.createdBitmaps===resources.releasedBitmaps
        &&resources.liveRAF===0&&resources.framesPending===0
        ?{state,prewarmed:document.querySelector('[data-agent-skin-stage]').dataset.prewarmed}:false;
    })()`), 3000, 'late bitmap closes without reviving disposed preview');
    assert.equal(lateSettled.prewarmed, 'false');
    await delay(120);
    const afterLateSettle = await cdp.evaluate('window.launcherUI.report().resources');
    assert.deepEqual(afterLateSettle, lateSettled.state.resources, 'late callbacks cannot add frames or resources after disposal');

    await cdp.call('Page.navigate', { url: previewURL });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'preview reload for following checks');
    await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-stage]')?.dataset.prewarmed==='true'`),
      10000, 'preview ready for following checks');
    await cdp.evaluate('window.launcherUI.pause()');
    return { beforeDPR, rebound: rebound.watch, playing: playing.resources,
      disposed: afterDispose.watch, finalResources: settled.resources, settleMs: 120,
      replayAfterDispose, heldResources, lateDispose: { watcher: lateDisposed.watch,
        resources: lateDisposed.report.resources, replayAfterDispose: false },
      lateSettledResources: afterLateSettle, lateSettleMs: 120 };
  });

  await check('local preview controls pause, resume, seek and replay the same prepared scene', async () => {
    const controls = await cdp.evaluate(`({visible:!document.querySelector('#preview-controls').hidden,
      timeline:document.querySelector('#timeline').max,handle:typeof window.launcherUI.replay==='function'})`);
    assert.deepEqual(controls, { visible: true, timeline: '12', handle: true });
    await cdp.evaluate("document.querySelector('#pause').click()");
    const startingElapsed = await cdp.evaluate('window.launcherUI.report().elapsed');
    const started = await until(() => cdp.evaluate('document.querySelector("[data-agent-skin-stage]").dataset.playing === "true"'), 1500, 'preview resume before pause check');
    await until(() => cdp.evaluate(`window.launcherUI.report().elapsed>${startingElapsed + 0.04}`), 2000, 'preview clock advance before pause check');
    await cdp.evaluate("document.querySelector('#pause').click()");
    const pausedAt = await cdp.evaluate('window.launcherUI.report().elapsed');
    await delay(180);
    const stillPausedAt = await cdp.evaluate('window.launcherUI.report().elapsed');
    assert.ok(Math.abs(stillPausedAt - pausedAt) < 0.02, 'pause freezes the shared rAF clock');
    await cdp.evaluate("document.querySelector('#pause').click()");
    const resumed = await until(() => cdp.evaluate(`window.launcherUI.report().elapsed>${pausedAt + 0.04}`), 2000, 'preview resume');
    await cdp.evaluate(`(()=>{const input=document.querySelector('#timeline');input.value='2.34';input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    const seek = await cdp.evaluate('window.launcherUI.report()');
    assert.ok(Math.abs(seek.elapsed - 2.34) < 0.03);
    await cdp.evaluate("document.querySelector('#replay').click()");
    const replayed = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]');
      return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'&&window.launcherUI.report().elapsed>0
        ?window.launcherUI.report():false;
    })()`), 10000, 'preview replay after resource release');
    return { controls, started, pausedAt, stillPausedAt, resumed, seek: { elapsed: seek.elapsed, stage: seek.stage }, replayed: { elapsed: replayed.elapsed, stage: replayed.stage } };
  });

  await check('repeated preview replay releases JavaScript-owned resources after a five second settle', async () => {
    const cycles = [];
    for (let index = 0; index < 10; index++) {
      await cdp.evaluate("document.querySelector('[data-agent-skin-skip]').click()");
      const completed = await until(() => cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        const resources=window.launcherUI.report().resources;
        return root.dataset.completed==='true'&&resources.liveImages===0&&resources.liveBitmaps===0
          &&resources.liveCanvases===0&&resources.livePaths===0&&resources.liveRAF===0
          ?resources:false;
      })()`), 3000, 'resource release after replay skip ' + index);
      cycles.push(completed);
      if (index < 9) {
        await cdp.evaluate("document.querySelector('#replay').click()");
        await until(() => cdp.evaluate(`(()=>{
          const root=document.querySelector('[data-agent-skin-stage]');
          const resources=window.launcherUI.report().resources;
          return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'
            &&resources.liveImages+resources.liveBitmaps>0;
        })()`), 10000, 'replay prepare ' + (index + 2));
      }
    }
    await delay(5000);
    const settled = await cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]');
      return {rootCount:document.querySelectorAll('[data-agent-skin-stage]').length,
        iframeCount:document.querySelectorAll('iframe').length,completed:root.dataset.completed==='true',
        report:window.launcherUI.report()};
    })()`);
    assert.equal(settled.rootCount, 1);
    assert.equal(settled.iframeCount, 0);
    assert.equal(settled.completed, true);
    for (const [kind, created, released, live] of [
      ['images', 'createdImages', 'releasedImages', 'liveImages'],
      ['bitmaps', 'createdBitmaps', 'releasedBitmaps', 'liveBitmaps'],
      ['canvases', 'createdCanvases', 'releasedCanvases', 'liveCanvases'],
      ['paths', 'createdPaths', 'releasedPaths', 'livePaths'],
    ]) {
      assert.equal(settled.report.resources[created], settled.report.resources[released], `${kind} are released`);
      assert.equal(settled.report.resources[live], 0, `${kind} are not left live`);
    }
    assert.equal(settled.report.resources.liveRAF, 0);
    assert.equal(settled.report.resources.liveObjectURLs, 0);
    assert.equal(settled.report.jsFrame.scope, 'JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing');
    return { replayCycles: cycles.length, finalResources: settled.report.resources,
      jsFrame: settled.report.jsFrame, settleSeconds: 5, rootCount: settled.rootCount, iframeCount: settled.iframeCount };
  });

  await check('skip and Escape finish idempotently at the first second, a transition, and the final second', async () => {
    const results = [];
    for (const [seconds, input] of [[0.4, 'button'], [4.5, 'escape'], [11.6, 'button']]) {
      await cdp.evaluate("document.querySelector('#replay').click()");
      await until(() => cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        return root.dataset.prewarmed==='true'&&root.dataset.playing==='true';
      })()`), 10000, 'phase skip replay prewarm');
      await cdp.evaluate('window.launcherUI.pause()');
      await cdp.evaluate(`window.launcherUI.seek(${seconds})`);
      const stage = await cdp.evaluate('window.launcherUI.report().stage');
      if (input === 'escape') {
        await cdp.evaluate("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true}))");
      } else {
        await cdp.evaluate("document.querySelector('[data-agent-skin-skip]').click();document.querySelector('[data-agent-skin-skip]').click()");
      }
      const state = await cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        return {completed:root.dataset.completed==='true',report:window.launcherUI.report()};
      })()`);
      assert.equal(state.completed, true);
      assert.equal(state.report.completed, true);
      assert.equal(state.report.skipped, true);
      assert.equal(state.report.resources.liveRAF, 0);
      results.push({ seconds, phase: stage, input, skipped: state.report.skipped, resources: state.report.resources });
    }
    assert.equal(results[0].phase, 'pulse');
    assert.equal(results[1].phase, 'dispersing');
    assert.equal(results[2].phase, 'shutter');
    return results;
  });

  await check('one upper-bound natural replay with the 60-unit Chinese subtitle settles without resource growth', async () => {
    await cdp.call('Page.navigate', { url: pathToFileURL(join(upperPreviewDir, 'index.html')).href });
    await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, 'upper subtitle fixture page load');
    const prepared = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]'),state=window.launcherUI?.report();
      return root?.dataset.prewarmed==='true'&&state?state:false;
    })()`), 30000, 'upper path fixture and longest subtitle prewarm');
    const bounds = await cdp.evaluate(`(()=>{
      const assets=window.AGENT_SKIN_ASSETS;
      return {contourPaths:assets.contours.length,
        contourPoints:assets.contours.reduce((sum,path)=>sum+path.length,0),
        subtitleCodeUnits:assets.artworkSubtitle.length,subtitle:assets.artworkSubtitle};
    })()`);
    assert.equal(bounds.contourPaths, 1200);
    assert.equal(bounds.contourPoints, 300000);
    assert.equal(bounds.subtitleCodeUnits, 60);
    const completed = await until(() => cdp.evaluate(`(()=>{
      const root=document.querySelector('[data-agent-skin-stage]'),state=window.launcherUI.report();
      return root.dataset.completed==='true'&&state.completed&&state.stage==='complete'
        &&state.resources.liveRAF===0&&state.resources.liveImages===0&&state.resources.liveBitmaps===0
        &&state.resources.liveCanvases===0&&state.resources.livePaths===0?state:false;
    })()`), 30000, 'one natural upper-bound replay completes and releases resources');
    assert.equal(completed.elapsed, 12);
    assert.ok(completed.jsFrame.rafIntervalMs?.count > 100);
    assert.ok(completed.jsFrame.renderSubmissionMs?.count > 100);
    const settleBaseline = { resources: completed.resources, jsFrame: completed.jsFrame };
    await delay(5000);
    const afterSettle = await cdp.evaluate('window.launcherUI.report()');
    assert.deepEqual({ resources: afterSettle.resources, jsFrame: afterSettle.jsFrame }, settleBaseline);
    return { bounds: { contourPaths: bounds.contourPaths, contourPoints: bounds.contourPoints,
      subtitleCodeUnits: bounds.subtitleCodeUnits }, initialResources: prepared.resources,
      elapsedSeconds: completed.elapsed, resources: completed.resources, jsFrame: completed.jsFrame,
      settleSeconds: 5, measurementScope: completed.jsFrame.scope };
  });

  await check('RC6 default and upper path-limit fixtures naturally complete ten 12-second replays with five-second settle checks', async () => {
    const limits = {
      avatarDataURLChars: 2 * 1024 * 1024,
      artworkDataURLChars: 12 * 1024 * 1024,
      contourPaths: 1200,
      contourPoints: 300000,
      serializedRecordChars: 20 * 1024 * 1024,
    };
    const fixtures = [
      { name: 'default', dir: animationPreviewDir, expectedPaths: 4, expectedPoints: 20 },
      { name: 'upper', dir: upperPreviewDir, expectedPaths: 1200, expectedPoints: 300000 },
    ];
    const result = [];
    for (const fixture of fixtures) {
      await cdp.call('Page.navigate', { url: pathToFileURL(join(fixture.dir, 'index.html')).href });
      await until(() => cdp.evaluate('document.readyState === "complete"'), 10000, fixture.name + ' fixture page load');
      const prewarmed = await until(() => cdp.evaluate(`(()=>{
        const root=document.querySelector('[data-agent-skin-stage]');
        return window.launcherUI&&root?.dataset.prewarmed==='true'?window.launcherUI.report():false;
      })()`), 30000, fixture.name + ' fixture image and path prewarm');
      const assetBounds = await cdp.evaluate(`(()=>{
        const assets=window.AGENT_SKIN_ASSETS;
        const pointCount=assets.contours.reduce((total,path)=>total+path.length,0);
        const record=JSON.stringify({avatar:assets.avatar,artwork:assets.artwork,contours:assets.contours,
          introTitle:assets.introTitle,introCaption:assets.introCaption,artworkSubtitle:assets.artworkSubtitle});
        return {avatarDataURLChars:assets.avatar.length,artworkDataURLChars:assets.artwork.length,
          contourPaths:assets.contours.length,contourPoints:pointCount,serializedRecordChars:record.length,
          resources:window.launcherUI.report().resources};
      })()`);
      assert.ok(assetBounds.avatarDataURLChars <= limits.avatarDataURLChars, 'avatar data URL stays within its configured bound');
      assert.ok(assetBounds.artworkDataURLChars <= limits.artworkDataURLChars, 'artwork data URL stays within its configured bound');
      assert.ok(assetBounds.contourPaths <= limits.contourPaths && assetBounds.contourPaths === fixture.expectedPaths);
      assert.ok(assetBounds.contourPoints <= limits.contourPoints && assetBounds.contourPoints === fixture.expectedPoints);
      assert.ok(assetBounds.serializedRecordChars <= limits.serializedRecordChars, 'serialized settings record stays within its configured bound');
      await cdp.evaluate('window.launcherUI.pause()');

      const rounds = [];
      for (let index = 0; index < 10; index++) {
        const startedAt = Date.now();
        await cdp.evaluate("document.querySelector('#replay').click()");
        await until(() => cdp.evaluate(`(()=>{
          const root=document.querySelector('[data-agent-skin-stage]');
          return root.dataset.prewarmed==='true'&&root.dataset.playing==='true'
            &&window.launcherUI.report().elapsed>0;
        })()`), 30000, fixture.name + ' natural playback start ' + (index + 1));
        const completed = await until(() => cdp.evaluate(`(()=>{
          const root=document.querySelector('[data-agent-skin-stage]');
          const state=window.launcherUI.report();
          return root.dataset.completed==='true'&&state.completed&&state.stage==='complete'
            &&state.resources.liveRAF===0&&state.resources.liveImages===0&&state.resources.liveBitmaps===0
            &&state.resources.liveCanvases===0&&state.resources.livePaths===0?state:false;
        })()`), 30000, fixture.name + ' natural animation completion ' + (index + 1));
        assert.equal(completed.elapsed, 12);
        assert.ok(completed.jsFrame.rafIntervalMs?.count > 100, 'natural replay records actual rAF intervals');
        assert.ok(completed.jsFrame.renderSubmissionMs?.count > 100, 'natural replay records actual canvas submission work');
        const settleBaseline = { resources: completed.resources, jsFrame: completed.jsFrame };
        await delay(5000);
        const afterSettle = await cdp.evaluate('window.launcherUI.report()');
        assert.deepEqual({ resources: afterSettle.resources, jsFrame: afterSettle.jsFrame }, settleBaseline,
          fixture.name + ' resources and frame samples stay stable for five seconds after complete');
        assert.equal(afterSettle.resources.framesPending, 0);
        assert.equal(afterSettle.resources.liveObjectURLs, 0);
        rounds.push({ round: index + 1, wallTimeMs: Date.now() - startedAt,
          elapsedSeconds: completed.elapsed, resources: completed.resources, jsFrame: completed.jsFrame });
      }
      result.push({ fixture: fixture.name, assetBounds, initialResources: prewarmed.resources, rounds });
    }
    return { limits, fixtures: result, measurementScope: 'JS rAF interval and 2D canvas submission only; GPU/compositor/presentation/system-memory timing not measured' };
  });

  if (options.generatedPayload) {
    const startupWallpaperFailureCheck = 'generated startup wallpaper failure is visible near the appearance entry';
    if (!onlyChecks || onlyChecks.has(startupWallpaperFailureCheck)) {
      await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1&hold-shell=1&fail-first-wallpaper-shell-observer=1&focus-case=notice');
    }
    await check(startupWallpaperFailureCheck, async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready?state:false;
      })()`), 20000, 'generated animation ready before recovering its startup wallpaper failure');
      const skipped = await cdp.evaluate(`(()=>{
        const button=document.querySelector('iframe[aria-label]')?.contentDocument
          .querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();
        return true;
      })()`);
      assert.equal(skipped, true, 'the generated startup animation exposes its normal skip control');
      const failed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.wallpaper.failureCode==='shell-unsupported'?state:false;
      })()`), 5000, 'the first generated wallpaper shell observer fails without waiting for the shell timeout');
      const recovery = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const node=entry?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-recovery]');
        if(!node)return null;
        const style=getComputedStyle(node);
        return {display:style.display,role:node.getAttribute('role'),
          title:node.querySelector('[data-agent-skin-wallpaper-title]')?.textContent,
          reason:node.querySelector('[data-agent-skin-wallpaper-reason]')?.textContent,
          retry:node.querySelector('[data-agent-skin-wallpaper-retry]')?.getAttribute('aria-label'),
          close:node.querySelector('[data-agent-skin-wallpaper-close]')?.getAttribute('aria-label')};
      })()`);
      assert.ok(recovery && recovery.display !== 'none' && recovery.retry && recovery.close,
        'a completed startup wallpaper failure must expose its reason, retry and close beside the existing entry; '
          + JSON.stringify({ ready: { phase: ready.phase, runId: ready.runId }, failed, recovery }));
      assert.equal(recovery.role, 'group');
      assert.equal(recovery.title, '启动背景未应用');
      assert.equal(recovery.reason, '当前页面暂时无法监测可用的工作区背景区域。');
      assert.equal(recovery.retry, '重试启动背景');
      assert.equal(recovery.close, '关闭启动背景失败提示');

      await cdp.evaluate(`document.documentElement.lang='en'`);
      const english = await until(() => cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const node=entry?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-recovery]');
        return node?.querySelector('[data-agent-skin-wallpaper-title]')?.textContent
          ==='Startup background not applied'?{
            title:node.querySelector('[data-agent-skin-wallpaper-title]').textContent,
            reason:node.querySelector('[data-agent-skin-wallpaper-reason]').textContent,
            retry:node.querySelector('[data-agent-skin-wallpaper-retry]').getAttribute('aria-label'),
            close:node.querySelector('[data-agent-skin-wallpaper-close]').getAttribute('aria-label')}:false;
      })()`), 3000, 'the visible startup wallpaper recovery updates with the host language');
      assert.equal(english.reason, 'This page cannot currently monitor a supported workspace background area.');
      assert.equal(english.retry, 'Retry startup background');
      assert.equal(english.close, 'Close startup background notice');
      await cdp.evaluate(`document.documentElement.lang='zh-CN'`);
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]')
        ?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-title]')?.textContent==='启动背景未应用'`),
      3000, 'the recovery returns to the Chinese host language');

      const keyboardFocus = [];
      for (const theme of ['dark', 'light']) {
        await cdp.evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme)}`);
        await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]')
          ?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-recovery]')?.style.colorScheme
          ===${JSON.stringify(theme)}`), 3000, theme + ' recovery appearance update');
        const focusStart = await cdp.evaluate(`(()=>{
          const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
          const shadow=entry?.shadowRoot,button=shadow?.querySelector('[aria-haspopup="dialog"]');
          const retry=shadow?.querySelector('[data-agent-skin-wallpaper-retry]');
          button?.focus();
          return {hostFocused:document.activeElement===entry,buttonFocused:shadow?.activeElement===button,
            display:entry&&getComputedStyle(entry).display, inert:entry?.inert, retryDisabled:retry?.disabled};
        })()`);
        assert.equal(focusStart.buttonFocused, true,
          'the appearance button receives focus before testing recovery Tab order: '+JSON.stringify(focusStart));
        await dispatchTab();
        const retryFocus = await cdp.evaluate(`(()=>{
          const shadow=document.querySelector('[data-agent-skin-entry="appearance"]')?.shadowRoot;
          const retry=shadow?.querySelector('[data-agent-skin-wallpaper-retry]');
          const style=retry&&getComputedStyle(retry);
          return {active:shadow?.activeElement===retry,focusVisible:retry?.matches(':focus-visible'),
            outlineColor:style?.outlineColor,outlineStyle:style?.outlineStyle,outlineWidth:style?.outlineWidth};
        })()`);
        assert.equal(retryFocus.active, true, theme + ' Tab focuses retry');
        assert.equal(retryFocus.focusVisible, true, theme + ' keyboard focus matches :focus-visible');
        assert.ok(retryFocus.outlineStyle !== 'none' && parseFloat(retryFocus.outlineWidth) >= 2
          && retryFocus.outlineColor !== 'transparent' && !/rgba\([^)]*,\s*0(?:\.0+)?\)$/.test(retryFocus.outlineColor),
        theme + ' retry has a visible focus outline: ' + JSON.stringify(retryFocus));
        await dispatchTab();
        const closeFocus = await cdp.evaluate(`(()=>{
          const shadow=document.querySelector('[data-agent-skin-entry="appearance"]')?.shadowRoot;
          const close=shadow?.querySelector('[data-agent-skin-wallpaper-close]');
          const style=close&&getComputedStyle(close);
          return {active:shadow?.activeElement===close,focusVisible:close?.matches(':focus-visible'),
            outlineColor:style?.outlineColor,outlineStyle:style?.outlineStyle,outlineWidth:style?.outlineWidth};
        })()`);
        assert.equal(closeFocus.active, true, theme + ' Tab focuses close');
        assert.equal(closeFocus.focusVisible, true, theme + ' close keyboard focus matches :focus-visible');
        assert.ok(closeFocus.outlineStyle !== 'none' && parseFloat(closeFocus.outlineWidth) >= 2
          && closeFocus.outlineColor !== 'transparent' && !/rgba\([^)]*,\s*0(?:\.0+)?\)$/.test(closeFocus.outlineColor),
        theme + ' close has a visible focus outline: ' + JSON.stringify(closeFocus));
        keyboardFocus.push({ theme, retryFocus, closeFocus });
      }
      await dispatchEnter();
      const closed = await until(() => cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const shadow=entry?.shadowRoot,notice=shadow?.querySelector('[data-agent-skin-wallpaper-recovery]');
        if(getComputedStyle(notice).display!=='none')return false;
        const live=shadow?.querySelector('[data-agent-skin-wallpaper-live]');
        const appearanceButton=shadow?.querySelector('[aria-haspopup="dialog"]');
        return {noticeDisplay:getComputedStyle(notice).display,buttonDisplay:getComputedStyle(entry).display,
          failureCode:window.__startupAPI.status().wallpaper.failureCode,phase:window.__startupAPI.status().phase,
          focusReturnedToEntry:document.activeElement===entry&&shadow?.activeElement===appearanceButton,
          announcement:live?.textContent};
      })()`), 3000, 'Enter closes the recovery notice');
      assert.deepEqual(closed, { noticeDisplay: 'none', buttonDisplay: 'block',
        failureCode: 'shell-unsupported', phase: 'complete', focusReturnedToEntry: true,
        announcement: '已关闭启动背景失败提示，应用仍可使用。' },
      'Enter closes only the recovery card, keeps the controller available, and returns focus to the entry');
      const disposed = await cdp.evaluate('window.__startupAPI.dispose()');
      assert.deepEqual(disposed, { disposed: true }, 'the completed synthetic controller is disposed before page reuse');
      return { ready: { phase: ready.phase, runId: ready.runId }, skipped, failed, recovery, english, keyboardFocus, closed, disposed };
    });

    const startupWallpaperRetryCheck = 'generated startup wallpaper retry succeeds without replaying the animation';
    if (!onlyChecks || onlyChecks.has(startupWallpaperRetryCheck)) {
      await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1&hold-shell=1&fail-first-wallpaper-shell-observer=1&focus-case=retry');
    }
    await check(startupWallpaperRetryCheck, async () => {
      const ready = await awaitGeneratedReady('generated animation ready before its wallpaper retry');
      const skipped = await cdp.evaluate(`(()=>{
        const button=document.querySelector('iframe[aria-label]')?.contentDocument
          .querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();
        return true;
      })()`);
      assert.equal(skipped, true);
      const failed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.wallpaper.failureCode==='shell-unsupported'?state:false;
      })()`), 5000, 'the generated startup wallpaper failure is recorded before retry');
      const entryBeforeRetry = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const notice=entry?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-recovery]');
        return {display:getComputedStyle(notice).display,
          retry:notice?.querySelector('[data-agent-skin-wallpaper-retry]')?.getAttribute('aria-label')};
      })()`);
      assert.equal(entryBeforeRetry.display, 'block');
      assert.equal(entryBeforeRetry.retry, '重试启动背景');
      await cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]')
        ?.shadowRoot?.querySelector('[aria-haspopup="dialog"]')?.focus()`);
      await dispatchTab();
      const retryBeforeEnter = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const shadow=entry?.shadowRoot,retry=shadow?.querySelector('[data-agent-skin-wallpaper-retry]');
        return {focused:shadow?.activeElement===retry,focusVisible:retry?.matches(':focus-visible')};
      })()`);
      assert.deepEqual(retryBeforeEnter, { focused: true, focusVisible: true },
        'Tab places keyboard focus on retry before Enter');
      await dispatchEnter();
      const retryClicked = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const retry=entry?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-retry]');
        if(!retry)return false;
        const disabledWhilePending=retry.disabled;
        const pendingLabel=retry.getAttribute('aria-label');
        retry.click();
        return {started:true,disabledWhilePending,disabledAfterDuplicateClick:retry.disabled,pendingLabel};
      })()`);
      assert.deepEqual(retryClicked, { started: true, disabledWhilePending: true,
        disabledAfterDuplicateClick: true, pendingLabel: '正在重试启动背景' },
      'the visible retry becomes busy immediately and does not start a concurrent retry');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true,
        'the existing fixture releases the supported shell while the user retry is pending');
      const applied = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.wallpaper.applied?state:false;
      })()`), 15000, 'the user retry applies the wallpaper after the shell appears');
      const after = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const shadow=entry?.shadowRoot,notice=shadow?.querySelector('[data-agent-skin-wallpaper-recovery]');
        const appearanceButton=shadow?.querySelector('[aria-haspopup="dialog"]');
        return {state:window.__startupAPI.status(),noticeDisplay:getComputedStyle(notice).display,
          entryDisplay:getComputedStyle(entry).display,iframeCount:document.querySelectorAll('iframe[aria-label]').length,
          focusReturnedToEntry:document.activeElement===entry&&shadow?.activeElement===appearanceButton,
          announcement:shadow?.querySelector('[data-agent-skin-wallpaper-live]')?.textContent,
          wallpaperStyleCount:document.querySelectorAll('#azhou-wallpaper-style').length};
      })()`);
      assert.equal(after.state.runId, ready.runId, 'retry keeps the original controller run');
      assert.equal(after.noticeDisplay, 'none', 'success removes the startup failure card');
      assert.equal(after.entryDisplay, 'block', 'success leaves the existing appearance entry available');
      assert.equal(after.iframeCount, 0, 'retry does not replay or reopen the startup animation');
      assert.equal(after.focusReturnedToEntry, true,
        'successful Enter retry returns focus to the entry when the retry control held keyboard focus');
      assert.equal(after.announcement, '启动背景已应用。');
      assert.equal(after.wallpaperStyleCount, 1, 'the supported shell receives one owned wallpaper layer');
      return { ready: { phase: ready.phase, runId: ready.runId }, skipped, failed, entryBeforeRetry,
        retryClicked, applied, after };
    });

    const startupWallpaperHostFocusCheck = 'generated startup wallpaper retry preserves host focus after it moves outside recovery';
    if (!onlyChecks || onlyChecks.has(startupWallpaperHostFocusCheck)) {
      await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1&hold-shell=1&fail-first-wallpaper-shell-observer=1&focus-case=host');
    }
    await check(startupWallpaperHostFocusCheck, async () => {
      const ready = await awaitGeneratedReady('generated animation ready before preserving host focus');
      const skipped = await cdp.evaluate(`(()=>{
        const button=document.querySelector('iframe[aria-label]')?.contentDocument
          .querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();
        return true;
      })()`);
      assert.equal(skipped, true);
      await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.wallpaper.failureCode==='shell-unsupported'?state:false;
      })()`), 5000, 'startup wallpaper failure is ready for keyboard retry');
      await cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]')
        ?.shadowRoot?.querySelector('[aria-haspopup="dialog"]')?.focus()`);
      await dispatchTab();
      const retryFocused = await cdp.evaluate(`(()=>{
        const shadow=document.querySelector('[data-agent-skin-entry="appearance"]')?.shadowRoot;
        return shadow?.activeElement?.hasAttribute('data-agent-skin-wallpaper-retry')===true;
      })()`);
      assert.equal(retryFocused, true);
      await dispatchEnter();
      await until(() => cdp.evaluate(`document.querySelector('[data-agent-skin-entry="appearance"]')
        ?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-retry]')?.disabled===true`),
      3000, 'retry enters its busy state before moving focus');
      const hostFocus = await cdp.evaluate(`(()=>{
        const button=document.querySelector('#theme');
        button.focus();
        return document.activeElement===button;
      })()`);
      assert.equal(hostFocus, true, 'focus moves to a host control while retry is pending');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      const applied = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.wallpaper.applied?state:false;
      })()`), 15000, 'retry succeeds after the shell becomes available');
      const after = await cdp.evaluate(`(()=>({activeIsHostButton:document.activeElement===document.querySelector('#theme'),
        activeId:document.activeElement?.id,
        noticeDisplay:getComputedStyle(document.querySelector('[data-agent-skin-entry="appearance"]')
          ?.shadowRoot?.querySelector('[data-agent-skin-wallpaper-recovery]')).display}))()`);
      assert.deepEqual(after, { activeIsHostButton: true, activeId: 'theme', noticeDisplay: 'none' },
        'retry success preserves focus after the user moves it to the host');
      return { ready: { runId: ready.runId }, skipped, applied, after };
    });

    await navigate('/fixture.html?generated-payload=1&no-initial-wallpaper=1');
    await check('generated settings editor Tab cannot modify the host composer', async () => {
      await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready?state:false;
      })()`), 15000, 'generated animation is ready before opening settings');
      const hostInput = await cdp.evaluate(`(()=>{
        const input=document.querySelector('.composer textarea')||document.querySelector('textarea');
        if(!input)return false;
        const alreadyInert=document.createElement('div');
        alreadyInert.id='fixture-focus-preexisting-inert';alreadyInert.inert=true;
        document.body.appendChild(alreadyInert);
        input.value='host-composer-sentinel';input.focus();
        return {focused:document.activeElement===input,accepted:window.__startupAPI.openSettings()};
      })()`);
      assert.deepEqual(hostInput, { focused: true, accepted: true },
        'the fixture has a focused host textarea before the generated settings dialog opens');
      await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
        return window.__startupAPI.status().phase==='settings'
          &&doc?.querySelector('[data-agent-skin-settings]')?.open;
      })()`), 15000, 'generated settings dialog opens inside the overlay iframe');
      const chooserCancel = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
        const input=doc?.querySelector('[data-agent-skin-image-input="artwork"]');
        input?.dispatchEvent(new frame.contentWindow.Event('cancel',{bubbles:true}));
        return {phase:window.__startupAPI.status().phase,
          open:!!doc?.querySelector('[data-agent-skin-settings]')?.open};
      })()`);
      assert.deepEqual(chooserCancel,{phase:'settings',open:true},
        'canceling the native image chooser keeps generated settings open');
      const isolation = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        return {bodyInert:document.body.inert,rootInert:document.querySelector('#root')?.inert,
          frameInert:frame?.inert,preexistingInert:document.querySelector('#fixture-focus-preexisting-inert')?.inert};
      })()`);
      assert.deepEqual(isolation, { bodyInert: false, rootInert: true, frameInert: false, preexistingInert: true },
        'isolation covers host content without inerting the frame ancestor or changing existing inert state');
      await cdp.evaluate(`(()=>{
        const late=document.createElement('button');late.id='fixture-focus-late-host-button';
        late.textContent='Late host action';window.__fixtureFocusDetachedButton=late;document.body.appendChild(late);
      })()`);
      await until(() => cdp.evaluate(`document.querySelector('#fixture-focus-late-host-button')?.inert===true`),
        3000, 'a host button added during settings becomes inert');
      await cdp.evaluate(`document.querySelector('#root').inert=false`);
      await until(() => cdp.evaluate(`document.querySelector('#root')?.inert===true`),
        3000, 'a host inert edit during settings does not open the keyboard boundary');
      await cdp.evaluate(`document.querySelector('#fixture-focus-late-host-button')?.remove()`);
      await until(() => cdp.evaluate(`!window.__fixtureFocusDetachedButton?.isConnected`),
        3000, 'the late host button is detached');
      await cdp.evaluate(`window.__fixtureFocusDetachedButton.inert=false`);
      await delay(50);
      await cdp.evaluate(`document.body.appendChild(window.__fixtureFocusDetachedButton)`);
      await until(() => cdp.evaluate(`document.querySelector('#fixture-focus-late-host-button')?.inert===true`),
        3000, 'a detached host button is re-isolated when it is reinserted');
      const trace = [];
      let textareaReached = null;
      const boundaries = [];
      for (const shiftKey of [false, true]) {
        const boundary = await cdp.evaluate(`(()=>{
          const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
          const dialog=doc?.querySelector('[data-agent-skin-settings]');
          const controls=[...dialog.querySelectorAll('button,input,textarea,select,[tabindex]')]
            .filter(item=>item.tabIndex>=0&&!item.disabled&&item.type!=='hidden'
              &&getComputedStyle(item).display!=='none'&&getComputedStyle(item).visibility!=='hidden'
              &&item.getClientRects().length>0);
          const control=controls.at(${shiftKey ? 0 : -1});
          control?.focus();
          return control&&doc.activeElement===control?{count:controls.length,
            edge:control.getAttribute('aria-label')||control.tagName}:false;
        })()`);
        assert.ok(boundary, 'generated settings dialog exposes a focusable control at each Tab boundary');
        boundaries.push({ shiftKey, ...boundary });
        for (let index = 0; index < boundary.count * 2 + 1; index++) {
          await dispatchTab(shiftKey);
          const focus = await cdp.evaluate(`(()=>{
            const input=document.querySelector('.composer textarea')||document.querySelector('textarea');
            const frame=document.querySelector('iframe[aria-label]');
            const selected=frame?.contentDocument?.activeElement;
            const style=selected?frame.contentWindow.getComputedStyle(selected):null;
            return {value:input?.value,hostTextareaFocused:document.activeElement===input,
              hostFrameFocused:document.activeElement===frame,
              parentFocus:document.activeElement?.tagName+'#'+(document.activeElement?.id||''),
              dialogFocus:frame?.contentDocument?.activeElement?.tagName+'#'
                +(frame?.contentDocument?.activeElement?.id||''),
              focusVisible:selected?.matches(':focus-visible'),outlineStyle:style?.outlineStyle,outlineWidth:style?.outlineWidth};
          })()`);
          if (focus.hostFrameFocused && focus.focusVisible) {
            assert.ok(focus.outlineStyle !== 'none' && parseFloat(focus.outlineWidth) >= 3,
              'keyboard focus remains visible in the generated settings payload: ' + JSON.stringify(focus));
          }
          if (!focus.hostFrameFocused && trace.length < 4) trace.push({ shiftKey, index, ...focus });
          if (focus.hostTextareaFocused) {
            textareaReached = { shiftKey, index, parentFocus: focus.parentFocus };
            await cdp.call('Input.insertText', { text: 'focus-leak' });
            break;
          }
        }
        if (textareaReached) break;
      }
      const finalValue = await cdp.evaluate(`(document.querySelector('.composer textarea')||document.querySelector('textarea'))?.value`);
      assert.equal(finalValue, 'host-composer-sentinel',
        'Tab must not reach the host textarea and accept keyboard text; boundary=' + JSON.stringify({ boundaries, trace, textareaReached, finalValue }));
      assert.equal(trace.length, 0,
        'focus must remain in the generated settings iframe; boundary=' + JSON.stringify({ boundaries, trace, textareaReached }));
      const importErrorShown = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),win=frame.contentWindow,doc=frame.contentDocument;
        const input=doc?.querySelector('input[data-agent-skin-image-input="artwork"]');
        if(!input)return false;
        const transfer=new win.DataTransfer();
        transfer.items.add(new win.File([],'generated-empty-artwork.png',{type:'image/png'}));
        input.files=transfer.files;
        input.dispatchEvent(new win.Event('change',{bubbles:true}));
        return true;
      })()`);
      assert.equal(importErrorShown, true, 'an empty artwork import is dispatched for the error-state walk');
      const importErrorAlert = await until(() => cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
        const status=doc?.querySelector('[data-agent-skin-settings-status]');
        return status?.getAttribute('role')==='alert'&&status.textContent?status.textContent:false;
      })()`), 5000, 'the generated panel reports the import error while staying open');
      const errorWalk = await walkGeneratedSettingsTabs();
      const errorFinalValue = await cdp.evaluate(`(document.querySelector('.composer textarea')||document.querySelector('textarea'))?.value`);
      assert.equal(errorFinalValue, 'host-composer-sentinel',
        'Tab must not reach the host textarea while an import error is showing; boundary=' + JSON.stringify(errorWalk));
      assert.equal(errorWalk.trace.length, 0,
        'focus must remain inside the panel in the import-error state; boundary=' + JSON.stringify(errorWalk));
      await cdp.call('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 });
      await cdp.call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 });
      await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='settings-cancel'&&!document.querySelector('iframe[aria-label]')
          ?state:false;
      })()`), 5000, 'Escape closes the generated settings editor and restores ownership');
      const restored = await cdp.evaluate(`(()=>{
        const input=document.querySelector('.composer textarea')||document.querySelector('textarea');
        return {value:input?.value,inputFocused:document.activeElement===input,
          rootInert:document.querySelector('#root')?.inert,
          lateHostInert:document.querySelector('#fixture-focus-late-host-button')?.inert,
          preexistingInert:document.querySelector('#fixture-focus-preexisting-inert')?.inert};
      })()`);
      assert.deepEqual(restored, { value: 'host-composer-sentinel', inputFocused: true,
        rootInert: false, lateHostInert: false, preexistingInert: true },
      'closing returns focus and each host node to its latest or original state');
      await cdp.evaluate(`document.querySelector('#fixture-focus-late-host-button')?.remove();delete window.__fixtureFocusDetachedButton;document.querySelector('#fixture-focus-preexisting-inert')?.remove()`);
      return { boundaries, trace, textareaReached, finalValue, isolation, restored,
        importError: importErrorAlert, errorWalk };
    });

    await navigate('/fixture.html?generated-payload=1&no-initial-wallpaper=1');
    await check('generated settings preview keeps keyboard focus out of the host composer', async () => {
      await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready?state:false;
      })()`), 15000, 'generated animation is ready before opening settings');
      const hostInput = await cdp.evaluate(`(()=>{
        const input=document.querySelector('.composer textarea')||document.querySelector('textarea');
        if(!input)return false;
        input.value='preview-host-sentinel';input.focus();
        return {focused:document.activeElement===input,accepted:window.__startupAPI.openSettings()};
      })()`);
      assert.deepEqual(hostInput, { focused: true, accepted: true },
        'the fixture has a focused host textarea before the generated settings dialog opens');
      await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
        const dialog=doc?.querySelector('[data-agent-skin-settings]');
        return window.__startupAPI.status().phase==='settings'&&dialog?.open
          ?{runId:window.__startupAPI.status().runId,dialogOpen:dialog.open}:false;
      })()`), 15000, 'generated settings dialog opens inside the real overlay iframe');
      await cdp.evaluate(`(()=>{
        const dialog=document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-settings]');
        dialog.querySelector('[data-agent-skin-settings-tab="startup"]').click();
        const title=dialog.querySelector('input[maxlength="16"]');
        title.value='Draft survives';title.dispatchEvent(new dialog.ownerDocument.defaultView.Event('input',{bubbles:true}));
      })()`);
      await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        frame.contentDocument.querySelector('[data-agent-skin-preview-animation]').click();
      })()`);
      const preview = await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
        const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
        const close=overlay?.querySelector('[data-agent-skin-settings-preview-close]');
        const previewFrame=overlay?.querySelector('[data-agent-skin-settings-preview-frame]');
        return overlay&&close&&previewFrame?{runId:window.__startupAPI.status().runId}:false;
      })()`), 10000, 'generated settings preview mounts');
      const previewState = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame.contentDocument;
        const close=doc.querySelector('[data-agent-skin-settings-preview-close]');
        return {hostFrameFocused:document.activeElement===frame,rootInert:document.querySelector('#root')?.inert,
          previewFrameTabIndex:doc.querySelector('[data-agent-skin-settings-preview-frame]')?.tabIndex,
          closeFocused:doc.activeElement===close};
      })()`);
      assert.deepEqual(previewState, { hostFrameFocused: true, rootInert: true, previewFrameTabIndex: -1, closeFocused: true });
      const focusLoss = [];
      for (const shiftKey of [false, false, true, true]) {
        for (let index = 0; index < 32; index++) {
          await dispatchTab(shiftKey);
          const focus = await cdp.evaluate(`(()=>{
            const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
            const overlay=doc?.querySelector('[data-agent-skin-settings-preview]');
            const active=doc?.activeElement;
            return {hostFrameFocused:document.activeElement===frame,
              insidePreview:!!overlay&&!!active&&(active===overlay||overlay.contains(active)),
              hostTextareaFocused:document.activeElement===document.querySelector('.composer textarea')
                ||document.activeElement===document.querySelector('textarea')};
          })()`);
          if (!focus.hostFrameFocused || !focus.insidePreview || focus.hostTextareaFocused) {
            focusLoss.push({ shiftKey, index, ...focus });
            await cdp.call('Input.insertText', { text: 'focus-leak' });
            break;
          }
        }
        if (focusLoss.length) break;
      }
      const after = await cdp.evaluate(`(()=>({
        value:(document.querySelector('.composer textarea')||document.querySelector('textarea'))?.value,
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        phase:window.__startupAPI.status().phase
      }))()`);
      assert.deepEqual(focusLoss, [], 'forward and reverse Tab stay inside the active generated preview');
      assert.equal(after.value, 'preview-host-sentinel', 'keyboard input cannot modify the host composer');
      assert.equal(after.frameCount, 1);
      assert.equal(after.phase, 'settings');
      await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        doc.querySelector('[data-agent-skin-settings-preview-close]').click();
      })()`);
      const returned = await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame?.contentDocument;
        const dialog=doc?.querySelector('[data-agent-skin-settings]');
        const title=dialog?.querySelector('input[maxlength="16"]');
        const previewButton=dialog?.querySelector('[data-agent-skin-preview-animation]');
        return dialog?.open&&!dialog.querySelector('[data-agent-skin-settings-preview]')
          ?{draftTitle:title?.value,previewButtonFocused:doc.activeElement===previewButton,
            hostFrameFocused:document.activeElement===frame,rootInert:document.querySelector('#root')?.inert}:false;
      })()`), 5000, 'closing the generated preview returns to the settings draft');
      assert.deepEqual(returned, { draftTitle: 'Draft survives', previewButtonFocused: true,
        hostFrameFocused: true, rootInert: true });
      const returnWalk = await walkGeneratedSettingsTabs();
      const returnWalkValue = await cdp.evaluate(`(document.querySelector('.composer textarea')||document.querySelector('textarea'))?.value`);
      assert.equal(returnWalkValue, 'preview-host-sentinel',
        'Tab must not reach the host textarea after returning from preview; boundary=' + JSON.stringify(returnWalk));
      assert.equal(returnWalk.trace.length, 0,
        'focus must remain inside the panel after preview return; boundary=' + JSON.stringify(returnWalk));
      await cdp.call('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 });
      await cdp.call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 });
      await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='complete'&&!document.querySelector('iframe[aria-label]')`),
        5000, 'settings dialog closes after preview return');
      const restored = await cdp.evaluate(`(()=>({
        value:(document.querySelector('.composer textarea')||document.querySelector('textarea'))?.value,
        inputFocused:document.activeElement===(document.querySelector('.composer textarea')||document.querySelector('textarea')),
        rootInert:document.querySelector('#root')?.inert
      }))()`);
      assert.deepEqual(restored, { value: 'preview-host-sentinel', inputFocused: true, rootInert: false });
      return { runId: preview.runId, focusCycles: 4, hostComposerValue: after.value, returned, returnWalk, restored };
    });

    await check('generated payload settings panel passes zh-CN/en, light/dark, and 390/980/1512 layout matrix', async () => {
      assert.ok(generatedPayloadSource !== null, 'requires the generated install.js payload');
      const expectedTabs = { 'zh-CN': ['启动动画', '工作区背景', '关于与状态'], en: ['Startup animation', 'Workspace background', 'About & status'] };
      const matrix = [];
      // A previous check may leave another tab in front, which pauses this page's
      // animation frames. Exercise that case before bringing the fixture forward.
      const { targetId: otherTarget } = await cdp.call('Target.createTarget', { url: 'about:blank' });
      try {
        await cdp.call('Page.bringToFront');
        for (const locale of ['zh-CN', 'en']) for (const theme of ['light', 'dark']) {
          await cdp.call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: false });
          await cdp.call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: theme }] });
          await navigate('/fixture.html?generated-payload=1&no-initial-wallpaper=1');
          await cdp.evaluate(`(()=>{document.documentElement.lang=${JSON.stringify(locale)};document.documentElement.dataset.theme=${JSON.stringify(theme)};})()`);
          await awaitGeneratedReady('generated payload ready for ' + locale + '/' + theme);
          await until(() => cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]')?.contentDocument;
            return d?.documentElement.lang===${JSON.stringify(locale)}&&d.documentElement.dataset.theme===${JSON.stringify(theme)};})()`),
          5000, 'generated appearance update');
          assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
          await until(() => cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]')?.contentDocument;
            return d?.querySelector('dialog[data-agent-skin-settings]')?.open===true;})()`), 15000, 'generated settings dialog');
          await until(() => cdp.evaluate(`document.querySelector('iframe[aria-label]')?.contentDocument
            ?.querySelector('[data-agent-skin-workspace-preview-image]')?.naturalWidth>0`), 10000, 'generated preview artwork');
          for (const viewport of [{ width: 390, height: 844 }, { width: 980, height: 900 }, { width: 1512, height: 982 }]) {
            await cdp.call('Emulation.setDeviceMetricsOverride', { ...viewport, deviceScaleFactor: 1, mobile: false });
            await cdp.evaluate('new Promise(resolve => { let settled = false; const settle = () => { if (settled) return; settled = true; resolve(); }; requestAnimationFrame(() => requestAnimationFrame(settle)); setTimeout(settle, 300); })');
            await until(() => cdp.evaluate(`document.querySelector('iframe[aria-label]')?.contentWindow.innerWidth===${viewport.width}`),
              5000, 'CSS viewport ' + viewport.width);
            const cell = await cdp.evaluate(`(()=>{
              const frame=document.querySelector('iframe[aria-label]'),d=frame?.contentDocument,dialog=d?.querySelector('dialog[data-agent-skin-settings]');
              if(!d||!dialog)return null;
              const hit=e=>{e.scrollIntoView?.({block:'center',inline:'nearest'});const r=e.getBoundingClientRect(),t=d.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
                return {visible:e.getClientRects().length>0&&r.width>0&&r.height>0,hit:t===e||e.contains(t),
                  rect:{x:r.x,y:r.y,width:r.width,height:r.height},target:t?.tagName??null};};
              const tabs=[...dialog.querySelectorAll('[role=tab]')];
              const sections=tabs.map(t=>{t.click();const panel=dialog.querySelector('#'+CSS.escape(t.getAttribute('aria-controls')));
                return {name:t.textContent.trim(),linked:!!panel,visible:!!panel&&!panel.hidden,hit:hit(t),
                  overflow:dialog.scrollWidth>dialog.clientWidth+1||d.documentElement.scrollWidth>frame.contentWindow.innerWidth+1
                    ||panel?.scrollWidth>panel?.clientWidth+1};});
              const startup=dialog.querySelector('[data-agent-skin-settings-tab=startup]');startup.click();
              const fields=[...dialog.querySelector('[data-agent-skin-settings-section=startup]').querySelectorAll('[maxlength]')].map(e=>{const limit=e.maxLength;
                e.value=${JSON.stringify(locale==='en'?'A':'舟')}.repeat(limit);e.dispatchEvent(new d.defaultView.Event('input',{bubbles:true}));
                const result={limit,length:e.value.length,name:e.labels?.[0]?.textContent.trim()||'',visible:hit(e).visible,
                  horizontalOverflow:dialog.scrollWidth>dialog.clientWidth+1||d.documentElement.scrollWidth>frame.contentWindow.innerWidth+1};
                e.value='';e.dispatchEvent(new d.defaultView.Event('input',{bubbles:true}));return {...result,empty:e.value===''};});
              const previewAction=dialog.querySelector('[data-agent-skin-preview-animation]'),previewActionHit=hit(previewAction);
              dialog.querySelector('[data-agent-skin-settings-tab=about]').click();
              const summary=dialog.querySelector('[data-agent-skin-settings-section=about] summary'),summaryHit=hit(summary),details=summary.closest('details');
              if(!details.open)summary.click();
              const detailsOpened=details.open;
              const version=dialog.querySelector('[data-agent-skin-setting-value=version]')?.textContent.trim();
              dialog.querySelector('[data-agent-skin-settings-tab=workspace]').click();
              const presetDetails=dialog.querySelector('[data-agent-skin-disclosure=presets]'),preset=dialog.querySelector('[data-agent-skin-preset-name]');
              presetDetails.open=true;preset.value=${JSON.stringify(locale==='en'?'A':'舟')}.repeat(preset.maxLength);
              preset.dispatchEvent(new d.defaultView.Event('input',{bubbles:true}));
              const presetField={limit:preset.maxLength,length:preset.value.length,name:preset.labels?.[0]?.textContent.trim()||'',...hit(preset)};
              preset.value='';preset.dispatchEvent(new d.defaultView.Event('input',{bubbles:true}));presetDetails.open=false;
              const range=dialog.querySelector('input[type=range]'),preview=dialog.querySelector('[data-agent-skin-workspace-preview]');
              const choose=dialog.querySelector('[data-agent-skin-image-action=artwork]');
              const strength=[0,42,75].map(value=>{range.value=String(value);range.dispatchEvent(new d.defaultView.Event('input',{bubbles:true}));
                const image=dialog.querySelector('[data-agent-skin-workspace-preview-image]'),wash=dialog.querySelector('[data-agent-skin-workspace-preview-wash]');
                return {value:range.value,readout:dialog.querySelector('[data-agent-skin-wallpaper-strength-value]')?.textContent.trim(),
                  aria:range.getAttribute('aria-valuetext'),hidden:image.hidden,imageDisplay:d.defaultView.getComputedStyle(image).display,
                  washDisplay:d.defaultView.getComputedStyle(wash).display,washImage:d.defaultView.getComputedStyle(wash).backgroundImage,
                  imageWidth:image.getBoundingClientRect().width,naturalWidth:image.naturalWidth};});
              const footer=[...dialog.querySelectorAll('footer button')].map(e=>({name:e.textContent.trim(),...hit(e),enabled:!e.disabled}));
              const css=e=>d.defaultView.getComputedStyle(e), rgba=v=>{const p=String(v).match(/[0-9.]+/g)?.map(Number);
                return p?.length>=3?{rgb:p.slice(0,3),alpha:p.length>3?p[3]:1}:null;};
              const lum=c=>c?.map(x=>x/255<=.04045?x/3294.6:((x/255+.055)/1.055)**2.4)
                .reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
              const base=rgba(css(dialog).backgroundColor), blend=(top,bottom)=>top.rgb.map((x,i)=>x*top.alpha+bottom[i]*(1-top.alpha));
              const ratio=(fg,bg)=>{if(!base||base.alpha<.99)return 0;const f=rgba(fg),b=rgba(bg);if(!f||!b)return 0;
                const background=b.alpha<.99?blend(b,base.rgb):b.rgb,foreground=f.alpha<.99?blend(f,background):f.rgb;
                const a=lum(foreground),c=lum(background);return Number(((Math.max(a,c)+.05)/(Math.min(a,c)+.05)).toFixed(2));};
              const title=dialog.querySelector('h2'),normal=dialog.querySelector('[data-agent-skin-settings-section=workspace] label span');
              const muted=dialog.querySelector('[data-agent-skin-running-version]'),selected=dialog.querySelector('[role=tab][aria-selected=true]');
              const contrast={title:ratio(css(title).color,css(dialog).backgroundColor),normal:ratio(css(normal).color,css(dialog).backgroundColor),
                muted:ratio(css(muted).color,css(dialog).backgroundColor),selected:ratio(css(selected).color,css(selected).backgroundColor)};
              const active=dialog.querySelector('[role=tabpanel]:not([hidden])'),r=dialog.getBoundingClientRect();
              return {locale:d.documentElement.lang,theme:d.documentElement.dataset.theme,width:frame.contentWindow.innerWidth,height:frame.contentWindow.innerHeight,
                dialog:{left:r.left,right:r.right,scroll:dialog.scrollWidth,client:dialog.clientWidth,root:d.documentElement.scrollWidth},
                version:dialog.querySelector('[data-agent-skin-running-version]')?.textContent.trim(),titleSize:parseFloat(css(title).fontSize),
                titleWeight:parseInt(css(title).fontWeight,10),tabs:tabs.map(t=>t.textContent.trim()),sections,
                activeOverflow:active.scrollWidth>active.clientWidth+1,fields,presetField,previewAction:{name:previewAction.textContent.trim(),...previewActionHit},
                summary:{name:summary.textContent.trim(),...summaryHit,opened:detailsOpened,version},
                workspace:{preview:hit(preview),previewName:preview.getAttribute('aria-label'),rangeName:range.labels?.[0]?.textContent.trim(),choose:{name:choose.textContent.trim(),...hit(choose)}},
                strength,footer,contrast};
            })()`);
            assert.ok(cell, 'settings panel is present');
            assert.deepEqual({ locale: cell.locale, theme: cell.theme, width: cell.width, height: cell.height }, { locale, theme, ...viewport });
            assert.ok(cell.version.includes(packageMetadata.runtime_version)&&cell.version.includes(packageMetadata.runtime_build),
              'visible identity matches the package runtime version and build');
            assert.deepEqual(cell.tabs.slice().sort(), expectedTabs[locale].slice().sort(), 'localized section names are present');
            assert.ok(cell.sections.every(s=>s.linked&&s.visible&&s.hit.visible&&s.hit.hit&&!s.overflow), 'each named section is reachable without horizontal overflow');
            assert.ok(cell.dialog.left>=-1&&cell.dialog.right<=viewport.width+1&&cell.dialog.scroll<=cell.dialog.client+1
              &&cell.dialog.root<=viewport.width+1&&!cell.activeOverflow, 'settings panel fits the CSS viewport');
            assert.deepEqual(cell.fields.map(f=>[f.limit,f.length,f.empty]), [[16,16,true],[48,48,true],[60,60,true]]);
            assert.deepEqual([cell.presetField.limit,cell.presetField.length],[40,40]);
            assert.ok(cell.presetField.name&&cell.presetField.visible&&cell.presetField.hit,'preset name is labeled and reachable');
            assert.ok(cell.fields.every(f=>f.name&&f.visible&&!f.horizontalOverflow),
              'bounded text fields have visible names and do not overflow horizontally: '+JSON.stringify({locale,theme,width:viewport.width,fields:cell.fields}));
            if (!cell.previewAction.hit) {
              const diagnostic = await cdp.evaluate(`(()=>{
                const frame=document.querySelector('iframe[aria-label]'),d=frame?.contentDocument,dialog=d?.querySelector('dialog[data-agent-skin-settings]');
                dialog.querySelector('[data-agent-skin-settings-tab=startup]').click();
                const button=dialog.querySelector('[data-agent-skin-preview-animation]');button.scrollIntoView({block:'center',inline:'nearest'});
                const r=button.getBoundingClientRect(),target=d.elementFromPoint(r.left+r.width/2,r.top+r.height/2),footer=dialog.querySelector('footer'),f=footer.getBoundingClientRect();
                return {button:button.textContent.trim(),buttonRect:{x:r.x,y:r.y,width:r.width,height:r.height},
                  target:target&&{tag:target.tagName,text:target.textContent.trim().slice(0,80),rect:(()=>{const q=target.getBoundingClientRect();return {x:q.x,y:q.y,width:q.width,height:q.height};})()},
                  panel:{scrollTop:dialog.scrollTop,scrollHeight:dialog.scrollHeight,clientHeight:dialog.clientHeight},
                  footer:{x:f.x,y:f.y,width:f.width,height:f.height,top:f.top,bottom:f.bottom}};
              })()`);
              const evidence = await screenshot('settings-matrix-hit-failure-' + locale + '-' + theme + '-' + viewport.width + '.png');
              throw new Error('animation preview action hit-test failed: ' + JSON.stringify({locale,theme,width:viewport.width,diagnostic,screenshot:evidence.file}));
            }
            assert.ok(cell.previewAction.name&&cell.previewAction.visible&&cell.previewAction.hit,
              'animation preview action is reachable: '+JSON.stringify({locale,theme,width:viewport.width,action:cell.previewAction}));
            assert.ok(cell.summary.name&&cell.summary.visible&&cell.summary.hit&&cell.summary.opened
              &&cell.summary.version.includes(packageMetadata.runtime_version)&&cell.summary.version.includes(packageMetadata.runtime_build),
              'about and build-details action is reachable: '+JSON.stringify({locale,theme,width:viewport.width,summary:cell.summary}));
            assert.ok(cell.workspace.preview.visible&&cell.workspace.preview.hit&&cell.workspace.previewName
              &&cell.workspace.rangeName&&cell.workspace.choose.name&&cell.workspace.choose.visible&&cell.workspace.choose.hit,
              'workspace preview, strength name, and choose-background action are reachable');
            assert.ok(cell.footer.length>=2&&cell.footer.every(a=>a.name&&a.visible&&a.hit&&a.enabled), 'footer actions are reachable');
            assert.ok(cell.strength[0].readout===(locale==='en'?'Off':'关闭')&&cell.strength[0].aria===cell.strength[0].readout
              &&cell.strength[0].hidden&&cell.strength[0].imageDisplay==='none'&&cell.strength[0].washDisplay==='none'
              &&cell.strength[0].washImage==='none', 'strength 0 closes the draft artwork and exposes its off state');
            assert.ok(cell.strength.slice(1).every(s=>s.readout===String(s.value)&&s.aria===null&&!s.hidden
              &&s.imageDisplay==='block'&&s.washDisplay==='block'&&s.washImage!=='none'&&s.imageWidth>0&&s.naturalWidth>0),
              'strength 42 and 75 show the generated artwork preview');
            assert.notEqual(cell.strength[1].washImage,cell.strength[2].washImage, '42 and 75 have distinct preview strengths');
            const titleThreshold=cell.titleSize>=24||(cell.titleSize>=18.66&&cell.titleWeight>=700)?3:4.5;
            assert.ok(cell.contrast.title>=titleThreshold&&cell.contrast.normal>=4.5&&cell.contrast.muted>=4.5&&cell.contrast.selected>=4.5,
              'representative parsed text/surface token contrast meets thresholds: '+JSON.stringify(cell.contrast));
            let actionScreenshot=null;
            if(locale==='en'&&theme==='light'&&viewport.width===390){
              await cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]').contentDocument,dialog=d.querySelector('dialog[data-agent-skin-settings]');
                dialog.querySelector('[data-agent-skin-settings-tab=startup]').click();
                dialog.querySelector('[data-agent-skin-preview-animation]').scrollIntoView({block:'center',inline:'nearest'});})()`);
              actionScreenshot=(await screenshot('settings-matrix-preview-action-en-light-390.png')).file;
            }
            matrix.push({locale,theme,...viewport,version:cell.version,tabs:cell.tabs,sections:cell.sections.map(s=>({name:s.name,overflow:s.overflow})),
              fields:cell.fields.map(f=>({limit:f.limit,length:f.length,empty:f.empty,name:f.name,horizontalOverflow:f.horizontalOverflow})),strength:cell.strength.map(s=>({value:s.value,readout:s.readout,
                imageDisplay:s.imageDisplay,washDisplay:s.washDisplay,washImage:s.washImage})),contrast:cell.contrast,actionScreenshot});
          }
        }
      } finally {
        try { await cdp.call('Target.closeTarget', { targetId: otherTarget }); }
        finally {
          try { await cdp.call('Emulation.clearDeviceMetricsOverride'); }
          finally { await cdp.call('Emulation.setEmulatedMedia', { features: [] }); }
        }
      }
      return { payload: options.generatedPayload, matrix };
    });

    await navigate('/fixture.html?generated-payload=1&no-initial-wallpaper=1');
    await check('generated appearance entry avoids sidebar update and profile controls', async () => {
      await until(() => cdp.evaluate(`window.__startupAPI?.status().phase==='playing' && window.__startupAPI.status().ready`),
        15000, 'generated animation ready before sidebar check');
      assert.equal(await cdp.evaluate(`(()=>{
        const button=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;button.click();return true;
      })()`), true);
      await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='complete'`), 5000, 'generated animation skipped');
      return verifySidebarUpdatePlacement();
    });
    await navigate('/fixture.html?generated-payload=1&no-initial-wallpaper=1');
    await check('generated appearance fallback preserves crowded host controls', async () => {
      await until(() => cdp.evaluate(`window.__startupAPI?.status().phase==='playing' && window.__startupAPI.status().ready`),
        15000, 'generated animation ready before crowded fallback check');
      assert.equal(await cdp.evaluate(`(()=>{
        const button=document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;button.click();return true;
      })()`), true);
      await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='complete'`), 5000, 'generated animation skipped');
      try {
        await cdp.evaluate(`(()=>{
          const side=document.querySelector('.sidebar');
          for(let top=0;top<innerHeight;top+=48){
            const item=document.createElement('button');item.dataset.fixtureCrowded='1';
            item.style.cssText='position:fixed;left:10px;top:'+top+'px;width:48px;height:48px;z-index:100';
            item.addEventListener('click',()=>{window.__generatedHostClicks=(window.__generatedHostClicks||0)+1});
            side.appendChild(item);
          }
        })()`);
        const result = await until(() => cdp.evaluate(`(()=>{
          const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),e=entry.getBoundingClientRect();
          const controls=[...document.querySelectorAll('[data-fixture-crowded]')];
          const overlap=controls.some(control=>{
            const r=control.getBoundingClientRect();
            return r.left<e.right&&r.right>e.left&&r.top<e.bottom&&r.bottom>e.top;
          });
          const host=controls[0],r=host.getBoundingClientRect();
          return entry.style.display==='block'&&!overlap
            &&document.elementFromPoint(e.left+e.width/2,e.top+e.height/2)===entry
            &&document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===host
            ?{hostX:r.left+r.width/2,hostY:r.top+r.height/2}:false;
        })()`), 3000, 'generated fallback and host controls are simultaneously reachable');
        await cdp.call('Input.dispatchMouseEvent', { type: 'mousePressed', x: result.hostX, y: result.hostY, button: 'left', clickCount: 1 });
        await cdp.call('Input.dispatchMouseEvent', { type: 'mouseReleased', x: result.hostX, y: result.hostY, button: 'left', clickCount: 1 });
        assert.equal(await cdp.evaluate('window.__generatedHostClicks'), 1);
        const opened = await clickAppearanceEntry();
        assert.ok(['loading', 'settings'].includes(opened?.state?.phase));
        return { hostClickable: true, appearanceOpened: true };
      } finally {
        await cdp.evaluate(`document.querySelectorAll('[data-fixture-crowded]').forEach(item=>item.remove())`);
      }
    });
    await navigate('/fixture.html?generated-payload=1');
    await check('pinned gated wallpaper continuity', async()=>{
      await cdp.evaluate(`(()=>{ const style=document.createElement('style'); style.textContent='html:not([data-azhou-wallpaper=active]) body,html:not([data-azhou-wallpaper=active]) main {background:#00ff65!important}';document.head.append(style)})()`);
      await until(()=>cdp.evaluate(`(()=>{const s=window.__startupAPI?.status();return s?.phase==='complete'&&s.wallpaper?.applied?s:false})()`),25000,'startup complete');
      await cdp.evaluate(`(()=>{const raw=HTMLImageElement.prototype.decode, bitmap=window.createImageBitmap, held=new WeakSet();
        let release;const delay=new Promise(r=>{release=r;});window.__continuityRelease=release;window.__holdContinuity=false;
        window.__continuityDecodes=0;window.__revokedScenes=[];const revoke=URL.revokeObjectURL;
        URL.revokeObjectURL=function(value){window.__revokedScenes.push(value);return revoke.call(this,value);};
        HTMLImageElement.prototype.decode=function(...a){window.__continuityDecodes++;const actual=raw.apply(this,a); if(!window.__holdContinuity)return actual;held.add(this);return Promise.all([actual,delay]).then(([value])=>value);};
        if(bitmap)window.createImageBitmap=function(el,...args){return held.has(el)?delay.then(()=>bitmap.call(this,el,...args)):bitmap.call(this,el,...args);};})()`);
      const states=[]; let firstFrame;
      const actions=[
        [0,""],[1,"window.dispatchEvent(new Event('blur'));document.dispatchEvent(new Event('visibilitychange'))"],[3,"window.dispatchEvent(new Event('focus'));document.dispatchEvent(new Event('visibilitychange'))"],[5,"window.dispatchEvent(new Event('pagehide'));window.dispatchEvent(new Event('pageshow'))"],[7,"{window.__holdContinuity=true;const main=document.querySelector('[data-app-shell-main-surface]'); const next=main.cloneNode(true); for(const n of [next,...next.querySelectorAll('*')]) for(const k of ['data-azhou-wallpaper-plane','data-azhou-wallpaper-pseudo','data-azhou-wallpaper-decoration'])n.removeAttribute(k); main.replaceWith(next); window.__azhouWallpaper.status(); window.dispatchEvent(new Event('resize'));}"],[12,"window.__holdContinuity=false;window.__continuityRelease();"],[17,"{const main=document.querySelector('[data-app-shell-main-surface]');window.__fixtureDetached=main; window.__fixtureParent=main.parentNode; main.remove();}"],[21,"window.__fixtureParent.append(window.__fixtureDetached);window.dispatchEvent(new Event('resize'));"]
      ];
      for(let i=0;i<26;i++){
        const match=actions.find(a=>a[0]===i);
        if(match&&match[1]) await cdp.evaluate(match[1]);
        await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
        const frame=await cdp.call('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});
        if(i===0)firstFrame=frame.data;
        await writeFile(join(options.out,'visual-'+String(i).padStart(2,'0')+'.png'),Buffer.from(frame.data,'base64'));
        const state=await cdp.evaluate(`(()=>{const s=window.__startupAPI.status();return {decodes:window.__continuityDecodes,phase:s.phase,runId:s.runId,frames:document.querySelectorAll('iframe[aria-label]').length,applied:s.wallpaper?.applied,revocations:window.__revokedScenes.length}})()`);
        states.push({i,...state,samePNG:firstFrame===frame.data});
      }
      await writeFile(join(options.out,'sample-states.json'),JSON.stringify(states,null,2));
      assert.ok(states.slice(0,7).every(s=>s.applied&&s.decodes===0&&s.samePNG&&s.revocations===0),'focus and visibility changes should not disturb wallpaper');
      assert.ok(states.every(s=>s.phase==='complete'&&s.runId===states[0].runId&&s.frames===0),'the startup cover must not replay');
      assert.ok(states.slice(7,12).every(s=>s.applied&&s.decodes===0&&s.samePNG&&s.revocations===0),'valid successor should preserve decoded wallpaper: '+JSON.stringify(states.slice(7,12)));
      assert.ok(states.slice(17,21).every(s=>!s.applied&&!s.samePNG&&s.decodes===0&&s.revocations===1),'missing workspace must restore native pixels and relinquish old image');
      assert.ok(states.slice(21).every(s=>s.applied&&s.samePNG&&s.decodes===1&&s.revocations===1),'late validated workspace must independently decode and restore');
      return {states};
    });
    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('generated wallpaper survives a shell mounted after natural animation completion', async () => {
      const completed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='complete'&&state.completion?.cause==='natural'?state:false;
      })()`), 20000, 'natural animation finishes before shell mount');
      assert.equal(completed.wallpaper.failureCode, undefined,
        'wallpaper keeps waiting beyond the old five-second deadline and natural completion');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      const applied = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),wallpaper=window.__azhouWallpaper?.status();
        return state.wallpaper.applied&&wallpaper?.imageDecoded?{state,wallpaper,
          observers:window.__fixtureMutationObserverStats(),
          frames:document.querySelectorAll('iframe[aria-label]').length}:false;
      })()`), 5000, 'late shell receives wallpaper without replay');
      assert.equal(applied.state.runId, completed.runId);
      assert.equal(applied.frames, 0);
      assert.equal(applied.observers.wallpaperShellWait.active, 0);
      assert.equal(applied.observers.workspaceActive.active, 1, 'only the committed wallpaper retains an active observation lease');
      await cdp.evaluate('window.__startupAPI.dispose()');
      const released = await cdp.evaluate('window.__fixtureMutationObserverStats()');
      assert.equal(released.wallpaperShellWait.active, 0);
      assert.equal(released.workspaceActive.active, 0, 'disposing the owner releases its committed workspace lease');
      return { ...applied, released };
    });
    await navigate('/fixture.html?generated-payload=1');
    await check('generated cold start restores saved wallpaper after natural completion without another save', () => withColdStartupVideoProbe(cdp, async assertNoStartupVideo => {
      const fields = { introTitle: '冷启动恢复', wallpaperStrength: 19 };
      const initial = await awaitGeneratedReady('generated animation is ready before saving cold-start fields');
      const firstURL = await cdp.evaluate('location.href');
      assert.equal(await cdp.evaluate('window.__fixtureHost.__azhouStartup.openSettings()'), true,
        'the generated controller opens its Appearance settings');
      await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        return window.__startupAPI.status().phase==='settings'
          &&frame?.contentDocument.querySelector('[data-agent-skin-settings]')?.open?true:false;
      })()`), 10000, 'generated Appearance settings open before the first save');
      await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        doc.querySelector('[data-agent-skin-settings-tab="startup"]').click();
        const title=doc.querySelector('input[maxlength="16"]');
        title.value=${JSON.stringify(fields.introTitle)};
        title.dispatchEvent(new Event('input',{bubbles:true}));
        doc.querySelector('[data-agent-skin-settings-tab="workspace"]').click();
        const strength=doc.querySelector('input[type="range"]');
        strength.value='${fields.wallpaperStrength}';
        strength.dispatchEvent(new Event('input',{bubbles:true}));
        doc.querySelector('[data-agent-skin-settings] footer button:last-child').click();
      })()`);
      const saved = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='settings-save'
          &&state.runId===${initial.runId}&&!document.querySelector('iframe[aria-label]')?state:false;
      })()`), 15000, 'first generated settings save commits without replay');
      const firstTimeOrigin = await cdp.evaluate('performance.timeOrigin');

      await navigate('/fixture.html?generated-payload=1&hold-shell=1');
      const nextURL = await cdp.evaluate('location.href');
      const nextTimeOrigin = await cdp.evaluate('performance.timeOrigin');
      assert.equal(new URL(nextURL).origin, new URL(firstURL).origin,
        'the cold startup is a new document on the same origin as the committed IndexedDB record');
      assert.notEqual(nextTimeOrigin, firstTimeOrigin, 'navigation created a new top-level document');
      const coldRun = await awaitGeneratedReady('cold generated animation is ready while its shell is withheld');
      const held = await cdp.evaluate(`(()=>({
        state:window.__startupAPI.status(),
        shellCount:document.querySelectorAll('[data-app-shell-frame]').length,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length
      }))()`);
      assert.equal(held.state.runId, coldRun.runId);
      assert.equal(held.state.phase, 'playing');
      assert.equal(held.state.wallpaper.applied, false);
      assert.equal(held.shellCount, 0);
      assert.equal(held.styleCount, 0);

      const natural = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='natural'
          &&!document.querySelector('iframe[aria-label]')?state:false;
      })()`), 20000, 'the cold generated startup finishes its full natural playback before shell mount');
      assert.equal(natural.runId, coldRun.runId);
      assert.equal(natural.wallpaper.applied, false,
        'the wallpaper remains pending until the deliberately withheld shell mounts');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true,
        'the synthetic supported shell is released after natural completion');

      const inspectWallpaper = () => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status(),api=window.__azhouWallpaper?.status?.();
        const style=document.querySelector('#azhou-wallpaper-style');
        const wash=document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash');
        return {startup:state?.wallpaper||null,api:api||null,
          owner:window.__azhouWallpaper?.owner||null,
          apiKeys:Object.keys(window.__azhouWallpaper||{}).sort(),
          styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
          styleOwner:style?.getAttribute('data-azhou-owner')||null,
          washStops:Array.from(wash.matchAll(/var\\(--azhou-base\\)\\s+(\\d+)%/g),match=>Number(match[1])),
          wash};
      })()`);
      let restored;
      try {
        restored = await until(async () => {
          const state = await inspectWallpaper();
          return state.startup?.applied&&state.startup.imageDecoded
            &&state.api?.applied&&state.api.imageDecoded&&state.styleCount===1?state:false;
        }, 5000, 'saved wallpaper is restored after the late shell mounts without reopening settings');
      } catch (error) {
        restored = { ...(await inspectWallpaper()), waitError: error.message };
      }
      const expectedWashStops = [89, 92, 95, 93, 86, 71, 68];
      const appliedWithoutSave = restored.startup?.applied===true
        &&restored.startup.imageDecoded===true&&restored.api?.applied===true
        &&restored.api.imageDecoded===true&&restored.owner==='azhou.codex-startup-animation'
        &&restored.styleCount===1&&restored.styleOwner==='azhou.codex-startup-animation';
      const strengthMatches = JSON.stringify(restored.washStops)===JSON.stringify(expectedWashStops);
      if (!appliedWithoutSave || !strengthMatches) {
        const beforeRecoverySave = restored;
        let recoverySave;
        try {
          assert.equal(await cdp.evaluate('window.__fixtureHost.__azhouStartup.openSettings()'), true,
            'recovery can open Appearance after the cold run completes');
          await until(() => cdp.evaluate(`(()=>{
            const frame=document.querySelector('iframe[aria-label]');
            return window.__startupAPI.status().phase==='settings'
              &&frame?.contentDocument.querySelector('[data-agent-skin-settings]')?.open?true:false;
          })()`), 10000, 'Appearance opens for the failure recovery save');
          const recoveryFields = await cdp.evaluate(`(()=>{
            const doc=document.querySelector('iframe[aria-label]').contentDocument;
            doc.querySelector('[data-agent-skin-settings-tab="startup"]').click();
            const introTitle=doc.querySelector('input[maxlength="16"]')?.value;
            doc.querySelector('[data-agent-skin-settings-tab="workspace"]').click();
            return {introTitle,wallpaperStrength:Number(doc.querySelector('input[type="range"]')?.value)};
          })()`);
          await cdp.evaluate(`document.querySelector('iframe[aria-label]').contentDocument
            .querySelector('[data-agent-skin-settings] footer button:last-child').click()`);
          let afterSave;
          try {
            afterSave = await until(async () => {
              const state = await inspectWallpaper();
              const controller = await cdp.evaluate('window.__startupAPI.status()');
              return controller.phase==='complete'&&controller.completion?.cause==='settings-save'
                &&state.startup?.applied&&state.api?.imageDecoded?{...state,controller}:false;
            }, 10000, 'recovery Appearance Save applies the persisted wallpaper');
          } catch (saveError) {
            afterSave = { ...(await inspectWallpaper()), waitError: saveError.message,
              controller: await cdp.evaluate('window.__startupAPI.status()') };
          }
          recoverySave = { recoveryFields, afterSave };
        } catch (recoveryError) {
          recoverySave = { error: recoveryError.message,
            afterSave: await inspectWallpaper().catch(statusError => ({ error: statusError.message })) };
        }
        assert.ok(appliedWithoutSave && strengthMatches,
          'saved wallpaper must restore at strength 19 after natural completion and late shell mount, before another Save; '
          + JSON.stringify({ natural: { runId: natural.runId, completion: natural.completion },
            beforeRecoverySave, recoverySave, expectedWashStops }));
      }

      assert.deepEqual(restored.washStops, expectedWashStops,
        'the applied wallpaper wash is generated from the persisted wallpaperStrength=19');
      assert.equal(await cdp.evaluate('window.__fixtureHost.__azhouStartup.openSettings()'), true,
        'Appearance can be opened after wallpaper restoration for a read-only persistence check');
      await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        return window.__startupAPI.status().phase==='settings'
          &&frame?.contentDocument.querySelector('[data-agent-skin-settings]')?.open?true:false;
      })()`), 10000, 'read-only Appearance persistence check opens');
      const readback = await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        doc.querySelector('[data-agent-skin-settings-tab="startup"]').click();
        const introTitle=doc.querySelector('input[maxlength="16"]')?.value;
        doc.querySelector('[data-agent-skin-settings-tab="workspace"]').click();
        return {introTitle,wallpaperStrength:Number(doc.querySelector('input[type="range"]')?.value)};
      })()`);
      assert.deepEqual(readback, fields,
        'the newly opened Appearance panel reads the saved title and wallpaperStrength from IndexedDB without editing them');
      await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        frame.contentWindow.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true}));
      })()`);
      const canceled = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='settings-cancel'
          &&!document.querySelector('iframe[aria-label]')?state:false;
      })()`), 5000, 'read-only Appearance check closes without saving');
      return { firstSave: { runId: saved.runId, completion: saved.completion },
        sameOrigin: new URL(firstURL).origin, timeOriginChanged: nextTimeOrigin!==firstTimeOrigin,
        coldRun: { runId: coldRun.runId, phase: coldRun.phase },
        natural: { runId: natural.runId, completion: natural.completion }, held,
        wallpaperWithoutSave: { owner: restored.owner, styleCount: restored.styleCount,
          apiKeys: restored.apiKeys, styleOwner: restored.styleOwner, washStops: restored.washStops },
        readback, closedWith: canceled.completion, startupVideo: await assertNoStartupVideo() };
    }));
    await cdp.call('Storage.clearDataForOrigin', { origin, storageTypes: 'indexeddb' });
    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('builder-generated wallpaper waits for a late supported shell and remains after animation completion', async () => {
      const waiting = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied
          &&document.querySelectorAll('[data-app-shell-frame]').length===0
          &&document.querySelectorAll('#azhou-wallpaper-style').length===0
          ?{phase:state.phase,runId:state.runId,wallpaper:state.wallpaper}:false;
      })()`), 15000, 'generated animation ready while the synthetic shell is not mounted');
      assert.equal(waiting.phase, 'playing');
      assert.equal(waiting.wallpaper.applied, false);
      assert.equal(waiting.wallpaper.imageDecoded, false);
      await delay(250);
      const held = await cdp.evaluate(`(()=>({state:window.__startupAPI.status(),
        shellCount:document.querySelectorAll('[data-app-shell-frame]').length,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length}))()`);
      assert.equal(held.state.phase, 'playing');
      assert.equal(held.state.ready, true);
      assert.equal(held.state.wallpaper.applied, false);
      assert.equal(held.shellCount, 0);
      assert.equal(held.styleCount, 0);

      assert.equal(await cdp.evaluate('window.__releaseShell()'), true, 'the supported synthetic shell mounts later');
      let applied;
      try {
        applied = await until(() => cdp.evaluate(`(()=>{
          const state=window.__startupAPI.status().wallpaper;
          const api=window.__azhouWallpaper?.status?.();
          const style=document.querySelector('#azhou-wallpaper-style');
          return state.applied&&state.imageDecoded&&api?.applied&&api.imageDecoded&&style
            ?{controller:state,api,owner:window.__azhouWallpaper.owner,
              styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
              styleOwner:style.getAttribute('data-azhou-owner')}:false;
        })()`), 5000, 'wallpaper apply after the supported shell mounts');
      } catch (error) {
        const afterMount = await cdp.evaluate(`(()=>({state:window.__startupAPI.status(),
          shellCount:document.querySelectorAll('[data-app-shell-frame]').length,
          styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
          wallpaperOwner:window.__azhouWallpaper?.owner||null}))()`);
        error.message += '; beforeMount=' + JSON.stringify({ waiting, held })
          + '; afterMount=' + JSON.stringify(afterMount);
        throw error;
      }
      assert.equal(applied.owner, 'azhou.codex-startup-animation');
      assert.equal(applied.styleCount, 1);
      assert.equal(applied.styleOwner, 'azhou.codex-startup-animation');

      const skipped = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const button=frame?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();
        return true;
      })()`);
      assert.equal(skipped, true, 'the real generated animation exposes its skip control');
      const complete = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completed&&state.wallpaper.applied
          &&document.querySelectorAll('iframe[aria-label]').length===0
          ?{phase:state.phase,completion:state.completion,wallpaper:state.wallpaper}:false;
      })()`), 5000, 'animation completion with the static wallpaper still applied');
      assert.equal(complete.phase, 'complete');
      assert.deepEqual(complete.completion, { cause: 'skip', beforeReady: false });
      const shot = await screenshot('wallpaper-late-shell-after-complete.png');
      const entry = await appearanceEntryMetrics();
      assert.equal(entry.display, 'block');
      assert.equal(entry.entryHit, true);
      assert.equal(entry.buttonHit, true);
      assert.equal(entry.composerOverlap.area, 0);
      const opened = await clickAppearanceEntry();
      assert.equal(opened.focused, true);
      const settings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
        return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
      })()`), 15000, 'generated payload appearance button opens settings after animation completion');
      await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        frame.contentWindow.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true}));
      })()`);
      const canceledSettings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const button=entry?.shadowRoot?.querySelector('button');
        return state.phase==='complete'&&state.completion?.cause==='settings-cancel'
          &&document.activeElement===entry&&entry.shadowRoot.activeElement===button?state:false;
      })()`), 5000, 'generated payload settings cancellation restores the appearance button focus');
      return { waiting, shellMounted: true, applied, complete, screenshot: shot,
        entry: { rect: entry.rect, buttonText: entry.buttonText, composerOverlap: entry.composerOverlap },
        settings: { runId: settings.runId, phase: settings.phase }, canceledSettings: canceledSettings.completion };
    });
    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('disposing during a generated wallpaper shell wait cleans its observer and rejects a late shell', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied?state:false;
      })()`), 15000, 'generated animation ready before wallpaper shell wait disposal');
      await until(() => cdp.evaluate('window.__fixtureMutationObserverStats().wallpaperShellWait.active>0'), 2000,
        'temporary wallpaper shell observer');
      const before = await cdp.evaluate(`({state:window.__startupAPI.status(),
        observers:window.__fixtureMutationObserverStats(),styleCount:document.querySelectorAll('#azhou-wallpaper-style').length})`);
      assert.equal(before.state.phase, 'playing');
      assert.equal(before.state.wallpaper.applied, false);
      assert.equal(before.styleCount, 0);

      const disposed = await cdp.evaluate(`(()=>{
        const api=window.__startupAPI;
        api.dispose();
        return api.status();
      })()`);
      assert.equal(disposed.phase, 'disposed');
      const cleaned = await until(() => cdp.evaluate(`(()=>{
        const observers=window.__fixtureMutationObserverStats();
        return observers.active===0&&observers.disconnectCalls>0?observers:false;
      })()`), 2000, 'wallpaper observer cleanup after controller disposal');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      await delay(250);
      const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
        wallpaperOwner:window.__azhouWallpaper?.owner||null,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
        observers:window.__fixtureMutationObserverStats()})`);
      assert.equal(after.state.phase, 'disposed');
      assert.equal(after.state.wallpaper.applied, false);
      assert.equal(after.wallpaperOwner, null);
      assert.equal(after.styleCount, 0);
      assert.equal(after.rootAttribute, null);
      assert.equal(after.observers.active, 0);
      return { ready: { phase: ready.phase, runId: ready.runId }, before, disposed,
        cleaned, shellMountedAfterDispose: true, after };
    });

    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('skipping a generated animation during wallpaper wait rejects a shell mounted afterward', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied?state:false;
      })()`), 15000, 'generated animation ready before skip during wallpaper wait');
      await until(() => cdp.evaluate('window.__fixtureMutationObserverStats().wallpaperShellWait.active>0'), 2000,
        'temporary wallpaper observer before skip');
      const skipped = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const button=frame?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();
        return true;
      })()`);
      assert.equal(skipped, true);
      const completed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='skip'?state:false;
      })()`), 3000, 'play run completes while the wallpaper observer is pending');
      const cleaned = await until(() => cdp.evaluate(`(()=>{
        const observers=window.__fixtureMutationObserverStats();
        return observers.wallpaperShellWait.active===0&&observers.wallpaperShellWait.disconnectCalls>0?observers:false;
      })()`), 2000, 'wallpaper observer cleanup after skip');
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      await delay(250);
      const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
        wallpaperOwner:window.__azhouWallpaper?.owner||null,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        rootAttribute:document.documentElement.getAttribute('data-azhou-wallpaper'),
        observers:window.__fixtureMutationObserverStats()})`);
      assert.equal(completed.phase, 'complete');
      assert.equal(after.state.wallpaper.applied, false);
      assert.equal(after.wallpaperOwner, null);
      assert.equal(after.styleCount, 0);
      assert.equal(after.rootAttribute, null);
      assert.equal(after.observers.wallpaperShellWait.active, 0);
      assert.equal(after.observers.appearanceAttributesOnly.active, 1,
        'the controller keeps its root-appearance observer while its completed entry remains available');
      const disposed = await cdp.evaluate(`(()=>{
        const api=window.__startupAPI;
        api.dispose();
        return {state:api.status(),observers:window.__fixtureMutationObserverStats()};
      })()`);
      assert.equal(disposed.state.phase, 'disposed');
      assert.equal(disposed.observers.active, 0,
        'final controller disposal disconnects the root-appearance observer');
      return { ready: { phase: ready.phase, runId: ready.runId }, completed, cleaned,
        shellMountedAfterSkip: true, after, disposed };
    });

    await navigate('/fixture.html?generated-payload=1&hold-shell=1');
    await check('generated wallpaper shell wait is bounded and leaves no observer when the shell stays unsupported', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready&&!state.wallpaper.applied?state:false;
      })()`), 15000, 'generated animation ready before wallpaper wait timeout');
      const pending = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),observers=window.__fixtureMutationObserverStats();
        return observers.wallpaperShellWait.active>0?{state,observers}:false;
      })()`), 2000, 'bounded wallpaper observer is active');
      assert.equal(pending.state.wallpaper.reason, '');
      const started = Date.now();
      const timedOut = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.wallpaper.reason==='wallpaper-unsupported'?state:false;
      })()`), 65000, 'wallpaper unsupported after bounded shell wait');
      const elapsedMs = Date.now() - started;
      assert.ok(elapsedMs >= 58000 && elapsedMs <= 65000,
        'the wallpaper request remains pending for the bounded shell wait before returning unsupported');
      assert.equal(timedOut.wallpaper.failureCode, 'shell-timeout');
      assert.equal(timedOut.wallpaper.failureStage, 'shell');
      const after = await cdp.evaluate(`({state:window.__startupAPI.status(),
        observers:window.__fixtureMutationObserverStats(),shellCount:document.querySelectorAll('[data-app-shell-frame]').length,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        wallpaperOwner:window.__azhouWallpaper?.owner||null})`);
      assert.equal(timedOut.phase, 'complete');
      assert.equal(after.state.wallpaper.applied, false);
      assert.equal(after.observers.wallpaperShellWait.active, 0);
      assert.ok(after.observers.wallpaperShellWait.disconnectCalls > 0);
      assert.equal(after.observers.appearanceAttributesOnly.active, 1,
        'the controller keeps its root-appearance observer after the bounded shell wait ends');
      assert.equal(after.shellCount, 0);
      assert.equal(after.styleCount, 0);
      assert.equal(after.wallpaperOwner, null);
      assert.equal(await cdp.evaluate('window.__releaseShell()'), true);
      await delay(250);
      const late = await cdp.evaluate(`({state:window.__startupAPI.status(),
        observers:window.__fixtureMutationObserverStats(),
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        wallpaperOwner:window.__azhouWallpaper?.owner||null})`);
      assert.equal(late.state.wallpaper.applied, false);
      assert.equal(late.observers.wallpaperShellWait.active, 0);
      assert.equal(late.styleCount, 0);
      assert.equal(late.wallpaperOwner, null);
      const completed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'?state:false;
      })()`), 5000, 'failed wallpaper run completes before explicit recovery');
      assert.deepEqual(await evaluateNativeHelper('retrySource', { startup: 'unknown' }),
        { state: 'owner-conflict', applied: false });
      assert.deepEqual(await evaluateNativeHelper('retrySource', { startup: 'none' }),
        { state: 'retry-unavailable', applied: false });
      const nativeBefore = await evaluateNativeHelper('statusSource');
      assert.equal(nativeBefore.failureCode, 'shell-timeout');
      const recovered = await evaluateNativeHelper('retrySource');
      assert.equal(recovered.retried, true);
      assert.equal(recovered.wallpaper.applied, true);
      assert.equal(recovered.previousFailure.failureCode, 'shell-timeout');
      const repeated = await evaluateNativeHelper('retrySource');
      assert.equal(repeated.retried, false, 'a healthy wallpaper is not applied twice');
      assert.equal(repeated.wallpaper.applied, true);
      const recoveredState = await cdp.evaluate(`({state:window.__startupAPI.status(),
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
        frameCount:document.querySelectorAll('iframe[aria-label]').length,
        image:window.__azhouWallpaper.status().imageSHA256})`);
      assert.equal(recoveredState.state.runId, completed.runId, 'recovery keeps the original controller run');
      assert.equal(recoveredState.frameCount, 0, 'recovery does not replay the startup animation');
      assert.equal(recoveredState.styleCount, 1, 'repeated recovery owns exactly one wallpaper layer');
      const disposed = await cdp.evaluate(`(()=>{
        const api=window.__startupAPI;
        api.dispose();
        return {state:api.status(),observers:window.__fixtureMutationObserverStats()};
      })()`);
      assert.equal(disposed.state.phase, 'disposed');
      assert.equal(disposed.observers.active, 0,
        'final controller disposal disconnects the root-appearance observer');
      return { ready: { runId: ready.runId, phase: ready.phase }, pending, elapsedMs, timedOut, after, late,
        recovered, repeated, recoveredState, disposed };
    });
    await navigate('/fixture.html?generated-payload=1');
    await check('builder-generated startup payload saves settings and applies wallpaper without replay', async () => {
      const initial = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return window.__startupInstallResult?.installed===true&&state?.phase==='playing'&&state.ready?state:false;
      })()`), 15000, 'builder-generated controller and animation ready');
      assert.equal(await cdp.evaluate('document.querySelectorAll(\'iframe[aria-label]\').length'), 1);
      const wallpaper = await until(() => cdp.evaluate(`(()=>{
        const controller=window.__startupAPI.status().wallpaper;
        const api=window.__azhouWallpaper?.status?.();
        const style=document.querySelector('#azhou-wallpaper-style');
        return controller.applied&&controller.imageDecoded&&api?.applied&&api.imageDecoded&&style
          ?{controller,api,owner:window.__azhouWallpaper.owner,version:window.__azhouWallpaper.version,
            styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,styleOwner:style.getAttribute('data-azhou-owner')}
          :false;
      })()`), 10000, 'builder-generated wallpaper applied and decoded in the app route realm');
      assert.equal(wallpaper.controller.applied, true);
      assert.equal(wallpaper.controller.imageDecoded, true);
      assert.equal(wallpaper.api.applied, true);
      assert.equal(wallpaper.api.imageDecoded, true);
      assert.equal(wallpaper.owner, 'azhou.codex-startup-animation');
      assert.equal(wallpaper.version, '0.9.0');
      assert.equal(wallpaper.styleCount, 1);
      assert.equal(wallpaper.styleOwner, 'azhou.codex-startup-animation');
      await cdp.evaluate('window.__ticket05InitialWallpaperAPI=window.__azhouWallpaper;true');
      const firstRun = initial.runId;
      assert.equal(await cdp.evaluate('window.__fixtureHost.__azhouStartup.openSettings()'), true);
      await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        return window.__startupAPI.status().phase==='settings'&&frame?.contentDocument.querySelector('dialog')?.open===true;
      })()`), 5000, 'generated payload settings panel');
      const themePage = await cdp.evaluate(`(()=>{
        const doc=document.querySelector('iframe[aria-label]').contentDocument;
        const value=key=>doc.querySelector('[data-agent-skin-setting-value="'+key+'"]').textContent;
        return {appName:value('appName'),botName:value('botName'),version:value('version'),
          source:value('source'),sections:doc.querySelectorAll('[data-agent-skin-settings-section]').length,
          runningVersion:doc.querySelector('header [data-agent-skin-running-version]')?.textContent};
      })()`);
      // The settings About row reads the build-owned identity from
      // theme-config.json. Since main 21021a5 ("distinguish the Codex launcher")
      // that identity is deliberately "阿舟 AI 实验室 for Codex" (matching
      // CFBundleDisplayName), and 21021a5 updated the builder-level expectations
      // (tools/test-startup-build.py) to the same value. This browser-matrix
      // expectation predates that change and was never re-run (the matrix is not
      // part of scripts/verify.py), so it is aligned here rather than reverting
      // the launcher distinction.
      assert.equal(themePage.appName, '阿舟 AI 实验室 for Codex');
      assert.equal(themePage.botName, '阿舟');
      assert.equal(themePage.version, `${packageMetadata.runtime_version} · ${packageMetadata.runtime_build}`);
      assert.equal(themePage.runningVersion,
        `当前运行：${packageMetadata.runtime_version} · build ${packageMetadata.runtime_build}`);
      assert.equal(themePage.sections, 3);
      assert.equal(themePage.source, '默认设置');
      const draft = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),doc=frame.contentDocument;
        const title=doc.querySelector('input[maxlength="16"]');
        title.value='生成载荷保存验证';title.dispatchEvent(new Event('input',{bubbles:true}));
        const button=doc.querySelector('[data-agent-skin-settings] footer button:last-child');
        if(!button)throw new Error('generated payload settings save control is missing');
        button.click();
        return {title:title.value,button:button.textContent.trim()};
      })()`);
      assert.equal(draft.title, '生成载荷保存验证');
      assert.equal(draft.button, '保存', 'the current settings action saves and closes without replay wording');
      const saved = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='settings-save'&&state.runId===${firstRun}
          &&document.querySelectorAll('iframe[aria-label]').length===0
          ?{state,frameCount:document.querySelectorAll('iframe[aria-label]').length}:false;
      })()`), 15000, 'generated payload settings save closes the existing run without replay');
      assert.equal(saved.frameCount, 0, 'generated payload save closes its animation frame without replay');
      const appliedWallpaper = await until(() => cdp.evaluate(`(()=>{
        const startup=window.__startupAPI.status(),api=window.__azhouWallpaper;
        const apiState=api?.status?.(),style=document.querySelector('#azhou-wallpaper-style');
        return startup.runId===${firstRun}&&startup.phase==='complete'
          &&startup.wallpaper.applied&&startup.wallpaper.imageDecoded&&apiState?.applied&&apiState.imageDecoded&&style
          ?{controller:startup.wallpaper,api:apiState,owner:api.owner,version:api.version,
            styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,styleOwner:style.getAttribute('data-azhou-owner')}
          :false;
      })()`), 10000, 'saved settings apply the generated wallpaper in the existing app route');
      assert.equal(appliedWallpaper.controller.applied, true);
      assert.equal(appliedWallpaper.controller.imageDecoded, true);
      assert.equal(appliedWallpaper.api.applied, true);
      assert.equal(appliedWallpaper.api.imageDecoded, true);
      assert.equal(appliedWallpaper.owner, 'azhou.codex-startup-animation');
      assert.equal(appliedWallpaper.version, '0.9.0');
      assert.equal(appliedWallpaper.styleCount, 1);
      assert.equal(appliedWallpaper.styleOwner, 'azhou.codex-startup-animation');
      assert.equal(await cdp.evaluate('delete window.__ticket05InitialWallpaperAPI'), true);
      assert.equal(await cdp.evaluate('window.__fixtureHost.__azhouStartup.openSettings()'), true);
      const persisted = await until(() => cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const title=frame?.contentDocument.querySelector('input[maxlength="16"]');
        const state=window.__startupAPI.status();
        return state.phase==='settings'&&title?{title:title.value,runId:state.runId}:false;
      })()`), 10000, 'saved generated payload settings are loaded into a newly opened settings run');
      assert.equal(persisted.title, '生成载荷保存验证');
      assert.ok(persisted.runId > firstRun, 'only the explicit settings reopen creates a newer run after save');
      const disposed = await cdp.evaluate(`(()=>{
        window.__fixtureHost.__azhouStartup.dispose();
        return {owned:Object.hasOwn(window.__fixtureHost,'__azhouStartup'),
          frames:document.querySelectorAll('iframe[aria-label]').length,
          wallpaper:!!window.__azhouWallpaper,styles:document.querySelectorAll('#azhou-wallpaper-style').length};
      })()`);
      assert.deepEqual(disposed, { owned: false, frames: 0, wallpaper: false, styles: 0 });
      return { firstRun, saved: { runId: saved.state.runId, completion: saved.state.completion,
        frameCount: saved.frameCount }, wallpaper, appliedWallpaper, savedTitle: persisted, disposed };
    });

    await navigate('/csp-style.html?generated-payload=1');
    await check('generated appearance entry stays styled and opens settings under strict style-src self after completion', async () => {
      const ready = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='playing'&&state.ready?state:false;
      })()`), 15000, 'generated animation ready under strict style-src self');
      const skip = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]');
        const button=frame?.contentDocument.querySelector('[data-agent-skin-skip]');
        if(!button)return false;
        button.click();return true;
      })()`);
      assert.equal(skip, true, 'generated animation exposes its skip control under strict CSP');
      const completed = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status();
        return state.phase==='complete'&&state.completion?.cause==='skip'?state:false;
      })()`), 5000, 'generated animation completes under strict style-src self');
      const entry = await until(async () => {
        const value = await appearanceEntryMetrics();
        return value?.display !== 'none' ? value : false;
      }, 5000, 'appearance entry becomes available under strict style-src self');
      const recovery = await cdp.evaluate(`(()=>{
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]');
        const shadow=entry?.shadowRoot;
        const card=shadow?.querySelector('[data-agent-skin-wallpaper-recovery]');
        const style=card&&getComputedStyle(card),rect=card?.getBoundingClientRect();
        const button=shadow?.querySelector('button');
        const close=shadow?.querySelector('[data-agent-skin-wallpaper-close]');
        const closeRect=close?.getBoundingClientRect();
        const center=value=>value&&({x:value.left+value.width/2,y:value.top+value.height/2});
        const cardCenter=center(rect),closeCenter=center(closeRect);
        const cardTarget=cardCenter&&shadow.elementFromPoint?.(cardCenter.x,cardCenter.y);
        const closeTarget=closeCenter&&shadow.elementFromPoint?.(closeCenter.x,closeCenter.y);
        const entryStyle=entry&&getComputedStyle(entry),entryRect=entry?.getBoundingClientRect();
        const rectData=value=>value&&({x:value.x,y:value.y,width:value.width,height:value.height,
          right:value.right,bottom:value.bottom});
        const visible=!!card&&entryStyle?.display!=='none'&&style?.display!=='none'
          &&style?.visibility==='visible'&&Number(style.opacity)>0&&rect?.width>0&&rect?.height>0;
        return {visible,display:style?.display??null,visibility:style?.visibility??null,
          title:card?.querySelector('[data-agent-skin-wallpaper-title]')?.textContent??null,
          reason:card?.querySelector('[data-agent-skin-wallpaper-reason]')?.textContent??null,
          retryText:shadow?.querySelector('[data-agent-skin-wallpaper-retry]')?.textContent??null,
          retryDisabled:shadow?.querySelector('[data-agent-skin-wallpaper-retry]')?.disabled??null,
          closeText:close?.textContent??null,closeDisabled:close?.disabled??null,
          cardHit:!!card&&!!cardTarget&&(cardTarget===card||card.contains(cardTarget)),
          closeHit:!!close&&!!closeTarget&&(closeTarget===close||close.contains(closeTarget)),
          rect:rectData(rect),buttonRect:rectData(button?.getBoundingClientRect()),
          entryLayout:entryStyle&&{display:entryStyle.display,position:entryStyle.position,
            flexDirection:entryStyle.flexDirection,alignItems:entryStyle.alignItems,gap:entryStyle.gap,
            rect:rectData(entryRect)}};
      })()`);
      await screenshot('appearance-entry-csp-style-src-self.png');
      const diagnostic = JSON.stringify({ phase: completed.phase, viewport: entry?.viewport,
        wallpaper: completed.wallpaper, display: entry?.display, position: entry?.position, rect: entry?.rect,
        avatar: entry?.avatar, nameLabel: entry?.nameLabel,
        entryHit: entry?.entryHit, buttonHit: entry?.buttonHit, buttonText: entry?.buttonText, recovery });
      const cspStyleFailure = ['styles-not-effective', 'styles-not-effective-after-replacement']
        .includes(completed.wallpaper?.failureCode);
      assert.equal(entry?.display, recovery.visible ? 'flex' : 'block',
        'appearance entry uses its normal or recovery layout under strict CSP: ' + diagnostic);
      assert.equal(entry.position, 'fixed', 'appearance entry positioning is available under strict CSP: ' + diagnostic);
      assert.ok(entry.rect.width >= 44 && entry.rect.width <= 120,
        'appearance entry stays within compact avatar-and-name geometry under strict CSP: ' + diagnostic);
      assert.ok(entry.rect.x >= 0 && entry.rect.y >= 0
        && entry.rect.x + entry.rect.width <= entry.viewport.width
        && entry.rect.y + entry.rect.height <= entry.viewport.height,
      'appearance button remains fully inside the viewport under strict CSP: ' + diagnostic);
      assert.deepEqual(entry.avatar, { width: 32, height: 32, display: 'block', borderRadius: '10px', objectFit: 'cover' },
        'generated avatar keeps its bounded styled dimensions under strict CSP: ' + diagnostic);
      assert.deepEqual(entry.nameLabel, { text: '阿舟外观', fontSize: '12px', lineHeight: '18px' },
        'generated avatar name remains visible with the button typography under strict CSP: ' + diagnostic);
      assert.equal(entry.entryHit, true, 'appearance entry host is hit-testable under strict CSP: ' + diagnostic);
      assert.equal(entry.buttonHit, true, 'shadow button is hit-testable under strict CSP: ' + diagnostic);
      if (cspStyleFailure) {
        assert.equal(completed.wallpaper.applied, false, 'strict CSP leaves the requested wallpaper unapplied: ' + diagnostic);
        assert.equal(completed.wallpaper.failureStage, 'styles', 'strict CSP refusal is classified as a style failure: ' + diagnostic);
        assert.equal(recovery.visible, true, 'strict CSP failure exposes its recovery card: ' + diagnostic);
        assert.equal(recovery.title, '启动背景未应用', 'the recovery card names the failed startup background: ' + diagnostic);
        assert.equal(recovery.reason, '当前页面未能应用背景样式。', 'the recovery card reports the actual CSP style refusal: ' + diagnostic);
        assert.equal(recovery.display, 'block');
        assert.equal(recovery.retryText, '重试');
        assert.equal(recovery.retryDisabled, false);
        assert.equal(recovery.closeText, '关闭提示');
        assert.equal(recovery.closeDisabled, false);
        assert.equal(recovery.cardHit, true, 'the visible recovery card remains hit-testable: ' + diagnostic);
        assert.equal(recovery.closeHit, true, 'the recovery dismissal action remains hit-testable: ' + diagnostic);
        assert.equal(recovery.entryLayout.display, 'flex');
        assert.equal(recovery.entryLayout.flexDirection, 'column-reverse');
        assert.equal(recovery.entryLayout.alignItems, 'flex-start');
        assert.equal(recovery.entryLayout.gap, '8px');
        assert.ok(recovery.rect.x >= 0 && recovery.rect.y >= 0
          && recovery.rect.right <= entry.viewport.width && recovery.rect.bottom <= entry.viewport.height,
        'the recovery card remains fully inside the viewport: ' + diagnostic);
        assert.ok(recovery.rect.bottom <= recovery.buttonRect.y,
          'the recovery card and appearance button keep separate hit areas: ' + diagnostic);
      } else {
        assert.equal(recovery.visible, false, 'no recovery card is shown without a wallpaper failure: ' + diagnostic);
      }
      const opened = await clickAppearanceEntry();
      assert.equal(opened.focused, true, 'the generated appearance button receives a real pointer click');
      const settings = await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
        return state.phase==='settings'&&state.ready&&frame?.contentDocument.querySelector('dialog')?.open?state:false;
      })()`), 15000, 'generated appearance entry opens settings under strict style-src self');
      await dispatchTab(false);
      const focus = await cdp.evaluate(`(()=>{
        const frame=document.querySelector('iframe[aria-label]'),element=frame?.contentDocument?.activeElement;
        const style=element&&frame.contentWindow.getComputedStyle(element);
        return {visible:!!element?.matches(':focus-visible'),style:style?.outlineStyle,width:style?.outlineWidth};
      })()`);
      assert.ok(focus.visible && focus.style !== 'none' && parseFloat(focus.width) >= 3,
        'settings keyboard focus stays visible under strict host CSP: '+JSON.stringify(focus));
      await screenshot('appearance-settings-csp-style-src-self.png');
      return { ready: { runId: ready.runId, phase: ready.phase }, completed: completed.completion,
        wallpaper: completed.wallpaper, entry, recovery,
        settings: { runId: settings.runId, phase: settings.phase }, pointerFocused: opened.focused };
    });
  }

  await navigate('/fixture.html');
  await check('real appearance observer preserves a host surface edit through wallpaper disposal', async () => {
    const ready = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI?.status();
      return state?.phase==='playing'&&state.ready&&state.wallpaper?.applied?state:false;
    })()`), 15000, 'real controller wallpaper before host surface edit');
    const writtenSurface = await cdp.evaluate(`({value:document.documentElement.style.getPropertyValue('--azhou-wallpaper-surface'),
      priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-surface')})`);
    assert.deepEqual(writtenSurface, { value: '#10121c', priority: '' });

    await cdp.evaluate("document.documentElement.style.setProperty('--azhou-wallpaper-surface','rgb(100, 110, 120)','important')");
    await delay(50);
    const afterObserver = await cdp.evaluate(`({value:document.documentElement.style.getPropertyValue('--azhou-wallpaper-surface'),
      priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-surface')})`);
    assert.deepEqual(afterObserver, { value: 'rgb(100, 110, 120)', priority: 'important' },
      'the observer must leave a host-owned value and priority in place');

    await cdp.evaluate('window.__startupAPI.dispose()');
    const afterDispose = await cdp.evaluate(`({wallpaper:!!window.__azhouWallpaper,styleCount:document.querySelectorAll('#azhou-wallpaper-style').length,
      value:document.documentElement.style.getPropertyValue('--azhou-wallpaper-surface'),
      priority:document.documentElement.style.getPropertyPriority('--azhou-wallpaper-surface')})`);
    assert.deepEqual(afterDispose, { wallpaper: false, styleCount: 0,
      value: 'rgb(100, 110, 120)', priority: 'important' });
    return { runId: ready.runId, writtenSurface, afterObserver, afterDispose };
  });

  await check('native retry transport permits slow success and bounded controller timeout receipts', async () => {
    await navigate('/fixture.html');
    const samples = [];
    for (const [mode, expectedState, minimum] of [
      ['success', 'fixture-complete', 6500], ['timeout', 'retry-timeout', 9500],
    ]) {
      const started = Date.now();
      const { stdout } = await promisify(execFile)(join(ROOT, '.build/startup-native-tests'),
        ['--wallpaper-transport-fixture', page.webSocketDebuggerUrl, mode], { timeout: 15000 });
      const value = JSON.parse(stdout);
      const elapsedMs = Date.now() - started;
      assert.equal(value.state, expectedState);
      assert.ok(elapsedMs >= minimum && elapsedMs < 13000, 'native transport preserves the bounded slow result');
      samples.push({ mode, elapsedMs, value });
    }
    return samples;
  });

  await check('settings dialog remains usable by keyboard across constrained viewports', async () => {
    const scenarios = [
      { name: 'desktop-dark-zh', width: 1440, height: 900, locale: 'zh-CN', theme: 'dark', tab: 'workspace' },
      { name: 'desktop-light-en', width: 1440, height: 900, locale: 'en', theme: 'light', tab: 'startup' },
      { name: 'narrow-dark-en', width: 320, height: 568, locale: 'en', theme: 'dark', tab: 'startup' },
      { name: 'short-light-en', width: 640, height: 360, locale: 'en', theme: 'light', tab: 'workspace' },
      { name: 'small-dark-zh', width: 320, height: 360, locale: 'zh-CN', theme: 'dark', tab: 'startup' },
      { name: 'about-light-en', width: 640, height: 600, locale: 'en', theme: 'light', tab: 'about' },
    ];
    const results = [];
    const issues = [];
    try {
      await navigate('/fixture.html?animation=1&no-initial-wallpaper=1&entry-avatar=1');
      await until(() => cdp.evaluate("window.__startupAPI?.status().phase === 'playing' && window.__startupAPI.status().ready"),
        15000, 'settings design fixture ready');
      assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
      await until(() => cdp.evaluate(`(()=>{
        const state=window.__startupAPI?.status();
        return state?.phase==='settings'&&state.ready&&document.querySelector('iframe[aria-label]')?.contentDocument
          ?.querySelector('[data-agent-skin-settings]');
      })()`), 15000, 'settings dialog ready');

      for (const scenario of scenarios) {
        await cdp.call('Emulation.setDeviceMetricsOverride', {
          width: scenario.width, height: scenario.height, deviceScaleFactor: 1, mobile: false,
        });
        await cdp.evaluate(`(()=>{
          const scenario=${JSON.stringify(scenario)},root=document.documentElement;
          root.lang=scenario.locale;root.dataset.theme=scenario.theme;
          const colors=scenario.theme==='light'
            ? ['#f8fafc','#172033','#536176','#cbd5e1']
            : ['#10121c','#fff8ef','#b8b4c4','#595366'];
          ['--color-surface','--color-text-primary','--color-text-secondary','--color-border']
            .forEach((key,index)=>root.style.setProperty(key,colors[index]));
        })()`);
        await until(() => cdp.evaluate(`(()=>{
          const doc=document.querySelector('iframe[aria-label]')?.contentDocument;
          return doc?.documentElement.lang===${JSON.stringify(scenario.locale)}
            &&doc.documentElement.dataset.theme===${JSON.stringify(scenario.theme)};
        })()`), 5000, 'settings locale and theme update');

        const metrics = await cdp.evaluate(`(()=>{
          const scenario=${JSON.stringify(scenario)};
          const frame=document.querySelector('iframe[aria-label]'),doc=frame.contentDocument,win=frame.contentWindow;
          const dialog=doc.querySelector('[data-agent-skin-settings]');
          const selectedTab=dialog.querySelector('[data-agent-skin-settings-tab="'+scenario.tab+'"]');
          if(!selectedTab)throw new Error('missing settings tab: '+scenario.tab);
          selectedTab.click();
          const textFields=[...dialog.querySelectorAll('input[type="text"],textarea')];
          const values=['阿舟的 Agent 实验室','Azhou / Intelligent Agents & Creative Workflows',
            '和阿舟一起，把真实工作里的复杂想法变成可以检查、可以复用、可以交付的结果。'];
          textFields.forEach(field=>{
            const value=field.matches('[data-agent-skin-preset-name]')?'本机外观预设名称':
              field.maxLength===16?values[0]:field.maxLength===48?values[1]:values[2];
            const limit=field.maxLength>0?field.maxLength:value.length;
            field.value=value.slice(0,limit);
            field.dispatchEvent(new win.Event('input',{bubbles:true}));
          });
          const strength=dialog.querySelector('input[type="range"]');
          if(strength){strength.value='42';strength.dispatchEvent(new win.Event('input',{bubbles:true}));}
          const panel=dialog.querySelector('[role="tabpanel"]:not([hidden])');
          const footer=dialog.querySelector('footer');
          if(!panel||!footer)throw new Error('settings layout is missing a measured region');
          const rect=element=>{const r=element.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
          dialog.scrollTop=0;
          const footerBefore=rect(footer),dialogBox=rect(dialog);
          dialog.scrollTop=dialog.scrollHeight;
          const footerAfter=rect(footer);
          const overflow=dialog.scrollWidth>dialog.clientWidth+1
            ||doc.documentElement.scrollWidth>win.innerWidth+1||doc.body.scrollWidth>win.innerWidth+1;
          const result={viewport:{width:win.innerWidth,height:win.innerHeight},dialog:dialogBox,
            scroller:{clientHeight:dialog.clientHeight,scrollHeight:dialog.scrollHeight},overflow,
            footerStable:Math.abs(footerBefore.top-footerAfter.top)<1};
          dialog.scrollTop=0;
          selectedTab.focus();
          return result;
        })()`);
        const scenarioIssues=[];
        const keyboard=[];
        if(metrics.overflow)scenarioIssues.push('horizontal overflow');
        if(metrics.dialog.left<0||metrics.dialog.right>scenario.width+1
          ||metrics.dialog.top<0||metrics.dialog.bottom>scenario.height+1)scenarioIssues.push('dialog outside viewport');
        if(!metrics.footerStable)scenarioIssues.push('footer scrolls away');
        if(metrics.scroller.clientHeight<48)scenarioIssues.push('content scroller has no usable space');
        for(let step=0;step<8;step++){
          await dispatchTab();
          if(await cdp.evaluate(`document.querySelector('iframe[aria-label]').contentDocument.activeElement?.matches('section[role="tabpanel"]')`))
            await screenshot('settings-section-focus-'+scenario.name+'-'+step+'.png');
          const focus=await cdp.evaluate(`(()=>{
            const frame=document.querySelector('iframe[aria-label]'),doc=frame.contentDocument;
            const dialog=doc.querySelector('[data-agent-skin-settings]'),active=doc.activeElement;
            if(!active||!dialog.contains(active))return {inside:false};
            const box=active.getBoundingClientRect(),style=frame.contentWindow.getComputedStyle(active);
            const footer=dialog.querySelector('footer'),footerBox=footer?.getBoundingClientRect();
            const dialogBox=dialog.getBoundingClientRect();
            const fitsAboveFooter=box.height<=footerBox.top-dialogBox.top+0.5;
            const evaluateHit=${settingsFocusHitEvidence.toString()};
            const hitEvidence=evaluateHit(active,dialog,footer,doc,frame.contentWindow);
            let negativeControls=null;
            if(active.matches('section[role="tabpanel"][data-agent-skin-settings-section="workspace"]')&&frame.contentWindow.innerHeight===360) {
              const scrollBefore=dialog.scrollTop;
              const input=active.querySelector('#agent-skin-settings-wallpaper-strength');
              const inputBaseline=evaluateHit(input,dialog,footer,doc,frame.contentWindow);
              const inputVisible=!!input.getClientRects().length&&input.getBoundingClientRect().width>0&&input.getBoundingClientRect().height>0;
              const cover=doc.createElement('div');cover.style.cssText='position:fixed;inset:0;z-index:2147483647;background:black';dialog.appendChild(cover);
              const covered=evaluateHit(active,dialog,footer,doc,frame.contentWindow);cover.remove();
              active.hidden=true;const hidden=evaluateHit(active,dialog,footer,doc,frame.contentWindow);active.hidden=false;
              const inputStyle=input.style.cssText,footerStyle=footer.style.cssText;
              let footerCovered;
              try {
                const f=footer.getBoundingClientRect();footer.style.zIndex='1';
                input.style.cssText='position:fixed;left:'+ (f.left+16)+'px;top:'+(f.top+8)+'px;width:60px;height:20px;z-index:0';
                footerCovered=evaluateHit(input,dialog,footer,doc,frame.contentWindow);
              } finally {input.style.cssText=inputStyle;footer.style.cssText=footerStyle;}
              active.focus({preventScroll:true});dialog.scrollTop=scrollBefore;
              negativeControls={covered,hidden,inputBaseline,inputVisible,footerCovered,focusRestored:doc.activeElement===active,restored:evaluateHit(active,dialog,footer,doc,frame.contentWindow)};
            }
            return {inside:true,tag:active.tagName,label:active.id||active.getAttribute('aria-label')||active.textContent?.trim()||active.type,
              hit:hitEvidence.hit,hitEvidence,negativeControls,visible:box.width>0&&box.height>0
              &&box.bottom>0&&box.top<frame.contentWindow.innerHeight,
              clearFooter:!footerBox||footer.contains(active)||!fitsAboveFooter||box.bottom<=footerBox.top+0.5,
              focusVisible:active.matches(':focus-visible'),outlineStyle:style.outlineStyle,
              outlineWidth:parseFloat(style.outlineWidth),outlineColor:style.outlineColor};
          })()`);
          if(focus.negativeControls) {
            const n=focus.negativeControls;
            await writeFile(join(options.out,'focus-controls-'+scenario.name+'-'+step+'.json'),JSON.stringify(n,null,2));
            assert.equal(n.covered.hit,false,'visible tabpanel fully covered must be rejected');
            assert.equal(n.hidden.hit,false,'hidden tabpanel must be rejected');
            assert.equal(n.inputVisible,true,'public strength range is visible before fault injection');
            assert.equal(n.inputBaseline.hit,true,'public strength range is hit before fault injection');
            assert.equal(n.footerCovered.hit,false,'a real input hidden by the footer must be rejected');
            assert.equal(n.footerCovered.footerTarget,true,'negative control actually hits the footer');
            assert.equal(n.restored.hit,true,'removing faults restores the visible tabpanel');
            assert.equal(n.focusRestored,true,'fault injection restores the original active element');
          }
          keyboard.push(focus);
          if(!focus.inside||!focus.visible||!focus.hit)scenarioIssues.push('keyboard focus is outside or obscured in settings: '+JSON.stringify(focus));
          if(focus.inside&&!focus.clearFooter)scenarioIssues.push('keyboard focus is clipped by the settings footer: '+JSON.stringify(focus));
          if(focus.inside&&(!focus.focusVisible||focus.outlineStyle==='none'||focus.outlineWidth<1.9||focus.outlineColor==='transparent'))
            scenarioIssues.push('keyboard focus indicator missing: '+JSON.stringify(focus));
        }
        if(new Set(keyboard.map(focus=>focus.label)).size<3)scenarioIssues.push('Tab did not traverse at least three distinct controls');
        results.push({scenario,metrics,keyboard,issues:scenarioIssues});
        issues.push(...scenarioIssues.map(issue=>scenario.name+': '+issue));
        await screenshot('settings-design-'+scenario.name+'.png');
      }
      await writeFile(join(options.out,'settings-design-matrix.json'),JSON.stringify({
        scope:'Current source in an isolated synthetic host; keyboard focus is tested through Tab traversal. Actual browser zoom and installed-host behavior are not tested.',
        results,issues,
      },null,2)+'\n');
      assert.deepEqual(issues,[],issues.join('\n'));
      return {scenarios:results.length,checks:results.map(result=>({name:result.scenario.name,issues:result.issues})),
        focusMethod:'keyboard Tab traversal; actual browser zoom not tested'};
    } finally {
      await cdp.evaluate('window.__startupAPI?.dispose()');
      await cdp.call('Emulation.setDeviceMetricsOverride',{width:1512,height:889,deviceScaleFactor:1,mobile:false});
      await cdp.call('Emulation.setEmulatedMedia',{features:[]});
    }
  });


  for (const delayedShell of [false, true]) {
    await check('ready playback timeout restores Appearance ' + (delayedShell ? 'after a delayed shell' : 'in the current navigation'), async () => {
      // Settings saved by earlier checks override no-initial-wallpaper and can
      // surface the wallpaper recovery notice after cancel; start from a clear
      // settings database so the asserted entry display stays deterministic.
      await navigateFreshRecoveryFixture('/fixture.html?animation=1&home-nav-fixture=1&entry-avatar=1&no-initial-wallpaper=1&manual-startup-timeout=1'
        + (delayedShell ? '&hold-shell=1' : ''));
      await until(() => cdp.evaluate('window.__startupAPI?.status().phase === "playing" && window.__startupAPI.status().ready'),
        15000, 'actual animation ready before its playback watchdog');
      const expired = await cdp.evaluate(`(() => {
        const state = __startupAPI.status();
        if (state.phase !== 'playing' || !state.ready) throw new Error('fixture did not reach ready playback');
        __startupAnimationRuns.at(-1).handle.preview.pause();
        window.__fixtureTimeoutEntry = document.querySelector('[data-agent-skin-entry="appearance"]');
        window.__fixtureTimeoutRunID = state.runId;
        const watchdog = __fixtureStartupWatchdog;
        watchdog.fire();
        const after = __startupAPI.status();
        return {milliseconds:watchdog.milliseconds,
          state:{phase:after.phase,reason:after.reason,ready:after.ready,completed:after.completed,
            overlay:after.overlay,completion:after.completion},
          frames:document.querySelectorAll('iframe[aria-label]').length};
      })()`);
      assert.equal(expired.milliseconds, 25_000);
      assert.deepEqual(expired.state, {phase:'timeout',reason:'overlay-timeout',ready:true,
        completed:false,overlay:false,completion:null});
      assert.equal(expired.frames, 0);
      if (delayedShell) {
        assert.equal(await cdp.evaluate('getComputedStyle(__fixtureTimeoutEntry).display'), 'none',
          'an enabled recovery entry still waits for a usable host layout');
        assert.equal(await cdp.evaluate('__releaseShell()'), true);
      }
      const entry = await until(() => cdp.evaluate(`(() => {
        const entries = document.querySelectorAll('[data-agent-skin-entry="appearance"]');
        const node = entries[0], button = node?.shadowRoot?.querySelector('button');
        const bounds = button?.getBoundingClientRect();
        if (!bounds || bounds.width <= 0 || bounds.height <= 0 || getComputedStyle(node).display === 'none') return false;
        const dot = document.querySelector('[data-fixture-your-dot]');
        const nav = document.querySelector('[data-fixture-home-nav]');
        const row = node.getBoundingClientRect(), anchor = dot.getBoundingClientRect(), navigation = nav.getBoundingClientRect();
        const x = bounds.left + bounds.width / 2, y = bounds.top + bounds.height / 2;
        const hit = node.shadowRoot.elementFromPoint(x,y);
        return {count:entries.length,same:node===__fixtureTimeoutEntry,display:getComputedStyle(node).display,
          marginTop:getComputedStyle(node).marginTop,inNavigation:node.parentElement===document.querySelector('[data-fixture-nav-list]'),
          followsAnchor:node.previousElementSibling===dot,belowAnchor:row.top>=anchor.bottom,
          withinNavigation:row.left>=navigation.left&&row.right<=navigation.right,
          hit:document.elementFromPoint(x,y)===node&&(hit===button||button.contains(hit)),
          disabled:button.disabled,x,y,width:bounds.width,height:bounds.height,phase:__startupAPI.status().phase};
      })()`), 2500, 'the same timeout entry occupies a visible, clickable navigation row');
      assert.equal(entry.count, 1);
      assert.equal(entry.same, true);
      assert.equal(entry.display, 'block');
      assert.equal(entry.marginTop, '6px');
      assert.equal(entry.inNavigation, true);
      assert.equal(entry.followsAnchor, true);
      assert.equal(entry.belowAnchor, true);
      assert.equal(entry.withinNavigation, true);
      assert.equal(entry.hit, true);
      assert.equal(entry.disabled, false);
      assert.equal(entry.phase, 'timeout', 'layout recovery never rewrites the timeout receipt');

      await cdp.call('Input.dispatchMouseEvent', {type:'mousePressed',x:entry.x,y:entry.y,button:'left',clickCount:1});
      await cdp.call('Input.dispatchMouseEvent', {type:'mouseReleased',x:entry.x,y:entry.y,button:'left',clickCount:1});
      const settings = await until(() => cdp.evaluate(`(() => {
        const state=__startupAPI.status(),frame=document.querySelector('iframe[aria-label]');
        if(state.phase!=='settings'||!frame?.contentDocument.querySelector('dialog')?.open)return false;
        return {runChanged:state.runId!==__fixtureTimeoutRunID,completed:state.completed,overlay:state.overlay,
          intents:__startupAnimationRuns.map(run=>run.intent),inert:document.getElementById('root').inert};
      })()`), 15000, 'a real entry click opens the existing settings panel');
      assert.deepEqual(settings, {runChanged:true,completed:false,overlay:true,intents:['play','settings'],inert:true});
      await cdp.call('Input.dispatchKeyEvent', {type:'rawKeyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
      await cdp.call('Input.dispatchKeyEvent', {type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
      const closed = await until(() => cdp.evaluate(`(() => {
        const state=__startupAPI.status();
        if(state.phase!=='complete'||state.overlay)return false;
        const entry=document.querySelector('[data-agent-skin-entry="appearance"]'),button=entry.shadowRoot.querySelector('button');
        return {completion:state.completion,frames:document.querySelectorAll('iframe[aria-label]').length,
          inert:document.getElementById('root').inert,display:getComputedStyle(entry).display,
          focus:document.activeElement===entry&&entry.shadowRoot.activeElement===button,
          same:entry===__fixtureTimeoutEntry,intents:__startupAnimationRuns.map(run=>run.intent)};
      })()`), 2500, 'cancel releases the settings frame and restores entry focus');
      assert.deepEqual(closed, {completion:{cause:'settings-cancel',beforeReady:false},frames:0,inert:false,
        display:'block',focus:true,same:true,intents:['play','settings']});
      return {delayedShell,expired,entry,settings,closed};
    });
  }

  await check('DSH ordinary wallpaper preserves reversible surface ownership', async()=>{
    await navigate('/fixture.html?legacy-only=1');
    const result=await cdp.evaluate(`(async()=>{
      window.__azhouWallpaper?.dispose();
      document.getElementById('root').innerHTML='<div class="fixture_mainPanel" style="display:flex;flex-direction:column;width:100%;height:100vh"><div data-slot="main" style="display:contents"><main style="display:contents"><div style="flex:1"></div></main></div></div>';
      window.__ModuleLoader__={load(){}};window.__DSH_BOOT__={};
      const {createDSHPageAdapter}=await import('/extension/hosts/dsh.mjs');
      const {createWallpaperApplicator}=await import('/wallpaper/apply.js');
      const {installRenderer}=await import('/wallpaper/renderer.js');
      const adapter=createDSHPageAdapter(window,{sidebarEntry:false});
      const css=await(await fetch('/wallpaper.css')).text();
      const apply=createWallpaperApplicator(installRenderer,{version:'0.9.0',css,pageAdapter:adapter},window);
      const base={image:${JSON.stringify(pixelImage)},strength:42};
      const first=await apply(base,()=>true);if(!first.applied)throw Error(JSON.stringify(first));
      const root=document.documentElement,node=document.querySelector('.fixture_mainPanel');
      const owner=()=>window.__azhouWallpaper;
      const sheet=()=>document.getElementById('azhou-wallpaper-style');
      const wash=()=>root.style.getPropertyValue('--azhou-wallpaper-wash');
      const prior=owner(),priorSheet=sheet(),priorWash=wash();
      const retired=await apply({...base,mainPaint:{profile:'codex-main-literal-paint/v1',rgba:[10,20,30,.4],backgroundImage:'none',sourceDeclarationCount:1}},()=>true,null,{transactional:true});
      const noRetiredMutation=retired.applied===false&&retired.failureCode==='main-paint-unsupported'
        &&owner()===prior&&sheet()===priorSheet&&wash()===priorWash&&!node.hasAttribute('data-azhou-dream-main');
      const changed={...base,strength:67};
      const transaction=()=>apply(changed,()=>true,null,{transactional:true});
      const candidate=await transaction();
      if(!candidate.applied)throw Error(JSON.stringify(candidate));
      const distinguishable=owner()!==prior&&sheet()!==priorSheet&&wash()!==priorWash;
      const changedWash=wash();
      const rollback=candidate.transaction.rollback();
      const same=owner()===prior&&sheet()===priorSheet&&wash()===priorWash;
      const next=await transaction();
      const destination=owner();
      const finalized=next.transaction.finalize();
      const handedOver=destination!==prior&&owner()===destination&&wash()===changedWash;
      const restore=await apply(base,()=>true,null,{transactional:true});
      const restored=restore.transaction.finalize()&&wash()===priorWash;
      const transparent=getComputedStyle(node).backgroundColor;
      const zero=await apply({...base,strength:0},()=>true,null,{transactional:true});
      node.remove();document.getElementById('root').appendChild(node);
      const zeroStale=zero.transaction.current(),zeroFinalized=zero.transaction.finalize();
      window.__azhouWallpaper?.dispose();
      const absent=await apply({...base,strength:0},()=>true,null,{transactional:true});
      node.remove();document.getElementById('root').appendChild(node);
      const absentStale=absent.transaction.current(),absentFinalized=absent.transaction.finalize();
      const disabled=await apply({...base,strength:0},()=>true,null,{transactional:true});
      const disabledFinalized=disabled.transaction.finalize(),disabledRepeated=disabled.transaction.finalize();
      const routeCleanup=[];
      for(const eventName of ['hashchange','popstate']){
        const applied=await transaction();
        if(!applied.transaction.finalize())throw Error('route setup failed');
        window.dispatchEvent(new Event(eventName));
        routeCleanup.push(!window.__azhouWallpaper&&!document.getElementById('azhou-wallpaper-style')&&!node.hasAttribute('data-azhou-dream-main'));
      }
      return {noRetiredMutation,distinguishable,rollback,same,finalized,handedOver,restored,transparent,zeroStale,zeroFinalized,absentStale,absentFinalized,disabledFinalized,disabledRepeated,routeCleanup,marker:node.getAttribute('data-azhou-dream-main')};
    })()`);
    assert.deepEqual(result,{noRetiredMutation:true,distinguishable:true,rollback:true,same:true,finalized:true,handedOver:true,restored:true,transparent:'rgba(0, 0, 0, 0)',zeroStale:false,zeroFinalized:false,absentStale:false,absentFinalized:false,disabledFinalized:true,disabledRepeated:true,routeCleanup:[true,true],marker:null});
    return result;
  });

  await check('detached startup overlay invalidates playback readiness', async () => {
    await navigate('/fixture.html?animation=1');
    await awaitGeneratedReady('actual animation playing');
    const after = await cdp.evaluate(`(() => {
      document.body.replaceChildren();
      return window.__startupAPI.status();
    })()`);
    assert.equal(after.ready, false);
    assert.equal(after.phase, 'failed');
    assert.equal(after.overlay, false);
    assert.equal(after.reason, 'startup-interrupted');
  });

  async function startLifecycleFixture(kind) {
    await navigate('/fixture.html?legacy-only=1');
    const installed = await cdp.evaluate(`(async kind => {
      const {installStartup} = await import('/extension/renderer.mjs');
      let host = window;
      let adapter;
      if (kind === 'dsh') {
        const {createDSHPageAdapter} = await import('/extension/hosts/dsh.mjs');
        window.__ModuleLoader__ = {load() {}};
        window.__DSH_BOOT__ = {};
        adapter = createDSHPageAdapter(host, {sidebarEntry:false});
      } else {
        const href = 'app://-/index.html?initialRoute=%2F';
        host = new Proxy(window, {get(target, name) {
          if (name === 'top') return host;
          if (name === 'location') return new URL(href);
          const value = Reflect.get(target, name, target);
          return ['addEventListener','removeEventListener','setTimeout','clearTimeout','getComputedStyle','matchMedia'].includes(name)
            ? value.bind(target) : value;
        }});
        const {createCodexPageAdapter} = await import('/extension/codex-page-adapter.mjs');
        adapter = createCodexPageAdapter(host);
      }
      const evidence = window.lifecycleFixture = {disposed:0,closed:0,embedPresentations:[]};
      const payload = (_win, _doc, _location, _performance, _indexedDB, _Image, _Path2D, _URL,
        _raf, _cancelRaf, _setTimeout, _clearTimeout, _module, send, spec) => {
        const emit = (action, fields={}) => send({type:'azhou-startup', action, runId:spec.runId, ...fields});
        if (spec.intent === 'settings') evidence.embedPresentations.push(spec.presentation ?? null);
        if (spec.intent === 'play') {
          evidence.ready = () => emit('ready');
          evidence.complete = () => emit('complete', {skipped:false});
        } else queueMicrotask(() => emit('ready'));
        return {openSettings() { emit('settings-open'); return true; },
          dispose() { if (spec.intent === 'settings') evidence.disposed++; }};
      };
      return installStartup(payload, host, adapter);
    })(${JSON.stringify(kind)})`);
    assert.equal(installed.installed, true, kind + ' fixture installed');
    const state = await cdp.evaluate('window.__azhouStartup.status()');
    assert.equal(state.owner, 'azhou-' + kind + '-startup');
    assert.equal(state.phase, 'loading');
  }

  for (const kind of ['codex', 'dsh']) {
    await check(kind + ' startup and settings lifecycle contract', async () => {
      await startLifecycleFixture(kind);
      const completed = await cdp.evaluate(`(() => {
        lifecycleFixture.ready();
        lifecycleFixture.complete();
        return __azhouStartup.status();
      })()`);
      assert.equal(completed.phase, 'complete');
      assert.equal(completed.ready, true);
      assert.equal(completed.overlay, false);
      for (const ready of [false, true]) {
        await startLifecycleFixture(kind);
        if (ready) await cdp.evaluate('lifecycleFixture.ready()');
        const state = await cdp.evaluate(`(() => {
          document.body.replaceChildren();
          const {phase,ready,overlay,reason} = __azhouStartup.status();
          return {phase,ready,overlay,reason};
        })()`);
        assert.deepEqual(state, {phase:'failed',ready:false,overlay:false,reason:'startup-interrupted'},
          ready ? 'overlay lost after ready' : 'overlay lost before ready');
      }
      await startLifecycleFixture(kind);
      await cdp.evaluate('lifecycleFixture.ready()');
      assert.equal(await cdp.evaluate('__azhouStartup.openSettings()'), true);
      assert.equal(await cdp.evaluate('document.querySelector("#root").inert'), true);
      await cdp.evaluate('document.querySelector("iframe[aria-label]").remove()');
      await until(() => cdp.evaluate('document.querySelector("#root").inert === false'),
        1000, 'host unlocked without a status request');
      assert.equal(await cdp.evaluate('__azhouStartup.status().reason'), 'startup-interrupted');
    });
  }

  await check('DSH settings panel releases its resources when its iframe is removed', async () => {
    await startLifecycleFixture('dsh');
    const mounted = await cdp.evaluate(`(() => {
      lifecycleFixture.ready();
      const target = document.body.appendChild(document.createElement('div'));
      lifecycleFixture.dispose = __azhouStartup.mountSettings(target, {onClose:()=>lifecycleFixture.closed++});
      if (typeof lifecycleFixture.dispose !== 'function' || target.querySelectorAll('iframe').length !== 1) return false;
      target.querySelector('iframe').remove();
      return true;
    })()`);
    assert.equal(mounted, true, 'DSH controller mounted one embedded settings frame');
    assert.deepEqual(await cdp.evaluate('lifecycleFixture.embedPresentations'), ['embedded'],
      'the embed frameSpec declares the non-modal presentation in a real browser');
    await until(() => cdp.evaluate('lifecycleFixture.disposed === 1 && lifecycleFixture.closed === 1'),
      1000, 'detached DSH settings panel released and host notified');
    const state = await cdp.evaluate(`(() => {
      lifecycleFixture.dispose();
      return {disposed:lifecycleFixture.disposed,closed:lifecycleFixture.closed,
        phase:__azhouStartup.status().phase};
    })()`);
    assert.deepEqual(state, {disposed:1,closed:1,phase:'playing'});
  });

  if(options.generatedPayload)await check('generated Appearance exposes Azhou inputs without external theme transfer',async()=>{
    await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1');
    await awaitGeneratedReady('generated Appearance fixture ready');
    await cdp.evaluate(`document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]').click()`);
    await until(()=>cdp.evaluate(`window.__startupAPI.status().phase==='complete'&&window.__azhouWallpaper?.status().applied`),10000,'Azhou wallpaper ready');
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'),true);
    const controls=await until(()=>cdp.evaluate(`(()=>{
      const d=document.querySelector('iframe[aria-label]')?.contentDocument;
      if(!d?.querySelector('[data-agent-skin-settings]')||__startupAPI.status().phase!=='settings')return false;
      const foreign=['section','import','import-button','list','apply','restore'].filter(key=>d.querySelector('[data-agent-skin-dream-'+key+']'));
      return {foreign,artwork:!!d.querySelector('[data-agent-skin-image-input=artwork]'),
        preset:!!d.querySelector('[data-agent-skin-preset-import]')};
    })()`),10000,'generated Appearance controls');
    assert.deepEqual(controls,{foreign:[],artwork:true,preset:true});
    await cdp.call('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
    await cdp.call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
    await until(()=>cdp.evaluate(`__startupAPI.status().phase==='complete'&&window.__azhouWallpaper?.status().applied`),10000,'existing wallpaper survives closing Appearance');
    return controls;
  });

  if (options.generatedPayload) await check('generated full owner chain restores navigation after settings cancellation and retains native input', async () => {
    await navigate('/fixture.html?generated-payload=1');
    await awaitGeneratedReady('full owner chain starts the generated payload');
    await until(() => cdp.evaluate(`window.__startupAPI.status().wallpaper.applied&&window.__azhouWallpaper?.status().applied`),
      10000, 'the navigation scenario begins with a committed appearance, not a skippable pending startup request');
    await cdp.evaluate(`document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]').click()`);
    await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='complete'&&window.__azhouWallpaper?.status().applied`),
      10000, 'initial committed wallpaper is ready');
    assert.equal(await cdp.evaluate('window.__startupAPI.openSettings()'), true);
    await until(() => cdp.evaluate(`window.__startupAPI.status().phase==='settings'`), 10000, 'settings panel opens');
    await cdp.call('Input.dispatchKeyEvent', {type:'rawKeyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
    await cdp.call('Input.dispatchKeyEvent', {type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
    const cancelled = await until(() => cdp.evaluate(`(()=>{const s=window.__startupAPI.status();return s.completion?.cause==='settings-cancel'?s:false;})()`),
      10000, 'settings cancels without saving or replay');
    await cdp.evaluate(`(()=>{
      window.__priorWorkspaceWallpaper=window.__azhouWallpaper;
      const old=document.querySelector('[data-app-shell-main-surface]'),next=old.cloneNode(true);
      for(const node of [next,...next.querySelectorAll('*')]) for(const attr of ['data-azhou-wallpaper-plane','data-azhou-wallpaper-pseudo','data-azhou-wallpaper-decoration']) node.removeAttribute(attr);
      const geometryStyle=document.createElement('style');document.head.appendChild(geometryStyle);
      const sheet=geometryStyle.sheet;
      const index=sheet.insertRule('.fixture-geometry-pending {flex:none!important;align-self:flex-start!important;width:0!important;height:0!important;min-width:0!important;min-height:0!important;padding:0!important;border:0!important}',sheet.cssRules.length);
      window.__geometryRule=sheet.cssRules[index];
      next.classList.add('fixture-geometry-pending');
      old.replaceWith(next);
    })()`);
    await until(() => cdp.evaluate('window.__fixtureMutationObserverStats().wallpaperShellWait.active>0'),5000,'new zero-sized main reaches pending availability lease');
    const zeroGeometry=await cdp.evaluate(`(()=>{const n=document.querySelector('[data-app-shell-main-surface]');return {width:n.getBoundingClientRect().width,className:n.className,style:n.getAttribute('style'),computed:getComputedStyle(n).width,rule:window.__geometryRule.cssText,connected:window.__geometryRule.parentStyleSheet.ownerNode.isConnected,all:[...document.querySelectorAll('[data-app-shell-main-surface]')].map(n=>({tag:n.tagName,classes:n.className,width:n.getBoundingClientRect().width}))};})()`);
    assert.equal(zeroGeometry.width,0,JSON.stringify(zeroGeometry));
    await cdp.evaluate(`window.__geometryRule.style.setProperty('width','600px','important');window.__geometryRule.style.setProperty('height','600px','important')`);
    const restored = await until(() => cdp.evaluate(`(()=>{
      const state=window.__startupAPI.status(),wallpaper=window.__azhouWallpaper;
      return wallpaper&&wallpaper!==window.__priorWorkspaceWallpaper&&state.wallpaper.applied&&wallpaper.status().applied
        ?{state,marked:!!document.querySelector('[data-app-shell-main-surface][data-azhou-wallpaper-plane]'),frames:document.querySelectorAll('iframe[aria-label]').length}:false;
    })()`), 10000, 'actual new DOM receives wallpaper through the original owner');
    assert.equal(restored.state.runId, cancelled.runId);
    assert.equal(restored.frames, 0);
    assert.equal(restored.marked, true);
    assert.equal(restored.state.wallpaper.fullCoverage,false);
    assert.equal(restored.state.wallpaper.coverage.auxiliary,'unknown');
    const point = await cdp.evaluate(`(()=>{const input=document.querySelector('textarea'),r=input.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    for(const type of ['mousePressed','mouseReleased']) await cdp.call('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1});
    await cdp.call('Input.insertText',{text:'工作区恢复后仍可输入'});
    assert.equal(await cdp.evaluate(`document.querySelector('textarea').value`), '工作区恢复后仍可输入');
    const button = await cdp.evaluate(`(()=>{const b=document.querySelector('button[aria-label="示例发送按钮"]');b.addEventListener('click',()=>{window.__hostControlClicks=(window.__hostControlClicks||0)+1;},{once:true});const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    for(const type of ['mousePressed','mouseReleased']) await cdp.call('Input.dispatchMouseEvent',{type,...button,button:'left',clickCount:1});
    assert.equal(await cdp.evaluate('window.__hostControlClicks'), 1);
    await cdp.evaluate('window.__startupAPI.dispose()');
    assert.equal(await cdp.evaluate(`document.querySelectorAll('[data-azhou-wallpaper-plane],[data-azhou-wallpaper-pseudo],[data-azhou-wallpaper-decoration]').length`),0);
    return {restored,actualInput:true,actualHostClick:true};
  });

  async function prepareGeneratedThemeMeasurement(scenario) {
    await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1');
    await awaitGeneratedReady('formal measurement installs the generated controller');
    assert.equal(await cdp.evaluate('!!window.__startupAPI && window.__startupInstallResult.installed===true'),true,'formal calibration must retain the generated payload controller');
    await until(()=>cdp.evaluate('window.__azhouWallpaper?.status().applied===true'),10000,'generated wallpaper applies before skip');
    await cdp.evaluate(`document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]').click()`);
    await until(()=>cdp.evaluate("window.__startupAPI.status().phase==='complete'"),10000,'generated startup completes');
    await cdp.evaluate(`(()=>{
      window.__formalMeasurementController=window.__startupAPI;
      const faultStyle=document.createElement('style');document.head.appendChild(faultStyle);
      faultStyle.sheet.insertRule('html[data-azhou-wallpaper=active] body:not([data-p07-no-such-fixture]) {}',0);
      window.__sceneFaultRule=faultStyle.sheet.cssRules[0];
      document.documentElement.style.zoom=${scenario.zoom};
      document.documentElement.style.setProperty('--color-surface',${JSON.stringify(scenario.color)});
      const main=document.querySelector('[data-app-shell-main-surface]');
      const scrollFixture=main.appendChild(document.createElement('div'));scrollFixture.style.height='1800px';scrollFixture.setAttribute('data-p07-scroll-fixture','');
      for(const node of document.querySelectorAll('.sidebar,.topbar'))node.style.background='transparent';
      window.__themeGeometry=()=>{const r=main.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,scroll:main.scrollTop};};
      window.__themeStructure=${observedThemeStructure.toString()};
      const measuredDocument=document,documentIdentity=crypto.randomUUID();
      window.__themeEvidence=()=>{if(document!==measuredDocument||!measuredDocument.documentElement.isConnected)throw Error('measured document replaced');const status=window.__azhouWallpaper?.status();return {now:performance.now(),documentToken:documentIdentity,documentTokenSource:'collector-document-identity',workspaceEpoch:status?.workspaceEpoch,geometry:window.__themeGeometry(),wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),status};};
      window.__themeMaskBounds=()=>{const wash=document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash');if(!wash.startsWith('url('))return null;const svg=decodeURIComponent(JSON.parse(wash.slice(4,-1)).split(',')[1]);const d=new DOMParser().parseFromString(svg,'image/svg+xml'),r=d.documentElement.lastElementChild;return Object.fromEntries(['x','y','width','height'].map(k=>[k,Number(r.getAttribute(k))]));};
      window.__themeApply=async value=>{
        const wait=async predicate=>{const end=performance.now()+15000;while(performance.now()<end){const result=predicate();if(result)return result;await new Promise(r=>setTimeout(r,20));}throw Error('formal settings timeout');};
        if(window.__startupAPI!==window.__formalMeasurementController)throw Error('formal controller replaced');
        if(!window.__startupAPI.openSettings())throw Error('formal settings rejected');
        const doc=await wait(()=>{const d=document.querySelector('iframe[aria-label]')?.contentDocument;return d?.querySelector('[data-agent-skin-theme-choice]')?d:false;});
        const select=(selector,value,event)=>{const element=doc.querySelector(selector);if(!element||element.disabled)throw Error('formal setting unavailable '+selector);element.value=value;element.dispatchEvent(new doc.defaultView.Event(event,{bubbles:true}));};
        select('[data-agent-skin-theme-choice]',value===null?'':'azhou-q-v3','change');
        if(value!==null){select('[data-agent-skin-theme-alpha-mode]','override','change');select('[data-agent-skin-theme-transparency]',String(value),'input');}
        const save=[...doc.querySelectorAll('button')].find(b=>/^(保存|Save)$/.test(b.textContent.trim()));
        if(!save||save.disabled)throw Error('formal save unavailable');save.click();
        await wait(()=>!document.querySelector('iframe[aria-label]')&&window.__startupAPI.status().wallpaper?.applied&&window.__azhouWallpaper?.status().applied);
        const state=window.__azhouWallpaper.status();
        if(value!==null&&state.themeApplied!==true)throw Error('saved theme not applied by controller');
        window.__formalMeasurementApplication={generated:true,publicSettingsSaved:true,runId:window.__startupAPI.status().runId,owner:window.__azhouWallpaper.owner};
        return state;
      };
    })()`);
  }
  async function verifyGeneratedSceneDisplacements(scenario,label) {
    await cdp.evaluate('window.__themeApply(100)');
    const geometry=await cdp.evaluate('window.__themeGeometry()');
    const roi={x:geometry.x+35,y:geometry.y+35,width:12,height:12};
    const baseline=await cdp.evaluate(`window.__sceneFaultOwner=window.__azhouWallpaper;window.__sceneFaultController=window.__startupAPI;window.__themeStructure(100)`);
    const captureFull=async name=>{const frame=(await cdp.call('Page.captureScreenshot',{format:'png',fromSurface:true})).data;await writeFile(join(options.out,name),Buffer.from(frame,'base64'));return frame;};
    const beforeName=label+'-scene-baseline.png',before=await captureFull(beforeName);
    const findings=[];
    for(const axis of ['x','y']) for(const offset of [-1,1]) {
      const mutation=await cdp.evaluate(`(()=>{
        const body=document.body,computed=getComputedStyle(body).backgroundPosition.split(',').map(v=>v.trim());
        if(computed.length!==2)throw Error('expected mask and scene background layers');
        const parts=computed[1].split(' ');if(parts.length!==2)throw Error('unsupported initial scene position');
        window.__sceneFaultRestore={value:window.__sceneFaultRule.style.getPropertyValue('background-position'),priority:window.__sceneFaultRule.style.getPropertyPriority('background-position')};
        const next=parts.map((value,index)=>index===${axis==='x'?0:1}?'calc('+value+' + (${offset}px))':value).join(' ');
        window.__sceneFaultRule.style.setProperty('background-position',computed[0]+', '+next,'important');
        return {before:computed.join(', '),after:getComputedStyle(body).backgroundPosition};
      })()`);
      try {
        await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
        const observed=await cdp.evaluate('window.__themeStructure(100)');
        const expected=structuredClone(baseline.invariant);expected.paint.position=mutation.after;
        assert.notEqual(mutation.after,mutation.before,'actual scene position changed');
        assert.deepEqual(observed.invariant,expected,'only actual scene background position changed');
        const owner=await cdp.evaluate('window.__sceneFaultOwner===window.__azhouWallpaper&&window.__sceneFaultController===window.__startupAPI&&window.__azhouWallpaper.status().applied');
        assert.equal(owner,true,'scene fault retained generated controller and wallpaper owner');
        const name=label+'-scene-'+axis+'-'+offset+'.png',after=await captureFull(name);
        const pixels=await cdp.evaluate(`(async()=>{
          const read=async data=>{const im=new Image();im.src='data:image/png;base64,'+data;await im.decode();const c=document.createElement('canvas');c.width=im.width;c.height=im.height;const ctx=c.getContext('2d');ctx.drawImage(im,0,0);const roi=${JSON.stringify(roi)},sx=im.width/${scenario.width},sy=im.height/${scenario.height};return ctx.getImageData(Math.round(roi.x*sx),Math.round(roi.y*sy),Math.round(roi.width*sx),Math.round(roi.height*sy)).data;};
          const a=await read(${JSON.stringify(before)}),b=await read(${JSON.stringify(after)});let max=0,changed=0;for(let i=0;i<a.length;i++)if(i%4!==3){const d=Math.abs(a[i]-b[i]);max=Math.max(max,d);if(d)changed++;}return {max,changed};
        })()`);
        findings.push({axis,offset,roi,mutation,structureDetected:true,ownerRetained:owner,baselineInvariant:baseline.invariant,injectedInvariant:observed.invariant,pixels,pixelDetected:pixels.max>1,rawBefore:beforeName,rawAfter:name});
      } finally {
        await cdp.evaluate(`(()=>{const r=window.__sceneFaultRestore;if(r.value)window.__sceneFaultRule.style.setProperty('background-position',r.value,r.priority);else window.__sceneFaultRule.style.removeProperty('background-position');})()`);
        await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
        assert.deepEqual((await cdp.evaluate('window.__themeStructure(100)')).invariant,baseline.invariant,'scene fault restored exact structure');
        const restoredOwner=await cdp.evaluate('window.__sceneFaultOwner===window.__azhouWallpaper&&window.__sceneFaultController===window.__startupAPI&&window.__azhouWallpaper.status().applied');
        assert.equal(restoredOwner,true);
        if(findings.at(-1)?.axis===axis&&findings.at(-1)?.offset===offset)findings.at(-1).restored={exactStructure:true,ownerRetained:restoredOwner};
      }
    }
    await writeFile(join(options.out,label+'-scene-displacements.json'),JSON.stringify({scenario,roi,findings},null,2));
    assert.ok(findings.every(f=>f.pixelDetected),'fixed scene ROI detects actual X/Y +/-1 CSS pixel displacement');
    return findings;
  }
  if(options.generatedPayload&&themeProtocol) await check('generated measurement scene detects actual image displacement in four conditions',async()=>{
    const findings=[];
    for(const scenario of themeProtocol.conditions){
      await cdp.call('Emulation.setDeviceMetricsOverride',{width:scenario.width,height:scenario.height,deviceScaleFactor:scenario.dpr,mobile:false});
      await prepareGeneratedThemeMeasurement(scenario);
      findings.push(await verifyGeneratedSceneDisplacements(scenario,'controls-'+scenario.width+'-'+scenario.color.slice(1)));
    }
    await cdp.call('Emulation.clearDeviceMetricsOverride');
    return {findings,scope:'measurement fixture detection controls, not training or acceptance'};
  });

  if(options.generatedPayload) await check('generated theme measurement uses public settings and retained payload owner',async()=>{
    await prepareGeneratedThemeMeasurement({zoom:1,color:'#123b57'});
    const applied=await cdp.evaluate('window.__themeApply(57)');assert.equal(applied.themeApplied,true);
    return cdp.evaluate('window.__formalMeasurementApplication');
  });

  await check('theme readability is pixel bounded through viewport changes and legacy handover', async () => {
    const results=[];
    for (const scenario of themeProtocol ? themeProtocol.conditions.map(condition=>({...condition,trial:themeProtocol.session})) : Array.from({length:5},(_,trial)=>[{width:997,height:613,dpr:1.5,zoom:0.9},{width:811,height:577,dpr:2,zoom:1.1}].flatMap(v=>['#123b57','#d8c49a'].map(color=>({...v,color,trial})))).flat()) {
      await cdp.call('Emulation.setDeviceMetricsOverride',{width:scenario.width,height:scenario.height,deviceScaleFactor:scenario.dpr,mobile:false});
      if(options.generatedPayload&&themeProtocol) await prepareGeneratedThemeMeasurement(scenario);
      else {
      await navigate('/fixture.html?legacy-only=1');
      await cdp.evaluate(`(async()=>{
        const {createCodexPageAdapter}=await import('/extension/codex-page-adapter.mjs');
        const {createObservedRenderer}=await import('/workspace-renderer.mjs');
        let host; host=new Proxy(window,{get(target,key){
          if(['window','top','self','globalThis'].includes(key))return host;
          if(key==='location')return new URL('app://-/index.html');
          const value=Reflect.get(target,key,target);
          return typeof value==='function'&&['getComputedStyle','addEventListener','removeEventListener','setTimeout','clearTimeout','atob','createImageBitmap'].includes(key)?value.bind(target):value;
        }});
        const main=document.querySelector('[data-app-shell-main-surface]');
        document.documentElement.style.zoom=${scenario.zoom};
        const scrollFixture=main.appendChild(document.createElement('div'));scrollFixture.style.height='1800px';scrollFixture.setAttribute('data-p07-scroll-fixture','');
        // Transparent synthetic chrome makes an accidental global wash observable.
        for(const node of document.querySelectorAll('.sidebar,.topbar'))node.style.background='transparent';
        const canvas=document.createElement('canvas');canvas.width=1200;canvas.height=800;
        const ctx=canvas.getContext('2d');for(let y=0;y<800;y+=17)for(let x=0;x<1200;x+=19){ctx.fillStyle=((x/19+Math.floor(y/17))%2)?'#ff6030':'#2060ff';ctx.fillRect(x,y,19,17);}
        const css=await(await fetch('/wallpaper.css')).text();const adapter=createCodexPageAdapter(host);const render=createObservedRenderer(host);
        const image=canvas.toDataURL('image/png');const bytes=Uint8Array.from(atob(image.split(',')[1]),c=>c.charCodeAt(0));
        const imageSHA256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
        window.__themeApply=async value=>render({version:'0.9.0',css,image,imageSHA256,strength:37,surface:${JSON.stringify(scenario.color)},pageAdapter:adapter,workspaceObservation:adapter.observeWorkspace(host),
          ...(value===null?{}:{themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value}}}})});
        window.__themeGeometry=()=>{const r=main.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,scroll:main.scrollTop};};
        window.__themeStructure=${observedThemeStructure.toString()};
        window.__themeEvidence=()=>{const observation=adapter.observeWorkspace(host);return {now:performance.now(),documentToken:observation.documentToken,workspaceEpoch:observation.workspaceEpoch,geometry:window.__themeGeometry(),wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),status:window.__azhouWallpaper?.status()};};
        window.__themeMaskBounds=()=>{const wash=document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash');if(!wash.startsWith('url('))return null;const svg=decodeURIComponent(JSON.parse(wash.slice(4,-1)).split(',')[1]);const d=new DOMParser().parseFromString(svg,'image/svg+xml'),r=d.documentElement.lastElementChild;return Object.fromEntries(['x','y','width','height'].map(k=>[k,Number(r.getAttribute(k))]));};
      })()`);
      }
      await cdp.evaluate(`window.__themePaintContext=async value=>{
        const owner=window.__azhouWallpaper,status=owner?.status();
        if(window.__formalMeasurementController && (window.__startupAPI!==window.__formalMeasurementController || window.__formalMeasurementApplication?.owner!==owner?.owner || !window.__startupAPI.status().wallpaper?.applied))throw Error('formal payload owner lost');
        if(!owner||owner!==window.__themeCapturedOwner||owner!==window.__azhouWallpaper||status?.applied!==true||status.themeApplied!==true||status.themePending!==false)throw Error('measurement owner not continuously valid');
        const structure=await window.__themeStructure(value);
        const properties=['backgroundColor','backgroundImage','backgroundSize','backgroundPosition','backgroundAttachment','backgroundRepeat','opacity','filter','backdropFilter','transform','mixBlendMode','backgroundBlendMode','zoom'];
        const paint={};for(const [name,node] of [['root',document.documentElement],['body',document.body],['sidebar',document.querySelector('.sidebar')],['header',document.querySelector('.topbar')]]){
          if(!node?.isConnected)throw Error('measurement surface disconnected');const css=getComputedStyle(node);paint[name]=Object.fromEntries(properties.map(key=>[key,css[key]]));
          if(name==='body')paint[name].backgroundImage=structure.invariant.paint.backgroundImage;
        }
        if(owner!==window.__azhouWallpaper||owner.status().applied!==true)throw Error('measurement owner retired during observation');
        return {executionLane:window.__formalMeasurementController?'generated-payload-public-settings':'source-fixture',controllerOwner:window.__formalMeasurementController?.owner||null,owner:owner.owner,retained:true,mainConnected:document.querySelector('[data-app-shell-main-surface]')?.isConnected===true,paint,viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},structure};
      }`);
      const captureFrame=async()=> (await cdp.call('Page.captureScreenshot',{format:'png',fromSurface:true})).data;
      // All probes in a sample derive from one fixed full-viewport raster. CDP
      // clip capture changes the rasterization path, even for unchanged input.
      const capture=async(x,y,frame)=>{
        const pixels=frame??await captureFrame();
        return cdp.evaluate(`(async()=>{const image=new Image();image.src='data:image/png;base64,'+${JSON.stringify(pixels)};await image.decode();const source=document.createElement('canvas');source.width=image.width;source.height=image.height;const ctx=source.getContext('2d');ctx.drawImage(image,0,0);const sx=image.width/${scenario.width},sy=image.height/${scenario.height};const width=Math.round(12*sx),height=Math.round(12*sy);const data=ctx.getImageData(Math.round(${x}*sx),Math.round(${y}*sy),width,height);const crop=document.createElement('canvas');crop.width=width;crop.height=height;crop.getContext('2d').putImageData(data,0,0);return crop.toDataURL('image/png').split(',')[1];})()`);
      };
      const delta=async(a,b)=>cdp.evaluate(`(async()=>{const read=async src=>{const img=new Image();img.src='data:image/png;base64,'+src;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const ctx=c.getContext('2d');ctx.drawImage(img,0,0);return ctx.getImageData(0,0,c.width,c.height).data;};const a=await read(${JSON.stringify(a)}),b=await read(${JSON.stringify(b)});let max=0,total=0,count=0;for(let i=0;i<a.length;i++)if(i%4!==3){const d=Math.abs(a[i]-b[i]);max=Math.max(max,d);total+=d;count++;}return {max,mean:total/count};})()`);
      await cdp.evaluate('window.__themeApply(null)');
      const baselineFrame=await captureFrame();
      const baselineOutside={sidebar:await capture(24,180,baselineFrame),top:await capture(280,24,baselineFrame)};
      // Negative control: the original global-alpha approach must be detected.
      await cdp.evaluate("document.documentElement.style.setProperty('--azhou-wallpaper-wash','linear-gradient(transparent,transparent)')");
      await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      assert.ok((await delta(await capture(24,180),baselineOutside.sidebar)).max>1,'transparent sidebar probe detects global wash leakage');
      assert.ok((await delta(await capture(280,24),baselineOutside.top)).max>1,'transparent header probe detects global wash leakage');
      const samples=[];
      for(const value of themeProtocol?.transparencies??[0,15,57,85,100]) {
        const applied=await cdp.evaluate(`window.__themeApply(${value})`);assert.equal(applied.applied,true);
        await cdp.evaluate('window.__themeCapturedOwner=window.__azhouWallpaper');
        await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
        const geometry=await cdp.evaluate('window.__themeGeometry()');
        const firstBefore=await cdp.evaluate('window.__themeEvidence()');
        const firstContextBefore=await cdp.evaluate('window.__themePaintContext('+value+')');
        const frame=await captureFrame();
        const firstContextAfter=await cdp.evaluate('window.__themePaintContext('+value+')');
        const firstAfter=await cdp.evaluate('window.__themeEvidence()');
        await writeFile(join(options.out,'full-frame-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'-'+value+'.png'),Buffer.from(frame,'base64'));
        const sample={value,geometry,applied,sidebar:await capture(24,180,frame),top:await capture(280,24,frame),inside:await capture(geometry.x+35,geometry.y+35,frame)};
        sample.wash=await cdp.evaluate('document.documentElement.style.getPropertyValue("--azhou-wallpaper-wash")');
        sample.structure=await cdp.evaluate('window.__themeStructure('+value+')');
        sample.contexts=[{before:firstContextBefore,after:firstContextAfter}];
        sample.sameT=[];sample.evidence=[{before:firstBefore,after:firstAfter}];sample.rawFrames=['full-frame-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'-'+value+'.png'];
        for(let repeat=0;repeat<(themeProtocol?5:3);repeat++){
          const before=await cdp.evaluate('window.__themeEvidence()');
          const contextBefore=await cdp.evaluate('window.__themePaintContext('+value+')');
          const repeatedFrame=await captureFrame();
          const contextAfter=await cdp.evaluate('window.__themePaintContext('+value+')');
          sample.contexts.push({before:contextBefore,after:contextAfter});
          const filename='full-frame-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'-'+value+'-repeat-'+repeat+'.png';
          await writeFile(join(options.out,filename),Buffer.from(repeatedFrame,'base64'));sample.rawFrames.push(filename);
          sample.sameT.push(await capture(280,24,repeatedFrame));
          const after=await cdp.evaluate('window.__themeEvidence()');sample.evidence.push({before,after});
        }

        samples.push(sample);
        await screenshot('theme-scope-'+scenario.width+'-'+value+'.png');
      }
      await writeFile(join(options.out,'outside-legacy.png'),Buffer.from(baselineOutside.sidebar,'base64'));
      await writeFile(join(options.out,'outside-candidate.png'),Buffer.from(samples[0].sidebar,'base64'));
      const outsideDeltas=[];for(const sample of samples)outsideDeltas.push({value:sample.value,sidebar:await delta(sample.sidebar,baselineOutside.sidebar),top:await delta(sample.top,baselineOutside.top)});
      const legacyWithinEmpiricalBudget=outsideDeltas.every(s=>s.sidebar.max<=1&&s.top.max<=1);
      await writeFile(join(options.out,'outside-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'.json'),JSON.stringify({baselineOutside,samples:samples.map(({value,geometry,sidebar,top,sameT,wash,evidence,applied,structure,rawFrames,contexts})=>({value,geometry,sidebar,top,sameT,wash,evidence,applied,structure,rawFrames,contexts}))}));
      for(const sample of samples)assert.deepEqual(sample.structure.invariant,samples[0].structure.invariant,'only the authorized local opacity may change');
      const interTheme=[];for(const sample of samples)interTheme.push({sidebar:await delta(sample.sidebar,samples[0].sidebar),top:await delta(sample.top,samples[0].top)});
      const outsideTExact=interTheme.every(s=>s.sidebar.max===0&&s.top.max===0);
      const sameTDeltas=[];for(const sample of samples)for(const repeated of sample.sameT)sameTDeltas.push({value:sample.value,...await delta(sample.top,repeated)});
      const sameTExact=sameTDeltas.every(sample=>sample.max===0);
      for(const sample of samples)for(const evidence of sample.evidence){
        const {now:beforeTime,...before}=evidence.before,{now:afterTime,...after}=evidence.after;
        assert.ok(afterTime>=beforeTime);assert.deepEqual(after,before,'capture must not change theme identity or geometry');
      }
      for(const sample of samples.slice(1)){assert.deepEqual(sample.geometry,samples[0].geometry);}
      assert.notEqual(samples[0].inside,samples[1].inside);assert.notEqual(samples[1].inside,samples[2].inside);
      await cdp.evaluate('window.__themeApply(0)');
      const boundary=samples[0].geometry;
      const boundaryROI={x:boundary.x+5,y:boundary.y-2,width:12,height:12};
      const boundarySamples={};
      const captureBoundary=async stage=>{
        const frame=await captureFrame();
        const roi=await capture(boundaryROI.x,boundaryROI.y,frame);
        boundarySamples[stage]={frame,roi};
        return roi;
      };
      const retainBoundaryFailure=async (failure,clipFault,restoration)=>{
        try {
          const prefix='clip-fault-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'-'+failure;
          const captures={};
          for(const [stage,{frame,roi}] of Object.entries(boundarySamples)) {
            const raw=Buffer.from(frame,'base64');
            const width=raw.readUInt32BE(16),height=raw.readUInt32BE(20);
            const sx=width/scenario.width,sy=height/scenario.height;
            const rawFile=prefix+'-'+stage+'-raw.png',roiFile=prefix+'-'+stage+'-roi.png';
            captures[stage]={raw:rawFile,roi:roiFile,viewport:{width,height},pixelROI:{
              x:Math.round(boundaryROI.x*sx),y:Math.round(boundaryROI.y*sy),
              width:Math.round(boundaryROI.width*sx),height:Math.round(boundaryROI.height*sy),
            }};
            await writeFile(join(options.out,rawFile),raw);
            await writeFile(join(options.out,roiFile),Buffer.from(roi,'base64'));
          }
          const postFailure=await cdp.evaluate(`(()=>{const state=window.__themeEvidence(),owner=window.__azhouWallpaper;return {
            owner:owner?.owner??null,applied:state.status?.applied===true,imageDecoded:state.status?.imageDecoded===true,
            documentToken:state.documentToken,workspaceEpoch:state.workspaceEpoch,geometry:state.geometry,wash:state.wash,
          };})()`).then(state=>({...state,washMatchesOriginal:state.wash===injected.before}),
            error=>({error:String(error)}));
          await writeFile(join(options.out,prefix+'-manifest.json'),JSON.stringify({
            schema:1,scenario,boundary,cssROI:boundaryROI,captures,failure,clipFault,restoration,postFailure,
          }));
        } catch(error) {
          // Evidence collection must not replace the original strict assertion.
          console.error('Failed to retain boundary control diagnostics:',error);
        }
      };
      const boundaryBefore=await captureBoundary('before');
      const injected=await cdp.evaluate(`(async()=>{const root=document.documentElement,before=root.style.getPropertyValue('--azhou-wallpaper-wash');const svg=decodeURIComponent(JSON.parse(before.slice(4,-1)).split(',')[1]);const d=new DOMParser().parseFromString(svg,'image/svg+xml');for(const r of [d.querySelector('mask rect[fill="black"]'),d.documentElement.lastElementChild])r.setAttribute('y',Number(r.getAttribute('y'))+1);const source='data:image/svg+xml,'+encodeURIComponent(new XMLSerializer().serializeToString(d));const image=new Image();image.src=source;await image.decode();image.src='';const after='url('+JSON.stringify(source)+')';root.style.setProperty('--azhou-wallpaper-wash',after);return {before,after};})()`);
      await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      const boundaryAfter=await captureBoundary('displaced');
      const clipFault=await delta(boundaryBefore,boundaryAfter);
      await writeFile(join(options.out,'clip-fault-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'.json'),JSON.stringify({clipFault,injected}));
      if (!(clipFault.max>1)) await retainBoundaryFailure('displacement',clipFault,null);
      assert.ok(clipFault.max>1,'actual one-pixel clip displacement must be detected '+JSON.stringify({clipFault,injected}));
      await cdp.evaluate('document.documentElement.style.setProperty("--azhou-wallpaper-wash",'+JSON.stringify(injected.before)+')');
      await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      const boundaryRestored=await captureBoundary('restored');
      const restoration=await delta(boundaryBefore,boundaryRestored);
      if (restoration.max!==0) await retainBoundaryFailure('restoration',clipFault,restoration);
      assert.equal(restoration.max,0);
      await cdp.evaluate(`window.__themeFaultOwner=window.__azhouWallpaper;window.__themeFaultObservation=()=>{
        const owner=window.__themeFaultOwner,status=owner?.status();
        if(!owner||owner!==window.__azhouWallpaper||status?.reason==='disposed'||status?.imageDecoded!==true)throw Error('fault control owner invalid');
        const root=document.documentElement,body=getComputedStyle(document.body);
        return {retained:true,owner:owner.owner,geometry:window.__themeGeometry(),wash:root.style.getPropertyValue('--azhou-wallpaper-wash'),image:root.style.getPropertyValue('--azhou-wallpaper-image'),paint:{image:body.backgroundImage,size:body.backgroundSize,position:body.backgroundPosition,attachment:body.backgroundAttachment},applied:status.applied};
      }`);
      const structuralBaseline=await cdp.evaluate('window.__themeStructure(0)');
      const structuralFaults=[];
      for(const fault of [{kind:'rect',delta:-1},{kind:'rect',delta:1},{kind:'outer-alpha',delta:1/255},{kind:'outer-alpha',delta:0.01},{kind:'global-wash'}]){
        const faultIndex=structuralFaults.length;
        const controlBefore=await cdp.evaluate('window.__themeFaultObservation()');assert.equal(controlBefore.applied,true);
        const faultBeforeName='fault-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'-'+faultIndex+'-before.png';
        await writeFile(join(options.out,faultBeforeName),Buffer.from(await captureFrame(),'base64'));
        const controlBeforeAfter=await cdp.evaluate('window.__themeFaultObservation()');assert.deepEqual(controlBeforeAfter,controlBefore);
        const mutation=await cdp.evaluate(`(async()=>{const root=document.documentElement,before=root.style.getPropertyValue('--azhou-wallpaper-wash');window.__themeFaultOriginal=before;const fault=${JSON.stringify(fault)};if(fault.kind==='global-wash'){root.style.setProperty('--azhou-wallpaper-wash','linear-gradient(transparent,transparent)');return {before,after:root.style.getPropertyValue('--azhou-wallpaper-wash')};}const source=decodeURIComponent(JSON.parse(before.slice(4,-1)).split(',')[1]);const xml=new DOMParser().parseFromString(source,'image/svg+xml');if(fault.kind==='rect'){for(const r of [xml.querySelector('mask rect[fill="black"]'),xml.documentElement.lastElementChild])r.setAttribute('y',Number(r.getAttribute('y'))+fault.delta);}else for(const stop of xml.querySelectorAll('stop'))stop.setAttribute('stop-opacity',Math.min(1,Number(stop.getAttribute('stop-opacity'))+fault.delta));const uri='data:image/svg+xml,'+encodeURIComponent(new XMLSerializer().serializeToString(xml));const image=new Image();image.src=uri;await image.decode();root.style.setProperty('--azhou-wallpaper-wash','url('+JSON.stringify(uri)+')');return {before,after:root.style.getPropertyValue('--azhou-wallpaper-wash')};})()`);
        const verdict=await cdp.evaluate(`(async()=>{try{return {observed:await window.__themeStructure(0)};}catch(error){const message=String(error?.message||error);if(!['theme structure: workspace geometry y','theme structure: not a local color mask'].includes(message))throw error;return {oracleRejection:message};}})()`);
        let rejectionReason;
        if(fault.kind==='outer-alpha'){
          assert.ok(verdict.observed,'alpha control must remain valid XML');
          const expected=structuredClone(structuralBaseline.invariant);
          for(const stop of expected.stops)stop['stop-opacity']=String(Math.min(1,Number(stop['stop-opacity'])+fault.delta));
          assert.deepEqual(verdict.observed.invariant,expected,'only intended exterior alpha changed');
          rejectionReason='external-alpha-invariant-mismatch';
        }else{
          rejectionReason=fault.kind==='rect'?'theme structure: workspace geometry y':'theme structure: not a local color mask';
          assert.equal(verdict.oracleRejection,rejectionReason,'only expected oracle rejection counts');
        }
        const rejected=true;
        const controlInjected=await cdp.evaluate('window.__themeFaultObservation()');
        assert.equal(controlInjected.wash,mutation.after);assert.notEqual(mutation.before,mutation.after);
        assert.deepEqual(controlInjected.geometry,controlBefore.geometry);assert.equal(controlInjected.image,controlBefore.image);
        if(fault.kind!=='global-wash')assert.ok(controlInjected.paint.image.includes(JSON.parse(mutation.after.slice(4,-1))),'injected SVG actually painted');
        else assert.ok(controlInjected.paint.image.startsWith('linear-gradient('),'global wash actually painted');
        assert.equal(rejected,true,'actual applied structural fault must be detected '+JSON.stringify(fault));
        const faultAfterName='fault-'+scenario.width+'-'+scenario.color.slice(1)+'-'+scenario.trial+'-'+faultIndex+'-after.png';
        await writeFile(join(options.out,faultAfterName),Buffer.from(await captureFrame(),'base64'));
        const controlInjectedAfter=await cdp.evaluate('window.__themeFaultObservation()');assert.deepEqual(controlInjectedAfter,controlInjected);

        await cdp.evaluate('document.documentElement.style.setProperty("--azhou-wallpaper-wash",window.__themeFaultOriginal)');
        assert.deepEqual((await cdp.evaluate('window.__themeStructure(0)')).invariant,structuralBaseline.invariant);
        const controlRestored=await cdp.evaluate('window.__themeFaultObservation()');assert.deepEqual(controlRestored,controlBefore);
        structuralFaults.push({...fault,rejected,rejectionReason,mutation,controlBefore,controlBeforeAfter,controlInjected,controlInjectedAfter,controlRestored,rawBefore:faultBeforeName,rawAfter:faultAfterName,pixelDisposition:'pending-independent-envelope-comparison'});
      }

      const sceneDisplacements=options.generatedPayload&&themeProtocol?await verifyGeneratedSceneDisplacements(scenario,'training-'+scenario.width+'-'+scenario.color.slice(1)):null;
      await cdp.evaluate('window.__themeApply(100)');
      const themePixels=await capture(samples[2].geometry.x+35,samples[2].geometry.y+35);
      const before=await cdp.evaluate('window.__themeGeometry()');
      const registrationNegative=await delta(themePixels,await capture(before.x+36,before.y+35));
      assert.ok(registrationNegative.max>1,'one CSS pixel sampling offset must fail pixel comparison (comparator diagnostic, not actual scene mutation)');
      await writeFile(join(options.out,'crop-theme-'+scenario.width+'.png'),Buffer.from(themePixels,'base64'));
      const themeGeometry=await cdp.evaluate(`(()=>{const s=getComputedStyle(document.querySelector('[data-app-shell-main-surface]'));return {size:s.backgroundSize,position:s.backgroundPosition,attachment:s.backgroundAttachment};})()`);
      const legacy=await cdp.evaluate(`(async()=>{const old=window.__azhouWallpaper;const result=await window.__themeApply(null);old.dispose();return {applied:result.applied,marker:document.querySelector('[data-azhou-theme-readability]')!==null,geometry:window.__themeGeometry()};})()`);
      assert.equal(legacy.applied,true);assert.equal(legacy.marker,false);assert.deepEqual(legacy.geometry,before);
      // Remove only the test renderer's wash to compare the same image at the same
      // screen coordinate. This is fixture inspection, not a product styling path.
      const legacyWash=await cdp.evaluate("document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash')");
      await cdp.evaluate("document.documentElement.style.setProperty('--azhou-wallpaper-wash','linear-gradient(transparent,transparent)')");
      await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      const legacyPixels=await capture(before.x+35,before.y+35);
      await writeFile(join(options.out,'crop-legacy-'+scenario.width+'.png'),Buffer.from(legacyPixels,'base64'));
      assert.equal(await capture(before.x+35,before.y+35),legacyPixels,'repeat capture is self-consistent');
      const cropGeometry=await cdp.evaluate(`(()=>{const m=document.querySelector('[data-app-shell-main-surface]');const pick=n=>{const s=getComputedStyle(n),r=n.getBoundingClientRect();return {rect:{x:r.x,y:r.y,width:r.width,height:r.height},size:s.backgroundSize,position:s.backgroundPosition,attachment:s.backgroundAttachment,zoom:s.zoom};};return {body:pick(document.body),main:pick(m),viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio}};})()`);
      const cropDifference=await cdp.evaluate(`(async()=>{const read=async src=>{const img=new Image();img.src='data:image/png;base64,'+src;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const ctx=c.getContext('2d');ctx.drawImage(img,0,0);return ctx.getImageData(0,0,c.width,c.height).data;};const a=await read(${JSON.stringify(themePixels)}),b=await read(${JSON.stringify(legacyPixels)});let max=0,total=0,count=0;for(let i=0;i<a.length;i++)if(i%4!==3){const d=Math.abs(a[i]-b[i]);max=Math.max(max,d);total+=d;count++;}return {max,mean:total/count};})()`);
      assert.equal(cropDifference.max,0,'viewport crop pixel delta '+JSON.stringify({cropDifference,cropGeometry,themeGeometry}));
      await cdp.evaluate('document.documentElement.style.setProperty("--azhou-wallpaper-wash",'+JSON.stringify(legacyWash)+')');
      assert.equal((await cdp.evaluate('window.__themeApply(30)')).applied,true);
      await cdp.evaluate('window.__heldThemeOwner=window.__azhouWallpaper');
      await cdp.call('Emulation.setDeviceMetricsOverride',{width:scenario.width-40,height:scenario.height-30,deviceScaleFactor:scenario.dpr,mobile:false});
      await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      await until(()=>cdp.evaluate('window.__azhouWallpaper?.status().themeApplied===true'),5000,'same owner settles resized SVG mask');
      const automaticResize=await cdp.evaluate(`(()=>{const r=document.querySelector('[data-app-shell-main-surface]').getBoundingClientRect();return {applied:window.__azhouWallpaper?.status().applied,sameOwner:window.__heldThemeOwner===window.__azhouWallpaper,rect:{x:r.x,y:r.y,width:r.width,height:r.height},mask:window.__themeMaskBounds()};})()`);
      assert.equal(automaticResize.applied,true);assert.equal(automaticResize.sameOwner,true);assert.deepEqual(automaticResize.mask,automaticResize.rect);
      await cdp.call('Input.dispatchMouseEvent',{type:'mouseWheel',x:automaticResize.rect.x+5,y:150,deltaX:0,deltaY:120});
      await until(()=>cdp.evaluate('document.querySelector(".thread-scroll-container").scrollTop>0'),3000,'wheel moves actual thread scroller');
      const threadScroll=await cdp.evaluate('document.querySelector(".thread-scroll-container").scrollTop');
      await cdp.call('Input.dispatchMouseEvent',{type:'mouseWheel',x:24,y:150,deltaX:0,deltaY:120});
      try{await until(()=>cdp.evaluate('scrollY>0'),3000,'actual wheel scroll must move document');}catch(e){throw new Error(e.message+' '+JSON.stringify(await cdp.evaluate(`({scrollY,html:{height:document.documentElement.clientHeight,scrollHeight:document.documentElement.scrollHeight,overflow:getComputedStyle(document.documentElement).overflow},body:{height:document.body.clientHeight,scrollHeight:document.body.scrollHeight,overflow:getComputedStyle(document.body).overflow},scroller:document.scrollingElement?.tagName,hit:document.elementFromPoint(${automaticResize.rect.x+5},150)?.outerHTML.slice(0,200)})`)));}
      await cdp.evaluate('new Promise(r=>setTimeout(r,100))');
      await until(()=>cdp.evaluate('window.__azhouWallpaper?.status().themeApplied===true'),5000,'same owner settles wheel geometry');
      const scrolling=await cdp.evaluate(`(()=>{const r=document.querySelector('[data-app-shell-main-surface]').getBoundingClientRect();return {scrollY,sameOwner:window.__heldThemeOwner===window.__azhouWallpaper,mask:window.__themeMaskBounds(),rect:{x:r.x,y:r.y,width:r.width,height:r.height}};})()`);
      assert.ok(scrolling.scrollY>0);assert.equal(scrolling.sameOwner,true);assert.deepEqual(scrolling.mask,scrolling.rect);
      await cdp.evaluate('scrollTo(0,0)');await cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      assert.equal((await cdp.evaluate('window.__themeApply(30)')).applied,true);
      const replacement=await cdp.evaluate(`(async()=>{const old=document.querySelector('[data-app-shell-main-surface]');const next=old.cloneNode(true);
        for(const node of [next,...next.querySelectorAll('*')])for(const name of ['data-azhou-wallpaper-plane','data-azhou-wallpaper-pseudo','data-azhou-wallpaper-decoration','data-azhou-theme-readability'])node.removeAttribute(name);
        const prior=window.__azhouWallpaper;old.replaceWith(next);await new Promise(r=>setTimeout(r,0));const invalidated=!window.__azhouWallpaper;
        const result=await window.__themeApply(30);prior.dispose();return {invalidated,applied:result.applied,detachedMarker:old.getAttribute('data-azhou-wallpaper-plane'),newMarker:!!next.getAttribute('data-azhou-wallpaper-plane')};})()`);
      assert.deepEqual(replacement,{invalidated:true,applied:true,detachedMarker:null,newMarker:true});
      await cdp.evaluate('window.__azhouWallpaper.dispose()');
      assert.equal(await cdp.evaluate("document.querySelectorAll('[data-azhou-theme-layer]').length"),0);
      results.push({scenario,threadScroll,clipFault,structuralFaults,sceneDisplacements,registrationNegative,outsideDeltas,interTheme,sameTDeltas,sameTExact,automaticResize,scrolling,legacyWithinEmpiricalBudget,outsideTExact,themePixelsOutsideUnchanged:true,pixelsInsideChanged:true,geometryUnchanged:true,viewportCropEqual:true,legacy,replacement});
    }
    await cdp.call('Emulation.clearDeviceMetricsOverride');
    await writeFile(join(options.out,'holdout-matrix.json'),JSON.stringify(results,null,2));
    // V1/V2 pixel outcomes remain diagnostics; V3 acceptance is a separate
    // registered train/frozen-envelope/holdout gate, never this collection check.
    if(themeProtocol) assert.ok(results.every(r=>r.legacyWithinEmpiricalBudget),'legacy empirical budget failed');
    return {results,protocol:themeProtocol,measurementDisposition:themeProtocol?'raw-collection-only; independent V3 analysis required':'functional-structural-only; calibrated V3 measurement NOT RUN',scope:'synthetic Chrome pixels; not native host or final Azhou asset visual approval'};
  });


  await check('theme ancestor clipping revokes paint without a main rectangle change',async()=>{
    const scenario={color:'#123b57'};
    await cdp.call('Emulation.setDeviceMetricsOverride',{width:1100,height:800,deviceScaleFactor:1,mobile:false});
    await navigate('/fixture.html?legacy-only=1');
      await cdp.evaluate(`(async()=>{
        const {createCodexPageAdapter}=await import('/extension/codex-page-adapter.mjs');
        const {createObservedRenderer}=await import('/workspace-renderer.mjs');
        let host; host=new Proxy(window,{get(target,key){
          if(['window','top','self','globalThis'].includes(key))return host;
          if(key==='location')return new URL('app://-/index.html');
          const value=Reflect.get(target,key,target);
          return typeof value==='function'&&['getComputedStyle','addEventListener','removeEventListener','setTimeout','clearTimeout','atob','createImageBitmap'].includes(key)?value.bind(target):value;
        }});
        const main=document.querySelector('[data-app-shell-main-surface]');
        document.documentElement.style.zoom=1;
        const clip=main.parentElement.insertBefore(document.createElement('div'),main);clip.id='p07-clip';clip.style.cssText='position:absolute;left:240px;top:64px;width:400px;height:300px;overflow:visible';clip.appendChild(main);main.style.cssText='position:absolute;left:0;top:0;width:800px;height:600px;flex:none';
        window.__themeClip=clip;
        const scrollFixture=main.appendChild(document.createElement('div'));scrollFixture.style.height='1800px';scrollFixture.setAttribute('data-p07-scroll-fixture','');
        // Transparent synthetic chrome makes an accidental global wash observable.
        for(const node of document.querySelectorAll('.sidebar,.topbar'))node.style.background='transparent';
        const canvas=document.createElement('canvas');canvas.width=1200;canvas.height=800;
        const ctx=canvas.getContext('2d');for(let y=0;y<800;y+=17)for(let x=0;x<1200;x+=19){ctx.fillStyle=((x/19+Math.floor(y/17))%2)?'#ff6030':'#2060ff';ctx.fillRect(x,y,19,17);}
        const css=await(await fetch('/wallpaper.css')).text();const adapter=createCodexPageAdapter(host);const render=createObservedRenderer(host);
        const image=canvas.toDataURL('image/png');const bytes=Uint8Array.from(atob(image.split(',')[1]),c=>c.charCodeAt(0));
        const imageSHA256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
        window.__themeApply=async value=>render({version:'0.9.0',css,image,imageSHA256,strength:37,surface:${JSON.stringify(scenario.color)},pageAdapter:adapter,workspaceObservation:adapter.observeWorkspace(host),
          ...(value===null?{}:{themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value}}}})});
        window.__themeAdapter=adapter;window.__themeHost=host;
        window.__themeGeometry=()=>{const r=main.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,scroll:main.scrollTop};};
        window.__themeStructure=${observedThemeStructure.toString()};
        window.__themeEvidence=()=>{const observation=adapter.observeWorkspace(host);return {now:performance.now(),documentToken:observation.documentToken,workspaceEpoch:observation.workspaceEpoch,geometry:window.__themeGeometry(),wash:document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash'),status:window.__azhouWallpaper?.status()};};
        window.__themeMaskBounds=()=>{const wash=document.documentElement.style.getPropertyValue('--azhou-wallpaper-wash');if(!wash.startsWith('url('))return null;const svg=decodeURIComponent(JSON.parse(wash.slice(4,-1)).split(',')[1]);const d=new DOMParser().parseFromString(svg,'image/svg+xml'),r=d.documentElement.lastElementChild;return Object.fromEntries(['x','y','width','height'].map(k=>[k,Number(r.getAttribute(k))]));};
      })()`);

    const settle=()=>cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
    const capture=async()=>(await cdp.call('Page.captureScreenshot',{format:'png',fromSurface:true,clip:{x:700,y:400,width:24,height:24,scale:1}})).data;
    await cdp.evaluate("window.__themeClip.style.overflow='hidden'");await settle();
    const nativeClip=await capture();
    await cdp.evaluate("window.__themeClip.style.overflow='visible'");await settle();
    const applied=await cdp.evaluate('window.__themeApply(30)');assert.equal(applied.themeApplied,true);
    const before=await cdp.evaluate('window.__themeGeometry()');
    await cdp.evaluate("window.__oldThemeOwner=window.__azhouWallpaper;window.__themeClip.style.overflow='hidden'");await settle();
    const clipped=await cdp.evaluate('({geometry:window.__themeGeometry(),owner:!!window.__azhouWallpaper,admission:window.__themeAdapter.readThemeGeometry(window.__themeAdapter.observeWorkspace(window.__themeHost),window.__themeHost).kind,markers:document.querySelectorAll(\"[data-azhou-wallpaper-plane]\").length})');
    assert.deepEqual(clipped.geometry,before);assert.equal(clipped.owner,false);assert.equal(clipped.admission,'unsupported');assert.equal(clipped.markers,0);
    const candidateClip=await capture();
    const max=await cdp.evaluate(`(async()=>{const read=async data=>{const i=new Image();i.src='data:image/png;base64,'+data;await i.decode();const c=document.createElement('canvas');c.width=i.width;c.height=i.height;const x=c.getContext('2d');x.drawImage(i,0,0);return x.getImageData(0,0,c.width,c.height).data;};const a=await read(${JSON.stringify(nativeClip)}),b=await read(${JSON.stringify(candidateClip)});let max=0;for(let i=0;i<a.length;i++)if(i%4!==3)max=Math.max(max,Math.abs(a[i]-b[i]));return max;})()`);
    assert.equal(max,0,'clipped-out native region must not retain theme wash');
    await cdp.evaluate("window.__themeClip.style.overflow='visible'");await settle();
    const restored=await cdp.evaluate('(async()=>{const result=await window.__themeApply(30);const owner=window.__azhouWallpaper;window.__oldThemeOwner.dispose();return {applied:result.themeApplied,sameOwner:window.__azhouWallpaper===owner};})()');
    assert.deepEqual(restored,{applied:true,sameOwner:true});
    await cdp.evaluate('window.__azhouWallpaper.dispose()');
    const initial=await cdp.evaluate(`(async()=>{
      const {installStartup}=await import('/extension/renderer.mjs');
      const {createWallpaperApplicator}=await import('/wallpaper/apply.js');
      const {createObservedRenderer}=await import('/workspace-renderer.mjs');
      const host=window.__themeHost,adapter=window.__themeAdapter,css=await(await fetch('/wallpaper.css')).text();
      let emit;const payload=(_w,_d,_l,_p,_idb,_i,_path,_url,_raf,_caf,_st,_ct,_module,send,spec)=>{emit=(action,fields={})=>send({type:'azhou-startup',action,runId:spec.runId,...fields});return {};};
      const apply=createWallpaperApplicator(createObservedRenderer(host),{version:'0.9.0',css,pageAdapter:adapter},host);
      window.__themeApplyCalls=0;payload.applyWallpaper=(...args)=>{window.__themeApplyCalls++;return apply(...args);};
      const installed=installStartup(payload,host,adapter);if(!installed.installed)throw Error(installed.reason);
      const result=await emit('background',{image:${JSON.stringify(pixelImage)},strength:37,themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value:30}}}});
      emit('ready');emit('complete',{skipped:false});return {result,state:window.__azhouStartup.status()};
    })()`);
    assert.equal(initial.result.themeApplied,true);assert.equal(initial.state.phase,'complete');
    await cdp.evaluate("window.__themeClip.style.overflow='hidden'");
    const failed=await until(()=>cdp.evaluate(`(()=>{const state=window.__azhouStartup.status();const e=document.querySelector('[data-agent-skin-entry="appearance"]'),s=e?.shadowRoot,b=s?.querySelector('[data-agent-skin-wallpaper-retry]'),group=s?.querySelector('[data-agent-skin-wallpaper-recovery]');return state.wallpaper.failureCode==='apply-failed'&&b&&!b.disabled&&group?.style.display!=='none'?{state,calls:window.__themeApplyCalls,label:b.getAttribute('aria-label')}:false;})()`),5000,'bounded theme recovery and visible retry');
    assert.equal(failed.calls,2,'one initial apply and one automatic recovery attempt');assert.ok(failed.label);
    await cdp.evaluate("window.__themeClip.style.overflow='visible'");await settle();
    assert.equal(await cdp.evaluate('window.__themeApplyCalls'),2,'support restoration alone does not start polling');
    const point=await cdp.evaluate(`(()=>{const e=document.querySelector('[data-agent-skin-entry="appearance"]'),b=e.shadowRoot.querySelector('[data-agent-skin-wallpaper-retry]'),r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,hit:e.shadowRoot.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===b};})()`);
    assert.equal(point.hit,true);for(const type of ['mousePressed','mouseReleased'])await cdp.call('Input.dispatchMouseEvent',{type,x:point.x,y:point.y,button:'left',clickCount:1});
    const retried=await until(()=>cdp.evaluate('window.__azhouStartup.status().wallpaper.themeApplied ? {state:window.__azhouStartup.status(),calls:window.__themeApplyCalls} : false'),5000,'actual retry click restores supported theme');
    assert.equal(retried.calls,3);await cdp.evaluate('window.__azhouStartup.dispose()');
    await cdp.call('Emulation.clearDeviceMetricsOverride');
    return {clipped,max,restored,failed,retried,actualRetryClick:true,scope:'synthetic actual owner bounded recovery and explicit user retry; not installed host'};
  });

  await check('theme initial decode is cancelled through the actual startup owner', async()=>{
    await navigate('/fixture.html?legacy-only=1');
    const result=await cdp.evaluate(`(async()=>{
      const {installStartup}=await import('/extension/renderer.mjs');
      const {createCodexPageAdapter}=await import('/extension/codex-page-adapter.mjs');
      const {createWallpaperApplicator}=await import('/wallpaper/apply.js');
      const {createObservedRenderer}=await import('/workspace-renderer.mjs');
      const masks=[],timers=new Set();const NativeImage=window.Image;
      const ImageProbe=function(){const img=new NativeImage(),decode=img.decode.bind(img);img.decode=()=>img.src.startsWith('data:image/svg+xml,')?new Promise(resolve=>masks.push({img,resolve})):decode();return img;};
      let host;host=new Proxy(window,{get(target,key){
        if(['window','top','self','globalThis'].includes(key))return host;
        if(key==='location')return new URL('app://-/index.html');
        if(key==='Image')return ImageProbe;
        if(key==='setTimeout')return (fn,ms)=>{const id=window.setTimeout(fn,ms);if(ms===4000)timers.add(id);return id;};
        if(key==='clearTimeout')return id=>{timers.delete(id);window.clearTimeout(id);};
        const value=Reflect.get(target,key,target);return typeof value==='function'&&['getComputedStyle','addEventListener','removeEventListener','atob','createImageBitmap','matchMedia'].includes(key)?value.bind(target):value;
      }});
      const adapter=createCodexPageAdapter(host),css=await(await fetch('/wallpaper.css')).text();
      let emit;const payload=(_w,_d,_l,_p,_idb,_i,_path,_url,_raf,_caf,_st,_ct,_module,send,spec)=>{emit=(fields)=>send({type:'azhou-startup',action:'background',runId:spec.runId,...fields});return {};};
      payload.applyWallpaper=createWallpaperApplicator(createObservedRenderer(host),{version:'0.9.0',css,pageAdapter:adapter},host);
      const installed=installStartup(payload,host,adapter);if(!installed.installed)throw Error(installed.reason);
      const pending=emit({image:${JSON.stringify(pixelImage)},strength:37,themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value:30}}}});
      for(let i=0;i<100&&!masks.length;i++)await new Promise(r=>window.setTimeout(r,10));
      if(masks.length!==1)throw Error('initial mask not reached '+JSON.stringify({result:await pending,status:window.__azhouStartup.status(),geometry:adapter.readThemeGeometry(adapter.observeWorkspace(host),host)}));
      const disabled=await emit({image:${JSON.stringify(pixelImage)},strength:0});
      const immediate={src:masks[0].img.getAttribute('src'),timers:timers.size};await pending;
      masks[0].resolve();await new Promise(r=>window.setTimeout(r,0));
      const state=window.__azhouStartup.status();window.__azhouStartup.dispose();
      return {disabled,immediate,state,wallpaper:!!window.__azhouWallpaper};
    })()`);
    assert.equal(result.disabled.reason,'disabled');assert.equal(result.immediate.src,'');assert.equal(result.immediate.timers,0);
    assert.equal(result.state.wallpaper.reason,'disabled');assert.equal(result.wallpaper,false);
    await cdp.evaluate('document.querySelector("textarea").focus()');await cdp.call('Input.insertText',{text:'P07 cancelled input'});
    assert.equal(await cdp.evaluate('document.querySelector("textarea").value'),'P07 cancelled input');
    return {...result,actualNativeInput:true,scope:'synthetic generated payload Chrome owner chain'};
  });

  await check('theme-specific CSP denial cleans owned layers and preserves native input', async()=>{
    await navigate('/csp-theme-data.html?legacy-only=1');
    const result=await cdp.evaluate(`(async()=>{
      const {createCodexPageAdapter}=await import('/extension/codex-page-adapter.mjs');
      const {createObservedRenderer}=await import('/workspace-renderer.mjs');
      let host;host=new Proxy(window,{get(target,key){if(['window','top','self','globalThis'].includes(key))return host;if(key==='location')return new URL('app://-/index.html');const value=Reflect.get(target,key,target);return typeof value==='function'&&['getComputedStyle','addEventListener','removeEventListener','setTimeout','clearTimeout','atob','createImageBitmap'].includes(key)?value.bind(target):value;}});
      const adapter=createCodexPageAdapter(host),render=createObservedRenderer(host),css=await(await fetch('/wallpaper.css')).text();
      let code;try{await render({version:'0.9.0',css,image:${JSON.stringify(pixelImage)},imageSHA256:${JSON.stringify(imageSHA256)},strength:37,surface:'#202024',pageAdapter:adapter,workspaceObservation:adapter.observeWorkspace(host),themeState:{schemaVersion:1,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value:30}}}});}catch(e){code=e.code||e.message;}
      return {code,layers:document.querySelectorAll('[data-azhou-theme-layer]').length,marker:document.querySelectorAll('[data-azhou-theme-readability]').length};})()`);
    assert.match(result.code,/theme-mask-decode-failed/);assert.equal(result.layers,0);assert.equal(result.marker,0);
    await cdp.evaluate('document.querySelector("textarea").focus()');
    await cdp.call('Input.insertText',{text:'P07 CSP native input'});
    assert.equal(await cdp.evaluate('document.querySelector("textarea").value'),'P07 CSP native input');
    return {...result,actualNativeInput:true,scope:'isolated synthetic Chrome, not native app'};
  });

  await check('Codex workspace apply cannot attest late auxiliary Dot paint', async () => {
    await navigate('/fixture.html?legacy-only=1');
    const clip = await cdp.evaluate(`(async () => {
      const {createCodexPageAdapter} = await import('/extension/codex-page-adapter.mjs');
      const {createWallpaperApplicator} = await import('/wallpaper/apply.js');
      const {createObservedRenderer} = await import('/workspace-renderer.mjs');
      let host;
      host = new Proxy(window, { get(target, key) {
        if (['window','top','self','globalThis'].includes(key)) return host;
        if (key === 'location') return new URL('app://-/index.html');
        const value = Reflect.get(target,key,target);
        return typeof value === 'function' && ['getComputedStyle','addEventListener','removeEventListener','setTimeout','clearTimeout','atob','createImageBitmap'].includes(key) ? value.bind(target) : value;
      } });
      const adapter = createCodexPageAdapter(host);
      const css = await (await fetch('/wallpaper.css')).text();
      const apply = createWallpaperApplicator(createObservedRenderer(host), {version:'0.9.0',css,pageAdapter:adapter}, host);
      const main = document.querySelector('[data-app-shell-main-surface]');
      const route = document.createElement('section');
      route.style.cssText = 'position:fixed;top:160px;left:480px;width:100px;height:90px;z-index:2';
      const input = document.createElement('textarea');
      input.style.cssText = 'position:absolute;right:0;bottom:0;width:36px;height:24px;background:rgb(26,36,46)';
      route.append(input);
      window.__auxiliaryFixture = {main,route,input,owner:null};
      const result = await apply({image:${JSON.stringify(pixelImage)},strength:37});
      if (!result.applied || result.coverage?.auxiliary !== 'unknown' || result.fullCoverage !== false) {
        throw Error('initial coverage: ' + JSON.stringify(result));
      }
      window.__auxiliaryFixture.owner = window.__azhouWallpaper;
      return {x:484,y:164,width:12,height:12,scale:1};
    })()`);
    const settle = () => cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
    const capture = async () => (await cdp.call('Page.captureScreenshot',{format:'png',fromSurface:true,clip})).data;
    await settle();
    const workspacePixels = await capture();
    await cdp.evaluate(`(() => {
      const {main,route} = window.__auxiliaryFixture;
      route.style.background = 'rgb(11,23,37)';
      main.append(route);
    })()`);
    await settle();
    const auxiliaryPixels = await capture();
    assert.notEqual(auxiliaryPixels, workspacePixels, 'the late opaque route really hides the workspace wallpaper in this clip');
    const result = await cdp.evaluate(`(async () => {
      const {main,route,input,owner} = window.__auxiliaryFixture;
      const i = new Image();
      i.src = 'data:image/png;base64,' + ${JSON.stringify(auxiliaryPixels)};
      await i.decode();
      const c = document.createElement('canvas'); c.width=i.width; c.height=i.height;
      const ctx=c.getContext('2d'); ctx.drawImage(i,0,0);
      const status=owner.status();
      const evidence={pixel:[...ctx.getImageData(0,0,1,1).data],sameOwner:window.__azhouWallpaper===owner,
        sameMain:main===document.querySelector('[data-app-shell-main-surface]'),applied:status.applied,
        auxiliary:status.coverage.auxiliary,fullCoverage:status.fullCoverage,
        routeMark:route.getAttribute('data-azhou-wallpaper-plane'),inputBackground:getComputedStyle(input).backgroundColor};
      route.remove();
      return evidence;
    })()`);
    assert.deepEqual(result, {pixel:[11,23,37,255],sameOwner:true,sameMain:true,applied:true,
      auxiliary:'unknown',fullCoverage:false,routeMark:null,inputBackground:'rgb(26, 36, 46)'});
    await settle();
    assert.equal(await capture(),workspacePixels,'leaving the auxiliary route reveals the same workspace');
  });

  await check('Codex attested Dot wallpaper preserves controls and fails closed', async () => {
    await navigate('/fixture.html?legacy-only=1');
    const clip = await cdp.evaluate(`(async () => {
      const {createCodexPageAdapter} = await import('/extension/codex-page-adapter.mjs');
      const {createWallpaperApplicator} = await import('/wallpaper/apply.js');
      const {createObservedRenderer} = await import('/workspace-renderer.mjs');
      let host;
      host = new Proxy(window, { get(target, key) {
        if (['window','top','self','globalThis'].includes(key)) return host;
        if (key === 'location') return new URL('app://-/index.html');
        const value = Reflect.get(target,key,target);
        return typeof value === 'function' && ['getComputedStyle','addEventListener','removeEventListener','setTimeout','clearTimeout','atob','createImageBitmap'].includes(key) ? value.bind(target) : value;
      } });
      const adapter = createCodexPageAdapter(host);
      const css = await (await fetch('/wallpaper.css')).text();
      const apply = createWallpaperApplicator(createObservedRenderer(host), {version:'0.9.0',css,pageAdapter:adapter}, host);
      const main = document.querySelector('[data-app-shell-main-surface]');
      const route = document.createElement('section');
      route.style.cssText = 'position:fixed;top:160px;left:480px;width:100px;height:90px;z-index:2';
      const input = document.createElement('textarea');
      input.style.cssText = 'position:absolute;right:0;bottom:0;width:36px;height:24px;background:rgb(26,36,46)';
      route.append(input);
      const nav = document.createElement('button');
      nav.dataset.sidebarDestination = 'builtin:orbit';
      nav.style.cssText='position:fixed;left:0;top:0;width:20px;height:20px';
      document.querySelector('#root').append(nav);
      route.className = 'messaging-root messaging-embedded';
      route.innerHTML = '<div class="workspace"><main class="thread-pane"></main></div>';
      const thread = route.querySelector('.thread-pane');
      thread.style.cssText = 'height:90px;width:100px';
      thread.append(input);
      window.__auxiliaryFixture = {main,route,input,nav,apply,owner:null};
      const result = await apply({image:${JSON.stringify(pixelImage)},strength:37});
      if (!result.applied || result.coverage?.auxiliary !== 'unknown' || result.fullCoverage !== false) {
        throw Error('initial coverage: ' + JSON.stringify(result));
      }
      window.__auxiliaryFixture.owner = window.__azhouWallpaper;
      return {x:484,y:164,width:12,height:12,scale:1};
    })()`);
    const settle = () => cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
    const capture = async () => (await cdp.call('Page.captureScreenshot',{format:'png',fromSurface:true,clip})).data;
    await settle();
    const workspacePixels = await capture();
    const set = script => cdp.evaluate(script);
    const stage = async (action, marked, clear) => {
      const evidence = await set(`(async () => {
        const {main,route,input,nav,apply} = window.__auxiliaryFixture;
        ${action}
        await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
        const result=await apply({image:${JSON.stringify(pixelImage)},strength:37});
        const rect = input.getBoundingClientRect();
        input.focus();
        const operable = document.activeElement === input
          && document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2) === input;
        return {applied:result.applied,marked:route.hasAttribute('data-azhou-wallpaper-plane'),
          input:getComputedStyle(input).backgroundColor,operable};
      })()`);
      assert.deepEqual(evidence,{applied:true,marked,input:'rgb(26, 36, 46)',operable:true});
      await settle();
      const pixels=await capture();
      if(clear) assert.equal(pixels,workspacePixels,'Dot shows the same wallpaper pixels');
      else assert.notEqual(pixels,workspacePixels,'unadmitted Dot shape keeps native paint');
    };
    await stage("route.style.background='rgb(11,23,37)'; main.append(route)",false,false);
    await stage("nav.setAttribute('aria-current','page')",true,true);
    await stage("route.setAttribute('data-floating','')",false,false);
    await stage("route.removeAttribute('data-floating')",true,true);
    await stage("const extra=route.cloneNode(true);for(const n of [extra,...extra.querySelectorAll('[data-azhou-wallpaper-plane]')]) n.removeAttribute('data-azhou-wallpaper-plane');extra.id='duplicate-dot';extra.style.pointerEvents='none';main.append(extra)",false,false);
    await stage("const extra=document.getElementById('duplicate-dot');extra.classList.remove('messaging-embedded');extra.style.background='none'",true,true);
    await stage("document.getElementById('duplicate-dot').remove()",true,true);
    const retired=await set(`(async()=>{
      const {nav,route}=window.__auxiliaryFixture;
      nav.removeAttribute('aria-current');
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      return !route.hasAttribute('data-azhou-wallpaper-plane');
    })()`);
    assert.equal(retired,true,'leaving Dot retires the owned marker');
    await stage("nav.setAttribute('aria-current','page')",true,true);
    const restored=await set(`(()=>{
      window.__azhouWallpaper.dispose();
      const {route}=window.__auxiliaryFixture;
      return [route.hasAttribute('data-azhou-wallpaper-plane'), getComputedStyle(route).backgroundColor];
    })()`);
    assert.deepEqual(restored,[false,'rgb(11, 23, 37)']);
  });

  await check('generated Dot wallpaper follows route and shell changes automatically', async () => {
    await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1');
    await awaitGeneratedReady('generated Dot recovery fixture installed');
    await until(()=>cdp.evaluate('window.__azhouWallpaper?.status().applied===true'),10000,'initial generated wallpaper');
    await cdp.evaluate("document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]').click()");
    await until(()=>cdp.evaluate("window.__startupAPI.status().phase==='complete'"),10000,'startup phase complete');
    await cdp.evaluate(`(() => {
      const main = document.querySelector('[data-app-shell-main-surface]');
      const nav = document.createElement('button');
      nav.dataset.sidebarDestination = 'builtin:orbit';
      nav.style.cssText = 'position:fixed;left:0;top:0;width:20px;height:20px';
      document.querySelector('#root').append(nav);
      const make = () => {
        const dot = document.createElement('section');
        dot.className = 'messaging-root messaging-embedded';
        dot.style.cssText = 'position:fixed;top:160px;left:480px;width:100px;height:90px;background:rgb(11,23,37)';
        dot.innerHTML = '<div class="workspace"><main class="thread-pane" style="height:90px"></main></div>';
        return dot;
      };
      const root = document.documentElement;
      const scene = root.style.getPropertyValue('--azhou-wallpaper-image');
      const decode = HTMLImageElement.prototype.decode;
      const revoke = URL.revokeObjectURL;
      const evidence = {decodes: 0, revoked: []};
      const gate = new Promise(resolve => { evidence.release = resolve; });
      HTMLImageElement.prototype.decode = function (...args) {
        evidence.decodes++;
        return Promise.all([decode.apply(this, args), gate]).then(([value]) => value);
      };
      URL.revokeObjectURL = function (value) {
        evidence.revoked.push(value);
        return revoke.call(this, value);
      };
      // Keep the generated image and sizing; remove gradient-wash rounding from the exact pixel oracle.
      const visualProbe = document.createElement('style');
      visualProbe.textContent = 'html[data-azhou-wallpaper="active"] body {'
        + '--azhou-wallpaper-wash:linear-gradient(transparent,transparent)}';
      document.head.append(visualProbe);
      window.__dotRecovery = { main, nav, make, runId:window.__startupAPI.status().runId, dot:make(), scene, evidence };
    })()`);
    const settleFrame = () => cdp.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
    const clip = {x:484,y:164,width:12,height:12,scale:1};
    const captureDot = async () => (await cdp.call('Page.captureScreenshot',{format:'png',fromSurface:true,clip})).data;
    await settleFrame();
    const workspacePixels = await captureDot();
    const settled = (marked, previous='null') => cdp.evaluate(`(() => {
      const current = window.__dotRecovery;
      return current.dot.hasAttribute('data-azhou-wallpaper-plane') === ${marked}
        && (!(${previous}) || !(${previous}).hasAttribute('data-azhou-wallpaper-plane'))
        && window.__startupAPI.status().runId === current.runId
        && window.__startupAPI.status().wallpaper.applied === true;
    })()`);
    const action = script => cdp.evaluate(`(() => { const f=window.__dotRecovery; ${script} })()`);
    await action("f.nav.setAttribute('aria-current','page'); f.main.append(f.dot)");
    await until(()=>settled(true),10000,'late Dot shell receives paint without a second apply');
    const dotPaintIs = expected => cdp.evaluate(`(() => {
      const {dot} = window.__dotRecovery;
      return dot.hasAttribute('data-azhou-wallpaper-plane') === ${expected}
        && getComputedStyle(dot).backgroundColor === (${expected} ? 'rgba(0, 0, 0, 0)' : 'rgb(11, 23, 37)');
    })()`);
    const checkAlias = async (label, edit, painted) => {
      await action(edit);
      // Do not query controller state or synthesize layout events: only the
      // production observer may react to these route/collision mutations.
      await until(()=>dotPaintIs(painted),2500,label);
      await settleFrame();
      const pixels = await captureDot();
      if (painted) assert.equal(pixels,workspacePixels,label+': exact wallpaper ROI');
      else assert.notEqual(pixels,workspacePixels,label+': native surface retains its paint');
      const preserved = await action(`
        const rect=f.input.getBoundingClientRect();
        f.input.focus();
        return {inputColor:getComputedStyle(f.input).backgroundColor, focused:document.activeElement===f.input,
          receivesPointer:document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2)===f.input,
          unrelatedColor:getComputedStyle(f.unrelated).backgroundColor,
          unrelatedMarked:f.unrelated.hasAttribute('data-azhou-wallpaper-plane')};
      `);
      assert.deepEqual(preserved,{inputColor:'rgb(26, 36, 46)',focused:true,receivesPointer:true,
        unrelatedColor:'rgb(91, 32, 73)',unrelatedMarked:false});
    };
    await checkAlias('unsupported prefix relinquishes the old route',`
      f.nav.dataset.sidebarDestination='builtin:dot-hub-extra';
      const input=document.createElement('textarea');
      input.style.cssText='position:absolute;right:4px;bottom:4px;width:36px;height:19px;background:rgb(26,36,46)';
      f.dot.querySelector('.thread-pane').append(input);f.input=input;
      const unrelated=document.createElement('section');
      unrelated.style.cssText='position:fixed;top:280px;left:480px;width:40px;height:30px;background:rgb(91,32,73)';
      f.main.append(unrelated);f.unrelated=unrelated;
    `,false);
    await checkAlias('in-place marker changes to the precise current Dot alias',
      "f.nav.dataset.sidebarDestination='builtin:dot-hub'",true);
    await checkAlias('no active route does not attest Dot',"f.nav.removeAttribute('aria-current')",false);
    await checkAlias('exact active alias attests Dot without layout hints',"f.nav.setAttribute('aria-current','page')",true);
    await checkAlias('hidden inert duplicate marker and shell do not attest or interfere',`
      const skeleton=f.make();skeleton.hidden=true;skeleton.inert=true;skeleton.style.display='none';
      f.main.append(skeleton);f.hiddenShell=skeleton;
      const hidden=f.nav.cloneNode();hidden.hidden=true;hidden.inert=true;hidden.style.display='none';
      f.nav.after(hidden);f.hiddenNav=hidden;
    `,true);
    assert.equal(await action("return f.hiddenShell.hasAttribute('data-azhou-wallpaper-plane')"),false);
    await checkAlias('visible duplicate of the active alias fails closed even when inactive',`
      const duplicate=f.nav.cloneNode();duplicate.removeAttribute('aria-current');f.nav.after(duplicate);f.duplicate=duplicate;
    `,false);
    await checkAlias('an active exact legacy alias conflicts with the current alias',
      "f.duplicate.dataset.sidebarDestination='builtin:orbit';f.duplicate.setAttribute('aria-current','page')",false);
    await checkAlias('an inactive exact legacy alias does not conflict',
      "f.duplicate.removeAttribute('aria-current')",true);
    await checkAlias('exact active legacy route survives an inactive current alias',`
      f.nav.removeAttribute('aria-current');f.duplicate.setAttribute('aria-current','page');
    `,true);
    await checkAlias('cleanup of other rows leaves the original legacy behavior',`
      f.duplicate.remove();f.hiddenNav.remove();f.hiddenShell.remove();
      f.nav.dataset.sidebarDestination='builtin:orbit';f.nav.setAttribute('aria-current','page');
    `,true);

    const checkRoom = async (label, edit, painted) => {
      await checkAlias(label,edit,painted);
      const evidence = await action(`
        const rect=f.input.getBoundingClientRect(); f.input.focus();
        return {shellOwned:f.dot.hasAttribute('data-azhou-wallpaper-plane'),
          shellColor:getComputedStyle(f.dot).backgroundColor,
          paneOwned:f.pane.hasAttribute('data-azhou-wallpaper-plane'),
          paneColor:getComputedStyle(f.pane).backgroundColor,
          nativePanePaint:f.pane.style.backgroundColor,
          editorColor:getComputedStyle(f.editor).backgroundColor,
          editorMarked:f.editor.hasAttribute('data-azhou-wallpaper-plane'),
          editorEditable:f.editor.isContentEditable,
          inputFocused:document.activeElement===f.input,
          inputHit:document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2)===f.input};
      `);
      assert.deepEqual(evidence,{shellOwned:painted,shellColor:painted?'rgba(0, 0, 0, 0)':'rgb(11, 23, 37)',
        paneOwned:true,paneColor:'rgba(0, 0, 0, 0)',nativePanePaint:'rgb(60, 30, 90)',
        editorColor:'rgb(82, 31, 24)',editorMarked:false,editorEditable:true,inputFocused:true,inputHit:true},label);
    };
    await checkRoom('direct complete room control',`
      f.nav.dataset.sidebarDestination='builtin:dot-hub';
      const pane=f.dot.querySelector('.workspace > main.thread-pane');
      pane.style.backgroundColor='rgb(60,30,90)';f.pane=pane;
      const editor=document.createElement('div');
      editor.contentEditable='true';
      editor.style.cssText='position:absolute;left:60px;top:26px;width:19px;height:18px;background:rgb(82,31,24)';
      pane.append(editor);f.editor=editor;
    `,true);
    await checkRoom('one room wrapper does not establish ownership by itself',`
      const outer=document.createElement('div');outer.className='relative flex h-full min-h-0 flex-col';
      f.dot.before(outer);outer.append(f.dot);f.roomOuter=outer;
    `,false);
    await checkRoom('exact host two-wrapper room loses centered wallpaper on current adapter',`
      const inner=document.createElement('div');inner.className='relative min-h-0 flex-1';
      f.roomOuter.insertBefore(inner,f.dot);inner.append(f.dot);f.roomInner=inner;
    `,false);
    await checkRoom('same wrapped room with nested transcript helper still denied',`
      const helper=document.createElement('div');helper.className='messaging-root messaging-embedded';
      helper.style.cssText='position:fixed;top:305px;left:480px;width:20px;height:20px;background:rgb(80,20,60)';
      helper.innerHTML='<div class="thread-pane flex-1">test</div>';
      f.pane.append(helper);f.helper=helper;
    `,false);
    assert.equal(await action("return f.helper.hasAttribute('data-azhou-wallpaper-plane')"),false);
    await checkRoom('the confirmed three-wrapper room admits central wallpaper',`
      f.helper.remove();
      const conversation=document.createElement('div');conversation.className='h-full min-h-0';
      f.roomOuter.before(conversation);conversation.append(f.roomOuter);f.conversation=conversation;
    `,true);
    const assertSameHelperScene = async label => {
      assert.deepEqual(await action(`
        const scene=document.documentElement.style.getPropertyValue('--azhou-wallpaper-image');
        const state=window.__startupAPI.status();
        return {sameScene:!!f.scene&&scene===f.scene,decodes:f.evidence.decodes,
          revoked:f.evidence.revoked,phase:state.phase,sameRun:state.runId===f.runId};
      `),{sameScene:true,decodes:0,revoked:[],phase:'complete',sameRun:true},label);
    };
    await checkRoom('known transcript helper inside three-wrapper room does not compete',`
      const helper=document.createElement('div');helper.className='messaging-root messaging-embedded';
      helper.style.cssText='position:fixed;top:305px;left:480px;width:20px;height:20px;background:rgb(80,20,60)';
      helper.innerHTML='<div class="thread-pane flex-1">test</div>';
      f.pane.append(helper);f.helper=helper;
    `,true);
    await assertSameHelperScene('off-center helper mount retains the decoded scene and completed run');
    await checkRoom('in-flow transcript helper preserves exact central wallpaper pixels',`
      const css = document.createElement('style');
      css.textContent = '#dot-paint-probe.messaging-root {background:var(--color-background-primary);}'
        + '#dot-paint-probe.messaging-embedded {flex-direction:column;width:100%;min-width:0;height:100%;min-height:0;display:flex;position:relative;}'
        + ':where(#dot-paint-probe.messaging-root) .thread-pane {background:var(--color-background-primary);flex-direction:column;min-width:0;min-height:0;display:flex;position:relative;container-type:inline-size;}'
        + '#dot-paint-probe .flex-1 {flex:1}';
      document.head.append(css);
      f.helper.firstElementChild.textContent='';
      f.helper.id='dot-paint-probe';
      f.helper.style.cssText='--color-background-primary:rgb(97,45,62)';
      f.pane.style.display='flex';
      f.pane.style.flexDirection='column';
      f.input.style.zIndex='2';
      const editor=document.createElement('input');
      editor.style.cssText='position:absolute;left:12px;top:52px;box-sizing:border-box;width:20px;height:15px;background:rgb(44,63,89)';
      f.helper.firstElementChild.append(editor);f.helperEditor=editor;
    `,true);
    assert.equal(await action(`
      const rect=f.helper.firstElementChild.getBoundingClientRect();
      return rect.left<=484 && rect.right>=496 && rect.top<=164 && rect.bottom>=176;
    `),true,'center ROI actually intersects the in-flow helper pane');
    assert.deepEqual(await action(`
      return [f.helper,f.helper.firstElementChild].map(node=>[
        node.hasAttribute('data-azhou-wallpaper-plane'),getComputedStyle(node).backgroundColor]);
    `),[[true,'rgba(0, 0, 0, 0)'],[true,'rgba(0, 0, 0, 0)']],'own both attested helper paint planes');
    await assertSameHelperScene('in-flow helper keeps the scene and completed run');
    const assertHelperEditor = async () => {
      assert.deepEqual(await action(`
        const editor=f.helperEditor,rect=editor.getBoundingClientRect();editor.focus();
        return {marked:editor.hasAttribute('data-azhou-wallpaper-plane'),
          color:getComputedStyle(editor).backgroundColor,focused:document.activeElement===editor,
          hit:document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2)===editor};
      `),{marked:false,color:'rgb(44, 63, 89)',focused:true,hit:true});
    };
    await assertHelperEditor();
    await checkRoom('losing route attestation does not mark the nested input or helper',`
      f.nav.removeAttribute('aria-current');
    `,false);
    assert.deepEqual(await action(`
      return [f.helper,f.helper.firstElementChild].map(node=>[
        node.hasAttribute('data-azhou-wallpaper-plane'),getComputedStyle(node).backgroundColor]);
    `),[[false,'rgb(97, 45, 62)'],[false,'rgb(97, 45, 62)']]);
    await assertHelperEditor();
    await checkRoom('restoring route attestation keeps the nested input usable and exact center pixels',`
      f.nav.setAttribute('aria-current','page');
    `,true);
    await assertHelperEditor();
    await checkRoom('hidden helper leaves exact center wallpaper and existing controls intact',`
      f.helper.hidden=true; f.helper.style.display='none';
    `,true);
    await assertSameHelperScene('hiding helper keeps the scene and completed run');
    await checkRoom('showing the same helper restores transparent planes without replay',`
      f.helper.hidden=false; f.helper.style.removeProperty('display');
    `,true);
    await assertSameHelperScene('showing helper keeps the scene and completed run');
    await checkRoom('returning the helper off-center preserves the remaining route guards',`
      f.helperEditor.remove();
      f.helper.removeAttribute('id');
      f.helper.style.cssText='position:fixed;top:305px;left:480px;width:20px;height:20px;background:rgb(80,20,60)';
      f.pane.style.removeProperty('display');f.pane.style.removeProperty('flex-direction');f.input.style.removeProperty('z-index');
    `,true);
    await assertSameHelperScene('returning helper off-center keeps the scene and completed run');
    await action("f.ownerBeforeDrag=window.__azhouWallpaper");
    const stableHelperOwner = () => action("return f.ownerBeforeDrag===window.__azhouWallpaper");
    await checkRoom('host drag-active helper token preserves exact ROI',
      "f.helper.firstElementChild.classList.add('drag-active')",true);
    assert.equal(await stableHelperOwner(),true,'drag-active does not change the paint lease');
    await assertSameHelperScene('drag-active keeps the scene and completed run');
    await checkRoom('host drag-active can clear without repaint',
      "f.helper.firstElementChild.classList.remove('drag-active')",true);
    assert.equal(await stableHelperOwner(),true,'drag-active clear does not change the paint lease');
    await assertSameHelperScene('drag-active clear keeps the scene and completed run');
    await checkRoom('a malformed helper with second child vetoes ownership',`
      const invalid=document.createElement('div');f.helper.append(invalid);f.invalidHelperChild=invalid;
    `,false);
    await checkRoom('removing the old two-token helper root identity restores paint while node remains',
      "f.helper.className='non-dot-helper'",true);
    await checkRoom('restoring the old two-token identity reintroduces malformed ambiguity',
      "f.helper.className='messaging-root messaging-embedded'",false);
    await checkRoom('recovering helper shape restores paint without a new apply',
      "f.invalidHelperChild.remove()",true);
    await checkRoom('populated nested shell is an ambiguity even in the attested room',`
      const workspace=document.createElement('div');workspace.className='workspace';
      workspace.innerHTML='<main class="thread-pane" style="width:20px;height:20px">second</main>';
      f.helper.append(workspace); f.helperWorkspace=workspace;
    `,false);
    await checkRoom('removing nested population admits the safe room again',"f.helperWorkspace.remove()",true);
    await checkRoom('helper losing exact pane class fails closed',
      "f.helper.firstElementChild.classList.remove('flex-1')",false);
    await checkRoom('in-place helper class repair restores automatic paint',
      "f.helper.firstElementChild.classList.add('flex-1')",true);
    await checkRoom('a bare main under the helper pane is not a competing room',`
      const nestedMain=document.createElement('main');
      f.helper.firstElementChild.append(nestedMain);f.nestedMain=nestedMain;
    `,true);
    await checkRoom('class-only nested thread pane withdraws room ownership',
      "f.nestedMain.classList.add('thread-pane')",false);
    await checkRoom('removing only the nested pane class restores exact wallpaper',
      "f.nestedMain.classList.remove('thread-pane')",true);
    await checkRoom('adding a preclassified nested thread pane also withdraws ownership',`
      f.nestedMain.remove();f.nestedMain.className='thread-pane';
      f.helper.firstElementChild.append(f.nestedMain);
    `,false);
    await checkRoom('removing the nested thread pane restores exact wallpaper',"f.nestedMain.remove()",true);
    await action(`
      f.freshHelper=left=>{
        const helper=document.createElement('div');helper.className='messaging-root messaging-embedded';
        helper.style.cssText='position:fixed;top:305px;left:'+left+'px;width:20px;height:20px;background:rgb(80,20,60)';
        helper.innerHTML='<div class="thread-pane flex-1"></div>';
        return helper;
      };
    `);
    const assertNativeHelpers = async other => {
      assert.deepEqual(await action(`
        return [f.helper,f.${other}].map(helper=>[
          helper.hasAttribute('data-azhou-wallpaper-plane'),
          helper.firstElementChild.hasAttribute('data-azhou-wallpaper-plane'),
          getComputedStyle(helper).backgroundColor]);
      `),[[false,false,'rgb(80, 20, 60)'],[false,false,'rgb(80, 20, 60)']]);
    };
    await checkRoom('two identical helper-shaped descendants are ambiguous',`
      const extra=f.freshHelper(520);f.pane.append(extra);f.secondHelper=extra;
    `,false);
    await assertNativeHelpers('secondHelper');
    await checkRoom('removing second helper restores the recognized room',"f.secondHelper.remove()",true);
    await checkRoom('incomplete direct sibling remains an ambiguity beside the attested room',`
      const duplicate=f.freshHelper(530);f.main.append(duplicate);f.competingRoom=duplicate;
    `,false);
    await assertNativeHelpers('competingRoom');
    await checkRoom('removing the incomplete competing shell restores the attested room',
      "f.competingRoom.remove(); f.helper.remove()",true);
    await checkRoom('mutating the innermost wrapper class invalidates recognition',
      "f.roomInner.classList.add('unexpected-wrapper-token')",false);
    await checkRoom('repairing the wrapper classes restores automatic paint',
      "f.roomInner.classList.remove('unexpected-wrapper-token')",true);
    await checkRoom('explicit accessibility-role boundary cannot attest a room',
      "f.roomInner.setAttribute('role','region')",false);
    await checkRoom('removing role from exact wrapper restores automatic paint',
      "f.roomInner.removeAttribute('role')",true);
    await checkRoom('floating outer conversation wrapper cannot attest Dot',
      "f.conversation.setAttribute('data-floating','')",false);
    await action("f.conversation.removeAttribute('data-floating'); f.conversation.hidden=true; f.conversation.style.display='none'");
    await until(()=>action("return !f.dot.hasAttribute('data-azhou-wallpaper-plane')"),2500,'hidden room remains unpainted');
    await settleFrame();
    const hiddenRoom=await action(`
      return {outerMarked:f.dot.hasAttribute('data-azhou-wallpaper-plane'),
        hiddenWrapper:getComputedStyle(f.conversation).display==='none',
        editorColor:getComputedStyle(f.editor).backgroundColor,
        editorMarked:f.editor.hasAttribute('data-azhou-wallpaper-plane')};
    `);
    assert.deepEqual(hiddenRoom,{outerMarked:false,hiddenWrapper:true,editorColor:'rgb(82, 31, 24)',editorMarked:false});
    const hiddenROI=(await captureDot())===workspacePixels;
    assert.equal(hiddenROI,true,'parked hidden room cannot obscure the wallpaper ROI');
    await checkRoom('showing confirmed room again restores ownership',
      "f.conversation.hidden=false; f.conversation.style.removeProperty('display')",true);
    await checkRoom('a per-profile orbit marker outside official navigation is not admitted',
      "f.nav.dataset.sidebarDestination='builtin:orbit:sample-profile'",false);
    await checkRoom('inactive profile in attested native sidebar navigation remains denied',`
      const sidebar=document.querySelector('#app-shell-sidebar')||document.createElement('aside');
      if(!sidebar.isConnected){sidebar.id='app-shell-sidebar';document.querySelector('#root').append(sidebar);}
      const root=document.createElement('div'),nav=document.createElement('nav'),group=document.createElement('div');
      root.setAttribute('data-sidebar-navigation-root','');
      nav.setAttribute('role','navigation');group.className='group/nav-list';
      sidebar.append(root);root.append(nav);nav.append(group);
      f.profileRoot=root;f.profileNav=nav;f.profileGroup=group;
      f.nav.removeAttribute('aria-current');group.append(f.nav);
    `,false);
    await checkRoom('aria-current alone admits the scoped native profile row',
      "f.nav.setAttribute('aria-current','page')",true);
    await checkRoom('removing the sidebar navigation root marker withdraws paint',
      "f.profileRoot.removeAttribute('data-sidebar-navigation-root')",false);
    await checkRoom('restoring only the sidebar navigation root marker recovers paint',
      "f.profileRoot.setAttribute('data-sidebar-navigation-root','')",true);
    await checkRoom('disabling the selected native profile row fails closed',
      "f.nav.disabled=true",false);
    await checkRoom('enabling the same profile row recovers without route replay',
      "f.nav.disabled=false",true);
    await checkRoom('a plain fieldset wrapper preserves the selected native row',`
      const fieldset=document.createElement('fieldset');
      f.profileGroup.append(fieldset);fieldset.append(f.nav);f.profileFieldset=fieldset;
    `,true);
    await checkRoom('native row disabled by its fieldset loses attestation',
      "f.profileFieldset.disabled=true",false);
    assert.deepEqual(await action("return [f.nav.disabled,f.nav.hasAttribute('disabled'),f.nav.matches(':disabled')]"),
      [false,false,true],'fieldset alone makes the mounted button effectively disabled');
    await checkRoom('re-enabling the fieldset restores paint through the observer',
      "f.profileFieldset.disabled=false",true);
    await checkRoom('removing the fieldset keeps the selected native row eligible',
      "f.profileGroup.append(f.nav);f.profileFieldset.remove()",true);
    await checkRoom('native profile row is not evidence within an inert ancestor',
      "f.profileRoot.inert=true",false);
    await checkRoom('clearing inert restores the selected profile row',
      "f.profileRoot.inert=false",true);
    await checkRoom('an editable control cannot attest a profile',
      "f.nav.setAttribute('contenteditable','')",false);
    await checkRoom('clearing editability restores native navigation attestation',
      "f.nav.removeAttribute('contenteditable')",true);
    await checkRoom('composer marker excludes the profile control itself',
      "f.nav.setAttribute('data-composer-layout','')",false);
    await checkRoom('clearing composer marker restores the selected profile',
      "f.nav.removeAttribute('data-composer-layout')",true);
    await checkRoom('a selected profile moved outside the scoped native sidebar is denied',
      "document.querySelector('#root').append(f.nav)",false);
    await checkRoom('moving the same profile back under native navigation restores paint',
      "f.profileGroup.append(f.nav)",true);
    await checkRoom('empty profile suffix cannot attest the right conversation',
      "f.nav.dataset.sidebarDestination='builtin:orbit:'",false);
    await checkRoom('restoring the same selected concrete profile recovers paint',
      "f.nav.dataset.sidebarDestination='builtin:orbit:sample-profile'",true);
    await checkRoom('a visible duplicate of the active profile remains ambiguous',`
      const duplicate=document.createElement('button');
      duplicate.dataset.sidebarDestination='builtin:orbit:sample-profile';
      duplicate.style.cssText='position:fixed;left:27px;top:0;width:20px;height:20px';
      f.profileGroup.append(duplicate);f.profileDuplicate=duplicate;
    `,false);
    await checkRoom('only the remaining selected profile attests after duplicate removal',
      "f.profileDuplicate.remove()",true);
    await checkRoom('aria-current on the profile ancestor alone is not profile evidence',`
      f.nav.removeAttribute('aria-current');f.profileGroup.setAttribute('aria-current','page');
    `,false);
    await action(`
      document.querySelector('#root').append(f.nav);f.profileRoot.remove();
      f.nav.setAttribute('aria-current','page');
    `);
    await checkRoom('restoring exact route and dropping outer wrapper',`
      f.nav.dataset.sidebarDestination='builtin:dot-hub';
      f.main.insertBefore(f.roomOuter,f.conversation);f.conversation.remove();
    `,false);
    await checkRoom('four wrappers do not establish ownership',`
      f.helper.remove();
      const third=document.createElement('div'),fourth=document.createElement('div');
      f.dot.before(third);third.append(fourth);fourth.append(f.dot);f.extraWrappers=third;
    `,false);
    await checkRoom('direct control restores exact centered wallpaper',`
      f.main.insertBefore(f.dot,f.roomOuter);f.roomOuter.remove();
    `,true);
    await checkRoom('second visible complete shell remains ambiguous',`
      const duplicate=f.make();duplicate.style.left='590px';
      f.main.append(duplicate);f.roomDuplicate=duplicate;
    `,false);
    await checkRoom('removing duplicate restores single direct control',"f.roomDuplicate.remove()",true);

    await action("f.dot.firstElementChild.classList.remove('workspace')");
    await until(()=>dotPaintIs(false),2000,'losing the Dot workspace class restores native paint without a status query');
    await action("f.dot.firstElementChild.classList.add('workspace')");
    await until(()=>dotPaintIs(true),2000,'regaining the Dot workspace class restores the attested paint');

    await action("f.previous=f.dot; f.dot=f.make(); f.previous.replaceWith(f.dot)");
    await until(()=>settled(true,'current.previous'),10000,'replacement Dot shell acquires lease');
    await action("f.extra=f.make(); f.main.append(f.extra)");
    await until(()=>settled(false),10000,'duplicate Dot shell is not painted');
    await action("f.extra.classList.remove('messaging-embedded')");
    await until(()=>settled(true),10000,'removing the duplicate class recovers without a second apply');
    await action("f.dot.setAttribute('role','dialog')");
    await until(()=>settled(false),10000,'dynamic protected role restores native paint');
    await action("f.dot.removeAttribute('role')");
    await until(()=>settled(true),10000,'removing the protected role recovers paint');
    await action("f.nav.removeAttribute('aria-current')");
    await until(()=>settled(false),10000,'leaving Dot restores native paint');
    const retained = await action(`
      const root = document.documentElement;
      const state = window.__startupAPI.status();
      f.evidence.release();
      return { sameScene: !!f.scene && f.scene === root.style.getPropertyValue('--azhou-wallpaper-image'),
        decodes: f.evidence.decodes, revoked: f.evidence.revoked, phase: state.phase,
        frames: document.querySelectorAll('iframe[aria-label]').length };
    `);
    assert.deepEqual(retained,{sameScene:true,decodes:0,revoked:[],phase:'complete',frames:0});
    await cdp.evaluate('window.__startupAPI.dispose()');
    assert.equal(await cdp.evaluate("document.querySelectorAll('[data-azhou-wallpaper-plane]').length"),0);
  });

  await check('Codex workspace leases reject batched navigation and retain scoped wallpaper ownership', async () => {
    await navigate('/fixture.html?legacy-only=1');
    const result = await cdp.evaluate(`(async () => {
      const {createCodexPageAdapter} = await import('/extension/codex-page-adapter.mjs');
      const {createWallpaperApplicator} = await import('/wallpaper/apply.js');
      const {createObservedRenderer} = await import('/workspace-renderer.mjs');
      const {bootstrapStartup} = await import('/extension/bootstrap.mjs');
      const observers = new Set();
      let computedReads = 0;
      class TrackedObserver extends MutationObserver {
        constructor(callback) { super(callback); observers.add(this); }
        disconnect() { super.disconnect(); observers.delete(this); }
      }
      class TrackedResizeObserver extends ResizeObserver {
        constructor(callback) { super(callback); observers.add(this); }
        disconnect() { super.disconnect(); observers.delete(this); }
      }
      let host;
      let observedURL = new URL('app://-/index.html');
      host = new Proxy(window, { get(target, key) {
        if (['window','top','self','globalThis'].includes(key)) return host;
        if (key === 'location') return observedURL;
        if (key === 'MutationObserver') return TrackedObserver;
        if (key === 'ResizeObserver') return TrackedResizeObserver;
        if (key === 'getComputedStyle') return (...args) => { computedReads++; return window.getComputedStyle(...args); };
        const value = Reflect.get(target, key, target);
        return ['addEventListener','removeEventListener','setTimeout','clearTimeout','atob','createImageBitmap'].includes(key)
          && typeof value === 'function' ? value.bind(target) : value;
      } });
      const adapter = createCodexPageAdapter(host);
      const main = document.querySelector('[data-app-shell-main-surface]');
      const cached = main.cloneNode(false);
      cached.hidden = true;
      main.before(cached);
      let observed = adapter.observeWorkspace(host);
      const selectsVisible = observed.kind === 'observed' && observed.activeMain === main;
      cached.hidden = false;
      const ambiguous = adapter.observeWorkspace(host).kind === 'ambiguous';
      cached.hidden = true;
      observed = adapter.observeWorkspace(host);
      let invalidated = 0;
      let lease = adapter.watchWorkspace(observed, () => invalidated++, host);
      const prior = main.getAttribute('data-app-shell-main-surface');
      main.removeAttribute('data-app-shell-main-surface');
      main.setAttribute('data-app-shell-main-surface', prior);
      const markerABA = !lease.current() && invalidated === 1;
      observed = adapter.observeWorkspace(host);
      lease = adapter.watchWorkspace(observed, () => invalidated++, host);
      document.documentElement.style.setProperty('--azhou-wallpaper-wash', 'transparent');
      const ownStyleSurvives = lease.current();
      const oldDisplay = document.documentElement.style.display;
      document.documentElement.style.display = 'none';
      document.documentElement.style.display = oldDisplay;
      const rootStyleABA = !lease.current();
      document.documentElement.style.removeProperty('--azhou-wallpaper-wash');
      observed = adapter.observeWorkspace(host);
      lease = adapter.watchWorkspace(observed, () => invalidated++, host);
      const sibling = main.nextSibling;
      const parent = main.parentElement;
      main.remove(); parent.insertBefore(main, sibling);
      const nodeABA = !lease.current();
      observed = adapter.observeWorkspace(host);
      lease = adapter.watchWorkspace(observed, () => invalidated++, host);
      const readsBefore = computedReads;
      const message = main.appendChild(document.createElement('span')); message.remove();
      await Promise.resolve();
      const irrelevantMutationReads = computedReads - readsBefore;
      lease.dispose();
      cached.remove();
      const workspace = main.appendChild(document.createElement('div'));
      workspace.className = 'workspace';
      const thread = workspace.appendChild(document.createElement('main'));
      thread.className = 'thread-pane';
      thread.style.cssText = 'width:100px;height:100px';
      thread.hidden = true;
      observed = adapter.observeWorkspace(host);
      let revealed = false;
      lease = adapter.watchWorkspace(observed, () => { revealed = true; }, host);
      thread.hidden = false;
      await Promise.resolve();
      const revealedPlaneInvalidates = revealed;
      lease.dispose();
      const sheet=document.styleSheets[0];
      const index=sheet.insertRule('.fixture-paint-zero {width:0!important;height:0!important}',sheet.cssRules.length);
      const rule=sheet.cssRules[index];
      thread.classList.add('fixture-paint-zero');
      observed=adapter.observeWorkspace(host);
      let geometryInvalidated=false;
      lease=adapter.watchWorkspace(observed,()=>{geometryInvalidated=true;},host);
      rule.style.setProperty('width','100px','important');rule.style.setProperty('height','100px','important');
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      const geometryPlaneInvalidates=geometryInvalidated;
      lease.dispose(); workspace.remove();
      observed = adapter.observeWorkspace(host);
      let navigated = false;
      lease = adapter.watchWorkspace(observed, () => { navigated = true; }, host);
      observedURL = new URL('app://-/index.html#next');
      window.dispatchEvent(new Event('hashchange'));
      const hashNavigationInvalidates = navigated;
      lease.dispose();
      const css = await (await fetch('/wallpaper.css')).text();
      const render = createObservedRenderer(host);
      const animation = () => {};
      bootstrapStartup({installStartup:()=>{}, installAnimation:animation, createLocalization:()=>{}, createImageSettings:()=>{},
        createWallpaperApplicator, installRenderer:render, version:'0.9.0', css, assets:{}, host, pageAdapter:adapter});
      const applied = await animation.applyWallpaper({image:${JSON.stringify(pixelImage)},strength:37,surface:'#202024'});
      const controller = window.__azhouWallpaper;
      const installed = {applied:applied.applied, fullCoverage:applied.fullCoverage,
        markers:document.querySelectorAll('[data-azhou-wallpaper-plane]').length};
      controller.dispose();
      return {geometryPlaneInvalidates,revealedPlaneInvalidates,hashNavigationInvalidates,selectsVisible,ambiguous,markerABA,ownStyleSurvives,rootStyleABA,nodeABA,irrelevantMutationReads,installed,
        remainingObservers:observers.size, remainingMarkers:document.querySelectorAll('[data-azhou-wallpaper-plane],[data-azhou-wallpaper-pseudo],[data-azhou-wallpaper-decoration]').length};
    })()`);
    assert.equal(result.geometryPlaneInvalidates, true);
    assert.equal(result.revealedPlaneInvalidates, true);
    assert.equal(result.hashNavigationInvalidates, true);
    assert.equal(result.selectsVisible, true);
    assert.equal(result.ambiguous, true);
    assert.equal(result.markerABA, true);
    assert.equal(result.ownStyleSurvives, true);
    assert.equal(result.rootStyleABA, true);
    assert.equal(result.nodeABA, true);
    assert.equal(result.irrelevantMutationReads, 0);
    assert.equal(result.installed.applied, true);
    assert.equal(result.installed.fullCoverage, false);
    assert.ok(result.installed.markers >= 3);
    assert.equal(result.remainingObservers, 0);
    assert.equal(result.remainingMarkers, 0);
    return result;
  });

  await check('generated early Skip preserves pending wallpaper across appearance change', async () => {
    const results=[];
    for (const changeTheme of [false,true]) {
      await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1&hold-decode=1');
      await awaitGeneratedReady('generated ready before wallpaper decode release');
      await until(()=>cdp.evaluate('window.__decodePending===true'),10000,'pending real wallpaper decode');
      const before=await cdp.evaluate('({controller:__startupAPI.status(),gates:__decodeGateCount,owner:!!window.__azhouWallpaper})');
      const point=await cdp.evaluate(`(()=>{const f=document.querySelector('iframe[aria-label]'),b=f.contentDocument.querySelector('[data-agent-skin-skip]'),r=b.getBoundingClientRect(),fr=f.getBoundingClientRect();return {x:fr.x+r.x+r.width/2,y:fr.y+r.y+r.height/2};})()`);
      await cdp.call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
      await cdp.call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
      await until(()=>cdp.evaluate("__startupAPI.status().completion?.cause==='skip'&&!document.querySelector('iframe[aria-label]')"),5000,'actual Skip releases overlay');
      if(changeTheme)await cdp.evaluate("document.documentElement.dataset.theme='light'");
      const skipped=await cdp.evaluate('({controller:__startupAPI.status(),owner:!!window.__azhouWallpaper,theme:document.documentElement.dataset.theme})');
      await cdp.evaluate('window.__releaseDecode()');
      let failure=null;
      try {await until(()=>cdp.evaluate('window.__azhouWallpaper?.status().applied===true&&__startupAPI.status().wallpaper.applied===true'),5000,'pending wallpaper remains valid after Skip');} catch(error){failure=String(error);}
      const after=await cdp.evaluate('({controller:__startupAPI.status(),owner:window.__azhouWallpaper?.status()??null,pending:__decodePending,blobs:__fixtureBlobCount})');
      results.push({changeTheme,before,skipped,after,failure});
    }
    await writeFile(join(options.out,'early-skip-observations.json'),JSON.stringify(results,null,2));
    assert.ok(results.every(r=>!r.failure),'Skip closes startup but must preserve current same-run wallpaper: '+JSON.stringify(results));
    return {results,scope:'generated payload with real gated decode and CDP Skip; synthetic host'};
  });
  await check('generated decode admission cannot outlive cancellation or workspace replacement', async () => {
    const results=[];
    for(const mode of ['already-applied','natural','settings-cancel','unmount','dispose','skip-workspace-replaced']) {
      await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1&hold-decode=1');
      await awaitGeneratedReady('ready with pending scene for '+mode);
      await until(()=>cdp.evaluate('window.__decodePending===true'),10000,'real pending scene');
      const before=await cdp.evaluate('({state:__startupAPI.status(),pending:__decodePending})');
      const click=async selector=>{
        const point=await cdp.evaluate(`(()=>{const f=document.querySelector('iframe[aria-label]'),d=f.contentDocument,b=${selector},r=b.getBoundingClientRect(),fr=f.getBoundingClientRect();b.scrollIntoView({block:'center'});return {x:fr.x+r.x+r.width/2,y:fr.y+r.y+r.height/2};})()`);
        await cdp.call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
        await cdp.call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
      };
      if(['already-applied','natural'].includes(mode)) {
        await cdp.evaluate('__releaseDecode()');await until(()=>cdp.evaluate('window.__azhouWallpaper?.status().applied'),5000,'applied before completion');
        if(mode==='already-applied')await click("d.querySelector('[data-agent-skin-skip]')");
        await until(()=>cdp.evaluate("__startupAPI.status().phase==='complete'"),20000,'completion');
      } else if(mode==='settings-cancel') {
        assert.equal(await cdp.evaluate('__startupAPI.openSettings()'),true);
        await until(()=>cdp.evaluate("!!document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-settings]')"),5000,'settings');
        await click("[...d.querySelectorAll('button')].find(b=>/^(取消|Cancel)$/.test(b.textContent.trim()))");
      } else if(mode==='unmount')await cdp.evaluate("document.querySelector('iframe[aria-label]').remove()");
      else if(mode==='dispose')await cdp.evaluate('__startupAPI.dispose()');
      else {await click("d.querySelector('[data-agent-skin-skip]')");await cdp.evaluate("(()=>{const n=document.querySelector('[data-app-shell-main-surface]');n.replaceWith(n.cloneNode(true));})()");}
      if(!['already-applied','natural'].includes(mode)) {
        await cdp.evaluate('__releaseDecode()');
        await until(()=>cdp.evaluate('!window.__decodePending&&window.__fixtureBlobCount===0'),5000,'released rejected decode');
      }
      const after=await cdp.evaluate('({state:__startupAPI.status(),wallpaper:window.__azhouWallpaper?.status()??null,blobs:__fixtureBlobCount,overlay:!!document.querySelector("iframe[aria-label]")})');
      assert.equal(after.overlay,false,mode+' must release overlay');
      assert.equal(after.wallpaper?.applied===true,['already-applied','natural'].includes(mode),mode);
      results.push({mode,before,after});
    }
    await writeFile(join(options.out,'decode-admission-boundaries.json'),JSON.stringify(results,null,2));
    return {results};
  });
  await check('generated selected theme mask decode preserves only its admitted workspace after Skip', async () => {
    const results=[];
    try {
    for(const replaceWorkspace of [false,true]) {
      await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1');
      await awaitGeneratedReady('theme setup');
      await until(()=>cdp.evaluate('window.__azhouWallpaper?.status().applied'),10000,'setup background');
      await cdp.evaluate("document.querySelector('iframe[aria-label]').contentDocument.querySelector('[data-agent-skin-skip]').click()");
      await until(()=>cdp.evaluate("__startupAPI.status().phase==='complete'"),5000,'setup skip');
      assert.equal(await cdp.evaluate('__startupAPI.openSettings()'),true);
      await until(()=>cdp.evaluate("!!document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-theme-choice]')"),5000,'theme controls');
      await cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]').contentDocument;for(const [sel,val,event] of [['[data-agent-skin-theme-choice]','azhou-q-v3','change'],['[data-agent-skin-theme-alpha-mode]','override','change'],['[data-agent-skin-theme-transparency]','50','input']]){const e=d.querySelector(sel);e.value=val;e.dispatchEvent(new d.defaultView.Event(event,{bubbles:true}));}[...d.querySelectorAll('button')].find(b=>/^(保存|Save)$/.test(b.textContent.trim())).click();})()`);
      await until(()=>cdp.evaluate("!document.querySelector('iframe[aria-label]')&&window.__azhouWallpaper?.status().themeApplied===true"),10000,'saved selected theme');
      await navigate('/fixture.html?generated-payload=1&hold-mask-decode=1');
      await awaitGeneratedReady('selected theme ready before mask decode finishes');
      await until(()=>cdp.evaluate('window.__decodePending===true'),10000,'actual mask gate');
      const before=await cdp.evaluate('({state:__startupAPI.status(),sources:__decodeGateSources,owner:!!window.__azhouWallpaper})');
      assert.equal(before.sources.length,1);assert.ok(before.sources[0].startsWith('data:image/svg+xml,'));
      assert.ok(decodeURIComponent(before.sources[0]).includes('fill-opacity="0.5"'),'gate holds the selected T50 mask, not scene or host color');
      const point=await cdp.evaluate(`(()=>{const f=document.querySelector('iframe[aria-label]'),b=f.contentDocument.querySelector('[data-agent-skin-skip]'),r=b.getBoundingClientRect(),fr=f.getBoundingClientRect();return {x:fr.x+r.x+r.width/2,y:fr.y+r.y+r.height/2};})()`);
      await cdp.call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
      await cdp.call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
      await until(()=>cdp.evaluate("__startupAPI.status().completion?.cause==='skip'&&!document.querySelector('iframe[aria-label]')"),5000,'Skip before mask release');
      if(replaceWorkspace)await cdp.evaluate("(()=>{const n=document.querySelector('[data-app-shell-main-surface]');n.replaceWith(n.cloneNode(true));})()");
      await cdp.evaluate('__releaseDecode()');let failure=null;
      try{await until(()=>cdp.evaluate(replaceWorkspace ? '!window.__azhouWallpaper&&__fixtureBlobCount===0' : 'window.__azhouWallpaper?.status().themeApplied===true'),5000,'admitted mask outcome');}catch(error){failure=String(error);}
      const after=await cdp.evaluate('({state:__startupAPI.status(),owner:window.__azhouWallpaper?.status()??null,pending:__decodePending,blobs:__fixtureBlobCount})');
      results.push({replaceWorkspace,before,after,failure});
    }
    await writeFile(join(options.out,'mask-admission-observations.json'),JSON.stringify(results,null,2));
    assert.ok(results.every(row=>!row.failure),'mask admission boundary failed: '+JSON.stringify(results));return {results};
    } finally {
      await navigateFreshRecoveryFixture('/fixture.html?animation=1&no-initial-wallpaper=1');
      await awaitGeneratedReady('fresh defaults after selected-theme regression');
      const fresh = await cdp.evaluate('({state:__startupAPI.status(),owner:!!window.__azhouWallpaper})');
      await cdp.evaluate('__startupAPI.dispose()');
      await writeFile(join(options.out,'mask-regression-cleanup.json'),JSON.stringify(fresh,null,2));
      assert.equal(fresh.state.wallpaper.reason,'disabled','the regression removes its saved theme and restores fresh defaults');
      assert.equal(fresh.owner,false);
    }
  });

  await check('generated theme fields remain labeled and keyboard operable in narrow layouts', async () => {
    const cells=[];
    try {
      for(const locale of ['zh-CN','en']) for(const theme of ['light','dark']) {
        await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
        await navigateFreshRecoveryFixture('/fixture.html?generated-payload=1&no-initial-wallpaper=1');
        await cdp.evaluate(`document.documentElement.lang=${JSON.stringify(locale)};document.documentElement.dataset.theme=${JSON.stringify(theme)}`);
        await awaitGeneratedReady('theme UI fixture');
        assert.equal(await cdp.evaluate('__startupAPI.openSettings()'),true);
        await until(()=>cdp.evaluate(`document.querySelector('iframe[aria-label]')?.contentDocument.documentElement.lang===${JSON.stringify(locale)}&&!!document.querySelector('iframe[aria-label]')?.contentDocument.querySelector('[data-agent-skin-theme-choice]')`),5000,'localized theme controls');
        const before=await cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]').contentDocument;d.querySelector('[data-agent-skin-settings-tab=workspace]').click();const controls=['choice','alpha-mode','transparency'].map(k=>d.querySelector('[data-agent-skin-theme-'+k+']'));return controls.map(e=>({id:e.id,label:e.labels?.[0]?.textContent.trim()||'',disabled:e.disabled}));})()`);
        assert.deepEqual(before.map(x=>x.label),locale==='en'?['Theme','Reading mask settings','Reading mask transparency']:['主题','阅读遮罩设置','阅读遮罩透明度']);
        assert.equal(before[2].disabled,true);
        await cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]').contentDocument;for(const [key,value,event] of [['choice','azhou-q-v3','change'],['alpha-mode','override','change'],['transparency','50','input']]){const e=d.querySelector('[data-agent-skin-theme-'+key+']');e.value=value;e.dispatchEvent(new d.defaultView.Event(event,{bubbles:true}));}const e=d.querySelector('[data-agent-skin-theme-transparency]');e.scrollIntoView({block:'center'});e.focus();})()`);
        await cdp.call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
        await cdp.call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
        const after=await cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]').contentDocument,dialog=d.querySelector('dialog'),e=d.querySelector('[data-agent-skin-theme-transparency]'),r=e.getBoundingClientRect(),hit=d.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return {value:e.value,readout:d.querySelector('[data-agent-skin-theme-transparency-value]').textContent,aria:e.getAttribute('aria-valuetext'),focus:d.activeElement===e,hit:hit===e,width:r.width,viewport:d.defaultView.innerWidth,overflow:dialog.scrollWidth>dialog.clientWidth+1,strength:d.querySelector('#agent-skin-settings-wallpaper-strength').value,description:e.getAttribute('aria-describedby').split(' ').every(id=>!!d.getElementById(id)),label:d.querySelector('label[for="'+e.id+'"]').getBoundingClientRect().width};})()`);
        assert.equal(after.value,'51');assert.equal(after.readout,'51%');assert.equal(after.aria,'51%');
        assert.ok(after.focus&&after.hit&&after.description&&!after.overflow&&after.width>200&&after.label>0,JSON.stringify(after));
        await dispatchTab(false);
        assert.equal(await cdp.evaluate("document.activeElement===document.querySelector('iframe[aria-label]')"),true);
        await screenshot('theme-fields-'+locale+'-'+theme+'-390.png',{width:390,height:844});
        const restorePoint=await cdp.evaluate(`(()=>{const f=document.querySelector('iframe[aria-label]'),d=f.contentDocument,b=[...d.querySelectorAll('button')].find(e=>/^(恢复全部默认|Restore all defaults)$/.test(e.textContent.trim()));b.scrollIntoView({block:'center'});const r=b.getBoundingClientRect(),fr=f.getBoundingClientRect();return {x:fr.x+r.x+r.width/2,y:fr.y+r.y+r.height/2};})()`);
        await cdp.call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...restorePoint});
        await cdp.call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...restorePoint});
        const restored=await cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]').contentDocument,c=d.querySelector('[data-agent-skin-theme-choice]'),m=d.querySelector('[data-agent-skin-theme-alpha-mode]'),a=d.querySelector('[data-agent-skin-theme-transparency]');c.focus();return {choice:c.value,modeDisabled:m.disabled,alphaDisabled:a.disabled,reason:d.querySelector('[data-agent-skin-theme-transparency-reason]').textContent};})()`);
        assert.equal(restored.choice,'');assert.equal(restored.modeDisabled,true);assert.equal(restored.alphaDisabled,true);
        await dispatchTab(false);
        assert.equal(await cdp.evaluate(`(()=>{const d=document.querySelector('iframe[aria-label]').contentDocument;return d.activeElement.matches('[data-agent-skin-theme-alpha-mode],[data-agent-skin-theme-transparency]');})()`),false);
        cells.push({locale,theme,before,after,restored});
        await cdp.evaluate('__startupAPI.dispose()');
      }
      return {cells};
    } finally {
      await navigateFreshRecoveryFixture('/fixture.html?animation=1&no-initial-wallpaper=1');
      await cdp.evaluate('__startupAPI.dispose()');
      await cdp.call('Emulation.clearDeviceMetricsOverride');
    }
  });

  report.finishedAt = new Date().toISOString();
  report.selectedChecks = options.only;
  const selection = validateCheckSelection(options.only, availableChecks);
  report.missingChecks = selection.missingChecks;
  report.passed = report.checks.some(item => item.passed)
    && report.checks.every(item => item.passed || item.skipped)
    && selection.valid;
  suiteCompleted = true;
} catch (error) {
  report.fatalError = safeError(error);
  if (chromeError && !cdp) report.ownChromeStartupError = chromeError.slice(-1200);
} finally {
  try { await cleanup(); } catch (error) { report.cleanupError = safeError(error); }
  report.finishedAt = new Date().toISOString();
  const selection = validateCheckSelection(options.only, availableChecks);
  report.missingChecks = selection.missingChecks;
  report.passed = !report.fatalError && !report.cleanupError && report.cleanup?.ownChromeStopped
    && report.cleanup.temporaryProfileRemoved && report.cleanup.serverClosed
    && report.checks.some(item => item.passed)
    && report.checks.every(item => item.passed || item.skipped)
    && selection.valid;
  if(measurementOutput)await assertOutputOwner(measurementOutput);
  else await mkdir(options.out, { recursive: true });
  if(measurementRoot){
    report.measurementInputs={before:measurementBefore,collectionStartedAt:measurementStartedAt};
    try{report.measurementInputs.after=await checkpointMeasurement();assert.deepEqual(report.measurementInputs.after.execution,measurementBefore.execution,'execution drift');}
    catch(error){report.measurementInputs.drift=String(error);report.passed=false;}
  }
  await writeFile(join(options.out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  if(measurementRoot)await sealCollection(options.out);
  console.log(JSON.stringify({ passed: report.passed, report: join(options.out, 'report.json'),
    checks: report.checks.map(({ name, passed, skipped, error }) => ({ name, passed, skipped, error })),
    missingChecks: report.missingChecks, fatalError: report.fatalError }));
  if (!report.passed) process.exitCode = 1;
}
