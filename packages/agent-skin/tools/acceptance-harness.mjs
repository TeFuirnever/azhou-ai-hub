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
