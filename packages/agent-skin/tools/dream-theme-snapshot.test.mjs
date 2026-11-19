import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import * as canonicalAzhou from '../azhou-theme-snapshot.mjs';
import { generatedDream } from './test-dream-generated.mjs';
for (const api of [canonicalAzhou, generatedDream]) {
const { validateThemeSnapshot } = api;
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
assert.throws(() => validateThemeSnapshot(imported), /dream_snapshot_invalid/);
assert.equal(typeof api.verifyThemeSnapshotArtwork, 'undefined');
for (const value of [null, {}, [], {...bundled, schemaVersion: 99}, {...bundled, imagesBinding:'INVALID'},
  {...bundled, selection: {...bundled.selection, kind: 'future'}},
  {...bundled, selection: {...bundled.selection, capsuleSha256: hash}},
  ...[true, -1, 101, Infinity, NaN].map(value=>({...bundled,
    selection:{...bundled.selection,surfaceTransparency:{mode:'override',value}}})),
]) assert.throws(() => validateThemeSnapshot(value), /dream_snapshot_invalid/);
}
