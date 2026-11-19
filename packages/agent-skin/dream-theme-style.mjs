import { parseSafeCssAst } from './vendor/dream-safe-css-ast.mjs';
import { validateOfficialTheme } from './vendor/dream-theme-validator.mjs';

export const DREAM_PAINT_PROFILE = 'codex-main-literal-paint/v1';

function literalRgba(value) {
  const literal = value.toLowerCase();
  if (literal === 'transparent') return [0, 0, 0, 0];
  if (literal.startsWith('#')) {
    let hex = literal.slice(1);
    if (hex.length <= 4) hex = [...hex].map(character => character + character).join('');
    return [0, 2, 4].map(offset => Number.parseInt(hex.slice(offset, offset + 2), 16))
      .concat(hex.length === 8 ? Number.parseInt(hex.slice(6), 16) / 255 : 1);
  }
  const match = /^(rgb|rgba)\((.*)\)$/i.exec(literal);
  if (!match) throw new Error('dream_profile_unmapped_color');
  const channels = match[2].split(',').map(part => part.trim());
  const rgba = channels.slice(0, 3).map(part => part.endsWith('%') ? Number(part.slice(0, -1)) * 255 / 100 : Number(part));
  const alpha = channels[3];
  rgba.push(alpha === undefined ? 1 : alpha.endsWith('%') ? Number(alpha.slice(0, -1)) / 100 : Number(alpha));
  return rgba;
}

// The pristine parser validates every source declaration first. This adapter consumes
// its AST, not compiled selectors, and cannot silently discard an unsupported rule.
export function mapDreamTheme(manifest, source) {
  validateOfficialTheme(manifest);
  if (Object.keys(manifest).length !== 4) throw new Error('dream_profile_unmapped_manifest');
  const parsed = parseSafeCssAst(source);
  const steps = [];
  for (const {selector, declarations} of parsed.rules) {
    if (selector.part !== 'main' || selector.state) throw new Error('dream_profile_unmapped_selector');
    for (const {property, value} of declarations) {
      if (property !== 'background-color') throw new Error('dream_profile_unmapped_declaration');
      steps.push(Object.freeze({rgba: Object.freeze(literalRgba(value)), backgroundImage: 'none'}));
    }
  }
  return Object.freeze({profile: DREAM_PAINT_PROFILE, ruleCount: parsed.ruleCount,
    declarationCount: parsed.declarationCount, steps: Object.freeze(steps)});
}

const HASH = /^[0-9a-f]{64}$/;

function requireValue(condition, reason) {
  if (!condition) throw new Error(reason);
}

function exactKeys(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}

export function validateThemeSnapshot(value) {
  requireValue(value && typeof value === 'object' && !Array.isArray(value), 'dream_snapshot_invalid');
  requireValue(Number.isSafeInteger(value.revision) && value.revision >= 1
    && typeof value.imagesBinding === 'string' && HASH.test(value.imagesBinding), 'dream_snapshot_invalid');
  let selection;
  if (value.schemaVersion === 1) {
    requireValue(exactKeys(value,['schemaVersion','revision','activeThemeId','preferencesByTheme','imagesBinding'])
      && value.activeThemeId === 'azhou-q-v3' && exactKeys(value.preferencesByTheme,['azhou-q-v3']), 'dream_snapshot_invalid');
    selection = {kind:'bundled',id:'azhou-q-v3',surfaceTransparency:value.preferencesByTheme['azhou-q-v3']};
  } else {
    requireValue(value.schemaVersion === 2 && exactKeys(value,['schemaVersion','revision','imagesBinding','selection']), 'dream_snapshot_invalid');
    selection = value.selection;
  }
  requireValue(exactKeys(selection,['kind','id','surfaceTransparency'])
    && selection.kind === 'bundled' && selection.id === 'azhou-q-v3', 'dream_snapshot_invalid');
  const preference = selection.surfaceTransparency;
  requireValue((exactKeys(preference,['mode']) && preference.mode === 'follow')
    || (exactKeys(preference,['mode','value']) && preference.mode === 'override'
      && typeof preference.value === 'number' && Number.isFinite(preference.value)
      && preference.value >= 0 && preference.value <= 100), 'dream_snapshot_invalid');
  const normalized = Object.freeze({kind:'bundled',id:'azhou-q-v3',surfaceTransparency:Object.freeze({...preference})});
  return Object.freeze({schemaVersion:2,revision:value.revision,imagesBinding:value.imagesBinding,selection:normalized});
}
