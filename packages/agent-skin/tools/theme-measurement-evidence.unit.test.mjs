import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm,readFile,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {hash,validateRegistration,sealCollection} from './theme-measurement-evidence.mjs';
test('holdout cannot collect without a frozen binding or before freeze',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'theme-registration-test-'));
 try{
  const protocol={name:'p07-readability-measurement-v3',conditions:[{width:811}],framesPerT:6};
  const path=join(dir,'protocol.json');await writeFile(path,JSON.stringify(protocol));
  const config={rootProtocolPath:path,rootProtocolSHA256:hash(await readFile(path)),phase:'holdout',session:0,conditions:protocol.conditions,framesPerT:6,transparencies:[57,0,100,15,85]};
  await assert.rejects(validateRegistration(config,'2026-11-15T00:01:00.000Z'),/unbound holdout/);
  const frozenAt='2026-11-15T00:00:00.000Z',envelopePath=join(dir,'envelope.json');
  await writeFile(envelopePath,JSON.stringify({status:'training-frozen',protocolSHA256:config.rootProtocolSHA256,frozenAt}));
  Object.assign(config,{envelopePath,envelopeSHA256:hash(await readFile(envelopePath)),frozenAt});
  await validateRegistration(config,'2026-11-15T00:01:00.000Z');
  await assert.rejects(validateRegistration(config,frozenAt),/predates freeze/);
  await writeFile(envelopePath,'{}');await assert.rejects(validateRegistration(config,'2026-11-15T00:01:00.000Z'));
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('collection manifest includes non-PNG context and cannot be overwritten',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'theme-seal-test-'));
 try{
  for(const name of ['report.json','outside.json','holdout-matrix.json','frame.png'])await writeFile(join(dir,name),name);
  await sealCollection(dir);const manifest=JSON.parse(await readFile(join(dir,'collection-manifest.json'),'utf8'));
  assert.deepEqual(Object.keys(manifest.files),['frame.png','holdout-matrix.json','outside.json','report.json']);
  await assert.rejects(sealCollection(dir),{code:'EEXIST'});
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('atomic output claim refuses old evidence before browser startup and without writes',async()=>{
 const {claimOutput,assertOutputOwner}=await import('./theme-measurement-evidence.mjs');
 const {execFile}=await import('node:child_process');const {promisify}=await import('node:util');
 const {chmod,access}=await import('node:fs/promises');const {fileURLToPath}=await import('node:url');
 const dir=await mkdtemp(join(tmpdir(),'theme-output-test-'));
 try{
  const old=join(dir,'old');const claim=await claimOutput(old);await assertOutputOwner(claim);
  const originals={};for(const name of ['sentinel','raw.png','report.json','collection-manifest.json']){const bytes=Buffer.from('preserve '+name);await writeFile(join(old,name),bytes);originals[name]=hash(bytes);}
  await assert.rejects(claimOutput(old),{code:'EEXIST'});
  const marker=join(dir,'browser-started'),fake=join(dir,'fake-chrome');await writeFile(fake,'#!/bin/sh\n: > "'+marker+'"\n');await chmod(fake,0o755);
  const runner=fileURLToPath(new URL('./test-startup-browser.mjs',import.meta.url));
  await assert.rejects(promisify(execFile)(process.execPath,[runner,'--theme-protocol',join(dir,'missing-protocol.json'),'--out',old,'--chrome',fake]),error=>String(error.stderr).includes('EEXIST'));
  await assert.rejects(access(marker),{code:'ENOENT'});
  for(const [name,digest] of Object.entries(originals))assert.equal(hash(await readFile(join(old,name))),digest);
  assert.deepEqual((await readdir(old)).sort(),Object.keys(originals).sort());
  await assert.rejects(assertOutputOwner(null),/no output ownership/);
  const fresh=await claimOutput(join(dir,'fresh'));await assertOutputOwner(fresh);
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('cloned evaluator binds original Git inputs, copied bytes and generated payload',async()=>{
 const {executionCheckpoint}=await import('./theme-measurement-evidence.mjs');
 const {mkdir,copyFile,lstat,chmod}=await import('node:fs/promises');
 const {execFile}=await import('node:child_process');const {promisify}=await import('node:util');
 const run=promisify(execFile),dir=await mkdtemp(join(tmpdir(),'theme-execution-test-'));
 try{
  const source=join(dir,'source'),clone=join(dir,'clone');await mkdir(source);await mkdir(clone);
  const names=['tools/test-startup-browser.mjs','tools/theme-measurement-evidence.mjs','tools/test-startup-payload-browser.py'];
  const sources={},sourceSHA256={},sourceModes={};
  for(const name of names){const rel='packages/agent-skin/'+name;await mkdir(join(source,'packages/agent-skin/tools'),{recursive:true});await mkdir(join(clone,'tools'),{recursive:true});await writeFile(join(source,rel),name);await copyFile(join(source,rel),join(clone,name));sources[name]=hash(Buffer.from(name));sourceSHA256[rel]=sources[name];sourceModes[rel]=(await lstat(join(source,rel))).mode;}
  const git=async args=>(await run('git',args,{cwd:source})).stdout;
  await git(['init','-q']);await git(['add','.']);await git(['-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture']);
  const protocol={head:(await git(['rev-parse','HEAD'])).trim(),indexSHA256:hash(Buffer.from(await git(['ls-files','--stage','-z']))),sourceSHA256,sourceModes};
  await mkdir(join(clone,'.build'));const payload=join(clone,'.build/install.js');await writeFile(payload,'generated');
  const binding={schema:1,sourceRoot:source,executionRoot:clone,sources,fixtures:{},payload:{path:payload,sha256:hash(Buffer.from('generated'))}};
  const path=join(dir,'binding.json');await writeFile(path,JSON.stringify(binding));
  await executionCheckpoint(path,clone,protocol,payload);
  await writeFile(join(clone,'tools/unregistered.mjs'),'extra');
  await assert.rejects(executionCheckpoint(path,clone,protocol,payload),/inventory/);
  await rm(join(clone,'tools/unregistered.mjs'));
  await writeFile(payload,'changed');await assert.rejects(executionCheckpoint(path,clone,protocol,payload),/payload drift/);await writeFile(payload,'generated');
  await writeFile(join(clone,names[0]),'changed');await assert.rejects(executionCheckpoint(path,clone,protocol,payload),/execution source drift/);await copyFile(join(source,'packages/agent-skin',names[0]),join(clone,names[0]));
  await writeFile(join(source,'packages/agent-skin',names[0]),'changed');await assert.rejects(executionCheckpoint(path,clone,protocol,payload),/source drift/);
 }finally{await rm(dir,{recursive:true,force:true});}
});
