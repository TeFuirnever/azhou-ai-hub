import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readFile,lstat,readdir,writeFile,mkdir} from 'node:fs/promises';
import {join,resolve,dirname} from 'node:path';
const run=promisify(execFile);
export const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
export async function sourceCheckpoint(root,protocol){
  const git=async args=>(await run('git',args,{cwd:root,encoding:'buffer',maxBuffer:16*1024*1024})).stdout;
  assert.equal((await git(['rev-parse','HEAD'])).toString().trim(),protocol.head,'HEAD drift');
  assert.equal(hash(await git(['ls-files','--stage','-z'])),protocol.indexSHA256,'index drift');
  const names=[...new Set((await git(['ls-files','-z','--cached','--others','--exclude-standard'])).toString().split('\0').filter(Boolean))].sort();
  assert.deepEqual(names,Object.keys(protocol.sourceSHA256).sort(),'input inventory drift');
  for(const name of names){const path=join(root,name),stat=await lstat(path);assert.equal(hash(await readFile(path)),protocol.sourceSHA256[name],'source drift '+name);assert.equal(stat.mode&0o177777,protocol.sourceModes[name],'mode drift '+name);}
  return {head:protocol.head,indexSHA256:protocol.indexSHA256,inputCount:names.length,checkedAt:new Date().toISOString()};
}
export async function validateRegistration(config,startedAt){
  const path=resolve(config.rootProtocolPath),bytes=await readFile(path),protocol=JSON.parse(bytes);
  assert.equal(hash(bytes),config.rootProtocolSHA256,'protocol changed');
  assert.equal(protocol.name,'p07-readability-measurement-v3');
  assert.ok(Number.isInteger(config.session)&&config.session>=0&&config.session<5);
  assert.deepEqual(config.conditions,protocol.conditions);assert.equal(config.framesPerT,6);
  assert.ok(['train','holdout'].includes(config.phase));
  if(config.phase==='holdout'){
    assert.ok(config.envelopePath&&config.envelopeSHA256&&config.frozenAt,'unbound holdout');
    const bytes=await readFile(config.envelopePath),envelope=JSON.parse(bytes);
    assert.equal(hash(bytes),config.envelopeSHA256);assert.equal(envelope.status,'training-frozen');
    assert.equal(envelope.protocolSHA256,config.rootProtocolSHA256);assert.equal(envelope.frozenAt,config.frozenAt);
    assert.ok(Date.parse(startedAt)>Date.parse(config.frozenAt),'collection predates freeze');
  }
  const order=config.phase==='train'?[0,15,57,85,100]:config.session%2===0?[57,0,100,15,85]:[85,15,100,0,57];
  assert.deepEqual(config.transparencies,order);
  return protocol;
}
export async function sealCollection(directory){
  const entries={};for(const name of (await readdir(directory)).sort()){if(name==='collection-manifest.json')continue;const path=join(directory,name);assert.ok((await lstat(path)).isFile(),'unexpected evidence directory');entries[name]=hash(await readFile(path));}
  await writeFile(join(directory,'collection-manifest.json'),JSON.stringify({schema:1,files:entries},null,2),{flag:'wx'});
}

export async function claimOutput(directory){
  const path=resolve(directory);await mkdir(dirname(path),{recursive:true});
  await mkdir(path); // Atomic ownership claim; existing evidence is never writable.
  const stat=await lstat(path);return {path,dev:stat.dev,ino:stat.ino};
}
export async function assertOutputOwner(claim){
  assert.ok(claim,'no output ownership');const stat=await lstat(claim.path);
  assert.ok(stat.isDirectory()&&!stat.isSymbolicLink()&&stat.dev===claim.dev&&stat.ino===claim.ino,'output ownership changed');
}

export async function executionCheckpoint(bindingPath, executionRoot, protocol, payloadPath) {
  const bindingBytes = await readFile(bindingPath);
  const binding = JSON.parse(bindingBytes);
  assert.equal(binding.schema, 1, 'execution binding schema');
  assert.equal(resolve(binding.executionRoot), resolve(executionRoot), 'execution root mismatch');
  assert.equal(resolve(binding.payload.path), resolve(payloadPath), 'payload path mismatch');
  assert.ok(Object.keys(binding.sources).length > 0, 'empty execution sources');
  const inventory=[];
  async function walk(relative='') {
    for(const name of await readdir(join(executionRoot,relative))){
      if(name==='.build'||name==='__pycache__')continue;
      const child=relative?relative+'/'+name:name,stat=await lstat(join(executionRoot,child));
      assert.ok(!stat.isSymbolicLink(),'execution symlink');
      if(stat.isDirectory())await walk(child);else inventory.push(child);
    }
  }
  await walk();
  assert.deepEqual(inventory.sort(),[...Object.keys(binding.sources),...Object.keys(binding.fixtures)].sort(),'execution inventory drift');
  for(const [relative,digest] of Object.entries(binding.fixtures)){
    assert.ok(relative.startsWith('assets/private/')&&!relative.split('/').includes('..'),'invalid fixture path');
    assert.equal(hash(await readFile(join(executionRoot,relative))),digest,'fixture drift');
  }
  for (const [relative, digest] of Object.entries(binding.sources)) {
    assert.ok(!relative.startsWith('/') && !relative.split('/').includes('..'), 'invalid execution path');
    assert.equal(protocol.sourceSHA256['packages/agent-skin/' + relative], digest, 'unregistered execution source');
    assert.equal(hash(await readFile(join(executionRoot, relative))), digest, 'execution source drift');
    assert.equal((await lstat(join(executionRoot,relative))).mode&0o177777,protocol.sourceModes['packages/agent-skin/'+relative],'execution mode drift');
  }
  for (const required of ['tools/test-startup-browser.mjs', 'tools/theme-measurement-evidence.mjs', 'tools/test-startup-payload-browser.py']) {
    assert.ok(binding.sources[required], 'missing execution authority');
  }
  assert.equal(hash(await readFile(payloadPath)), binding.payload.sha256, 'generated payload drift');
  const source = await sourceCheckpoint(resolve(binding.sourceRoot), protocol);
  return { ...source, execution: { bindingSHA256:hash(bindingBytes), sources:binding.sources, fixtures:binding.fixtures, payloadSHA256:binding.payload.sha256 } };
}
