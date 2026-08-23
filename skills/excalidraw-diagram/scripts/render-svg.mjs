// Render a diagram to hand-drawn style SVG using roughjs (excalidraw's sketch
// engine) + embedded Virgil font when available.
// Usage: node render-svg.mjs <input.(excalidraw|json)> <out.svg>
// Input may be a native .excalidraw scene ({"type":"excalidraw","elements":[...]})
// or a simplified element array (same schema as to-excalidraw.mjs input).
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const argv = process.argv.slice(2);
const dashIdx = argv.indexOf('-o');
let inPath, outPath;
if (dashIdx >= 0) { inPath = argv[dashIdx - 1]; outPath = argv[dashIdx + 1]; }
else { [inPath, outPath] = argv; }
if (!inPath || !outPath) {
  console.error('usage: node render-svg.mjs <input.(excalidraw|json)> [-o] <out.svg>');
  process.exit(1);
}

let rough, JSDOM;
try {
  rough = (await import('roughjs/bundled/rough.esm.js')).default;
  JSDOM = (await import('jsdom')).JSDOM;
} catch {
  console.error('missing deps — run: cd ' + dirname(fileURLToPath(import.meta.url)) + ' && npm ci --ignore-scripts');
  process.exit(1);
}

const FONT = "Virgil, 'Comic Sans MS', 'Segoe Print', cursive";
// Official fontFamily ids → CSS stacks (see references/element-types.md)
const FONT_STACKS = {
  1: "Virgil, 'Comic Sans MS', 'Segoe Print', cursive",
  2: "Helvetica, 'Liberation Sans', Arial, sans-serif",
  3: "Cascadia, 'Comic Shanns', ui-monospace, monospace",
  5: "Excalifont, Virgil, 'Comic Sans MS', cursive",
};
const fontStack = (f) => FONT_STACKS[f] ?? FONT_STACKS[1];

// Official Excalifont subsets (excalidraw repo packages/excalidraw/fonts/Excalifont/index.ts)
const EXCALIFONT_SUBSETS = [
  ['a88b72a24fb54c9f94e3b5fdaa7481c9', 'U+20-7e,U+a0-a3,U+a5-a6,U+a8-ab,U+ad-b1,U+b4,U+b6-b8,U+ba-ff,U+131,U+152-153,U+2bc,U+2c6,U+2da,U+2dc,U+304,U+308,U+2013-2014,U+2018-201a,U+201c-201e,U+2020,U+2022,U+2024-2026,U+2030,U+2039-203a,U+20ac,U+2122,U+2212'],
  ['be310b9bcd4f1a43f571c46df7809174', 'U+100-130,U+132-137,U+139-149,U+14c-151,U+154-17e,U+192,U+1fc-1ff,U+218-21b,U+237,U+1e80-1e85,U+1ef2-1ef3,U+2113'],
  ['b9dcf9d2e50a1eaf42fc664b50a3fd0d', 'U+400-45f,U+490-491,U+2116'],
  ['41b173a47b57366892116a575a43e2b6', 'U+37e,U+384-38a,U+38c,U+38e-393,U+395-3a1,U+3a3-3a8,U+3aa-3cf,U+3d7'],
  ['3f2c5db56cc93c5a6873b1361d730c16', 'U+2c7,U+2d8-2d9,U+2db,U+2dd,U+302,U+306-307,U+30a-30c,U+326-328,U+212e,U+2211,U+fb01-fb02'],
  ['349fac6ca4700ffec595a7150a0d1e1d', 'U+462-463,U+472-475,U+4d8-4d9,U+4e2-4e3,U+4e6-4e9,U+4ee-4ef'],
  ['623ccf21b21ef6b3a0d87738f77eb071', 'U+300-301,U+303'],
];

const b64File = (p) => (existsSync(p) ? readFileSync(p).toString('base64') : null);
function fontFaceCss(usedFamilies) {
  const here = dirname(fileURLToPath(import.meta.url));
  const refs = join(here, '..', 'references');
  const faces = [];
  if (usedFamilies.has(1)) {
    const v = b64File(join(refs, 'fonts', 'Virgil', 'Virgil-Regular.woff2'));
    if (v) faces.push(`@font-face{font-family:'Virgil';src:url(data:font/woff2;base64,${v}) format('woff2');}`);
  }
  if (usedFamilies.has(3)) {
    const c = b64File(join(refs, 'fonts', 'Cascadia', 'CascadiaCode-Regular.woff2'));
    if (c) faces.push(`@font-face{font-family:'Cascadia';src:url(data:font/woff2;base64,${c}) format('woff2');}`);
  }
  if (usedFamilies.has(5)) {
    for (const [hash, range] of EXCALIFONT_SUBSETS) {
      const f = b64File(join(refs, 'fonts', 'Excalifont', `Excalifont-Regular-${hash}.woff2`));
      if (f) faces.push(`@font-face{font-family:'Excalifont';src:url(data:font/woff2;base64,${f}) format('woff2');unicode-range:${range};}`);
    }
  }
  return faces.length ? `<style>${faces.join('')}</style>\n` : '';
}
function usedFontFamilies(elements) {
  const used = new Set();
  for (const e of elements) {
    if (e.type === 'text' && e.text != null) used.add(e.fontFamily ?? 1);
    else if (e.label) used.add(e.label.fontFamily ?? 1);
  }
  return used;
}

let raw;
try {
  raw = JSON.parse(readFileSync(inPath, 'utf8'));
} catch (err) {
  console.error(`cannot read/parse ${inPath}: ${err.message}`);
  process.exit(1);
}
const native = raw.type === 'excalidraw' && Array.isArray(raw.elements);
const elements = (native ? raw.elements.filter((e) => !e.isDeleted) : raw)
  .filter((e) => ['rectangle', 'ellipse', 'diamond', 'arrow', 'text', 'line', 'freedraw'].includes(e.type));

const dom = new JSDOM('<!DOCTYPE html>');
const doc = dom.window.document;
const NS = 'http://www.w3.org/2000/svg';
const svg = doc.createElementNS(NS, 'svg');
const rc = rough.svg(svg);

const hash = (s) => {
  let h = 7;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % 2147483000;
};
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const dashFor = (ss) => (ss === 'dashed' ? '10,8' : ss === 'dotted' ? '2,6' : null);
const applyDash = (node, ss) => {
  const dash = dashFor(ss);
  if (dash) for (const p of node.querySelectorAll('path')) p.setAttribute('stroke-dasharray', dash);
};

const bounds = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
const track = (x0, y0, x1, y1) => {
  bounds.minX = Math.min(bounds.minX, x0); bounds.minY = Math.min(bounds.minY, y0);
  bounds.maxX = Math.max(bounds.maxX, x1); bounds.maxY = Math.max(bounds.maxY, y1);
};
const chunks = [];
// Wrap text to maxW so bound labels stay inside their container (the official
// engine auto-wraps; this mirrors it for the local renderer). Word-based, keeps
// manual \n. Virgil runs wider than Helvetica — budget 0.62 × fontSize per char.
const wrapTo = (body, size, maxW) => {
  const charW = size * 0.62;
  const out = [];
  for (const para of String(body).split('\n')) {
    if (para.length * charW <= maxW) { out.push(para); continue; }
    let line = '';
    for (const word of para.split(/\s+/)) {
      const cand = line ? line + ' ' + word : word;
      if (cand.length * charW <= maxW || !line) line = cand;
      else { out.push(line); line = word; }
    }
    if (line) out.push(line);
  }
  return out.join('\n');
};
const text = (cx, cy, body, size, fill, anchor, ff = 1, maxW = 0) => {
  if (maxW > 0) body = wrapTo(body, size, maxW);
  const lines = String(body).split('\n');
  const lh = size * 1.3;
  const y0 = cy - ((lines.length - 1) * lh) / 2;
  const tspans = lines.map((l, i) => `<tspan x="${cx}" dy="${i === 0 ? 0 : lh}">${esc(l)}</tspan>`).join('');
  chunks.push(`<text x="${cx}" y="${y0}" font-size="${size}" font-family="${fontStack(ff)}" fill="${fill}" text-anchor="${anchor}" dominant-baseline="middle">${tspans}</text>`);
};

for (const e of elements) {
  // harden against string coordinates (string + number concat explodes bounds)
  for (const k of ['x', 'y', 'width', 'height', 'fontSize']) {
    if (e[k] != null && typeof e[k] !== 'number') e[k] = Number(e[k]) || 0;
  }
  const seed = hash(e.id ?? String(e.x) + e.y);
  const stroke = e.strokeColor ?? '#1e1e1e';
  const sw = e.strokeWidth ?? 2;
  const fill = e.backgroundColor && e.backgroundColor !== 'transparent' ? e.backgroundColor : undefined;
  const ropts = { stroke, strokeWidth: sw, roughness: sw === 1 ? 0.9 : 1.2, bowing: 1, seed, fill, fillStyle: 'solid' };
  let node = null;
  if (e.type === 'rectangle') node = rc.rectangle(e.x, e.y, e.width, e.height, ropts);
  else if (e.type === 'ellipse') node = rc.ellipse(e.x + e.width / 2, e.y + e.height / 2, e.width, e.height, ropts);
  else if (e.type === 'diamond') {
    const cx = e.x + e.width / 2, cy = e.y + e.height / 2;
    node = rc.polygon([[cx, e.y], [e.x + e.width, cy], [cx, e.y + e.height], [e.x, cy]], ropts);
  }
  if (node) {
    if (e.opacity != null && e.opacity < 100) node.setAttribute('opacity', String(e.opacity / 100));
    applyDash(node, e.strokeStyle);
    svg.appendChild(node);
    track(e.x, e.y, e.x + e.width, e.y + e.height);
    if (e.label) text(e.x + e.width / 2, e.y + e.height / 2, e.label.text, e.label.fontSize ?? 16, '#1e1e1e', 'middle', e.label.fontFamily ?? 1, e.width - 16);
    continue;
  }
  if (e.type === 'freedraw') {
    const pts = (e.points ?? [[0, 0]]).map(([dx, dy]) => [e.x + dx, e.y + dy]);
    if (pts.length > 1) {
      const seg = rc.curve(pts, { stroke, strokeWidth: Math.max(1, sw * 0.8), roughness: 0.35, bowing: 0.2, seed });
      if (e.opacity != null && e.opacity < 100) seg.setAttribute('opacity', String(e.opacity / 100));
      svg.appendChild(seg);
      track(...pts.reduce(([a, b], [x, y]) => [Math.min(a, x), Math.min(b, y)], [Infinity, Infinity]),
        ...pts.reduce(([a, b], [x, y]) => [Math.max(a, x), Math.max(b, y)], [-Infinity, -Infinity]));
    }
    continue;
  }
  if (e.type === 'arrow' || e.type === 'line') {
    const pts = (e.points ?? [[0, 0]]).map(([dx, dy]) => [e.x + dx, e.y + dy]);
    for (let i = 0; i < pts.length - 1; i++) {
      const seg = rc.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], { stroke, strokeWidth: sw, roughness: 0.9, seed: seed + i });
      applyDash(seg, e.strokeStyle);
      svg.appendChild(seg);
    }
    if (e.type === 'arrow' && (e.endArrowhead ?? 'arrow') !== 'none') {
      const [tx, ty] = pts[pts.length - 1];
      const [px, py] = pts[pts.length - 2] ?? pts[pts.length - 1];
      let dx = tx - px, dy = ty - py;
      const L = Math.hypot(dx, dy) || 1; dx /= L; dy /= L;
      for (const s of [-0.42, 0.42]) {
        const wx = tx - 12 * (dx * Math.cos(s) - dy * Math.sin(s));
        const wy = ty - 12 * (dx * Math.sin(s) + dy * Math.cos(s));
        svg.appendChild(rc.line(tx, ty, wx, wy, { stroke, strokeWidth: sw, roughness: 0.6, seed: seed + 500 + s * 100 }));
      }
    }
    track(...pts.reduce(([a, b], [x, y]) => [Math.min(a, x), Math.min(b, y)], [Infinity, Infinity]),
      ...pts.reduce(([a, b], [x, y]) => [Math.max(a, x), Math.max(b, y)], [-Infinity, -Infinity]));
    if (e.label) {
      const p = e.points;
      let mx, my;
      if (p.length > 2) {
        const i = Math.floor((p.length - 1) / 2);
        mx = e.x + (p[i][0] + p[i + 1][0]) / 2; my = e.y + (p[i][1] + p[i + 1][1]) / 2;
      } else { mx = e.x + (p[0][0] + p[1][0]) / 2; my = e.y + (p[0][1] + p[1][1]) / 2; }
      chunks.push(`<text x="${mx}" y="${my}" font-size="${e.label.fontSize ?? 16}" font-family="${fontStack(e.label.fontFamily ?? 1)}" fill="#1e1e1e" text-anchor="middle" dominant-baseline="middle" paint-order="stroke" stroke="#ffffff" stroke-width="5" stroke-linejoin="round">${esc(e.label.text)}</text>`);
    }
    continue;
  }
  if (e.type === 'text') {
    const fs = e.fontSize ?? 20;
    const w = e.width ?? Math.max(...String(e.text).split('\n').map((l) => l.length)) * fs * 0.6;
    const h = e.height ?? String(e.text).split('\n').length * fs * 1.25;
    const fill = e.strokeColor ?? '#1e1e1e';
    if (e.textAlign === 'center') text(e.x + w / 2, e.y + h / 2, e.text, fs, fill, 'middle', e.fontFamily);
    else text(e.x, e.y + h / 2, e.text, fs, fill, 'start', e.fontFamily);
    track(e.x, e.y, e.x + w, e.y + h);
  }
}

const pad = 34;
const vb = `${bounds.minX - pad} ${bounds.minY - pad} ${bounds.maxX - bounds.minX + pad * 2} ${bounds.maxY - bounds.minY + pad * 2}`;
const g = doc.createElementNS(NS, 'g');
for (const child of [...svg.childNodes]) g.appendChild(child);

const title = esc(outPath.replace(/.*[\\/]/, '').replace(/\.[^.]*$/, '') || 'diagram');

const fontCss = fontFaceCss(usedFontFamilies(elements));
writeFileSync(outPath, `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}">\n<title>${title}</title>\n${fontCss}<rect x="${bounds.minX - pad}" y="${bounds.minY - pad}" width="${bounds.maxX - bounds.minX + pad * 2}" height="${bounds.maxY - bounds.minY + pad * 2}" fill="#ffffff"/>\n${new dom.window.XMLSerializer().serializeToString(g)}\n${chunks.join('\n')}\n</svg>\n`);
console.log(`wrote ${outPath}`);
