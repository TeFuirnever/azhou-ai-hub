import assert from 'node:assert/strict';
import { webcrypto, createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import vm from 'node:vm';

const SOURCE_PATH = join(dirname(fileURLToPath(import.meta.url)), '..', 'image-settings.js');
const LOCALIZATION_SOURCE_PATH = join(dirname(fileURLToPath(import.meta.url)), '..', 'localization.js');
const MAX_INPUT_BYTES = 31_457_280;
const source = await readFile(SOURCE_PATH, 'utf8');
const imageSettingsContext = {};
new vm.Script(source, { filename: SOURCE_PATH }).runInNewContext(imageSettingsContext);
const { createImageSettings } = imageSettingsContext;
const localizationSource = await readFile(LOCALIZATION_SOURCE_PATH, 'utf8');
const localizationContext = {};
new vm.Script(localizationSource, { filename: LOCALIZATION_SOURCE_PATH }).runInNewContext(localizationContext);
const { createLocalization } = localizationContext;
const PNG_SIGNATURE = Uint8Array.of(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a);
const PREVIEW_WASH_POSITIONS = ['0%', '22%', '36%', '62%', '73%', '87%', '100%'];
const PREVIEW_WASH_BASE_MIXES = new Map([
  [0, [100, 100, 100, 100, 100, 100, 100]],
  [42, [76, 82, 88, 84, 70, 35, 30]],
  [57, [67, 76, 84, 78, 59, 12, 5]],
  [75, [57, 68, 79, 71, 46, 0, 0]],
]);

function expectedPreviewWash(strength) {
  const base = '#10121c';
  return 'linear-gradient(90deg,' + PREVIEW_WASH_BASE_MIXES.get(strength).map((percent, index) =>
    `color-mix(in srgb, ${base} ${percent}%, transparent) ${PREVIEW_WASH_POSITIONS[index]}`,
  ).join(',') + ')';
}

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
  const blobs = [];
  const canvases = [];
  const elements = [];
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
  const images = [];
  function makeElement(tagName) {
    const attributes = new Map();
    const element = {
      tagName: tagName.toUpperCase(),
      style: {
        cssText: '',
        properties: new Map(),
        setProperty(name, value) { this.properties.set(name, String(value)); },
        getPropertyValue(name) { return this.properties.get(name) || ''; },
      },
      children: [],
      get firstChild() {return element.children[0];},
      removeChild(child) {element.children.splice(element.children.indexOf(child),1);},
      attributes,
      disabled: false,
      value: '',
      textContent: '',
      setAttribute(name, value) { attributes.set(name, String(value)); },
      getAttribute(name) { return attributes.get(name) ?? null; },
      addEventListener(type, listener) {
        if (!element.listeners.has(type)) element.listeners.set(type, []);
        element.listeners.get(type).push(listener);
      },
      append(...children) { for (const child of children) element.appendChild(child); },
      appendChild(child) { element.children.push(child); child.parentNode = element; return child; },
      remove() {
        element.removed = true;
        if (element.parentNode?.children) {
          element.parentNode.children = element.parentNode.children.filter(child => child !== element);
        }
      },
      click() {
        element.clickCount = (element.clickCount || 0) + 1;
        if (tagName === 'a' && options.downloadError) throw new Error('download unavailable');
        for (const listener of element.listeners.get('click') || []) listener({ target: element });
      },
      removeAttribute(name) { attributes.delete(name); },
      showModal() { element.showModalCalls = (element.showModalCalls || 0) + 1; element.open = true; },
      show() { element.showCalls = (element.showCalls || 0) + 1; element.open = true; },
      close() { element.open = false; },
      listeners: new Map(),
    };
    elements.push(element);
    return element;
  }
  function makeImage(index) {
    const dimensions = options.imageDimensions?.[index];
    const current = {
      naturalWidth: dimensions?.[0] ?? options.width ?? 2048,
      naturalHeight: dimensions?.[1] ?? options.height ?? 1024,
      onload: null,
      onerror: null,
      released: false,
      removeAttribute(name) {
        assert.equal(name, 'src');
        current.released = true;
      },
    };
    Object.defineProperty(current, 'src', {
      set(value) {
        if (options.dimensionsForSource) [current.naturalWidth,current.naturalHeight] = options.dimensionsForSource(value);
        if (!value) { current.released = true; return; }
        current.released = false;
        if (options.decode === 'pending' || options.decodeForSource?.(value) === 'pending') return;
        queueMicrotask(() => {
          if (current.released) return;
          if (options.decode === 'error' || options.decodeForSource?.(value) === 'error') current.onerror?.(new Error('decoder detail must not escape'));
          else current.onload?.();
        });
      },
    });
    images.push(current);
    return current;
  }
  const image = makeImage(0);
  let imageInstances = 0;
  const ImageConstructor = class {
    constructor() {
      const index = imageInstances++;
      return index === 0 ? image : makeImage(index);
    }
  };
  const environment = {
    document: {
      body: makeElement('body'),
      createElement(name) {
        if (name !== 'canvas') return makeElement(name);
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
    indexedDB: options.indexedDB,
    crypto: options.crypto ?? webcrypto, TextEncoder, TextDecoder, Blob, btoa, AbortController,
    settingsNamespace: options.settingsNamespace,
    localization: options.localization,
    appearanceAvatar: options.appearanceAvatar,
    themeConfig: options.themeConfig,
    getAppearance: options.getAppearance,
    Image: ImageConstructor,
    URL: {
      createObjectURL(blob) { blobs.push(blob); const value = `blob:fixture-${created.length + 1}`; created.push(value); return value; },
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
    environment,
    image,
    images,
    canvases,
    drawCalls,
    created,
    blobs,
    revoked,
    timers,
    hasPausedYield() { return pausedYields.length > 0; },
    resumeYield() { return pausedYields.shift()?.() ?? false; },
    advance(milliseconds) {
      now += milliseconds;
      runDueTimers();
    },
    elements,
  };
}

function makeIndexedDB(initialRecord, options = {}) {
  const state = { record: initialRecord, themeRecord: options.themeRecord, libraryRecord: options.libraryRecord, dreamRecord: options.dreamRecord, puts: 0, putSuccesses: 0, completions: 0,
    deletes: 0, clears: 0, closeCalls: 0, opens: [], transactions: [], heldRequests: [], releaseOpen: null };
  let hasStore = false;
  let connectionClosed = false;
  const database = {
    objectStoreNames: { contains: name => name === 'settings' && hasStore },
    createObjectStore(name) { assert.equal(name, 'settings'); hasStore = true; },
    close() {state.closeCalls++;connectionClosed=true;},
    transaction(storeName, mode) {
      if(connectionClosed)throw Object.assign(new Error('closed database connection'),{name:'InvalidStateError'});
      assert.equal(storeName, 'settings');
      assert.ok(mode === 'readonly' || mode === 'readwrite');
      if (options.transactionFailure && mode === 'readwrite') throw options.transactionFailure;
      let pendingRequests = 0;
      const deletedRecords = new Set();
      let stagedRecord;
      let stagedThemeRecord;
      let stagedLibraryRecord;
      let stagedDreamRecord;
      let aborted = false;
      let transactionFinished = false;
      let completionQueued = false;
      const transaction = {
        mode,
        completed: false,
        aborted: false,
        error: null,
        abort() {
          if (aborted || transactionFinished) return;
          aborted = true;
          transaction.aborted = true;
          queueMicrotask(() => {
            transactionFinished = true;
            transaction.onabort?.({ target: transaction });
          });
        },
        request(kind, start) {
          const request = { result: undefined, error: null };
          pendingRequests++;
          const release = (ignoreAbort = false) => {
            if (aborted && !ignoreAbort) return false;
            start(request);
            if (kind === 'put' && !request.error) state.putSuccesses++;
            options.afterRequest?.({ kind, request, transaction, state });
            pendingRequests--;
            if (pendingRequests === 0 && !completionQueued) {
              completionQueued = true;
              queueMicrotask(() => {
                completionQueued = false;
                if (aborted || transactionFinished || pendingRequests !== 0) return;
                transactionFinished = true;
                transaction.completed = true;
                if (stagedRecord !== undefined) state.record = structuredClone(stagedRecord);
                if (stagedThemeRecord !== undefined) state.themeRecord = structuredClone(stagedThemeRecord);
                if (stagedLibraryRecord !== undefined) state.libraryRecord = structuredClone(stagedLibraryRecord);
                if (stagedDreamRecord !== undefined) state.dreamRecord = structuredClone(stagedDreamRecord);
                for (const name of deletedRecords) state[name] = undefined;
                state.completions++;
                transaction.oncomplete?.({ target: transaction });
              });
            }
            return true;
          };
          if (options.holdRequests) {
            state.heldRequests.push({ kind, release });
            options.onHeldRequest?.(state);
          }
          else queueMicrotask(() => release());
          return request;
        },
        objectStore(name) {
          assert.equal(name, 'settings');
          return {
            get(key) {
              assert.ok(['images', 'themeState', 'appearancePresets', 'dreamThemes'].includes(key));
              return transaction.request('get', request => {
                const record = key === 'images' ? state.record : key === 'themeState' ? state.themeRecord : key === 'appearancePresets' ? state.libraryRecord : state.dreamRecord;
                request.result = record === undefined ? undefined : structuredClone(record);
                request.onsuccess?.({ target: request });
              });
            },
            put(value, key) {
              assert.equal(mode, 'readwrite');
              assert.ok(['images', 'themeState', 'appearancePresets', 'dreamThemes'].includes(key));
              state.puts++;
              return transaction.request('put', request => {
                if (options.putError) {
                  request.error = options.putError;
                  request.onerror?.({ target: request });
                  try { transaction.abort(); } catch {}
                  return;
                }
                if (key === 'images') stagedRecord = structuredClone(value);
                else if (key === 'themeState') stagedThemeRecord = structuredClone(value);
                else if (key === 'appearancePresets') stagedLibraryRecord = structuredClone(value);
                else stagedDreamRecord = structuredClone(value);
                request.result = key;
                request.onsuccess?.({ target: request });
              });
            },
            delete(key) {
              assert.equal(mode,'readwrite');state.deletes++;
              const name={images:'record',themeState:'themeRecord',appearancePresets:'libraryRecord',dreamThemes:'dreamRecord'}[key];
              assert.ok(name);
              return transaction.request('delete',request=>{deletedRecords.add(name);request.onsuccess?.({target:request});});
            },
            clear() { state.clears++; throw new Error('unexpected clear'); },
          };
        },
      };
      state.transactions.push(transaction);
      return transaction;
    },
  };
  const indexedDB = {
    open(name, version) {
      state.opens.push({ name, version });
      const request = { result: database, error: null, transaction: null };
      const deliver = () => {
        connectionClosed=false;
        if (options.openBlocked) {
          request.onblocked?.({ target: request });
          return false;
        }
        if (!hasStore) {
          request.transaction = {};
          request.onupgradeneeded?.({ oldVersion: 0, newVersion: version, target: request });
        }
        queueMicrotask(() => request.onsuccess?.({ target: request }));
        return true;
      };
      if (options.holdOpen) state.releaseOpen = () => {
        if (!state.releaseOpen) return false;
        state.releaseOpen = null;
        return deliver();
      };
      else queueMicrotask(deliver);
      return request;
    },
  };
  state.releaseHeldRequests = (ignoreAbort = false) => state.heldRequests.splice(0)
    .map(item => item.release(ignoreAbort));
  return { indexedDB, state };
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
  await assert.rejects(fixture.api.save({}), error => error.reason === 'operation-busy');
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

test('rectangular contours keep a straight continuation through an eight-neighbor branch', async () => {
  const fixture = makeFixture({ imageData: edgeImageData() });

  const result = await fixture.api.importImage(makeFile(), 'artwork');

  assert.equal(result.contours.length, 1, 'the connected rectangle should stay one contour');
  assert.ok(result.contours[0].length > 300, 'the contour should cover the rectangle rather than a short branch');
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('uniform artwork without usable edges is rejected and does not leak its input URL', async () => {
  const fixture = makeFixture({ imageData: uniformImageData() });

  await assert.rejects(fixture.api.importImage(makeFile(), 'artwork'), error =>
    error.reason === 'asset-invalid' && error.causeCode === 'contours-empty');
  assert.deepEqual(fixture.revoked, fixture.created);
});

test('loading settings without IndexedDB returns a copy of the supplied defaults', async () => {
  const fixture = makeFixture();
  const defaults = {
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    introTitle: 'Synthetic default',
    introCaption: '',
    artworkSubtitle: 'Generated only',
    wallpaperStrength: 42,
  };

  const loaded = await fixture.api.load(defaults);

  assert.equal(loaded.reason, 'settings-unavailable');
  assert.equal(loaded.baseline, undefined);
  assert.equal(loaded.settings.schemaVersion, 1);
  assert.equal(loaded.settings.introCaption, '');
  assert.deepEqual(JSON.parse(JSON.stringify(loaded.settings)), {
    schemaVersion: 1,
    ...defaults,
  });
});

test('loadSnapshot distinguishes a missing record and freezes only resolved settings', async () => {
  const storage = makeIndexedDB(undefined);
  const fixture = makeFixture({ indexedDB: storage.indexedDB });
  const defaults = {
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    introTitle: 'Bundled title',
    wallpaperStrength: 42,
  };

  const snapshot = await fixture.api.loadSnapshot(defaults);

  assert.equal(snapshot.status, 'missing');
  assert.equal(snapshot.settings.introTitle, 'Bundled title');
  assert.deepEqual(JSON.parse(JSON.stringify(snapshot.explicitText)), {
    introTitle: true,
    introCaption: false,
    artworkSubtitle: false,
  });
  assert.equal(Object.hasOwn(snapshot, 'baseline'), false);
  assert.equal(Object.isFrozen(snapshot), true);
  assert.equal(Object.isFrozen(snapshot.settings), true);
  assert.equal(Object.isFrozen(snapshot.settings.contours), true);
  assert.equal(Object.isFrozen(snapshot.settings.contours[0]), true);
  assert.equal(Object.isFrozen(snapshot.settings.contours[0][0]), true);
  assert.equal(storage.state.transactions.at(-1).mode, 'readonly');
  assert.equal(storage.state.puts, 0);
  assert.equal(storage.state.deletes, 0);
  assert.equal(storage.state.clears, 0);
});

test('loadSnapshot returns normalized custom settings without the raw baseline', async () => {
  const record = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    introTitle: 'Saved title',
    wallpaperStrength: 17,
  };
  const storage = makeIndexedDB(record);
  const fixture = makeFixture({
    indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]],
  });

  const snapshot = await fixture.api.loadSnapshot({
    avatar: 'data:image/png;base64,CCCC',
    artwork: 'data:image/png;base64,DDDD',
    contours: [[[2, 2], [3, 3]]],
    introTitle: 'Bundled title',
    introCaption: 'Bundled caption',
    artworkSubtitle: 'Bundled subtitle',
    wallpaperStrength: 42,
  });

  assert.equal(snapshot.status, 'valid');
  assert.equal(snapshot.settings.introTitle, 'Saved title');
  assert.equal(snapshot.settings.wallpaperStrength, 17);
  assert.deepEqual(JSON.parse(JSON.stringify(snapshot.explicitText)), {
    introTitle: true,
    introCaption: true,
    artworkSubtitle: true,
  });
  assert.equal(Object.hasOwn(snapshot, 'baseline'), false);
  assert.deepEqual(storage.state.record, record);
  assert.equal(storage.state.transactions.at(-1).mode, 'readonly');
  assert.equal(storage.state.puts, 0);
  assert.equal(storage.state.deletes, 0);
  assert.equal(storage.state.clears, 0);
});

test('loadSnapshot reports an unknown stored image schema as read-only failure', async () => {
  const invalid = { schemaVersion: 7, futureField: { keep: true } };
  const storage = makeIndexedDB(invalid);
  const fixture = makeFixture({ indexedDB: storage.indexedDB });

  const snapshot = await fixture.api.loadSnapshot({
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    wallpaperStrength: 42,
  });

  assert.equal(snapshot.status, 'failure');
  assert.equal(snapshot.reason, 'settings-blocked');
  assert.equal(snapshot.readOnly, true);
  assert.equal(Object.hasOwn(snapshot, 'settings'), false);
  assert.deepEqual(storage.state.record, invalid);
  assert.equal(storage.state.puts, 0);
  assert.equal(storage.state.deletes, 0);
  assert.equal(storage.state.clears, 0);
});

test('loadSnapshot identifies a temporarily blocked database without declaring unknown data', async () => {
  const storage=makeIndexedDB(undefined,{openBlocked:true});
  const fixture=makeFixture({indexedDB:storage.indexedDB});
  const snapshot=await fixture.api.loadSnapshot({avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[],wallpaperStrength:42});
  assert.equal(snapshot.status,'failure');assert.equal(snapshot.reason,'settings-blocked');assert.notEqual(snapshot.readOnly,true);
  assert.equal(storage.state.puts,0);fixture.api.dispose();
});

test('loadSnapshot reports a storage read failure separately from a missing record', async () => {
  const fixture = makeFixture({ indexedDB: { open() { throw new Error('private storage detail'); } } });

  const snapshot = await fixture.api.loadSnapshot({
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [],
    wallpaperStrength: 42,
  });

  assert.equal(snapshot.status, 'failure');
  assert.equal(snapshot.reason, 'settings-unavailable');
  assert.equal(Object.hasOwn(snapshot, 'settings'), false);
});

test('loadSnapshot reports a pending read timeout as failure, not as a missing record', async () => {
  const storage = makeIndexedDB(undefined, { holdRequests: true });
  const fixture = makeFixture({ indexedDB: storage.indexedDB });
  const loading = fixture.api.loadSnapshot({
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    introTitle: 'Safe default',
    wallpaperStrength: 42,
  });
  for (let attempt = 0; attempt < 10 && storage.state.heldRequests.length === 0; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  assert.equal(storage.state.heldRequests.length, 3, 'all three readonly settings reads are pending');

  fixture.advance(5_000);
  const snapshot = await loading;

  assert.equal(snapshot.status, 'failure');
  assert.equal(snapshot.reason, 'operation-timeout');
  assert.equal(Object.hasOwn(snapshot, 'settings'), false);
  assert.equal(Object.hasOwn(snapshot, 'baseline'), false);
  assert.equal(storage.state.transactions[0].aborted, true);
  assert.equal(storage.state.puts, 0);
  assert.deepEqual(storage.state.releaseHeldRequests(true), [true, true, true]);
  fixture.api.dispose();
});

test('loadSnapshot remains unchanged after later saved settings change', async () => {
  const initial = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    introTitle: 'Before save',
    introCaption: 'Caption',
    artworkSubtitle: 'Subtitle',
    wallpaperStrength: 42,
  };
  const next = { ...initial, contours: [[[4, 4], [5, 5]]], introTitle: 'After save' };
  const storage = makeIndexedDB(initial);
  const fixture = makeFixture({
    indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024], [512, 512], [1536, 1024], [512, 512], [1536, 1024]],
  });
  const snapshot = await fixture.api.loadSnapshot(initial);
  const frozenValue = JSON.stringify(snapshot);

  await fixture.api.save(next);
  await fixture.api.loadSnapshot(initial);

  assert.equal(snapshot.settings.introTitle, 'Before save');
  assert.deepEqual(JSON.parse(JSON.stringify(snapshot.settings.contours)), [[[0, 0], [1, 1]]]);
  assert.equal(JSON.stringify(snapshot), frozenValue);
  assert.equal(storage.state.puts, 1);
});

test('settings editor leads with a draft workspace preview and passes a clone to animation preview', async () => {
  const localization = createLocalization({ locale: 'zh-CN' });
  const fixture = makeFixture({ localization });
  const loaded = await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[1, 2]]],
    introTitle: 'Saved title', introCaption: 'Saved caption', artworkSubtitle: 'Saved subtitle',
    wallpaperStrength: 42,
  });
  let previewSettings = null;
  let applyCalls = 0;
  assert.equal(fixture.api.openSettings({
    onPreview: settings => { previewSettings = settings; },
    onApply: () => { applyCalls++; return { applied: true }; },
  }), true);

  const sections = fixture.elements.filter(element => element.getAttribute('data-agent-skin-settings-section'));
  assert.deepEqual(sections.map(element => element.getAttribute('data-agent-skin-settings-section')),
    ['workspace', 'startup', 'about']);
  const tabs = fixture.elements.filter(element => element.getAttribute('role') === 'tab');
  assert.equal(tabs.length, 3);
  assert.equal(fixture.elements.filter(element => element.tagName === 'H2').length, 1,
    'the page keeps one visible settings title');
  assert.equal(fixture.elements.filter(element => element.tagName === 'H3').length, 0,
    'the tab labels name panels without repeated section headings');
  for (const panel of sections) {
    assert.equal(panel.getAttribute('role'), 'tabpanel');
    assert.equal(panel.getAttribute('aria-labelledby'), 'agent-skin-settings-tab-'
      + panel.getAttribute('data-agent-skin-settings-section'));
  }
  assert.equal(fixture.elements.filter(element => element.tagName === 'P'
    && /保存后用于下次启动/.test(element.textContent)).length, 1,
  'only the startup section keeps its unique next-launch and preview note');
  assert.equal(fixture.elements.some(element => element.tagName === 'P'
    && /预览只反映当前草稿|显示语言、深浅色/.test(element.textContent)), false,
  'current values and the workspace preview replace explanatory paragraphs');
  const workspaceTab = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-tab') === 'workspace');
  const startupTab = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-tab') === 'startup');
  const workspacePanel = sections[0];
  const startupPanel = sections[1];
  const backgroundPreview = fixture.elements.find(element => element.getAttribute('data-agent-skin-workspace-preview') === '');
  const backgroundImage = fixture.elements.find(element => element.getAttribute('data-agent-skin-workspace-preview-image') === '');
  const backgroundWash = fixture.elements.find(element => element.getAttribute('data-agent-skin-workspace-preview-wash') === '');
  const strength = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'range');
  const strengthValue = fixture.elements.find(element => element.getAttribute('data-agent-skin-wallpaper-strength-value') === '');
  assert.ok(workspaceTab);
  assert.ok(startupTab);
  assert.equal(workspaceTab.getAttribute('aria-selected'), 'true');
  assert.equal(workspacePanel.hidden, false);
  assert.equal(startupPanel.hidden, true);
  assert.equal(backgroundPreview.getAttribute('aria-label'), '背景草稿预览');
  assert.equal(backgroundImage.src, loaded.settings.artwork);
  const backgroundAction = fixture.elements.find(element => element.getAttribute('data-agent-skin-image-action') === 'artwork');
  assert.equal(backgroundAction.textContent, '选择背景图片');
  assert.equal(backgroundAction.getAttribute('aria-label'), null,
    'the visible button text is its accessible name without a duplicate aria-label');
  const titleInput = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  assert.equal(titleInput.parentNode.tagName, 'LABEL');
  assert.equal(titleInput.parentNode.children[0].textContent, '启动标题（最多 16 个字符）');
  assert.equal(titleInput.getAttribute('aria-label'), null,
    'the visible field label supplies the accessible name');
  assert.equal(titleInput.maxLength, 16);
  const restoreButton = fixture.elements.find(element => element.tagName === 'BUTTON'
    && element.textContent === '恢复全部默认');
  assert.ok(restoreButton);
  assert.ok(backgroundWash, 'workspace preview has a separate wash overlay');
  assert.equal(backgroundWash.style.getPropertyValue('background-image'), expectedPreviewWash(42));

  strength.value = '0';
  strength.listeners.get('input')[0]();
  assert.equal(strengthValue.textContent, '关闭', 'zero strength is shown as closed next to the slider');
  assert.equal(strength.getAttribute('aria-valuetext'), '关闭', 'assistive technology hears that zero means closed');
  assert.equal(backgroundWash.style.getPropertyValue('background-image'), 'none',
    'zero strength removes the wash so the current surface shows through');
  assert.equal(backgroundImage.hidden, true, 'zero strength closes the wallpaper image layer');

  strength.value = '75';
  strength.listeners.get('input')[0]();
  assert.equal(strengthValue.textContent, '75');
  assert.equal(strength.getAttribute('aria-valuetext'), null, 'nonzero strengths retain the native numeric range value');
  assert.equal(backgroundWash.style.getPropertyValue('background-image'), expectedPreviewWash(75),
    'maximum strength uses the renderer wash stops and saturation');

  strength.value = '57';
  strength.listeners.get('input')[0]();
  assert.equal(backgroundWash.style.getPropertyValue('background-image'), expectedPreviewWash(57));
  assert.equal(loaded.settings.wallpaperStrength, 42, 'editing only updates the draft preview');
  assert.equal(applyCalls, 0, 'adjusting the draft preview never writes the live wallpaper');

  startupTab.click();
  assert.equal(workspaceTab.getAttribute('aria-selected'), 'false');
  assert.equal(startupTab.getAttribute('aria-selected'), 'true');
  assert.equal(workspacePanel.hidden, true);
  assert.equal(startupPanel.hidden, false);
  const previewButton = fixture.elements.find(element => element.getAttribute('data-agent-skin-preview-animation') === '');
  assert.equal(previewButton.parentNode, startupPanel);
  previewButton.click();
  assert.equal(previewSettings.wallpaperStrength, 57);
  assert.notEqual(previewSettings, loaded.settings);
  assert.notEqual(previewSettings.contours, loaded.settings.contours);
  previewSettings.contours[0][0][0] = 99;
  assert.equal(loaded.settings.contours[0][0][0], 1, 'callback mutations cannot alter saved settings');
  assert.equal(fixture.api.isSettingsOpen(), true, 'preview leaves the editor open');
  assert.equal(fixture.api.cancelSettings(), true);
  fixture.api.dispose();
});

test('disposing settings releases its focus stylesheet without disturbing host styles', async () => {
  const fixture = makeFixture();
  const existing = {};
  class CSSStyleSheet {
    replaceSync(rules) { this.rules = rules; }
  }
  fixture.environment.document.defaultView = { CSSStyleSheet };
  fixture.environment.document.adoptedStyleSheets = [existing];
  await fixture.api.load({ avatar: '', artwork: '', contours: [], introTitle: 'Title',
    introCaption: '', artworkSubtitle: '', wallpaperStrength: 42 });
  assert.equal(fixture.api.openSettings(), true);
  assert.equal(fixture.environment.document.adoptedStyleSheets.length, 2);
  assert.equal(fixture.api.cancelSettings(), true);
  assert.equal(fixture.api.openSettings(), true);
  assert.equal(fixture.environment.document.adoptedStyleSheets.length, 2);
  fixture.api.dispose();
  assert.equal(fixture.environment.document.adoptedStyleSheets.length, 1);
  assert.equal(fixture.environment.document.adoptedStyleSheets[0], existing);
});

test('a failed animation preview reports an error and keeps the draft editable', async () => {
  const fixture = makeFixture();
  await fixture.api.load({
    avatar: '', artwork: 'data:image/png;base64,BBBB', contours: [],
    introTitle: 'Saved title', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  assert.equal(fixture.api.openSettings({ onPreview: () => { throw new Error('preview unavailable'); } }), true);
  const title = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  const previewButton = fixture.elements.find(element => element.getAttribute('data-agent-skin-preview-animation') === '');
  const alert = fixture.elements.find(element => element.getAttribute('aria-live') === 'assertive');
  title.value = 'Unsaved title';
  title.listeners.get('input')[0]();
  previewButton.click();
  assert.equal(alert.textContent, '动画预览失败；草稿仍可编辑或保存。');
  assert.equal(alert.getAttribute('role'), 'alert');
  assert.equal(title.value, 'Unsaved title');
  assert.equal(fixture.api.isSettingsOpen(), true);
  fixture.api.cancelSettings();
  fixture.api.dispose();
});

test('a failed background apply retries the saved result without repeating the settings transaction', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]] });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: 'Saved title', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  const applied = [];
  const saved = [];
  let applyAttempt = 0;
  let cancelled = 0;
  assert.equal(fixture.api.openSettings({
    onApply: async value => {
      applied.push(value);
      applyAttempt++;
      return applyAttempt === 1
        ? { applied: false, reason: 'wallpaper-unavailable' }
        : { applied: false, reason: 'disabled' };
    },
    onSaved: value => saved.push(value),
    onCancel: () => { cancelled++; },
  }), true);
  const title = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  title.value = 'New title';
  title.listeners.get('input')[0]();
  const saveButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '保存');
  const status = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');

  await saveButton.listeners.get('click')[0]();

  assert.equal(storage.state.puts, 1, status.textContent);
  assert.equal(applied.length, 1);
  assert.equal(applied[0].introTitle, 'New title');
  assert.equal(fixture.api.isSettingsOpen(), true);
  assert.equal(status.textContent, '设置已保存，但背景应用失败。可以重试，或关闭设置。');
  assert.equal(status.getAttribute('role'), 'alert');
  assert.equal(saveButton.textContent, '重试应用');
  const closeButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '关闭');
  assert.ok(closeButton);
  assert.equal(saved.length, 0, 'the host is not told to finish settings until the panel closes');

  await saveButton.listeners.get('click')[0]();

  assert.equal(storage.state.puts, 1, 'retry does not write to IndexedDB again');
  assert.equal(applied.length, 2);
  assert.notEqual(applied[0], applied[1], 'each apply attempt receives a fresh snapshot');
  assert.equal(fixture.api.isSettingsOpen(), false);
  assert.equal(saved.length, 1);
  assert.equal(saved[0].introTitle, 'New title');
  assert.equal(cancelled, 0);
  fixture.api.dispose();
});

test('closing during a pending background apply finalizes committed settings once and ignores late completion', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]] });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: 'Saved title', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  let finishApply;
  const saved = [];
  let cancelled = 0;
  assert.equal(fixture.api.openSettings({
    onApply: () => new Promise(resolve => { finishApply = resolve; }),
    onSaved: value => saved.push(value),
    onCancel: () => { cancelled++; },
  }), true);
  const saveButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '保存');
  const saving = saveButton.listeners.get('click')[0]();
  for (let attempt = 0; attempt < 10 && !finishApply; attempt++) await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(typeof finishApply, 'function');
  assert.equal(fixture.api.isSettingsOpen(), true);
  assert.equal(fixture.api.cancelSettings(), true, 'the user can close while the host apply is pending');
  assert.equal(saved.length, 1);
  assert.equal(cancelled, 0, 'committed settings are not reported as a draft cancellation');
  finishApply({ applied: true });
  await saving;
  assert.equal(saved.length, 1, 'late completion does not notify the host twice');
  assert.equal(fixture.api.isSettingsOpen(), false);
  fixture.api.dispose();
});

test('settings callbacks keep cancel semantics and legacy onSaved behavior when onApply is absent', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]] });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: 'Saved title', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  let cancelled = 0;
  assert.equal(fixture.api.openSettings({ onCancel: () => { cancelled++; } }), true);
  assert.equal(fixture.api.cancelSettings(), true);
  assert.equal(cancelled, 1);

  const saved = [];
  assert.equal(fixture.api.openSettings({ onSaved: value => saved.push(value) }), true);
  const saveButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '保存');
  await saveButton.listeners.get('click')[0]();
  assert.equal(fixture.api.isSettingsOpen(), false);
  assert.equal(storage.state.puts, 1);
  assert.equal(saved.length, 1);
  assert.equal(saved[0].introTitle, 'Saved title');
  assert.equal(cancelled, 1);
  fixture.api.dispose();
});

test('embedded presentation renders inline without modal traps and keeps the section open', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024], [512, 512], [1536, 1024]] });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: 'Saved title', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  const saved = [];
  const applied = [];
  let cancelled = 0;
  assert.equal(fixture.api.openSettings({
    onApply: async value => { applied.push(value); return { applied: true }; },
    onSaved: value => saved.push(value),
    onCancel: () => { cancelled++; },
  }, { presentation: 'embedded' }), true);
  const dialog = fixture.elements.find(element => element.tagName === 'DIALOG');
  assert.ok(dialog);
  assert.equal(dialog.showCalls, 1, 'the embedded section opens inline');
  assert.equal(dialog.showModalCalls ?? 0, 0, 'the embedded section never takes the modal stack');
  assert.equal(dialog.style.getPropertyValue('width'), '100%');
  assert.equal(dialog.style.getPropertyValue('max-height'), 'none');
  assert.equal(dialog.listeners.has('cancel'), false, 'no native cancel path is wired inline');
  assert.equal(dialog.listeners.has('keydown'), false, 'the host page navigation stays untrapped');

  const title = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  title.value = 'Draft edit';
  title.listeners.get('input')[0]();
  const cancelButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '取消');
  cancelButton.click();
  assert.equal(fixture.api.isSettingsOpen(), true, 'embedded cancel keeps the section mounted');
  assert.equal(cancelled, 0, 'embedded cancel is not a settings cancellation');
  assert.equal(title.value, 'Saved title', 'embedded cancel discards the draft edit');
  for (const listener of dialog.listeners.get('cancel') || []) listener({ target: dialog, preventDefault() {} });
  assert.equal(fixture.api.isSettingsOpen(), true, 'an unwired cancel event stays inert inline');

  title.value = 'Embedded title';
  title.listeners.get('input')[0]();
  const saveButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '保存');
  const status = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');
  await saveButton.listeners.get('click')[0]();
  assert.equal(fixture.api.isSettingsOpen(), true, 'an embedded save keeps the section mounted');
  assert.equal(saved.length, 1);
  assert.equal(saved[0].introTitle, 'Embedded title');
  assert.equal(applied.length, 1);
  assert.equal(status.textContent, '设置已保存。');
  assert.equal(saveButton.textContent, '保存', 'a settled embedded save returns to the plain save action');

  title.value = 'Embedded title 2';
  title.listeners.get('input')[0]();
  await saveButton.listeners.get('click')[0]();
  assert.equal(saved.length, 2, 'the live embedded section accepts further save rounds');
  assert.equal(applied.length, 2);
  fixture.api.dispose();
});

test('embedded cancel reverts to the last saved record, not the open-time baseline', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024], [512, 512], [1536, 1024]] });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: 'Open-time baseline', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  const applied = [];
  assert.equal(fixture.api.openSettings({
    onApply: async value => { applied.push(value.introTitle); return { applied: true }; },
    onSaved: () => {},
  }, { presentation: 'embedded' }), true);
  const title = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  const saveButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '保存');
  const cancelButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '取消');

  title.value = 'Saved round 1';
  title.listeners.get('input')[0]();
  await saveButton.listeners.get('click')[0]();
  assert.equal(storage.state.puts, 1);

  title.value = 'Unsaved round 2';
  title.listeners.get('input')[0]();
  cancelButton.click();
  assert.equal(title.value, 'Saved round 1',
    'the embedded cancel rolls back to the last saved record, keeping the earlier save');

  await saveButton.listeners.get('click')[0]();
  assert.equal(storage.state.puts, 2, 'the next save stores the reverted draft');
  assert.deepEqual(applied, ['Saved round 1', 'Saved round 1']);
  fixture.api.dispose();
});

test('embedded cancel drops a saved-but-unapplied commit so the next save is fresh', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024], [512, 512], [1536, 1024]] });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: 'Open-time baseline', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  const applied = [];
  const saved = [];
  let applyOutcome = { applied: false, reason: 'wallpaper-unavailable' };
  assert.equal(fixture.api.openSettings({
    onApply: async value => { applied.push(value.introTitle); return applyOutcome; },
    onSaved: value => saved.push(value.introTitle),
  }, { presentation: 'embedded' }), true);
  const title = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  const saveButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '保存');
  const cancelButton = fixture.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '取消');

  title.value = 'Broken apply';
  title.listeners.get('input')[0]();
  await saveButton.listeners.get('click')[0]();
  assert.equal(storage.state.puts, 1, 'the record is stored even though the host apply failed');
  assert.equal(saveButton.textContent, '重试应用', 'the failed apply leaves the retry action visible');

  cancelButton.click();
  assert.equal(saveButton.textContent, '保存', 'the embedded cancel drops the pending-apply commit');
  assert.equal(title.value, 'Broken apply',
    'the revert baseline is the stored record, matching what the host still holds');

  applyOutcome = { applied: true };
  title.value = 'Fresh edit';
  title.listeners.get('input')[0]();
  await saveButton.listeners.get('click')[0]();
  assert.equal(storage.state.puts, 2, 'the next save is a fresh save, not a retry of the old commit');
  assert.deepEqual(applied, ['Broken apply', 'Fresh edit'],
    'the fresh save carries the edited draft rather than replaying the dropped commit');
  fixture.api.dispose();

  const modalFixture = makeFixture({ indexedDB: makeIndexedDB().indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]] });
  await modalFixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: 'Saved title', introCaption: '', artworkSubtitle: '', wallpaperStrength: 42,
  });
  assert.equal(modalFixture.api.openSettings({}), true, 'the standalone default stays modal');
  const modalDialog = modalFixture.elements.find(element => element.tagName === 'DIALOG');
  assert.equal(modalDialog.showModalCalls, 1);
  assert.equal(modalDialog.showCalls ?? 0, 0);
  assert.ok(modalDialog.listeners.has('cancel'));
  assert.ok(modalDialog.listeners.has('keydown'));
  modalFixture.api.dispose();
});

test('the settings page puts editing first and keeps read-only appearance state without exposing build instructions', async () => {
  const themeConfig = {
    identity: { appName: { 'zh-CN': '阿舟 AI 实验室', en: 'Azhou AI Lab' },
      botName: { 'zh-CN': '阿舟', en: 'Azhou' }, version: '0.9.0', build: '10',
      installationName: '阿舟 AI 实验室.app', iconInput: 'assets/private/app-icon/source.png',
      entryAvatarInput: 'assets/private/entry-avatar.png' },
    startup: { durationMs: 12000 }, wallpaper: { strength: 42, min: 0, max: 75 },
  };
  let appearance = { locale: 'zh-CN', theme: 'dark', reducedMotion: false, colors: { surface: '#10121c' } };
  const localization = createLocalization({ locale: 'zh-CN' });
  const fixture = makeFixture({ localization, themeConfig, getAppearance: () => appearance });
  const loaded = await fixture.api.load({ avatar: '', artwork: '', contours: [] });
  assert.equal(fixture.api.openSettings(), true);
  const sections = fixture.elements.filter(element => element.getAttribute('data-agent-skin-settings-section'));
  assert.deepEqual(sections.map(element => element.getAttribute('data-agent-skin-settings-section')),
    ['workspace', 'startup', 'about']);
  const value = key => fixture.elements.find(element => element.getAttribute('data-agent-skin-setting-value') === key);
  assert.equal(value('appName').textContent, '阿舟 AI 实验室');
  assert.equal(value('version').textContent, '0.9.0 · 10');
  const runningVersion = fixture.elements.find(element => element.getAttribute('data-agent-skin-running-version') === '');
  assert.equal(runningVersion?.textContent, '当前运行：0.9.0 · build 10');
  assert.equal(runningVersion.parentNode.parentNode.tagName, 'HEADER', 'version is visible above every settings tab');
  assert.equal(value('theme').textContent, '深色');
  assert.equal(value('reducedMotion').textContent, '关闭');
  assert.equal(value('installation'), undefined);
  assert.equal(fixture.elements.some(element => /theme-config\.json|build-macos\.sh/.test(element.textContent)), false);
  assert.equal(loaded.settings.themeConfig, undefined);
  assert.equal(loaded.settings.reducedMotion, undefined);
  appearance = { ...appearance, locale: 'en', theme: 'light', reducedMotion: true };
  localization.setLocale('en');
  fixture.api.refreshAppearance();
  assert.equal(value('appName').textContent, 'Azhou AI Lab');
  assert.equal(runningVersion.textContent, 'Running: 0.9.0 · build 10');
  assert.equal(value('theme').textContent, 'Light');
  assert.equal(value('reducedMotion').textContent, 'On');
  assert.equal(fixture.api.cancelSettings(), true);
  fixture.api.dispose();
});

test('the settings dialog follows host locale changes without replacing the dialog or draft', async () => {
  const localization = createLocalization({ locale: 'zh-CN' });
  const fixture = makeFixture({ localization, appearanceAvatar: 'data:image/png;base64,AAAA' });
  const defaults = {
    avatar: '', artwork: '', contours: [], introTitle: 'Saved title', introCaption: 'Saved caption',
    artworkSubtitle: 'Saved subtitle', wallpaperStrength: 42,
  };

  const loaded = await fixture.api.load(defaults);
  assert.deepEqual(Object.keys(loaded.settings).sort(), [
    'artwork', 'artworkSubtitle', 'avatar', 'contours', 'introCaption', 'introTitle',
    'schemaVersion', 'wallpaperStrength',
  ]);
  assert.equal(fixture.api.openSettings(), true);

  const dialog = fixture.elements.find(element => element.tagName === 'DIALOG');
  const appearanceAvatar = fixture.elements.find(element =>
    element.getAttribute('data-agent-skin-appearance-avatar') === '');
  const titleInput = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  const status = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');
  assert.equal(dialog.getAttribute('data-agent-skin-settings'), '');
  assert.equal(appearanceAvatar.src, 'data:image/png;base64,AAAA');
  assert.equal(appearanceAvatar.getAttribute('alt'), '');
  assert.equal(loaded.settings.appearanceAvatar, undefined, 'the host bot avatar is outside the settings record');
  assert.equal(titleInput.value, 'Saved title');
  assert.equal(titleInput.getAttribute('aria-label'), null, 'the wrapping label supplies the accessible name');
  assert.equal(titleInput.parentNode.children[0].textContent, '启动标题（最多 16 个字符）');
  assert.equal(status.textContent, '暂时无法读取已保存设置；当前使用默认值，原设置保持不变。');

  titleInput.value = 'Local draft';
  titleInput.listeners.get('input')[0]();
  localization.setLocale('en');

  assert.equal(fixture.elements.filter(element => element.tagName === 'DIALOG').length, 1);
  assert.equal(fixture.elements.find(element => element.tagName === 'DIALOG'), dialog);
  assert.equal(dialog.open, true);
  assert.equal(titleInput.value, 'Local draft');
  assert.equal(titleInput.getAttribute('aria-label'), null, 'localization does not add a duplicate aria-label');
  assert.equal(titleInput.parentNode.children[0].textContent, 'Startup title (up to 16 characters)');
  assert.equal(status.textContent,
    'Saved settings are temporarily unavailable. Defaults are in use; saved settings are unchanged.');
  assert.equal(fixture.elements.find(element => element.id === 'agent-skin-settings-title').textContent,
    'Azhou · Theme & Appearance');
  assert.equal(fixture.elements.find(element => element.getAttribute('data-agent-skin-running-version') === '').textContent,
    'Running: Unavailable in this environment', 'missing build metadata is never replaced by a claimed latest version');
  assert.equal(dialog.style.getPropertyValue('color-scheme'), 'inherit');
  assert.equal(dialog.style.getPropertyValue('background-color'), 'var(--agent-skin-surface, Canvas)');
  assert.equal(dialog.style.getPropertyValue('color'), 'var(--agent-skin-text, CanvasText)');
  const restoreButton = fixture.elements.find(element => element.tagName === 'BUTTON'
    && element.textContent === 'Restore all defaults');
  const saveButton = fixture.elements.find(element => element.tagName === 'BUTTON'
    && element.textContent === 'Save');
  assert.equal(restoreButton.style.getPropertyValue('background-color'), 'var(--agent-skin-surface, Canvas)');
  assert.equal(restoreButton.style.getPropertyValue('color'), 'var(--agent-skin-text, CanvasText)');
  assert.equal(saveButton.style.getPropertyValue('background-color'), 'var(--agent-skin-text, CanvasText)');
  assert.equal(saveButton.style.getPropertyValue('color'), 'var(--agent-skin-surface, Canvas)');

  assert.equal(fixture.api.cancelSettings(), true);
  assert.equal(localization.locale, 'en', 'cancel discards the text draft and leaves host locale alone');
  fixture.api.dispose();
});

test('localized image selection buttons use hidden file inputs and disable while importing', async () => {
  const localization = createLocalization({ locale: 'zh-CN' });
  const fixture = makeFixture({ localization, decode: 'pending' });
  await fixture.api.load({
    avatar: '', artwork: '', contours: [], introTitle: 'Title', introCaption: '',
    artworkSubtitle: 'Subtitle', wallpaperStrength: 42,
  });
  assert.equal(fixture.api.openSettings(), true);

  const portraitInput = fixture.elements.find(element =>
    element.getAttribute('data-agent-skin-image-input') === 'avatar');
  const backgroundInput = fixture.elements.find(element =>
    element.getAttribute('data-agent-skin-image-input') === 'artwork');
  const portraitButton = fixture.elements.find(element =>
    element.getAttribute('data-agent-skin-image-action') === 'avatar');
  const backgroundButton = fixture.elements.find(element =>
    element.getAttribute('data-agent-skin-image-action') === 'artwork');
  assert.ok(portraitInput);
  assert.ok(backgroundInput);
  assert.ok(portraitButton);
  assert.ok(backgroundButton);
  assert.equal(portraitInput.hidden, true);
  assert.equal(backgroundInput.hidden, true);
  assert.equal(portraitInput.accept, 'image/png,image/jpeg,image/webp');
  assert.equal(portraitButton.textContent, '选择启动头像');
  assert.equal(portraitButton.getAttribute('aria-label'), null, 'visible button text is its accessible name');
  assert.equal(backgroundButton.textContent, '选择背景图片');
  assert.equal(backgroundButton.getAttribute('aria-label'), null, 'visible button text is its accessible name');

  portraitButton.click();
  assert.equal(portraitInput.clickCount, 1, 'the visible action forwards a user click to the hidden input');
  localization.setLocale('en');
  assert.equal(portraitButton.textContent, 'Choose startup portrait');
  assert.equal(portraitButton.getAttribute('aria-label'), null);
  assert.equal(backgroundButton.textContent, 'Choose background image');
  assert.equal(backgroundButton.getAttribute('aria-label'), null);

  portraitInput.files = [makeFile()];
  const change = portraitInput.listeners.get('change')[0]();
  assert.equal(portraitButton.disabled, true);
  assert.equal(backgroundButton.disabled, true);
  assert.equal(portraitInput.disabled, true);
  assert.equal(backgroundInput.disabled, true);
  assert.equal(fixture.api.cancelImport(), true);
  await change;
  assert.equal(portraitButton.disabled, false);
  assert.equal(backgroundButton.disabled, false);
  const status = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');
  assert.equal(status.textContent, '', 'canceling an import clears the damaged-image alert');
  assert.equal(status.getAttribute('role'), 'status');
  fixture.api.dispose();
});

test('image selection errors name the field, state the cause, and offer a recovery action', async () => {
  const cases = [
    { name: 'empty file', file: makeFile({ size: 0 }), expected: '文件为空' },
    { name: 'byte limit', file: makeFile({ size: MAX_INPUT_BYTES + 1 }), expected: '超过 30 MiB' },
    { name: 'pixel limit', file: makeFile(), dimensions: [24_000, 2_001], expected: '原始像素超过 48 MP' },
    { name: 'MIME mismatch', file: makeFile({ type: 'image/jpeg' }), expected: '与实际内容不符' },
    { name: 'unsupported signature', file: makeFile({ signature: Uint8Array.of(1, 2, 3, 4, 5, 6, 7, 8) }),
      expected: '不是受支持的' },
    { name: 'decode failure', file: makeFile(), decode: 'error', expected: '无法解码' },
  ];
  for (const item of cases) {
    const fixture = makeFixture({ decode: item.decode, width: item.dimensions?.[0], height: item.dimensions?.[1] });
    await fixture.api.load({
      avatar: '', artwork: '', contours: [], introTitle: 'Title', introCaption: '',
      artworkSubtitle: 'Subtitle', wallpaperStrength: 42,
    });
    assert.equal(fixture.api.openSettings(), true, item.name);
    const input = fixture.elements.find(element => element.getAttribute('data-agent-skin-image-input') === 'avatar');
    const status = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');
    input.files = [item.file];
    await input.listeners.get('change')[0]();
    assert.equal(status.getAttribute('role'), 'alert', item.name);
    assert.ok(status.textContent.includes('启动头像'), item.name + ': ' + status.textContent);
    assert.ok(status.textContent.includes(item.expected), item.name + ': ' + status.textContent);
    assert.match(status.textContent, /请选择|换一张/, item.name + ': ' + status.textContent);
    assert.doesNotMatch(status.textContent, /decoder detail|blob:fixture|image-settings\.js/);
    assert.equal(input.value, '');
    assert.deepEqual(fixture.revoked, fixture.created);
    fixture.api.cancelSettings();
    fixture.api.dispose();
  }
});

test('image selection timeout feedback distinguishes a slow header read and a slow decode', async () => {
  const defaults = {
    avatar: '', artwork: '', contours: [], introTitle: 'Title', introCaption: '',
    artworkSubtitle: 'Subtitle', wallpaperStrength: 42,
  };
  const headerFixture = makeFixture();
  await headerFixture.api.load(defaults);
  headerFixture.api.openSettings();
  const headerInput = headerFixture.elements.find(element =>
    element.getAttribute('data-agent-skin-image-input') === 'avatar');
  const headerStatus = headerFixture.elements.find(element =>
    element.getAttribute('data-agent-skin-settings-status') === '');
  headerInput.files = [{ size: 64, type: 'image/png', slice: () => ({ arrayBuffer: () => new Promise(() => {}) }) }];
  const headerChange = headerInput.listeners.get('change')[0]();
  headerFixture.advance(10_000);
  await headerChange;
  assert.equal(headerStatus.getAttribute('role'), 'alert');
  assert.match(headerStatus.textContent, /处理启动头像超时/);
  headerFixture.api.cancelSettings();
  headerFixture.api.dispose();

  const decodeFixture = makeFixture({ decode: 'pending' });
  await decodeFixture.api.load(defaults);
  decodeFixture.api.openSettings();
  const decodeInput = decodeFixture.elements.find(element =>
    element.getAttribute('data-agent-skin-image-input') === 'avatar');
  const decodeStatus = decodeFixture.elements.find(element =>
    element.getAttribute('data-agent-skin-settings-status') === '');
  decodeInput.files = [makeFile()];
  const decodeChange = decodeInput.listeners.get('change')[0]();
  await new Promise(resolve => setTimeout(resolve, 0));
  decodeFixture.advance(4_000);
  await decodeChange;
  assert.equal(decodeStatus.getAttribute('role'), 'alert');
  assert.match(decodeStatus.textContent, /解码启动头像超时/);
  decodeFixture.api.cancelSettings();
  decodeFixture.api.dispose();
});

test('missing built-in text uses the host locale while the open draft stays unchanged', async () => {
  const localization = createLocalization({ locale: 'zh-CN' });
  const fixture = makeFixture({ localization });
  const loaded = await fixture.api.load({ avatar: '', artwork: '', contours: [], wallpaperStrength: 42 });

  assert.equal(loaded.settings.introTitle, '阿舟 AI 实验室');
  assert.equal(loaded.settings.introCaption, 'AZHOU / AI LAB');
  assert.equal(loaded.settings.artworkSubtitle, '和阿舟一起，把想法做出来。');
  assert.equal(fixture.api.openSettings(), true);
  const titleInput = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  assert.equal(titleInput.value, '阿舟 AI 实验室');

  localization.setLocale('en');
  assert.equal(titleInput.value, '阿舟 AI 实验室', 'changing host language does not rewrite the active draft');
  assert.equal(fixture.api.cancelSettings(), true);
  assert.equal(fixture.api.openSettings(), true);
  assert.equal(titleInput.value, 'Azhou AI Lab', 'a new draft uses the current host language default');
  fixture.api.cancelSettings();
  fixture.api.dispose();
});

test('locale changes leave committed custom text and the stored settings record untouched', async () => {
  const localization = createLocalization({ locale: 'zh-CN' });
  const record = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    introTitle: 'My saved title',
    introCaption: 'My saved caption',
    artworkSubtitle: 'My saved subtitle',
    wallpaperStrength: 42,
  };
  const storage = makeIndexedDB(record);
  const fixture = makeFixture({
    indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]],
    localization,
  });
  const loaded = await fixture.api.load(record);
  assert.equal(loaded.reason, '');
  assert.equal(fixture.api.openSettings(), true);
  const titleInput = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);

  localization.setLocale('en');

  assert.equal(titleInput.value, 'My saved title');
  assert.equal(loaded.settings.introTitle, 'My saved title');
  assert.deepEqual(storage.state.record, record);
  assert.equal(fixture.api.cancelSettings(), true);
  assert.deepEqual(storage.state.record, record);
  fixture.api.dispose();
});

test('load returns the complete saved baseline from the v1 images record', async () => {
  const record = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]],
    introTitle: 'Saved title',
    introCaption: '',
    artworkSubtitle: 'Saved subtitle',
    wallpaperStrength: 17,
  };
  const storage = makeIndexedDB(record);
  const fixture = makeFixture({
    indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]],
  });
  const defaults = {
    avatar: 'data:image/png;base64,CCCC',
    artwork: 'data:image/png;base64,DDDD',
    contours: [[[2, 2], [3, 3]]],
    introTitle: 'Default title',
    introCaption: 'Default caption',
    artworkSubtitle: 'Default subtitle',
    wallpaperStrength: 42,
  };

  const loaded = await fixture.api.load(defaults);

  assert.equal(loaded.reason, '');
  assert.deepEqual(JSON.parse(JSON.stringify(loaded.settings)), record);
  assert.deepEqual(JSON.parse(JSON.stringify(loaded.baseline)), record);
  assert.deepEqual(storage.state.opens, [{ name: 'azhou-codex-startup', version: 1 }]);
  assert.equal(storage.state.puts, 0);
  assert.equal(storage.state.deletes, 0);
  assert.equal(storage.state.clears, 0);
});

test('load falls back for an unknown record but returns its untouched baseline', async () => {
  const unknown = { schemaVersion: 7, futureField: { keep: true } };
  const storage = makeIndexedDB(unknown);
  const fixture = makeFixture({ indexedDB: storage.indexedDB });
  const defaults = {
    avatar: 'data:image/png;base64,CCCC', artwork: 'data:image/png;base64,DDDD',
    contours: [[[0, 0], [1, 1]]], introTitle: 'Default', introCaption: 'Caption',
    artworkSubtitle: 'Subtitle', wallpaperStrength: 42,
  };

  const loaded = await fixture.api.load(defaults);

  assert.equal(loaded.reason, 'settings-invalid');
  assert.equal(loaded.settings.introTitle, 'Default');
  assert.deepEqual(JSON.parse(JSON.stringify(loaded.baseline)), unknown);
  assert.deepEqual(storage.state.record, unknown);
  assert.equal(storage.state.puts, 0);
  assert.equal(storage.state.deletes, 0);
  assert.equal(storage.state.clears, 0);
});

test('save returns only a committed complete record under the images key', async () => {
  const candidate = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA',
    artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]],
    introTitle: 'Saved title',
    introCaption: '',
    artworkSubtitle: 'Saved subtitle',
    wallpaperStrength: 17,
  };
  const storage = makeIndexedDB(undefined);
  const fixture = makeFixture({
    indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]],
  });
  await fixture.api.load(candidate);

  const saved = await fixture.api.save(candidate);

  assert.deepEqual(JSON.parse(JSON.stringify(saved)), candidate);
  assert.deepEqual(JSON.parse(JSON.stringify(storage.state.record)), candidate);
  assert.equal(storage.state.puts, 1);
  assert.equal(storage.state.transactions.at(-1).mode, 'readwrite');
});

test('put request success followed by abort is still a failed settings save', async () => {
  let observedBeforeComplete = '';
  let saveOutcome = 'pending';
  const storage = makeIndexedDB(undefined, {
    afterRequest({ kind, transaction }) {
      if (kind !== 'put') return;
      observedBeforeComplete = saveOutcome;
      transaction.abort();
    },
  });
  const candidate = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]], introTitle: 'Saved title', introCaption: '',
    artworkSubtitle: 'Saved subtitle', wallpaperStrength: 17,
  };
  const fixture = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
  await fixture.api.load(candidate);
  const result = fixture.api.save(candidate).then(
    value => { saveOutcome = 'resolved'; return value; },
    error => { saveOutcome = 'rejected'; throw error; },
  );

  await assert.rejects(result, error => error.causeCode === 'database-write-aborted');

  assert.equal(observedBeforeComplete, 'pending');
  assert.equal(storage.state.putSuccesses, 1);
  assert.equal(storage.state.completions, 1, 'the preceding baseline read completed; the write transaction did not');
  assert.equal(storage.state.transactions.at(-1).completed, false);
  assert.equal(storage.state.record, undefined, 'an aborted write does not replace the prior value');
});

test('a blocked database open leaves the supplied defaults available without a baseline', async () => {
  const storage = makeIndexedDB(undefined, { openBlocked: true });
  const fixture = makeFixture({ indexedDB: storage.indexedDB });
  const defaults = {
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]], introTitle: 'Default', introCaption: '',
    artworkSubtitle: 'Fixture', wallpaperStrength: 42,
  };

  const loaded = await fixture.api.load(defaults);

  assert.equal(loaded.reason, 'settings-blocked');
  assert.equal(loaded.baseline, undefined);
  assert.deepEqual(JSON.parse(JSON.stringify(loaded.settings)), {
    schemaVersion: 1,
    ...defaults,
  });
  assert.equal(storage.state.transactions.length, 0);
});

test('the baseline is compared inside the write transaction and conflicts preserve the other page value', async () => {
  const baseline = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]], introTitle: 'Old title', introCaption: '',
    artworkSubtitle: 'Fixture', wallpaperStrength: 42,
  };
  const storage = makeIndexedDB(baseline);
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024], [512, 512], [1536, 1024]] });
  const loaded = await fixture.api.load(baseline);
  const otherPageValue = { ...baseline, introTitle: 'Other page committed' };
  storage.state.record = otherPageValue;

  await assert.rejects(fixture.api.save({ ...loaded.settings, introTitle: 'Local draft' }), error =>
    error.reason === 'settings-conflict' && error.causeCode === 'baseline-changed');

  assert.deepEqual(storage.state.record, otherPageValue);
  assert.equal(storage.state.puts, 0);
  assert.equal(storage.state.transactions.at(-1).aborted, true);
});

test('quota errors and text-limit failures happen without replacing a committed record', async t => {
  await t.test('quota error from put', async () => {
    const quotaError = Object.assign(new Error('browser-specific quota detail'), { name: 'QuotaExceededError' });
    const storage = makeIndexedDB(undefined, { putError: quotaError });
    const fixture = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
    const defaults = {
      schemaVersion: 1, avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
      contours: [[[0, 0], [1536, 1024]]], introTitle: 'Default', introCaption: '',
      artworkSubtitle: 'Fixture', wallpaperStrength: 42,
    };
    await fixture.api.load(defaults);

    await assert.rejects(fixture.api.save({ ...defaults, introTitle: 'Candidate' }), error => {
      assert.equal(error.reason, 'settings-quota');
      assert.equal(error.causeCode, 'quota-exceeded');
      assert.equal(error.message, 'settings-quota');
      return true;
    });

    assert.equal(storage.state.record, undefined);
    assert.equal(storage.state.puts, 1);
    assert.equal(storage.state.transactions.at(-1).aborted, true);
  });

  await t.test('candidate UTF-16 text limit is checked before opening a write transaction', async () => {
    const storage = makeIndexedDB(undefined);
    const fixture = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
    const candidate = {
      schemaVersion: 1, avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
      contours: [[[0, 0], [1536, 1024]]], introTitle: '12345678901234567', introCaption: '',
      artworkSubtitle: 'Fixture', wallpaperStrength: 42,
    };
    await fixture.api.load(candidate);

    await assert.rejects(fixture.api.save(candidate), error => error.reason === 'settings-invalid');

    assert.equal(storage.state.puts, 0);
    assert.equal(storage.state.transactions.at(-1).mode, 'readonly');
    assert.equal(storage.state.record, undefined);
  });
});

test('a write timeout aborts the unfinished transaction and a late baseline callback cannot commit', async () => {
  const options = { holdRequests: false };
  const storage = makeIndexedDB(undefined, options);
  const fixture = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
  const candidate = {
    schemaVersion: 1, avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]], introTitle: 'Candidate', introCaption: '',
    artworkSubtitle: 'Fixture', wallpaperStrength: 42,
  };
  await fixture.api.load(candidate);
  options.holdRequests = true;
  const saving = fixture.api.save(candidate);
  for (let attempt = 0; attempt < 10 && storage.state.transactions.length < 2; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  const write = storage.state.transactions.at(-1);
  assert.equal(write.mode, 'readwrite');

  fixture.advance(5_000);
  await assert.rejects(saving, error =>
    error.reason === 'operation-timeout' && error.causeCode === 'database-write-timeout');
  assert.equal(write.aborted, true);
  assert.equal(storage.state.puts, 0);
  assert.equal(storage.state.record, undefined);

  assert.deepEqual(storage.state.releaseHeldRequests(true), [true, true, true]);
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(storage.state.puts, 0);
  assert.equal(write.completed, false);
  assert.equal(storage.state.record, undefined);
});

test('external dispose aborts a pending save and ignores its late request callback', async () => {
  const options = { holdRequests: false };
  const storage = makeIndexedDB(undefined, options);
  const fixture = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
  const candidate = {
    schemaVersion: 1, avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]], introTitle: 'Candidate', introCaption: '',
    artworkSubtitle: 'Fixture', wallpaperStrength: 42,
  };
  await fixture.api.load(candidate);
  options.holdRequests = true;
  const saving = fixture.api.save(candidate);
  for (let attempt = 0; attempt < 10 && storage.state.transactions.length < 2; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  const write = storage.state.transactions.at(-1);
  assert.equal(write.mode, 'readwrite');

  assert.equal(fixture.api.dispose(), true);
  await assert.rejects(saving, error => error.reason === 'operation-cancelled');
  assert.equal(write.aborted, true);
  assert.equal(storage.state.record, undefined);

  assert.deepEqual(storage.state.releaseHeldRequests(true), [true, true, true]);
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(storage.state.puts, 0);
  assert.equal(write.completed, false);
  assert.equal(storage.state.record, undefined);
});

test('load total timeout returns safe defaults, preserves the baseline, and leaves the settings panel usable', async () => {
  const stored = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]], introTitle: 'Saved value', introCaption: '',
    artworkSubtitle: 'Fixture', wallpaperStrength: 42,
  };
  const defaults = {
    avatar: 'data:image/png;base64,CCCC', artwork: 'data:image/png;base64,DDDD',
    contours: [[[0, 0], [1, 1]]], introTitle: 'Safe default', introCaption: '',
    artworkSubtitle: 'Generated only', wallpaperStrength: 0,
  };
  const options = { holdOpen: true, holdRequests: true };
  const storage = makeIndexedDB(stored, options);
  const fixture = makeFixture({ indexedDB: storage.indexedDB, decode: 'pending',
    imageDimensions: [[512, 512], [1536, 1024]] });
  const loading = fixture.api.load(defaults);
  for (let attempt = 0; attempt < 10 && !storage.state.releaseOpen; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  assert.equal(typeof storage.state.releaseOpen, 'function');

  fixture.advance(4_500);
  assert.equal(storage.state.releaseOpen(), true);
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(storage.state.transactions.length, 1);
  fixture.advance(4_500);
  assert.deepEqual(storage.state.releaseHeldRequests(), [true, true, true]);
  for (let attempt = 0; attempt < 10 && fixture.images.length < 2; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  assert.equal(fixture.images.length, 2, 'both stored PNGs have started decode validation');
  const lateCallbacks = fixture.images.map(image => image.onload);
  assert.ok(lateCallbacks.every(callback => typeof callback === 'function'));

  fixture.advance(1_000);
  const loaded = await loading;

  assert.equal(loaded.reason, 'operation-timeout');
  assert.equal(loaded.settings.introTitle, 'Safe default');
  assert.equal(loaded.baseline.introTitle, 'Saved value');
  assert.deepEqual(storage.state.record, stored);
  assert.equal(storage.state.deletes, 0);
  assert.equal(storage.state.clears, 0);
  assert.equal(fixture.api.openSettings(), true, 'the timeout fallback initializes a usable settings panel');
  assert.equal(fixture.api.isSettingsOpen(), true);
  const status = fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');
  assert.equal(status.textContent, '读取设置超时；当前使用默认值，已保存记录未改动。可以重试。');

  lateCallbacks.forEach(callback => callback());
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(fixture.api.isSettingsOpen(), true, 'late stored-image decodes cannot close or revive the panel');
  assert.equal(status.textContent, '读取设置超时；当前使用默认值，已保存记录未改动。可以重试。');
  assert.deepEqual(storage.state.record, stored);
  assert.equal(fixture.api.dispose(), true);
});

test('database open and read each time out after their five-second budget', async t => {
  const defaults = {
    avatar: 'data:image/png;base64,CCCC', artwork: 'data:image/png;base64,DDDD',
    contours: [[[0, 0], [1, 1]]], introTitle: 'Safe default', introCaption: '',
    artworkSubtitle: 'Generated fixture', wallpaperStrength: 0,
  };

  await t.test('a pending open returns defaults at 5000 ms and ignores a late success', async () => {
    const storage = makeIndexedDB(undefined, { holdOpen: true });
    const fixture = makeFixture({ indexedDB: storage.indexedDB });
    let settled = false;
    const loading = fixture.api.load(defaults).then(value => { settled = true; return value; });
    for (let attempt = 0; attempt < 10 && !storage.state.releaseOpen; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    assert.equal(typeof storage.state.releaseOpen, 'function');
    assert.equal(fixture.timers.some(timer => timer.delay === 5_000 && !timer.cleared), true);

    fixture.advance(4_999);
    await Promise.resolve();
    assert.equal(settled, false, 'the open budget does not expire early');
    fixture.advance(1);
    const loaded = await loading;
    assert.equal(loaded.reason, 'operation-timeout');
    assert.equal(loaded.settings.introTitle, 'Safe default');
    assert.equal(loaded.baseline, undefined);

    assert.equal(storage.state.releaseOpen(), true, 'the controlled request can report late success');
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(storage.state.transactions.length, 0, 'late open success cannot start a read after fallback');
    assert.equal(storage.state.record, undefined);
    fixture.api.dispose();
  });

  await t.test('a pending get aborts at 5000 ms and cannot apply its late request result', async () => {
    const storage = makeIndexedDB(undefined, { holdRequests: true });
    const fixture = makeFixture({ indexedDB: storage.indexedDB });
    let settled = false;
    const loading = fixture.api.load(defaults).then(value => { settled = true; return value; });
    for (let attempt = 0; attempt < 10 && storage.state.heldRequests.length === 0; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    assert.equal(storage.state.heldRequests.length, 3, 'all three read-only gets remain pending');
    const transaction = storage.state.transactions[0];
    assert.equal(transaction.mode, 'readonly');

    fixture.advance(4_999);
    await Promise.resolve();
    assert.equal(settled, false, 'the read budget does not expire early');
    fixture.advance(1);
    const loaded = await loading;
    assert.equal(loaded.reason, 'operation-timeout');
    assert.equal(loaded.settings.introTitle, 'Safe default');
    assert.equal(transaction.aborted, true);

    assert.deepEqual(storage.state.releaseHeldRequests(true), [true, true, true]);
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(transaction.completed, false, 'the late get cannot complete the aborted transaction');
    assert.equal(storage.state.record, undefined);
    fixture.api.dispose();
  });
});

test('restore all defaults changes only the draft and cancel keeps the saved record', async () => {
  const saved = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]], introTitle: 'Saved title', introCaption: 'Saved caption',
    artworkSubtitle: 'Saved subtitle', wallpaperStrength: 42,
  };
  const defaults = {
    avatar: 'data:image/png;base64,CCCC', artwork: 'data:image/png;base64,DDDD',
    contours: [[[1, 1], [2, 2]]], introTitle: 'Default title', introCaption: '',
    artworkSubtitle: '', wallpaperStrength: 0,
  };
  const storage = makeIndexedDB(saved);
  const fixture = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
  await fixture.api.load(defaults);
  assert.equal(fixture.api.openSettings(), true);
  const titleInput = fixture.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  const restore = fixture.elements.find(element => element.tagName === 'BUTTON'
    && element.textContent === '恢复全部默认');
  titleInput.value = 'Unsaved draft';
  titleInput.listeners.get('input')[0]({});
  restore.listeners.get('click')[0]({});

  assert.equal(titleInput.value, 'Default title');
  assert.equal(storage.state.record.introTitle, 'Saved title');
  assert.equal(storage.state.puts, 0);
  assert.match(fixture.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '').textContent,
    /草稿已恢复为默认设置/);
  assert.equal(fixture.api.cancelSettings(), true);
  assert.equal(storage.state.record.introTitle, 'Saved title');
  assert.equal(storage.state.puts, 0, 'cancel does not persist the restored draft');
  fixture.api.dispose();
});

test('a settings conflict keeps the local text copyable and reopening reads the winner', async () => {
  const baseline = {
    schemaVersion: 1,
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1536, 1024]]], introTitle: 'Old title', introCaption: '',
    artworkSubtitle: 'Fixture', wallpaperStrength: 42,
  };
  const storage = makeIndexedDB(baseline);
  const imageDimensions = [[512, 512], [1536, 1024], [512, 512], [1536, 1024]];
  const pageA = makeFixture({ indexedDB: storage.indexedDB, imageDimensions });
  const english = createLocalization({ locale: 'en' });
  const pageB = makeFixture({ indexedDB: storage.indexedDB, imageDimensions, localization: english });
  const loadedA = await pageA.api.load(baseline);
  const loadedB = await pageB.api.load(baseline);
  assert.equal(loadedA.reason, '', JSON.stringify(loadedA));
  assert.equal(loadedB.reason, '', JSON.stringify(loadedB));
  assert.equal(pageA.api.openSettings(), true);
  assert.equal(pageB.api.openSettings(), true);

  const pageATitle = pageA.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  const pageBTitle = pageB.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  const pageASave = pageA.elements.find(element => element.tagName === 'BUTTON' && element.textContent === '保存');
  const pageBSave = pageB.elements.find(element => element.tagName === 'BUTTON' && element.textContent === 'Save');
  const pageAStatus = pageA.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');
  const pageBStatus = pageB.elements.find(element => element.getAttribute('data-agent-skin-settings-status') === '');
  pageATitle.value = 'Page A saved';
  pageATitle.listeners.get('input')[0]({});
  pageBTitle.value = 'Page B draft';
  pageBTitle.listeners.get('input')[0]({});

  await pageASave.listeners.get('click')[0]();
  await pageBSave.listeners.get('click')[0]();

  assert.equal(storage.state.record.introTitle, 'Page A saved', pageAStatus.textContent);
  assert.equal(pageB.api.isSettingsOpen(), true, 'the conflicting panel remains open');
  assert.equal(pageBTitle.value, 'Page B draft', 'the local text stays available to copy');
  assert.equal(pageBStatus.getAttribute('role'), 'alert');
  assert.match(pageBStatus.textContent, /clos.*discard/i);
  assert.match(pageBStatus.textContent, /copy/i);
  assert.match(pageBStatus.textContent, /reopen.*new/i);
  assert.doesNotMatch(pageBStatus.textContent, /save your draft again|keep.*draft/i);

  assert.equal(pageB.api.cancelSettings(), true, 'closing is the discard action and needs no confirmation');
  assert.equal(storage.state.record.introTitle, 'Page A saved', 'closing cannot replace the other page value');
  const reopenedPage = makeFixture({ indexedDB: storage.indexedDB, imageDimensions, localization: english });
  const reopened = await reopenedPage.api.load(baseline);
  assert.equal(reopened.settings.introTitle, 'Page A saved');
  assert.equal(reopenedPage.api.openSettings(), true);
  const reopenedTitle = reopenedPage.elements.find(element => element.tagName === 'INPUT' && element.type === 'text' && element.getAttribute('data-agent-skin-preset-name') === null);
  assert.equal(reopenedTitle.value, 'Page A saved', 'a newly opened page reads the external winner');
  assert.equal(storage.state.puts, 1, 'the conflict and close add no writes');

  pageA.api.dispose();
  pageB.api.dispose();
  reopenedPage.api.dispose();
});

test('settings keep the exact legacy codex namespace when nothing is injected', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: '', introCaption: '', artworkSubtitle: '', wallpaperStrength: 0,
  });
  assert.deepEqual(storage.state.opens, [{ name: 'azhou-codex-startup', version: 1 }],
    'the default namespace stays azhou-codex-startup/version 1 verbatim');
  fixture.api.dispose();
});

test('an injected settings namespace replaces database name, version, store and key', async () => {
  const seen = { opens: [], stores: [], keys: [] };
  const record = {
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: '', introCaption: '', artworkSubtitle: '', wallpaperStrength: 0,
  };
  const objectStore = {
    get(key) {
      seen.keys.push({ operation: 'get', key });
      const request = { result: key === 'images-v3' ? JSON.parse(JSON.stringify(record)) : undefined, error: null };
      queueMicrotask(() => request.onsuccess?.({ target: request }));
      return request;
    },
    put(value, key) {
      seen.keys.push({ operation: 'put', key });
      const request = { result: key, error: null };
      queueMicrotask(() => request.onsuccess?.({ target: request }));
      return request;
    },
  };
  const database = {
    objectStoreNames: { contains: () => true },
    transaction(store) {
      seen.stores.push(store);
      const transaction = { oncomplete: null, onerror: null, onabort: null, abort() {}, objectStore: () => objectStore };
      // Complete only after the store requests delivered on the earlier microtask.
      queueMicrotask(() => queueMicrotask(() => transaction.oncomplete?.({ target: transaction })));
      return transaction;
    },
    close() {},
  };
  const indexedDB = {
    open(name, version) {
      seen.opens.push({ name, version });
      const request = { result: database, error: null, transaction: null };
      queueMicrotask(() => {
        request.onupgradeneeded?.({ oldVersion: 0, newVersion: version, target: request });
        request.onsuccess?.({ target: request });
      });
      return request;
    },
  };
  const fixture = makeFixture({
    indexedDB,
    settingsNamespace: {
      databaseName: 'azhou-synthetic-host', databaseVersion: 3, storeName: 'synthetic-settings', settingsKey: 'images-v3',
    },
  });
  await fixture.api.load(record);
  assert.deepEqual(seen.opens, [{ name: 'azhou-synthetic-host', version: 3 }],
    'an injected namespace replaces the database name and version');
  assert.ok(seen.stores.length > 0 && seen.stores.every(store => store === 'synthetic-settings'),
    'an injected namespace replaces the object store');
  assert.ok(seen.keys.length === 3 && seen.keys.some(({ key }) => key === 'images-v3') && seen.keys.some(({ key }) => key === 'images-v3:themeState') && seen.keys.some(({ key }) => key === 'images-v3:appearancePresets'),
    'an injected namespace replaces the record key');
  fixture.api.dispose();
});

test('invalid injected namespace values fall back to the verbatim defaults', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({ indexedDB: storage.indexedDB, settingsNamespace: {
    databaseName: '', databaseVersion: 0, storeName: 42, settingsKey: 'x'.repeat(101),
  } });
  await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0, 0], [1, 1]]],
    introTitle: '', introCaption: '', artworkSubtitle: '', wallpaperStrength: 0,
  });
  assert.deepEqual(storage.state.opens, [{ name: 'azhou-codex-startup', version: 1 }],
    'out-of-contract namespace fields keep the default namespace instead of inventing one');
  fixture.api.dispose();
});

test('theme selection rejects unknown catalog entries before persisting images', async () => {
  const storage = makeIndexedDB(undefined);
  const fixture = makeFixture({ indexedDB: storage.indexedDB,
    imageDimensions: [[512, 512], [1536, 1024]] });
  const loaded = await fixture.api.load({
    avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB',
    contours: [[[0, 0], [1, 1]]], wallpaperStrength: 42,
  });
  await assert.rejects(fixture.api.save(loaded.settings, {
    activeThemeId: 'unapproved-theme', surfaceTransparency: { mode: 'follow' },
  }), error => error.reason === 'settings-invalid');
  assert.equal(storage.state.puts, 0);
  fixture.api.dispose();
});

 test('approved theme saves and reloads with an images digest binding', async () => {
  const storage = makeIndexedDB(undefined);
  const fixture = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
  const defaults = { avatar: 'data:image/png;base64,AAAA', artwork: 'data:image/png;base64,BBBB', contours: [[[0,0],[1,1]]], wallpaperStrength: 42 };
  const loaded = await fixture.api.load(defaults);
  await fixture.api.save(loaded.settings, {activeThemeId: 'azhou-q-v3', surfaceTransparency: {mode: 'override', value: 30}});
  assert.equal(storage.state.themeRecord.activeThemeId, 'azhou-q-v3');
  assert.match(storage.state.themeRecord.imagesBinding, /^[a-f0-9]{64}$/);
  fixture.api.dispose();
  const fresh = makeFixture({ indexedDB: storage.indexedDB, imageDimensions: [[512, 512], [1536, 1024]] });
  const snapshot = await fresh.api.loadSnapshot(defaults);
  assert.equal(snapshot.themeState.preferencesByTheme['azhou-q-v3'].value, 30);
  fresh.api.dispose();
});

for (const scenario of ['old-writer', 'abort']) test('theme transaction protects '+scenario, async () => {
  const options = {};
  const storage = makeIndexedDB(undefined, options);
  const setup = () => makeFixture({indexedDB: storage.indexedDB, imageDimensions: [[512,512],[1536,1024],[512,512],[1536,1024]]});
  const fixture = setup();
  const defaults = {avatar:'data:image/png;base64,AAAA', artwork:'data:image/png;base64,BBBB', contours:[[[0,0],[1,1]]],wallpaperStrength:42};
  const loaded = await fixture.api.load(defaults);
  const selection = {activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'follow'}};
  await fixture.api.save(loaded.settings, selection);
  const before = JSON.stringify([storage.state.record, storage.state.themeRecord]);
  if (scenario === 'abort') {
    options.putError = {name:'QuotaExceededError'};
    await assert.rejects(fixture.api.save({...loaded.settings, wallpaperStrength:30}, selection), error => error.reason === 'settings-quota');
    assert.equal(JSON.stringify([storage.state.record, storage.state.themeRecord]), before);
  } else {
    storage.state.record.wallpaperStrength = 30;
    await assert.rejects(fixture.api.save(loaded.settings, selection), error => error.reason === 'settings-conflict');
    const fresh = setup();
    const snapshot = await fresh.api.loadSnapshot(defaults);
    assert.equal(snapshot.themeState, null);
    assert.equal(snapshot.settings.wallpaperStrength, 30);
    fresh.api.dispose();
  }
  fixture.api.dispose();
});

for (const themeRecord of [{schemaVersion: 2}, {schemaVersion: 1, imagesBinding: 'broken'}]) {
  test((themeRecord.schemaVersion === 1 ? 'damaged known theme state remains recoverable ' : 'unknown theme schema remains read-only ')+themeRecord.schemaVersion, async () => {
    const record = {schemaVersion:1, avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],introTitle:'Legacy',introCaption:'',artworkSubtitle:'',wallpaperStrength:42};
    const storage = makeIndexedDB(record, {themeRecord});
    const fixture = makeFixture({indexedDB:storage.indexedDB,imageDimensions:[[512,512],[1536,1024],[512,512],[1536,1024]]});
    const snapshot = await fixture.api.loadSnapshot(record);
    if (themeRecord.schemaVersion !== 1) {
      assert.equal(snapshot.status,'failure');assert.equal(snapshot.reason,'settings-blocked');
      await assert.rejects(fixture.api.save({...record,introTitle:'Must not erase future'}),{reason:'settings-blocked'});
      assert.deepEqual(storage.state.themeRecord,themeRecord);assert.equal(storage.state.puts,0);fixture.api.dispose();return;
    }
    assert.equal(snapshot.status,'valid');
    assert.equal(snapshot.settings.introTitle,'Legacy');
    assert.equal(snapshot.themeState,null);
    assert.equal(snapshot.themeReason,'settings-invalid');
    await fixture.api.save({...record,introTitle:'Recovered'});
    assert.equal(storage.state.record.introTitle,'Recovered');
    assert.equal(storage.state.themeRecord,null);
    fixture.api.dispose();
  });
}

test('theme controls save a committed preference and cancel never rolls it back', async () => {
  const storage = makeIndexedDB();
  const fixture = makeFixture({indexedDB:storage.indexedDB,imageDimensions:[[512,512],[1536,1024],[512,512],[1536,1024]]});
  await fixture.api.load({avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],wallpaperStrength:42});
  let applied;
  fixture.api.openSettings({onApply: async value => { applied=value; return {applied:false,reason:'wallpaper-unsupported'}; }});
  const control = attr => fixture.elements.find(element => element.getAttribute(attr) === '');
  const choice = control('data-agent-skin-theme-choice');
  choice.value='azhou-q-v3'; choice.listeners.get('change')[0]();
  const mode=control('data-agent-skin-theme-alpha-mode');
  mode.value='override'; mode.listeners.get('change')[0]();
  const alpha=control('data-agent-skin-theme-transparency');
  alpha.value='65'; alpha.listeners.get('input')[0]();
  const save=fixture.elements.find(element => element.tagName==='BUTTON' && element.textContent==='保存');
  await save.listeners.get('click')[0]();
  assert.equal(applied.themeState.preferencesByTheme['azhou-q-v3'].value,65);
  const committed=JSON.stringify(storage.state.themeRecord);
  fixture.api.cancelSettings();
  assert.equal(JSON.stringify(storage.state.themeRecord),committed);
  fixture.api.openSettings();
  assert.equal(alpha.value,'65');
  choice.value=''; choice.listeners.get('change')[0]();
  fixture.api.cancelSettings();
  assert.equal(JSON.stringify(storage.state.themeRecord),committed);
  fixture.api.dispose();
});

test('maximum theme revision cannot persist an unreadable increment and legacy recovery remains available', async () => {
  const storage=makeIndexedDB();
  const fixture=makeFixture({indexedDB:storage.indexedDB,imageDimensions:[[512,512],[1536,1024],[512,512],[1536,1024]]});
  const loaded=await fixture.api.load({avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],wallpaperStrength:42});
  const selection={activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'follow'}};
  await fixture.api.save(loaded.settings,selection);
  fixture.api.dispose();
  storage.state.themeRecord.revision=Number.MAX_SAFE_INTEGER;
  const fresh=makeFixture({indexedDB:storage.indexedDB,imageDimensions:[[512,512],[1536,1024],[512,512],[1536,1024]]});
  await fresh.api.load(loaded.settings);
  const before=JSON.stringify(storage.state.themeRecord);
  await assert.rejects(fresh.api.save(loaded.settings,selection), error=>error.reason==='settings-invalid');
  assert.equal(JSON.stringify(storage.state.themeRecord),before);
  await fresh.api.save(loaded.settings);
  assert.equal(storage.state.themeRecord.activeThemeId,null);
  assert.equal(storage.state.themeRecord.preferencesByTheme['azhou-q-v3'].mode,'follow');
  fresh.api.dispose();
});

for (const revision of ['bad', -3, 1.5]) test('invalid raw theme revision recovers to a readable record '+revision, async () => {
  const storage=makeIndexedDB(undefined,{themeRecord:{schemaVersion:1,revision}});
  const setup=()=>makeFixture({indexedDB:storage.indexedDB,imageDimensions:[[512,512],[1536,1024]]});
  const fixture=setup();
  const defaults={avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],wallpaperStrength:42};
  const loaded=await fixture.api.load(defaults);
  await fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  assert.equal(storage.state.themeRecord.revision,1);
  fixture.api.dispose();
  const fresh=setup();
  const snapshot=await fresh.api.loadSnapshot(defaults);
  assert.equal(snapshot.themeState.preferencesByTheme['azhou-q-v3'].value,65);
  fresh.api.dispose();
});

test('legacy appearance keeps theme preference across restart and reselection', async () => {
  const storage=makeIndexedDB();
  const setup=()=>makeFixture({indexedDB:storage.indexedDB,imageDimensions:Array.from({length:6},(_,i)=>i%2?[1536,1024]:[512,512])});
  const first=setup();
  const defaults={avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],wallpaperStrength:42};
  const loaded=await first.api.load(defaults);
  await first.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  await first.api.save(loaded.settings);
  assert.equal(storage.state.themeRecord.activeThemeId,null);
  assert.equal(storage.state.themeRecord.preferencesByTheme['azhou-q-v3'].value,65);
  first.api.dispose();
  const fresh=setup();
  const snapshot=await fresh.api.loadSnapshot(defaults);
  assert.equal(snapshot.themeState,null);
  fresh.api.openSettings();
  const control=attr=>fresh.elements.find(el=>el.getAttribute(attr)==='');
  const choice=control('data-agent-skin-theme-choice');
  assert.equal(choice.value,'');
  choice.value='azhou-q-v3';choice.listeners.get('change')[0]();
  assert.equal(control('data-agent-skin-theme-transparency').value,'65');
  const save=fresh.elements.find(el=>el.tagName==='BUTTON'&&el.textContent==='保存');
  await save.listeners.get('click')[0]();
  assert.equal(storage.state.themeRecord.activeThemeId,'azhou-q-v3');
  assert.equal(storage.state.themeRecord.preferencesByTheme['azhou-q-v3'].value,65);
  fresh.api.dispose();
});

function themeDraftFixture(storage=makeIndexedDB()) {
  const fixture=makeFixture({indexedDB:storage.indexedDB,imageDimensions:Array.from({length:40},(_,i)=>i%2?[1536,1024]:[512,512])});
  const defaults={avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],wallpaperStrength:42};
  const control=attr=>fixture.elements.find(el=>el.getAttribute(attr)==='');
  const choose=value=>{const el=control('data-agent-skin-theme-choice');el.value=value;el.listeners.get('change')[0]();};
  const click=label=>fixture.elements.find(el=>el.tagName==='BUTTON'&&el.textContent===label).listeners.get('click')[0]();
  return {fixture,defaults,storage,control,choose,click};
}

test('Restore all defaults resets remembered theme preference only after save',async()=>{
  const f=themeDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  await f.fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  f.fixture.api.openSettings();f.click('恢复全部默认');await f.click('保存');
  assert.equal(f.storage.state.themeRecord.activeThemeId,null);
  assert.deepEqual(f.storage.state.themeRecord.preferencesByTheme['azhou-q-v3'],{mode:'follow'});
  f.fixture.api.dispose();
});

test('existing custom appearance survives a theme draft round trip and save',async()=>{
  const f=themeDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  const custom={...loaded.settings,artwork:'data:image/png;base64,CCCC',contours:[[[2,2],[3,3]]]};
  await f.fixture.api.save(custom);
  f.fixture.api.openSettings();f.choose('azhou-q-v3');f.choose('');await f.click('保存');
  assert.equal(f.storage.state.record.artwork,custom.artwork);
  assert.deepEqual(f.storage.state.record.contours,custom.contours);
  f.fixture.api.dispose();
});

test('theme draft opacity survives inactive round trip without replacing saved preference',async()=>{
  const f=themeDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  await f.fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  f.fixture.api.openSettings();const alpha=f.control('data-agent-skin-theme-transparency');alpha.value='80';alpha.listeners.get('input')[0]();
  f.choose('');f.choose('azhou-q-v3');
  assert.equal(f.control('data-agent-skin-theme-transparency').value,'80');
  f.click('取消');assert.equal(f.storage.state.themeRecord.preferencesByTheme['azhou-q-v3'].value,65);
  f.fixture.api.dispose();
});

test('restore-all cancellation preserves both saved custom appearance and theme preference',async()=>{
  const f=themeDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  const custom={...loaded.settings,artwork:'data:image/png;base64,CCCC',contours:[[[2,2],[3,3]]]};
  await f.fixture.api.save(custom,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  const before=JSON.stringify({images:f.storage.state.record,theme:f.storage.state.themeRecord});
  f.fixture.api.openSettings();f.click('恢复全部默认');f.click('取消');
  assert.equal(JSON.stringify({images:f.storage.state.record,theme:f.storage.state.themeRecord}),before);
  f.fixture.api.openSettings();assert.equal(f.control('data-agent-skin-theme-transparency').value,'65');f.click('取消');
  f.fixture.api.dispose();
});

test('inactive save retains edited theme preference and round-trip image without activation',async()=>{
  const f=themeDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  const custom={...loaded.settings,artwork:'data:image/png;base64,CCCC',contours:[[[2,2],[3,3]]]};
  await f.fixture.api.save(custom);
  f.fixture.api.openSettings();f.choose('azhou-q-v3');
  const mode=f.control('data-agent-skin-theme-alpha-mode');mode.value='override';mode.listeners.get('change')[0]();
  const alpha=f.control('data-agent-skin-theme-transparency');alpha.value='80';alpha.listeners.get('input')[0]();
  f.choose('');await f.click('保存');
  assert.equal(f.storage.state.themeRecord.activeThemeId,null);
  assert.equal(f.storage.state.themeRecord.preferencesByTheme['azhou-q-v3'].value,80);
  assert.equal(f.storage.state.record.artwork,custom.artwork);
  f.fixture.api.dispose();
});

test('restore-all conflict leaves winner images and theme preference unchanged',async()=>{
  const f=themeDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  await f.fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  f.fixture.api.openSettings();f.click('恢复全部默认');
  f.storage.state.record={...f.storage.state.record,introTitle:'Other page'};
  const winner=JSON.stringify({images:f.storage.state.record,theme:f.storage.state.themeRecord});
  await f.click('保存');
  assert.equal(f.fixture.api.isSettingsOpen(),true);
  assert.equal(JSON.stringify({images:f.storage.state.record,theme:f.storage.state.themeRecord}),winner);
  f.click('取消');f.fixture.api.dispose();
});

test('native theme bridge prepares a production settings snapshot', {skip: !process.env.AZHOU_THEME_BRIDGE_INPUT}, async () => {
  const {writeFile}=await import('node:fs/promises');
  const storage=makeIndexedDB();
  const fixture=makeFixture({indexedDB:storage.indexedDB,imageDimensions:Array.from({length:6},(_,i)=>i%2?[1536,1024]:[512,512])});
  const png='data:image/png;base64,iVBORw0KGgo=';
  const loaded=await fixture.api.load({avatar:png,artwork:png,contours:[[[0,0],[100,100]]],wallpaperStrength:42});
  await fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  const snapshot=await fixture.api.loadSnapshot(loaded.settings);
  await writeFile(process.env.AZHOU_THEME_BRIDGE_INPUT,JSON.stringify({status:snapshot.status,settings:snapshot.settings,explicitText:snapshot.explicitText,appearance:{locale:'en',theme:'dark'},themeState:snapshot.themeState}));
  fixture.api.dispose();
});

test('theme fields expose visible labels, truthful values and independent strength', async () => {
  const f = themeDraftFixture();
  await f.fixture.api.load(f.defaults);
  f.fixture.api.openSettings();
  const choice = f.control('data-agent-skin-theme-choice');
  const mode = f.control('data-agent-skin-theme-alpha-mode');
  const alpha = f.control('data-agent-skin-theme-transparency');
  for (const [control, text] of [[choice, '主题'], [mode, '阅读遮罩设置'], [alpha, '阅读遮罩透明度']]) {
    assert.ok(control.id, 'each theme field has a stable label target');
    const label = f.fixture.elements.find(el => el.tagName === 'LABEL' && el.htmlFor === control.id);
    assert.ok(label && label.textContent === text, 'visible associated label: ' + text);
    assert.equal(control.style.getPropertyValue('width'), '100%');
    assert.equal(control.style.getPropertyValue('margin'), '0', 'full-width native controls do not retain browser margins');
  }
  const value = f.control('data-agent-skin-theme-transparency-value');
  const reason = f.control('data-agent-skin-theme-transparency-reason');
  assert.ok(alpha.getAttribute('aria-describedby').split(' ').includes(reason.id));
  assert.equal(reason.textContent, '选择阿舟主题后可调整');
  assert.equal(alpha.disabled, true);
  f.choose('azhou-q-v3');
  assert.equal(value.textContent, '跟随主题');
  assert.equal(alpha.getAttribute('aria-valuetext'), '跟随主题');
  assert.equal(reason.textContent, '使用主题默认遮罩；选择自定义后可调整');
  mode.value = 'override'; mode.listeners.get('change')[0]();
  for (const transparency of [0, 50, 100]) {
    alpha.value = String(transparency); alpha.listeners.get('input')[0]();
    assert.equal(value.textContent, transparency + '%');
    assert.equal(alpha.getAttribute('aria-valuetext'), transparency + '%');
    assert.equal(alpha.disabled, false);
    assert.equal(f.fixture.elements.find(el => el.id === 'agent-skin-settings-wallpaper-strength').value, '42');
  }
  f.fixture.api.cancelSettings(); f.fixture.api.openSettings();
  assert.equal(value.textContent, '跟随主题');
  assert.equal(reason.textContent, '选择阿舟主题后可调整');
  f.fixture.api.dispose();
});

test('theme field language changes preserve visible values and saved settings', async () => {
  const localization = createLocalization({locale:'zh-CN'});
  const storage = makeIndexedDB();
  const fixture = makeFixture({localization,indexedDB:storage.indexedDB,imageDimensions:[[512,512],[1536,1024]]});
  await fixture.api.load({avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],wallpaperStrength:42});
  fixture.api.openSettings();
  const control = attr => fixture.elements.find(el=>el.getAttribute(attr)==='');
  const choice=control('data-agent-skin-theme-choice'),mode=control('data-agent-skin-theme-alpha-mode'),alpha=control('data-agent-skin-theme-transparency');
  choice.value='azhou-q-v3';choice.listeners.get('change')[0]();
  mode.value='override';mode.listeners.get('change')[0]();alpha.value='50';alpha.listeners.get('input')[0]();
  localization.setLocale('en');
  for(const [el,text] of [[choice,'Theme'],[mode,'Reading mask settings'],[alpha,'Reading mask transparency']]) {
    assert.equal(fixture.elements.find(label=>label.tagName==='LABEL'&&label.htmlFor===el.id).textContent,text);
  }
  assert.equal(control('data-agent-skin-theme-transparency-value').textContent,'50%');
  mode.value='follow';mode.listeners.get('change')[0]();
  assert.equal(control('data-agent-skin-theme-transparency-value').textContent,'Follow theme');
  assert.equal(control('data-agent-skin-theme-transparency-reason').textContent,'Using the theme default mask; select Custom to adjust');
  const strength=fixture.elements.find(el=>el.id==='agent-skin-settings-wallpaper-strength');
  strength.value='0';strength.listeners.get('input')[0]();
  assert.equal(strength.max,'75');assert.equal(alpha.value,'50');
  assert.equal(fixture.elements.find(el=>el.getAttribute('data-agent-skin-workspace-preview-wash')==='').style.getPropertyValue('display'),'none');
  assert.equal(storage.state.puts,0);
  fixture.api.dispose();
});

test('Restore All synchronizes disabled theme controls without saving or changing cancellation', async () => {
  const f=themeDraftFixture();await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();
  f.choose('azhou-q-v3');const mode=f.control('data-agent-skin-theme-alpha-mode'),alpha=f.control('data-agent-skin-theme-transparency');
  mode.value='override';mode.listeners.get('change')[0]();alpha.value='80';alpha.listeners.get('input')[0]();
  assert.equal(mode.disabled,false);assert.equal(alpha.disabled,false);
  f.click('恢复全部默认');
  assert.equal(f.control('data-agent-skin-theme-choice').value,'');
  assert.equal(mode.disabled,true,'Restore All disables theme mode immediately');
  assert.equal(alpha.disabled,true,'Restore All disables the inactive slider immediately');
  assert.equal(f.control('data-agent-skin-theme-transparency-reason').textContent,'选择阿舟主题后可调整');
  assert.equal(f.storage.state.puts,0);f.fixture.api.cancelSettings();f.fixture.api.openSettings();
  assert.equal(mode.disabled,true);assert.equal(alpha.disabled,true);f.fixture.api.dispose();
});

function presetDraftFixture(storage=makeIndexedDB(),options={}) {
  const fixture=makeFixture({indexedDB:storage.indexedDB,dimensionsForSource:value=>value==='data:image/png;base64,AAAA'?[512,512]:[1536,1024],...options});
  const base=themeDraftFixture(storage);base.fixture.api.dispose();
  const control=attr=>fixture.elements.find(el=>el.getAttribute(attr)==='');
  return {...base,fixture,control,choose:value=>{const el=control('data-agent-skin-theme-choice');el.value=value;el.listeners.get('change')[0]();},click:label=>fixture.elements.find(el=>el.tagName==='BUTTON'&&el.textContent===label).listeners.get('click')[0]()};
}
function localPreset(artwork = 'data:image/png;base64,BBBB', value = 0) {
  return {id: 'local-fixture', name: '<img onerror=evil()>', recipeId: 'azhou-q-v3',
    appearance: {artwork, contours: [[[0,0],[1,1]]], wallpaperStrength: 42},
    surfaceTransparency: {mode:'override',value}};
}
test('local presets are draft-only, preserve startup fields and commit together', async()=>{
  const f=presetDraftFixture();await f.fixture.api.load(f.defaults);let applied=0;
  f.fixture.api.openSettings({onApply(){applied++;return {applied:true};}});
  f.choose('azhou-q-v3');
  const name=f.control('data-agent-skin-preset-name');assert.ok(name,'named local preset input exists');
  name.value='<b>A</b>';await f.click('新增预设');
  assert.equal(f.storage.state.puts,0);assert.equal(applied,0);
  f.click('取消');assert.equal(f.storage.state.libraryRecord,undefined);
  f.fixture.api.openSettings();f.choose('azhou-q-v3');name.value='A';await f.click('新增预设');
  await f.click('保存');
  assert.equal(f.storage.state.libraryRecord.entries[0].name,'A');
  assert.equal(f.storage.state.libraryRecord.schemaVersion,1);
  assert.equal(f.storage.state.libraryRecord.revision,1);
  assert.equal(f.storage.state.libraryRecord.entries[0].recipeId,'azhou-q-v3');
  assert.equal('avatar' in f.storage.state.libraryRecord.entries[0].appearance,false);
  f.fixture.api.dispose();
});
test('public save preserves a library and conflicts with a concurrent directory writer',async()=>{
  const storage=makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:1,entries:[]}});
  const f=themeDraftFixture(storage);const loaded=await f.fixture.api.load(f.defaults);
  await f.fixture.api.save(loaded.settings);assert.equal(storage.state.libraryRecord.revision,1);
  storage.state.libraryRecord={schemaVersion:1,revision:2,entries:[]};
  await assert.rejects(f.fixture.api.save(loaded.settings),e=>e.reason==='settings-conflict');
  assert.equal(storage.state.libraryRecord.revision,2);f.fixture.api.dispose();
});
for(const mutate of [x=>x.entries.push({...localPreset(),recipeId:'other'}),x=>x.extra=true,
  x=>x.entries.push({...localPreset(),appearance:{...localPreset().appearance,wallpaperStrength:76}}),
  x=>x.entries=Array.from({length:9},(_,i)=>({...localPreset(),id:String(i)}))]) {
  test('invalid local catalog fails closed without replacing valid current settings '+String(mutate),async()=>{
    const library={schemaVersion:1,revision:1,entries:[]};mutate(library);
    const storage=makeIndexedDB(undefined,{libraryRecord:library});const f=themeDraftFixture(storage);
    const loaded=await f.fixture.api.load(f.defaults);assert.equal(loaded.settings.artwork,f.defaults.artwork);
    f.fixture.api.openSettings();assert.equal(f.control('data-agent-skin-preset-name').disabled,true);
    f.click('取消');assert.deepEqual(storage.state.libraryRecord,library);f.fixture.api.dispose();
  });
}

test('A/B presets load distinct images and transparency endpoints, keep startup fields and survive reopen', async()=>{
  const storage=makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:1,entries:[localPreset(),{...localPreset('data:image/png;base64,CCCC',100),id:'B',name:'B'}]}});
  const f=presetDraftFixture(storage);await f.fixture.api.load(f.defaults);
  let applied=0;f.fixture.api.openSettings({onApply(){applied++;return {applied:true};}});
  const title=f.fixture.elements.find(el=>el.tagName==='INPUT'&&el.type==='text'&&el.getAttribute('data-agent-skin-preset-name')===null);
  title.value='Keep startup';title.listeners.get('input')[0]();
  const list=f.control('data-agent-skin-preset-list');
  assert.equal(list.children[0].textContent,'<img onerror=evil()>');
  const preview=f.fixture.elements.find(el=>el.getAttribute('data-agent-skin-workspace-preview-image')==='');
  for(const [id,image,alpha] of [['local-fixture','BBBB','0'],['B','CCCC','100']]) {
    list.value=id;f.click('载入到草稿');assert.equal(preview.src,'data:image/png;base64,'+image);
    assert.equal(f.control('data-agent-skin-theme-transparency').value,alpha);assert.equal(title.value,'Keep startup');
    assert.equal(storage.state.puts,0);assert.equal(applied,0);
  }
  await f.click('保存');assert.equal(applied,1);assert.equal(storage.state.record.avatar,f.defaults.avatar);
  assert.equal(storage.state.record.artwork,'data:image/png;base64,CCCC');assert.equal(storage.state.record.introTitle,'Keep startup');
  assert.equal(storage.state.themeRecord.preferencesByTheme['azhou-q-v3'].value,100);
  assert.equal(storage.state.libraryRecord.revision,1,'loading does not revise the library');
  f.fixture.api.openSettings();list.value='local-fixture';f.click('载入到草稿');await f.click('保存');
  assert.equal(storage.state.themeRecord.preferencesByTheme['azhou-q-v3'].value,0);
  const reopened=presetDraftFixture(storage);const loaded=await reopened.fixture.api.load(reopened.defaults);
  assert.equal(loaded.settings.artwork,'data:image/png;base64,BBBB');reopened.fixture.api.openSettings();
  assert.equal(reopened.control('data-agent-skin-theme-transparency').value,'0');
  reopened.fixture.api.dispose();f.fixture.api.dispose();
});
for (const key of ['record','themeRecord','libraryRecord']) {
  test('a concurrent '+key+' writer prevents all three draft records from committing',async()=>{
    const f=presetDraftFixture();const loaded=await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();f.choose('azhou-q-v3');
    f.control('data-agent-skin-preset-name').value='new';await f.click('新增预设');
    f.storage.state[key]=key==='record'?{...loaded.settings,introTitle:'winner'}:key==='themeRecord'?{winner:true}:{schemaVersion:1,revision:2,entries:[]};
    const before=JSON.stringify([f.storage.state.record,f.storage.state.themeRecord,f.storage.state.libraryRecord]);
    await f.click('保存');assert.equal(JSON.stringify([f.storage.state.record,f.storage.state.themeRecord,f.storage.state.libraryRecord]),before);
    assert.equal(f.storage.state.puts,0);assert.equal(f.fixture.api.isSettingsOpen(),true);f.fixture.api.dispose();
  });
}
for(const failure of ['quota','abort','cancel','timeout']) {
  test('local preset '+failure+' leaves three committed records untouched',async()=>{
    const options={};const storage=makeIndexedDB(undefined,options);const f=presetDraftFixture(storage);
    await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();f.choose('azhou-q-v3');
    f.control('data-agent-skin-preset-name').value='candidate';await f.click('新增预设');
    if(failure==='quota') options.putError={name:'QuotaExceededError'};
    if(failure==='abort') options.afterRequest=({kind,transaction})=>{if(kind==='put')transaction.abort();};
    if(failure==='cancel'||failure==='timeout') options.holdRequests=true;
    const saving=f.click('保存');
    if(failure==='cancel'||failure==='timeout') {
      await new Promise(resolve=>setImmediate(resolve));
      if(failure==='cancel') f.fixture.api.dispose();else f.fixture.advance(10_001);
    }
    await saving;assert.equal(storage.state.record,undefined);assert.equal(storage.state.themeRecord,undefined);assert.equal(storage.state.libraryRecord,undefined);
    f.fixture.api.dispose();
  });
}
test('catalog limits reject bad names, duplicate IDs, extra keys, huge JSON and undecodable images',async()=>{
  const f=presetDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  for(const entries of [ [{...localPreset(),name:' '}], [{...localPreset(),name:'x'.repeat(41)}],
    [localPreset(),localPreset()], [{...localPreset(),css:'body{}'}],
    [{...localPreset(),appearance:{...localPreset().appearance,contours:[[[0,0]]]}}],
    Array.from({length:3},(_,i)=>({...localPreset('data:image/png;base64,'+'A'.repeat(8*1024*1024)),id:'big-'+i}))]) {
    await assert.rejects(f.fixture.api.save(loaded.settings,undefined,{schemaVersion:1,revision:0,entries}),e=>['settings-invalid','asset-invalid'].includes(e.reason));
  }
  assert.equal(f.storage.state.puts,0);f.fixture.api.dispose();
  const storage=makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:1,entries:[localPreset()]}});
  const fixture=makeFixture({indexedDB:storage.indexedDB,decode:'error'});const result=await fixture.api.load(f.defaults);
  assert.equal(result.settings.artwork,f.defaults.artwork);fixture.api.openSettings();
  assert.equal(fixture.elements.find(el=>el.getAttribute('data-agent-skin-preset-name')==='').disabled,true);fixture.api.dispose();
});
test('restore defaults and embedded cancellation retain the catalog and discard new entries',async()=>{
  const storage=makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:3,entries:[]}});const f=presetDraftFixture(storage);
  await f.fixture.api.load(f.defaults);f.fixture.api.openSettings({}, {presentation:'embedded'});f.choose('azhou-q-v3');
  f.control('data-agent-skin-preset-name').value='not saved';await f.click('新增预设');
  f.click('恢复全部默认');assert.equal(f.control('data-agent-skin-preset-list').children.length,1);
  f.click('取消');assert.equal(f.control('data-agent-skin-preset-list').children.length,0);
  assert.equal(storage.state.libraryRecord.revision,3);assert.equal(storage.state.puts,0);f.fixture.api.dispose();
});

test('embedded cancel restores theme selection and committed library revision',async()=>{
  const f=presetDraftFixture();await f.fixture.api.load(f.defaults);f.fixture.api.openSettings({}, {presentation:'embedded'});
  f.choose('azhou-q-v3');f.control('data-agent-skin-preset-name').value='A';await f.click('新增预设');await f.click('保存');
  assert.equal(f.storage.state.libraryRecord.revision,1);await f.click('保存');
  assert.equal(f.storage.state.libraryRecord.revision,1,'unchanged embedded catalog is not rewritten');
  f.choose('');f.click('取消');assert.equal(f.control('data-agent-skin-theme-choice').value,'azhou-q-v3');
  assert.equal(f.storage.state.libraryRecord.revision,1);f.fixture.api.dispose();
});
test('a timed-out library image does not replace valid saved appearance',async()=>{
  const record={schemaVersion:1,avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],introTitle:'Keep saved',introCaption:'',artworkSubtitle:'',wallpaperStrength:17};
  const storage=makeIndexedDB(record,{libraryRecord:{schemaVersion:1,revision:1,entries:[localPreset('data:image/png;base64,CCCC')]}});
  const fixture=makeFixture({indexedDB:storage.indexedDB,dimensionsForSource:v=>v===record.avatar?[512,512]:[1536,1024],decodeForSource:v=>v.endsWith('CCCC')?'pending':''});
  const loading=fixture.api.load({...record,artwork:'data:image/png;base64,DDDD'});
  await new Promise(resolve=>setImmediate(resolve));fixture.advance(4001);const loaded=await loading;
  assert.equal(loaded.settings.artwork,record.artwork);assert.equal(loaded.settings.wallpaperStrength,17);assert.equal(storage.state.puts,0);
  fixture.api.openSettings();assert.equal(fixture.elements.find(el=>el.getAttribute('data-agent-skin-preset-name')==='').disabled,true);fixture.api.dispose();
});

for (const kind of ['BigInt', 'cyclic']) {
  test('an unchanged '+kind+' invalid catalog stays read-only while active appearance saves', async () => {
    const library = kind === 'BigInt' ? {corrupt: 1n} : {corrupt: true};
    if (kind === 'cyclic') library.self = library;
    const storage = makeIndexedDB(undefined, {libraryRecord: library});
    const f = presetDraftFixture(storage);
    const loaded = await f.fixture.api.load(f.defaults);
    f.fixture.api.openSettings();
    assert.equal(f.control('data-agent-skin-preset-name').disabled, true);
    await f.fixture.api.save({...loaded.settings, introTitle: 'Still editable'});
    assert.equal(storage.state.record.introTitle, 'Still editable');
    assert.deepEqual(storage.state.libraryRecord, library);
    assert.equal(storage.state.puts, 1, 'only active images are written');
    const changed = structuredClone(library);
    changed.corrupt = kind === 'BigInt' ? 2n : false;
    storage.state.libraryRecord = changed;
    await assert.rejects(f.fixture.api.save(loaded.settings), error => error.reason === 'settings-conflict');
    assert.deepEqual(storage.state.libraryRecord, changed);
    assert.equal(storage.state.record.introTitle, 'Still editable');
    f.fixture.api.dispose();
  });
}

test('a valid active snapshot does not wait for decoding inactive preset images', async () => {
  const record = {schemaVersion:1, avatar:'data:image/png;base64,AAAA', artwork:'data:image/png;base64,BBBB',
    contours:[[[0,0],[1,1]]], introTitle:'Keep saved', introCaption:'', artworkSubtitle:'', wallpaperStrength:17};
  const library = {schemaVersion:1, revision:1, entries:Array.from({length:8}, (_,i) => ({...localPreset('data:image/png;base64,CCCC'), id:'preset-'+i}))};
  const storage = makeIndexedDB(record, {libraryRecord:library});
  const fixture = makeFixture({indexedDB:storage.indexedDB,
    dimensionsForSource:value=>value===record.avatar?[512,512]:[1536,1024],
    decodeForSource:value=>value.endsWith('CCCC')?'pending':''});
  const loading = fixture.api.loadSnapshot(record);
  const snapshot = await Promise.race([loading, new Promise(resolve=>setImmediate(()=>resolve({status:'blocked-by-inactive-catalog'})))]);
  assert.equal(snapshot.status, 'valid');
  assert.equal(snapshot.settings.artwork, record.artwork);
  assert.equal(snapshot.settings.wallpaperStrength, 17);
  assert.equal(fixture.images.length, 2, 'only active avatar and wallpaper are decoded');
  assert.equal(storage.state.puts, 0);
  fixture.api.dispose();
});

for (const [kind, initial, changed] of [
  ['undefined', {value:undefined}, {}],
  ['non-finite number', {value:NaN}, {value:null}],
  ['Date', {value:new Date(0)}, {value:new Date(1)}],
  ['Date type', {value:new Date(0)}, {value:new Date(0).toISOString()}],
  ['RegExp', {value:/first/i}, {value:/second/i}],
  ['Map', {value:new Map([['key', 1]])}, {value:new Map([['key', 2]])}],
  ['Set', {value:new Set([1])}, {value:new Set([2])}],
  ['ArrayBuffer', {value:Uint8Array.of(1).buffer}, {value:Uint8Array.of(2).buffer}],
  ['typed array', {value:Uint8Array.of(1)}, {value:Uint8Array.of(2)}],
  ['view type', {value:Uint8Array.of(1)}, {value:Int8Array.of(1)}],
  ['sparse array', {value:new Array(1)}, {value:[undefined]}],
  ['alias topology', (()=>{const value={};return {a:value,b:value};})(), {a:{},b:{}}],
]) {
  test('invalid catalog '+kind+' uses clone equality without hiding concurrent changes', async () => {
    const storage = makeIndexedDB(undefined, {libraryRecord:initial});
    const f = presetDraftFixture(storage);
    const loaded = await f.fixture.api.load(f.defaults);
    await f.fixture.api.save({...loaded.settings, introTitle:'Saved safely'});
    assert.deepEqual(storage.state.libraryRecord, initial);
    storage.state.libraryRecord = changed;
    await assert.rejects(f.fixture.api.save(loaded.settings), error=>error.reason==='settings-conflict');
    assert.equal(storage.state.record.introTitle, 'Saved safely');
    assert.deepEqual(storage.state.libraryRecord, changed);
    f.fixture.api.dispose();
  });
}

test('a snapshot leaves unvalidated catalog disabled and normal load still rejects bad preset images', async () => {
  const storage = makeIndexedDB(undefined, {libraryRecord:{schemaVersion:1, revision:1, entries:[localPreset('data:image/png;base64,CCCC')]}});
  const fixture = makeFixture({indexedDB:storage.indexedDB,
    dimensionsForSource:value=>value.endsWith('AAAA')?[512,512]:value.endsWith('CCCC')?[1,1]:[1536,1024]});
  const defaults = {avatar:'data:image/png;base64,AAAA', artwork:'data:image/png;base64,BBBB', contours:[[[0,0],[1,1]]]};
  const snapshot = await fixture.api.loadSnapshot(defaults);
  assert.equal(snapshot.status, 'missing');
  fixture.api.openSettings();
  const name = fixture.elements.find(el=>el.getAttribute('data-agent-skin-preset-name')==='');
  assert.equal(name.disabled, true, 'snapshot never exposes unchecked catalog entries');
  fixture.api.cancelSettings();
  const loaded = await fixture.api.load(defaults);
  fixture.api.openSettings();
  assert.equal(name.disabled, true, 'normal settings load decodes and rejects wrong-size preset images');
  await assert.rejects(fixture.api.save(loaded.settings, undefined, storage.state.libraryRecord), error=>error.reason==='settings-invalid');
  assert.equal(storage.state.puts, 0);
  fixture.api.dispose();
});


function presetFile(entry = localPreset()) {
  const {id, ...content} = entry;
  return {schema:'azhou-appearance-preset.v1', ...content};
}
function jsonPresetFile(content = presetFile()) {
  const bytes = new TextEncoder().encode(JSON.stringify(content));
  return {size:bytes.byteLength, async arrayBuffer() { return bytes.buffer; }};
}
async function importPreset(f, file) {
  const input = f.control('data-agent-skin-preset-import');
  assert.ok(input, 'settings exposes an Azhou preset file input');
  input.files = [file]; input.value = 'C:\fakepath\preset.json';
  await input.listeners.get('change')[0]();
  assert.equal(input.value, '', 'file input resets for reimport');
}
test('exported Azhou file imports into another catalog, saves without applying and survives reopen', async () => {
  const sourceStorage = makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:7,entries:[localPreset()]}});
  const a = presetDraftFixture(sourceStorage); await a.fixture.api.load(a.defaults); a.fixture.api.openSettings();
  const output = a.control('data-agent-skin-preset-export'); assert.ok(output, 'selected preset export button exists');
  output.listeners.get('click')[0]();
  const blob = a.fixture.blobs[0];
  const content = JSON.parse(await blob.text());
  assert.deepEqual(content,presetFile());
  assert.equal(sourceStorage.state.puts,0);
  const anchor=a.fixture.elements.find(el=>el.tagName==='A');
  assert.equal(anchor.download,'azhou-preset.json'); assert.equal(anchor.removed,true);
  assert.deepEqual([...a.fixture.created],a.fixture.revoked);
  a.fixture.api.dispose();
  const b = presetDraftFixture(); const loaded = await b.fixture.api.load(b.defaults);
  await b.fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'override',value:65}});
  const before = structuredClone([b.storage.state.record,b.storage.state.themeRecord]); const puts=b.storage.state.puts;
  let applied=0,notified=0;
  b.fixture.api.openSettings({onApply(){applied++;return {applied:true};},onSaved(){notified++;}});
  await importPreset(b,blob);
  assert.equal(b.control('data-agent-skin-preset-list').children[0].textContent,localPreset().name);
  assert.equal(b.storage.state.puts,puts); assert.equal(applied,0);
  assert.equal(b.control('data-agent-skin-theme-transparency').value,'65');
  await b.click('保存');
  assert.equal(applied,0,'catalog-only save does not apply appearance'); assert.equal(notified,1,'normal save notification remains');
  assert.deepEqual([b.storage.state.record,b.storage.state.themeRecord],before,'catalog save preserves exact images/theme revisions');
  assert.equal(b.storage.state.puts,puts+1); assert.equal(b.storage.state.libraryRecord.entries.length,1);
  assert.notEqual(b.storage.state.libraryRecord.entries[0].id,localPreset().id);
  await b.fixture.api.load(b.defaults); b.fixture.api.openSettings();
  assert.equal(b.control('data-agent-skin-preset-list').children.length,1); b.fixture.api.dispose();
});
for (const mutate of [v=>v.extra=true,v=>v.id='foreign',v=>v.recipeId='dream',v=>v.appearance.artwork='https://example.com/a.png',v=>v.appearance.contours=[[[0,0],[Infinity,1]]],v=>v.surfaceTransparency={mode:'override',value:101},v=>v.appearance.avatar='data:image/png;base64,AAAA',v=>v.name='bad\u0000name']) {
  test('preset file rejects invalid boundary '+String(mutate),async()=>{
    const f=presetDraftFixture();await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();
    const content=presetFile();mutate(content);await importPreset(f,jsonPresetFile(content));
    assert.equal(f.control('data-agent-skin-preset-list').children.length,0);assert.equal(f.storage.state.puts,0);f.fixture.api.dispose();
  });
}
for(const kind of ['too-large-before','too-large-after','invalid-utf8','invalid-json']) {
  test('preset file rejects '+kind+' without staging',async()=>{
    const f=presetDraftFixture();await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();let reads=0;
    const file={size:kind==='too-large-before'?20*1024*1024+1:1,async arrayBuffer(){reads++;return kind==='too-large-after'?new ArrayBuffer(20*1024*1024+1):Uint8Array.of(kind==='invalid-utf8'?255:91).buffer;}};
    await importPreset(f,file);if(kind==='too-large-before')assert.equal(reads,0);
    assert.equal(f.control('data-agent-skin-preset-list').children.length,0);assert.equal(f.storage.state.puts,0);f.fixture.api.dispose();
  });
}
test('import cancellation and late file read do not write or stage into reopened panel',async()=>{
  const f=presetDraftFixture();await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();let release;
  const importing=importPreset(f,{size:1,arrayBuffer(){return new Promise(resolve=>release=resolve);}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.fixture.api.cancelSettings(),true);f.fixture.api.openSettings();
  release(await jsonPresetFile().arrayBuffer());await importing;
  assert.equal(f.control('data-agent-skin-preset-list').children.length,0);assert.equal(f.storage.state.puts,0);f.fixture.api.dispose();
});
test('imported file is discarded on embedded cancel and draft export never saves',async()=>{
  const f=presetDraftFixture();await f.fixture.api.load(f.defaults);f.fixture.api.openSettings({}, {presentation:'embedded'});
  await importPreset(f,jsonPresetFile());f.control('data-agent-skin-preset-export').listeners.get('click')[0]();
  assert.equal(f.storage.state.puts,0);f.click('取消');
  assert.equal(f.control('data-agent-skin-preset-list').children.length,0);assert.equal(f.fixture.created.length,1);assert.equal(f.fixture.revoked.length,1);f.fixture.api.dispose();
});

for(const failure of ['quota','abort','timeout','dispose']) {
  test('imported catalog-only save '+failure+' preserves all committed records',async()=>{
    const options={};const storage=makeIndexedDB(undefined,options);const f=presetDraftFixture(storage);
    const loaded=await f.fixture.api.load(f.defaults);await f.fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'follow'}});
    const before=structuredClone([storage.state.record,storage.state.themeRecord,storage.state.libraryRecord]);let applied=0;
    f.fixture.api.openSettings({onApply(){applied++;return {applied:true};}});await importPreset(f,jsonPresetFile());
    if(failure==='quota')options.putError={name:'QuotaExceededError'};
    if(failure==='abort')options.afterRequest=({kind,transaction})=>{if(kind==='put')transaction.abort();};
    if(failure==='timeout'||failure==='dispose')options.holdRequests=true;
    const saving=f.click('保存');
    if(failure==='timeout'||failure==='dispose'){
      await new Promise(resolve=>setImmediate(resolve));
      if(failure==='dispose')f.fixture.api.dispose();else f.fixture.advance(10_001);
    }
    await saving;assert.deepEqual([storage.state.record,storage.state.themeRecord,storage.state.libraryRecord],before);assert.equal(applied,0);f.fixture.api.dispose();
  });
}
for(const key of ['record','themeRecord','libraryRecord']) {
  test('imported catalog-only save checks concurrent '+key,async()=>{
    const f=presetDraftFixture();await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();await importPreset(f,jsonPresetFile());
    f.storage.state[key]={winner:true};await f.click('保存');
    assert.equal(f.storage.state.puts,0);assert.deepEqual(f.storage.state[key],{winner:true});f.fixture.api.dispose();
  });
}
for(const end of ['cancel','dispose','timeout']) {
  test('preset file late decode after '+end+' cannot stage or apply',async()=>{
    const f=presetDraftFixture(makeIndexedDB(),{decodeForSource:value=>value==='data:image/png;base64,CCCC'?'pending':undefined});
    await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();const importing=importPreset(f,jsonPresetFile(presetFile(localPreset('data:image/png;base64,CCCC'))));
    await new Promise(resolve=>setImmediate(resolve));const late=f.fixture.images.at(-1).onload;
    if(end==='cancel')f.fixture.api.cancelSettings();else if(end==='dispose')f.fixture.api.dispose();else f.fixture.advance(10_001);
    await importing;late();await new Promise(resolve=>setImmediate(resolve));
    if(end==='cancel'){f.fixture.api.openSettings();assert.equal(f.control('data-agent-skin-preset-list').children.length,0);}
    else if(end==='timeout')assert.equal(f.control('data-agent-skin-preset-list').children.length,0);
    assert.equal(f.storage.state.puts,0);assert.ok(f.fixture.images.at(-1).released);f.fixture.api.dispose();
  });
}
test('preset file rejects undecodable artwork and full or oversized catalogs',async()=>{
  const bad=presetDraftFixture(makeIndexedDB(),{decodeForSource:value=>value==='data:image/png;base64,CCCC'?'error':undefined});
  await bad.fixture.api.load(bad.defaults);bad.fixture.api.openSettings();await importPreset(bad,jsonPresetFile(presetFile(localPreset('data:image/png;base64,CCCC'))));
  assert.equal(bad.control('data-agent-skin-preset-list').children.length,0);bad.fixture.api.dispose();
  const entries=Array.from({length:8},(_,i)=>({...localPreset(),id:String(i)}));
  const full=presetDraftFixture(makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:1,entries}}));
  await full.fixture.api.load(full.defaults);full.fixture.api.openSettings();let reads=0;
  await importPreset(full,{size:1,arrayBuffer(){reads++;}});assert.equal(reads,0);assert.equal(full.control('data-agent-skin-preset-import').disabled,true);full.fixture.api.dispose();
  const huge=localPreset('data:image/png;base64,'+'A'.repeat(11*1024*1024));
  const f=presetDraftFixture(makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:1,entries:[huge]}}));
  await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();await importPreset(f,jsonPresetFile(presetFile(huge)));
  assert.equal(f.control('data-agent-skin-preset-list').children.length,1);assert.equal(f.storage.state.puts,0);f.fixture.api.dispose();
});

test('preset export cleans anchor and URL when download fails',async()=>{
  const f=presetDraftFixture(makeIndexedDB(undefined,{libraryRecord:{schemaVersion:1,revision:1,entries:[localPreset()]}}),{downloadError:true});
  await f.fixture.api.load(f.defaults);f.fixture.api.openSettings();f.control('data-agent-skin-preset-export').listeners.get('click')[0]();
  assert.equal(f.fixture.created.length,1);assert.deepEqual(f.fixture.revoked,[...f.fixture.created]);
  assert.equal(f.fixture.elements.find(el=>el.tagName==='A').removed,true);assert.equal(f.storage.state.puts,0);f.fixture.api.dispose();
});

test('catalog file remains independent at maximum active theme revision', async()=>{
  const f=presetDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
  await f.fixture.api.save(loaded.settings,{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'follow'}});
  f.storage.state.themeRecord.revision=Number.MAX_SAFE_INTEGER;await f.fixture.api.load(f.defaults);
  const before=structuredClone([f.storage.state.record,f.storage.state.themeRecord]);let applied=0;
  f.fixture.api.openSettings({onApply(){applied++;return {applied:true};}});await importPreset(f,jsonPresetFile());await f.click('保存');
  assert.equal(f.storage.state.libraryRecord?.entries.length,1,'independent catalog Save must not require a new theme revision');
  assert.deepEqual([f.storage.state.record,f.storage.state.themeRecord],before);assert.equal(applied,0);
  await assert.rejects(f.fixture.api.save({...before[0],wallpaperStrength:41},{activeThemeId:'azhou-q-v3',surfaceTransparency:{mode:'follow'}}),error=>error.reason==='settings-invalid');f.fixture.api.dispose();
});
for(const from of ['load','save']) {
  test('public catalog save honors edits to '+from+' returned settings',async()=>{
    const f=presetDraftFixture();const loaded=await f.fixture.api.load(f.defaults);
    const returned=from==='load'?loaded.settings:await f.fixture.api.save(loaded.settings);
    returned.introTitle='Edited returned';returned.contours[0][0][0]=2;
    await f.fixture.api.save(returned,undefined,{schemaVersion:1,revision:0,entries:[localPreset()]});
    assert.equal(f.storage.state.record?.introTitle,'Edited returned');assert.equal(f.storage.state.record.contours[0][0][0],2);f.fixture.api.dispose();
  });
}

for(const pending of ['file-read','image-decode']) {
  test('embedded preset '+pending+' cancellation leaves status clear without hiding errors',async()=>{
    const f=presetDraftFixture(makeIndexedDB(),{decodeForSource:value=>value==='data:image/png;base64,CCCC'?'pending':undefined});
    await f.fixture.api.load(f.defaults);f.fixture.api.openSettings({}, {presentation:'embedded'});let completeRead;
    const file=pending==='file-read'?{size:1,arrayBuffer(){return new Promise(resolve=>completeRead=resolve);}}:jsonPresetFile(presetFile(localPreset('data:image/png;base64,CCCC')));
    const importing=importPreset(f,file);await new Promise(resolve=>setImmediate(resolve));
    const lateDecode=pending==='image-decode'?f.fixture.images.at(-1).onload:null;
    const cancel=f.fixture.elements.find(el=>el.tagName==='BUTTON'&&el.textContent==='取消');
    assert.equal(cancel.disabled,false);await f.click('取消');await importing;
    const status=f.control('data-agent-skin-settings-status');
    assert.equal(status.textContent,'','embedded Cancel must not report an import failure');assert.equal(status.getAttribute('role'),'status');
    if(completeRead)completeRead(await jsonPresetFile().arrayBuffer());else lateDecode();
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(status.textContent,'');assert.equal(f.control('data-agent-skin-preset-list').children.length,0);assert.equal(f.storage.state.puts,0);
    await importPreset(f,jsonPresetFile({...presetFile(),extra:true}));
    assert.equal(status.getAttribute('role'),'alert');assert.match(status.textContent,/无法导入或导出 Azhou 预设文件/);f.fixture.api.dispose();
  });
}

test('Appearance has no external project transfer and keeps Azhou asset inputs', async () => {
  const f = presetDraftFixture();
  await f.fixture.api.load(f.defaults);
  assert.equal(f.fixture.api.openSettings(), true);
  for (const attribute of ['data-agent-skin-dream-import', 'data-agent-skin-dream-list', 'data-agent-skin-dream-apply']) {
    assert.equal(Boolean(f.control(attribute)), false, attribute);
  }
  for (const method of ['importDreamCapsule', 'loadDreamDirectory', 'applyDreamTheme']) {
    assert.equal(f.fixture.api[method], undefined, method);
  }
  assert.ok(f.control('data-agent-skin-preset-import'), 'ordinary Azhou preset input remains');
  assert.ok(f.fixture.elements.some(element => element.getAttribute('data-agent-skin-image-input') === 'artwork'));
  f.fixture.api.dispose();
});

test('a prior Dream selection resumes saved Azhou settings without reading or writing source capsules', async () => {
  const initial = presetDraftFixture();
  const record = {...initial.defaults, schemaVersion:1, introTitle:'Saved text', wallpaperStrength:19};
  initial.fixture.api.dispose();
  const imagesBinding = createHash('sha256').update(JSON.stringify(record)).digest('hex');
  const theme = {schemaVersion:2, revision:4, imagesBinding,
    selection:{kind:'imported', capsuleSha256:'a'.repeat(64)}, previousThemeId:'azhou-q-v3',
    preferencesByTheme:{'azhou-q-v3':{mode:'override',value:27}}, commitId:'b'.repeat(32)};
  const untouched = {schemaVersion:99, opaque:'foreign source bytes'};
  const storage = makeIndexedDB(record,{themeRecord:theme,dreamRecord:untouched});
  let sourceTouches = 0;
  Object.defineProperty(storage.state, 'dreamRecord', {
    get(){sourceTouches++; return untouched;},
    set(){sourceTouches++;},
  });
  const f = presetDraftFixture(storage);
  const snapshot = await f.fixture.api.loadSnapshot(f.defaults);
  assert.equal(snapshot.status,'valid');
  assert.equal(snapshot.settings.introTitle,'Saved text');
  assert.equal(snapshot.settings.artwork,record.artwork);
  assert.equal(snapshot.settings.wallpaperStrength,19);
  assert.equal(snapshot.themeState.activeThemeId,'azhou-q-v3');
  assert.deepEqual({...snapshot.themeState.preferencesByTheme['azhou-q-v3']},{mode:'override',value:27});
  assert.deepEqual(storage.state.themeRecord,theme);
  assert.equal(sourceTouches,0);
  assert.equal(storage.state.puts,0);
  assert.equal(f.fixture.api.openSettings(),true);
  assert.equal(f.control('data-agent-skin-theme-choice').value,'azhou-q-v3');
  const title=f.fixture.elements.find(element=>element.maxLength===16);
  title.value='Azhou save';title.listeners.get('input')[0]();
  await f.click('保存');
  assert.equal(storage.state.record.introTitle,'Azhou save');
  assert.equal(storage.state.record.artwork,record.artwork);
  assert.equal(storage.state.themeRecord.schemaVersion,1);
  assert.equal(storage.state.themeRecord.activeThemeId,'azhou-q-v3');
  assert.equal(sourceTouches,0,'Normal Appearance save never touches the retired catalog');
  f.fixture.api.dispose();
});

for (const savedImages of [undefined, 'digest-mismatch']) test(`retired selection without a verified prior Azhou binding falls back (${savedImages})`, async () => {
  const initial = presetDraftFixture();
  const record = savedImages ? {...initial.defaults,schemaVersion:1,introTitle:'Other saved edit'} : undefined;
  initial.fixture.api.dispose();
  const theme = {schemaVersion:2,revision:4,imagesBinding:'a'.repeat(64),
    selection:{kind:'imported',capsuleSha256:'b'.repeat(64)},previousThemeId:'azhou-q-v3',
    preferencesByTheme:{'azhou-q-v3':{mode:'override',value:27}},commitId:'c'.repeat(32)};
  const storage = makeIndexedDB(record,{themeRecord:theme,dreamRecord:{opaque:true}});
  const f = presetDraftFixture(storage);
  const snapshot = await f.fixture.api.loadSnapshot(f.defaults);
  assert.equal(snapshot.status,savedImages ? 'valid' : 'missing');
  assert.equal(snapshot.settings.artwork,f.defaults.artwork);
  if (record) assert.equal(snapshot.settings.introTitle,record.introTitle);
  assert.equal(snapshot.themeState,null);
  assert.deepEqual(storage.state.themeRecord,theme);
  assert.equal(storage.state.puts,0);
  f.fixture.api.dispose();
});

test('unknown active theme schema is read-only and cannot silently become legacy on Save',async()=>{
  const future={schemaVersion:99,selection:{kind:'future',opaque:'preserve'}};
  const storage=makeIndexedDB(undefined,{themeRecord:future});const f=presetDraftFixture(storage);
  const loaded=await f.fixture.api.load(f.defaults);const snapshot=await f.fixture.api.loadSnapshot(f.defaults);
  assert.equal(snapshot.status,'failure');assert.equal(snapshot.reason,'settings-blocked');
  await assert.rejects(f.fixture.api.save({...loaded.settings,introTitle:'Do not erase future'}),{reason:'settings-blocked'});
  assert.equal(storage.state.puts,0);assert.deepEqual(storage.state.themeRecord,future);f.fixture.api.dispose();
});
test('unknown stored image schema is read-only rather than rewritten from fallback defaults',async()=>{
  const future={schemaVersion:99,assets:{future:'preserve'}};const storage=makeIndexedDB(future);const f=presetDraftFixture(storage);
  const loaded=await f.fixture.api.load(f.defaults);
  await assert.rejects(f.fixture.api.save(loaded.settings),{reason:'settings-blocked'});
  assert.equal(storage.state.puts,0);assert.deepEqual(storage.state.record,future);f.fixture.api.dispose();
});

for (const locale of ['zh-CN', 'en']) test(`Appearance keeps optional instructions collapsed without changing drafts (${locale})`, async () => {
  const localization = createLocalization({locale});
  const storage = makeIndexedDB();
  const fixture = makeFixture({localization,indexedDB:storage.indexedDB,imageDimensions:[[512,512],[1536,1024]]});
  await fixture.api.load({avatar:'data:image/png;base64,AAAA',artwork:'data:image/png;base64,BBBB',contours:[[[0,0],[1,1]]],wallpaperStrength:42});
  let applies = 0;
  fixture.api.openSettings({onApply(){applies++;}});
  for (const name of ['presets', 'theme-help']) {
    const disclosure = fixture.elements.find(el => el.getAttribute('data-agent-skin-disclosure') === name);
    assert.ok(disclosure, `${name} offers progressive disclosure`);
    assert.equal(disclosure.tagName, 'DETAILS');
    assert.equal(Boolean(disclosure.open), false, 'optional content starts collapsed');
    assert.equal(disclosure.children[0].tagName, 'SUMMARY', 'native keyboard-accessible trigger');
    assert.ok(disclosure.children[0].textContent);
    disclosure.open = true;
    disclosure.open = false;
  }
  assert.equal(storage.state.puts, 0);
  assert.equal(applies, 0);
  fixture.api.dispose();
});
