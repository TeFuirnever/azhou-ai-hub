import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,readFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const harness=resolve(process.argv[2]);
const output=resolve(process.argv[3]);
await mkdir(output,{mode:0o700});
const {writeOwnedChunk,navigateWithLoad,trackOwnedChild}=await import(pathToFileURL(join(harness,'fixture-browser-lifecycle.mjs')));
const unhandled=[];process.on('unhandledRejection',error=>unhandled.push(String(error)));
let count=0;
{
  const actual=[];const expected=Buffer.from([0,255,13,10,128]);
  writeOwnedChunk(1,expected,(_fd,bytes,offset,length)=>{const n=Math.min(2,length);actual.push(...bytes.subarray(offset,offset+n));return n;});
  assert.deepEqual(Buffer.from(actual),expected);count++;
  assert.throws(()=>writeOwnedChunk(1,expected,()=>0),/zero-progress/);count++;
}
{
  let cancel=false;const loaded=new Promise(()=>{});loaded.cancel=()=>{cancel=true;};
  await assert.rejects(navigateWithLoad({waitForEvent:()=>loaded,call:async()=>({errorText:'controlled navigation error'})},'fixture.invalid'),/controlled navigation error/);
  assert.equal(cancel,true);count++;
}
{
  let cancel=false;const loaded=Promise.resolve({});loaded.cancel=()=>{cancel=true;};
  assert.deepEqual(await navigateWithLoad({waitForEvent:()=>loaded,call:async()=>({frameId:'fixture'})},'fixture.invalid'),{frameId:'fixture'});
  assert.equal(cancel,true);count++;
}
{
  const loaded=new Promise((_,reject)=>setTimeout(()=>reject(new Error('controlled load timeout')),10));loaded.cancel=()=>{};
  await assert.rejects(navigateWithLoad({waitForEvent:()=>loaded,call:()=>new Promise(()=>{})},'fixture.invalid'),/load timeout/);count++;
}
for (const mode of ['nonzero','term']) {
  const evidenceDir=join(output,mode);await mkdir(evidenceDir,{mode:0o700});
  const script=mode==='nonzero'?'process.stdout.write(Buffer.from([0,255,13,10]));process.exitCode=7;':"console.log('ready');setInterval(()=>{},1000)";
  const child=spawn(process.execPath,['-e',script],{stdio:['ignore','pipe','pipe']});
  const owner=trackOwnedChild(child,{argv:[process.execPath,'-e',script],profile:null,evidenceDir});
  await owner.recordStart();
  if(mode==='nonzero')await owner.closePromise;
  else await new Promise(resolveReady=>child.stdout.once('data',resolveReady));
  const result=await owner.stop({termMs:100,killMs:2000});
  assert.equal(result.waitObserved,true);assert.deepEqual(result.captureErrors,[]);
  if(mode==='nonzero'){
    assert.equal(result.exit.code,7);assert.deepEqual(await readFile(join(evidenceDir,'owned-child-stdout.bin')),Buffer.from([0,255,13,10]));
    assert.deepEqual(result.signals,[]);
  } else assert.equal(result.exit.signal,'SIGTERM');
  count++;
}
await new Promise(resolveWait=>setTimeout(resolveWait,30));assert.deepEqual(unhandled,[]);
console.log(JSON.stringify({scope:'restored lifecycle in-memory CDP and owned Node children only',passed:count,unhandledRejections:unhandled}));
