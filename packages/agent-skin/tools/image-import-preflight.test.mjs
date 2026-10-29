import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import vm from 'node:vm';
import { readRawDimensions } from '../vendor/dream-image-metadata.mjs';

const PACKAGE = join(dirname(fileURLToPath(import.meta.url)), '..');
const MAX_HEADER_BYTES = 2 * 1024 * 1024;
const source = await readFile(join(PACKAGE, 'image-settings.js'), 'utf8');
const classicReaderPath = join(PACKAGE, 'image-metadata-reader.js');
const classicReaderSource = await readFile(classicReaderPath, 'utf8');
const classicReaderContext = { Uint8Array, ArrayBuffer };
new vm.Script(classicReaderSource, { filename: classicReaderPath }).runInNewContext(classicReaderContext);
const productionReadRawDimensions = classicReaderContext.AGENT_SKIN_READ_RAW_DIMENSIONS;
assert.equal(typeof productionReadRawDimensions, 'function');
const context = { Uint8Array, ArrayBuffer, AGENT_SKIN_READ_RAW_DIMENSIONS: productionReadRawDimensions };
new vm.Script(source, { filename: join(PACKAGE, 'image-settings.js') }).runInNewContext(context);

function pngHeader(width, height) {
  const bytes = new Uint8Array(24);
  bytes.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  bytes.set([0, 0, 0, 13, 0x49, 0x48, 0x44, 0x52], 8);
  const view = new DataView(bytes.buffer);
  view.setUint32(16, width, false);
  view.setUint32(20, height, false);
  return bytes;
}

function jpegWithLongApp(width, height, appSegments = 20) {
  const segmentLength = 65_535;
  const sofLength = 10;
  const bytes = new Uint8Array(2 + appSegments * (segmentLength + 2) + sofLength + 2);
  bytes.set([0xff, 0xd8]);
  let offset = 2;
  for (let index = 0; index < appSegments; index++) {
    bytes[offset] = 0xff;
    bytes[offset + 1] = 0xe1;
    bytes[offset + 2] = 0xff;
    bytes[offset + 3] = 0xff;
    offset += segmentLength + 2;
  }
  bytes.set([0xff, 0xc0], offset);
  const lengthOffset = offset + 2;
  new DataView(bytes.buffer).setUint16(lengthOffset, 8, false);
  bytes[lengthOffset + 2] = 8;
  new DataView(bytes.buffer).setUint16(lengthOffset + 3, height, false);
  new DataView(bytes.buffer).setUint16(lengthOffset + 5, width, false);
  bytes[lengthOffset + 7] = 3;
  return bytes;
}

function webpWithLargeExif(width, height, exifBytes) {
  const pad = exifBytes & 1;
  const bytes = new Uint8Array(12 + 8 + exifBytes + pad + 8 + 10);
  bytes.set([0x52, 0x49, 0x46, 0x46], 0);
  new DataView(bytes.buffer).setUint32(4, bytes.length - 8, true);
  bytes.set([0x57, 0x45, 0x42, 0x50, 0x45, 0x58, 0x49, 0x46], 8);
  new DataView(bytes.buffer).setUint32(16, exifBytes, true);
  const vp8x = 20 + exifBytes + pad;
  bytes.set([0x56, 0x50, 0x38, 0x58], vp8x);
  new DataView(bytes.buffer).setUint32(vp8x + 4, 10, true);
  const widthMinusOne = width - 1;
  const heightMinusOne = height - 1;
  bytes[vp8x + 12] = widthMinusOne & 0xff;
  bytes[vp8x + 13] = (widthMinusOne >>> 8) & 0xff;
  bytes[vp8x + 14] = (widthMinusOne >>> 16) & 0xff;
  bytes[vp8x + 15] = heightMinusOne & 0xff;
  bytes[vp8x + 16] = (heightMinusOne >>> 8) & 0xff;
  bytes[vp8x + 17] = (heightMinusOne >>> 16) & 0xff;
  return bytes;
}

function makeFile({ bytes, size = bytes.length, type, pauseSecondRead,
  sliceThrows = 0, rejectRead = 0, invalidRead = 0 } = {}) {
  const reads = [];
  let releaseSecondRead;
  const secondRead = pauseSecondRead ? new Promise(resolve => { releaseSecondRead = resolve; }) : null;
  return {
    size,
    type,
    reads,
    releaseSecondRead,
    slice(start, end) {
      const read = reads.length + 1;
      reads.push([start, end]);
      if (sliceThrows === read) throw new Error('native slice details must stay private');
      return {
        async arrayBuffer() {
          if (read === 2 && secondRead) await secondRead;
          if (rejectRead === read) throw new Error('native read details must stay private');
          if (invalidRead === read) return {};
          const part = bytes.subarray(start, end);
          return part.buffer.slice(part.byteOffset, part.byteOffset + part.byteLength);
        },
      };
    },
  };
}

function makeFixture({ width = 2048, height = 1024, decodeError = false } = {}) {
  const decodedURLs = [];
  const created = [];
  const revoked = [];
  class Image {
    naturalWidth = width;
    naturalHeight = height;
    onload = null;
    onerror = null;
    removeAttribute(name) {
      assert.equal(name, 'src');
    }
    set src(value) {
      if (!value) return;
      decodedURLs.push(value);
      queueMicrotask(() => decodeError
        ? this.onerror?.(new Error('native details must stay private')) : this.onload?.());
    }
  }
  const api = context.createImageSettings({
    document: {
      createElement(name) {
        assert.equal(name, 'canvas');
        return {
          width: 0,
          height: 0,
          getContext(kind) {
            assert.equal(kind, '2d');
            return { fillStyle: '', fillRect() {}, drawImage() {} };
          },
          toDataURL() { return 'data:image/png;base64,AAAA'; },
        };
      },
    },
    Image,
    URL: {
      createObjectURL() { const url = 'blob:fixture-' + (created.length + 1); created.push(url); return url; },
      revokeObjectURL(url) { revoked.push(url); },
    },
    setTimeout,
    clearTimeout,
    performance,
  });
  return { api, decodedURLs, created, revoked };
}

test('PNG IHDR dimensions above 48 MP are rejected before image decoding', async () => {
  const fixture = makeFixture({ width: 24_000, height: 2_001 });
  const file = makeFile({ bytes: pngHeader(24_000, 2_001), type: 'image/png' });
  await assert.rejects(fixture.api.importImage(file, 'avatar'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'image-too-large');
  assert.equal(file.reads.length, 2);
  assert.deepEqual(file.reads, [[0, 12], [0, 24]]);
  assert.deepEqual(fixture.decodedURLs, []);
  assert.deepEqual(fixture.created, []);
});

test('JPEG dimensions are found after multiple maximum-size APP segments', async () => {
  const bytes = jpegWithLongApp(24_000, 2_001);
  const fixture = makeFixture({ width: 24_000, height: 2_001 });
  const file = makeFile({ bytes, type: 'image/jpeg' });
  await assert.rejects(fixture.api.importImage(file, 'avatar'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'image-too-large');
  assert.ok(bytes.length > 1_300_000, 'fixture exercises a long APP prefix');
  assert.deepEqual(file.reads, [[0, 12], [0, Math.min(MAX_HEADER_BYTES, file.size)]]);
  assert.deepEqual(fixture.decodedURLs, []);
  assert.deepEqual(fixture.created, []);
});

test('WebP dimensions are found after a large complete metadata chunk', async () => {
  const bytes = webpWithLargeExif(24_000, 2_001, 1_800_000);
  const fixture = makeFixture({ width: 24_000, height: 2_001 });
  const file = makeFile({ bytes, type: 'image/webp' });
  await assert.rejects(fixture.api.importImage(file, 'avatar'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'image-too-large');
  assert.ok(bytes.length < MAX_HEADER_BYTES);
  assert.deepEqual(file.reads, [[0, 12], [0, Math.min(MAX_HEADER_BYTES, file.size)]]);
  assert.deepEqual(fixture.decodedURLs, []);
  assert.deepEqual(fixture.created, []);
});

test('a WebP chunk beyond the 2 MiB read cap falls back to decode and final dimension validation', async () => {
  const bytes = new Uint8Array(MAX_HEADER_BYTES);
  bytes.set([0x52, 0x49, 0x46, 0x46], 0);
  new DataView(bytes.buffer).setUint32(4, 3 * 1024 * 1024 - 8, true);
  bytes.set([0x57, 0x45, 0x42, 0x50, 0x45, 0x58, 0x49, 0x46], 8);
  new DataView(bytes.buffer).setUint32(16, 3 * 1024 * 1024, true);
  assert.deepEqual(productionReadRawDimensions(bytes, '.webp'), readRawDimensions(bytes, '.webp'));
  const fixture = makeFixture({ width: 24_000, height: 2_001 });
  const file = makeFile({ bytes, size: 3 * 1024 * 1024, type: 'image/webp' });
  assert.equal(readRawDimensions(bytes, '.webp'), null);
  await assert.rejects(fixture.api.importImage(file, 'avatar'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'image-too-large');
  assert.deepEqual(file.reads, [[0, 12], [0, MAX_HEADER_BYTES]]);
  assert.deepEqual(fixture.decodedURLs, ['blob:fixture-1']);
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('failed signature reads reject safely while unreadable headers fall back to final decoding', async () => {
  for (const options of [
    { sliceThrows: 1 },
    { rejectRead: 1 },
    { invalidRead: 1 },
  ]) {
    const fixture = makeFixture();
    await assert.rejects(fixture.api.importImage(makeFile({
      bytes: pngHeader(2048, 1024), type: 'image/png', ...options,
    }), 'avatar'), error => error.reason === 'asset-invalid' && error.causeCode === 'unsupported-type');
    assert.deepEqual(fixture.created, []);
  }

  for (const options of [
    { sliceThrows: 2 },
    { rejectRead: 2 },
    { invalidRead: 2 },
  ]) {
    const fixture = makeFixture();
    const result = await fixture.api.importImage(makeFile({
      bytes: pngHeader(2048, 1024), type: 'image/png', ...options,
    }), 'avatar');
    assert.deepEqual([result.width, result.height], [512, 512]);
    assert.equal(fixture.created.length, 1);
    assert.deepEqual(fixture.revoked, fixture.created);
  }
});

test('a declared MIME outside the supported set is rejected before header parsing and decode', async () => {
  const fixture = makeFixture();
  await assert.rejects(fixture.api.importImage(makeFile({
    bytes: pngHeader(2048, 1024), type: 'image/gif',
  }), 'avatar'), error => error.reason === 'asset-invalid' && error.causeCode === 'unsupported-type');
  assert.deepEqual(fixture.created, []);
});

test('an unexpected raw-header parser error falls back to the decoder without exposing internals', async () => {
  const original = context.AGENT_SKIN_READ_RAW_DIMENSIONS;
  context.AGENT_SKIN_READ_RAW_DIMENSIONS = () => { throw new Error('private parser details'); };
  try {
    const fixture = makeFixture();
    const result = await fixture.api.importImage(makeFile({
      bytes: pngHeader(2048, 1024), type: 'image/png',
    }), 'avatar');
    assert.deepEqual([result.width, result.height], [512, 512]);
    assert.deepEqual(fixture.revoked, fixture.created);
  } finally {
    context.AGENT_SKIN_READ_RAW_DIMENSIONS = original;
  }
});

test('canceling a pending bounded-header read releases it without starting decode', async () => {
  const fixture = makeFixture();
  const file = makeFile({ bytes: pngHeader(24_000, 2_001), type: 'image/png', pauseSecondRead: true });
  const pending = fixture.api.importImage(file, 'avatar');
  await new Promise(resolve => setTimeout(resolve, 0));
  try {
    assert.equal(file.reads.length, 2, 'the bounded header read should be pending');
    assert.equal(fixture.api.cancelImport(), true);
  } finally {
    fixture.api.cancelImport();
    file.releaseSecondRead?.(pngHeader(24_000, 2_001).buffer);
  }
  await assert.rejects(pending, error => error.reason === 'operation-cancelled');
  assert.deepEqual(fixture.decodedURLs, []);
  assert.deepEqual(fixture.created, []);
});
