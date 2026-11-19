#!/usr/bin/env node
// Synthetic DSH carrier; executes the freshly built client and actual settings iframe.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {tmpdir} from 'node:os';
import {join,dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {CDP} from './test-startup-browser-cdp.mjs';
import {trackOwnedChild,profileIdentity,removeOwnedProfile} from './test-startup-browser-process.mjs';
const pkg=resolve(dirname(fileURLToPath(import.meta.url)),'..');
if(process.argv.length!==4||process.argv[2]!=='--out')throw Error('Usage: node test-dsh-dream-browser.mjs --out NEW_DIRECTORY');
const out=resolve(process.argv[3]);await mkdir(dirname(out),{recursive:true});await mkdir(out);
const code=await readFile(join(pkg,'.build/azhou-dsh-plugin/azhou-agent-skin/client.js'),'utf8');
const report={scope:'actual generated DSH client.js and embedded mountSettings iframe in isolated Chrome; observed display:contents host shape, mocked module loader and Cordis effects, synthetic dialog rather than React; not native DSH acceptance',clientSha256:createHash('sha256').update(code).digest('hex'),checks:[]};
const html=`<!doctype html><html lang="en"><head><style>html,body,#root{margin:0;width:100%;height:100%}.fixture_mainPanel{height:100vh;display:flex;flex-direction:column}main{display:contents}.hero{flex:1}</style></head><body><div id="root"><div class="fixture_mainPanel"><div data-slot="main" style="display:contents"><main><div class="hero"><textarea aria-label="test draft"></textarea></div></main></div></div></div><script>window.__DSH_BOOT__={};window.__effects=[];window.__ModuleLoader__={load(spec){const plugin=spec.factory(name=>{throw Error('synthetic platform has no '+name)});window.__plugin=plugin;window.__result=plugin.apply({effect(fn){const cleanup=fn();__effects.push(cleanup);return cleanup},slots:null})}};</script><script src="/client.js"></script></body></html>`;
const server=createServer((req,res)=>{res.setHeader('content-type',req.url==='/client.js'?'text/javascript; charset=utf-8':'text/html; charset=utf-8');res.end(req.url==='/client.js'?code:html)});await new Promise(r=>server.listen(0,'127.0.0.1',r));
const profile=await mkdtemp(join(tmpdir(),'azhou-dsh-generated-ui-'));
const profileOwner=await profileIdentity(profile);
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe']});const chromeOwner=trackOwnedChild(chrome);let stderr='';chrome.stderr.on('data',b=>stderr+=b);
let cdp;async function until(fn,label,timeout=20000){const end=Date.now()+timeout;let last;while(Date.now()<end){try{const v=await fn();if(v)return v}catch(e){last=e}await delay(60)}throw Error(label+': '+(last||'timeout'))}
const ev=x=>cdp.evaluate(x), panel=`document.querySelector('[data-fixture-settings] iframe[aria-label]')?.contentDocument`;
async function open(){
 assert.equal(await ev(`(()=>{
  const slot=document.createElement('div');slot.setAttribute('role','dialog');slot.setAttribute('data-fixture-settings','');
  slot.style.cssText='position:fixed;inset:20px 20px 20px auto;width:480px;z-index:2147483647;background:white';document.body.appendChild(slot);
  window.__fixtureClose=()=>{window.__fixtureDispose?.();window.__fixtureDispose=null;slot.remove();};
  window.__fixtureDispose=__azhouStartup.mountSettings(slot,{onClose:()=>window.__fixtureClose()});return typeof __fixtureDispose==='function';
 })()`),true);
 await until(()=>ev(`(()=>{const d=${panel};return d?.querySelector('[data-agent-skin-preset-import]')&&d.querySelector('[data-agent-skin-image-input=artwork]')})()`),'embedded settings ready');
}
async function close(){await ev('window.__fixtureClose()');await until(()=>ev(`!document.querySelector('[data-fixture-settings]')`),'host dialog closed')}
async function skipStartup(){await ev(`document.querySelector('iframe[aria-label]')?.contentDocument?.querySelector('[data-agent-skin-skip]')?.click()`);}

try{
 const port=Number((await until(async()=>await readFile(join(profile,'DevToolsActivePort'),'utf8'),'Chrome endpoint')).split('\n')[0]);
 const pages=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();cdp=await CDP.open(pages[0].webSocketDebuggerUrl,port);await cdp.call('Page.enable');
 await cdp.call('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/`});
 await until(()=>ev('window.__azhouStartup?.status().phase==="prepared"'),'generated startup ready');
 await until(()=>ev('window.__azhouWallpaper?.status().applied'),'initial wallpaper');
 await skipStartup();
 report.checks.push({initial:await ev('__azhouStartup.status()')});
 await cdp.call('Emulation.setDeviceMetricsOverride',{width:900,height:900,deviceScaleFactor:1,mobile:false});
 for(const locale of ['en','zh-CN']) for(const width of [390,640]) {
  await ev(`document.documentElement.lang=${JSON.stringify(locale)}`);await delay(100);await open();
  await ev(`document.querySelector('[data-fixture-settings]').style.width='${width}px'`);
  for(const expanded of [false,true]) {
   const geometry=await ev(`(async()=>{const d=${panel},dialog=d.querySelector('[data-agent-skin-settings]');
    for(const detail of d.querySelectorAll('[data-agent-skin-disclosure]'))detail.open=${expanded};
    d.querySelector('[data-agent-skin-disclosure=presets]').scrollIntoView({block:'end'});
    await new Promise(r=>d.defaultView.requestAnimationFrame(()=>d.defaultView.requestAnimationFrame(r)));
    return {width:dialog.clientWidth,scrollWidth:dialog.scrollWidth,text:dialog.innerText,
     foreign:['section','import','list','apply','restore'].filter(key=>d.querySelector('[data-agent-skin-dream-'+key+']'))};})()`);
   assert.ok(geometry.scrollWidth<=geometry.width+1,'embedded disclosure must not overflow');
   if(!expanded)assert.equal(/CLI|profile|main/.test(geometry.text),false,'technical help stays collapsed');
   assert.deepEqual(geometry.foreign,[],'no external appearance controls in either locale');
   await writeFile(join(out,`appearance-${locale}-${width}-${expanded?'expanded':'collapsed'}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
   report.checks.push({appearance:{locale,width,expanded,overflow:false}});
  }
  await close();
 }
 await until(()=>ev('window.__azhouWallpaper?.status().applied'),'wallpaper survives reopening Appearance');
 report.passed=true;
}catch(e){report.passed=false;report.error=String(e.stack||e);if(cdp)try{report.state=await ev(`({startup:window.__azhouStartup?.status(),wallpaper:window.__azhouWallpaper?.status(),text:(${panel})?.body.innerText})`)}catch{};process.exitCode=1}
finally{
 cdp?.close();const stopped=await chromeOwner.stop();server.closeAllConnections();await new Promise(r=>server.close(r));
 report.cleanup={ownChromeStopped:stopped,temporaryProfileRemoved:false};
 if(stopped&&report.passed)report.cleanup.temporaryProfileRemoved=await removeOwnedProfile(profile,profileOwner);
 if(!stopped||report.passed&&!report.cleanup.temporaryProfileRemoved){report.passed=false;process.exitCode=1;}
 if(!report.cleanup.temporaryProfileRemoved)report.profile=profile;
 report.stderr=stderr.slice(-1000);await writeFile(join(out,'result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
