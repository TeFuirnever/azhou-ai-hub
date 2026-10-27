/**
 * Normalize one local PNG, JPEG or WebP for the current child settings page.
 * Pass its document, Image, URL, timers and performance object explicitly.
 * Errors expose a stable reason (asset-invalid, operation-timeout, operation-busy
 * or operation-cancelled) and optional non-sensitive causeCode. cancelImport
 * returns true only when it cancels an active import. Results over 16 MP carry
 * warning=large-image; artwork results also contain bounded [[x, y], ...] paths.
 */
function createImageSettings(environment) {
  const document = environment && environment.document;
  const ImageConstructor = environment && environment.Image;
  const URLObject = environment && environment.URL;
  const setTimer = environment && environment.setTimeout;
  const clearTimer = environment && environment.clearTimeout;
  const performance = environment && environment.performance;
  const MAX_INPUT_BYTES = 31_457_280;
  const MAX_SOURCE_PIXELS = 48_000_000;
  const LARGE_SOURCE_PIXELS = 16_000_000;
  const PNG_PREFIX = 'data:image/png;base64,';
  let generation = 0;
  let active = null;

  function makeError(reason, causeCode) {
    const error = new Error(reason);
    error.reason = reason;
    if (causeCode) error.causeCode = causeCode;
    return error;
  }

  function validEnvironment() {
    return !!(
      document && typeof document.createElement === 'function'
      && typeof ImageConstructor === 'function'
      && URLObject && typeof URLObject.createObjectURL === 'function'
      && typeof URLObject.revokeObjectURL === 'function'
      && typeof setTimer === 'function' && typeof clearTimer === 'function'
      && performance && typeof performance.now === 'function'
    );
  }

  function clearTaskTimer(task, field) {
    if (task[field] !== null) {
      try { clearTimer.call(environment, task[field]); } catch {}
      task[field] = null;
    }
  }

  function release(task) {
    clearTaskTimer(task, 'decodeTimer');
    clearTaskTimer(task, 'prepareTimer');
    if (task.image) {
      task.image.onload = null;
      task.image.onerror = null;
      try {
        if (typeof task.image.removeAttribute === 'function') task.image.removeAttribute('src');
        else task.image.src = 'data:,';
      } catch {}
      task.image = null;
    }
    if (task.objectURL) {
      try { URLObject.revokeObjectURL.call(URLObject, task.objectURL); } catch {}
      task.objectURL = null;
    }
    for (const canvas of task.canvases) {
      try { canvas.width = 0; canvas.height = 0; } catch {}
    }
    task.canvases.length = 0;
  }

  function finish(task, succeeded, value) {
    if (task.settled) return;
    task.settled = true;
    if (active === task) active = null;
    release(task);
    const abortPending = task.abortPending;
    task.abortPending = null;
    if (succeeded) task.resolve(value);
    else {
      task.reject(value);
      if (abortPending) abortPending(value);
    }
  }

  function isCurrent(task) {
    return active === task && task.generation === generation && !task.settled;
  }

  function assertCurrent(task) {
    if (!isCurrent(task)) throw makeError('operation-cancelled');
    let elapsed;
    try { elapsed = performance.now.call(performance) - task.startedAt; }
    catch { elapsed = task.elapsedFallback; }
    if (elapsed >= 10_000) throw makeError('operation-timeout', 'prepare-timeout');
  }

  function invalidData(causeCode) {
    return makeError('asset-invalid', causeCode);
  }

  function detectType(bytes) {
    if (bytes.length >= 8
      && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47
      && bytes[4] === 0x0d && bytes[5] === 0x0a && bytes[6] === 0x1a && bytes[7] === 0x0a) {
      return 'image/png';
    }
    if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
      return 'image/jpeg';
    }
    if (bytes.length >= 12
      && bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46
      && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50) {
      return 'image/webp';
    }
    return null;
  }

  async function readSignature(file, task) {
    let buffer;
    try {
      const prefix = file.slice(0, 12);
      if (!prefix || typeof prefix.arrayBuffer !== 'function') throw new Error('slice unavailable');
      buffer = await prefix.arrayBuffer();
    } catch {
      assertCurrent(task);
      throw invalidData('unsupported-type');
    }
    assertCurrent(task);
    if (!buffer || Object.prototype.toString.call(buffer) !== '[object ArrayBuffer]') {
      throw invalidData('unsupported-type');
    }
    const actualType = detectType(new Uint8Array(buffer));
    if (!actualType) throw invalidData('unsupported-type');
    const declaredType = typeof file.type === 'string' ? file.type.toLowerCase() : '';
    if (declaredType && !['image/png', 'image/jpeg', 'image/webp'].includes(declaredType)) {
      throw invalidData('unsupported-type');
    }
    if (declaredType && declaredType !== actualType) throw invalidData('mime-mismatch');
  }

  function decode(task, file) {
    return new Promise((resolve, reject) => {
      let image;
      try {
        image = new ImageConstructor();
        task.image = image;
        task.abortPending = reject;
        image.onload = () => {
          clearTaskTimer(task, 'decodeTimer');
          task.abortPending = null;
          if (isCurrent(task)) resolve(image);
          else reject(makeError('operation-cancelled'));
        };
        image.onerror = () => {
          clearTaskTimer(task, 'decodeTimer');
          task.abortPending = null;
          reject(invalidData('decode-failed'));
        };
        task.objectURL = URLObject.createObjectURL.call(URLObject, file);
        task.decodeTimer = setTimer.call(environment, () => {
          const error = makeError('operation-timeout', 'decode-timeout');
          reject(error);
          finish(task, false, error);
        }, 4_000);
        image.src = task.objectURL;
      } catch {
        task.abortPending = null;
        reject(invalidData('decode-failed'));
      }
    });
  }

  function canvasFor(task, width, height) {
    let canvas;
    try {
      canvas = document.createElement('canvas');
      task.canvases.push(canvas);
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d', { willReadFrequently: width === 768 });
      if (!context) throw new Error('2d context unavailable');
      return { canvas, context };
    } catch {
      throw invalidData('canvas-unavailable');
    }
  }

  function normalizeAvatar(task, image) {
    const width = 512;
    const height = 512;
    const output = canvasFor(task, width, height);
    const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
    const drawnWidth = image.naturalWidth * scale;
    const drawnHeight = image.naturalHeight * scale;
    const x = (width - drawnWidth) / 2;
    const y = (height - drawnHeight) / 2;
    output.context.fillStyle = '#101114';
    output.context.fillRect(0, 0, width, height);
    output.context.imageSmoothingEnabled = true;
    try { output.context.imageSmoothingQuality = 'high'; } catch {}
    output.context.drawImage(image, x, y, drawnWidth, drawnHeight);
    return encodeOutput(output.canvas, width, height, 2 * 1024 * 1024);
  }

  function encodeOutput(canvas, width, height, maxBytes) {
    let dataURL;
    try { dataURL = canvas.toDataURL('image/png'); }
    catch { throw invalidData('png-encode-failed'); }
    if (typeof dataURL !== 'string' || !dataURL.startsWith(PNG_PREFIX)) {
      throw invalidData('png-encode-failed');
    }
    for (let index = 0; index < dataURL.length; index++) {
      if (dataURL.charCodeAt(index) > 0x7f) throw invalidData('png-encode-failed');
    }
    const bytes = dataURL.length;
    if (bytes > maxBytes) throw invalidData('output-too-large');
    return { dataURL, width, height, bytes };
  }

  async function yieldBetweenRows(task) {
    await new Promise(resolve => setTimer.call(environment, resolve, 0));
    assertCurrent(task);
  }

  async function extractContours(task, imageData) {
    const width = 768;
    const height = 512;
    const pixelCount = width * height;
    const rgba = imageData && imageData.data;
    if (!rgba || rgba.length !== pixelCount * 4) throw invalidData('pixel-data-invalid');

    const gray = new Uint8Array(pixelCount);
    for (let y = 0; y < height; y++) {
      const row = y * width;
      for (let x = 0; x < width; x++) {
        const pixel = (row + x) * 4;
        gray[row + x] = Math.round(
          rgba[pixel] * 0.299 + rgba[pixel + 1] * 0.587 + rgba[pixel + 2] * 0.114,
        );
      }
      if (y > 0 && y % 16 === 0) await yieldBetweenRows(task);
    }

    const magnitude = new Float32Array(pixelCount);
    const direction = new Uint8Array(pixelCount);
    for (let y = 1; y < height - 1; y++) {
      const row = y * width;
      for (let x = 1; x < width - 1; x++) {
        const index = row + x;
        const top = index - width;
        const bottom = index + width;
        const gx = -gray[top - 1] + gray[top + 1]
          - 2 * gray[index - 1] + 2 * gray[index + 1]
          - gray[bottom - 1] + gray[bottom + 1];
        const gy = -gray[top - 1] - 2 * gray[top] - gray[top + 1]
          + gray[bottom - 1] + 2 * gray[bottom] + gray[bottom + 1];
        const strength = Math.sqrt(gx * gx + gy * gy);
        magnitude[index] = strength;
        let angle = Math.atan2(gy, gx) * 180 / Math.PI;
        if (angle < 0) angle += 180;
        direction[index] = angle < 22.5 || angle >= 157.5 ? 0
          : angle < 67.5 ? 1
            : angle < 112.5 ? 2 : 3;
      }
      if (y % 16 === 0) await yieldBetweenRows(task);
    }

    const edges = new Uint8Array(pixelCount);
    for (let y = 1; y < height - 1; y++) {
      const row = y * width;
      for (let x = 1; x < width - 1; x++) {
        const index = row + x;
        const strength = magnitude[index];
        if (strength <= 32) continue;
        let first;
        let second;
        switch (direction[index]) {
          case 0: first = index - 1; second = index + 1; break;
          case 1: first = index - width - 1; second = index + width + 1; break;
          case 2: first = index - width; second = index + width; break;
          default: first = index - width + 1; second = index + width - 1;
        }
        if (strength >= magnitude[first] && strength >= magnitude[second]) edges[index] = 1;
      }
      if (y % 16 === 0) await yieldBetweenRows(task);
    }

    const visited = new Uint8Array(pixelCount);
    const neighborSteps = [
      [-1, -1], [0, -1], [1, -1], [-1, 0],
      [1, 0], [-1, 1], [0, 1], [1, 1],
    ];
    function adjacent(index, visit) {
      const x = index % width;
      const y = Math.floor(index / width);
      for (const [deltaX, deltaY] of neighborSteps) {
        const nextX = x + deltaX;
        const nextY = y + deltaY;
        if (nextX < 0 || nextX >= width || nextY < 0 || nextY >= height) continue;
        const next = nextY * width + nextX;
        if (edges[next]) visit(next);
      }
    }
    function edgeDegree(index) {
      let degree = 0;
      adjacent(index, () => { degree++; });
      return degree;
    }
    function nextEdge(index, previous) {
      let best = -1;
      let bestDot = -Infinity;
      let bestStrength = -Infinity;
      const x = index % width;
      const y = Math.floor(index / width);
      const previousX = previous < 0 ? x : previous % width;
      const previousY = previous < 0 ? y : Math.floor(previous / width);
      const incomingX = previous < 0 ? 0 : x - previousX;
      const incomingY = previous < 0 ? 0 : y - previousY;
      const incomingLength = Math.hypot(incomingX, incomingY) || 1;
      adjacent(index, candidate => {
        if (visited[candidate]) return;
        const candidateX = candidate % width;
        const candidateY = Math.floor(candidate / width);
        const outgoingX = candidateX - x;
        const outgoingY = candidateY - y;
        const outgoingLength = Math.hypot(outgoingX, outgoingY) || 1;
        const dot = previous < 0
          ? 0 : (incomingX * outgoingX + incomingY * outgoingY) / (incomingLength * outgoingLength);
        const candidateStrength = magnitude[candidate];
        if (dot > bestDot || (dot === bestDot && candidateStrength > bestStrength)) {
          best = candidate;
          bestDot = dot;
          bestStrength = candidateStrength;
        }
      });
      return best;
    }

    const paths = [];
    let walkedSinceYield = 0;
    async function trace(start) {
      const raw = [];
      let previous = -1;
      let current = start;
      while (current >= 0 && !visited[current]) {
        visited[current] = 1;
        raw.push(current);
        const next = nextEdge(current, previous);
        if (next < 0) {
          let closesLoop = false;
          if (raw.length > 2) adjacent(current, candidate => { if (candidate === start) closesLoop = true; });
          if (closesLoop) raw.push(start);
          break;
        }
        previous = current;
        current = next;
        walkedSinceYield++;
        if (walkedSinceYield >= 2048) {
          walkedSinceYield = 0;
          await yieldBetweenRows(task);
        }
      }
      if (raw.length >= 8) paths.push(raw);
    }

    for (let y = 1; y < height - 1; y++) {
      for (let x = 1; x < width - 1; x++) {
        const index = y * width + x;
        if (edges[index] && !visited[index] && edgeDegree(index) === 1) await trace(index);
      }
      if (y % 16 === 0) await yieldBetweenRows(task);
    }
    for (let y = 1; y < height - 1; y++) {
      for (let x = 1; x < width - 1; x++) {
        const index = y * width + x;
        if (edges[index] && !visited[index]) await trace(index);
      }
      if (y % 16 === 0) await yieldBetweenRows(task);
    }

    if (!paths.length) throw invalidData('contours-empty');
    paths.sort((left, right) => right.length - left.length);
    const output = [];
    let totalPoints = 0;
    for (let pathIndex = 0; pathIndex < paths.length && pathIndex < 1200; pathIndex++) {
      const raw = paths[pathIndex];
      const path = [];
      for (let pointIndex = 0; pointIndex < raw.length; pointIndex += 2) {
        const pixel = raw[pointIndex];
        path.push([(pixel % width) * 2, Math.floor(pixel / width) * 2]);
      }
      if (path.length < 2) continue;
      totalPoints += path.length;
      if (totalPoints > 300_000) throw invalidData('contours-too-many-points');
      output.push(path);
    }
    if (!output.length) throw invalidData('contours-empty');
    return output;
  }

  async function normalizeArtwork(task, image) {
    const width = 1536;
    const height = 1024;
    const output = canvasFor(task, width, height);
    const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
    const drawnWidth = image.naturalWidth * scale;
    const drawnHeight = image.naturalHeight * scale;
    output.context.fillStyle = '#101114';
    output.context.fillRect(0, 0, width, height);
    output.context.imageSmoothingEnabled = true;
    try { output.context.imageSmoothingQuality = 'high'; } catch {}
    output.context.drawImage(
      image,
      (width - drawnWidth) / 2,
      (height - drawnHeight) / 2,
      drawnWidth,
      drawnHeight,
    );

    const analysis = canvasFor(task, 768, 512);
    analysis.context.imageSmoothingEnabled = true;
    try { analysis.context.imageSmoothingQuality = 'high'; } catch {}
    analysis.context.drawImage(output.canvas, 0, 0, 768, 512);
    let imageData;
    try { imageData = analysis.context.getImageData(0, 0, 768, 512); }
    catch { throw invalidData('pixel-data-unavailable'); }
    const contours = await extractContours(task, imageData);
    const result = encodeOutput(output.canvas, width, height, 12 * 1024 * 1024);
    result.contours = contours;
    return result;
  }

  async function importImage(file, role) {
    if (!validEnvironment()) return Promise.reject(invalidData('environment-unavailable'));
    if (active) return Promise.reject(makeError('operation-busy'));
    if (role !== 'avatar' && role !== 'artwork') return Promise.reject(invalidData('invalid-role'));
    if (!file || !Number.isSafeInteger(file.size) || file.size <= 0) {
      return Promise.reject(invalidData('file-empty'));
    }
    if (file.size > MAX_INPUT_BYTES) return Promise.reject(invalidData('file-too-large'));

    const task = {
      generation: ++generation,
      startedAt: 0,
      elapsedFallback: 0,
      settled: false,
      resolve: null,
      reject: null,
      abortPending: null,
      decodeTimer: null,
      prepareTimer: null,
      objectURL: null,
      image: null,
      canvases: [],
    };
    try { task.startedAt = performance.now.call(performance); }
    catch { task.startedAt = 0; }
    active = task;

    const promise = new Promise((resolve, reject) => {
      task.resolve = resolve;
      task.reject = reject;
    });
    task.prepareTimer = setTimer.call(environment, () => {
      const error = makeError('operation-timeout', 'prepare-timeout');
      finish(task, false, error);
    }, 10_000);

    (async () => {
      try {
        await readSignature(file, task);
        const image = await decode(task, file);
        assertCurrent(task);
        const sourceWidth = Number(image.naturalWidth);
        const sourceHeight = Number(image.naturalHeight);
        if (!Number.isSafeInteger(sourceWidth) || !Number.isSafeInteger(sourceHeight)
          || sourceWidth <= 0 || sourceHeight <= 0) throw invalidData('invalid-dimensions');
        const sourcePixels = sourceWidth * sourceHeight;
        if (!Number.isSafeInteger(sourcePixels) || sourcePixels > MAX_SOURCE_PIXELS) {
          throw invalidData('image-too-large');
        }
        const result = role === 'avatar'
          ? normalizeAvatar(task, image)
          : await normalizeArtwork(task, image);
        if (sourcePixels > LARGE_SOURCE_PIXELS) result.warning = 'large-image';
        assertCurrent(task);
        finish(task, true, result);
      } catch (error) {
        if (task.settled) return;
        const reason = error && typeof error.reason === 'string'
          ? error : invalidData('image-processing-failed');
        finish(task, false, reason);
      }
    })();

    return promise;
  }

  function cancelImport() {
    if (!active) return false;
    generation += 1;
    finish(active, false, makeError('operation-cancelled'));
    return true;
  }

  return { importImage, cancelImport };
}
