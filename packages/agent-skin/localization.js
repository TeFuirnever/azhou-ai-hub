/**
 * Localize the self-contained startup and appearance UI from the host locale.
 * Pass locale explicitly; this module does not read or persist user preferences.
 */
function createLocalization(environment = {}) {
  const messages = {
    'zh-CN': {
      characterName: '阿舟',
      openAppearance: '打开外观设置',
      appearanceLabel: '阿舟外观设置',
      overlayLabel: '阿舟启动动画',
      'animation.stage.pulse': '实验室正在亮起来',
      'animation.stage.identity': '阿舟正在准备工作台',
      'animation.stage.dispersing': '头像与文字散成线稿',
      'animation.stage.scattered': '线稿正在汇聚',
      'animation.stage.drawing': '阿舟和背景正在显现',
      'animation.stage.colorize': '同一幅画面正在上色',
      'animation.stage.portrait': '阿舟正在完成画面',
      'animation.stage.shutter': '动画即将结束',
      'animation.stage.complete': '已结束',
      'animation.title.default': '阿舟 AI 实验室',
      'animation.caption.default': 'AZHOU / AI LAB',
      'animation.subtitle.default': '和阿舟一起，把想法做出来。',
      'animation.preview.title': '动画预览 · 12 秒',
      'animation.preview.canvas': '固定 1536 × 1024 画布',
      'animation.accessibility.root': '阿舟启动动画',
      'animation.accessibility.canvas': '阿舟动画画布',
      'animation.accessibility.progress': '动画进度',
      'animation.accessibility.skip': '跳过启动动画',
      'animation.accessibility.timeline': '动画时间轴',
      'animation.control.skip': '跳过',
      'animation.control.replay': '重播',
      'animation.control.pause': '暂停',
      'animation.control.resume': '继续',
      'animation.progress': '动画进度 {percent}%',
      'animation.elapsed': '{elapsed} / {duration} 秒',
      'animation.waiting': '仍在等待 Codex 启动…',
      'animation.error.title': '启动动画暂时无法播放',
      'animation.error.body': '你可以继续使用应用，或稍后重试。',
      'animation.wallpaper.failed.title': '设置已保存，但壁纸未能应用',
      'animation.wallpaper.failed.body': '启动动画仍可继续播放。之后可以重新应用壁纸。',
      'settings.title': '阿舟 · 外观设置',
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
    },
    en: {
      characterName: 'Azhou',
      openAppearance: 'Open appearance settings',
      appearanceLabel: 'Azhou appearance settings',
      overlayLabel: 'Azhou startup animation',
      'animation.stage.pulse': 'The lab is lighting up',
      'animation.stage.identity': 'Azhou is setting up the workspace',
      'animation.stage.dispersing': 'The portrait and text are spreading into line art',
      'animation.stage.scattered': 'The line art is gathering',
      'animation.stage.drawing': 'Azhou and the background are appearing',
      'animation.stage.colorize': 'Color is being added to the scene',
      'animation.stage.portrait': 'Azhou is finishing the scene',
      'animation.stage.shutter': 'The animation is almost finished',
      'animation.stage.complete': 'Finished',
      'animation.title.default': 'Azhou AI Lab',
      'animation.caption.default': 'AZHOU / AI LAB',
      'animation.subtitle.default': 'Let’s make ideas real with Azhou.',
      'animation.preview.title': '12-second animation preview',
      'animation.preview.canvas': 'Fixed 1536 × 1024 canvas',
      'animation.accessibility.root': 'Azhou startup animation',
      'animation.accessibility.canvas': 'Azhou animation canvas',
      'animation.accessibility.progress': 'Animation progress',
      'animation.accessibility.skip': 'Skip startup animation',
      'animation.accessibility.timeline': 'Animation timeline',
      'animation.control.skip': 'Skip',
      'animation.control.replay': 'Replay',
      'animation.control.pause': 'Pause',
      'animation.control.resume': 'Resume',
      'animation.progress': 'Animation progress: {percent}%',
      'animation.elapsed': '{elapsed} / {duration} s',
      'animation.waiting': 'Still waiting for Codex to start…',
      'animation.error.title': 'The startup animation is unavailable',
      'animation.error.body': 'You can keep using the app or try again later.',
      'animation.wallpaper.failed.title': 'Settings were saved, but the wallpaper could not be applied',
      'animation.wallpaper.failed.body': 'The startup animation can continue. You can try applying the wallpaper again later.',
      'settings.title': 'Azhou · Appearance',
      'settings.close': 'Cancel and close settings',
      'settings.avatar.label': 'Startup portrait',
      'settings.artwork.label': 'Background image',
      'settings.introTitle.label': 'Startup title (up to {limit} characters)',
      'settings.introCaption.label': 'Title caption (up to {limit} characters)',
      'settings.artworkSubtitle.label': 'Background subtitle (up to {limit} characters)',
      'settings.wallpaperStrength.label': 'Background effect strength ({min}–{max})',
      'settings.wallpaperStrength.aria': 'Background effect strength, {min} to {max}',
      'settings.button.restore': 'Restore defaults',
      'settings.button.cancel': 'Cancel',
      'settings.button.save': 'Save and replay',
      'settings.button.choosePortrait': 'Choose startup portrait',
      'settings.button.chooseBackground': 'Choose background image',
      'settings.status.importing': 'Processing image…',
      'settings.status.saving': 'Validating and saving settings…',
      'settings.status.imageLarge': 'Image ready. The original exceeds 16 MP, so processing may take longer.',
      'settings.status.imageReady': 'Image ready to save.',
      'settings.status.defaultsRestored': 'Draft restored to defaults. Saved settings are unchanged.',
      'settings.error.conflict': 'Another page changed these settings. Cancel, reopen the panel, and save your draft again.',
      'settings.error.quota': 'There is not enough storage space. Choose another image and try again.',
      'settings.error.blocked': 'Another page is blocking the settings database. Try again shortly.',
      'settings.error.timeout': 'The operation timed out. The panel is ready; cancel or try again.',
      'settings.error.invalid': 'The settings could not be validated. Saved content is unchanged.',
      'settings.error.save': 'Could not save settings. Saved content is unchanged.',
      'settings.load.invalid': 'The saved record is not recognized. Defaults are in use; the record was kept.',
      'settings.load.timeout': 'Settings took too long to load. Defaults are in use; saved data is unchanged. Try again.',
      'settings.load.unavailable': 'Saved settings are temporarily unavailable. Defaults are in use; the record was kept.',
    },
  };

  function normalizeLocale(value) {
    if (typeof value !== 'string') return 'zh-CN';
    return /^zh(?:-|$)/i.test(value) ? 'zh-CN' : 'en';
  }

  let currentLocale = normalizeLocale(environment && environment.locale);
  const listeners = new Set();

  function t(key, params) {
    const template = messages[currentLocale][key];
    if (typeof template !== 'string') return String(key);
    if (!params || typeof params !== 'object') return template;
    return template.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g, (placeholder, name) =>
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder);
  }

  function setLocale(locale) {
    const nextLocale = normalizeLocale(locale);
    if (nextLocale === currentLocale) return currentLocale;
    currentLocale = nextLocale;
    for (const listener of [...listeners]) {
      try { listener(currentLocale); } catch {}
    }
    return currentLocale;
  }

  function subscribe(listener) {
    if (typeof listener !== 'function') return () => {};
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  return {
    t,
    setLocale,
    subscribe,
    get locale() { return currentLocale; },
  };
}
