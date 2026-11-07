// Offline acceptance harness helpers. Shared by the supervisor-stage capture
// and any future offline acceptance runner, so the two mechanical failure
// classes from the 2026-11 rc35 rounds stay fixed in tested code:
//   1. CDP target URLs carry ?query/#hash (`…/index.html?locale=en-GB`);
//      exact-suffix matching finds zero pages.
//   2. Pre-created output directories made fs.mkdirSync throw EEXIST.
import fs from 'node:fs';

// Strip query and fragment before any suffix match on a CDP target URL.
export function stripUrlForMatch(url) {
  return String(url).split('?')[0].split('#')[0];
}

// Parse a /json target list; throw the stable capture error on bad input.
export function parseTargets(body) {
  try { return JSON.parse(String(body)); } catch { throw new Error('targets-not-json'); }
}

// Page targets whose URL is the packaged renderer index, query/hash-insensitive.
export function mainPageTargets(targets) {
  if (!Array.isArray(targets)) return [];
  return targets.filter(t => {
    if (!t || t.type !== 'page' || typeof t.url !== 'string') return false;
    const url = stripUrlForMatch(t.url);
    return url.startsWith('file://') && url.endsWith('/out/renderer/index.html');
  });
}

// The single main page, or throw the supervisor error contract.
export function singleMainPage(targets) {
  const pages = mainPageTargets(targets);
  if (pages.length !== 1) throw new Error('main-page-not-unique:' + pages.length);
  return pages[0];
}

// Idempotent 0o700 directory creation; an existing directory is fine.
export function ensureDir(path) {
  fs.mkdirSync(path, { mode: 0o700, recursive: true });
}

// Alpha of a computed CSS color, or null when it carries no alpha channel.
export function colorAlpha(color) {
  const m = String(color ?? '').match(/rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?\)/);
  if (!m) return null;
  return m[4] === undefined ? 1 : parseFloat(m[4]);
}

// Chain entries (innermost first) that paint an opaque background over the
// wallpaper layer. The 2026-11-07 rc36 round found the real-workspace main
// pane hidden behind an opaque ancestor <section> the controller-state checks
// never see; this is the decision core of the pixel-protection assertion.
export function wallpaperBlockers(chain) {
  if (!Array.isArray(chain)) return [];
  return chain.filter(entry => {
    if (!entry || typeof entry !== 'object') return false;
    if (entry.tag === 'MAIN') return false; // main itself is marker-controlled
    const alpha = colorAlpha(entry.bg);
    return alpha !== null && alpha > 0.5;
  });
}
