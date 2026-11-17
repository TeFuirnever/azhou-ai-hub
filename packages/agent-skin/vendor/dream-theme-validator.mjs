// Derived from Codex-Dream-Skin 6fc42df48a6a5365011f55cc349e20c038e56d1d.
// Copyright (c) 2026 Codex Dream Skin Studio contributors. MIT, see dream-theme-validator.LICENSE.
const BACKGROUND_MEDIA = new Map([
  ["background.webp", "image/webp"],
  ["background.jpg", "image/jpeg"],
  ["background.png", "image/png"],
]);

const THEME_REQUIRED = ["schemaVersion", "id", "name", "image"];
const THEME_COPY_KEYS = [
  "brandSubtitle",
  "tagline",
  "projectPrefix",
  "projectLabel",
  "statusText",
  "quote",
  "promoTitle",
  "promoSub",
];
const COLOR_KEYS = [
  "background",
  "panel",
  "panelAlt",
  "accent",
  "accentAlt",
  "secondary",
  "highlight",
  "text",
  "muted",
  "line",
];

const THEME_ID_PATTERN = /^[a-z0-9]+(?:[.-][a-z0-9]+)*$/;

const CONTROL_PATTERN = /[\u0000-\u001f\u007f]/u;

const COLOR_PATTERN = /^(#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?|#[0-9a-fA-F]{3,4}|rgb\(\s*[0-9]{1,3}\s*,\s*[0-9]{1,3}\s*,\s*[0-9]{1,3}\s*\)|rgba\(\s*[0-9]{1,3}\s*,\s*[0-9]{1,3}\s*,\s*[0-9]{1,3}\s*,\s*(0|1|1\.0|0?\.[0-9]{1,6})\s*\))$/;

function fail(message) {
  throw new Error(message);
}

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function assertObject(value, label) {
  if (!isObject(value)) fail(`${label} must be an object`);
  return value;
}

function assertExactKeys(value, required, optional, label) {
  const allowed = new Set([...required, ...optional]);
  for (const key of required) {
    if (!Object.hasOwn(value, key)) fail(`${label} is missing ${key}`);
  }
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) fail(`${label} contains unsupported field ${key}`);
  }
}

export function codePointLength(value) {
  return Array.from(value).length;
}

function assertString(value, label, { min = 0, max, pattern, controls = CONTROL_PATTERN } = {}) {
  if (typeof value !== "string") fail(`${label} must be a string`);
  const length = codePointLength(value);
  if (length < min || (max !== undefined && length > max)) fail(`${label} has an invalid length`);
  if (controls?.test(value)) fail(`${label} contains control characters`);
  if (pattern && !pattern.test(value)) fail(`${label} has an invalid format`);
  return value;
}

function validateOfficialTheme(value) {
  const theme = assertObject(value, "theme.json");
  assertExactKeys(
    theme,
    THEME_REQUIRED,
    [...THEME_COPY_KEYS, "promoUrl", "appearance", "art", "colors"],
    "theme.json",
  );
  if (theme.schemaVersion !== 1) fail("theme.json must use schemaVersion 1");
  assertString(theme.id, "theme.json.id", { min: 3, max: 64, pattern: THEME_ID_PATTERN, controls: null });
  assertString(theme.name, "theme.json.name", { min: 1, max: 80 });
  assertString(theme.image, "theme.json.image", { min: 1, max: 32, controls: null });
  if (!BACKGROUND_MEDIA.has(theme.image)) fail("theme.json.image must name one registered background file");
  for (const key of THEME_COPY_KEYS) {
    if (theme[key] !== undefined) assertString(theme[key], `theme.json.${key}`, { max: 120 });
  }
  if (theme.promoUrl !== undefined) assertString(theme.promoUrl, "theme.json.promoUrl", { max: 512 });
  if (theme.appearance !== undefined && !new Set(["auto", "light", "dark"]).has(theme.appearance)) {
    fail("theme.json.appearance is unsupported");
  }
  if (theme.art !== undefined) {
    const art = assertObject(theme.art, "theme.json.art");
    assertExactKeys(art, [], ["focusX", "focusY", "safeArea", "taskMode"], "theme.json.art");
    for (const key of ["focusX", "focusY"]) {
      if (art[key] !== undefined && (typeof art[key] !== "number" || !Number.isFinite(art[key]) || art[key] < 0 || art[key] > 1)) {
        fail(`theme.json.art.${key} must be between 0 and 1`);
      }
    }
    if (art.safeArea !== undefined && !new Set(["left", "right", "none"]).has(art.safeArea)) {
      fail("theme.json.art.safeArea is unsupported");
    }
    if (art.taskMode !== undefined && !new Set(["ambient", "full", "off"]).has(art.taskMode)) {
      fail("theme.json.art.taskMode is unsupported");
    }
  }
  if (theme.colors !== undefined) {
    const colors = assertObject(theme.colors, "theme.json.colors");
    assertExactKeys(colors, COLOR_KEYS, [], "theme.json.colors");
    for (const key of COLOR_KEYS) {
      assertString(colors[key], `theme.json.colors.${key}`, {
        min: 1,
        max: 64,
        pattern: COLOR_PATTERN,
        controls: null,
      });
    }
  }
  return theme;
}

export { validateOfficialTheme };
