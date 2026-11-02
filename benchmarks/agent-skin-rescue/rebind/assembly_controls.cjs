// In-memory DOM fixture only. No sockets or host browser.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const run=process.argv[2];const read=n=>fs.readFileSync(path.join(run,n),'utf8');
const styles=new Map(),operations=[];let failRemove=false;
const document={documentElement:{},head:{appendChild(node){operations.push('append');styles.set(node.id,node);}},
 getElementById(id){return styles.get(id)||null;},querySelectorAll(sel){return styles.has(sel.slice(1))?[styles.get(sel.slice(1))]:[];},
 createElement(kind){assert.equal(kind,'style');return {dataset:{},remove(){if(failRemove)throw new Error('synthetic remove failure');operations.push('remove');styles.delete(this.id);}};}};
const sandbox={URL,document,performance:{timeOrigin:456.75},location:{href:'file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html'},
 getComputedStyle(){return {getPropertyValue(){return [...styles.values()][0]?.dataset.owner||'';}};}};sandbox.top=sandbox;vm.createContext(sandbox);
const evaluate=n=>vm.runInContext(read(n),sandbox,{timeout:3000});
const unwrap=v=>{assert.equal(v.installed,false);assert.equal(v.reason,'probe-only');return v.assemblyObservation;};
const results=[];const test=(name,work)=>{work();results.push({name,passed:true});};
test('wrong-target-no-marker',()=>{sandbox.location.href='file:///wrong/index.html';assert.equal(evaluate('mount.js').reason,'probe-target-mismatch');assert.equal(operations.length,0);});
sandbox.location.href='file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html';
test('stale-generation-before-DOM',()=>{assert.equal(evaluate('stale.js').reason,'probe-target-mismatch');assert.equal(operations.length,0);});
test('mount-through-real-IIFE',()=>{const x=unwrap(evaluate('mount.js'));assert.equal(x.state,'mounted');assert.equal(x.count,1);assert.equal(x.readback,[...styles.values()][0].dataset.owner);});
test('repeat-one-owner',()=>{assert.equal(unwrap(evaluate('mount.js')).state,'reused');assert.equal(operations.join(','),'append');});
test('foreign-owner-refused',()=>{assert.equal(unwrap(evaluate('foreign.js')).state,'ownership-mismatch');assert.equal(operations.join(','),'append');});
test('failed-cleanup-is-unknown',()=>{failRemove=true;assert.equal(unwrap(evaluate('clean.js')).state,'cleanup-unknown');assert.equal(styles.size,1);failRemove=false;});
test('owned-cleanup',()=>{const x=unwrap(evaluate('clean.js'));assert.equal(x.state,'disposed');assert.equal(x.count,0);});
test('double-cleanup',()=>{assert.equal(unwrap(evaluate('clean.js')).state,'already-disposed');assert.equal(operations.join(','),'append,remove');});
test('unwired-default-Codex-rejection',()=>{assert.equal(evaluate('unwired.js').reason,'page-unsupported');assert.equal(operations.join(','),'append,remove');});
test('no-global-controller',()=>assert.ok(!Object.keys(sandbox).some(k=>/PageController|agentSkin/i.test(k))));
const bootstrap=fs.readFileSync(path.join(run,'source/extension/bootstrap.mjs'),'utf8').replace('export function bootstrapStartup(','function bootstrapStartup(');
test('formal-third-param-identity-and-normal-arity',()=>{
 const calls=[];const adapter={identify(){}};const payload=()=>{};
 const start=vm.runInNewContext(bootstrap+';bootstrapStartup',{});
 const dependencies={installStartup(...args){calls.push(args);return 'normal';},installAnimation:payload,createLocalization(){},createImageSettings(){},createWallpaperApplicator(){return ()=>{};},installRenderer(){},host:{},pageAdapter:adapter};
 assert.equal(start(dependencies),'normal');assert.equal(calls[0].length,3);assert.equal(calls[0][2],adapter);
});
console.log(JSON.stringify({scope:'FULL RESOURCE PIPELINE + VM FIXTURE; NOT HOST',results,passed:results.length,total:results.length}));
