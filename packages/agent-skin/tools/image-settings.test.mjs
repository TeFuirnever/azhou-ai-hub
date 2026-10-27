import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import vm from 'node:vm';

const SOURCE_PATH = join(dirname(fileURLToPath(import.meta.url)), '..', 'image-settings.js');
const MAX_INPUT_BYTES = 31_457_280;
const source = await readFile(SOURCE_PATH, 'utf8');
const createImageSettings = vm.runInNewContext(`${source}\ncreateImageSettings`, {});
const PNG_SIGNATURE = Uint8Array.of(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a);

function makeFile({ size = 64, type = 'image/png', signature = PNG_SIGNATURE } = {}) {
  return {
    size,
    type,
    slice(start, end) {
      return {
        async arrayBuffer() {
          const bytes = signature.slice(start, end);
          return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        },
      };
    },
  };
}

function makeFixture(options = {}) {
  const drawCalls = [];
  const revoked = [];
  const created = [];
  const canvases = [];
  const timers = [];
  const pausedYields = [];
  let now = 0;
  function runDueTimers() {
    let next;
    do {
      next = timers.find(timer => !timer.cleared && !timer.fired && timer.due <= now);
      if (next) {
        next.fired = true;
        next.callback();
      }
    } while (next);
  }
  const image = {
    naturalWidth: options.width ?? 2048,
    naturalHeight: options.height ?? 1024,
    onload: null,
    onerror: null,
    released: false,
    removeAttribute(name) {
      assert.equal(name, 'src');
      image.released = true;
    },
  };
  Object.defineProperty(image, 'src', {
    set(value) {
      if (!value) { image.released = true; return; }
      if (options.decode === 'pending') return;
      queueMicrotask(() => {
        if (image.released) return;
        if (options.decode === 'error') image.onerror?.(new Error('decoder detail must not escape'));
        else image.onload?.();
      });
    },
  });
  const environment = {
    document: {
      createElement(name) {
        assert.equal(name, 'canvas');
        const canvas = {
          width: 0,
          height: 0,
          getContext() {
            return {
              fillStyle: '',
              fillRect() {},
              drawImage(...args) { drawCalls.push({ canvas, args }); },
              getImageData(_x, _y, width, height) {
                if (options.imageData) return options.imageData;
                const data = new Uint8ClampedArray(width * height * 4);
                for (let index = 3; index < data.length; index += 4) data[index] = 255;
                return { data, width, height };
              },
            };
          },
          toDataURL() {
            const prefix = 'data:image/png;base64,';
            return prefix + 'A'.repeat(Math.max(4, (options.pngLength ?? 64) - prefix.length));
          },
        };
        canvases.push(canvas);
        return canvas;
      },
    },
    Image: class { constructor() { return image; } },
    URL: {
      createObjectURL() { const value = `blob:fixture-${created.length + 1}`; created.push(value); return value; },
      revokeObjectURL(value) { revoked.push(value); },
    },
    setTimeout(callback, delay) {
      const timer = { callback, delay, due: now + delay, cleared: false, fired: false, native: null };
      timers.push(timer);
      if (delay === 0) {
        timer.native = setTimeout(() => {
          if (timer.cleared) return;
          const fire = () => {
            if (timer.cleared || timer.fired) return false;
            timer.fired = true;
            now += options.zeroDelayAdvanceMs ?? 0;
            callback();
            runDueTimers();
            return true;
          };
          if (options.pauseYield) pausedYields.push(fire);
          else fire();
        }, 0);
      }
      return timer;
    },
    clearTimeout(timer) {
      if (!timer) return;
      timer.cleared = true;
      if (timer.native) clearTimeout(timer.native);
    },
    performance: { now: () => now },
  };
  return {
    api: createImageSettings(environment),
    image,
    canvases,
    drawCalls,
    created,
    revoked,
    timers,
    hasPausedYield() { return pausedYields.length > 0; },
    resumeYield() { return pausedYields.shift()?.() ?? false; },
    advance(milliseconds) {
      now += milliseconds;
      runDueTimers();
    },
  };
}

function edgeImageData() {
  const width = 768;
  const height = 512;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let index = 3; index < data.length; index += 4) data[index] = 255;
  for (let y = 140; y < 240; y++) {
    for (let x = 210; x < 340; x++) {
      const index = (y * width + x) * 4;
      data[index] = data[index + 1] = data[index + 2] = 255;
    }
  }
  return { data, width, height };
}

function diagonalEdgeImageData() {
  const width = 768;
  const height = 512;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let index = 3; index < data.length; index += 4) data[index] = 255;
  for (let x = 200; x <= 400; x++) {
    for (let offset = -1; offset <= 1; offset++) {
      const y = 600 - x + offset;
      const index = (y * width + x) * 4;
      data[index] = data[index + 1] = data[index + 2] = 255;
    }
  }
  return { data, width, height };
}

function uniformImageData() {
  const width = 768;
  const height = 512;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let index = 3; index < data.length; index += 4) data[index] = 255;
  return { data, width, height };
}

test('a landscape avatar is normalized to 512 square using a centered cover crop', async () => {
  const fixture = makeFixture();

  const result = await fixture.api.importImage(makeFile(), 'avatar');

  assert.equal(result.width, 512);
  assert.equal(result.height, 512);
  assert.equal(result.bytes, result.dataURL.length);
  assert.deepEqual(fixture.drawCalls[0].args.slice(1), [-256, 0, 1024, 512]);
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('a portrait avatar crops its top and bottom symmetrically', async () => {
  const fixture = makeFixture({ width: 1000, height: 2000 });

  const result = await fixture.api.importImage(makeFile(), 'avatar');

  assert.deepEqual([result.width, result.height], [512, 512]);
  assert.deepEqual(fixture.drawCalls[0].args.slice(1), [0, -256, 512, 1024]);
});

test('PNG, JPEG and WebP bytes are accepted only when their declared type matches', async t => {
  const formats = [
    ['image/png', PNG_SIGNATURE],
    ['image/jpeg', Uint8Array.of(0xff, 0xd8, 0xff, 0x00)],
    ['image/webp', Uint8Array.of(0x52, 0x49, 0x46, 0x46, 0x00, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50)],
  ];
  for (const [type, signature] of formats) {
    await t.test(type, async () => {
      const fixture = makeFixture();
      const result = await fixture.api.importImage(makeFile({ type, signature }), 'avatar');
      assert.equal(result.width, 512);
      assert.equal(result.height, 512);
      assert.deepEqual(fixture.revoked, fixture.created);
    });
  }
  const mismatched = makeFixture();
  await assert.rejects(mismatched.api.importImage(makeFile({ type: 'image/jpeg' }), 'avatar'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'mime-mismatch');
  assert.equal(mismatched.created.length, 0);
});

test('the 30 MiB source limit includes its boundary and rejects the next byte', async () => {
  const accepted = makeFixture();
  const result = await accepted.api.importImage(makeFile({ size: MAX_INPUT_BYTES }), 'avatar');
  assert.equal(result.width, 512);

  const rejected = makeFixture();
  await assert.rejects(
    rejected.api.importImage(makeFile({ size: MAX_INPUT_BYTES + 1 }), 'avatar'),
    error => error.reason === 'asset-invalid' && error.causeCode === 'file-too-large',
  );
  assert.equal(rejected.created.length, 0);
});

test('empty inputs, forged MIME and decoder failures have stable sanitized errors', async t => {
  await t.test('empty file', async () => {
    const fixture = makeFixture();
    await assert.rejects(fixture.api.importImage(makeFile({ size: 0 }), 'avatar'), error =>
      error.reason === 'asset-invalid' && error.causeCode === 'file-empty');
    assert.equal(fixture.created.length, 0);
  });
  await t.test('unsupported bytes under an allowed MIME', async () => {
    const fixture = makeFixture();
    await assert.rejects(
      fixture.api.importImage(makeFile({ signature: Uint8Array.of(1, 2, 3, 4, 5, 6, 7, 8) }), 'avatar'),
      error => error.reason === 'asset-invalid' && error.causeCode === 'unsupported-type',
    );
    assert.equal(fixture.created.length, 0);
  });
  await t.test('decoder error does not expose the file or native message', async () => {
    const fixture = makeFixture({ decode: 'error' });
    await assert.rejects(fixture.api.importImage(makeFile(), 'avatar'), error => {
      assert.equal(error.reason, 'asset-invalid');
      assert.equal(error.causeCode, 'decode-failed');
      assert.equal(error.message, 'asset-invalid');
      return true;
    });
    assert.deepEqual(fixture.revoked, fixture.created);
  });
});

test('known decoded dimensions enforce 48 MP and warn above 16 MP', async t => {
  await t.test('48 MP plus one pixel is rejected before canvas allocation', async () => {
    const fixture = makeFixture({ width: 24_000, height: 2_001 });
    await assert.rejects(fixture.api.importImage(makeFile(), 'avatar'), error =>
      error.reason === 'asset-invalid' && error.causeCode === 'image-too-large');
    assert.equal(fixture.canvases.length, 0);
    assert.deepEqual(fixture.revoked, fixture.created);
  });
  await t.test('more than 16 MP carries a visible warning code', async () => {
    const fixture = makeFixture({ width: 4_096, height: 4_096 });
    const result = await fixture.api.importImage(makeFile(), 'avatar');
    assert.equal(result.warning, 'large-image');
  });
  await t.test('zero decoded width is rejected', async () => {
    const fixture = makeFixture({ width: 0, height: 1024 });
    await assert.rejects(fixture.api.importImage(makeFile(), 'avatar'), error =>
      error.reason === 'asset-invalid' && error.causeCode === 'invalid-dimensions');
  });
});

test('an oversized serialized avatar is rejected rather than silently recompressed', async () => {
  const fixture = makeFixture({ pngLength: 2 * 1024 * 1024 + 1 });
  await assert.rejects(fixture.api.importImage(makeFile(), 'avatar'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'output-too-large');
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('an artwork PNG over 12 MiB is rejected after contour preparation', async () => {
  const fixture = makeFixture({ imageData: edgeImageData(), pngLength: 12 * 1024 * 1024 + 1 });
  await assert.rejects(fixture.api.importImage(makeFile(), 'artwork'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'output-too-large');
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('parallel imports reject as busy and canceling the active decode releases resources', async () => {
  const fixture = makeFixture({ decode: 'pending' });
  const active = fixture.api.importImage(makeFile(), 'avatar');
  await new Promise(resolve => setTimeout(resolve, 0));

  await assert.rejects(fixture.api.importImage(makeFile(), 'avatar'), error =>
    error.reason === 'operation-busy');
  assert.equal(fixture.api.cancelImport(), true);
  await assert.rejects(active, error => error.reason === 'operation-cancelled');
  assert.equal(fixture.api.cancelImport(), false);
  assert.equal(fixture.image.released, true);
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('canceling during contour preparation prevents a late normalized result', async () => {
  const fixture = makeFixture({ imageData: edgeImageData(), pauseYield: true });
  const active = fixture.api.importImage(makeFile(), 'artwork');
  for (let attempt = 0; attempt < 10 && !fixture.hasPausedYield(); attempt++) {
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  assert.equal(fixture.hasPausedYield(), true, 'contour preparation yields between fixed row chunks');
  assert.equal(fixture.api.cancelImport(), true);
  await assert.rejects(active, error => error.reason === 'operation-cancelled');
  assert.equal(fixture.canvases.every(canvas => canvas.width === 0 && canvas.height === 0), true);
  assert.deepEqual(fixture.revoked, fixture.created);
  assert.equal(fixture.resumeYield(), true, 'the interrupted row chunk can resume and observe cancellation');
  await new Promise(resolve => setTimeout(resolve, 0));
});

test('decode and preparation timeouts settle the import with distinct reasons', async t => {
  await t.test('decode deadline is four seconds', async () => {
    const fixture = makeFixture({ decode: 'pending' });
    let outcome = 'pending';
    const result = fixture.api.importImage(makeFile(), 'avatar').then(
      value => { outcome = 'resolved'; return value; },
      error => { outcome = 'rejected'; throw error; },
    );
    await new Promise(resolve => setTimeout(resolve, 0));
    fixture.advance(3_999);
    await Promise.resolve();
    assert.equal(outcome, 'pending');
    fixture.advance(1);
    await assert.rejects(result, error =>
      error.reason === 'operation-timeout' && error.causeCode === 'decode-timeout');
    assert.deepEqual(fixture.revoked, fixture.created);
  });

  await t.test('preparation deadline is ten seconds', async () => {
    const fixture = makeFixture({ imageData: edgeImageData(), zeroDelayAdvanceMs: 1_000 });
    await assert.rejects(fixture.api.importImage(makeFile(), 'artwork'), error =>
      error.reason === 'operation-timeout' && error.causeCode === 'prepare-timeout');
    assert.deepEqual(fixture.revoked, fixture.created);
  });
});

test('artwork contours are extracted from the normalized crop and stay in output coordinates', async () => {
  const fixture = makeFixture({ width: 1200, height: 1200, imageData: edgeImageData() });

  const result = await fixture.api.importImage(makeFile(), 'artwork');

  assert.equal(result.width, 1536);
  assert.equal(result.height, 1024);
  assert.equal(result.bytes, result.dataURL.length);
  assert.ok(result.contours.length > 0);
  const allPoints = result.contours.flat();
  assert.ok(allPoints.length >= 2);
  assert.ok(allPoints.length <= 300_000);
  assert.ok(result.contours.length <= 1200);
  for (const [x, y] of allPoints) {
    assert.ok(Number.isFinite(x) && x >= 0 && x <= 1536);
    assert.ok(Number.isFinite(y) && y >= 0 && y <= 1024);
  }
  assert.deepEqual(fixture.drawCalls[0].args.slice(1), [0, -256, 1536, 1536]);
  assert.equal(fixture.drawCalls[1].args[0], fixture.canvases[0]);
  assert.deepEqual(fixture.drawCalls[1].args.slice(1), [0, 0, 768, 512]);
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('diagonal edges remain traceable through eight-neighbor contour continuation', async () => {
  const fixture = makeFixture({ imageData: diagonalEdgeImageData() });

  const result = await fixture.api.importImage(makeFile(), 'artwork');

  assert.ok(result.contours.length > 0);
  assert.ok(result.contours.some(path => path.length >= 8));
});

test('uniform artwork without usable edges is rejected and does not leak its input URL', async () => {
  const fixture = makeFixture({ imageData: uniformImageData() });

  await assert.rejects(fixture.api.importImage(makeFile(), 'artwork'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'contours-empty');
  assert.deepEqual(fixture.revoked, fixture.created);
});
