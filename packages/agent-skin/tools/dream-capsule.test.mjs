import assert from 'node:assert/strict';
import { webcrypto, createHash } from 'node:crypto';
import * as canonicalDream from '../dream-theme-style.mjs';
import { generatedDream } from './test-dream-generated.mjs';
for (const api of [canonicalDream, generatedDream]) {
const { readDreamCapsule } = api;

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGMUt4xmYGBgYgADKAUADMEAsTl1AMYAAAAASUVORK5CYII=', 'base64');
const theme = {schemaVersion:1, id:'source.demo', name:'<img src=x onerror=alert(1)>', image:'background.png'};
const css = '[data-ds-part="main"]{background-color:rgba(10,20,30,.4);}';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const file = bytes => ({bytes:bytes.length, sha256:sha(bytes), base64:bytes.toString('base64')});
function capsule() {
  return {schema:'azhou-agent-skin.dream-capsule.v1', archiveSha256:'a'.repeat(64), files:{
    'theme.json':file(Buffer.from(JSON.stringify(theme))), 'theme.css':file(Buffer.from(css)), 'background.png':file(png)}};
}
const bytes = value => Buffer.from(JSON.stringify(value));
const options = {crypto:webcrypto, decodeImage: async (data, type) => {
  assert(Buffer.from(data).equals(png)); assert.equal(type,'image/png'); return {width:2,height:3};
}};
const original = bytes(capsule());
const verified = await readDreamCapsule(original, options);
assert.equal(verified.capsuleSha256, sha(original));
assert.equal(verified.archiveSha256, 'a'.repeat(64));
assert.deepEqual(verified.manifest, theme);
assert.equal(verified.css, css);
assert(Buffer.from(verified.image.bytes).equals(png));
assert.equal(verified.image.mime,'image/png');
assert.equal(verified.image.sha256,sha(png));
assert.deepEqual(verified.paint.steps[0].rgba,[10,20,30,.4]);
let decoded = 0;
const blocked = async value => assert.rejects(readDreamCapsule(value, {crypto:webcrypto,decodeImage:async()=>{decoded++;return {width:2,height:3};}}));
for (const change of [
  value => {value.extra=true;}, value => {value.safe=true;}, value => {value.schema='azhou-appearance-preset.v1';},
  value => {value.archiveSha256='NOTHASH';}, value => {value.files['other.png']=file(png);},
  value => {value.files['theme.css'].bytes++;}, value => {value.files['theme.css'].sha256='0'.repeat(64);},
  value => {value.files['theme.css'].base64+='\n';}, value => {value.files['theme.css'].extra=true;},
  value => {value.files['theme.json']=file(Buffer.from(JSON.stringify({...theme,appearance:'auto'})));},
  value => {value.files['theme.json']=file(Buffer.from('{"schemaVersion":1,"id":"a","id":"b","name":"n","image":"background.png"}'));},
  value => {value.files['theme.json']=file(Buffer.from('{"schemaVersion":1,"id":"a","\\u0069d":"b","name":"n","image":"background.png"}'));},
  value => {value.files['theme.css']=file(Buffer.from(css+'[data-ds-part="sidebar"]{color:#fff;}'));},
  value => {value.files['theme.css']=file(Buffer.from([0xc3,0x28]));},
  value => {value.files['background.png']=file(Buffer.from('not an image'));},
]) {const value=capsule();change(value);await blocked(bytes(value));}
assert.equal(decoded,0,'Reject metadata, bytes, UTF-8 and unsupported profile before rasterizing');
await blocked(Buffer.from('{"schema":1,"schema":2}'));
await blocked(Buffer.from([0xff]));
await blocked(Buffer.alloc(20*1024*1024+1));
await assert.rejects(readDreamCapsule(original,{crypto:webcrypto}));
await assert.rejects(readDreamCapsule(original,{crypto:webcrypto,decodeImage:async()=>{throw new Error('decode');}}));
await assert.rejects(readDreamCapsule(original,{crypto:webcrypto,decodeImage:async()=>({width:3,height:2})}));
console.log('Dream source capsule exact shape, original bytes, hashes, total mapping and decode boundary passed');

for (const themeSource of ['{', '{"schemaVersion":1,}', '{"schemaVersion":1} garbage', '{"x":1e999}',
  '['.repeat(20)+']'.repeat(20), '{"__proto__":{}}']) {
  const value=capsule();value.files['theme.json']=file(Buffer.from(themeSource));await blocked(bytes(value));
}
const animated=capsule();
const animationChunk=Buffer.alloc(12);animationChunk.write('acTL',4);
animated.files['background.png']=file(Buffer.concat([png.subarray(0,33),animationChunk,png.subarray(33)]));
await blocked(bytes(animated));
const trailing=capsule();trailing.files['background.png']=file(Buffer.concat([png,Buffer.from([0])]));
await blocked(bytes(trailing));
const controller=new AbortController();controller.abort();
await assert.rejects(readDreamCapsule(original,{...options,signal:controller.signal}), /operation-cancelled/);
const during=new AbortController();
await assert.rejects(readDreamCapsule(original,{crypto:webcrypto,signal:during.signal,decodeImage:async()=>{
  during.abort();return {width:2,height:3};
}}), /operation-cancelled/);
const mutable=Buffer.from(original);
const pending=readDreamCapsule(mutable,options);mutable.fill(0);
assert.equal((await pending).capsuleSha256,sha(original),'Input copied before any asynchronous boundary');
assert.equal(decoded,0);

// The metadata helper sniffs JPEG before honoring a .webp suffix. A source
// wrapper must not let a decoder's own sniffing accept a wrong named container.
const sniffedJpeg=Buffer.alloc(65546);
sniffedJpeg.set([0xff,0xd8,0xff,0xef,2,0,1,0]); // APP15 length 512; fake RIFF length 65538.
sniffedJpeg.write('JUNK',12);sniffedJpeg.writeUInt32LE(sniffedJpeg.length-20,16);
sniffedJpeg.set([0xff,0xc0,0,17,8,0,3,0,2,3,1,0x11,0,2,0x11,0,3,0x11,0],516);
sniffedJpeg.set([0xff,0xd9],sniffedJpeg.length-2);
const mismatch=capsule();delete mismatch.files['background.png'];
mismatch.files['background.webp']=file(sniffedJpeg);
mismatch.files['theme.json']=file(Buffer.from(JSON.stringify({...theme,image:'background.webp'})));
await blocked(bytes(mismatch));
assert.equal(decoded,0,'Reject a mismatched actual container before decoder sniffing');

// Self-authored solid-color 2x3 images, generated with Pillow 12.3.0.
for (const [name,mime,encoded] of [["background.jpg", "image/jpeg", "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAADAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyeiiivUOQ/9k="], ["background.webp", "image/webp", "UklGRjIAAABXRUJQVlA4ICYAAABwAQCdASoCAAMAAUAmJYgCdAF1AAD++kXL7U/ez8J+g5ZnCvPgAA=="]]) {
  const value=capsule();delete value.files['background.png'];const data=Buffer.from(encoded,'base64');
  value.files[name]=file(data);value.files['theme.json']=file(Buffer.from(JSON.stringify({...theme,image:name})));
  const result=await readDreamCapsule(bytes(value),{crypto:webcrypto,decodeImage:async(actual,type)=>{
    assert.equal(type,mime);assert(Buffer.from(actual).equals(data));return {width:2,height:3};
  }});assert.equal(result.image.mime,mime);
}

// Cancellation during the final capsule hash must not return an importable value.
let digestCalls=0, releaseFinalHash, finalHashReached;
const finalHashBarrier=new Promise(resolve=>{finalHashReached=resolve;});
const finalHashGate=new Promise(resolve=>{releaseFinalHash=resolve;});
const finalHashAbort=new AbortController();
const pausedCrypto={subtle:{async digest(...args){
  if (++digestCalls===4) {finalHashReached();await finalHashGate;}
  return webcrypto.subtle.digest(...args);
}}};
const finalHashResult=readDreamCapsule(original,{...options,crypto:pausedCrypto,signal:finalHashAbort.signal});
const finalHashAssertion=assert.rejects(finalHashResult,/operation-cancelled/);
await finalHashBarrier;
finalHashAbort.abort();releaseFinalHash();
await finalHashAssertion;
assert.equal(digestCalls,4);

// The same-origin settings factory can execute in the parent while TextEncoder
// belongs to its child frame. Brand checks must accept actual cross-realm bytes.
const {runInNewContext}=await import('node:vm');
const childRealmBytes=runInNewContext('Uint8Array.from(input)',{input:Array.from(original)});
assert.equal((await readDreamCapsule(childRealmBytes,options)).capsuleSha256,sha(original));
}
