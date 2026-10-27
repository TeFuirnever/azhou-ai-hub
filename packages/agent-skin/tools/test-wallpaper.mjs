#!/usr/bin/env node
// One-shot fixture checks. Uses a fresh, temporary Chrome profile, never Codex
// or an existing browser. Requires Node with built-in fetch and WebSocket.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const options = { chrome: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', image: 'wallpaper-scene-q-v3.png',
  out: join(ROOT, '.local/evidence/wallpaper-fixture-' + new Date().toISOString().replace(/[:.]/g, '-')) };
for (let i = 2; i < process.argv.length; i++) {
  const key = process.argv[i];
  if (key === '--help') {
    console.log('node tools/test-wallpaper.mjs [--chrome /path/to/Chrome] [--image private-file.png] [--out /path/to/evidence] [--baseline-dir /path/to/source-before]');
    process.exit(0);
  }
  if (!['--chrome', '--image', '--out', '--baseline-dir'].includes(key) || !process.argv[i + 1]) throw new Error('Unknown/missing argument: ' + key);
  options[key.slice(2)] = process.argv[++i];
}
if (!/^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:png|webp)$/i.test(options.image)) throw new Error('Expected a private PNG/WebP filename, without directories');
options.chrome = resolve(options.chrome);
options.out = resolve(options.out);
if (options['baseline-dir']) options.baselineDir = resolve(options['baseline-dir']);
const report = { schema: 1, scope: 'synthetic Codex-like DOM in isolated headless Chrome; not actual Codex validation',
  startedAt: new Date().toISOString(), checks: [], screenshots: [],
  limitations: ['No official Codex process, profile or user content is accessed.',
    'The fixture reproduces inspected shell anchors; actual application DOM and visual acceptance remain separate.',
    'CSP checks cover image and style enforcement after a CDP evaluation, not script-src injection permissions.',
    'Screenshots are visual evidence, not performance measurements; no GPU/pipeline performance claim.',
    'Cover fills the viewport by cropping; computed coverage does not certify character proportions, face visibility or text readability.',
    'Source pixels, screenshot pixels and calculated upscale are reported separately; no native-Retina-resolution claim.'] };
let server, chrome, profile, cdp, chromeError = '', stopping = false;

function safeError(error) {
  return String(error?.message || error).replace(/data:image\/[^\s"']+/g, '[private image omitted]').slice(0, 1800);
}
async function until(operation, milliseconds = 10000, label = 'condition') {
  const deadline = Date.now() + milliseconds;
  let last;
  do {
    try { const value = await operation(); if (value) return value; } catch (error) { last = error; }
    await delay(80);
  } while (Date.now() < deadline);
  throw new Error('Timed out waiting for ' + label + (last ? ': ' + safeError(last) : ''));
}
async function check(name, operation) {
  const start = Date.now();
  try { const details = await operation(); report.checks.push({ name, passed: true, elapsedMs: Date.now() - start, details }); }
  catch (error) { report.checks.push({ name, passed: false, elapsedMs: Date.now() - start, error: safeError(error) }); }
}
class CDP {
  constructor(socket) {
    this.socket = socket; this.nextID = 1; this.pending = new Map();
    socket.addEventListener('message', event => {
      const value = JSON.parse(String(event.data));
      if (!value.id || !this.pending.has(value.id)) return;
      const pending = this.pending.get(value.id); this.pending.delete(value.id); clearTimeout(pending.timer);
      value.error ? pending.reject(new Error(value.error.message)) : pending.resolve(value.result);
    });
    socket.addEventListener('close', () => {
      for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(new Error('Fixture CDP closed')); }
      this.pending.clear();
    });
  }
  static async open(address, expectedPort) {
    const url = new URL(address);
    assert.equal(url.protocol, 'ws:'); assert.equal(url.hostname, '127.0.0.1'); assert.equal(Number(url.port), expectedPort);
    assert.ok(url.pathname.startsWith('/devtools/page/'));
    const socket = new WebSocket(address);
    await new Promise((resolveOpen, reject) => {
      const timer = setTimeout(() => { socket.close(); reject(new Error('Fixture WebSocket timeout')); }, 5000);
      socket.addEventListener('open', () => { clearTimeout(timer); resolveOpen(); }, { once: true });
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Fixture WebSocket failed')); }, { once: true });
    });
    return new CDP(socket);
  }
  call(method, params = {}) {
    const id = this.nextID++;
    return new Promise((resolveCall, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error('Fixture CDP timeout: ' + method)); }, 12000);
      this.pending.set(id, { resolve: resolveCall, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, timeout: 10000 });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  }
  close() { this.socket.close(); }
}

async function cleanup() {
  if (stopping) return;
  stopping = true;
  try { cdp?.close(); } catch {}
  if (chrome && chrome.exitCode === null && chrome.signalCode === null) {
    const exited = new Promise(resolveExit => chrome.once('exit', resolveExit));
    chrome.kill('SIGTERM');
    await Promise.race([exited, delay(2500)]);
    if (chrome.exitCode === null && chrome.signalCode === null) { chrome.kill('SIGKILL'); await Promise.race([exited, delay(1500)]); }
  }
  if (server) { server.closeAllConnections(); await new Promise(resolveClose => server.close(resolveClose)); }
  if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 4, retryDelay: 100 });
  report.cleanup = { ownChromeStopped: !chrome || chrome.exitCode !== null || chrome.signalCode !== null,
    temporaryProfileRemoved: !!profile, serverClosed: !server?.listening };
}
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => { cleanup().finally(() => process.exit(signal === 'SIGINT' ? 130 : 143)); });
}

try {
  assert.equal(typeof WebSocket, 'function', 'Use Node 22+ with its built-in WebSocket; no package install is needed');
  await access(options.chrome);
  await mkdir(options.out, { recursive: true });
  const [renderer, css, preview, imageBytes] = await Promise.all([
    readFile(join(ROOT, 'wallpaper/renderer.js'), 'utf8'), readFile(join(ROOT, 'wallpaper/wallpaper.css'), 'utf8'),
    readFile(join(ROOT, 'wallpaper/preview.html'), 'utf8'), readFile(join(ROOT, 'assets/private', options.image)),
  ]);
  const imageSHA256 = createHash('sha256').update(imageBytes).digest('hex');
  const mime = options.image.toLowerCase().endsWith('.webp') ? 'image/webp' : 'image/png';
  const payload = { version: '0.7.1', preview: true, css, imageSHA256, image: 'data:' + mime + ';base64,' + imageBytes.toString('base64') };
  const installer = renderer.replace(/^export\s+(?=async function installRenderer)/m, '');
  assert.ok(!/^export\s/m.test(installer), 'Renderer must expose one self-contained function');
  const installExpression = '(async()=>{' + installer + '\nreturn await installRenderer(' + JSON.stringify(payload) + ');})()';
  report.input = { image: options.image, imageSHA256, imageBytes: imageBytes.length,
    rendererSHA256: createHash('sha256').update(renderer).digest('hex'), cssSHA256: createHash('sha256').update(css).digest('hex') };
  // Optional captured source proves the old false success using its actual bytes.
  let baseline;
  if (options.baselineDir) {
    const [oldRenderer, oldCSS] = await Promise.all([
      readFile(join(options.baselineDir, 'wallpaper/renderer.js'), 'utf8'),
      readFile(join(options.baselineDir, 'wallpaper/wallpaper.css'), 'utf8'),
    ]);
    const version = /const VERSION = '([^']+)'/.exec(oldRenderer)?.[1];
    assert.equal(version, '0.7.0');
    baseline = { installer: oldRenderer.replace(/^export\s+(?=async function installRenderer)/m, ''), payload: { ...payload, version, css: oldCSS } };
    report.baseline = { version, rendererSHA256: createHash('sha256').update(oldRenderer).digest('hex'), cssSHA256: createHash('sha256').update(oldCSS).digest('hex') };
  }
  const baseCSS = 'html{--color-surface:#202024}body{margin:0;background:#202024}#root,[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]{min-height:300px;background:#202024}';
  const bareFixture = '<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/fixture-base.css"></head><body><div id="root"><div data-app-shell-frame><main data-app-shell-main-surface="default"><section data-app-shell-page-surface>Local fixture only</section></main></div></div></body></html>';
  const allowedPolicy = "default-src 'none'; img-src data: blob:; style-src 'self' 'unsafe-inline'; script-src 'none'; connect-src 'none'; base-uri 'none'; object-src 'none'";
  const routes = new Map([
    ['/wallpaper/preview.html', ['text/html; charset=utf-8', preview]],
    ['/wallpaper/renderer.js', ['text/javascript; charset=utf-8', renderer]],
    ['/wallpaper/wallpaper.css', ['text/css; charset=utf-8', css]],
    ['/assets/private/' + options.image, [mime, imageBytes]],
    ['/fixture-base.css', ['text/css; charset=utf-8', baseCSS]],
    ['/csp-allow.html', ['text/html; charset=utf-8', bareFixture, allowedPolicy]],
    ['/csp-no-inline-style.html', ['text/html; charset=utf-8', bareFixture, allowedPolicy.replace("style-src 'self' 'unsafe-inline'", "style-src 'self'")]],
    ['/csp-no-blob.html', ['text/html; charset=utf-8', bareFixture, allowedPolicy.replace('img-src data: blob:', 'img-src data:')]],
  ]);
  server = createServer((request, response) => {
    const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
    const route = routes.get(decodeURIComponent(pathname));
    if (!route) { response.writeHead(404); response.end('Unknown fixture route'); return; }
    response.setHeader('Content-Type', route[0]); response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff'); if (route[2]) response.setHeader('Content-Security-Policy', route[2]);
    response.end(route[1]);
  });
  await new Promise((resolveListen, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveListen); });
  const origin = 'http://127.0.0.1:' + server.address().port;
  profile = await mkdtemp(join(tmpdir(), 'azhou-wallpaper-fixture-'));
  const chromeArgs = ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
    '--disable-default-apps', '--disable-sync', '--disable-extensions', '--disable-component-update', '--no-pings',
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', '--user-data-dir=' + profile, '--window-size=1512,889', 'about:blank'];
  chrome = spawn(options.chrome, chromeArgs, { stdio: ['ignore', 'ignore', 'pipe'] });
  chrome.on('error', error => { chromeError = safeError(error); });
  chrome.stderr.on('data', chunk => { chromeError = (chromeError + chunk.toString()).slice(-6000); });
  const debugPort = await until(async () => {
    if (chrome.exitCode !== null || chrome.signalCode !== null) throw new Error('Own Chrome exited: ' + chromeError);
    const file = await readFile(join(profile, 'DevToolsActivePort'), 'utf8');
    const port = Number(file.split('\n')[0]); assert.ok(port > 0 && port < 65536); return port;
  }, 15000, 'own Chrome DevToolsActivePort');
  const endpoint = 'http://127.0.0.1:' + debugPort;
  const fetchJSON = async path => { const response = await fetch(endpoint + path, { signal: AbortSignal.timeout(2000) }); assert.ok(response.ok); return response.json(); };
  const browser = await fetchJSON('/json/version');
  const page = await until(async () => (await fetchJSON('/json/list')).find(target => target.type === 'page' && target.url === 'about:blank'), 5000, 'own blank page');
  cdp = await CDP.open(page.webSocketDebuggerUrl, debugPort);
  await cdp.call('Page.enable'); await cdp.call('Runtime.enable');
  report.environment = { node: process.version, platform: process.platform, chromeExecutable: options.chrome,
    chromePID: chrome.pid, browser: browser.Browser, protocolVersion: browser['Protocol-Version'], isolatedTemporaryProfile: true,
    debugPortPolicy: 'port 0 is used only for the disposable headless fixture; not an assertion about the official app' };
  async function navigate(path) {
    const result = await cdp.call('Page.navigate', { url: origin + path });
    assert.ok(!result.errorText, result.errorText);
    await until(() => cdp.evaluate('location.href===' + JSON.stringify(origin + path) + '&&document.readyState==="complete"'), 10000, 'fixture page load');
  }
  async function dimensions(width, height) {
    await cdp.call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 2, mobile: false });
    await cdp.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  }
  async function screenshot(name) {
    await cdp.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
    const viewport = await cdp.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,theme:document.documentElement.dataset.theme})');
    const result = await cdp.call('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
    const bytes = Buffer.from(result.data, 'base64');
    assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10], 'Screenshot must be a PNG');
    const pixels = { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
    assert.equal(pixels.width, Math.round(viewport.width * viewport.dpr));
    assert.equal(pixels.height, Math.round(viewport.height * viewport.dpr));
    await writeFile(join(options.out, name), bytes);
    const metadata = { file: name, ...viewport, pixels };
    report.screenshots.push(metadata);
    return metadata;
  }
  async function onFixture(operation, ...args) {
    return cdp.evaluate('(' + operation.toString() + ')(' + args.map(value => JSON.stringify(value)).join(',') + ')');
  }
  await dimensions(1512, 889);
  await navigate('/wallpaper/preview.html?image=' + encodeURIComponent(options.image));
  await until(() => cdp.evaluate('(()=>{if(globalThis.__wallpaperFixtureError)throw new Error(__wallpaperFixtureError);return !!globalThis.__wallpaperFixture && !!globalThis.__azhouWallpaper?.status().applied;})()'), 10000, 'decoded fixture wallpaper');
  if (baseline) {
    await check('captured 0.7.0 falsely reports success with independent fades', async () => {
      try {
        await cdp.evaluate('__azhouWallpaper.dispose()');
        const state = await cdp.evaluate('(async()=>{' + baseline.installer + '\nreturn await installRenderer(' + JSON.stringify(baseline.payload) + ');})()');
        const inspected = await onFixture(() => {
          const fade = document.getElementById('fixture-fade');
          return { inFooter: !!fade.closest('[data-thread-scroll-footer]'), gradient: getComputedStyle(fade).backgroundImage,
            height: fade.getBoundingClientRect().height, topGradient: getComputedStyle(document.querySelector('._MainContentTopFade_fixture')).backgroundImage };
        });
        assert.equal(state.applied, true); assert.equal(state.footerBackgroundClear, true);
        assert.equal(inspected.inFooter, false); assert.equal(inspected.height, 32);
        assert.ok(inspected.gradient.includes('linear-gradient')); assert.ok(inspected.topGradient.includes('linear-gradient'));
        await onFixture(() => { document.getElementById('result').textContent = '0.7.0 基线：状态成功，但独立渐变仍覆盖背景'; });
        return { state, inspected, screenshot: await screenshot('00-baseline-fade-0.7.0.png') };
      } finally { await cdp.evaluate('__wallpaperFixture.apply()'); }
    });
  }
  await check('decoded image and matched shell/background', async () => {
    const status = await cdp.evaluate('__azhouWallpaper.status()');
    assert.equal(status.applied, true); assert.equal(status.imageDecoded, true); assert.equal(status.backgroundMatched, true);
    assert.equal(status.coverMatched, true); assert.equal(status.fixedViewport, true); assert.equal(status.image.displayMode, 'cover');
    assert.ok(status.image.width > status.image.height, 'Full scene must decode as a landscape image');
    assert.ok(status.matchedSurfaces >= 3); assert.equal(status.transparentSurfaces, status.matchedSurfaces);
    assert.equal(status.footerFadeSurfaces, 1); assert.equal(status.topFadeSurfaces, 1);
    assert.equal(status.footerFadeClear, true); assert.equal(status.topFadeClear, true);
    assert.equal(status.decorationEffectsClear, true); assert.deepEqual(status.unsupportedDecorations, []);
    assert.equal(status.imageSHA256, imageSHA256); assert.equal(status.persistentAnimation, false); return status;
  });
  await check('full-scene cover and screenshot dimensions in wide/narrow dark/light views', async () => {
    const views = [];
    try {
      for (const [width, height, theme, file] of [
        [1512, 889, 'dark', '01-dark-1512.png'], [1512, 889, 'light', '02-light-1512.png'],
        [840, 900, 'dark', '03-dark-840.png'], [840, 900, 'light', '04-light-840.png'],
      ]) {
        await dimensions(width, height);
        await cdp.evaluate('document.documentElement.dataset.theme=' + JSON.stringify(theme));
        const view = await cdp.evaluate(`(()=>{
          const layers=value=>{let depth=0,start=0;const out=[];for(let i=0;i<value.length;i++){
            if(value[i]==='(')depth++;else if(value[i]===')')depth--;
            else if(value[i]===','&&depth===0){out.push(value.slice(start,i).trim());start=i+1;}
          }out.push(value.slice(start).trim());return out;};
          const style=getComputedStyle(document.body),state=__azhouWallpaper.status();
          const images=layers(style.backgroundImage),imageIndex=images.findIndex(value=>value.startsWith('url(')&&value.includes('blob:'));
          const valueAt=name=>{const values=layers(style[name]);return imageIndex<0?null:values[imageIndex%values.length];};
          const scale=Math.max(innerWidth/state.image.width,innerHeight/state.image.height);
          const rendered={width:state.image.width*scale,height:state.image.height*scale};
          return {width:innerWidth,height:innerHeight,dpr:devicePixelRatio,theme:document.documentElement.dataset.theme,state,
            imageIndex,size:valueAt('backgroundSize'),attachment:valueAt('backgroundAttachment'),repeat:valueAt('backgroundRepeat'),
            position:valueAt('backgroundPosition'),rendered,sourceToDevicePixelScale:scale*devicePixelRatio,
            croppedCSSPixels:{horizontal:Math.max(0,rendered.width-innerWidth),vertical:Math.max(0,rendered.height-innerHeight)}};
        })()`);
        assert.equal(view.width, width); assert.equal(view.height, height); assert.equal(view.theme, theme);
        assert.equal(view.state.applied, true); assert.equal(view.state.coverMatched, true); assert.equal(view.state.fixedViewport, true);
        assert.equal(view.state.image.displayMode, 'cover'); assert.equal(view.state.footerBackgroundClear, true);
        assert.equal(view.state.footerFadeClear, true); assert.equal(view.state.topFadeClear, true); assert.equal(view.state.decorationEffectsClear, true);
        assert.ok(view.imageIndex >= 0); assert.equal(view.size, 'cover'); assert.equal(view.attachment, 'fixed'); assert.equal(view.repeat, 'no-repeat');
        assert.ok(view.rendered.width + 0.01 >= width && view.rendered.height + 0.01 >= height, 'Cover must fill both viewport axes');
        views.push({ ...view, screenshot: await screenshot(file) });
      }
    } finally {
      await dimensions(1512, 889);
      await cdp.evaluate('document.documentElement.dataset.theme="dark"');
    }
    return views;
  });
  await check('non-cover candidate is rejected without replacing the working wallpaper', async () => {
    const result = await cdp.evaluate(`(async()=>{
      const saved=__azhouWallpaper;let rejected=false;
      try {await __wallpaperFixture.installRenderer({...__wallpaperFixture.payload,
        css:__wallpaperFixture.payload.css+' html[data-azhou-wallpaper="active"] body {background-size:contain!important;}'});}
      catch {rejected=true;}
      const state=__azhouWallpaper.status();
      return {rejected,sameAPI:__azhouWallpaper===saved,applied:state.applied,coverMatched:state.coverMatched,
        fixedViewport:state.fixedViewport,styleCount:document.querySelectorAll('#azhou-wallpaper-style').length};
    })()`);
    assert.deepEqual(result, { rejected: true, sameAPI: true, applied: true, coverMatched: true, fixedViewport: true, styleCount: 1 });
    return result;
  });
  await check('real thread footer plate: clear backgrounds, intact composer, failure and restore', async () => {
    const result = await cdp.evaluate(`(async()=>{
      const originalTheme=document.documentElement.dataset.theme, results=[];
      const plate=document.querySelector('[data-thread-scroll-footer] > ._background_fixture');
      const footer=plate.parentElement, composer=document.querySelector('.composer');
      const sample=()=>{
        const r=composer.getBoundingClientRect(), s=getComputedStyle(plate);
        return {plate:s.backgroundColor,plateImage:s.backgroundImage,footer:getComputedStyle(footer).backgroundColor,
          composer:{background:getComputedStyle(composer).backgroundColor,x:r.x,y:r.y,width:r.width,height:r.height,pointerEvents:getComputedStyle(composer).pointerEvents},
          code:getComputedStyle(document.querySelector('pre')).backgroundColor,
          button:getComputedStyle(composer.querySelector('button')).backgroundColor};
      };
      try {
        for(const theme of ['dark','light']) {
          __azhouWallpaper.dispose();document.documentElement.dataset.theme=theme;
          const before=sample();await __wallpaperFixture.apply();const applied=sample(),state=__azhouWallpaper.status();
          plate.style.setProperty('background-color','var(--color-surface)','important');
          const blocked=__azhouWallpaper.status();plate.style.removeProperty('background-color');
          const recovered=__azhouWallpaper.status();
          const saved=__azhouWallpaper;let rejected=false;
          try { await __wallpaperFixture.installRenderer({...__wallpaperFixture.payload,
            css:__wallpaperFixture.payload.css+' html[data-azhou-wallpaper="active"] #root [data-app-shell-main-surface] [data-thread-scroll-footer] > div._background_fixture {background-color:#202024!important;}'}); }
          catch { rejected=true; }
          const rollback={rejected,sameAPI:__azhouWallpaper===saved,applied:__azhouWallpaper.status().applied,plate:sample().plate};
          __azhouWallpaper.dispose();const restored=sample();
          results.push({theme,before,applied,state,blocked,recovered,rollback,restored});
          await __wallpaperFixture.apply();
        }
      } finally {plate.style.removeProperty('background-color');document.documentElement.dataset.theme=originalTheme;}
      return results;
    })()`);
    for (const item of result) {
      assert.notEqual(item.before.plate, 'rgba(0, 0, 0, 0)', 'fixture must reproduce the opaque native footer');
      assert.equal(item.applied.plate, 'rgba(0, 0, 0, 0)'); assert.equal(item.applied.plateImage, 'none');
      assert.equal(item.applied.footer, 'rgba(0, 0, 0, 0)');
      assert.equal(item.state.footerSurfaces, 2); assert.equal(item.state.footerBackgroundClear, true); assert.equal(item.state.applied, true);
      assert.deepEqual(item.applied.composer, item.before.composer); assert.equal(item.applied.composer.pointerEvents, 'auto');
      assert.equal(item.applied.code, item.before.code); assert.equal(item.applied.button, item.before.button);
      assert.equal(item.blocked.applied, false); assert.equal(item.blocked.footerBackgroundClear, false);
      assert.equal(item.recovered.applied, true); assert.equal(item.recovered.footerBackgroundClear, true);
      assert.deepEqual(item.rollback, { rejected: true, sameAPI: true, applied: true, plate: 'rgba(0, 0, 0, 0)' });
      assert.deepEqual(item.restored, item.before);
    }
    return result;
  });
  await check('independent footer and top fades: clearing, rollback and restore', async () => {
    const results = await onFixture(async () => {
      const html = document.documentElement, themeBefore = html.dataset.theme;
      const fade = document.getElementById('fixture-fade');
      const top = document.querySelector('._MainContentTopFade_fixture');
      const sample = () => {
        const f = getComputedStyle(fade), r = fade.getBoundingClientRect();
        return { inFooter: !!fade.closest('[data-thread-scroll-footer]'),
          fade: { image: f.backgroundImage, background: f.backgroundColor, height: r.height, x: r.x, y: r.y, width: r.width },
          topImage: getComputedStyle(top).backgroundImage,
          protected: { composer: getComputedStyle(document.querySelector('.composer')).backgroundColor,
            editorMask: getComputedStyle(document.querySelector('.fixture-editor')).maskImage,
            code: getComputedStyle(document.querySelector('pre')).backgroundColor,
            menu: getComputedStyle(document.querySelector('.fixture-menu')).backgroundColor,
            menuShadow: getComputedStyle(document.querySelector('.fixture-menu')).boxShadow } };
      };
      const results = [];
      try {
        for (const theme of ['dark', 'light']) {
          __azhouWallpaper.dispose(); html.dataset.theme = theme;
          const before = sample(); await __wallpaperFixture.apply();
          const after = sample(), state = __azhouWallpaper.status();
          const blocked = [];
          for (const [name, node] of [['footer', fade], ['top', top]]) {
            try {
              node.style.setProperty('background-image', 'linear-gradient(#181818,transparent)', 'important');
              blocked.push({ name, state: __azhouWallpaper.status() });
            } finally { node.style.removeProperty('background-image'); }
          }
          const saved = __azhouWallpaper; let rejected = false;
          try { await __wallpaperFixture.installRenderer({ ...__wallpaperFixture.payload,
            css: __wallpaperFixture.payload.css + ' html[data-azhou-wallpaper="active"] #root#root #fixture-fade {background-image:linear-gradient(#181818,transparent)!important;}' }); }
          catch { rejected = true; }
          const rollback = { rejected, sameAPI: saved === __azhouWallpaper, applied: __azhouWallpaper.status().applied };
          __azhouWallpaper.dispose(); const restored = sample();
          results.push({ theme, before, after, state, blocked, rollback, restored });
          await __wallpaperFixture.apply();
        }
      } finally {
        fade.style.removeProperty('background-image'); top.style.removeProperty('background-image'); html.dataset.theme = themeBefore;
        if (!globalThis.__azhouWallpaper) await __wallpaperFixture.apply();
      }
      return results;
    });
    for (const item of results) {
      assert.equal(item.before.inFooter, false); assert.equal(item.before.fade.height, 32);
      assert.ok(item.before.fade.image.includes('linear-gradient')); assert.ok(item.before.topImage.includes('linear-gradient'));
      assert.equal(item.after.fade.image, 'none'); assert.equal(item.after.topImage, 'none');
      for (const key of ['x', 'y', 'width', 'height']) assert.equal(item.after.fade[key], item.before.fade[key]);
      assert.deepEqual(item.after.protected, item.before.protected); assert.notEqual(item.after.protected.editorMask, 'none');
      assert.equal(item.state.applied, true); assert.equal(item.state.footerFadeSurfaces, 1); assert.equal(item.state.topFadeSurfaces, 1);
      assert.equal(item.state.footerFadeClear, true); assert.equal(item.state.topFadeClear, true);
      for (const blocked of item.blocked) {
        assert.equal(blocked.state.applied, false);
        assert.equal(blocked.state[blocked.name === 'footer' ? 'footerFadeClear' : 'topFadeClear'], false);
      }
      assert.deepEqual(item.rollback, { rejected: true, sameAPI: true, applied: true });
      assert.deepEqual(item.restored, item.before);
    }
    return results;
  });
  await check('decorative effects and selector drift cannot produce false success', async () => {
    const result = await onFixture(() => {
      const fade = document.getElementById('fixture-fade'), holder = fade.parentElement, failures = [];
      const inject = (name, operation, undo) => {
        try {
          operation();
          failures.push({ name, state: __azhouWallpaper.status(),
            pseudoBackgroundImage: name === 'pseudo' ? getComputedStyle(fade, '::before').backgroundImage : null });
        } finally { undo(); }
      };
      inject('shadow', () => fade.style.setProperty('box-shadow', '0 -8px 14px #000', 'important'), () => fade.style.removeProperty('box-shadow'));
      inject('backdrop', () => fade.style.setProperty('backdrop-filter', 'brightness(.4)', 'important'), () => fade.style.removeProperty('backdrop-filter'));
      const pseudo = document.createElement('style');
      pseudo.textContent = '#root#root #fixture-fade::before{content:"";position:absolute;inset:0;background-image:linear-gradient(#181818,#181818)!important;}';
      inject('pseudo', () => document.head.appendChild(pseudo), () => pseudo.remove());
      const classes = holder.className; let drift;
      try { holder.classList.remove('sticky', 'bottom-0'); drift = { state: __azhouWallpaper.status(), image: getComputedStyle(fade).backgroundImage }; }
      finally { holder.className = classes; }
      return { failures, drift, recovered: __azhouWallpaper.status() };
    });
    assert.ok(result.failures.find(failure => failure.name === 'pseudo').pseudoBackgroundImage.includes('linear-gradient'),
      'The pseudo-element fault must still be painting after the wallpaper CSS cascade');
    for (const failure of result.failures) { assert.equal(failure.state.applied, false, failure.name); assert.equal(failure.state.decorationEffectsClear, false); }
    assert.ok(result.drift.image.includes('linear-gradient')); assert.equal(result.drift.state.applied, false);
    assert.ok(result.drift.state.unsupportedDecorations.length > 0);
    assert.equal(result.recovered.applied, true); assert.deepEqual(result.recovered.unsupportedDecorations, []);
    return result;
  });
  await check('dynamic branches, multi-line composer, scrolling and focus', async () => {
    const result = await onFixture(async () => {
      const fade = document.getElementById('fixture-fade'), holder = fade.parentElement;
      const route = holder.cloneNode(true), routeFade = route.firstElementChild;
      routeFade.id = 'fixture-route-fade'; routeFade.className = '_background_route _fade_route pointer-events-none absolute inset-x-0 z-0';
      routeFade.style.cssText = 'position:absolute;inset-inline:0;top:-32px;height:32px;background-image:linear-gradient(#181818,transparent);pointer-events:none';
      holder.before(route);
      const inserted = { state: __azhouWallpaper.status(), image: getComputedStyle(routeFade).backgroundImage }; route.remove();
      const removed = __azhouWallpaper.status();
      const layout = document.querySelector('.fixture-thread-layout'), scroll = document.querySelector('.thread-scroll-container');
      const textarea = document.querySelector('textarea'), composer = document.querySelector('.composer');
      const original = { height: layout.style.getPropertyValue('--fixture-composer-height'), value: textarea.value, scrollTop: scroll.scrollTop, focus: document.activeElement };
      const filler = document.createElement('div'); filler.style.height = '1200px'; document.querySelector('.reading-area').appendChild(filler);
      try {
        layout.style.setProperty('--fixture-composer-height', '220px');
        textarea.value = ['第一行：本地模拟', '第二行：输入检查', '第三行：布局检查'].join(String.fromCharCode(10));
        textarea.focus(); scroll.scrollTop = 200; await new Promise(resolve => requestAnimationFrame(resolve));
        const r = textarea.getBoundingClientRect();
        return { inserted, removed, typing: { state: __azhouWallpaper.status(), focused: document.activeElement === textarea,
          hit: document.elementFromPoint(r.x + 10, r.y + 10) === textarea, scrollTop: scroll.scrollTop,
          composerHeight: composer.getBoundingClientRect().height, composerBackground: getComputedStyle(composer).backgroundColor,
          editorMask: getComputedStyle(document.querySelector('.fixture-editor')).maskImage,
          fadeImage: getComputedStyle(fade).backgroundImage, fadeHeight: fade.getBoundingClientRect().height } };
      } finally {
        filler.remove(); textarea.value = original.value; scroll.scrollTop = original.scrollTop;
        if (original.height) layout.style.setProperty('--fixture-composer-height', original.height); else layout.style.removeProperty('--fixture-composer-height');
        if (original.focus?.isConnected && typeof original.focus.focus === 'function') original.focus.focus();
      }
    });
    assert.equal(result.inserted.state.applied, true); assert.equal(result.inserted.state.footerFadeSurfaces, 2); assert.equal(result.inserted.image, 'none');
    assert.equal(result.removed.footerFadeSurfaces, 1); assert.equal(result.removed.applied, true);
    assert.equal(result.typing.state.applied, true); assert.equal(result.typing.focused, true); assert.equal(result.typing.hit, true);
    assert.ok(result.typing.scrollTop > 0); assert.ok(result.typing.composerHeight > 180);
    assert.notEqual(result.typing.composerBackground, 'rgba(0, 0, 0, 0)'); assert.notEqual(result.typing.editorMask, 'none');
    assert.equal(result.typing.fadeImage, 'none'); assert.equal(result.typing.fadeHeight, 32);
    return result;
  });

  await check('fixture built-in lifecycle/rollback checks', () => cdp.evaluate('__wallpaperFixture.runChecks()').then(result => { assert.equal(result.passed, true); return result; }));
  await check('scoped surface tokens, composer, code and input remain intact', async () => {
    const result = await cdp.evaluate(`(async()=>{
      __azhouWallpaper.dispose();
      const sample=()=>({token:getComputedStyle(document.documentElement).getPropertyValue('--color-surface'),
        composer:getComputedStyle(document.querySelector('.composer')).backgroundColor,
        code:getComputedStyle(document.querySelector('pre')).backgroundColor,
        children:document.body.querySelectorAll('*').length});
      const before=sample(); await __wallpaperFixture.apply(); const after=sample();
      const textarea=document.querySelector('textarea'); textarea.focus(); textarea.value='fixture input remains editable';
      const rect=textarea.getBoundingClientRect(); const hit=document.elementFromPoint(rect.x+10,rect.y+10);
      return {before,after,focused:document.activeElement===textarea,hit:hit===textarea};
    })()`);
    assert.deepEqual(result.before, result.after); assert.equal(result.focused, true); assert.equal(result.hit, true); return result;
  });
  await check('status verifies wallpaper strength and restore preserves later host changes', async () => {
    const result = await cdp.evaluate(`(async()=>{
      __azhouWallpaper?.dispose();
      const root=document.documentElement, imageName='--azhou-wallpaper-image', washName='--azhou-wallpaper-wash';
      const before={attribute:root.getAttribute('data-azhou-wallpaper'),
        image:root.style.getPropertyValue(imageName),imagePriority:root.style.getPropertyPriority(imageName),
        wash:root.style.getPropertyValue(washName),washPriority:root.style.getPropertyPriority(washName)};
      await __wallpaperFixture.installRenderer({...__wallpaperFixture.payload,strength:75});
      const high=__azhouWallpaper.status(), firstWash=root.style.getPropertyValue(washName);
      __azhouWallpaper.dispose();
      await __wallpaperFixture.installRenderer({...__wallpaperFixture.payload,strength:21});
      const lower=__azhouWallpaper.status(), secondWash=root.style.getPropertyValue(washName);
      const owned=__azhouWallpaper, style=document.getElementById('azhou-wallpaper-style');
      root.setAttribute('data-azhou-wallpaper','host-later');
      root.style.setProperty(imageName,'host-image','important');
      root.style.setProperty(washName,'host-wash','important');
      style.textContent+='\\n/* host update */';
      owned.dispose();
      const after={attribute:root.getAttribute('data-azhou-wallpaper'),
        image:root.style.getPropertyValue(imageName),imagePriority:root.style.getPropertyPriority(imageName),
        wash:root.style.getPropertyValue(washName),washPriority:root.style.getPropertyPriority(washName),
        styleStillConnected:style.isConnected,styleWasChanged:style.textContent.includes('host update'),
        globalStillOwned:!!globalThis.__azhouWallpaper};
      style.remove();
      if(before.attribute===null)root.removeAttribute('data-azhou-wallpaper');else root.setAttribute('data-azhou-wallpaper',before.attribute);
      for(const [name,value,priority] of [[imageName,before.image,before.imagePriority],[washName,before.wash,before.washPriority]]){
        if(value)root.style.setProperty(name,value,priority);else root.style.removeProperty(name);
      }
      await __wallpaperFixture.apply();
      return {high:{applied:high.applied,imageDecoded:high.imageDecoded,washMatched:high.washMatched},
        lower:{applied:lower.applied,washMatched:lower.washMatched},differentWash:firstWash!==secondWash,after};
    })()`);
    assert.deepEqual(result.high, { applied: true, imageDecoded: true, washMatched: true });
    assert.deepEqual(result.lower, { applied: true, washMatched: true }); assert.equal(result.differentWash, true);
    assert.deepEqual(result.after, { attribute: 'host-later', image: 'host-image', imagePriority: 'important',
      wash: 'host-wash', washPriority: 'important', styleStillConnected: true, styleWasChanged: true, globalStillOwned: false });
    return result;
  });
  await check('unknown wallpaper owner and version remain untouched', async () => {
    const result = await cdp.evaluate(`(async()=>{
      __azhouWallpaper?.dispose();
      let disposeCount=0;
      const unknown={owner:'azhou.codex-startup-animation',version:'0.7.0',status(){return {applied:true};},dispose(){disposeCount++;}};
      globalThis.__azhouWallpaper=unknown;
      let rejected=false,error='';
      try{await __wallpaperFixture.installRenderer(__wallpaperFixture.payload);}
      catch(value){rejected=true;error=String(value.message);}
      const outcome={rejected,error,sameOwner:globalThis.__azhouWallpaper===unknown,disposeCount,
        styleCount:document.querySelectorAll('#azhou-wallpaper-style').length};
      delete globalThis.__azhouWallpaper;
      await __wallpaperFixture.apply();
      return outcome;
    })()`);
    assert.equal(result.rejected, true); assert.ok(result.error.includes('namespace-conflict'));
    assert.deepEqual({ sameOwner: result.sameOwner, disposeCount: result.disposeCount, styleCount: result.styleCount },
      { sameOwner: true, disposeCount: 0, styleCount: 0 });
    return result;
  });
  await check('repeat apply / bad updates / dispose: bounded Blob and no resize listeners', async () => {
    const result = await cdp.evaluate(`(async()=>{
      __azhouWallpaper.dispose();
      const original={make:URL.createObjectURL,revoke:URL.revokeObjectURL,add:window.addEventListener,remove:window.removeEventListener};
      const urls=new Set(),listeners=new Set();
      URL.createObjectURL=function(value){const url=original.make.call(URL,value);urls.add(url);return url;};
      URL.revokeObjectURL=function(url){urls.delete(url);return original.revoke.call(URL,url);};
      window.addEventListener=function(type,fn,...args){if(type==='resize')listeners.add(fn);return original.add.call(this,type,fn,...args);};
      window.removeEventListener=function(type,fn,...args){if(type==='resize')listeners.delete(fn);return original.remove.call(this,type,fn,...args);};
      try{
        for(let i=0;i<4;i++) await __wallpaperFixture.apply();
        const before={urls:urls.size,listeners:listeners.size,styles:document.querySelectorAll('#azhou-wallpaper-style').length};
        const saved=__azhouWallpaper,failed=[];
        for(const candidate of [{...__wallpaperFixture.payload,image:'data:image/png;base64,aW52YWxpZA=='},
          {...__wallpaperFixture.payload,css:__wallpaperFixture.payload.css.replace('--azhou-style-ready: ready','--azhou-style-ready: blocked')}]){
          let rejected=false;try{await __wallpaperFixture.installRenderer(candidate);}catch{rejected=true;}
          failed.push({rejected,sameAPI:globalThis.__azhouWallpaper===saved,applied:saved.status().applied,urls:urls.size,listeners:listeners.size});
        }
        saved.dispose();saved.dispose();
        return {before,failed,after:{urls:urls.size,listeners:listeners.size,styles:document.querySelectorAll('#azhou-wallpaper-style').length,global:!!globalThis.__azhouWallpaper}};
      }finally{globalThis.__azhouWallpaper?.dispose();URL.createObjectURL=original.make;URL.revokeObjectURL=original.revoke;window.addEventListener=original.add;window.removeEventListener=original.remove;}
    })()`);
    assert.deepEqual(result.before, { urls: 1, listeners: 0, styles: 1 });
    for (const failure of result.failed) assert.deepEqual(failure, { rejected: true, sameAPI: true, applied: true, urls: 1, listeners: 0 });
    assert.deepEqual(result.after, { urls: 0, listeners: 0, styles: 0, global: false }); return result;
  });
  for (const [path, expected, errorClass] of [
    ['/csp-allow.html', true, null], ['/csp-no-inline-style.html', false, 'styles-not-effective'], ['/csp-no-blob.html', false, 'image-decode-failed'],
  ]) {
    await check('CSP ' + path.slice(1, -5), async () => {
      await navigate(path);
      const outcome = await cdp.evaluate('(async()=>{try{return {ok:true,status:await ' + installExpression + '};}catch(error){return {ok:false,error:String(error.message),styleCount:document.querySelectorAll("#azhou-wallpaper-style").length,global:!!globalThis.__azhouWallpaper};}})()');
      assert.equal(outcome.ok, expected);
      if (expected) { assert.equal(outcome.status.applied, true); await cdp.evaluate('__azhouWallpaper.dispose()'); }
      else { assert.ok(outcome.error.includes(errorClass)); assert.equal(outcome.styleCount, 0); assert.equal(outcome.global, false); }
      return outcome;
    });
  }
  await check('production payload refuses fixture URL without explicit preview flag', async () => {
    await navigate('/csp-allow.html');
    const expression = '(async()=>{' + installer + '\ntry{await installRenderer(' + JSON.stringify({ ...payload, preview: false }) + ');return {rejected:false};}catch(error){return {rejected:true,error:String(error.message),styleCount:document.querySelectorAll("#azhou-wallpaper-style").length};}})()';
    const outcome = await cdp.evaluate(expression);
    assert.equal(outcome.rejected, true); assert.ok(outcome.error.includes('unexpected-page')); assert.equal(outcome.styleCount, 0); return outcome;
  });
} catch (error) {
  report.fatalError = safeError(error);
  if (chromeError && !cdp) report.ownChromeStartupError = chromeError.slice(-1800);
} finally {
  try { await cleanup(); } catch (error) { report.cleanupError = safeError(error); }
  report.finishedAt = new Date().toISOString();
  report.passed = !report.fatalError && !report.cleanupError && report.cleanup?.ownChromeStopped
    && report.cleanup.temporaryProfileRemoved && report.cleanup.serverClosed
    && report.checks.length > 0 && report.checks.every(item => item.passed);
  await mkdir(options.out, { recursive: true });
  await writeFile(join(options.out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ passed: report.passed, report: join(options.out, 'report.json'), checks: report.checks.map(({name,passed}) => ({name,passed})), fatalError: report.fatalError }));
  if (!report.passed) process.exitCode = 1;
}
