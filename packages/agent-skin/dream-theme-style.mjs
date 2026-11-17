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

const CAPSULE_LIMIT = 20 * 1024 * 1024;
const FILE_LIMITS = {'theme.json': 1048576, 'theme.css': 262144,
  'background.png': 10485760, 'background.jpg': 10485760, 'background.webp': 10485760};
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
function strictJson(bytes) {
  const source = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(bytes);
  let index = 0;
  let values = 0;
  const whitespace = () => {while (/[\t\n\r ]/.test(source[index] || '\0')) index++;};
  function string() {
    const start = index++;
    while (index < source.length) {
      const character = source[index++];
      if (character === '\\') index++;
      else if (character === '"') return JSON.parse(source.slice(start, index));
    }
    throw new Error('dream_json_invalid');
  }
  function value(depth) {
    requireValue(depth <= 16 && ++values <= 8192, 'dream_json_budget');
    whitespace();
    const character = source[index];
    if (character === '"') return string();
    if (character === '{' || character === '[') {
      index++;
      const object = character === '{';
      const result = object ? {} : [];
      const end = object ? '}' : ']';
      const keys = new Set();
      whitespace();
      if (source[index] === end) {index++;return result;}
      while (index < source.length) {
        let key;
        if (object) {
          requireValue(source[index] === '"', 'dream_json_invalid');
          key = string();
          requireValue(!keys.has(key), 'dream_json_duplicate_key');
          keys.add(key);
          whitespace();
          requireValue(source[index++] === ':', 'dream_json_invalid');
        }
        const item = value(depth + 1);
        if (object) Object.defineProperty(result, key, {value:item, enumerable:true, writable:true, configurable:true});
        else result.push(item);
        whitespace();
        const separator = source[index++];
        if (separator === end) return result;
        requireValue(separator === ',', 'dream_json_invalid');
        whitespace();
      }
      throw new Error('dream_json_invalid');
    }
    const token = /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/.exec(source.slice(index));
    requireValue(token, 'dream_json_invalid');
    index += token[0].length;
    const result = JSON.parse(token[0]);
    requireValue(typeof result !== 'number' || Number.isFinite(result), 'dream_json_invalid');
    return result;
  }
  const result = value(0);
  whitespace();
  requireValue(index === source.length, 'dream_json_invalid');
  return result;
}

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

export async function readDreamCapsule(input, {crypto = globalThis.crypto, decodeImage, signal} = {}) {
  requireValue(input instanceof Uint8Array && input.byteLength > 0 && input.byteLength <= CAPSULE_LIMIT, 'dream_capsule_size');
  requireValue(typeof decodeImage === 'function' && crypto?.subtle, 'dream_decoder_unavailable');
  const bytes = Uint8Array.prototype.slice.call(input);
  const check = () => {if (signal?.aborted) throw new Error('operation-cancelled');};
  const digest = async data => [...new Uint8Array(await crypto.subtle.digest('SHA-256', data))]
    .map(byte => byte.toString(16).padStart(2, '0')).join('');
  check();
  const capsule = strictJson(bytes);
  requireValue(exactKeys(capsule, ['schema', 'archiveSha256', 'files'])
    && capsule.schema === 'azhou-agent-skin.dream-capsule.v1'
    && typeof capsule.archiveSha256 === 'string' && HASH.test(capsule.archiveSha256), 'dream_capsule_invalid');
  requireValue(capsule.files && typeof capsule.files === 'object' && !Array.isArray(capsule.files)
    && Object.keys(capsule.files).length === 3, 'dream_capsule_files');
  const files = {};
  for (const [name, record] of Object.entries(capsule.files)) {
    const limit = Object.hasOwn(FILE_LIMITS, name) ? FILE_LIMITS[name] : 0;
    requireValue(limit && exactKeys(record, ['bytes', 'sha256', 'base64'])
      && Number.isSafeInteger(record.bytes) && record.bytes > 0 && record.bytes <= limit
      && typeof record.sha256 === 'string' && HASH.test(record.sha256)
      && typeof record.base64 === 'string' && record.base64.length === 4 * Math.ceil(record.bytes / 3)
      && /^[A-Za-z0-9+/]*={0,2}$/.test(record.base64), 'dream_capsule_file');
    const binary = atob(record.base64);
    requireValue(binary.length === record.bytes && btoa(binary) === record.base64, 'dream_capsule_file');
    const data = Uint8Array.from(binary, character => character.charCodeAt(0));
    requireValue(await digest(data) === record.sha256, 'dream_capsule_file_hash');
    check();
    files[name] = data;
  }
  requireValue(files['theme.json'] && files['theme.css'], 'dream_capsule_files');
  const manifest = strictJson(files['theme.json']);
  const css = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(files['theme.css']);
  const paint = mapDreamTheme(manifest, css);
  requireValue(Object.hasOwn(IMAGE_MIME, manifest.image) && Object.hasOwn(files, manifest.image), 'dream_capsule_files');
  const image = files[manifest.image];
  const metadata = staticImage(image, manifest.image);
  check();
  const decoded = await decodeImage(image.slice(), IMAGE_MIME[manifest.image], signal);
  check();
  requireValue(decoded && decoded.width === metadata.width && decoded.height === metadata.height, 'dream_image_decode');
  const capsuleSha256 = await digest(bytes);
  check();
  return {capsuleSha256, archiveSha256:capsule.archiveSha256, manifest, css, paint,
    image:{bytes:image, mime:IMAGE_MIME[manifest.image], sha256:capsule.files[manifest.image].sha256,
      width:metadata.width, height:metadata.height}};
}
