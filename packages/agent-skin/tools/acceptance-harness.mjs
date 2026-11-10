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

// Explicit declarations for offline ZCode host acceptance. Call only with a
// real supervisor's observation trail; this validator does not capture a host,
// attest the source of entries, or make L4/L5 real-host checks pass by itself.
// The returned flags are intentionally absent until BOTH capabilities have
// observed facts bound to this precise run and to declared evidence identifiers.
export const ACCEPTANCE_DECLARATION_FACTS = Object.freeze([
  'ownedAppearanceSurface', 'persistentSettings',
]);
const ACCEPTANCE_OUTCOMES = new Set(['observed', 'failed', 'refused', 'unverified']);
const UTC_TIMESTAMP = /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?Z$/;

function acceptanceEpoch(value) {
  if (typeof value !== 'string' || !UTC_TIMESTAMP.test(value)) return null;
  const ms = Date.parse(value);
  if (!Number.isFinite(ms) || new Date(ms).toISOString().slice(0, 19) !== value.slice(0, 19)) return null;
  return ms;
}

function safeAcceptanceId(value) {
  return typeof value === 'string' && value.trim().length > 0 &&
    !/[\r\n\u0000]/.test(value) && Buffer.byteLength(value) <= 256;
}

export function acceptanceDeclarations(run, observations) {
  function refuse(reason) { throw new Error('declaration-refused:' + reason); }
  const validRun = run && typeof run === 'object' && !Array.isArray(run) &&
    safeAcceptanceId(run.runID) && Array.isArray(run.evidenceIDs) &&
    run.evidenceIDs.length > 0 && run.evidenceIDs.every(safeAcceptanceId);
  const started = validRun ? acceptanceEpoch(run.startedAt) : null;
  const ended = validRun ? acceptanceEpoch(run.endedAt) : null;
  if (!validRun || started === null || ended === null || ended < started) refuse('run-invalid');
  if (!Array.isArray(observations)) refuse('observations-not-array');

  const observed = new Set();
  for (let i = 0; i < observations.length; i++) {
    const entry = observations[i];
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) refuse('entry-' + i + '-malformed');
    if (!safeAcceptanceId(entry.fact)) refuse('entry-' + i + '-fact-invalid');
    if (!ACCEPTANCE_OUTCOMES.has(entry.outcome)) refuse('entry-' + i + '-outcome-invalid');
    const at = acceptanceEpoch(entry.observedAt);
    if (at === null) refuse('entry-' + i + '-observedAt-invalid');
    if (entry.runID !== run.runID) refuse('entry-' + i + '-foreign-run');
    if (at < started || at > ended) refuse('entry-' + i + '-outside-window');
    if (ACCEPTANCE_DECLARATION_FACTS.includes(entry.fact)) {
      if (!safeAcceptanceId(entry.evidenceID) || !run.evidenceIDs.includes(entry.evidenceID)) {
        refuse('entry-' + i + '-evidence-unbound');
      }
      if (entry.outcome !== 'observed') refuse('entry-' + i + '-outcome-not-observed');
      observed.add(entry.fact);
    }
  }
  const declarations = {};
  for (const fact of ACCEPTANCE_DECLARATION_FACTS) {
    if (!observed.has(fact)) refuse(fact + '-not-observed');
    declarations[fact] = true;
  }
  return declarations;
}
