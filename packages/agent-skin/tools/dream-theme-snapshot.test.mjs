import assert from 'node:assert/strict';
import { webcrypto, createHash } from 'node:crypto';
import { validateThemeSnapshot, verifyThemeSnapshotArtwork } from '../dream-theme-style.mjs';
const hash='a'.repeat(64), audit='b'.repeat(64);
const bundled={schemaVersion:2,revision:1,imagesBinding:hash,selection:{kind:'bundled',id:'azhou-q-v3',surfaceTransparency:{mode:'override',value:0}}};
assert.deepEqual(validateThemeSnapshot(bundled),bundled);
for(const preference of [{mode:'follow'},{mode:'override',value:0},{mode:'override',value:100}]) {
  assert.deepEqual(validateThemeSnapshot({...bundled,selection:{...bundled.selection,surfaceTransparency:preference}}).selection.surfaceTransparency,preference);
}
const legacy={schemaVersion:1,revision:1,imagesBinding:hash,activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':{mode:'override',value:0}}};
assert.deepEqual(validateThemeSnapshot(legacy),bundled);
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGMUt4xmYGBgYgADKAUADMEAsTl1AMYAAAAASUVORK5CYII=','base64');
const imported={schemaVersion:2,revision:2,imagesBinding:hash,selection:{kind:'imported',profile:'codex-main-literal-paint/v1',capsuleSha256:hash,archiveSha256:audit,
  image:{name:'background.png',mime:'image/png',bytes:png.length,sha256:createHash('sha256').update(png).digest('hex'),width:2,height:3},
  paint:{rgba:[17,34,51,.25],backgroundImage:'none',sourceDeclarationCount:2}}};
assert.deepEqual(validateThemeSnapshot(imported),imported);
assert(Object.isFrozen(validateThemeSnapshot(imported).selection.paint.rgba));
const url='data:image/png;base64,'+png.toString('base64');
assert.deepEqual(await verifyThemeSnapshotArtwork(imported,url,{crypto:webcrypto}),imported);
for(const mutate of [v=>v.schemaVersion=99,v=>v.selection.kind='future',v=>v.extra=true,
  v=>v.selection.css='body{}',v=>v.selection.profile='other',v=>v.selection.paint.backgroundImage='url(x)',
  v=>v.selection.paint.rgba=[0,0,256,1],v=>v.selection.paint.rgba=[0,0,0,true],v=>v.selection.paint.rgba=[0,0,0,NaN],
  v=>v.selection.paint.sourceDeclarationCount=129,v=>v.selection.paint.sourceDeclarationCount=0,
  v=>v.selection.image.mime='image/jpeg',v=>v.selection.image.name='../background.png',
  v=>v.selection.image.bytes=10485761,v=>v.selection.image.width=16385,v=>v.selection.image.height=0,
  v=>v.selection.surfaceTransparency={mode:'follow'},v=>v.imagesBinding='INVALID']) {
  const value=structuredClone(imported);mutate(value);assert.throws(()=>validateThemeSnapshot(value));
}
for(const value of [null,{},[],{...bundled,selection:{...bundled.selection,capsuleSha256:hash}},
  {...bundled,selection:{...bundled.selection,surfaceTransparency:{mode:'override',value:true}}}]) {
  assert.throws(()=>validateThemeSnapshot(value));
}
for(const mutate of [v=>v.selection.image.sha256='0'.repeat(64),v=>v.selection.image.bytes++,v=>v.selection.image.width=3]) {
  const value=structuredClone(imported);mutate(value);await assert.rejects(verifyThemeSnapshotArtwork(value,url,{crypto:webcrypto}));
}
await assert.rejects(verifyThemeSnapshotArtwork(imported,url.replace('image/png','image/webp'),{crypto:webcrypto}));
await assert.rejects(verifyThemeSnapshotArtwork(imported,url+'\n',{crypto:webcrypto}));
const abort=new AbortController();let release,arrived;
const barrier=new Promise(resolve=>arrived=resolve),gate=new Promise(resolve=>release=resolve);
const pending=verifyThemeSnapshotArtwork(imported,url,{signal:abort.signal,crypto:{subtle:{async digest(...args){arrived();await gate;return webcrypto.subtle.digest(...args);}}}});
const rejected=assert.rejects(pending,/operation-cancelled/);await barrier;abort.abort();release();await rejected;
console.log('Tagged finite-plan snapshot exact schema, legacy normalization, original image bytes and cancellation passed');
