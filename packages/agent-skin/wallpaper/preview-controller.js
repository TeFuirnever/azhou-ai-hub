import { installRenderer } from './renderer.js';

const status = document.getElementById('result');
const buttons = Object.fromEntries(['theme', 'apply', 'restore', 'checks'].map(id => [id, document.getElementById(id)]));
const show = value => { status.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2); };
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
let generation = 0;

async function payloadForPreview() {
  const filename = new URL(location.href).searchParams.get('image') || 'wallpaper-scene-q-v3.png';
  ensure(/^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:png|webp)$/i.test(filename), '无效的本地素材文件名');
  const [imageResponse, cssResponse] = await Promise.all([
    fetch('../assets/private/' + encodeURIComponent(filename)), fetch('./wallpaper.css'),
  ]);
  ensure(imageResponse.ok, '缺少本地阿舟素材：' + filename);
  ensure(cssResponse.ok, '无法读取壁纸样式');
  const bytes = await imageResponse.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const imageSHA256 = [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
  const type = filename.toLowerCase().endsWith('.webp') ? 'image/webp' : 'image/png';
  const image = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(new Blob([bytes], { type }));
  });
  return { version: '0.9.0', preview: true, image, imageSHA256, css: await cssResponse.text() };
}

function restore() {
  generation += 1;
  globalThis.__azhouWallpaper?.dispose();
  show('已恢复模拟宿主底色');
}

function makeController(payload) {
  async function apply() {
    const ticket = ++generation;
    const state = await installRenderer({ ...payload, isCurrent: () => ticket === generation });
    if (ticket === generation) {
      show({ applied: state.applied, imageDecoded: state.imageDecoded, coverMatched: state.coverMatched,
        fixedViewport: state.fixedViewport, sourceSize: [state.image?.width, state.image?.height],
        footerBackgroundClear: state.footerBackgroundClear, footerFadeClear: state.footerFadeClear,
        topFadeClear: state.topFadeClear, decorationEffectsClear: state.decorationEffectsClear,
        scope: '模拟宿主；画面仍需视觉验收' });
    }
    return state;
  }

  async function runChecks() {
    for (const button of Object.values(buttons)) button.disabled = true;
    const root = document.documentElement;
    const checks = [];
    try {
      generation += 1;
      globalThis.__azhouWallpaper?.dispose();
      const originalStyle = root.style.cssText;
      root.style.setProperty('--azhou-wallpaper-image', 'none', 'important');
      const value = root.style.getPropertyValue('--azhou-wallpaper-image');
      const priority = root.style.getPropertyPriority('--azhou-wallpaper-image');
      try {
        let state = await apply();
        ensure(state.applied && state.workspaceBackgroundClear && state.footerBackgroundClear &&
          state.footerSurfaces === 2 && state.footerFadeSurfaces === 1 && state.footerFadeClear &&
          state.topFadeSurfaces === 1 && state.topFadeClear && state.decorationEffectsClear, '宿主背景未完全清除');
        ensure(state.coverMatched && state.fixedViewport && state.image?.displayMode === 'cover', '图片没有覆盖固定视口');
        ensure(!/rgba\([^)]*,\s*0\)$/.test(getComputedStyle(document.querySelector('.composer')).backgroundColor), '输入区域意外透明');
        checks.push('背景与宿主表面匹配', '图片覆盖固定视口', '输入区域保持不透明');
        state = await apply();
        ensure(state.styleCount === 1, '重复应用产生多个样式');
        checks.push('重复应用不会累积样式');
        const previous = globalThis.__azhouWallpaper;
        let rejected = false;
        try { await installRenderer({ ...payload, css: payload.css.replace('--azhou-style-ready: ready', '--azhou-style-ready: blocked') }); }
        catch { rejected = true; }
        ensure(rejected && globalThis.__azhouWallpaper === previous && previous.status().applied, '更新失败时未保留原壁纸');
        checks.push('更新失败保留原壁纸');
        previous.dispose(); previous.dispose();
        ensure(!document.getElementById('azhou-wallpaper-style') && !globalThis.__azhouWallpaper, '恢复后仍有残留');
        ensure(root.style.getPropertyValue('--azhou-wallpaper-image') === value &&
          root.style.getPropertyPriority('--azhou-wallpaper-image') === priority, '原样式未完整恢复');
        checks.push('重复恢复保留原始属性');
        const frame = document.querySelector('[data-app-shell-frame]');
        frame.removeAttribute('data-app-shell-frame');
        try {
          rejected = false;
          try { await installRenderer(payload); } catch { rejected = true; }
          ensure(rejected && !document.getElementById('azhou-wallpaper-style'), '缺少宿主锚点时未拒绝');
        } finally { frame.setAttribute('data-app-shell-frame', ''); }
        checks.push('缺少宿主锚点时拒绝');
        for (const candidate of [
          { ...payload, image: 'data:image/png;base64,aW52YWxpZA==' },
          { ...payload, css: payload.css.replace('--azhou-style-ready: ready', '--azhou-style-ready: blocked') },
        ]) {
          rejected = false;
          try { await installRenderer(candidate); } catch { rejected = true; }
          ensure(rejected && !document.getElementById('azhou-wallpaper-style') && !globalThis.__azhouWallpaper, '无效候选未回滚');
        }
        checks.push('坏图和无效样式均被拒绝并回滚');
      } finally {
        globalThis.__azhouWallpaper?.dispose();
        root.style.cssText = originalStyle;
      }
      await apply();
      const summary = { passed: true, checks, limitations: ['模拟宿主，非真实 Codex 页面', 'cover 会随窗口比例裁切', '角色和阅读效果需要视觉检查', '不验证冷启动、调试端口或脚本注入策略'] };
      show(summary);
      return summary;
    } finally {
      for (const button of Object.values(buttons)) button.disabled = false;
    }
  }
  return { payload, apply, runChecks, installRenderer };
}

try {
  const controller = makeController(await payloadForPreview());
  globalThis.__wallpaperFixture = controller;
  buttons.apply.onclick = () => {
    const pending = controller.apply();
    const ticket = generation;
    pending.catch(error => { if (ticket === generation) show(error.message); });
  };
  buttons.restore.onclick = restore;
  buttons.checks.onclick = () => controller.runChecks().catch(error => show({ passed: false, error: error.message }));
  buttons.theme.onclick = () => {
    const light = document.documentElement.dataset.theme !== 'light';
    document.documentElement.dataset.theme = light ? 'light' : 'dark';
    buttons.theme.textContent = light ? '深色' : '浅色';
  };
  const initial = controller.apply();
  const initialGeneration = generation;
  try { await initial; } catch (error) { if (initialGeneration === generation) throw error; }
} catch (error) {
  globalThis.__wallpaperFixtureError = error.message;
  show(error.message);
}
