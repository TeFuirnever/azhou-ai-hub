import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import vm from 'node:vm';

const SOURCE_PATH = join(dirname(fileURLToPath(import.meta.url)), '..', 'localization.js');
const source = await readFile(SOURCE_PATH, 'utf8');
const createLocalization = vm.runInNewContext(`${source}\ncreateLocalization`, {});

test('localization follows only the explicitly supplied host locale', () => {
  const localization = createLocalization({ locale: 'en', navigator: { language: 'zh-CN' } });

  assert.equal(localization.locale, 'en');
  assert.equal(localization.t('characterName'), 'Azhou');
  localization.setLocale('zh-CN');
  assert.equal(localization.locale, 'zh-CN');
  assert.equal(localization.t('characterName'), '阿舟');
});

test('build-owned names and startup text follow locale without becoming preferences', () => {
  const localization = createLocalization({ locale: 'en', themeConfig: {
    identity: { botName: { en: 'Azhou build', 'zh-CN': '阿舟构建' } },
    startup: { text: { introTitle: { en: 'Built lab', 'zh-CN': '构建实验室' } } },
  } });
  assert.equal(localization.t('characterName'), 'Azhou build');
  assert.equal(localization.t('animation.title.default'), 'Built lab');
  localization.setLocale('zh-CN');
  assert.equal(localization.t('characterName'), '阿舟构建');
  assert.equal(localization.t('animation.title.default'), '构建实验室');
  assert.equal(localization.t('animation.subtitle.default'), '和阿舟一起，把想法做出来。');
});

test('localization defaults safely to Chinese without a host locale', () => {
  const localization = createLocalization({ navigator: { language: 'en-US' } });

  assert.equal(localization.locale, 'zh-CN');
  assert.equal(localization.t('settings.button.cancel'), '取消');
});

test('language changes notify active subscribers and unsubscribe cleanly', () => {
  const localization = createLocalization({ locale: 'en' });
  const seen = [];
  const unsubscribe = localization.subscribe(() => seen.push(localization.locale));

  localization.setLocale('zh-CN');
  localization.setLocale('zh-CN');
  unsubscribe();
  localization.setLocale('en');

  assert.deepEqual(seen, ['zh-CN']);
});

test('animation, renderer and settings strings are present in both locales', () => {
  const localization = createLocalization({ locale: 'en' });
  const keys = [
    'characterName', 'openAppearance', 'appearanceLabel', 'overlayLabel',
    'animation.stage.pulse', 'animation.stage.identity', 'animation.stage.dispersing',
    'animation.stage.scattered', 'animation.stage.drawing', 'animation.stage.colorize',
    'animation.stage.portrait', 'animation.stage.shutter', 'animation.stage.complete',
    'animation.title.default', 'animation.caption.default', 'animation.subtitle.default',
    'animation.preview.title', 'animation.preview.canvas',
    'animation.accessibility.root', 'animation.accessibility.canvas',
    'animation.accessibility.progress', 'animation.accessibility.skip',
    'animation.accessibility.timeline', 'animation.control.skip', 'animation.control.replay',
    'animation.control.pause', 'animation.control.resume', 'animation.progress',
    'animation.elapsed', 'animation.waiting', 'animation.error.title', 'animation.error.body',
    'animation.wallpaper.failed.title', 'animation.wallpaper.failed.body',
    'settings.title', 'settings.close', 'settings.avatar.label', 'settings.artwork.label',
    'settings.introTitle.label', 'settings.introCaption.label', 'settings.artworkSubtitle.label',
    'settings.wallpaperStrength.label', 'settings.wallpaperStrength.aria',
    'settings.button.restore', 'settings.button.cancel', 'settings.button.choosePortrait',
    'settings.button.chooseBackground',
    'settings.button.save', 'settings.status.importing', 'settings.status.saving', 'settings.status.imageLarge',
    'settings.status.imageReady', 'settings.status.defaultsRestored', 'settings.error.conflict',
    'settings.error.quota', 'settings.error.blocked', 'settings.error.timeout',
    'settings.error.invalid', 'settings.error.save', 'settings.load.invalid',
    'settings.load.timeout', 'settings.load.unavailable',
  ];

  for (const locale of ['en', 'zh-CN']) {
    localization.setLocale(locale);
    for (const key of keys) {
      const value = localization.t(key);
      assert.equal(typeof value, 'string', `${locale}:${key} is a string`);
      assert.notEqual(value, key, `${locale}:${key} has a translation`);
    }
  }
  assert.match(localization.t('animation.progress', { percent: 42 }), /42%$/);
  assert.match(localization.t('animation.elapsed', { elapsed: '2.4', duration: '12' }), /2\.4.*12/);
  assert.match(localization.t('settings.introTitle.label', { limit: 16 }), /16/);
  localization.setLocale('zh-CN');
  assert.equal(localization.t('animation.title.default'), '阿舟 AI 实验室');
  assert.equal(localization.t('animation.caption.default'), 'AZHOU / AI LAB');
  assert.equal(localization.t('animation.progress', { percent: 42 }), '动画进度 42%');
  assert.equal(localization.t('animation.waiting'), '仍在等待 Codex 启动…');
  assert.equal(localization.t('animation.wallpaper.failed.title'), '设置已保存，但壁纸未能应用');
  localization.setLocale('en');
  assert.equal(localization.t('animation.title.default'), 'Azhou AI Lab');
  assert.equal(localization.t('animation.waiting'), 'Still waiting for Codex to start…');
  assert.equal(localization.t('animation.wallpaper.failed.title'),
    'Settings were saved, but the wallpaper could not be applied');
  assert.equal(localization.t('settings.close'), 'Cancel and close settings');
});
