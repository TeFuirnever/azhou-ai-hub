import test from 'node:test';
import assert from 'node:assert/strict';
import { createZCodePageAdapter } from '../extension/hosts/zcode.mjs';
const base='file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html';
function host(url=base){const h={location:{href:url},indexedDB:{own:true},crypto:{randomUUID:()=>'synthetic-page-nonce'}};h.top=h;return h;}
test('constructor stores only, matches installed top-level main page',()=>{
 const h=host(base+'?restoreSession=false&zcodeLaunchMarks=synthetic');const a=createZCodePageAdapter(h);
 assert.equal(a.identify().kind,'matched');assert.equal(a.identify().documentToken,'synthetic-page-nonce');assert(!a.identify().documentToken.includes('?'));assert.equal(a.controllerOwner,'azhou-zcode-startup');
 assert.equal(a.identify(host('app://-/index.html')).kind,'unmatched');
 for(const suffix of ['?other=x','?locale=en&locale=zh','?locale=en&%6cocale=zh','#login','?windowKind=update-status'])assert.equal(a.identify(host(base+suffix)).kind,'unmatched');
 const child=host();child.top={};assert.equal(a.identify(child).kind,'unmatched');
 assert.equal(a.identify(host(base.replace('index.html','plugin-sandbox.html'))).kind,'unmatched');
 assert.equal(a.identify(host(base.replace('file:///','file://foreign/'))).kind,'unmatched');
});
test('namespace is explicit, immutable, no Codex DB or open on construction',()=>{
 const h=host();h.indexedDB={open(){throw Error('must not open')}};const a=createZCodePageAdapter(h);
 const e=a.settingsEnvironment();assert.equal(e.indexedDB,h.indexedDB);assert.deepEqual(e.settingsNamespace,{databaseName:'azhou-zcode-startup',databaseVersion:1,storeName:'settings',settingsKey:'images'});
 assert(Object.isFrozen(e));assert(Object.isFrozen(e.settingsNamespace));
});
test('cleanup has exactly controller-owned registry, unsupported refuses',()=>{
 const resource={key:'zcode',dispose(){}};assert.equal(createZCodePageAdapter(host()).registerCleanup(resource),false);
 const seen=[];const a=createZCodePageAdapter(host(),{}, {registerCleanup:r=>seen.push(r)});
 assert.equal(a.registerCleanup({key:'bad'}),false);assert.equal(a.registerCleanup(resource),true);assert.deepEqual(seen,[resource]);
});
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.attrs={};this.events=new Map();this.style={setProperty(k,v){this[k]=v}};this.rect={left:0,right:200,top:0,bottom:30,width:200,height:30};}
 setAttribute(k,v){this.attrs[k]=v}getAttribute(k){return this.attrs[k]}
 append(...nodes){for(const n of nodes)this.appendChild(n)}
 appendChild(n){if(n.parentElement)n.remove();this.children.push(n);n.parentElement=this;return n}
 remove(){if(this.parentElement){this.parentElement.children=this.parentElement.children.filter(n=>n!==this);this.parentElement=null}}
 attachShadow(){this.shadowRoot=new Element('shadow');return this.shadowRoot}
 contains(n){return this===n||this.children.some(c=>c.contains(n))}
 addEventListener(k,v){this.events.set(k,v)}removeEventListener(k){this.events.delete(k)}
 getBoundingClientRect(){return this.rect}
}
function dom(){
 const sidebar=new Element('aside');sidebar.rect={left:0,right:240,top:0,bottom:700,width:240,height:700};
 const root=new Element();root.lang='en';root.classList={contains:v=>v==='dark'};
 const document={documentElement:root,createElement:t=>new Element(t),querySelectorAll:s=>s==='aside[data-testid="sidebar"]'?[sidebar]:[],getElementById:()=>root};
 let disconnected=0;const h={...host(),document,CSS:{supports:()=>true},getComputedStyle:()=>({colorScheme:'dark',getPropertyValue:k=>({'--color-background':'#161616','--color-foreground':'#eee'})[k]||''}),setTimeout:()=>1,clearTimeout(){},addEventListener(){},removeEventListener(){},MutationObserver:class{observe(){}disconnect(){disconnected++}}};h.top=h;
 return {h,sidebar,get disconnected(){return disconnected}};
}
test('entry owns in-flow row, hides on overflow, removes listeners once',()=>{
 const d=dom();const a=createZCodePageAdapter(d.h);const appearance=a.observeAppearance();assert.equal(appearance.theme,'dark');assert.equal(appearance.colors.surface,'#161616');
 let opened=0,retried=0;const e=a.mountEntry(d.h.document,()=>opened++,{},null,appearance,d.h,()=>retried++,()=>{});
 assert.equal(d.sidebar.children.length,0);e.update(true);assert.equal(e.element.parentElement,d.sidebar);assert.equal(e.element.style.display,'block');
 e.button.events.get('click')();assert.equal(opened,1);e.setWallpaperFailure({retrying:true});assert.equal(e.element.shadowRoot.children[2].hidden,false);
 e.element.rect={left:0,right:300,top:0,bottom:30,width:300,height:30};e.update(true);assert.equal(e.element.style.display,'none');
 e.update(false);assert(e.button.disabled);e.remove();e.remove();assert.equal(d.disconnected,1);assert.equal(d.sidebar.children.length,0);assert.equal(e.button.events.size,0);
});
test('entry anchors beneath the marketplace row when the sidebar supports lookup',()=>{
 const d=dom();const market=new Element('button');market.textContent='Plugin Marketplace';d.sidebar.appendChild(market);
 const account=new Element('button');account.textContent='nscdeclsr';d.sidebar.appendChild(account);
 d.sidebar.querySelectorAll=selector=>selector.includes('button')?[market,account]:[];
 market.insertAdjacentElement=function(pos,el){this.parentElement.children.splice(this.parentElement.children.indexOf(this)+1,0,el);el.parentElement=this.parentElement;return el;};
 const a=createZCodePageAdapter(d.h);const appearance=a.observeAppearance();
 const e=a.mountEntry(d.h.document,()=>{},{},null,appearance,d.h,()=>{},()=>{});
 e.update(true);
 const index=d.sidebar.children.indexOf(e.element);
 assert.ok(index===d.sidebar.children.indexOf(market)+1,'entry sits directly beneath the marketplace row');
 assert.notEqual(e.element.parentElement,account,'entry never lands after the account row');
 assert.equal(e.element.style.display,'block');
 e.remove();assert.equal(d.sidebar.children.length,2);
});
test('entry falls back to the sidebar tail without a findable marketplace row',()=>{
 const d=dom();const a=createZCodePageAdapter(d.h);const appearance=a.observeAppearance();
 const e=a.mountEntry(d.h.document,()=>{},{},null,appearance,d.h,()=>{},()=>{});
 e.update(true);
 assert.equal(e.element.parentElement,d.sidebar);assert.equal(d.sidebar.children[d.sidebar.children.length-1],e.element);
 e.remove();
});
test('wallpaper shell refuses absent or ambiguous main and respects cancellation',()=>{
 const h=host();const main={closest:()=>null};let count=1;
 const root={querySelectorAll:s=>s==='main'?Array(count).fill(main):[{}]};h.document={getElementById:()=>root};
 const a=createZCodePageAdapter(h);
 assert.deepEqual(a.controllerWallpaper,{owner:'azhou.zcode-startup-animation',requiresControllerMetadata:true});
 assert(Object.isFrozen(a.controllerWallpaper));assert(Object.isFrozen(a.wallpaper));assert(Object.isFrozen(a.wallpaper.attributes));
 assert.equal(a.wallpaper.validPage(h),true);assert.equal(a.wallpaper.shellState(()=>false),'cancelled');assert.equal(a.wallpaper.shellState(()=>true),'ready');assert.deepEqual(a.wallpaper.surfaces(h),[main]);
 count=2;assert.equal(a.wallpaper.shellState(()=>true),null);assert.deepEqual(a.wallpaper.surfaces(h),[]);h.location.href='https://invalid/';assert.deepEqual(a.wallpaper.surfaces(h),[]);assert.equal(a.wallpaper.validPage(h),false);
});

test('native metadata token never echoes URL bootstrap values',()=>{
 const h=host(base+'?initialWorkspacePath=SYNTHETIC_PRIVATE_PATH');const metadata=Object.freeze({documentToken:'actual-opaque-context-id'});const a=createZCodePageAdapter(h,{controllerMetadata:metadata});assert.equal(a.controllerMetadata,metadata);assert.equal(a.identify().documentToken,metadata.documentToken);assert(!JSON.stringify(a.identify()).includes('SYNTHETIC_PRIVATE_PATH'));
});
