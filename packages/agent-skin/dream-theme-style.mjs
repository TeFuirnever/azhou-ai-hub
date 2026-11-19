import { parseSafeCssAst } from './vendor/dream-safe-css-ast.mjs';
import { readImageMetadata } from './vendor/dream-image-metadata.mjs';
import { validateOfficialTheme } from './vendor/dream-theme-validator.mjs';

export const DREAM_PAINT_PROFILE = 'codex-main-literal-paint/v1';

function literalRgba(value) {
  const literal = value.toLowerCase();
  if (literal === 'transparent') return [0, 0, 0, 0];
  if (literal.startsWith('#')) {
    let hex = literal.slice(1);
    if (hex.length <= 4) hex = [...hex].map(character => character + character).join('');
    return [0, 2, 4].map(offset => Number.parseInt(hex.slice(offset, offset + 2), 16))
      .concat(hex.length === 8 ? Number.parseInt(hex.slice(6), 16) / 255 : 1);
  }
  const match = /^(rgb|rgba)\((.*)\)$/i.exec(literal);
  if (!match) throw new Error('dream_profile_unmapped_color');
  const channels = match[2].split(',').map(part => part.trim());
  const rgba = channels.slice(0, 3).map(part => part.endsWith('%') ? Number(part.slice(0, -1)) * 255 / 100 : Number(part));
  const alpha = channels[3];
  rgba.push(alpha === undefined ? 1 : alpha.endsWith('%') ? Number(alpha.slice(0, -1)) / 100 : Number(alpha));
  return rgba;
}

// The pristine parser validates every source declaration first. This adapter consumes
// its AST, not compiled selectors, and cannot silently discard an unsupported rule.
export function mapDreamTheme(manifest, source) {
  validateOfficialTheme(manifest);
  if (Object.keys(manifest).length !== 4) throw new Error('dream_profile_unmapped_manifest');
  const parsed = parseSafeCssAst(source);
  const steps = [];
  for (const {selector, declarations} of parsed.rules) {
    if (selector.part !== 'main' || selector.state) throw new Error('dream_profile_unmapped_selector');
    for (const {property, value} of declarations) {
      if (property !== 'background-color') throw new Error('dream_profile_unmapped_declaration');
      steps.push(Object.freeze({rgba: Object.freeze(literalRgba(value)), backgroundImage: 'none'}));
    }
  }
  return Object.freeze({profile: DREAM_PAINT_PROFILE, ruleCount: parsed.ruleCount,
    declarationCount: parsed.declarationCount, steps: Object.freeze(steps)});
}

const IMAGE_MIME = {'background.png': 'image/png', 'background.jpg': 'image/jpeg', 'background.webp': 'image/webp'};
const HASH = /^[0-9a-f]{64}$/;

function requireValue(condition, reason) {
  if (!condition) throw new Error(reason);
}

function exactKeys(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}

// JSON.parse alone erases duplicate keys, including escaped aliases. Bound depth
// and values while retaining its string/number grammar, before trusting any shape.
function staticImage(bytes, name) {
  const extension = name.slice(name.lastIndexOf('.'));
  const matches = extension === '.png'
    ? [137,80,78,71,13,10,26,10].every((byte,index) => bytes[index] === byte)
    : extension === '.jpg' ? bytes[0] === 0xff && bytes[1] === 0xd8
      : String.fromCharCode(...bytes.subarray(0,4)) === 'RIFF'
        && String.fromCharCode(...bytes.subarray(8,12)) === 'WEBP';
  requireValue(matches, 'dream_image_type');
  const metadata = readImageMetadata(bytes, extension);
  requireValue(metadata, 'dream_image_invalid');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const ascii = (offset, length) => String.fromCharCode(...bytes.subarray(offset, offset + length));
  let offset;
  if (extension === '.png') {
    offset = 8;
    while (offset + 12 <= bytes.length) {
      const size = view.getUint32(offset);
      const type = ascii(offset + 4, 4);
      requireValue(size <= bytes.length - offset - 12 && !['acTL', 'fcTL', 'fdAT'].includes(type), 'dream_image_invalid');
      offset += size + 12;
      if (type === 'IEND') {requireValue(size === 0 && offset === bytes.length, 'dream_image_invalid');return metadata;}
    }
  } else if (extension === '.webp') {
    requireValue(view.getUint32(4, true) + 8 === bytes.length, 'dream_image_invalid');
    offset = 12;
    while (offset + 8 <= bytes.length) {
      const type = ascii(offset, 4);
      const size = view.getUint32(offset + 4, true);
      requireValue(size <= bytes.length - offset - 8 && !['ANIM', 'ANMF'].includes(type)
        && !(type === 'VP8X' && size > 0 && (bytes[offset + 8] & 2)), 'dream_image_invalid');
      offset += 8 + size + size % 2;
    }
    requireValue(offset === bytes.length, 'dream_image_invalid');
    return metadata;
  } else {
    requireValue(bytes.at(-2) === 0xff && bytes.at(-1) === 0xd9, 'dream_image_invalid');
    offset = 2;
    while (offset + 4 <= bytes.length) {
      requireValue(bytes[offset++] === 0xff, 'dream_image_invalid');
      while (bytes[offset] === 0xff) offset++;
      const marker = bytes[offset++];
      if (marker === 0xda) return metadata;
      requireValue(marker !== 0xd8 && marker !== 0xd9 && marker !== 0x01 && !(marker >= 0xd0 && marker <= 0xd7), 'dream_image_invalid');
      const size = view.getUint16(offset);
      requireValue(size >= 2 && size <= bytes.length - offset && !(marker === 0xe2 && ascii(offset + 2, 4) === 'MPF\0'), 'dream_image_invalid');
      offset += size;
    }
  }
  throw new Error('dream_image_invalid');
}

export function validateThemeSnapshot(value) {
  requireValue(value && typeof value === 'object' && !Array.isArray(value), 'dream_snapshot_invalid');
  requireValue(Number.isSafeInteger(value.revision) && value.revision >= 1
    && typeof value.imagesBinding === 'string' && HASH.test(value.imagesBinding), 'dream_snapshot_invalid');
  let selection;
  if (value.schemaVersion === 1) {
    requireValue(exactKeys(value,['schemaVersion','revision','activeThemeId','preferencesByTheme','imagesBinding'])
      && value.activeThemeId === 'azhou-q-v3' && exactKeys(value.preferencesByTheme,['azhou-q-v3']), 'dream_snapshot_invalid');
    selection = {kind:'bundled',id:'azhou-q-v3',surfaceTransparency:value.preferencesByTheme['azhou-q-v3']};
  } else {
    requireValue(value.schemaVersion === 2 && exactKeys(value,['schemaVersion','revision','imagesBinding','selection']), 'dream_snapshot_invalid');
    selection = value.selection;
  }
  requireValue(selection && typeof selection === 'object', 'dream_snapshot_invalid');
  let normalized;
  if (selection.kind === 'bundled') {
    const preference = selection.surfaceTransparency;
    requireValue(exactKeys(selection,['kind','id','surfaceTransparency']) && selection.id === 'azhou-q-v3'
      && ((exactKeys(preference,['mode']) && preference.mode === 'follow')
        || (exactKeys(preference,['mode','value']) && preference.mode === 'override'
          && typeof preference.value === 'number' && Number.isFinite(preference.value)
          && preference.value >= 0 && preference.value <= 100)), 'dream_snapshot_invalid');
    normalized = Object.freeze({kind:'bundled',id:'azhou-q-v3',surfaceTransparency:Object.freeze({...preference})});
  } else {
    const image = selection.image, paint = selection.paint;
    requireValue(exactKeys(selection,['kind','profile','capsuleSha256','archiveSha256','image','paint'])
      && selection.kind === 'imported' && selection.profile === DREAM_PAINT_PROFILE
      && typeof selection.capsuleSha256 === 'string' && HASH.test(selection.capsuleSha256)
      && typeof selection.archiveSha256 === 'string' && HASH.test(selection.archiveSha256)
      && exactKeys(image,['name','mime','bytes','sha256','width','height'])
      && Object.hasOwn(IMAGE_MIME,image.name) && image.mime === IMAGE_MIME[image.name]
      && Number.isSafeInteger(image.bytes) && image.bytes > 0 && image.bytes <= 10485760
      && typeof image.sha256 === 'string' && HASH.test(image.sha256)
      && Number.isSafeInteger(image.width) && image.width >= 1 && image.width <= 16384
      && Number.isSafeInteger(image.height) && image.height >= 1 && image.height <= 16384
      && image.width * image.height <= 50000000
      && exactKeys(paint,['rgba','backgroundImage','sourceDeclarationCount']) && paint.backgroundImage === 'none'
      && Number.isSafeInteger(paint.sourceDeclarationCount) && paint.sourceDeclarationCount >= 1 && paint.sourceDeclarationCount <= 128
      && Array.isArray(paint.rgba) && paint.rgba.length === 4
      && paint.rgba.every((channel,index)=>typeof channel === 'number' && Number.isFinite(channel)
        && channel >= 0 && channel <= (index === 3 ? 1 : 255)), 'dream_snapshot_invalid');
    normalized = Object.freeze({kind:'imported',profile:DREAM_PAINT_PROFILE,
      capsuleSha256:selection.capsuleSha256,archiveSha256:selection.archiveSha256,
      image:Object.freeze({...image}),paint:Object.freeze({...paint,rgba:Object.freeze([...paint.rgba])})});
  }
  return Object.freeze({schemaVersion:2,revision:value.revision,imagesBinding:value.imagesBinding,selection:normalized});
}

export async function verifyThemeSnapshotArtwork(value, artwork, {crypto=globalThis.crypto,signal}={}) {
  const theme = validateThemeSnapshot(value);
  if (theme.selection.kind === 'bundled') return theme;
  const image = theme.selection.image;
  const check = () => {if (signal?.aborted) throw new Error('operation-cancelled');};
  check();
  const prefix = 'data:'+image.mime+';base64,';
  requireValue(typeof artwork === 'string' && artwork.length <= 13981039 && artwork.startsWith(prefix), 'dream_snapshot_artwork');
  const encoded = artwork.slice(prefix.length);
  requireValue(encoded.length === 4*Math.ceil(image.bytes/3) && /^[A-Za-z0-9+/]*={0,2}$/.test(encoded), 'dream_snapshot_artwork');
  const binary = atob(encoded);
  requireValue(binary.length === image.bytes && btoa(binary) === encoded && crypto?.subtle, 'dream_snapshot_artwork');
  const bytes = Uint8Array.from(binary,character=>character.charCodeAt(0));
  const metadata = staticImage(bytes,image.name);
  requireValue(metadata.width === image.width && metadata.height === image.height, 'dream_snapshot_artwork');
  const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(byte=>byte.toString(16).padStart(2,'0')).join('');
  check();
  requireValue(hash === image.sha256, 'dream_snapshot_artwork');
  return theme;
}
