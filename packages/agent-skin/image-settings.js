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
  const dreamThemeStyle = environment?.dreamThemeStyle
    ?? (typeof createDreamThemeStyle === 'function' ? createDreamThemeStyle() : null);
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
  const MAX_HEADER_READ_BYTES = 2 * 1024 * 1024;
  const MAX_SOURCE_PIXELS = 48_000_000;
  const LARGE_SOURCE_PIXELS = 16_000_000;
  const PNG_PREFIX = 'data:image/png;base64,';
  // Storage namespace seam (agent-skin-zcode-contract/v0.1): a host page adapter may
  // inject its own verified namespace through the existing environment object.
  // The contract name is frozen under its historical ZCode-era name; installed
  // 0.9.0 state depends on the exact string.
  // The defaults below are the legacy Codex values and stay verbatim; nothing here
  // adds a new storage backend.
  const namespaceDefaults = Object.freeze({
    databaseName: 'azhou-codex-startup',
    databaseVersion: 1,
    storeName: 'settings',
    settingsKey: 'images',
  });
  const injectedNamespace = environment && typeof environment.settingsNamespace === 'object'
    && environment.settingsNamespace !== null ? environment.settingsNamespace : {};
  const boundedNamespaceString = value => typeof value === 'string'
    && value.length >= 1 && value.length <= 100 ? value : null;
  const DATABASE_NAME = boundedNamespaceString(injectedNamespace.databaseName)
    ?? namespaceDefaults.databaseName;
  const DATABASE_VERSION = Number.isSafeInteger(injectedNamespace.databaseVersion)
    && injectedNamespace.databaseVersion >= 1
    ? injectedNamespace.databaseVersion : namespaceDefaults.databaseVersion;
  const STORE_NAME = boundedNamespaceString(injectedNamespace.storeName)
    ?? namespaceDefaults.storeName;
  const SETTINGS_KEY = boundedNamespaceString(injectedNamespace.settingsKey)
    ?? namespaceDefaults.settingsKey;
  const MAX_RECORD_BYTES = 20 * 1024 * 1024;
  const TEXT_LIMITS = Object.freeze({ introTitle: 16, introCaption: 48, artworkSubtitle: 60 });
  const FALLBACK_MESSAGES = Object.freeze({
    'animation.title.default': '阿舟 AI 实验室',
    'animation.caption.default': 'AZHOU / AI LAB',
    'animation.subtitle.default': '和阿舟一起，把想法做出来。',
    "settings.dream.import": "导入 Dream 源胶囊",
    "settings.dream.list": "本机 Dream 主题",
    "settings.dream.apply": "应用选中 Dream 主题",
    "settings.dream.note": "导入立即存入独立本机目录，不保存其他草稿、不应用。仅接受 CLI 导出的源胶囊，非 ZIP 或 Azhou 预设。首个 profile 仅映射 main 静态背景色字面值，拒绝其他清单字段或样式声明。",
    "settings.dream.imported": "Dream 源胶囊已存入本机目录；当前外观与其他草稿未变。",
    "settings.dream.readonly": "Dream 目录无法识别或验证，已设为只读；原数据保留。",
    "settings.dream.error": "Dream 导入失败；已保存目录和当前外观未改变。请使用有效源胶囊。",
    'settings.presets.name': '本机外观预设名称（最多40个字符）',
    'settings.presets.list': '本机外观预设',
    'settings.presets.add': '新增预设',
    'settings.presets.load': '载入到草稿',
    'settings.presets.note': '仅本机，最多8项。选择阿舟主题后可新增预设。新增和载入仅改草稿；统一保存后生效。恢复全部默认保留预设目录。',
    'settings.presets.unavailable': '本机预设目录无法验证，已禁用；当前外观仍可编辑和保存，原目录保留。',
    'settings.presets.added': '预设已加入目录草稿；尚未保存。',
    'settings.presets.loaded': '预设已载入当前草稿；尚未保存。',
    'settings.presets.import': '导入 Azhou 预设文件',
    'settings.presets.export': '导出选中预设',
    'settings.presets.exchangeNote': '仅支持单项 Azhou JSON 文件，不是 Dream ZIP。导入仅加入目录草稿，不改变当前外观；保存后保留。导出选中草稿，不会隐式保存。',
    'settings.presets.imported': 'Azhou 预设已加入目录草稿；当前外观未变，尚未保存。',
    'settings.presets.exported': '已导出选中预设；本机草稿未保存。',
    'settings.presets.fileError': '无法导入或导出 Azhou 预设文件。请使用有效的单项 Azhou JSON 文件（最多20 MiB）。',
    'settings.title': '阿舟 · 主题与外观',
    'settings.close': '取消并关闭设置',
    'settings.categories.label': '设置分类',
    'settings.section.workspace': '工作区背景',
    'settings.section.startup': '启动动画',
    'settings.section.about': '关于与状态',
    'settings.appName': '应用名称',
    'settings.botName': '助手名称',
    'settings.version': '版本 · 构建',
    'settings.runningVersion': '当前运行：{version}',
    'settings.about.buildDetails': '应用与版本信息',
    'settings.startup.note': '保存后用于下次启动；预览不会保存草稿。',
    'settings.preview.background.label': '背景草稿预览',
    'settings.preview.background.caption': '当前草稿 · 缩略图裁切可能与工作区不同 · 保存后应用',
    'settings.preview.background.empty': '选择图片后可在此预览',
    'settings.avatar.label': '启动头像',
    'settings.artwork.label': '背景图片',
    'settings.introTitle.label': '启动标题（最多 {limit} 个字符）',
    'settings.introCaption.label': '标题说明（最多 {limit} 个字符）',
    'settings.artworkSubtitle.label': '背景字幕（最多 {limit} 个字符）',
    'settings.themeControl.choice': '主题',
    'settings.themeControl.legacy': '原有外观',
    'settings.themeControl.azhou': '阿舟 · Q 场景',
    'settings.themeControl.mode': '阅读遮罩设置',
    'settings.themeControl.follow': '跟随主题',
    'settings.themeControl.override': '自定义透明度',
    'settings.themeControl.transparency': '阅读遮罩透明度',
    'settings.themeControl.description': '数值越高，遮罩越透明，背景图片越清晰；不改变文字和图标。',
    'settings.themeControl.chooseFirst': '选择阿舟主题后可调整',
    'settings.themeControl.followReason': '使用主题默认遮罩；选择自定义后可调整',
    'settings.themeControl.strengthNote': '阿舟主题使用阅读遮罩设置。背景强度保留原有外观设置，设为 0 仍关闭背景。',
    'settings.wallpaperStrength.label': '背景强度（{min}–{max}）',
    'settings.button.restore': '恢复全部默认',
    'settings.button.cancel': '取消',
    'settings.button.save': '保存',
    'settings.button.previewAnimation': '预览动画',
    'settings.button.closePreview': '关闭动画预览',
    'settings.button.close': '关闭',
    'settings.button.retryApply': '重试应用',
    'settings.button.applyingBackground': '正在应用…',
    'settings.status.applyingBackground': '设置已保存，正在应用背景…',
    'settings.status.saved': '设置已保存。',
    'settings.error.backgroundApply': '设置已保存，但背景应用失败。可以重试，或关闭设置。',
    'settings.button.choosePortrait': '选择启动头像',
    'settings.button.chooseBackground': '选择背景图片',
    'settings.status.importing': '正在处理图片…',
    'settings.importError.fileEmpty': '{field}文件为空。请选择一张图片。',
    'settings.importError.fileTooLarge': '{field}超过 30 MiB。请选择较小的图片。',
    'settings.importError.imageTooLarge': '{field}原始像素超过 48 MP。请选择尺寸较小的图片。',
    'settings.importError.mimeMismatch': '{field}的文件类型声明与实际内容不符。请选择正确格式的 PNG、JPEG 或 WebP 图片。',
    'settings.importError.unsupported': '{field}内容不是受支持的 PNG、JPEG 或 WebP。请选择其中一种格式的图片。',
    'settings.importError.decode': '{field}无法解码。请换一张可正常打开的图片。',
    'settings.importError.dimensions': '{field}的原始尺寸无效。请重新选择一张图片。',
    'settings.importError.canvas': '当前环境无法准备{field}。请稍后重试。',
    'settings.importError.pixelsUnavailable': '当前环境无法读取{field}的像素。请换一张图片重试。',
    'settings.importError.pixelsInvalid': '{field}的像素数据不完整。请重新选择原图。',
    'settings.importError.contoursEmpty': '无法从{field}提取有效轮廓。请选择边缘更清楚的图片。',
    'settings.importError.contoursComplex': '{field}包含过多轮廓点，无法处理。请换一张细节较少的图片。',
    'settings.importError.pngEncode': '{field}无法转换为 PNG。请重新选择图片。',
    'settings.importError.outputTooLarge': '{field}处理后超过存储上限。请使用文件较小的图片。',
    'settings.importError.decodeTimeout': '解码{field}超时。请换一张较小的图片。',
    'settings.importError.timeout': '处理{field}超时。请尝试较小的图片。',
    'settings.importError.busy': '另一张图片正在处理中。请等待后重新选择{field}。',
    'settings.importError.environment': '当前无法处理{field}。请稍后重试或换一张图片。',
    'settings.importError.processing': '无法处理{field}。请使用有效的 PNG、JPEG 或 WebP 图片后重试。',
    'settings.status.saving': '正在校验候选并保存…',
    'settings.status.imageLarge': '图片已准备；原图超过 16 MP，处理可能较慢。',
    'settings.status.imageReady': '图片已准备，可以保存。',
    'settings.status.defaultsRestored': '草稿已恢复为默认设置；已保存值尚未更改。',
    'settings.status.previewStarted': '动画预览已启动；草稿仍未保存。',
    'settings.status.previewUnavailable': '当前无法预览动画；草稿仍可保存。',
    'settings.error.preview': '动画预览失败；草稿仍可编辑或保存。',
    'settings.error.conflict': '本页更改尚未保存；关闭将丢弃。可以先复制需要保留的文字。重新打开将读取其他页面保存的新值。',
    'settings.error.quota': '存储空间不足。请更换图片后重试。',
    'settings.error.blocked': '设置数据库被其他页面阻塞。稍后可以重试。',
    'settings.error.timeout': '操作超时，面板已恢复，可以取消或重试。',
    'settings.error.invalid': '候选设置无法验证，已保存内容保持不变。',
    'settings.error.save': '保存失败，已保存内容保持不变。',
    'settings.load.readonly': '保存记录使用较新的格式，当前只读，不会覆写。请使用支持该格式的版本。',
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
  let currentThemeBaseline;
  let currentLibraryBaseline;
  let currentDreamBaseline;
  let dreamDirectoryView = {status:'missing',entries:[]};
  let currentLibrary = { schemaVersion: 1, revision: 0, entries: [] };
  let draftLibrary = null;
  let currentThemeState = null;
  let currentThemeReason = '';
  let currentThemeReadOnly = false;
  let currentImagesReadOnly = false;
  let defaultRecord = null;
  let defaultTextFallbacks = Object.create(null);
  let loadReason = '';
  let dialog = null;
  let panelFocusSheet = null;
  let panelControls = null;
  let draft = null;
  let draftTheme = null;
  let draftThemePreference = null;
  let draftAppearances = null;
  let panelOpen = false;
  let panelGeneration = 0;
  let panelCallbacks = null;
  let panelCommit = null;
  let panelApplying = false;
  let panelThemeApplying = false;
  let panelSavedNotified = false;
  let panelPresentation = 'modal';
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
    if (!succeeded && task.deferSettlement) {
      task.failure ||= value;
      task.applyAbort.abort();
      try { task.transaction?.abort(); } catch {}
      return;
    }
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
    if (task.failure) throw task.failure;
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
      let themeValue;
      let sawTheme = false;
      let libraryValue;
      let sawLibrary = false;
      let dreamValue;
      let sawDream = false;
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
        const store = transaction.objectStore(STORE_NAME);
        const dreamRequest = store.get(DREAM_KEY);
        dreamRequest.onsuccess = () => { dreamValue = dreamRequest.result; sawDream = true; };
        dreamRequest.onerror = () => { failure = storageError('settings-unavailable', 'dream-read-failed'); };
        const libraryRequest = store.get(LIBRARY_KEY);
        libraryRequest.onsuccess = () => { libraryValue = libraryRequest.result; sawLibrary = true; };
        libraryRequest.onerror = () => { failure = storageError('settings-unavailable', 'library-read-failed'); };
        const themeRequest = store.get(THEME_KEY);
        themeRequest.onsuccess = () => { themeValue = themeRequest.result; sawTheme = true; };
        themeRequest.onerror = () => { failure = storageError('settings-unavailable', 'theme-read-failed'); };
        request = store.get(SETTINGS_KEY);
        request.onsuccess = () => { value = request.result; sawResult = true; };
        request.onerror = () => { failure = storageError('settings-unavailable', 'database-read-failed'); };
        transaction.oncomplete = () => {
          if (task && task.transaction === transaction) task.transaction = null;
          finish(sawResult && sawTheme && sawLibrary && sawDream, sawResult && sawTheme && sawLibrary && sawDream
            ? { images: value, theme: themeValue, library: libraryValue, dream: dreamValue } : (failure || storageError('settings-unavailable', 'database-read-failed')));
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

  async function load(defaults, includeLibrary = true) {
    const fallback = defaultSettings(defaults);
    defaultRecord = fallback;
    if (disposed) throw makeError('operation-cancelled');
    if (active) {
      loadReason = 'operation-busy';
      return { settings: cloneSettings(fallback), baseline: currentBaseline, reason: loadReason };
    }
    if (!indexedDB || typeof indexedDB.open !== 'function') {
      currentSettings = fallback;
      currentBaseline = undefined;
      loadReason = 'settings-unavailable';
      return { settings: cloneSettings(fallback), baseline: undefined, reason: loadReason };
    }
    const { task, promise } = beginOperation('load', 10_000, (timedOutTask) => {
      currentSettings = timedOutTask.resolvedSettings || fallback;
      if (timedOutTask.baselineKnown) currentBaseline = timedOutTask.baseline;
      loadReason = 'operation-timeout';
      if (timedOutTask.transaction && !timedOutTask.transactionFinished) {
        const transaction = timedOutTask.transaction;
        timedOutTask.transaction = null;
        try { transaction.abort(); } catch {}
      }
      finish(timedOutTask, true, { settings: cloneSettings(currentSettings), baseline: currentBaseline, reason: loadReason });
    });
    Promise.resolve().then(async () => {
      let baseline;
      try {
        const db = await openDatabase();
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        const stored = await readStoredRecord(db, task);
        baseline = stored.images;
        let resolvedTheme = null;
        let themeReason = '';
        try { resolvedTheme = await resolveTheme(stored.theme, baseline); }
        catch (error) { themeReason = error?.reason || 'settings-invalid'; }
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        currentThemeReadOnly = !!themeReason && stored.theme !== undefined && stored.theme !== null && stored.theme?.schemaVersion !== 1;
        currentImagesReadOnly = !!baseline && typeof baseline === 'object' && own(baseline,'schemaVersion') && baseline.schemaVersion !== 1;
        currentLibraryBaseline = stored.library;
        currentDreamBaseline = stored.dream;
        currentLibrary = null;
        currentThemeBaseline = stored.theme;
        currentThemeState = resolvedTheme;
        currentThemeReason = themeReason;
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
        task.resolvedSettings = settings;
        try { if (includeLibrary) currentLibrary = await validateLibrary(task, stored.library); }
        catch (error) {
          if (error?.reason === 'operation-cancelled') throw error;
          currentLibrary = null;
        }
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        currentSettings = settings;
        currentBaseline = baseline;
        loadReason = reason;
        finish(task, true, { settings: cloneSettings(settings), baseline, reason, themeState: currentThemeState?.activeThemeId ? structuredCloneTheme(currentThemeState) : null });
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
          settings: cloneSettings(fallback),
          baseline,
          reason: loadReason,
        });
      }
    });
    return promise;
  }

  async function loadSnapshot(defaults, includeLibrary = false) {
    const explicitDefaults = {
      introTitle: typeof defaults?.introTitle === 'string',
      introCaption: typeof defaults?.introCaption === 'string',
      artworkSubtitle: typeof defaults?.artworkSubtitle === 'string',
    };
    let loaded;
    try {
      loaded = await load(defaults, includeLibrary);
    } catch (error) {
      return Object.freeze({
        status: 'failure',
        reason: typeof error?.reason === 'string' ? error.reason : 'settings-unavailable',
      });
    }
    if (currentThemeReadOnly || currentImagesReadOnly) return Object.freeze({status:'failure',reason:'settings-blocked',readOnly:true});
    const reason = typeof loaded?.reason === 'string' ? loaded.reason : 'settings-unavailable';
    if (reason) return Object.freeze({ status: 'failure', reason });
    if (currentThemeState?.selection?.kind === 'imported') return loadImportedSnapshot(loaded,explicitDefaults);

    try {
      const contours = (Array.isArray(loaded.settings?.contours) ? loaded.settings.contours : [])
        .map(path => Object.freeze(path.map(point => Object.freeze([point[0], point[1]]))));
      const settings = Object.freeze({
        schemaVersion: loaded.settings?.schemaVersion,
        avatar: loaded.settings?.avatar,
        artwork: loaded.settings?.artwork,
        contours: Object.freeze(contours),
        introTitle: loaded.settings?.introTitle,
        introCaption: loaded.settings?.introCaption,
        artworkSubtitle: loaded.settings?.artworkSubtitle,
        wallpaperStrength: loaded.settings?.wallpaperStrength,
      });
      const explicitText = Object.freeze({
        introTitle: explicitDefaults.introTitle || typeof loaded.baseline?.introTitle === 'string',
        introCaption: explicitDefaults.introCaption || typeof loaded.baseline?.introCaption === 'string',
        artworkSubtitle: explicitDefaults.artworkSubtitle || typeof loaded.baseline?.artworkSubtitle === 'string',
      });
      return Object.freeze({
        status: loaded.baseline === undefined ? 'missing' : 'valid',
        settings,
        explicitText,
        themeState: currentThemeState?.activeThemeId ? structuredCloneTheme(currentThemeState) : null,
        themeReason: currentThemeReason,
      });
    } catch {
      return Object.freeze({ status: 'failure', reason: 'settings-invalid' });
    }
  }

  async function projectImportedSnapshot(task, loaded, explicitDefaults, state, directoryRecord) {
    const directory = dreamDirectoryShape(directoryRecord);
    const entry = directory.entries.find(entry=>entry.capsuleSha256 === state.selection.capsuleSha256);
    if (!entry) throw makeError('settings-invalid');
    const verified = await verifyDreamSource(task,new environment.TextEncoder().encode(entry.capsule),true);
    assertCurrent(task);
    if (verified.capsuleSha256 !== entry.capsuleSha256) throw makeError('settings-invalid');
    let binary = '';
    for (let offset=0;offset<verified.image.bytes.length;offset+=8192) {
      binary += String.fromCharCode(...verified.image.bytes.subarray(offset,offset+8192));
    }
    const encodeBase64 = environment.btoa || document.defaultView?.btoa || globalThis.btoa;
    if (typeof encodeBase64 !== 'function') throw makeError('settings-unavailable');
    const contours = verified.contours.map(path=>Object.freeze(path.map(point=>Object.freeze([...point]))));
    const settings = Object.freeze({...loaded.settings,schemaVersion:2,wallpaperStrength:75,
      artwork:'data:'+verified.image.mime+';base64,'+encodeBase64(binary),contours:Object.freeze(contours)});
    recordByteLength(settings);
    const binding = await imagesBinding(settings);
    assertCurrent(task);
    const last = verified.paint.steps[verified.paint.steps.length-1];
    const themeState = dreamThemeStyle.validateThemeSnapshot({schemaVersion:2,revision:state.revision,imagesBinding:binding,
      selection:{kind:'imported',profile:verified.paint.profile,capsuleSha256:verified.capsuleSha256,archiveSha256:verified.archiveSha256,
        image:{name:verified.manifest.image,mime:verified.image.mime,bytes:verified.image.bytes.length,sha256:verified.image.sha256,
          width:verified.image.width,height:verified.image.height},
        paint:{rgba:[...last.rgba],backgroundImage:'none',sourceDeclarationCount:verified.paint.declarationCount}}});
    const explicitText = Object.freeze({
      introTitle:explicitDefaults.introTitle || typeof loaded.baseline?.introTitle === 'string',
      introCaption:explicitDefaults.introCaption || typeof loaded.baseline?.introCaption === 'string',
      artworkSubtitle:explicitDefaults.artworkSubtitle || typeof loaded.baseline?.artworkSubtitle === 'string',
    });
    const snapshot = Object.freeze({status:loaded.baseline === undefined ? 'missing' : 'valid',settings,explicitText,themeState,themeReason:''});
    if (new environment.TextEncoder().encode(JSON.stringify(snapshot)).byteLength > 24*1024*1024+4096) throw makeError('settings-invalid');
    assertCurrent(task);return snapshot;
  }

  function loadImportedSnapshot(loaded, explicitDefaults) {
    const {task,promise} = beginOperation('dream-snapshot',10_000);
    Promise.resolve().then(async() => {
      try {
        const snapshot = await projectImportedSnapshot(task,loaded,explicitDefaults,currentThemeState,currentDreamBaseline);
        assertCurrent(task);finish(task,true,snapshot);
      } catch(error) {
        if (!task.settled) finish(task,true,Object.freeze({status:'failure',readOnly:true,reason:error?.reason === 'operation-cancelled'
          ? 'operation-cancelled' : error?.reason === 'operation-timeout' ? 'operation-timeout' : 'settings-invalid'}));
      }
    });
    return promise;
  }

  const THEME_KEY = SETTINGS_KEY === 'images' ? 'themeState' : SETTINGS_KEY + ':themeState';
  const LIBRARY_KEY = SETTINGS_KEY === 'images' ? 'appearancePresets' : SETTINGS_KEY + ':appearancePresets';
  const DREAM_KEY = SETTINGS_KEY === 'images' ? 'dreamThemes' : SETTINGS_KEY + ':dreamThemes';
  const APPROVED_THEME_ID = 'azhou-q-v3';

  async function imagesBinding(record) {
    if (!environment.crypto?.subtle || typeof environment.TextEncoder !== 'function') {
      throw storageError('settings-unavailable', 'digest-unavailable');
    }
    const bytes = new environment.TextEncoder().encode(JSON.stringify(record));
    const digest = await environment.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
  }

  function exactKeys(value, keys) {
    return value && typeof value === 'object' && !Array.isArray(value)
      && Object.keys(value).length === keys.length && keys.every(key => own(value, key));
  }

  function validTransparency(preference) {
    return (exactKeys(preference, ['mode']) && preference.mode === 'follow')
      || (exactKeys(preference, ['mode', 'value']) && preference.mode === 'override'
        && Number.isFinite(preference.value) && preference.value >= 0 && preference.value <= 100);
  }

  async function validateLibrary(task, value) {
    if (value === undefined) return { schemaVersion: 1, revision: 0, entries: [] };
    if (!exactKeys(value, ['schemaVersion', 'revision', 'entries']) || value.schemaVersion !== 1
      || !Number.isSafeInteger(value.revision) || value.revision < 0
      || !Array.isArray(value.entries) || value.entries.length > 8) throw makeError('settings-invalid');
    recordByteLength(value);
    const ids = new Set();
    for (const entry of value.entries) {
      if (!exactKeys(entry, ['id', 'name', 'recipeId', 'appearance', 'surfaceTransparency'])
        || typeof entry.id !== 'string' || !/^[a-zA-Z0-9-]{1,80}$/.test(entry.id) || ids.has(entry.id)
        || typeof entry.name !== 'string' || entry.name !== entry.name.trim() || !entry.name.length
        || entry.name.length > 40 || /[\u0000-\u001f\u007f]/.test(entry.name)
        || entry.recipeId !== APPROVED_THEME_ID || !validTransparency(entry.surfaceTransparency)
        || !exactKeys(entry.appearance, ['artwork', 'contours', 'wallpaperStrength'])) throw makeError('settings-invalid');
      ids.add(entry.id);
      const appearance = entry.appearance;
      if (!normalizeStoredRecord({ schemaVersion: 1, ...appearance }, defaultRecord)
        || !validContours(appearance.contours)) throw makeError('settings-invalid');
      await decodeRecordImage(task, appearance.artwork, 1536, 1024);
    }
    return structuredCloneTheme(value);
  }

  async function stagePreset(task, entry) {
    const candidate = structuredCloneTheme(draftLibrary);
    candidate.entries.push({id: newPresetId(), ...entry});
    return validateLibrary(task, candidate);
  }

  async function readPresetFile(task, file) {
    if (!file || !Number.isSafeInteger(file.size) || file.size <= 0 || file.size > MAX_RECORD_BYTES
      || typeof file.arrayBuffer !== 'function') throw makeError('settings-invalid');
    const buffer = await file.arrayBuffer();
    assertCurrent(task);
    if (Object.prototype.toString.call(buffer) !== '[object ArrayBuffer]'
      || buffer.byteLength <= 0 || buffer.byteLength > MAX_RECORD_BYTES) throw makeError('settings-invalid');
    const Decoder = environment.TextDecoder || document.defaultView?.TextDecoder;
    const value = JSON.parse(new Decoder('utf-8', {fatal: true}).decode(buffer));
    if (!exactKeys(value, ['schema', 'name', 'recipeId', 'appearance', 'surfaceTransparency'])
      || value.schema !== 'azhou-appearance-preset.v1') throw makeError('settings-invalid');
    const {schema, ...entry} = value;
    return stagePreset(task, entry);
  }

  function sameThemeSelection(selection) {
    return selection === undefined ? !currentThemeState : recordEquals(selection, {
      activeThemeId: currentThemeState?.activeThemeId ?? null,
      surfaceTransparency: currentThemeState?.preferencesByTheme?.[APPROVED_THEME_ID] || {mode: 'follow'},
    });
  }

  function newPresetId() {
    if (typeof environment.crypto?.randomUUID === 'function') return environment.crypto.randomUUID();
    if (typeof environment.crypto?.getRandomValues !== 'function') throw makeError('settings-unavailable');
    return Array.from(environment.crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
  }

  function validThemeSelection(selection) {
    return exactKeys(selection, ['activeThemeId', 'surfaceTransparency'])
      && (selection.activeThemeId === APPROVED_THEME_ID || selection.activeThemeId === null)
      && validTransparency(selection.surfaceTransparency);
  }

  async function resolveTheme(record, images) {
    if (record === undefined || record === null) return null;
    if (record.schemaVersion === 2) {
      if (!exactKeys(record,['schemaVersion','revision','imagesBinding','selection','preferencesByTheme','commitId','previousThemeId'])
        || !Number.isSafeInteger(record.revision) || record.revision < 1
        || !exactKeys(record.selection,['kind','capsuleSha256']) || record.selection.kind !== 'imported'
        || typeof record.selection.capsuleSha256 !== 'string' || !/^[a-f0-9]{64}$/.test(record.selection.capsuleSha256)
        || !exactKeys(record.preferencesByTheme,[APPROVED_THEME_ID]) || !validTransparency(record.preferencesByTheme[APPROVED_THEME_ID])
        || ![null,APPROVED_THEME_ID].includes(record.previousThemeId)
        || typeof record.commitId !== 'string' || !/^[a-f0-9]{32}$/.test(record.commitId)
        || typeof record.imagesBinding !== 'string' || !/^[a-f0-9]{64}$/.test(record.imagesBinding)
        || images === undefined || await imagesBinding(images) !== record.imagesBinding) throw makeError('settings-invalid');
      return structuredCloneTheme(record);
    }
    if (!exactKeys(record, ['schemaVersion', 'revision', 'activeThemeId', 'preferencesByTheme', 'imagesBinding'])
      || record.schemaVersion !== 1 || !Number.isSafeInteger(record.revision)
      || record.revision < 1 || (record.activeThemeId !== null && record.activeThemeId !== APPROVED_THEME_ID)
      || !exactKeys(record.preferencesByTheme, [APPROVED_THEME_ID])
      || !validTransparency(record.preferencesByTheme[APPROVED_THEME_ID])
      || typeof record.imagesBinding !== 'string' || !/^[a-f0-9]{64}$/.test(record.imagesBinding)) {
      throw makeError('settings-invalid');
    }
    if (images === undefined || await imagesBinding(images) !== record.imagesBinding) return { ...structuredCloneTheme(record), activeThemeId: null };
    return structuredCloneTheme(record);
  }

  function structuredCloneTheme(value) {
    return value === null ? null : JSON.parse(JSON.stringify(value));
  }

  function recordEquals(left, right) {
    const leftSeen = new Map();
    const rightSeen = new Map();
    const equal = (a, b) => {
      if (Object.is(a, b)) return true;
      if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false;
      if (leftSeen.has(a) || rightSeen.has(b)) return leftSeen.get(a) === b && rightSeen.get(b) === a;
      const tag = Object.prototype.toString.call(a);
      if (tag !== Object.prototype.toString.call(b)) return false;
      leftSeen.set(a, b);
      rightSeen.set(b, a);
      if (tag === '[object Date]') return Object.is(a.getTime(), b.getTime());
      if (tag === '[object RegExp]') return a.source === b.source && a.flags === b.flags;
      if (tag === '[object ArrayBuffer]') {
        if (a.byteLength !== b.byteLength) return false;
        const bytes = new Uint8Array(b);
        return new Uint8Array(a).every((byte, index) => byte === bytes[index]);
      }
      if (ArrayBuffer.isView(a)) return a.byteOffset === b.byteOffset && a.byteLength === b.byteLength && equal(a.buffer, b.buffer);
      if (tag === '[object Map]' || tag === '[object Set]') {
        if (a.size !== b.size) return false;
        const other = b.entries();
        for (const [key, value] of a.entries()) {
          const entry = other.next().value;
          if (!equal(key, entry[0]) || !equal(value, entry[1])) return false;
        }
        return true;
      }
      if (tag !== '[object Object]' && tag !== '[object Array]') return false;
      if (Array.isArray(a) && a.length !== b.length) return false;
      const keys = Object.keys(a);
      return keys.length === Object.keys(b).length && keys.every(key => own(b, key) && equal(a[key], b[key]));
    };
    try { return equal(left, right); }
    catch { return false; }
  }

  function storageFailureFrom(error, operation) {
    const name = error?.name;
    if (name === 'QuotaExceededError') return makeError('settings-quota', 'quota-exceeded');
    if (error?.reason && ['settings-conflict', 'settings-invalid', 'asset-invalid',
      'operation-timeout', 'operation-cancelled', 'settings-quota', 'settings-unavailable'].includes(error.reason)) return error;
    return storageError('settings-unavailable', operation + '-failed');
  }

  function saveInTransaction(task, db, candidate, themeCandidate, libraryCandidate, preserveActive, dreamCandidate) {
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
      let imageReady = false, themeReady = false, libraryReady = false, dreamReady = false;
      const dreamRequest = store.get(DREAM_KEY);
      const libraryRequest = store.get(LIBRARY_KEY);
      const themeRequest = store.get(THEME_KEY);
      const baselineRequest = store.get(SETTINGS_KEY);
      const tryWrite = () => {
        if (!imageReady || !themeReady || !libraryReady || !dreamReady) return;

        if (!isCurrent(task) || ((currentThemeReadOnly || currentImagesReadOnly) && (themeCandidate !== undefined || !preserveActive))) {
          failure = makeError(currentThemeReadOnly || currentImagesReadOnly ? 'settings-blocked' : 'operation-cancelled');
          try { transaction.abort(); } catch {}
          return;
        }
        if (!recordEquals(baselineRequest.result, currentBaseline)
          || !recordEquals(themeRequest.result, currentThemeBaseline)
          || !recordEquals(libraryRequest.result, currentLibraryBaseline)
          || !recordEquals(dreamRequest.result, currentDreamBaseline)) {
          failure = makeError('settings-conflict', 'baseline-changed');
          try { transaction.abort(); } catch {}
          return;
        }
        try {
          if (dreamCandidate !== undefined) {
            const dreamPut = store.put(dreamCandidate, DREAM_KEY);
            dreamPut.onerror = () => { failure = storageFailureFrom(dreamPut.error, 'dream-write'); };
          }
          if (themeCandidate !== undefined) {
            const themePut = store.put(themeCandidate, THEME_KEY);
            themePut.onerror = () => { failure = storageFailureFrom(themePut.error, 'theme-write'); };
          }
          if (libraryCandidate !== undefined) {
            const libraryPut = store.put(libraryCandidate, LIBRARY_KEY);
            libraryPut.onerror = () => { failure = storageFailureFrom(libraryPut.error, 'library-write'); };
          }
          if (!preserveActive) {
            const putRequest = store.put(candidate, SETTINGS_KEY);
            putRequest.onerror = () => { failure = storageFailureFrom(putRequest.error, 'database-write'); };
          }
        } catch (error) {
          failure = storageFailureFrom(error, 'database-write');
          try { transaction.abort(); } catch {}
        }
      };
      dreamRequest.onerror = () => { failure = storageFailureFrom(dreamRequest.error, 'dream-read'); };
      dreamRequest.onsuccess = () => { dreamReady = true; tryWrite(); };
      libraryRequest.onerror = () => { failure = storageFailureFrom(libraryRequest.error, 'library-read'); };
      libraryRequest.onsuccess = () => { libraryReady = true; tryWrite(); };
      baselineRequest.onerror = () => { failure = storageFailureFrom(baselineRequest.error, 'database-read'); };
      themeRequest.onerror = () => { failure = storageFailureFrom(themeRequest.error, 'theme-read'); };
      baselineRequest.onsuccess = () => { imageReady = true; tryWrite(); };
      themeRequest.onsuccess = () => { themeReady = true; tryWrite(); };
      transaction.oncomplete = () => {
        clear();
        task.transactionFinished = true;
        if (task.transaction === transaction) task.transaction = null;
        if (task.settled || !isCurrent(task)) return;
        if (!preserveActive) {
          currentSettings = candidate;
          currentBaseline = candidate;
        }
        if (themeCandidate !== undefined) {
          currentThemeBaseline = themeCandidate;
          currentThemeState = themeCandidate;
        }
        if (libraryCandidate !== undefined) {
          currentLibraryBaseline = libraryCandidate;
          currentLibrary = structuredCloneTheme(libraryCandidate);
        }
        if (dreamCandidate !== undefined) currentDreamBaseline = dreamCandidate;
        loadReason = '';
        finish(task, true, cloneSettings(candidate));
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

  function save(candidate, themeSelection, libraryDraft) {
    if (currentThemeReadOnly || currentImagesReadOnly) return Promise.reject(makeError('settings-blocked'));
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
        const imported = currentThemeState?.selection?.kind === 'imported';
        if (imported && !['artwork','contours','wallpaperStrength'].every(key=>recordEquals(record[key],currentSettings[key]))) {
          throw makeError('settings-blocked');
        }
        const revision = currentThemeState?.revision ?? 0;
        if (imported && revision >= Number.MAX_SAFE_INTEGER) throw makeError('settings-blocked');
        const preserveActive = libraryDraft !== undefined && recordEquals(record, currentSettings) && sameThemeSelection(themeSelection);
        if (themeSelection !== undefined && (!validThemeSelection(themeSelection)
          || (!preserveActive && themeSelection?.activeThemeId !== null && revision >= Number.MAX_SAFE_INTEGER))) throw makeError('settings-invalid');
        const themeCandidate = preserveActive ? undefined : imported
          ? {...structuredCloneTheme(currentThemeState),revision:revision+1,imagesBinding:await imagesBinding(record)} : themeSelection === undefined && !currentThemeState
          ? (currentThemeBaseline === undefined ? undefined : null) : {
            schemaVersion: 1, revision: revision < Number.MAX_SAFE_INTEGER ? revision + 1 : 1,
            activeThemeId: themeSelection?.activeThemeId ?? null,
            preferencesByTheme: themeSelection
              ? { [APPROVED_THEME_ID]: { ...themeSelection.surfaceTransparency } }
              : structuredCloneTheme(currentThemeState.preferencesByTheme),
            imagesBinding: await imagesBinding(record),
          };
        let libraryCandidate;
        if (libraryDraft !== undefined) {
          if (!currentLibrary || currentLibrary.revision >= Number.MAX_SAFE_INTEGER) throw makeError('settings-invalid');
          libraryCandidate = await validateLibrary(task, libraryDraft);
          libraryCandidate.revision = currentLibrary.revision + 1;
          recordByteLength(libraryCandidate);
        }
        if (!preserveActive) await validateRecordImages(task, record);
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        const db = await openDatabase();
        if (!isCurrent(task)) throw makeError('operation-cancelled');
        saveInTransaction(task, db, record, themeCandidate, libraryCandidate, preserveActive);
      } catch (error) {
        if (!task.settled) finish(task, false,
          ['operation-timeout','operation-cancelled','settings-blocked'].includes(error?.reason)
            ? error : storageFailureFrom(error, 'candidate-validation'));
      }
    });
    return promise;
  }

  function dreamDirectoryShape(record) {
    if (record === undefined) return {schemaVersion:1,revision:0,entries:[]};
    if (!exactKeys(record, ['schemaVersion','revision','entries']) || record.schemaVersion !== 1
      || !Number.isSafeInteger(record.revision) || record.revision < 1
      || !Array.isArray(record.entries) || record.entries.length > 8) throw makeError('settings-blocked');
    recordByteLength(record);
    const ids = new Set();
    for (const entry of record.entries) {
      if (!exactKeys(entry, ['capsuleSha256','capsule']) || typeof entry.capsuleSha256 !== 'string'
        || !/^[a-f0-9]{64}$/.test(entry.capsuleSha256) || ids.has(entry.capsuleSha256)
        || typeof entry.capsule !== 'string') throw makeError('settings-blocked');
      ids.add(entry.capsuleSha256);
    }
    return record;
  }

  async function verifyDreamSource(task, bytes, withContours = false) {
    let contours;
    const reader = dreamThemeStyle?.readDreamCapsule;
    if (typeof reader !== 'function' || typeof environment.Blob !== 'function') throw makeError('settings-unavailable');
    const verified = await reader(bytes, {crypto:environment.crypto, decodeImage:async(data,mime) => {
      let image;
      try {
        image = await decode(task, new environment.Blob([data], {type:mime}));
        assertCurrent(task);
        if (withContours) {
          const derived = await normalizeArtwork(task,image,{contoursOnly:true});
          assertCurrent(task);contours = derived.contours;
        }
        return {width:image.naturalWidth,height:image.naturalHeight};
      } finally {
        if (task.image) {
          task.image.onload = null; task.image.onerror = null;
          try { task.image.src = 'data:,'; } catch {}
          task.image = null;
        }
        if (task.objectURL) {
          try { URLObject.revokeObjectURL(task.objectURL); } catch {}
          task.objectURL = null;
        }
      }
    }});
    assertCurrent(task);
    return withContours ? {...verified,contours} : verified;
  }

  async function verifyDreamDirectory(task, record) {
    const directory = dreamDirectoryShape(record);
    const entries = [];
    for (const entry of directory.entries) {
      const verified = await verifyDreamSource(task, new environment.TextEncoder().encode(entry.capsule));
      assertCurrent(task);
      if (verified.capsuleSha256 !== entry.capsuleSha256) throw makeError('settings-invalid');
      entries.push({capsuleSha256:entry.capsuleSha256,name:verified.manifest.name,profile:verified.paint.profile});
    }
    return {status:record === undefined ? 'missing' : 'valid',revision:directory.revision,entries};
  }

  function loadDreamDirectory() {
    if (disposed) return Promise.reject(makeError('operation-cancelled'));
    if (active) return Promise.reject(makeError('operation-busy'));
    const {task,promise} = beginOperation('dream-directory',10_000);
    Promise.resolve().then(async() => {
      try {
        const directory = await verifyDreamDirectory(task,currentDreamBaseline);
        assertCurrent(task); finish(task,true,directory);
      } catch(error) {
        if (error?.reason === 'settings-blocked') finish(task,true,{status:'readonly',entries:[]});
        else finish(task,false,storageFailureFrom(error,'dream-read'));
      }
    });
    return promise;
  }

  function importDreamCapsule(file) {
    if (disposed) return Promise.reject(makeError('operation-cancelled'));
    if (active) return Promise.reject(makeError('operation-busy'));
    if (!currentSettings) return Promise.reject(makeError('settings-unavailable'));
    const {task,promise} = beginOperation('dream-file',10_000);
    let receipt;
    Promise.resolve().then(async() => {
      try {
        const directory = dreamDirectoryShape(currentDreamBaseline);
        if (!file || !Number.isSafeInteger(file.size) || file.size < 1 || file.size > MAX_RECORD_BYTES
          || typeof file.arrayBuffer !== 'function') throw makeError('settings-invalid');
        const input = await file.arrayBuffer();
        assertCurrent(task);
        if (input.byteLength !== file.size || input.byteLength > MAX_RECORD_BYTES) throw makeError('settings-invalid');
        const capsule = new environment.TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(input);
        const verified = await verifyDreamSource(task,new environment.TextEncoder().encode(capsule));
        assertCurrent(task);
        await verifyDreamDirectory(task,currentDreamBaseline);
        assertCurrent(task);
        const existing = directory.entries.find(entry => entry.capsuleSha256 === verified.capsuleSha256);
        receipt = {capsuleSha256:verified.capsuleSha256,name:verified.manifest.name,stored:true,idempotent:!!existing};
        let candidate;
        if (!existing) {
          if (directory.entries.length >= 8 || directory.revision >= Number.MAX_SAFE_INTEGER) throw makeError('settings-invalid');
          candidate = {schemaVersion:1,revision:directory.revision+1,
            entries:[...directory.entries.map(entry=>({...entry})),{capsuleSha256:verified.capsuleSha256,capsule}]};
          recordByteLength(candidate);
        }
        const db = await openDatabase();
        assertCurrent(task);
        saveInTransaction(task,db,currentSettings,undefined,undefined,true,candidate);
      } catch(error) {finish(task,false,error?.reason === 'settings-blocked' ? error : storageFailureFrom(error,'dream-import'));}
    });
    return promise.then(()=>receipt);
  }

  function cancelDreamImport() {
    if (active?.kind !== 'dream-file') return false;
    finish(active,false,makeError('operation-cancelled'));
    return true;
  }

  function themeBaselines() {
    return {images:currentBaseline,theme:currentThemeBaseline,library:currentLibraryBaseline,dream:currentDreamBaseline};
  }

  async function baselineToken(baselines) {
    try {
      const records = Object.values(baselines).map(value => value === undefined ? {missing:true} : {value});
      records.forEach(recordByteLength);
      return await imagesBinding(records);
    } catch { throw makeError('settings-blocked'); }
  }

  function themeApplyToken() {
    if (disposed || !currentSettings) return Promise.reject(makeError('operation-cancelled'));
    return baselineToken(themeBaselines());
  }

  function themeTransaction(task, db, expected, updates, compensation = false) {
    return new Promise((resolve,reject) => {
      let transaction, timer, failure;
      const clear = () => { if (timer !== undefined) clearTimer.call(environment,timer); };
      const rejectWith = error => {
        failure ||= error;
        try { transaction.abort(); } catch {}
      };
      try {
        transaction = db.transaction(STORE_NAME,'readwrite');
        task.transaction = transaction;
        const store = transaction.objectStore(STORE_NAME);
        timer = setTimer.call(environment,()=>rejectWith(makeError('operation-timeout')),5_000);
        const keys = {images:SETTINGS_KEY,theme:THEME_KEY,library:LIBRARY_KEY,dream:DREAM_KEY};
        const requests = {}; let pending=4;
        for (const [name,key] of Object.entries(keys)) {
          const request = requests[name] = store.get(key);
          request.onerror = () => rejectWith(storageFailureFrom(request.error,'theme-read'));
          request.onsuccess = () => {
            if (--pending) return;
            if (!compensation && (!isCurrent(task) || task.failure)) {
              rejectWith(task.failure || makeError('operation-cancelled'));return;
            }
            const compared=compensation?['images','theme']:Object.keys(keys);
            if (!compared.every(name=>recordEquals(requests[name].result,expected[name]))) {
              rejectWith(makeError('settings-conflict'));return;
            }
            try {
              for (const [name,value] of Object.entries(updates)) {
                const write = value === undefined ? store.delete(keys[name]) : store.put(value,keys[name]);
                write.onerror = () => rejectWith(storageFailureFrom(write.error,'theme-write'));
              }
            } catch(error) { rejectWith(storageFailureFrom(error,'theme-write')); }
          };
        }
        transaction.oncomplete = () => {
          clear();if(task.transaction===transaction)task.transaction=null;
          resolve();
        };
        transaction.onerror = () => {failure ||= storageFailureFrom(transaction.error,'theme-write');};
        transaction.onabort = () => {
          clear();if(task.transaction===transaction)task.transaction=null;
          reject(failure || task.failure || makeError('settings-unavailable'));
        };
      } catch(error) {clear();if(task.transaction===transaction)task.transaction=null;reject(storageFailureFrom(error,'theme-write'));}
    });
  }

  function applyDreamTheme(capsuleSha256,options) {
    return applyThemeSelection(capsuleSha256,options);
  }

  function restoreAzhouTheme(options) {
    return applyThemeSelection(null,options);
  }

  function applyThemeSelection(capsuleSha256,options = {}) {
    if (disposed) return Promise.reject(makeError('operation-cancelled'));
    if (active) return Promise.reject(makeError('operation-busy'));
    if (!currentSettings || currentThemeReadOnly || currentImagesReadOnly
      || !dreamThemeStyle || typeof environment.AbortController !== 'function' || typeof options.activate !== 'function'
      || typeof options.expectedToken !== 'string' || !/^[a-f0-9]{64}$/.test(options.expectedToken)
      || capsuleSha256 !== null && (typeof capsuleSha256 !== 'string' || !/^[a-f0-9]{64}$/.test(capsuleSha256))) {
      return Promise.reject(makeError('settings-blocked'));
    }
    const expected = themeBaselines();
    const savedSettings = cloneSettings(currentSettings);
    const previous = currentThemeState;
    const {task,promise} = beginOperation('theme-apply',10_000);
    const applyAbort = task.applyAbort = new environment.AbortController();
    const cancel = () => finish(task,false,makeError('operation-cancelled'));
    options.signal?.addEventListener('abort',cancel,{once:true});
    if (options.signal?.aborted) cancel();
    Promise.resolve().then(async() => {
      let activation, committed = false, candidate, images, db, compensationFailure;
      try {
        assertCurrent(task);
        if (await baselineToken(expected) !== options.expectedToken) throw makeError('settings-conflict');
        assertCurrent(task);
        images = expected.images === undefined ? savedSettings : expected.images;
        const binding = await imagesBinding(images);assertCurrent(task);
        const revision = (previous?.revision ?? 0)+1;
        if (!Number.isSafeInteger(revision) || revision >= Number.MAX_SAFE_INTEGER) throw makeError('settings-invalid');
        const preferencesByTheme = previous?.preferencesByTheme || {[APPROVED_THEME_ID]:{mode:'follow'}};
        let snapshot;
        if (capsuleSha256 !== null) {
          const random = environment.crypto.getRandomValues(new Uint8Array(16));
          candidate = {schemaVersion:2,revision,imagesBinding:binding,selection:{kind:'imported',capsuleSha256},
            preferencesByTheme:structuredCloneTheme(preferencesByTheme),
            previousThemeId:previous?.selection?.kind === 'imported' ? previous.previousThemeId : previous?.activeThemeId ?? null,
            commitId:Array.from(random,byte=>byte.toString(16).padStart(2,'0')).join('')};
          snapshot = await projectImportedSnapshot(task,{settings:savedSettings,baseline:images},{},candidate,expected.dream);
        } else {
          if (previous?.selection?.kind !== 'imported') throw makeError('settings-blocked');
          candidate = {schemaVersion:1,revision,imagesBinding:binding,activeThemeId:previous.previousThemeId,
            preferencesByTheme:structuredCloneTheme(preferencesByTheme)};
          snapshot = {status:'valid',settings:savedSettings,themeState:candidate.activeThemeId ? candidate : null};
        }
        assertCurrent(task);recordByteLength(candidate);
        task.deferSettlement = true;
        activation = await options.activate(snapshot,{signal:applyAbort.signal});
        if (!activation?.applied || typeof activation.transaction?.current !== 'function'
          || typeof activation.transaction?.finalize !== 'function' || typeof activation.transaction?.rollback !== 'function') {
          throw makeError('settings-unavailable');
        }
        assertCurrent(task);
        if (!activation.transaction.current()) throw makeError('operation-cancelled');
        db = await openDatabase();assertCurrent(task);
        const updates = expected.images === undefined ? {images,theme:candidate} : {theme:candidate};
        await themeTransaction(task,db,expected,updates);
        committed = true;
        assertCurrent(task);
        if (!activation.transaction.current() || activation.transaction.finalize() !== true) throw makeError('operation-cancelled');
        currentBaseline = images;currentSettings = savedSettings;
        currentThemeBaseline = candidate;currentThemeState = candidate;currentThemeReason = '';
        task.deferSettlement = false;
        finish(task,true,{applied:true,themeState:snapshot.themeState});
      } catch(error) {
        try {activation?.transaction?.rollback();} catch {}
        if (committed) {
          // Restore only this exact commit. A newer writer's values are never compensated away.
          try {
            let restoredTheme=expected.theme;
            if (expected.images !== undefined && (previous || expected.theme == null)) {
              restoredTheme=previous?{...structuredCloneTheme(previous),revision:candidate.revision+1}
                :{schemaVersion:1,revision:candidate.revision+1,imagesBinding:candidate.imagesBinding,
                  activeThemeId:null,preferencesByTheme:{[APPROVED_THEME_ID]:{mode:'follow'}}};
              if (restoredTheme.schemaVersion===2) {
                restoredTheme.commitId=Array.from(environment.crypto.getRandomValues(new Uint8Array(16)),byte=>byte.toString(16).padStart(2,'0')).join('');
              }
            }
            await themeTransaction(task,db,{...expected,images,theme:candidate},
              {theme:restoredTheme,...(expected.images===undefined?{images:undefined}:{})},true);
            currentBaseline=expected.images;currentThemeBaseline=restoredTheme;
            currentThemeState=previous?structuredCloneTheme(restoredTheme):null;
          } catch(compensationError) {
            compensationFailure = makeError(compensationError?.reason === 'settings-conflict' ? 'settings-conflict' : 'settings-unavailable');
          }
        }
        task.deferSettlement = false;
        if (!task.settled) finish(task,false,compensationFailure || task.failure || storageFailureFrom(error,'theme-apply'));
      } finally {
        options.signal?.removeEventListener('abort',cancel);
        if (disposed) {
          try {(database || db)?.close();} catch {}
          database=null;
        }
      }
    });
    return promise;
  }

  function appearanceDraft(value) {
    return { artwork: value.artwork, contours: cloneSettings(value).contours };
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

  function displayImportError(error) {
    if (error?.reason === 'operation-cancelled') return null;
    if (error?.reason === 'operation-busy') return 'settings.importError.busy';
    if (error?.reason === 'operation-timeout') {
      return error?.causeCode === 'decode-timeout'
        ? 'settings.importError.decodeTimeout' : 'settings.importError.timeout';
    }
    const keys = {
      'file-empty': 'settings.importError.fileEmpty',
      'file-too-large': 'settings.importError.fileTooLarge',
      'image-too-large': 'settings.importError.imageTooLarge',
      'mime-mismatch': 'settings.importError.mimeMismatch',
      'unsupported-type': 'settings.importError.unsupported',
      'decode-failed': 'settings.importError.decode',
      'invalid-dimensions': 'settings.importError.dimensions',
      'canvas-unavailable': 'settings.importError.canvas',
      'pixel-data-unavailable': 'settings.importError.pixelsUnavailable',
      'pixel-data-invalid': 'settings.importError.pixelsInvalid',
      'contours-empty': 'settings.importError.contoursEmpty',
      'contours-too-many-points': 'settings.importError.contoursComplex',
      'png-encode-failed': 'settings.importError.pngEncode',
      'output-too-large': 'settings.importError.outputTooLarge',
      'environment-unavailable': 'settings.importError.environment',
      'image-processing-failed': 'settings.importError.processing',
    };
    return keys[error?.causeCode] || 'settings.importError.processing';
  }

  function panelStatusParams(value) {
    const params = { ...(value?.params || {}) };
    if (value?.fieldRole) {
      params.field = translate(value.fieldRole === 'avatar' ? 'settings.avatar.label' : 'settings.artwork.label');
    }
    return params;
  }

  function setPanelStatus(key, role = 'status', params = {}) {
    if (!panelControls?.status) return;
    panelStatus = key ? { key, role, params: { ...params }, fieldRole: params.fieldRole || '' } : null;
    panelControls.status.textContent = panelStatus
      ? translate(panelStatus.key, panelStatusParams(panelStatus)) : '';
    panelControls.status.setAttribute('role', panelStatus?.role || 'status');
    panelControls.status.setAttribute('aria-live', panelStatus?.role === 'alert' ? 'assertive' : 'polite');
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
    const { heading, close, categoryNav, labels, ariaLabels, buttons, strengthLabel, status } = panelControls;
    heading.textContent = translate('settings.title');
    close?.setAttribute('aria-label', translate('settings.close'));
    categoryNav.setAttribute('aria-label', translate('settings.categories.label'));
    for (const [key, label] of Object.entries(labels)) {
      label.element.textContent = translate(key, label.params);
    }
    for (const item of ariaLabels) item.control.setAttribute('aria-label', translate(item.key, item.params));
    for (const [key, button] of Object.entries(buttons)) button.textContent = translate(key);
    if (panelControls.saveButton) {
      panelControls.saveButton.textContent = translate(panelCommit
        ? panelApplying ? 'settings.button.applyingBackground' : 'settings.button.retryApply'
        : 'settings.button.save');
    }
    if (panelControls.cancelButton) {
      panelControls.cancelButton.textContent = translate(panelCommit ? 'settings.button.close' : 'settings.button.cancel');
    }
    strengthLabel.textContent = translate('settings.wallpaperStrength.label', { min: 0, max: 75 });
    updateStrengthValue(panelControls.strength.value);
    updateThemeReadout();
    status.textContent = panelStatus ? translate(panelStatus.key, panelStatusParams(panelStatus)) : '';
    status.setAttribute('role', panelStatus?.role || 'status');
    status.setAttribute('aria-live', panelStatus?.role === 'alert' ? 'assertive' : 'polite');
    panelControls.workspacePreview.setAttribute('aria-label', translate('settings.preview.background.label'));
    panelControls.workspacePreviewCaption.textContent = panelControls.workspacePreviewHasImage
      ? translate('settings.preview.background.caption') : translate('settings.preview.background.empty');
    refreshAppearance();
  }

  function currentAppearance() {
    try {
      const value = environment?.getAppearance?.();
      return value && typeof value === 'object' ? value : {};
    } catch { return {}; }
  }

  function currentSurface() {
    const appearance = currentAppearance();
    const surface = appearance.colors?.surface;
    const color = typeof surface === 'string' ? surface.trim() : '';
    const css = document.defaultView?.CSS;
    if (color && color.length <= 100 && !/[;{}]/.test(color) && !/\bvar\s*\(/i.test(color)
      && !/^(?:currentcolor|inherit|initial|unset|revert(?:-layer)?)$/i.test(color)) {
      try {
        if (typeof css?.supports === 'function' && css.supports('color', color)) return color;
      } catch {}
    }
    return appearance.theme === 'light' ? '#ffffff' : '#10121c';
  }

  function refreshAppearance() {
    if (!panelControls || disposed) return false;
    for (const item of panelControls.readouts) {
      try { item.element.textContent = item.value(); }
      catch { item.element.textContent = translate('settings.unknown'); }
    }
    const surface = currentSurface();
    const strength = Number(draft?.wallpaperStrength ?? panelControls.strength.value);
    const hasVisibleImage = Boolean(draft?.artwork) && strength > 0;
    const view = document.defaultView;
    const width = Number(view?.innerWidth) || 0;
    const height = Number(view?.innerHeight) || 0;
    const cropPosition = width > 0 && height > 0 && width / height <= 6 / 5
      ? '88% center' : '60% center';
    panelControls.workspacePreview.hidden = currentThemeState?.selection?.kind === 'imported';
    panelControls.workspacePreview.style.setProperty('display',panelControls.workspacePreview.hidden?'none':'grid');
    panelControls.workspacePreview.style.setProperty('background-color', surface);
    panelControls.workspacePreviewSurface.style.setProperty('background-color', surface);
    panelControls.workspacePreviewImage.hidden = !draft?.artwork || strength === 0;
    panelControls.workspacePreviewImage.style.setProperty('display', hasVisibleImage ? 'block' : 'none');
    panelControls.workspacePreviewImage.style.setProperty('object-position', cropPosition);
    panelControls.workspacePreviewWash.style.setProperty('background-image', hasVisibleImage
      ? (draftTheme ? 'linear-gradient(color-mix(in srgb, ' + surface + ' ' + (draftTheme.surfaceTransparency.mode === 'follow' ? 70 : 100 - draftTheme.surfaceTransparency.value) + '%, transparent), color-mix(in srgb, ' + surface + ' ' + (draftTheme.surfaceTransparency.mode === 'follow' ? 70 : 100 - draftTheme.surfaceTransparency.value) + '%, transparent))' : workspaceWashGradient(strength, surface)) : 'none');
    panelControls.workspacePreviewWash.style.setProperty('display', hasVisibleImage ? 'block' : 'none');
    return true;
  }

  function handleLocaleChange() {
    if (disposed) return;
    refreshLocalizedDefaults();
    updatePanelText();
  }

  function updatePanelBusy() {
    if (!panelControls) return;
    const busy = Boolean(active || panelApplying);
    for (const control of panelControls.controls) {
      const isSave = control === panelControls.saveButton;
      const isCancel = control === panelControls.cancelButton;
      control.disabled = (Boolean(active) && !(isCancel && ['preset-file','dream-file','dream-directory'].includes(active.kind)))
        || ([panelControls.dreamImport,panelControls.dreamImportButton].includes(control) && (!dreamThemeStyle || dreamDirectoryView.status === 'readonly' || dreamDirectoryView.entries.length >= 8))
        || (control === panelControls.dreamList && !dreamDirectoryView.entries.length)
        || (isSave && (currentThemeReadOnly || currentImagesReadOnly))
        || (control === panelControls.dreamApply && (!panelCallbacks?.onThemeApply || !dreamDirectoryView.entries.length || currentThemeReadOnly || currentImagesReadOnly))
        || (control === panelControls.dreamRestore && (!panelCallbacks?.onThemeApply || currentThemeState?.selection?.kind !== 'imported'))
        || (currentThemeState?.selection?.kind === 'imported' && (
          [panelControls.strength,panelControls.themeChoice,panelControls.themeMode,panelControls.themeTransparency,
            panelControls.presetAdd,panelControls.presetLoad,panelControls.buttons['settings.button.restore']].includes(control)
          || control.getAttribute?.('data-agent-skin-image-action') === 'artwork'
          || control.getAttribute?.('data-agent-skin-image-input') === 'artwork'
          || control.hasAttribute?.('data-agent-skin-preview-animation')))
        || (panelApplying && !isCancel)
        || (Boolean(panelCommit) && !panelApplying && !isSave && !isCancel)
        || ([panelControls.presetName, panelControls.presetAdd, panelControls.presetList, panelControls.presetLoad, panelControls.presetImport, panelControls.presetExport].includes(control) && !draftLibrary)
        || (control === panelControls.presetAdd && (!draftTheme || draftLibrary?.entries.length >= 8))
        || (control === panelControls.presetImport && draftLibrary?.entries.length >= 8)
        || ([panelControls.presetLoad, panelControls.presetExport].includes(control) && !draftLibrary?.entries.length)
        || (control === panelControls.themeMode && !draftTheme)
        || (control === panelControls.themeTransparency && (!draftTheme || draftTheme.surfaceTransparency.mode !== 'override'));
      if (control.style && typeof control.style.setProperty === 'function') {
        control.style.setProperty('opacity', control.disabled ? '.58' : '1');
        control.style.setProperty('cursor', busy && control.disabled ? 'wait'
          : control.tagName === 'BUTTON' ? 'pointer' : 'auto');
      }
    }
    if (active?.kind === 'import') setPanelStatus('settings.status.importing');
    else if (active?.kind === 'save') setPanelStatus('settings.status.saving');
    else if (panelApplying) setPanelStatus('settings.status.applyingBackground');
    updatePanelText();
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

  function workspaceWashGradient(strength, surface) {
    const washStops = [24, 18, 12, 16, 30, 65, 70];
    const washPositions = ['0%', '22%', '36%', '62%', '73%', '87%', '100%'];
    const washScale = Math.max(0, Math.min(75, Number(strength) || 0)) / 42;
    const base = typeof surface === 'string' && surface.trim() ? surface.trim() : '#202024';
    return 'linear-gradient(90deg,' + washStops.map((opacity, index) => {
      const visible = Math.min(100, Math.round(opacity * washScale));
      return 'color-mix(in srgb, ' + base + ' ' + (100 - visible) + '%, transparent) '
        + washPositions[index];
    }).join(',') + ')';
  }

  function containPanelTab(event) {
    if (!panelOpen || event.key !== 'Tab' || !dialog) return;
    syncPanelScrollPadding();
    const preview = dialog.querySelector('[data-agent-skin-settings-preview]');
    const scope = preview || dialog;
    const controls = Array.from(scope.querySelectorAll(
      'a[href],button,input,select,textarea,iframe,[tabindex],summary',
    )).filter(element => {
      if (element.tabIndex < 0 || element.disabled || element.hidden || element.type === 'hidden') return false;
      try {
        const style = document.defaultView?.getComputedStyle?.(element);
        return style?.display !== 'none' && style?.visibility !== 'hidden'
          && (!element.getClientRects || element.getClientRects().length > 0);
      } catch { return false; }
    });
    if (!controls.length) {
      event.preventDefault();
      return;
    }
    const activeIndex = controls.indexOf(document.activeElement);
    if (activeIndex < 0) {
      event.preventDefault();
      controls[event.shiftKey ? controls.length - 1 : 0].focus?.();
    } else if (event.shiftKey && activeIndex === 0) {
      event.preventDefault();
      controls.at(-1).focus?.();
    } else if (!event.shiftKey && activeIndex === controls.length - 1) {
      event.preventDefault();
      controls[0].focus?.();
    }
  }

  function updateDreamList(preferred) {
    if (!panelControls) return;
    const list = panelControls.dreamList;
    const selected = preferred || list.value;
    while (list.firstChild) list.removeChild(list.firstChild);
    for (const entry of dreamDirectoryView.entries) {
      const option = document.createElement('option'); option.value = entry.capsuleSha256;
      option.textContent = entry.name; list.appendChild(option);
    }
    list.value = dreamDirectoryView.entries.some(entry=>entry.capsuleSha256 === selected)
      ? selected : dreamDirectoryView.entries[0]?.capsuleSha256 || '';
  }

  function updatePresetList() {
    if (!panelControls) return;
    const list = panelControls.presetList;
    const selected = list.value;
    while (list.firstChild) list.removeChild(list.firstChild);
    for (const entry of draftLibrary?.entries || []) {
      const option = document.createElement('option');
      option.value = entry.id;
      option.textContent = entry.name;
      list.appendChild(option);
    }
    list.value = draftLibrary?.entries.some(entry => entry.id === selected)
      ? selected : draftLibrary?.entries[0]?.id || '';
  }

  function updatePanelFields() {
    if (!panelControls || !draft) return;
    for (const [key, control] of Object.entries(panelControls.fields)) control.value = draft[key] ?? '';
    updatePresetList();
    panelControls.themeChoice.value = draftTheme?.activeThemeId || '';
    panelControls.themeMode.value = draftTheme?.surfaceTransparency.mode || 'follow';
    panelControls.themeTransparency.value = String(draftTheme?.surfaceTransparency.value ?? 30);
    panelControls.strength.value = String(draft.wallpaperStrength);
    updateStrengthValue(draft.wallpaperStrength);
    panelControls.workspacePreviewHasImage = Boolean(draft.artwork);
    panelControls.workspacePreviewCaption.textContent = draft.artwork
      ? translate('settings.preview.background.caption') : translate('settings.preview.background.empty');
    for (const [role, preview] of Object.entries(panelControls.previews)) {
      const value = draft[role];
      preview.hidden = !value;
      preview.style.setProperty('display', value ? 'block' : 'none');
      if (value) preview.src = value;
      else preview.removeAttribute('src');
    }
    updateThemeReadout();
    refreshAppearance();
  }

  function updateThemeReadout() {
    if (!panelControls) return;
    const preference = draftTheme?.surfaceTransparency;
    const text = preference?.mode === 'override' ? preference.value + '%' : translate('settings.themeControl.follow');
    panelControls.themeTransparencyValue.textContent = text;
    panelControls.themeTransparency.setAttribute('aria-valuetext', text);
    panelControls.themeTransparencyReason.textContent = !draftTheme
      ? translate('settings.themeControl.chooseFirst')
      : preference.mode === 'follow' ? translate('settings.themeControl.followReason') : '';
    panelControls.themeStrengthNote.hidden = !draftTheme;
  }

  function updateStrengthValue(value) {
    if (!panelControls) return;
    const isClosed = Number(value) === 0;
    const text = isClosed ? translate('settings.off') : String(value);
    panelControls.strengthValue.textContent = text;
    if (isClosed) panelControls.strength.setAttribute('aria-valuetext', text);
    else panelControls.strength.removeAttribute('aria-valuetext');
  }

  async function applyCommittedSettings(commit) {
    if (!panelOpen || panelCommit !== commit || panelApplying) return false;
    const panelAtStart = panelGeneration;
    panelApplying = true;
    commit.failed = false;
    updatePanelBusy();
    try {
      const result = await commit.onApply(cloneSettings(commit.saved));
      if (!panelOpen || panelAtStart !== panelGeneration || panelCommit !== commit) return false;
      if (result?.applied !== true && result?.reason !== 'disabled') throw new Error('background-apply-failed');
      panelApplying = false;
      if (panelPresentation === 'embedded') settleEmbeddedSave(commit.saved);
      else closePanel('saved');
      return true;
    } catch {
      if (!panelOpen || panelAtStart !== panelGeneration || panelCommit !== commit) return false;
      panelApplying = false;
      commit.failed = true;
      setPanelStatus('settings.error.backgroundApply', 'alert');
      updatePanelBusy();
      return false;
    } finally {
      if (panelOpen && panelCommit === commit && panelApplying) {
        panelApplying = false;
        updatePanelBusy();
      }
    }
  }

  function buildSettingsPanel() {
    if (dialog) return true;
    if (!document || typeof document.createElement !== 'function' || !document.body) return false;
    dialog = document.createElement('dialog');
    dialog.setAttribute('aria-labelledby', 'agent-skin-settings-title');
    dialog.setAttribute('data-agent-skin-settings', '');
    // Keep keyboard-focused fields above the sticky action footer as it wraps on narrow screens.
    dialog.style.cssText = 'box-sizing:border-box;color-scheme:inherit;width:min(780px,calc(100vw - 24px));max-height:calc(100vh - 24px);overflow:auto;scroll-padding-bottom:120px;padding:0;border:1px solid var(--agent-skin-border,CanvasText);border-radius:18px;background:var(--agent-skin-surface,Canvas);color:var(--agent-skin-text,CanvasText);box-shadow:0 24px 90px #0006;font:14px/1.5 system-ui,sans-serif';
    dialog.style.setProperty('color-scheme', 'inherit');
    dialog.style.setProperty('border-color', 'var(--agent-skin-border, CanvasText)');
    dialog.style.setProperty('background-color', 'var(--agent-skin-surface, Canvas)');
    dialog.style.setProperty('color', 'var(--agent-skin-text, CanvasText)');
    if (panelPresentation === 'embedded') {
      // Inline section presentation: flow with the host container instead of
      // the modal sheet viewport clamps.
      dialog.style.setProperty('width', '100%');
      dialog.style.setProperty('max-height', 'none');
      dialog.style.setProperty('box-shadow', 'none');
    }

    const focusRules = '[data-agent-skin-settings] :is(button,input,textarea,select,summary,[tabindex]):focus-visible{outline:3px solid #fff;outline-offset:2px;box-shadow:0 0 0 5px #111}@media(forced-colors:active){[data-agent-skin-settings] :is(button,input,textarea,select,summary,[tabindex]):focus-visible{outline-color:Highlight;box-shadow:none}}';
    try {
      const Sheet = document.defaultView?.CSSStyleSheet;
      if (typeof Sheet === 'function' && 'adoptedStyleSheets' in document) {
        panelFocusSheet = new Sheet();
        panelFocusSheet.replaceSync(focusRules);
        document.adoptedStyleSheets = [...document.adoptedStyleSheets, panelFocusSheet];
      }
    } catch { panelFocusSheet = null; }
    if (!panelFocusSheet) {
      const focusStyle = document.createElement('style');
      focusStyle.textContent = focusRules;
      dialog.appendChild(focusStyle);
    }
    const content = document.createElement('section');
    content.style.cssText = 'padding:20px clamp(16px,3vw,26px) 0';
    const header = document.createElement('header');
    header.style.cssText = 'display:flex;align-items:center;gap:12px;min-width:0';
    const heading = document.createElement('h2');
    heading.id = 'agent-skin-settings-title';
    heading.textContent = translate('settings.title');
    heading.style.cssText = 'min-width:0;flex:1;margin:0;font-size:20px';
    const titleGroup = document.createElement('div');
    titleGroup.style.cssText = 'min-width:0;flex:1';
    const runningVersion = document.createElement('p');
    runningVersion.setAttribute('data-agent-skin-running-version', '');
    runningVersion.style.cssText = 'margin:4px 0 0;font-size:12px;overflow-wrap:anywhere;color:var(--agent-skin-muted,CanvasText)';
    titleGroup.append(heading, runningVersion);
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
    header.appendChild(titleGroup);
    content.appendChild(header);

    const categoryNav = document.createElement('nav');
    categoryNav.setAttribute('role', 'tablist');
    categoryNav.setAttribute('aria-label', translate('settings.categories.label'));
    categoryNav.setAttribute('aria-orientation', 'horizontal');
    categoryNav.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-top:20px;padding-bottom:14px;border-bottom:1px solid var(--agent-skin-border,CanvasText)';
    content.appendChild(categoryNav);

    const fields = Object.create(null);
    const labels = Object.create(null);
    const ariaLabels = [];
    const controls = [];
    const readouts = [];
    readouts.push({ element: runningVersion, value: () => translate('settings.runningVersion', {
      version: themeConfig?.identity?.version && themeConfig?.identity?.build
        ? themeConfig.identity.version + ' · build ' + themeConfig.identity.build : translate('settings.unknown'),
    }) });
    const previews = {};
    const buttons = Object.create(null);
    const tabs = [];
    const categoryPanels = Object.create(null);
    let section = content;
    let workspacePreviewHasImage = false;
    const addText = (key, parent = section, tag = 'p') => {
      const element = document.createElement(tag);
      element.style.cssText = 'margin:8px 0;overflow-wrap:anywhere;color:var(--agent-skin-muted,CanvasText)';
      labels[key] = { element, params: {} };
      element.textContent = translate(key);
      parent.appendChild(element);
      return element;
    };
    const addDisclosure = (name, key, parent) => {
      const details = document.createElement('details');
      details.setAttribute('data-agent-skin-disclosure', name);
      details.style.cssText = 'margin-top:14px;min-width:0;overflow-wrap:anywhere';
      addText(key, details, 'summary').style.cssText = 'cursor:pointer;overflow-wrap:anywhere';
      parent.appendChild(details);
      return details;
    };
    const selectCategory = name => {
      for (const tab of tabs) {
        const selected = tab.getAttribute('data-agent-skin-settings-tab') === name;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        styleButton(tab, selected);
      }
      for (const [key, panel] of Object.entries(categoryPanels)) panel.hidden = key !== name;
    };
    const addSection = (name, note = '') => {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.id = 'agent-skin-settings-tab-' + name;
      tab.setAttribute('role', 'tab');
      tab.setAttribute('data-agent-skin-settings-tab', name);
      tab.setAttribute('aria-controls', 'agent-skin-settings-panel-' + name);
      tab.setAttribute('aria-selected', 'false');
      tab.tabIndex = -1;
      tab.textContent = translate('settings.section.' + name);
      styleButton(tab);
      tab.style.setProperty('flex', '1 1 130px');
      tab.addEventListener('click', () => selectCategory(name));
      tab.addEventListener('keydown', event => {
        const index = tabs.indexOf(tab);
        let nextIndex = -1;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (index + 1) % tabs.length;
        else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (index + tabs.length - 1) % tabs.length;
        else if (event.key === 'Home') nextIndex = 0;
        else if (event.key === 'End') nextIndex = tabs.length - 1;
        if (nextIndex < 0) return;
        event.preventDefault?.();
        tabs[nextIndex].focus?.();
        selectCategory(tabs[nextIndex].getAttribute('data-agent-skin-settings-tab'));
      });
      categoryNav.appendChild(tab);
      tabs.push(tab);
      controls.push(tab);
      buttons['settings.section.' + name] = tab;

      const panel = document.createElement('section');
      panel.id = 'agent-skin-settings-panel-' + name;
      panel.setAttribute('role', 'tabpanel');
      panel.setAttribute('data-agent-skin-settings-section', name);
      panel.setAttribute('aria-labelledby', 'agent-skin-settings-tab-' + name);
      panel.tabIndex = 0;
      panel.hidden = true;
      panel.style.cssText = 'min-width:0;padding:20px 0 4px';
      content.appendChild(panel);
      categoryPanels[name] = panel;
      section = panel;
      if (note) addText(note, panel);
      return panel;
    };
    const addInfo = (key, labelKey, value) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;flex-wrap:wrap;justify-content:space-between;gap:3px 20px;margin-top:12px;min-width:0';
      const label = addText(labelKey, row, 'span');
      label.style.cssText += ';flex:1 1 160px;margin:0';
      const element = document.createElement('span');
      element.style.cssText = 'min-width:0;flex:1 1 200px;overflow-wrap:anywhere';
      element.setAttribute('data-agent-skin-setting-value', key);
      readouts.push({ element, value });
      row.appendChild(element);
      section.appendChild(row);
    };
    const localized = values => values?.[localization?.locale || 'zh-CN'] || translate('settings.unknown');
    const inherited = key => {
      try { return environment.getAppearance?.()?.[key]; } catch { return undefined; }
    };
    const addRow = (key, control, params = {}) => {
      const wrapper = document.createElement('label');
      wrapper.style.cssText = 'display:grid;gap:5px;margin-top:14px';
      const label = document.createElement('span');
      label.textContent = translate(key, params);
      label.style.cssText = 'overflow-wrap:anywhere';
      labels[key] = { element: label, params };
      wrapper.append(label, control);
      section.appendChild(wrapper);
      controls.push(control);
      return control;
    };

    const addFile = (role, actionKey) => {
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
          if (panelOpen && panelAtStart === panelGeneration) {
            const key = displayImportError(error);
            if (key) setPanelStatus(key, 'alert', { fieldRole: role });
            else setPanelStatus('');
          }
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
      button.style.setProperty('display', 'block');
      button.style.setProperty('margin-top', '14px');
      button.addEventListener('click', () => {
        if (panelOpen && !active) input.click?.();
      });
      section.appendChild(button);
      controls.push(button);
      controls.push(input);
      section.appendChild(input);

      let preview = previews[role];
      if (!preview) {
        preview = document.createElement('img');
        preview.setAttribute('alt', '');
        preview.setAttribute('data-agent-skin-image-preview', role);
        previews[role] = preview;
        if (role === 'avatar') {
          preview.style.cssText = 'display:block;width:72px;height:72px;object-fit:cover;border-radius:16px;margin-top:10px';
          section.appendChild(preview);
        }
      }
      buttons[actionKey] = button;
      return button;
    };

    const workspacePanel = addSection('workspace');
    const workspacePreview = document.createElement('figure');
    workspacePreview.setAttribute('role', 'img');
    workspacePreview.setAttribute('data-agent-skin-workspace-preview', '');
    workspacePreview.setAttribute('aria-label', translate('settings.preview.background.label'));
    workspacePreview.style.cssText = 'box-sizing:border-box;display:grid;grid-template-rows:minmax(0,1fr) auto;min-height:112px;height:clamp(112px,28vh,240px);max-height:240px;overflow:hidden;margin:18px 0 14px;border:1px solid var(--agent-skin-border,CanvasText);border-radius:12px;background-color:var(--agent-skin-surface,Canvas)';
    ariaLabels.push({ control: workspacePreview, key: 'settings.preview.background.label', params: {} });
    const backgroundImage = document.createElement('img');
    backgroundImage.setAttribute('alt', '');
    backgroundImage.setAttribute('aria-hidden', 'true');
    backgroundImage.setAttribute('data-agent-skin-image-preview', 'artwork');
    backgroundImage.setAttribute('data-agent-skin-workspace-preview-image', '');
    backgroundImage.hidden = true;
    backgroundImage.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover';
    previews.artwork = backgroundImage;
    const workspacePreviewSurface = document.createElement('div');
    workspacePreviewSurface.style.cssText = 'position:relative;min-height:0;overflow:hidden;background-color:var(--agent-skin-surface,Canvas)';
    const backgroundWash = document.createElement('div');
    backgroundWash.setAttribute('aria-hidden', 'true');
    backgroundWash.setAttribute('data-agent-skin-workspace-preview-wash', '');
    backgroundWash.style.cssText = 'position:absolute;inset:0;pointer-events:none';
    workspacePreviewSurface.append(backgroundImage, backgroundWash);
    const workspacePreviewCaption = document.createElement('figcaption');
    workspacePreviewCaption.textContent = translate('settings.preview.background.empty');
    workspacePreviewCaption.style.cssText = 'padding:7px 10px;overflow-wrap:anywhere;color:var(--agent-skin-muted,CanvasText)';
    workspacePreview.append(workspacePreviewSurface, workspacePreviewCaption);
    workspacePanel.appendChild(workspacePreview);
    addFile('artwork', 'settings.button.chooseBackground');

    const strength = document.createElement('input');
    strength.type = 'range';
    strength.id = 'agent-skin-settings-wallpaper-strength';
    strength.min = '0';
    strength.max = '75';
    strength.step = '1';
    styleInput(strength);
    const strengthValue = document.createElement('output');
    strengthValue.setAttribute('data-agent-skin-wallpaper-strength-value', '');
    strengthValue.setAttribute('aria-hidden', 'true');
    strengthValue.style.cssText = 'min-width:3ch;text-align:right';
    const strengthLabel = document.createElement('span');
    strengthLabel.textContent = translate('settings.wallpaperStrength.label', { min: 0, max: 75 });
    strengthLabel.style.cssText = 'overflow-wrap:anywhere';
    const strengthRow = document.createElement('label');
    strengthRow.htmlFor = strength.id;
    strengthRow.style.cssText = 'display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 12px;align-items:center;margin-top:14px';
    strengthRow.append(strengthLabel, strengthValue, strength);
    strength.addEventListener('input', () => {
      if (!draft) return;
      draft.wallpaperStrength = Number(strength.value);
      updateStrengthValue(draft.wallpaperStrength);
      refreshAppearance();
    });
    workspacePanel.appendChild(strengthRow);
    controls.push(strength);

    const themeChoice = document.createElement('select');
    themeChoice.setAttribute('data-agent-skin-theme-choice', '');
    themeChoice.setAttribute('aria-label', translate('settings.themeControl.choice'));
    for (const [value, label] of [['', 'legacy'], [APPROVED_THEME_ID, 'azhou']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = translate('settings.themeControl.' + label);
      labels['settings.themeControl.' + label] = {element: option};
      themeChoice.appendChild(option);
    }
    const themeMode = document.createElement('select');
    themeMode.setAttribute('data-agent-skin-theme-alpha-mode', '');
    themeMode.setAttribute('aria-label', translate('settings.themeControl.mode'));
    for (const [value, label] of [['follow', 'follow'], ['override', 'override']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = translate('settings.themeControl.' + label);
      labels['settings.themeControl.' + label] = {element: option};
      themeMode.appendChild(option);
    }
    const themeTransparency = document.createElement('input');
    themeTransparency.type = 'range'; themeTransparency.min = '0'; themeTransparency.max = '100';
    themeTransparency.step = '1';
    themeTransparency.setAttribute('data-agent-skin-theme-transparency', '');
    themeTransparency.setAttribute('aria-label', translate('settings.themeControl.transparency'));
    themeChoice.addEventListener('change', () => {
      if (!draft || active || panelApplying) return;
      const previous = draftTheme ? 'theme' : 'existing';
      draftAppearances[previous] = appearanceDraft(draft);
      if (draftTheme) draftThemePreference = { ...draftTheme.surfaceTransparency };
      draftTheme = themeChoice.value === APPROVED_THEME_ID
        ? {activeThemeId: APPROVED_THEME_ID, surfaceTransparency: { ...draftThemePreference }} : null;
      const appearance = draftAppearances[draftTheme ? 'theme' : 'existing'];
      draft.artwork = appearance.artwork;
      draft.contours = cloneSettings(appearance).contours;
      updatePanelFields();
      updatePanelBusy();
    });
    const changeTransparency = () => {
      if (!draftTheme || active || panelApplying) return;
      draftTheme.surfaceTransparency = themeMode.value === 'override'
        ? {mode: 'override', value: Number(themeTransparency.value)} : {mode: 'follow'};
      updatePanelBusy();
      refreshAppearance();
    };
    themeMode.addEventListener('change', changeTransparency);
    themeTransparency.addEventListener('input', changeTransparency);
    const addThemeField = (control, key, readout = null) => {
      control.id = 'agent-skin-settings-theme-' + key;
      styleInput(control);
      setStyle(control, {'min-width': '0', 'grid-column': '1 / -1', margin: '0'});
      const row = document.createElement('div');
      row.style.cssText = 'display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 12px;align-items:center;margin-top:14px;min-width:0';
      const label = document.createElement('label');
      label.htmlFor = control.id;
      label.style.cssText = 'overflow-wrap:anywhere';
      labels['settings.themeControl.' + key] = {element: label};
      row.appendChild(label);
      if (readout) row.appendChild(readout);
      row.appendChild(control);
      workspacePanel.appendChild(row);
    };
    const themeTransparencyValue = document.createElement('output');
    themeTransparencyValue.setAttribute('data-agent-skin-theme-transparency-value', '');
    themeTransparencyValue.setAttribute('aria-hidden', 'true');
    themeTransparencyValue.style.cssText = 'text-align:right;overflow-wrap:anywhere';
    addThemeField(themeChoice, 'choice');
    addThemeField(themeMode, 'mode');
    addThemeField(themeTransparency, 'transparency', themeTransparencyValue);
    const themeDescription = document.createElement('p');
    themeDescription.id = 'agent-skin-theme-transparency-description';
    themeDescription.style.cssText = 'margin:8px 0;overflow-wrap:anywhere;color:var(--agent-skin-muted,CanvasText)';
    labels['settings.themeControl.description'] = {element: themeDescription};
    const themeTransparencyReason = document.createElement('p');
    themeTransparencyReason.id = 'agent-skin-theme-transparency-reason';
    themeTransparencyReason.setAttribute('data-agent-skin-theme-transparency-reason', '');
    themeTransparencyReason.style.cssText = themeDescription.style.cssText;
    themeMode.setAttribute('aria-describedby', themeTransparencyReason.id);
    themeTransparency.setAttribute('aria-describedby', themeDescription.id + ' ' + themeTransparencyReason.id);
    const themeStrengthNote = document.createElement('p');
    themeStrengthNote.id = 'agent-skin-theme-strength-note';
    themeStrengthNote.style.cssText = themeDescription.style.cssText;
    labels['settings.themeControl.strengthNote'] = {element: themeStrengthNote};
    strength.setAttribute('aria-describedby', themeStrengthNote.id);
    workspacePanel.append(themeTransparencyReason, themeStrengthNote);
    addDisclosure('theme-help', 'settings.themeControl.help', workspacePanel).appendChild(themeDescription);
    controls.push(themeChoice, themeMode, themeTransparency);
    for (const [control, key] of [[themeChoice, 'choice'], [themeMode, 'mode'], [themeTransparency, 'transparency']]) ariaLabels.push({control, key: 'settings.themeControl.' + key});

    const presetDetails = addDisclosure('presets', 'settings.presets.heading', workspacePanel);
    const presetSection = document.createElement('div');
    presetSection.style.cssText = 'display:grid;gap:8px;margin-top:14px;min-width:0';
    presetDetails.appendChild(presetSection);
    const dreamSection = document.createElement('div');
    dreamSection.setAttribute('data-agent-skin-dream-section','');
    dreamSection.style.cssText = 'display:grid;gap:8px;margin-top:20px;padding-top:14px;border-top:1px solid var(--agent-skin-border,GrayText)';
    section.appendChild(dreamSection);
    const dreamImport = document.createElement('input');
    dreamImport.type = 'file'; dreamImport.accept = '.json,application/json';
    dreamImport.id = 'agent-skin-dream-import'; dreamImport.setAttribute('data-agent-skin-dream-import','');
    dreamImport.hidden = true; dreamImport.tabIndex = -1; dreamImport.setAttribute('aria-hidden','true');
    const dreamImportButton = document.createElement('button'); dreamImportButton.type = 'button';
    dreamImportButton.setAttribute('data-agent-skin-dream-import-button',''); styleButton(dreamImportButton);
    buttons['settings.dream.import'] = dreamImportButton; controls.push(dreamImportButton);
    dreamImportButton.addEventListener('click',()=>{if(panelOpen && !active && !panelCommit) dreamImport.click?.();});
    dreamSection.appendChild(dreamImportButton);
    const dreamImportNote = addText('settings.dream.importNote', dreamSection);
    dreamImportNote.setAttribute('data-agent-skin-dream-import-note', '');
    dreamImportNote.id = 'agent-skin-dream-import-note';
    dreamImportButton.setAttribute('aria-describedby', dreamImportNote.id);
    const dreamList = document.createElement('select');
    dreamList.id = 'agent-skin-dream-list'; dreamList.setAttribute('data-agent-skin-dream-list','');
    for (const [control,key] of [[dreamImport,'import'],[dreamList,'list']]) {
      styleInput(control);
      const label = document.createElement('label'); label.htmlFor = control.id;
      if (control === dreamImport) label.hidden = true;
      labels['settings.dream.'+key] = {element:label};
      dreamSection.append(label,control); controls.push(control);
    }
    const dreamApply = document.createElement('button'); dreamApply.type = 'button';
    dreamApply.setAttribute('data-agent-skin-dream-apply',''); styleButton(dreamApply);
    buttons['settings.dream.apply'] = dreamApply; controls.push(dreamApply);
    const dreamRestore = document.createElement('button'); dreamRestore.type='button';
    dreamRestore.setAttribute('data-agent-skin-dream-restore','');styleButton(dreamRestore);
    buttons['settings.dream.restore']=dreamRestore;controls.push(dreamRestore);
    const requestThemeApply = async capsuleSha256 => {
      if (!panelOpen || active || panelApplying || !panelCallbacks?.onThemeApply) return;
      const atStart=panelGeneration;
      panelThemeApplying=true;panelApplying=true;updatePanelBusy();setPanelStatus('settings.dream.applying');
      try {
        const expectedToken=await themeApplyToken();
        if (!panelOpen || atStart!==panelGeneration || !panelThemeApplying) return;
        const result=await panelCallbacks.onThemeApply({capsuleSha256,expectedToken});
        if (!panelOpen || atStart!==panelGeneration) return;
        if (result?.applied !== true) throw makeError(result?.reason || 'settings-unavailable');
        await load(defaultRecord);
        if (!panelOpen || atStart!==panelGeneration) return;
        updatePanelFields();setPanelStatus(capsuleSha256===null?'settings.dream.restored':'settings.dream.applied');
      } catch(error) {
        if (error?.reason !== 'operation-cancelled' && panelOpen && atStart===panelGeneration) {
          setPanelStatus(error?.reason==='settings-conflict'?'settings.error.conflict':'settings.dream.applyError','alert');
        }
      } finally {
        panelThemeApplying=false;panelApplying=false;updatePanelBusy();
      }
    };
    dreamApply.addEventListener('click',()=>requestThemeApply(dreamList.value));
    dreamRestore.addEventListener('click',()=>requestThemeApply(null));
    dreamSection.append(dreamApply,dreamRestore);
    addText('settings.dream.note', addDisclosure('dream-help', 'settings.dream.help', dreamSection));
    dreamImport.addEventListener('change',async() => {
      const file = dreamImport.files?.[0]; dreamImport.value = '';
      if (!file || !panelOpen || active || panelCommit) return;
      const atStart = panelGeneration;
      try {
        const operation = importDreamCapsule(file); updatePanelBusy();
        const receipt = await operation;
        if (!panelOpen || atStart !== panelGeneration) return;
        if (!dreamDirectoryView.entries.some(entry=>entry.capsuleSha256 === receipt.capsuleSha256)) {
          dreamDirectoryView.entries.push({capsuleSha256:receipt.capsuleSha256,name:receipt.name});
        }
        dreamDirectoryView.status = 'valid';
        updateDreamList(receipt.capsuleSha256); setPanelStatus('settings.dream.imported');
      } catch(error) {
        if (error?.reason !== 'operation-cancelled' && panelOpen && atStart === panelGeneration) {
          setPanelStatus(error?.reason === 'settings-blocked' ? 'settings.dream.readonly' : 'settings.dream.error','alert');
        }
      } finally {updatePanelBusy();}
    });

    const presetName = document.createElement('input');
    presetName.type = 'text'; presetName.maxLength = 40;
    presetName.setAttribute('data-agent-skin-preset-name', '');
    const presetList = document.createElement('select');
    presetList.setAttribute('data-agent-skin-preset-list', '');
    for (const [control, key] of [[presetName, 'name'], [presetList, 'list']]) {
      control.id = 'agent-skin-presets-' + key;
      styleInput(control);
      const label = document.createElement('label'); label.htmlFor = control.id;
      labels['settings.presets.' + key] = {element: label};
      presetSection.append(label, control); controls.push(control);
    }
    const presetAdd = document.createElement('button');
    const presetLoad = document.createElement('button');
    for (const [button, key] of [[presetAdd, 'add'], [presetLoad, 'load']]) {
      button.type = 'button'; styleButton(button);
      buttons['settings.presets.' + key] = button;
      presetSection.appendChild(button); controls.push(button);
    }
    const presetImport = document.createElement('input');
    presetImport.type = 'file'; presetImport.accept = '.json,application/json';
    presetImport.id = 'agent-skin-presets-import';
    presetImport.setAttribute('data-agent-skin-preset-import', '');
    styleInput(presetImport);
    const importLabel = document.createElement('label'); importLabel.htmlFor = presetImport.id;
    labels['settings.presets.import'] = {element: importLabel};
    const presetExport = document.createElement('button');
    presetExport.type = 'button'; styleButton(presetExport);
    presetExport.setAttribute('data-agent-skin-preset-export', '');
    buttons['settings.presets.export'] = presetExport;
    const exchangeNote = document.createElement('p');
    labels['settings.presets.exchangeNote'] = {element: exchangeNote};
    presetSection.append(importLabel, presetImport, presetExport, exchangeNote);
    controls.push(presetImport, presetExport);
    presetImport.addEventListener('change', async () => {
      const file = presetImport.files?.[0];
      presetImport.value = '';
      if (!file || !panelOpen || active || panelCommit || !draftLibrary || draftLibrary.entries.length >= 8) return;
      const {task, promise} = beginOperation('preset-file', 10_000);
      const atStart = panelGeneration;
      updatePanelBusy();
      Promise.resolve().then(async () => {
        try {
          const validated = await readPresetFile(task, file);
          if (!isCurrent(task) || panelGeneration !== atStart) throw makeError('operation-cancelled');
          draftLibrary = validated;
          finish(task, true, true);
          updatePresetList(); setPanelStatus('settings.presets.imported');
        } catch (error) { if (!task.settled) finish(task, false, error); }
      });
      try { await promise; }
      catch (error) {
        if (error?.reason !== 'operation-cancelled' && panelOpen && panelGeneration === atStart) setPanelStatus(error?.reason === 'operation-timeout'
          ? displayError(error.reason) : 'settings.presets.fileError', 'alert');
      }
      updatePanelBusy();
    });
    presetExport.addEventListener('click', () => {
      if (!panelOpen || active || panelCommit || !draftLibrary) return;
      const entry = draftLibrary.entries.find(value => value.id === presetList.value);
      if (!entry) return;
      let url, anchor;
      try {
        const {id, ...content} = entry;
        const BlobConstructor = environment.Blob || document.defaultView?.Blob;
        const blob = new BlobConstructor([JSON.stringify({schema: 'azhou-appearance-preset.v1', ...content})], {type: 'application/json'});
        url = URLObject.createObjectURL(blob);
        anchor = document.createElement('a'); anchor.href = url; anchor.download = 'azhou-preset.json';
        anchor.hidden = true; document.body.appendChild(anchor); anchor.click();
        setPanelStatus('settings.presets.exported');
      } catch { setPanelStatus('settings.presets.fileError', 'alert'); }
      finally {
        try { anchor?.remove(); } catch {}
        if (url) { try { URLObject.revokeObjectURL(url); } catch {} }
      }
    });
    const presetNote = document.createElement('p');
    labels['settings.presets.note'] = {element: presetNote};
    presetSection.appendChild(presetNote);
    presetAdd.addEventListener('click', async () => {
      if (!panelOpen || active || panelCommit || !draftTheme || !draftLibrary || draftLibrary.entries.length >= 8) return;
      const {task, promise} = beginOperation('preset', 10_000);
      const atStart = panelGeneration;
      updatePanelBusy();
      Promise.resolve().then(async () => {
        try {
          const validated = await stagePreset(task, {name: presetName.value.trim(), recipeId: APPROVED_THEME_ID,
            appearance: {...appearanceDraft(draft), wallpaperStrength: draft.wallpaperStrength},
            surfaceTransparency: {...draftTheme.surfaceTransparency}});
          if (!isCurrent(task) || panelGeneration !== atStart) throw makeError('operation-cancelled');
          draftLibrary = validated;
          finish(task, true, true);
          updatePresetList(); setPanelStatus('settings.presets.added');
        } catch (error) { if (!task.settled) finish(task, false, error); }
      });
      try { await promise; } catch (error) { setPanelStatus(displayError(error?.reason), 'alert'); }
      updatePanelBusy();
    });
    presetLoad.addEventListener('click', () => {
      if (!panelOpen || active || panelCommit || !draftLibrary) return;
      const entry = draftLibrary.entries.find(value => value.id === presetList.value);
      if (!entry) return;
      if (!draftTheme) draftAppearances.existing = appearanceDraft(draft);
      Object.assign(draft, structuredCloneTheme(entry.appearance));
      draftThemePreference = {...entry.surfaceTransparency};
      draftTheme = {activeThemeId: APPROVED_THEME_ID, surfaceTransparency: {...entry.surfaceTransparency}};
      draftAppearances.theme = appearanceDraft(draft);
      updatePanelFields(); updatePanelBusy(); setPanelStatus('settings.presets.loaded');
    });

    addSection('startup', 'settings.startup.note');
    addFile('avatar', 'settings.button.choosePortrait');
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
    const previewButton = document.createElement('button');
    previewButton.type = 'button';
    previewButton.setAttribute('data-agent-skin-preview-animation', '');
    previewButton.textContent = translate('settings.button.previewAnimation');
    styleButton(previewButton);
    previewButton.style.setProperty('margin-top', '18px');
    previewButton.addEventListener('click', () => {
      if (!panelOpen || active || !draft) return;
      const callback = panelCallbacks?.onPreview;
      if (typeof callback !== 'function') {
        setPanelStatus('settings.status.previewUnavailable');
        return;
      }
      const panelAtStart = panelGeneration;
      const showError = () => {
        if (panelOpen && panelAtStart === panelGeneration) setPanelStatus('settings.error.preview', 'alert');
      };
      try {
        const result = callback(cloneSettings(draft));
        if (result === false) {
          setPanelStatus('settings.status.previewUnavailable');
          return;
        }
        setPanelStatus('settings.status.previewStarted');
        if (result && typeof result.then === 'function') {
          Promise.resolve(result).then(value => {
            if (value === false && panelOpen && panelAtStart === panelGeneration) {
              setPanelStatus('settings.status.previewUnavailable');
            }
          }, showError);
        }
      } catch {
        showError();
      }
    });
    controls.push(previewButton);
    buttons['settings.button.previewAnimation'] = previewButton;
    section.appendChild(previewButton);
    workspacePanel.hidden = false;
    selectCategory('workspace');

    const aboutPanel = addSection('about');
    addInfo('locale', 'settings.locale', () => inherited('locale') || localization?.locale || translate('settings.unknown'));
    addInfo('theme', 'settings.theme', () => ['light', 'dark'].includes(inherited('theme'))
      ? translate('settings.theme.' + inherited('theme')) : translate('settings.unknown'));
    addInfo('reducedMotion', 'settings.reducedMotion', () => typeof inherited('reducedMotion') === 'boolean'
      ? translate(inherited('reducedMotion') ? 'settings.on' : 'settings.off') : translate('settings.unknown'));
    addInfo('source', 'settings.source', () => translate(loadReason
      ? 'settings.source.unavailable' : currentBaseline === undefined ? 'settings.source.defaults' : 'settings.source.user'));
    const buildDetails = document.createElement('details');
    buildDetails.style.cssText = 'margin-top:18px';
    addText('settings.about.buildDetails', buildDetails, 'summary').style.cssText = 'cursor:pointer';
    aboutPanel.appendChild(buildDetails);
    section = buildDetails;
    addInfo('appName', 'settings.appName', () => localized(themeConfig?.identity?.appName));
    addInfo('botName', 'settings.botName', () => localized(themeConfig?.identity?.botName));
    addInfo('version', 'settings.version', () => themeConfig?.identity?.version && themeConfig?.identity?.build
      ? themeConfig.identity.version + ' · ' + themeConfig.identity.build : translate('settings.unknown'));

    const status = document.createElement('p');
    status.style.cssText = 'flex:1 1 180px;min-width:0;min-height:1.5em;margin:0;overflow-wrap:anywhere;color:var(--agent-skin-muted,CanvasText)';
    status.setAttribute('data-agent-skin-settings-status', '');
    status.setAttribute('aria-live', 'polite');
    const actions = document.createElement('footer');
    actions.style.cssText = 'position:sticky;bottom:0;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-top:10px;padding:12px clamp(16px,3vw,26px);background:var(--agent-skin-surface,Canvas);border-top:1px solid var(--agent-skin-border,CanvasText)';
    const actionButtons = document.createElement('div');
    actionButtons.style.cssText = 'display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;margin-left:auto';
    const restore = document.createElement('button');
    restore.type = 'button';
    styleButton(restore);
    restore.textContent = translate('settings.button.restore');
    restore.addEventListener('click', () => {
      if (active || !panelOpen) return;
      draft = cloneSettings(defaultRecord || currentSettings);
      draftTheme = null;
      draftThemePreference = { mode: 'follow' };
      draftAppearances = { existing: appearanceDraft(draft), theme: appearanceDraft(draft) };
      updatePanelFields();
      updatePanelBusy();
      setPanelStatus('settings.status.defaultsRestored');
    });
    const cancel = document.createElement('button');
    cancel.type = 'button';
    styleButton(cancel);
    cancel.textContent = translate('settings.button.cancel');
    cancel.addEventListener('click', () => {
      if (panelPresentation === 'embedded') revertPanelDraft();
      else cancelSettings();
    });
    const saveButton = document.createElement('button');
    saveButton.type = 'button';
    styleButton(saveButton, true);
    saveButton.textContent = translate('settings.button.save');
    saveButton.addEventListener('click', async () => {
      if (!panelOpen || active || panelApplying) return;
      if (panelCommit) {
        await applyCommittedSettings(panelCommit);
        return;
      }
      if (!draft) return;
      for (const key of Object.keys(TEXT_LIMITS)) draft[key] = truncateText(draft[key], TEXT_LIMITS[key]);
      const panelAtStart = panelGeneration;
      const themeSelection = draftTheme || (currentThemeState || draftThemePreference.mode !== 'follow'
        ? { activeThemeId: null, surfaceTransparency: { ...draftThemePreference } } : undefined);
      const libraryDraft = draftLibrary && !recordEquals(draftLibrary, currentLibrary) ? draftLibrary : undefined;
      const catalogOnly = libraryDraft !== undefined && recordEquals(draft, currentSettings) && sameThemeSelection(themeSelection);
      const saving = save(cloneSettings(draft), themeSelection, libraryDraft);
      updatePanelBusy();
      let saved;
      try {
        saved = await saving;
      } catch (error) {
        if (panelOpen && panelAtStart === panelGeneration) setPanelStatus(displayError(error?.reason), 'alert');
        updatePanelBusy();
        return;
      }
      if (!panelOpen || panelAtStart !== panelGeneration) return;
      panelCommit = {
        saved: { ...cloneSettings(saved), themeState: currentThemeState?.activeThemeId ? structuredCloneTheme(currentThemeState) : null },
        onApply: !catalogOnly && currentThemeState?.selection?.kind !== 'imported' && typeof panelCallbacks?.onApply === 'function' ? panelCallbacks.onApply : null,
        failed: false,
      };
      panelSavedNotified = false;
      updatePanelBusy();
      if (panelCommit.onApply) await applyCommittedSettings(panelCommit);
      else if (panelPresentation === 'embedded') settleEmbeddedSave(panelCommit.saved);
      else closePanel('saved');
    });
    controls.push(restore, cancel, saveButton);
    buttons['settings.button.restore'] = restore;
    buttons['settings.button.cancel'] = cancel;
    buttons['settings.button.save'] = saveButton;
    actionButtons.append(restore, cancel, saveButton);
    actions.append(status, actionButtons);
    content.appendChild(actions);
    dialog.appendChild(content);
    document.body.appendChild(dialog);
    if (panelPresentation !== 'embedded') {
      // Native `cancel` fires only for showModal() dialogs, and the Tab trap
      // matches the modal presentation. The embedded section keeps the host
      // settings page's own navigation untrapped.
      dialog.addEventListener('cancel', event => {
        if (event.target !== dialog) return;
        event.preventDefault();
        cancelSettings();
      });
      dialog.addEventListener('keydown', containPanelTab, true);
    }
    panelControls = {
      dreamImport, dreamImportButton, dreamList, dreamApply, dreamRestore, presetName, presetList, presetAdd, presetLoad, presetImport, presetExport, controls, status, fields, strength, strengthValue, themeChoice, themeMode, themeTransparency, themeTransparencyValue, themeTransparencyReason, themeStrengthNote, heading, close: null, categoryNav, labels,
      ariaLabels, buttons, readouts, previews, workspacePreview, workspacePreviewCaption,
      workspacePreviewSurface, workspacePreviewImage: backgroundImage, workspacePreviewWash: backgroundWash,
      workspacePreviewHasImage, strengthLabel, saveButton, cancelButton: cancel, footer: actions,
    };
    updatePanelText();
    return true;
  }

  function syncPanelScrollPadding() {
    if (!panelOpen || !dialog || !panelControls?.footer) return;
    const footerHeight = panelControls.footer.offsetHeight;
    if (footerHeight > 0) dialog.style.setProperty('scroll-padding-bottom', footerHeight + 6 + 'px');
  }

  function openSettings(callbacks = {}, options = {}) {
    if (disposed || panelOpen || !currentSettings || active) return false;
    panelPresentation = options && options.presentation === 'embedded' ? 'embedded' : 'modal';
    if (!buildSettingsPanel()) return false;
    draft = cloneSettings(currentSettings);
    draftLibrary = structuredCloneTheme(currentLibrary);
    draftThemePreference = { ...(currentThemeState?.preferencesByTheme?.[APPROVED_THEME_ID] || { mode: 'follow' }) };
    draftTheme = currentThemeState?.activeThemeId ? { activeThemeId: currentThemeState.activeThemeId,
      surfaceTransparency: { ...draftThemePreference } } : null;
    draftAppearances = { existing: appearanceDraft(draft), theme: appearanceDraft(draftTheme ? draft : defaultRecord || draft) };
    panelCallbacks = callbacks && typeof callbacks === 'object' ? callbacks : {};
    panelCommit = null;
    panelApplying = false;
    panelSavedNotified = false;
    panelGeneration++;
    panelOpen = true;
    updatePanelFields();
    if (currentThemeReadOnly || currentImagesReadOnly) setPanelStatus('settings.load.readonly','alert');
    else if (loadReason === 'settings-invalid') setPanelStatus('settings.load.invalid', 'alert');
    else if (loadReason === 'operation-timeout') setPanelStatus('settings.load.timeout', 'alert');
    else if (loadReason === 'settings-unavailable' || loadReason === 'settings-blocked') {
      setPanelStatus('settings.load.unavailable', 'alert');
    } else if (currentThemeReadOnly) setPanelStatus('settings.load.unavailable','alert');
    else if (!currentLibrary) setPanelStatus('settings.presets.unavailable', 'alert');
    else setPanelStatus('');
    // The embedded section renders inline: show() keeps the dialog non-modal
    // with no backdrop and no native cancel event.
    try { if (panelPresentation === 'embedded') dialog.show(); else dialog.showModal(); }
    catch {
      panelOpen = false;
      panelCallbacks = null;
      return false;
    }
    if (dreamThemeStyle && currentDreamBaseline !== undefined) {
      const atStart = panelGeneration;
      loadDreamDirectory().then(directory => {
        if (!panelOpen || atStart !== panelGeneration) return;
        dreamDirectoryView = directory; updateDreamList();
        if (directory.status === 'readonly') setPanelStatus('settings.dream.readonly','alert');
        updatePanelBusy();
      },error => {
        if (error?.reason !== 'operation-cancelled' && panelOpen && atStart === panelGeneration) {
          dreamDirectoryView = {status:'readonly',entries:[]}; updateDreamList();
          setPanelStatus('settings.dream.readonly','alert'); updatePanelBusy();
        }
      });
    } else {dreamDirectoryView = {status:'missing',entries:[]};updateDreamList();}
    syncPanelScrollPadding();
    updatePanelBusy();
    try { panelCallbacks.onOpen?.(); } catch {}
    return true;
  }

  function closePanel(returnValue = '') {
    if (!panelOpen) return false;
    if (panelThemeApplying) {try {panelCallbacks?.onThemeCancel?.();} catch {} panelThemeApplying=false;}
    const commit = panelCommit;
    const callback = commit && !panelSavedNotified ? panelCallbacks?.onSaved : null;
    if (commit) panelSavedNotified = true;
    panelOpen = false;
    panelGeneration++;
    draft = null;
    draftTheme = null;
    draftThemePreference = null;
    draftAppearances = null;
    draftLibrary = null;
    panelCommit = null;
    panelApplying = false;
    panelCallbacks = null;
    try { dialog?.close(returnValue); } catch {}
    refreshLocalizedDefaults();
    try { callback?.(commit.saved); } catch {}
    return true;
  }

  function cancelPresetFile() {
    if (['preset-file','dream-file','dream-directory'].includes(active?.kind)) finish(active, false, makeError('operation-cancelled'));
  }

  function cancelSettings() {
    cancelPresetFile();
    if (!panelOpen || active) return false;
    if (panelCommit) return closePanel('saved');
    const callback = panelCallbacks?.onCancel;
    closePanel('cancel');
    try { callback?.(); } catch {}
    return true;
  }

  // Embedded presentation: a saved commit stays open for further edits. The
  // save notification fires exactly once per commit, matching closePanel's
  // modal-path contract, and the commit is cleared so the fields re-enable.
  // currentSettings mirrors the stored record — the modal path re-reads it
  // through load() on each reopen, the embedded panel never reopens.
  function settleEmbeddedSave(savedSnapshot) {
    if (!panelSavedNotified) {
      panelSavedNotified = true;
      const savedCallback = panelCallbacks?.onSaved;
      try { savedCallback?.(savedSnapshot); } catch {}
    }
    panelCommit = null;
    panelApplying = false;
    draftLibrary = structuredCloneTheme(currentLibrary);
    updatePanelBusy();
    setPanelStatus('settings.status.saved');
  }

  // Embedded presentation: cancel discards draft edits without closing the
  // section — only the host unmounting the embed ends it. A saved-but-unapplied
  // commit follows the modal cancel-with-commit contract: its stored record
  // becomes the revert baseline and the pending-apply state is dropped, so the
  // fields, the save action and the stored record agree again (the modal path
  // closes the panel instead of reverting).
  function revertPanelDraft() {
    if (panelThemeApplying) {try {panelCallbacks?.onThemeCancel?.();} catch {} return false;}
    cancelPresetFile();
    if (!panelOpen || active || panelApplying) return false;
    if (panelCommit) {
      if (!panelSavedNotified) {
        panelSavedNotified = true;
        const savedCallback = panelCallbacks?.onSaved;
        try { savedCallback?.(panelCommit.saved); } catch {}
      }
      panelCommit = null;
    }
    draft = cloneSettings(currentSettings);
    draftLibrary = structuredCloneTheme(currentLibrary);
    draftThemePreference = {...(currentThemeState?.preferencesByTheme?.[APPROVED_THEME_ID] || {mode:'follow'})};
    draftTheme = currentThemeState?.activeThemeId ? {activeThemeId: currentThemeState.activeThemeId,
      surfaceTransparency: {...draftThemePreference}} : null;
    draftAppearances = {existing: appearanceDraft(draft), theme: appearanceDraft(draftTheme ? draft : defaultRecord || draft)};
    updatePanelFields();
    updatePanelBusy();
    setPanelStatus('');
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
    if (panelOpen) closePanel(panelCommit ? 'saved' : 'dispose');
    else {
      panelCommit = null;
      panelApplying = false;
      panelCallbacks = null;
      draft = null;
      draftTheme = null;
      draftThemePreference = null;
      draftAppearances = null;
    draftLibrary = null;
    }
    try { dialog?.remove(); } catch {}
    if (panelFocusSheet) {
      try { document.adoptedStyleSheets = document.adoptedStyleSheets.filter(sheet => sheet !== panelFocusSheet); } catch {}
      panelFocusSheet = null;
    }
    try { localizationUnsubscribe?.(); } catch {}
    localizationUnsubscribe = null;
    dialog = null;
    panelControls = null;
    if (!active?.deferSettlement) {
      try { database?.close(); } catch {}
      database = null;
    }
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

  function rawDimensionsReader() {
    if (typeof readRawDimensions === 'function') return readRawDimensions;
    try {
      const reader = typeof globalThis === 'object' && globalThis.AGENT_SKIN_READ_RAW_DIMENSIONS;
      return typeof reader === 'function' ? reader : null;
    } catch { return null; }
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
    return actualType;
  }

  async function readHeaderDimensions(file, actualType, task) {
    const readRawDimensions = rawDimensionsReader();
    if (!readRawDimensions) return null;
    const limit = actualType === 'image/png' ? 24 : MAX_HEADER_READ_BYTES;
    const end = Math.min(limit, file.size);
    let buffer;
    try {
      const prefix = file.slice(0, end);
      if (!prefix || typeof prefix.arrayBuffer !== 'function') return null;
      buffer = await prefix.arrayBuffer();
    } catch (error) {
      assertCurrent(task);
      return null;
    }
    assertCurrent(task);
    if (!buffer || Object.prototype.toString.call(buffer) !== '[object ArrayBuffer]') return null;
    const extension = actualType === 'image/png' ? '.png'
      : actualType === 'image/jpeg' ? '.jpg' : '.webp';
    try {
      const dimensions = readRawDimensions(new Uint8Array(buffer), extension);
      assertCurrent(task);
      return dimensions;
    } catch (error) {
      if (error?.reason === 'operation-cancelled' || error?.reason === 'operation-timeout') throw error;
      assertCurrent(task);
      return null;
    }
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

  async function normalizeArtwork(task, image, {contoursOnly = false} = {}) {
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
    let contours;
    try { contours = await extractContours(task, imageData); }
    catch(error) {
      if (!contoursOnly || error?.causeCode !== 'contours-empty') throw error;
      contours = [[[0,0],[width,0],[width,height],[0,height],[0,0]]];
    }
    assertCurrent(task);
    if (contoursOnly) return {contours};
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
        const actualType = await readSignature(file, task);
        const headerDimensions = await readHeaderDimensions(file, actualType, task);
        const headerWidth = headerDimensions?.width;
        const headerHeight = headerDimensions?.height;
        if (Number.isSafeInteger(headerWidth) && headerWidth > 0
          && Number.isSafeInteger(headerHeight) && headerHeight > 0) {
          const headerPixels = headerWidth * headerHeight;
          if (!Number.isSafeInteger(headerPixels) || headerPixels > MAX_SOURCE_PIXELS) {
            throw invalidData('image-too-large');
          }
        }
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
    loadSnapshot,
    save,
    importImage,
    loadDreamDirectory,
    importDreamCapsule,
    cancelDreamImport,
    themeApplyToken,
    applyDreamTheme,
    restoreAzhouTheme,
    cancelImport,
    openSettings,
    cancelSettings,
    isSettingsOpen,
    isBusy,
    refreshAppearance,
    dispose,
  };
}
