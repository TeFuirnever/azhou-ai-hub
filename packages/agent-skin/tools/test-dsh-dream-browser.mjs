#!/usr/bin/env node
// Synthetic DSH carrier; executes the freshly built client and actual settings iframe.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {spawn,execFileSync} from 'node:child_process';
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
const python=process.env.AZHOU_TEST_PYTHON||'python3';
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
 await until(()=>ev(`(()=>{const d=${panel};return d?.querySelector('[data-agent-skin-dream-import]')&&!d.querySelector('[data-agent-skin-dream-import-button]').disabled})()`),'embedded settings ready');
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
 const capsule=execFileSync(python,['-B','-c',`import io,json,subprocess,sys,zipfile\nfrom pathlib import Path\nfrom PIL import Image\nr=Path(sys.argv[1]);image=io.BytesIO();Image.new('RGB',(24,16),(23,41,79)).save(image,format='PNG')\nz=r/'source.zip'\nwith zipfile.ZipFile(z,'w') as f:\n f.writestr('theme.json',json.dumps({'schemaVersion':1,'id':'dream.dsh.ui','name':'Synthetic DSH UI','image':'background.png'}))\n f.writestr('theme.css','[data-ds-part="main"]{background-color:rgba(120,60,20,.4);}')\n f.writestr('background.png',image.getvalue())\nb=[sys.executable,'-B',sys.argv[2]+'/tools/theme-library.py','--library',str(r/'library')]\nv=json.loads(subprocess.check_output([*b,'import',str(z)]))\nprint(subprocess.check_output([*b,'export-capsule',v['archiveSha256']]).decode())`,out,pkg],{encoding:'utf8'});
 await cdp.call('Emulation.setDeviceMetricsOverride',{width:900,height:900,deviceScaleFactor:1,mobile:false});
 for(const locale of ['en','zh-CN']) for(const width of [390,640]) {
  await ev(`document.documentElement.lang=${JSON.stringify(locale)}`);await delay(100);await open();
  await ev(`document.querySelector('[data-fixture-settings]').style.width='${width}px'`);
  for(const expanded of [false,true]) {
   const geometry=await ev(`(async()=>{const d=${panel},dialog=d.querySelector('[data-agent-skin-settings]');
    for(const detail of d.querySelectorAll('[data-agent-skin-disclosure]'))detail.open=${expanded};
    d.querySelector('[data-agent-skin-dream-section]').scrollIntoView({block:'end'});
    await new Promise(r=>d.defaultView.requestAnimationFrame(()=>d.defaultView.requestAnimationFrame(r)));
    return {width:dialog.clientWidth,scrollWidth:dialog.scrollWidth,text:dialog.innerText};})()`);
   assert.ok(geometry.scrollWidth<=geometry.width+1,'embedded disclosure must not overflow');
   if(!expanded)assert.equal(/CLI|profile|main/.test(geometry.text),false,'technical help stays collapsed');
   assert.ok(geometry.text.includes(locale==='en'?'Import theme':'导入主题'),'embedded host locale follows');
   await writeFile(join(out,`appearance-${locale}-${width}-${expanded?'expanded':'collapsed'}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
   report.checks.push({appearance:{locale,width,expanded,overflow:false}});
  }
  await close();
 }
 await ev(`document.documentElement.lang='en'`);await delay(100);await open();
 const globalObject=await cdp.call('Runtime.evaluate',{expression:'globalThis'});
 const imported=await cdp.call('Runtime.callFunctionOn',{objectId:globalObject.result.objectId,
  functionDeclaration:`function(capsule){const d=document.querySelector('[data-fixture-settings] iframe[aria-label]').contentDocument,
   w=d.defaultView,input=d.querySelector('[data-agent-skin-dream-import]'),t=new w.DataTransfer();
   t.items.add(new w.File([capsule],'dsh.json',{type:'application/json'}));input.files=t.files;input.dispatchEvent(new w.Event('change',{bubbles:true}));}`,
  arguments:[{value:capsule}],returnByValue:true});
 assert.equal(imported.exceptionDetails,undefined);
 await until(()=>ev(`(()=>{const d=${panel};return d.querySelector('[data-agent-skin-dream-list]').options.length===1&&!d.querySelector('[data-agent-skin-dream-apply]').disabled})()`),'imported');
 assert.equal(await ev('window.__azhouWallpaper.status().mainPaintApplied===true'),false);report.checks.push({importStoredWithoutApplying:true});
 await ev(`(${panel}).querySelector('[data-agent-skin-dream-apply]').click()`);
 await until(()=>ev(`window.__azhouWallpaper?.status().mainPaintApplied===true&&!(${panel}).querySelector('[data-agent-skin-dream-apply]').disabled`),'applied');
 const applied=await ev(`({color:getComputedStyle(document.querySelector('.fixture_mainPanel')).backgroundColor,status:__azhouWallpaper.status()})`);assert.equal(applied.color,'rgba(120, 60, 20, 0.4)');report.checks.push({applied});
 await close();await open();assert.equal(await ev(`(${panel}).querySelector('[data-agent-skin-dream-restore]').disabled`),false);report.checks.push({reopenRetainsApplied:true});
 await ev(`(${panel}).querySelector('[data-agent-skin-dream-restore]').click()`);
 await until(()=>ev(`window.__azhouWallpaper?.status().applied===true&&!document.querySelector('[data-azhou-dream-main]')&&(${panel}).querySelector('[data-agent-skin-dream-restore]').disabled`),'restored');
 report.checks.push({restored:await ev(`({color:getComputedStyle(document.querySelector('.fixture_mainPanel')).backgroundColor,status:__azhouWallpaper.status()})`)});
 await writeFile(join(out,'restored.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await close();await open();await ev(`(${panel}).querySelector('[data-agent-skin-dream-apply]').click()`);
 await until(()=>ev(`window.__azhouWallpaper?.status().mainPaintApplied===true&&!(${panel}).querySelector('[data-agent-skin-dream-apply]').disabled`),'reapply before navigation');await close();
 await ev(`(()=>{const old=document.querySelector('[data-slot=main]');window.__oldMain=old;window.__paintPlane=old.parentElement;old.replaceWith(old.cloneNode(true));})()`);await delay(300);
 const navigation=await ev(`({owner:window.__azhouWallpaper?.status(),mainColor:getComputedStyle(document.querySelector('.fixture_mainPanel')).backgroundColor,marker:document.querySelector('.fixture_mainPanel').getAttribute('data-azhou-dream-main'),oldMarker:__paintPlane.getAttribute('data-azhou-dream-main'),startup:__azhouStartup.status()})`);assert.equal(navigation.owner,undefined,'replaced main must lose its old owner');assert.equal(navigation.oldMarker,null);assert.equal(navigation.marker,null);assert.equal(navigation.mainColor,'rgba(0, 0, 0, 0)','paint plane must lose imported color');report.checks.push({mainReplacement:navigation});
 await cdp.call('Page.reload');await until(()=>ev('window.__azhouWallpaper?.status().mainPaintApplied===true'),'reload persisted Dream paint');
 assert.equal(await ev(`getComputedStyle(document.querySelector('.fixture_mainPanel')).backgroundColor`),'rgba(120, 60, 20, 0.4)');report.checks.push({reloadPersisted:true});await skipStartup();
 await open();await ev(`(${panel}).querySelector('[data-agent-skin-dream-restore]').click()`);await until(()=>ev(`window.__azhouWallpaper?.status().applied===true&&!document.querySelector('[data-azhou-dream-main]')&&(${panel}).querySelector('[data-agent-skin-dream-restore]').disabled`),'final restore');await close();report.passed=true;
}catch(e){report.passed=false;report.error=String(e.stack||e);if(cdp)try{report.state=await ev(`({startup:window.__azhouStartup?.status(),wallpaper:window.__azhouWallpaper?.status(),text:(${panel})?.body.innerText})`)}catch{};process.exitCode=1}
finally{
 cdp?.close();const stopped=await chromeOwner.stop();server.closeAllConnections();await new Promise(r=>server.close(r));
 report.cleanup={ownChromeStopped:stopped,temporaryProfileRemoved:false};
 if(stopped&&report.passed)report.cleanup.temporaryProfileRemoved=await removeOwnedProfile(profile,profileOwner);
 if(!stopped||report.passed&&!report.cleanup.temporaryProfileRemoved){report.passed=false;process.exitCode=1;}
 if(!report.cleanup.temporaryProfileRemoved)report.profile=profile;
 report.stderr=stderr.slice(-1000);await writeFile(join(out,'result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
