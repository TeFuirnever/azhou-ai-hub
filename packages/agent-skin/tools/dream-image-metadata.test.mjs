import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import vm from 'node:vm';
import {
  classifyImageDimensions,
  MAX_IMAGE_DIMENSION,
  MAX_IMAGE_PIXELS,
  readImageMetadata,
  readRawDimensions,
} from '../vendor/dream-image-metadata.mjs';

const PACKAGE = join(dirname(fileURLToPath(import.meta.url)), '..');
const classicReaderPath = join(PACKAGE, 'image-metadata-reader.js');
const classicSource = await readFile(classicReaderPath, 'utf8');
const classicContext = { ArrayBuffer, Uint8Array };
new vm.Script(classicSource, { filename: classicReaderPath }).runInNewContext(classicContext);
const classicReadRawDimensions = classicContext.AGENT_SKIN_READ_RAW_DIMENSIONS;
assert.equal(typeof classicReadRawDimensions, 'function');

function assertBothReaders(value, extension, expected) {
  assert.deepEqual(readRawDimensions(value, extension), expected);
  const classic = classicReadRawDimensions(value, extension);
  assert.deepEqual(classic && { ...classic }, expected);
}

function pngHeader(width, height) {
  const bytes = new Uint8Array(24);
  bytes.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  bytes.set([0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52], 8);
  const view = new DataView(bytes.buffer);
  view.setUint32(16, width, false);
  view.setUint32(20, height, false);
  return bytes;
}

function webpVp8xHeader(width, height) {
  const bytes = new Uint8Array(30);
  bytes.set([0x52, 0x49, 0x46, 0x46]);
  new DataView(bytes.buffer).setUint32(4, 22, true);
  bytes.set([0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x58], 8);
  new DataView(bytes.buffer).setUint32(16, 10, true);
  const widthMinusOne = width - 1;
  const heightMinusOne = height - 1;
  bytes[24] = widthMinusOne & 0xff;
  bytes[25] = (widthMinusOne >> 8) & 0xff;
  bytes[26] = (widthMinusOne >> 16) & 0xff;
  bytes[27] = heightMinusOne & 0xff;
  bytes[28] = (heightMinusOne >> 8) & 0xff;
  bytes[29] = (heightMinusOne >> 16) & 0xff;
  return bytes;
}

test('reads PNG dimensions from the header', () => {
  assertBothReaders(pngHeader(1280, 720), '.png', {
    width: 1280,
    height: 720,
  });
});

test('reads JPEG dimensions from a SOF marker', () => {
  const bytes = Uint8Array.from([
    0xff, 0xd8,
    0xff, 0xc0, 0x00, 0x07, 0x08, 0x00, 0x20, 0x00, 0x30,
    0x00, 0x00,
  ]);
  assertBothReaders(bytes, '.jpg', { width: 48, height: 32 });
});

test('reads WebP dimensions from a VP8X chunk', () => {
  assertBothReaders(webpVp8xHeader(640, 360), '.webp', {
    width: 640,
    height: 360,
  });
});

test('returns raw dimensions for an obviously oversized PNG header', () => {
  assertBothReaders(pngHeader(25000, 12000), '.png', {
    width: 25000,
    height: 12000,
  });
});

test('returns null for a truncated JPEG APP segment with a long declared length', () => {
  const bytes = Uint8Array.from([
    0xff, 0xd8, 0xff, 0xe1, 0xff, 0xff,
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06,
  ]);
  assertBothReaders(bytes, '.jpeg', null);
});

test('returns null for a WebP chunk whose declared size exceeds the RIFF payload', () => {
  const bytes = new Uint8Array(20);
  bytes.set([0x52, 0x49, 0x46, 0x46]);
  new DataView(bytes.buffer).setUint32(4, 0xffff_ffff, true);
  bytes.set([0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x58], 8);
  new DataView(bytes.buffer).setUint32(16, 0xffff_ffff, true);
  assertBothReaders(bytes, '.webp', null);
});

function jpegWithSegments(...segments) {
  return Uint8Array.from([0xff, 0xd8, ...segments.flat(), ...Array(12).fill(0)]);
}

function jpegSof(width, height, marker = 0xc0, length = 8) {
  return [0xff, marker, (length >> 8) & 0xff, length & 0xff, 8,
    (height >> 8) & 0xff, height & 0xff, (width >> 8) & 0xff, width & 0xff, 3];
}

function webp(chunks, declaredRiffSize) {
  const chunkBytes = chunks.flatMap(([type, payload]) => {
    const bytes = [
      ...Array.from(type, character => character.charCodeAt(0)),
      payload.length & 0xff, (payload.length >>> 8) & 0xff,
      (payload.length >>> 16) & 0xff, (payload.length >>> 24) & 0xff,
      ...payload,
    ];
    if (payload.length % 2) bytes.push(0);
    return bytes;
  });
  const bytes = new Uint8Array(12 + chunkBytes.length);
  bytes.set([0x52, 0x49, 0x46, 0x46], 0);
  new DataView(bytes.buffer).setUint32(4, declaredRiffSize ?? bytes.length - 8, true);
  bytes.set([0x57, 0x45, 0x42, 0x50], 8);
  bytes.set(chunkBytes, 12);
  return bytes;
}

function vp8x(width, height) {
  const payload = new Uint8Array(10);
  const widthMinusOne = width - 1;
  const heightMinusOne = height - 1;
  payload[4] = widthMinusOne & 0xff;
  payload[5] = (widthMinusOne >>> 8) & 0xff;
  payload[6] = (widthMinusOne >>> 16) & 0xff;
  payload[7] = heightMinusOne & 0xff;
  payload[8] = (heightMinusOne >>> 8) & 0xff;
  payload[9] = (heightMinusOne >>> 16) & 0xff;
  return payload;
}

test('PNG parser rejects short, mismatched, zero-sized, and malformed IHDR headers', () => {
  const short = new Uint8Array(23);
  const badSignature = pngHeader(32, 16);
  badSignature[0] = 0;
  const badLength = pngHeader(32, 16);
  badLength[11] = 12;
  const badType = pngHeader(32, 16);
  badType[15] = 0x58;
  assertBothReaders(short, '.png', null);
  assertBothReaders(badSignature, '.png', null);
  assertBothReaders(badLength, '.png', null);
  assertBothReaders(badType, '.png', null);
  assertBothReaders(pngHeader(0, 16), '.png', null);
  assertBothReaders(pngHeader(32, 0), '.png', null);
});

test('JPEG parser skips ordinary and standalone markers and handles SOF boundaries', () => {
  const valid = jpegWithSegments(
    [0x11, 0xff, 0xff, 0x01],
    [0xff, 0xd0],
    [0xff, 0xe1, 0x00, 0x04, 0xaa, 0xbb],
    jpegSof(96, 48, 0xc2),
  );
  assertBothReaders(valid, '.jpeg', { width: 96, height: 48 });
  const invalidStart = jpegWithSegments([0x00, 0xc0, 0x00, 0x08, ...jpegSof(96, 48).slice(4)]);
  invalidStart[1] = 0;
  assertBothReaders(invalidStart, '.jpeg', null);
  assertBothReaders(jpegWithSegments([0xff, 0xd9]), '.jpg', null);
  assertBothReaders(jpegWithSegments([0xff, 0xda]), '.jpg', null);
  assertBothReaders(jpegWithSegments([0xff, 0xc0, 0x00, 0x01]), '.jpg', null);
  assertBothReaders(jpegWithSegments([0xff, 0xc0, 0x00, 0xff, 0x00]), '.jpg', null);
  assertBothReaders(jpegWithSegments(jpegSof(96, 48, 0xc0, 6)), '.jpg', null);
  assertBothReaders(jpegWithSegments(jpegSof(0, 48)), '.jpg', null);
});

test('WebP parser handles VP8L, VP8, odd chunk padding, and invalid chunk boundaries', () => {
  const lossless = Uint8Array.from([0x2f, 49, 0xc0, 4, 0]);
  assertBothReaders(webp([['VP8L', lossless]]), '.webp', { width: 50, height: 20 });
  const lossy = new Uint8Array(10);
  lossy.set([0, 0, 0, 0x9d, 0x01, 0x2a]);
  new DataView(lossy.buffer).setUint16(6, 320, true);
  new DataView(lossy.buffer).setUint16(8, 180, true);
  assertBothReaders(webp([['VP8 ', lossy]]), '.webp', { width: 320, height: 180 });
  assertBothReaders(webp([['EXIF', [0x7f]], ['VP8X', vp8x(800, 600)]]), '.webp', {
    width: 800, height: 600,
  });
  assertBothReaders(webp([['VP8X', [0, 0, 0, 0, 0, 0, 0, 0, 0]]]), '.webp', null);
  assertBothReaders(webp([['VP8L', [0, 0, 0, 0, 0]]]), '.webp', null);
  assertBothReaders(webp([['VP8 ', new Array(10).fill(0)]]), '.webp', null);
  assertBothReaders(webp([['VP8X', vp8x(1, 1)]], 12), '.webp', null);
  const badContainer = webp([['VP8X', vp8x(800, 600)]]);
  badContainer[8] = 0;
  assertBothReaders(badContainer, '.webp', null);
});

test('raw dimension dispatch accepts ArrayBuffer and suffix hints without applying upstream caps', () => {
  const bytes = pngHeader(25_000, 12_000);
  assertBothReaders(bytes.buffer, '.PNG', { width: 25_000, height: 12_000 });
  assertBothReaders(pngHeader(1280, 720), '', { width: 1280, height: 720 });
  assertBothReaders(new Uint8Array(24), '.png', null);
  assertBothReaders(new Uint8Array(24), '.jpg', null);
  assertBothReaders(new Uint8Array(24), '.webp', null);
  assertBothReaders(new Uint8Array(24), '.tiff', null);
});

test('classifier and metadata facade retain their original capped classification behavior', () => {
  assert.equal(MAX_IMAGE_DIMENSION, 16384);
  assert.equal(MAX_IMAGE_PIXELS, 50_000_000);
  assert.equal(classifyImageDimensions({ width: 3600, height: 1000 }).aspect, 'ultrawide');
  assert.equal(classifyImageDimensions({ width: 2000, height: 1000 }).aspect, 'wide');
  assert.equal(classifyImageDimensions({ width: 1200, height: 1000 }).aspect, 'landscape');
  assert.equal(classifyImageDimensions({ width: 1000, height: 1000 }).aspect, 'square');
  assert.equal(classifyImageDimensions({ width: 500, height: 1000 }).aspect, 'portrait');
  assert.equal(classifyImageDimensions({ width: 3600, height: 1000 }).taskMode, 'banner');
  assert.equal(classifyImageDimensions({ width: 2000, height: 1000 }).wide, true);
  assert.equal(classifyImageDimensions({ width: 1, height: 0 }), null);
  assert.equal(classifyImageDimensions({ width: 1.5, height: 1 }), null);
  assert.equal(classifyImageDimensions({ width: MAX_IMAGE_DIMENSION + 1, height: 1 }), null);
  assert.equal(classifyImageDimensions({ width: 10001, height: 5000 }), null);
  assert.deepEqual(readImageMetadata(pngHeader(1280, 720), '.png')?.aspect, 'wide');
  assert.equal(readImageMetadata(pngHeader(25_000, 12_000), '.png'), null);
  assert.equal(readImageMetadata(new Uint8Array(24), '.png'), null);
});
