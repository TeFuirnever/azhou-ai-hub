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
  const localization = environment && environment.localization;
  const themeConfig = environment?.themeConfig;
  const appearanceAvatar = environment && typeof environment.appearanceAvatar === 'string'
    && environment.appearanceAvatar.length <= 2 * 1024 * 1024
    && /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(environment.appearanceAvatar)
    ? environment.appearanceAvatar : '';
  const ImageConstructor = environment && environment.Image;
  const URLObject = environment && environment.URL;
  const indexedDB = environment && environment.indexedDB;
  const setTimer = environment && environment.setTimeout;
  const clearTimer = environment && environment.clearTimeout;
  const performance = environment && environment.performance;
  const MAX_INPUT_BYTES = 31_457_280;
  const MAX_SOURCE_PIXELS = 48_000_000;
  const LARGE_SOURCE_PIXELS = 16_000_000;
  const PNG_PREFIX = 'data:image/png;base64,';
  const DATABASE_NAME = 'azhou-codex-startup';
  const DATABASE_VERSION = 1;
  const STORE_NAME = 'settings';
  const SETTINGS_KEY = 'images';
  const MAX_RECORD_BYTES = 20 * 1024 * 1024;
  const TEXT_LIMITS = Object.freeze({ introTitle: 16, introCaption: 48, artworkSubtitle: 60 });
  const FALLBACK_MESSAGES = Object.freeze({
    'animation.title.default': '阿舟 AI 实验室',
    'animation.caption.default': 'AZHOU / AI LAB',
    'animation.subtitle.default': '和阿舟一起，把想法做出来。',
    'settings.title': '阿舟 · 主题与外观',
    'settings.close': '取消并关闭设置',
    'settings.avatar.label': '启动头像',
    'settings.artwork.label': '背景图片',
    'settings.introTitle.label': '启动标题（最多 {limit} 个字符）',
    'settings.introCaption.label': '标题说明（最多 {limit} 个字符）',
    'settings.artworkSubtitle.label': '背景字幕（最多 {limit} 个字符）',
    'settings.wallpaperStrength.label': '背景效果强度（{min}–{max}）',
    'settings.wallpaperStrength.aria': '背景效果强度，{min} 到 {max}',
    'settings.button.restore': '恢复默认',
    'settings.button.cancel': '取消',
    'settings.button.save': '保存并重播',
    'settings.button.choosePortrait': '选择启动头像',
    'settings.button.chooseBackground': '选择背景图片',
    'settings.status.importing': '正在处理图片…',
    'settings.status.saving': '正在校验候选并保存…',
    'settings.status.imageLarge': '图片已准备；原图超过 16 MP，处理可能较慢。',
    'settings.status.imageReady': '图片已准备，可以保存。',
    'settings.status.defaultsRestored': '草稿已恢复为默认设置；已保存值尚未更改。',
    'settings.error.conflict': '其他页面已更新设置。请取消后重新打开，再保存草稿。',
    'settings.error.quota': '存储空间不足。请更换图片后重试。',
    'settings.error.blocked': '设置数据库被其他页面阻塞。稍后可以重试。',
    'settings.error.timeout': '操作超时，面板已恢复，可以取消或重试。',
    'settings.error.invalid': '候选设置无法验证，已保存内容保持不变。',
    'settings.error.save': '保存失败，已保存内容保持不变。',
    'settings.load.invalid': '保存记录无法识别；当前使用默认设置，原记录保留。',
    'settings.load.timeout': '读取设置超时；当前使用默认值，已保存记录未改动。可以重试。',
    'settings.load.unavailable': '暂时无法读取保存设置；当前使用默认设置，原记录未删除。',
  });
  let generation = 0;
  let active = null;
  let database = null;
  let openingDatabase = null;
  let disposed = false;
  let currentSettings = null;
  let currentBaseline;
  let defaultRecord = null;
  let defaultTextFallbacks = Object.create(null);
  let loadReason = '';
  let dialog = null;
  let panelControls = null;
  let draft = null;
  let panelOpen = false;
  let panelGeneration = 0;
  let panelCallbacks = null;
  let panelStatus = null;
  let localizationUnsubscribe = null;

  function translate(key, params = {}) {
    try {
      const translated = localization && typeof localization.t === 'function'
        ? localization.t(key, params) : null;
      if (typeof translated === 'string' && translated !== key) return translated;
    } catch {}
    const template = FALLBACK_MESSAGES[key] || String(key);
    return template.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g, (placeholder, name) =>
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder);
  }

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
    for (const timer of task.validationTimers || []) {
      try { clearTimer.call(environment, timer); } catch {}
    }
    task.validationTimers?.clear();
    for (const image of task.validationImages || []) {
      image.onload = null;
      image.onerror = null;
      try {
        if (typeof image.removeAttribute === 'function') image.removeAttribute('src');
        else image.src = 'data:,';
      } catch {}
    }
    task.validationImages?.clear();
    for (const canvas of task.canvases) {
      try { canvas.width = 0; canvas.height = 0; } catch {}
    }
    task.canvases.length = 0;
  }

  function finish(task, succeeded, value) {
    if (task.settled) return;
    task.settled = true;
    if (active === task) active = null;
    if (!succeeded && task.transaction && !task.transactionFinished) {
      const transaction = task.transaction;
      task.transaction = null;
      try { transaction.abort(); } catch {}
    }
    release(task);
    const abortPending = task.abortPending;
    task.abortPending = null;
    if (succeeded) task.resolve(value);
    else {
      task.reject(value);
      if (abortPending) abortPending(value);
    }
    updatePanelBusy();
  }

  function isCurrent(task) {
    return active === task && task.generation === generation && !task.settled;
  }

  function beginOperation(kind, timeout, onTimeout) {
    const task = {
      kind,
      generation: ++generation,
      startedAt: 0,
      elapsedFallback: 0,
      settled: false,
      resolve: null,
      reject: null,
      abortPending: null,
      decodeTimer: null,
      prepareTimer: null,
      validationTimers: new Set(),
      validationImages: new Set(),
      objectURL: null,
      image: null,
      canvases: [],
      transaction: null,
      transactionFinished: false,
      failure: null,
      baseline: undefined,
      baselineKnown: false,
    };
    try { task.startedAt = performance.now.call(performance); } catch {}
    active = task;
    const promise = new Promise((resolve, reject) => {
      task.resolve = resolve;
      task.reject = reject;
    });
    if (Number.isFinite(timeout)) {
      task.prepareTimer = setTimer.call(environment, () => {
        const error = makeError('operation-timeout', 'prepare-timeout');
        if (typeof onTimeout === 'function') onTimeout(task, error);
        else finish(task, false, error);
      }, timeout);
    }
    return { task, promise };
  }

  function decodeRecordImage(task, dataURL, width, height) {
    return new Promise((resolve, reject) => {
      if (!isCurrent(task)) { reject(makeError('operation-cancelled')); return; }
      let image;
      let timer = null;
      const clear = () => {
        if (timer !== null) {
          try { clearTimer.call(environment, timer); } catch {}
          task.validationTimers.delete(timer);
          timer = null;
        }
      };
      try {
        image = new ImageConstructor();
        task.validationImages.add(image);
        image.onload = () => {
          clear();
          if (!isCurrent(task)) { reject(makeError('operation-cancelled')); return; }
          if (image.naturalWidth !== width || image.naturalHeight !== height) {
            reject(invalidData('invalid-dimensions'));
          } else resolve(true);
        };
        image.onerror = () => { clear(); reject(invalidData('decode-failed')); };
        timer = setTimer.call(environment, () => {
          clear();
          reject(makeError('operation-timeout', 'decode-timeout'));
        }, 4_000);
        task.validationTimers.add(timer);
        image.src = dataURL;
      } catch {
        clear();
        reject(invalidData('decode-failed'));
      }
    });
  }

  async function validateRecordImages(task, record) {
    try {
      await Promise.all([
        decodeRecordImage(task, record.avatar, 512, 512),
        decodeRecordImage(task, record.artwork, 1536, 1024),
      ]);
    } catch (error) {
      if (error && (error.reason === 'operation-timeout' || error.reason === 'operation-cancelled')) throw error;
      throw invalidData(error?.causeCode || 'decode-failed');
    }
    if (!isCurrent(task)) throw makeError('operation-cancelled');
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

  function defaultSettings(defaults) {
    const source = defaults && typeof defaults === 'object' ? defaults : {};
    const dataURL = value => typeof value === 'string' ? value
      : value && typeof value.dataURL === 'string' ? value.dataURL : '';
    defaultTextFallbacks = {
      introTitle: typeof source.introTitle !== 'string',
      introCaption: typeof source.introCaption !== 'string',
      artworkSubtitle: typeof source.artworkSubtitle !== 'string',
    };
    return {
      schemaVersion: 1,
      avatar: dataURL(source.avatar),
      artwork: dataURL(source.artwork),
      contours: Array.isArray(source.contours) ? source.contours.map(path =>
        Array.isArray(path) ? path.map(point => Array.isArray(point) ? [...point] : point) : path) : [],
      introTitle: typeof source.introTitle === 'string' ? source.introTitle : translate('animation.title.default'),
      introCaption: typeof source.introCaption === 'string' ? source.introCaption : translate('animation.caption.default'),
      artworkSubtitle: typeof source.artworkSubtitle === 'string' ? source.artworkSubtitle : translate('animation.subtitle.default'),
      wallpaperStrength: Number.isInteger(source.wallpaperStrength) && source.wallpaperStrength >= 0
          && source.wallpaperStrength <= 75 ? source.wallpaperStrength : themeConfig?.wallpaper?.strength ?? 42,
    };
  }

  function storageError(reason, causeCode) {
    return makeError(reason || 'settings-unavailable', causeCode);
  }

  function openDatabase() {
    if (disposed) return Promise.reject(makeError('operation-cancelled'));
    if (database) return Promise.resolve(database);
    if (openingDatabase) return openingDatabase;
    if (!indexedDB || typeof indexedDB.open !== 'function') {
      return Promise.reject(storageError('settings-unavailable', 'indexeddb-unavailable'));
    }

    openingDatabase = new Promise((resolve, reject) => {
      let settled = false;
      let request;
      let timer = null;
      const clear = () => {
        if (timer !== null) {
          try { clearTimer.call(environment, timer); } catch {}
          timer = null;
        }
      };
      const finish = (succeeded, value) => {
        if (settled) return;
        settled = true;
        clear();
        openingDatabase = null;
        if (succeeded) resolve(value);
        else reject(value);
      };
      try {
        request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
        timer = setTimer.call(environment, () => finish(false,
          makeError('operation-timeout', 'database-open-timeout')), 5_000);
        request.onupgradeneeded = () => {
          const db = request.result;
          try {
            if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME);
          } catch {
            try { request.transaction?.abort?.(); } catch {}
          }
        };
        request.onblocked = () => finish(false, storageError('settings-blocked', 'database-blocked'));
        request.onerror = () => finish(false, storageError('settings-unavailable', 'database-open-failed'));
        request.onsuccess = () => {
          const db = request.result;
          if (settled || disposed) {
            try { db.close(); } catch {}
            if (!settled) finish(false, makeError('operation-cancelled'));
            return;
          }
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            try { db.close(); } catch {}
            finish(false, storageError('settings-unavailable', 'settings-store-missing'));
            return;
          }
          db.onversionchange = () => {
            try { db.close(); } catch {}
            if (database === db) database = null;
          };
          database = db;
          finish(true, db);
        };
      } catch {
        finish(false, storageError('settings-unavailable', 'database-open-failed'));
      }
    });
    return openingDatabase;
  }

  function readStoredRecord(db, task) {
    return new Promise((resolve, reject) => {
      let transaction;
      let request;
      let value;
      let sawResult = false;
      let settled = false;
      let timer = null;
      let failure = null;
      const clear = () => {
        if (timer !== null) {
          try { clearTimer.call(environment, timer); } catch {}
          timer = null;
        }
      };
      const finish = (succeeded, result) => {
        if (settled) return;
        settled = true;
        clear();
        if (succeeded) resolve(result);
        else reject(result);
      };
      try {
        transaction = db.transaction(STORE_NAME, 'readonly');
        if (task) task.transaction = transaction;
        timer = setTimer.call(environment, () => {
          failure = makeError('operation-timeout', 'database-read-timeout');
          try { transaction.abort(); } catch {}
          finish(false, failure);
        }, 5_000);
        request = transaction.objectStore(STORE_NAME).get(SETTINGS_KEY);
        request.onsuccess = () => { value = request.result; sawResult = true; };
        request.onerror = () => { failure = storageError('settings-unavailable', 'database-read-failed'); };
        transaction.oncomplete = () => {
          if (task && task.transaction === transaction) task.transaction = null;
          finish(sawResult, sawResult
            ? value : (failure || storageError('settings-unavailable', 'database-read-failed')));
        };
        transaction.onerror = () => { failure ||= storageError('settings-unavailable', 'database-read-failed'); };
        transaction.onabort = () => {
          if (task && task.transaction === transaction) task.transaction = null;
          finish(false, failure || storageError('settings-unavailable', 'database-read-aborted'));
        };
      } catch {
        finish(false, storageError('settings-unavailable', 'database-read-failed'));
      }
    });
  }

  function own(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  }

  function recordByteLength(value) {
    const serialized = JSON.stringify(value);
    if (typeof serialized !== 'string') throw invalidData('record-unserializable');
    let bytes = 0;
    for (let index = 0; index < serialized.length; index++) {
      const code = serialized.charCodeAt(index);
      if (code < 0x80) bytes += 1;
      else if (code < 0x800) bytes += 2;
      else if (code >= 0xd800 && code <= 0xdbff && index + 1 < serialized.length
        && serialized.charCodeAt(index + 1) >= 0xdc00 && serialized.charCodeAt(index + 1) <= 0xdfff) {
        bytes += 4;
        index++;
      } else bytes += 3;
      if (bytes > MAX_RECORD_BYTES) throw invalidData('record-too-large');
    }
    return bytes;
  }

  function validContours(contours) {
    if (!Array.isArray(contours) || contours.length > 1200) return false;
    let points = 0;
    for (const path of contours) {
      if (!Array.isArray(path) || path.length < 2) return false;
      points += path.length;
      if (points > 300_000) return false;
      for (const point of path) {
        if (!Array.isArray(point) || point.length !== 2
          || !Number.isFinite(point[0]) || point[0] < 0 || point[0] > 1536
          || !Number.isFinite(point[1]) || point[1] < 0 || point[1] > 1024) return false;
      }
    }
    return contours.length > 0;
  }

  function normalizeStoredRecord(value, defaults) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || value.schemaVersion !== 1) return null;
    const knownKeys = new Set(['schemaVersion', 'avatar', 'artwork', 'contours', ...Object.keys(TEXT_LIMITS), 'wallpaperStrength']);
    if (Object.keys(value).some(key => !knownKeys.has(key))) return null;
    const record = { ...defaults };
    for (const key of ['avatar', 'artwork']) {
      if (own(value, key)) {
        if (typeof value[key] !== 'string' || !value[key].startsWith(PNG_PREFIX)
          || !/^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(value[key])) return null;
        const maximum = key === 'avatar' ? 2 * 1024 * 1024 : 12 * 1024 * 1024;
        if (value[key].length > maximum) return null;
        record[key] = value[key];
      }
    }
    if (own(value, 'contours')) {
      if (!validContours(value.contours)) return null;
      record.contours = value.contours.map(path => path.map(point => [point[0], point[1]]));
    } else if (own(value, 'artwork')) return null;
    for (const [key, limit] of Object.entries(TEXT_LIMITS)) {
      if (own(value, key)) {
        if (typeof value[key] !== 'string' || value[key].length > limit) return null;
        record[key] = value[key];
      }
    }
    if (own(value, 'wallpaperStrength')) {
      if (!Number.isInteger(value.wallpaperStrength) || value.wallpaperStrength < 0 || value.wallpaperStrength > 75) return null;
      record.wallpaperStrength = value.wallpaperStrength;
    }
    try { recordByteLength(record); } catch { return null; }
    return record;
  }

  async function load(defaults) {
    const fallback = defaultSettings(defaults);
    defaultRecord = fallback;
    if (disposed) throw makeError('operation-cancelled');
    if (active) {
      loadReason = 'operation-busy';
      return { settings: fallback, baseline: currentBaseline, reason: loadReason };
    }
    if (!indexedDB || typeof indexedDB.open !== 'function') {
      currentSettings = fallback;
      currentBaseline = undefined;
      loadReason = 'settings-unavailable';
      return { settings: fallback, baseline: undefined, reason: loadReason };
    }
    const { task, promise } = beginOperation('load', 10_000, (timedOutTask) => {
      currentSettings = fallback;
      if (timedOutTask.baselineKnown) currentBaseline = timedOutTask.baseline;
      loadReason = 'operation-timeout';
      if (timedOutTask.transaction && !timedOutTask.transactionFinished) {
        const transaction = timedOutTask.transaction;
        timedOutTask.transaction = null;
        try { transaction.abort(); } catch {}
      }
      finish(timedOutTask, true, { settings: fallback, baseline: currentBaseline, reason: loadReason });
    });
    Promise.resolve().then(async () => {
      let baseline;
      try {
        const db = await openDatabase();
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        baseline = await readStoredRecord(db, task);
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        task.baseline = baseline;
        task.baselineKnown = true;
        let settings = baseline === undefined ? fallback : normalizeStoredRecord(baseline, fallback);
        let reason = '';
        if (baseline !== undefined && !settings) {
          settings = fallback;
          reason = 'settings-invalid';
        } else if (baseline !== undefined) {
          try { await validateRecordImages(task, settings); }
          catch (error) {
            if (error?.reason === 'operation-cancelled') throw error;
            settings = fallback;
            reason = error?.reason === 'operation-timeout' ? 'operation-timeout' : 'settings-invalid';
          }
        }
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        currentSettings = settings;
        currentBaseline = baseline;
        loadReason = reason;
        finish(task, true, { settings, baseline, reason });
      } catch (error) {
        if (task.settled) return;
        if (error?.reason === 'operation-cancelled') {
          finish(task, false, error);
          return;
        }
        currentSettings = fallback;
        currentBaseline = baseline;
        loadReason = error && typeof error.reason === 'string' ? error.reason : 'settings-unavailable';
        finish(task, true, {
          settings: fallback,
          baseline,
          reason: loadReason,
        });
      }
    });
    return promise;
  }

  function recordEquals(left, right) {
    if (left === undefined || right === undefined) return left === right;
    try { return JSON.stringify(left) === JSON.stringify(right); }
    catch { return false; }
  }

  function storageFailureFrom(error, operation) {
    const name = error?.name;
    if (name === 'QuotaExceededError') return makeError('settings-quota', 'quota-exceeded');
    if (error?.reason && ['settings-conflict', 'settings-invalid', 'asset-invalid',
      'operation-timeout', 'operation-cancelled', 'settings-quota', 'settings-unavailable'].includes(error.reason)) return error;
    return storageError('settings-unavailable', operation + '-failed');
  }

  function saveInTransaction(task, db, candidate) {
    let transaction;
    let failure = null;
    let timer = null;
    const clear = () => {
      if (timer !== null) {
        try { clearTimer.call(environment, timer); } catch {}
        timer = null;
      }
    };
    try {
      transaction = db.transaction(STORE_NAME, 'readwrite');
      task.transaction = transaction;
      timer = setTimer.call(environment, () => {
        failure = makeError('operation-timeout', 'database-write-timeout');
        try { transaction.abort(); } catch {}
        finish(task, false, failure);
      }, 5_000);
      const store = transaction.objectStore(STORE_NAME);
      const baselineRequest = store.get(SETTINGS_KEY);
      baselineRequest.onerror = () => {
        failure = storageFailureFrom(baselineRequest.error, 'database-read');
      };
      baselineRequest.onsuccess = () => {
        if (!isCurrent(task)) {
          failure = makeError('operation-cancelled');
          try { transaction.abort(); } catch {}
          return;
        }
        if (!recordEquals(baselineRequest.result, currentBaseline)) {
          failure = makeError('settings-conflict', 'baseline-changed');
          try { transaction.abort(); } catch {}
          return;
        }
        try {
          const putRequest = store.put(candidate, SETTINGS_KEY);
          putRequest.onerror = () => { failure = storageFailureFrom(putRequest.error, 'database-write'); };
        } catch (error) {
          failure = storageFailureFrom(error, 'database-write');
          try { transaction.abort(); } catch {}
        }
      };
      transaction.oncomplete = () => {
        clear();
        task.transactionFinished = true;
        if (task.transaction === transaction) task.transaction = null;
        if (task.settled || !isCurrent(task)) return;
        currentSettings = candidate;
        currentBaseline = candidate;
        loadReason = '';
        finish(task, true, candidate);
      };
      transaction.onerror = () => {
        failure ||= storageFailureFrom(transaction.error, 'database-write');
      };
      transaction.onabort = () => {
        clear();
        task.transactionFinished = true;
        if (task.transaction === transaction) task.transaction = null;
        if (!task.settled) finish(task, false, failure || storageError('settings-unavailable', 'database-write-aborted'));
      };
    } catch (error) {
      clear();
      if (task.transaction === transaction) task.transaction = null;
      finish(task, false, storageFailureFrom(error, 'database-write'));
    }
  }

  function save(candidate) {
    if (disposed) return Promise.reject(makeError('operation-cancelled'));
    if (active) return Promise.reject(makeError('operation-busy'));
    if (!indexedDB || typeof indexedDB.open !== 'function') {
      return Promise.reject(storageError('settings-unavailable', 'indexeddb-unavailable'));
    }
    if (!validEnvironment()) return Promise.reject(invalidData('environment-unavailable'));
    const { task, promise } = beginOperation('save', 10_000);
    Promise.resolve().then(async () => {
      try {
        const base = currentSettings || defaultSettings(candidate);
        const record = normalizeStoredRecord(candidate, base);
        if (!record || !['avatar', 'artwork', 'contours', ...Object.keys(TEXT_LIMITS), 'wallpaperStrength']
          .every(key => own(candidate, key))) throw makeError('settings-invalid');
        await validateRecordImages(task, record);
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        const db = await openDatabase();
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        saveInTransaction(task, db, record);
      } catch (error) {
        if (!task.settled) finish(task, false,
          error?.reason === 'operation-timeout' || error?.reason === 'operation-cancelled'
            ? error : storageFailureFrom(error, 'candidate-validation'));
      }
    });
    return promise;
  }

  function cloneSettings(value) {
    return {
      ...value,
      contours: Array.isArray(value?.contours)
        ? value.contours.map(path => path.map(point => [point[0], point[1]])) : [],
    };
  }

  function displayError(reason) {
    if (reason === 'settings-conflict') return 'settings.error.conflict';
    if (reason === 'settings-quota') return 'settings.error.quota';
    if (reason === 'settings-blocked') return 'settings.error.blocked';
    if (reason === 'operation-timeout') return 'settings.error.timeout';
    if (reason === 'settings-invalid' || reason === 'asset-invalid') return 'settings.error.invalid';
    return 'settings.error.save';
  }

  function setPanelStatus(key, role = 'status') {
    if (!panelControls?.status) return;
    panelStatus = key ? { key, role } : null;
    panelControls.status.textContent = panelStatus ? translate(panelStatus.key) : '';
    panelControls.status.setAttribute('role', panelStatus?.role || 'status');
  }

  function refreshLocalizedDefaults() {
    if (!defaultRecord) return;
    const fallbackKeys = {
      introTitle: 'animation.title.default',
      introCaption: 'animation.caption.default',
      artworkSubtitle: 'animation.subtitle.default',
    };
    for (const [key, translationKey] of Object.entries(fallbackKeys)) {
      if (!defaultTextFallbacks[key]) continue;
      const value = translate(translationKey);
      defaultRecord[key] = value;
      if (!panelOpen && currentBaseline === undefined && currentSettings) currentSettings[key] = value;
    }
  }

  function updatePanelText() {
    if (!panelControls) return;
    const { heading, close, labels, ariaLabels, buttons, strengthLabel, status } = panelControls;
    heading.textContent = translate('settings.title');
    close.setAttribute('aria-label', translate('settings.close'));
    for (const [key, label] of Object.entries(labels)) {
      label.element.textContent = translate(key, label.params);
    }
    for (const item of ariaLabels) item.control.setAttribute('aria-label', translate(item.key, item.params));
    for (const [key, button] of Object.entries(buttons)) button.textContent = translate(key);
    strengthLabel.textContent = translate('settings.wallpaperStrength.label', { min: 0, max: 75 });
    panelControls.strength.setAttribute('aria-label',
      translate('settings.wallpaperStrength.aria', { min: 0, max: 75 }));
    status.textContent = panelStatus ? translate(panelStatus.key) : '';
    status.setAttribute('role', panelStatus?.role || 'status');
    refreshAppearance();
  }

  function refreshAppearance() {
    if (!panelControls || disposed) return false;
    for (const item of panelControls.readouts) {
      try { item.element.textContent = item.value(); }
      catch { item.element.textContent = translate('settings.unknown'); }
    }
    return true;
  }

  function handleLocaleChange() {
    if (disposed) return;
    refreshLocalizedDefaults();
    updatePanelText();
  }

  function updatePanelBusy() {
    if (!panelControls) return;
    const busy = Boolean(active);
    for (const control of panelControls.controls) {
      control.disabled = busy;
      if (control.style && typeof control.style.setProperty === 'function') {
        control.style.setProperty('opacity', busy ? '.58' : '1');
        control.style.setProperty('cursor', busy ? 'wait' : control.tagName === 'BUTTON' ? 'pointer' : 'auto');
      }
    }
    if (busy && active.kind === 'import') setPanelStatus('settings.status.importing');
    else if (busy && active.kind === 'save') setPanelStatus('settings.status.saving');
  }

  function setStyle(element, properties) {
    if (!element?.style || typeof element.style.setProperty !== 'function') return;
    for (const [name, value] of Object.entries(properties)) element.style.setProperty(name, value);
  }

  function styleInput(control) {
    setStyle(control, {
      'box-sizing': 'border-box',
      width: '100%',
      border: '1px solid var(--agent-skin-border, CanvasText)',
      'border-radius': '8px',
      padding: control.type === 'range' ? '0' : control.type === 'file' ? '7px' : '9px',
      'background-color': 'var(--agent-skin-surface, Canvas)',
      color: 'var(--agent-skin-text, CanvasText)',
      font: 'inherit',
    });
  }

  function styleButton(button, primary = false) {
    setStyle(button, {
      border: '1px solid var(--agent-skin-border, CanvasText)',
      'border-radius': '999px',
      padding: '8px 14px',
      'background-color': primary
        ? 'var(--agent-skin-text, CanvasText)' : 'var(--agent-skin-surface, Canvas)',
      color: primary
        ? 'var(--agent-skin-surface, Canvas)' : 'var(--agent-skin-text, CanvasText)',
      font: 'inherit',
      cursor: 'pointer',
    });
  }

  function truncateText(value, limit) {
    let result = String(value ?? '').slice(0, limit);
    if (result.length && result.charCodeAt(result.length - 1) >= 0xd800
      && result.charCodeAt(result.length - 1) <= 0xdbff) result = result.slice(0, -1);
    return result;
  }

  function updatePanelFields() {
    if (!panelControls || !draft) return;
    for (const [key, control] of Object.entries(panelControls.fields)) control.value = draft[key] ?? '';
    panelControls.strength.value = String(draft.wallpaperStrength);
    panelControls.strengthValue.textContent = String(draft.wallpaperStrength);
    for (const [role, preview] of Object.entries(panelControls.previews)) {
      const value = draft[role];
      preview.hidden = !value;
      preview.style.setProperty('display', value ? 'block' : 'none');
      if (value) preview.src = value;
      else preview.removeAttribute('src');
    }
    refreshAppearance();
  }

  function buildSettingsPanel() {
    if (dialog) return true;
    if (!document || typeof document.createElement !== 'function' || !document.body) return false;
    dialog = document.createElement('dialog');
    dialog.setAttribute('aria-labelledby', 'agent-skin-settings-title');
    dialog.setAttribute('data-agent-skin-settings', '');
    dialog.style.cssText = 'box-sizing:border-box;color-scheme:inherit;width:min(740px,calc(100vw - 24px));max-height:calc(100vh - 24px);overflow:auto;padding:0;border:1px solid var(--agent-skin-border,CanvasText);border-radius:18px;background:var(--agent-skin-surface,Canvas);color:var(--agent-skin-text,CanvasText);box-shadow:0 24px 90px #0006;font:14px/1.5 system-ui,sans-serif';
    dialog.style.setProperty('color-scheme', 'inherit');
    dialog.style.setProperty('border-color', 'var(--agent-skin-border, CanvasText)');
    dialog.style.setProperty('background-color', 'var(--agent-skin-surface, Canvas)');
    dialog.style.setProperty('color', 'var(--agent-skin-text, CanvasText)');
    const content = document.createElement('section');
    content.style.cssText = 'padding:22px 24px 20px';
    const header = document.createElement('header');
    header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:16px';
    const heading = document.createElement('h2');
    heading.id = 'agent-skin-settings-title';
    heading.textContent = translate('settings.title');
    heading.style.cssText = 'min-width:0;flex:1;margin:0;font-size:20px';
    if (appearanceAvatar) {
      const identityAvatar = document.createElement('img');
      identityAvatar.setAttribute('data-agent-skin-appearance-avatar', '');
      identityAvatar.setAttribute('alt', '');
      identityAvatar.src = appearanceAvatar;
      setStyle(identityAvatar, {
        width: '36px', height: '36px', 'border-radius': '12px',
        'object-fit': 'cover', flex: 'none',
      });
      header.appendChild(identityAvatar);
    }
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = '×';
    styleButton(close);
    close.setAttribute('aria-label', translate('settings.close'));
    close.addEventListener('click', cancelSettings);
    header.append(heading, close);
    content.appendChild(header);

    const fields = Object.create(null);
    const labels = Object.create(null);
    const ariaLabels = [];
    const controls = [close];
    const readouts = [];
    const previews = {};
    let section = content;
    const addText = (key, parent = section, tag = 'p') => {
      const element = document.createElement(tag);
      element.style.cssText = tag === 'h3' ? 'margin:0;font-size:16px' : 'margin:8px 0;overflow-wrap:anywhere;color:var(--agent-skin-muted,CanvasText)';
      labels[key] = { element, params: {} };
      element.textContent = translate(key);
      parent.appendChild(element);
      return element;
    };
    const addSection = (name, note) => {
      section = document.createElement('section');
      section.setAttribute('data-agent-skin-settings-section', name);
      section.setAttribute('aria-labelledby', `agent-skin-section-${name}`);
      section.style.cssText = 'min-width:0;margin-top:22px;padding-top:20px;border-top:1px solid var(--agent-skin-border,CanvasText)';
      content.appendChild(section);
      addText(`settings.section.${name}`, section, 'h3').id = `agent-skin-section-${name}`;
      addText(note);
    };
    const addInfo = (key, labelKey, value) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;flex-wrap:wrap;justify-content:space-between;gap:3px 20px;margin-top:10px;min-width:0';
      const label = addText(labelKey, row, 'span');
      label.style.cssText += ';flex:1 1 180px;margin:0';
      const element = document.createElement('span');
      element.style.cssText = 'min-width:0;flex:1 1 220px;overflow-wrap:anywhere';
      element.setAttribute('data-agent-skin-setting-value', key);
      readouts.push({ element, value });
      row.appendChild(element);
      section.appendChild(row);
    };
    const localized = values => values?.[localization?.locale || 'zh-CN'] || translate('settings.unknown');
    const inherited = key => {
      try { return environment.getAppearance?.()?.[key]; } catch { return undefined; }
    };
    addText('settings.draft.note', content);
    addSection('identity', 'settings.identity.note');
    addInfo('appName', 'settings.appName', () => localized(themeConfig?.identity?.appName));
    addInfo('botName', 'settings.botName', () => localized(themeConfig?.identity?.botName));
    addInfo('version', 'settings.version', () => themeConfig?.identity?.version && themeConfig?.identity?.build
      ? `${themeConfig.identity.version} · ${themeConfig.identity.build}` : translate('settings.unknown'));
    const identitySection = section;
    const buildDetails = document.createElement('details');
    buildDetails.style.cssText = 'margin-top:14px';
    addText('settings.buildDetails', buildDetails, 'summary').style.cssText = 'cursor:pointer';
    identitySection.appendChild(buildDetails);
    section = buildDetails;
    addInfo('icon', 'settings.icon', () => themeConfig?.identity?.iconInput || translate('settings.unknown'));
    addInfo('botAvatar', 'settings.botAvatar', () => themeConfig?.identity?.entryAvatarInput || translate('settings.unknown'));
    addInfo('installationName', 'settings.installationName', () => themeConfig?.identity?.installationName || translate('settings.unknown'));
    const installation = addText('settings.installation');
    installation.setAttribute('data-agent-skin-setting-value', 'installation');
    section = identitySection;
    addSection('startup', 'settings.startup.note');
    const addRow = (key, control, params = {}, ariaKey = key) => {
      const wrapper = document.createElement('label');
      wrapper.style.cssText = 'display:grid;gap:5px;margin-top:14px';
      const label = document.createElement('span');
      label.textContent = translate(key, params);
      labels[key] = { element: label, params };
      control.setAttribute('aria-label', translate(ariaKey, params));
      ariaLabels.push({ control, key: ariaKey, params });
      wrapper.append(label, control);
      section.appendChild(wrapper);
      controls.push(control);
      return control;
    };
    const addFile = (role, key, actionKey) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/png,image/jpeg,image/webp';
      input.hidden = true;
      input.tabIndex = -1;
      input.setAttribute('aria-hidden', 'true');
      input.setAttribute('data-agent-skin-image-input', role);
      styleInput(input);
      input.addEventListener('change', async () => {
        const file = input.files?.[0];
        if (!file || !panelOpen || active) return;
        const panelAtStart = panelGeneration;
        const importing = importImage(file, role);
        updatePanelBusy();
        try {
          const result = await importing;
          if (!panelOpen || panelAtStart !== panelGeneration) return;
          if (role === 'avatar') draft.avatar = result.dataURL;
          else { draft.artwork = result.dataURL; draft.contours = result.contours; }
          updatePanelFields();
          setPanelStatus(result.warning === 'large-image'
            ? 'settings.status.imageLarge' : 'settings.status.imageReady');
        } catch (error) {
          if (panelOpen && panelAtStart === panelGeneration) setPanelStatus(displayError(error?.reason), 'alert');
        } finally {
          input.value = '';
          updatePanelBusy();
        }
      });
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('data-agent-skin-image-action', role);
      button.textContent = translate(actionKey);
      styleButton(button);
      button.style.setProperty('justify-self', 'start');
      button.addEventListener('click', () => {
        if (panelOpen && !active) input.click?.();
      });
      const rowAction = addRow(key, button, {}, actionKey);
      controls.push(input);
      section.appendChild(input);
      const preview = document.createElement('img');
      preview.setAttribute('alt', '');
      preview.setAttribute('data-agent-skin-image-preview', role);
      preview.style.cssText = role === 'avatar'
        ? 'display:block;width:72px;height:72px;object-fit:cover;border-radius:16px;margin-top:10px'
        : 'display:block;width:100%;max-height:190px;object-fit:cover;border-radius:10px;margin-top:10px';
      previews[role] = preview;
      section.appendChild(preview);
      buttons[actionKey] = button;
      return rowAction;
    };
    const buttons = Object.create(null);
    addFile('avatar', 'settings.avatar.label', 'settings.button.choosePortrait');

    for (const [key, limit, labelKey] of [
      ['introTitle', 16, 'settings.introTitle.label'],
      ['introCaption', 48, 'settings.introCaption.label'],
      ['artworkSubtitle', 60, 'settings.artworkSubtitle.label'],
    ]) {
      const control = key === 'artworkSubtitle' ? document.createElement('textarea') : document.createElement('input');
      if (control.tagName === 'INPUT') control.type = 'text';
      styleInput(control);
      control.maxLength = limit;
      control.addEventListener('input', () => {
        const value = truncateText(control.value, limit);
        if (control.value !== value) control.value = value;
        if (draft) draft[key] = value;
      });
      fields[key] = control;
      addRow(labelKey, control, { limit });
    }

    addSection('workspace', 'settings.workspace.note');
    addFile('artwork', 'settings.artwork.label', 'settings.button.chooseBackground');
    addInfo('layout', 'settings.layout', () => translate('settings.layout.value'));
    const strength = document.createElement('input');
    strength.type = 'range';
    strength.min = '0';
    strength.max = '75';
    strength.step = '1';
    styleInput(strength);
    const strengthValue = document.createElement('output');
    strengthValue.style.cssText = 'min-width:3ch;text-align:right';
    strength.addEventListener('input', () => {
      if (!draft) return;
      draft.wallpaperStrength = Number(strength.value);
      strengthValue.textContent = String(draft.wallpaperStrength);
    });
    const strengthRow = document.createElement('label');
    strengthRow.style.cssText = 'display:grid;grid-template-columns:1fr auto;gap:8px 12px;align-items:center;margin-top:14px';
    const strengthLabel = document.createElement('span');
    strengthLabel.textContent = translate('settings.wallpaperStrength.label', { min: 0, max: 75 });
    strengthRow.append(strengthLabel, strengthValue, strength);
    section.appendChild(strengthRow);
    controls.push(strength);

    addSection('inherited', 'settings.inherited.note');
    addInfo('preferenceSource', 'settings.preferenceSource', () => ['official', 'preview'].includes(inherited('source'))
      ? translate(`settings.preferenceSource.${inherited('source')}`) : translate('settings.unknown'));
    addInfo('locale', 'settings.locale', () => inherited('locale') || localization?.locale || translate('settings.unknown'));
    addInfo('theme', 'settings.theme', () => ['light', 'dark'].includes(inherited('theme'))
      ? translate(`settings.theme.${inherited('theme')}`) : translate('settings.unknown'));
    addInfo('reducedMotion', 'settings.reducedMotion', () => typeof inherited('reducedMotion') === 'boolean'
      ? translate(inherited('reducedMotion') ? 'settings.on' : 'settings.off') : translate('settings.unknown'));
    addInfo('surface', 'settings.surface', () => inherited('colors')?.surface || translate('settings.unknown'));
    addInfo('source', 'settings.source', () => translate(loadReason
      ? 'settings.source.unavailable' : currentBaseline === undefined ? 'settings.source.defaults' : 'settings.source.user'));

    const status = document.createElement('p');
    status.style.cssText = 'min-height:1.5em;margin:14px 0 0';
    status.style.setProperty('color', 'var(--agent-skin-muted, CanvasText)');
    status.setAttribute('aria-live', 'polite');
    content.appendChild(status);
    const actions = document.createElement('footer');
    actions.style.cssText = 'position:sticky;bottom:0;display:flex;justify-content:flex-end;flex-wrap:wrap;gap:9px;margin-top:16px;padding:12px 0;background:var(--agent-skin-surface,Canvas);border-top:1px solid var(--agent-skin-border,CanvasText)';
    const restore = document.createElement('button');
    restore.type = 'button';
    styleButton(restore);
    restore.textContent = translate('settings.button.restore');
    restore.addEventListener('click', () => {
      if (active || !panelOpen) return;
      draft = cloneSettings(defaultRecord || currentSettings);
      updatePanelFields();
      setPanelStatus('settings.status.defaultsRestored');
    });
    const cancel = document.createElement('button');
    cancel.type = 'button';
    styleButton(cancel);
    cancel.textContent = translate('settings.button.cancel');
    cancel.addEventListener('click', cancelSettings);
    const saveButton = document.createElement('button');
    saveButton.type = 'button';
    styleButton(saveButton, true);
    saveButton.textContent = translate('settings.button.save');
    saveButton.addEventListener('click', async () => {
      if (!panelOpen || active || !draft) return;
      for (const key of Object.keys(TEXT_LIMITS)) draft[key] = truncateText(draft[key], TEXT_LIMITS[key]);
      const panelAtStart = panelGeneration;
      const saving = save(cloneSettings(draft));
      updatePanelBusy();
      try {
        const saved = await saving;
        if (!panelOpen || panelAtStart !== panelGeneration) return;
        const callback = panelCallbacks?.onSaved;
        closePanel('saved');
        try { callback?.(saved); } catch {}
      } catch (error) {
        if (panelOpen && panelAtStart === panelGeneration) setPanelStatus(displayError(error?.reason), 'alert');
      } finally {
        updatePanelBusy();
      }
    });
    controls.push(restore, cancel, saveButton);
    actions.append(restore, cancel, saveButton);
    content.appendChild(actions);
    dialog.append(content);
    document.body.appendChild(dialog);
    dialog.addEventListener('cancel', event => {
      event.preventDefault();
      cancelSettings();
    });
    panelControls = {
      controls, status, fields, strength, strengthValue, heading, close, labels, ariaLabels, readouts, previews,
      buttons: {
        ...buttons,
        'settings.button.restore': restore,
        'settings.button.cancel': cancel,
        'settings.button.save': saveButton,
      },
      strengthLabel,
    };
    updatePanelText();
    return true;
  }

  function openSettings(callbacks = {}) {
    if (disposed || panelOpen || !currentSettings || active || !buildSettingsPanel()) return false;
    draft = cloneSettings(currentSettings);
    panelCallbacks = callbacks && typeof callbacks === 'object' ? callbacks : {};
    panelGeneration++;
    panelOpen = true;
    updatePanelFields();
    if (loadReason === 'settings-invalid') setPanelStatus('settings.load.invalid', 'alert');
    else if (loadReason === 'operation-timeout') setPanelStatus('settings.load.timeout', 'alert');
    else if (loadReason === 'settings-unavailable' || loadReason === 'settings-blocked') {
      setPanelStatus('settings.load.unavailable', 'alert');
    } else setPanelStatus('');
    try { dialog.showModal(); }
    catch {
      panelOpen = false;
      panelCallbacks = null;
      return false;
    }
    updatePanelBusy();
    try { panelCallbacks.onOpen?.(); } catch {}
    return true;
  }

  function closePanel(returnValue = '') {
    if (!panelOpen) return false;
    panelOpen = false;
    panelGeneration++;
    draft = null;
    panelCallbacks = null;
    try { dialog?.close(returnValue); } catch {}
    refreshLocalizedDefaults();
    return true;
  }

  function cancelSettings() {
    if (!panelOpen || active) return false;
    const callback = panelCallbacks?.onCancel;
    closePanel('cancel');
    try { callback?.(); } catch {}
    return true;
  }

  function isSettingsOpen() { return panelOpen; }
  function isBusy() { return active !== null; }

  function dispose() {
    if (disposed) return false;
    disposed = true;
    generation++;
    panelGeneration++;
    if (active) finish(active, false, makeError('operation-cancelled'));
    panelOpen = false;
    panelCallbacks = null;
    draft = null;
    try { dialog?.close('dispose'); } catch {}
    try { dialog?.remove(); } catch {}
    try { localizationUnsubscribe?.(); } catch {}
    localizationUnsubscribe = null;
    dialog = null;
    panelControls = null;
    try { database?.close(); } catch {}
    database = null;
    return true;
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
    if (disposed) return Promise.reject(makeError('operation-cancelled'));
    if (!validEnvironment()) return Promise.reject(invalidData('environment-unavailable'));
    if (active) return Promise.reject(makeError('operation-busy'));
    if (role !== 'avatar' && role !== 'artwork') return Promise.reject(invalidData('invalid-role'));
    if (!file || !Number.isSafeInteger(file.size) || file.size <= 0) {
      return Promise.reject(invalidData('file-empty'));
    }
    if (file.size > MAX_INPUT_BYTES) return Promise.reject(invalidData('file-too-large'));

    const task = {
      kind: 'import',
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

  try {
    const unsubscribe = localization && typeof localization.subscribe === 'function'
      ? localization.subscribe(handleLocaleChange) : null;
    if (typeof unsubscribe === 'function') localizationUnsubscribe = unsubscribe;
  } catch {}

  function cancelImport() {
    if (!active || active.kind !== 'import') return false;
    generation += 1;
    finish(active, false, makeError('operation-cancelled'));
    return true;
  }

  return {
    load,
    save,
    importImage,
    cancelImport,
    openSettings,
    cancelSettings,
    isSettingsOpen,
    isBusy,
    refreshAppearance,
    dispose,
  };
}
