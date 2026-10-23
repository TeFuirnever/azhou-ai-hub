// Convert a simplified element array (JSON) into a native .excalidraw scene file.
// Usage: node to-excalidraw.mjs <elements.json> <out.excalidraw>
// elements.json = the exact array sent to the excalidraw MCP create_view,
// with pseudo-elements (cameraUpdate/delete/restoreCheckpoint) removed.
// Element fields: rectangle/ellipse/diamond: x,y,width,height,strokeColor,backgroundColor,
//   label (string, or {text,fontSize,fontFamily}); arrow/line: x,y,points[[dx,dy]..],
//   startBinding/endBinding {elementId}, label (same forms); text: x,y,text,fontSize.
import { readFileSync, writeFileSync } from 'node:fs';

const [,, inPath, outPath] = process.argv;
if (!inPath || !outPath) {
  console.error('usage: node to-excalidraw.mjs <elements.json> <out.excalidraw>');
  process.exit(1);
}

const hash = (s) => {
  let h = 7;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % 2147483000;
};
const labelText = (l) => (typeof l === 'string' ? l : l.text);
const labelFs = (l, d = 16) => (typeof l === 'string' ? d : (l.fontSize ?? d));
const textW = (t, fs) => Math.max(...t.split('\n').map((l) => l.length)) * fs * 0.6;
const textH = (t, fs) => t.split('\n').length * fs * 1.25;

function labelPos(e) {
  if (e.type === 'arrow') {
    const p = e.points;
    if (p.length < 2) return [e.x, e.y];
    if (p.length > 2) {
      const i = Math.floor((p.length - 1) / 2);
      return [e.x + (p[i][0] + p[i + 1][0]) / 2, e.y + (p[i][1] + p[i + 1][1]) / 2];
    }
    return [e.x + (p[0][0] + p[1][0]) / 2, e.y + (p[0][1] + p[1][1]) / 2];
  }
  return [e.x + e.width / 2, e.y + e.height / 2];
}

const SKIP = new Set(['cameraUpdate', 'delete', 'restoreCheckpoint']);
let elements;
try {
  elements = JSON.parse(readFileSync(inPath, 'utf8'));
} catch (err) {
  console.error(`cannot read/parse ${inPath}: ${err.message}`);
  process.exit(1);
}
if (!Array.isArray(elements)) {
  console.error(`input must be a JSON array of elements, got ${typeof elements}`);
  process.exit(1);
}
const els = elements.filter((e) => !SKIP.has(e.type));
elements = els;

const out = [];
const backrefs = {};
const add = (id, ref) => (backrefs[id] ??= []).push(ref);
for (const e of elements) {
  if (e.type === 'arrow') {
    for (const b of [e.startBinding, e.endBinding]) if (b) add(b.elementId, { id: e.id, type: 'arrow' });
    if (e.label) add(e.id, { id: e.id + '_label', type: 'text' });
  } else if (e.label) {
    add(e.id, { id: e.id + '_label', type: 'text' });
  }
}

const base = (id) => ({
  id, angle: 0, groupIds: [], frameId: null, seed: hash(id),
  version: 1, versionNonce: hash(id) + 13, isDeleted: false,
  updated: 1, link: null, locked: false,
});

const textEl = (id, x, y, text, fs, align, valign, containerId, ff = 1, color = '#1e1e1e') => {
  const w = textW(text, fs), h = textH(text, fs);
  return { ...base(id), type: 'text', x, y, width: w, height: h,
    strokeColor: color, backgroundColor: 'transparent', fillStyle: 'solid',
    strokeWidth: 1, strokeStyle: 'solid', roughness: 1, opacity: 100,
    roundness: null, boundElements: null, text, rawText: text, originalText: text,
    fontSize: fs, fontFamily: ff, textAlign: align, verticalAlign: valign,
    containerId, autoResize: true, lineHeight: 1.25 };
};


for (const e of elements) {
    if (e.type === 'text') {
      out.push(textEl(e.id, e.x, e.y, e.text, e.fontSize ?? 20, 'left', 'top', null, e.fontFamily, e.strokeColor ?? '#1e1e1e'));
    } else if (['rectangle', 'ellipse', 'diamond'].includes(e.type)) {
    out.push({ ...base(e.id), type: e.type, x: e.x, y: e.y, width: e.width, height: e.height,
      strokeColor: e.strokeColor ?? '#1e1e1e', backgroundColor: e.backgroundColor ?? 'transparent',
      fillStyle: 'solid', strokeWidth: e.strokeWidth ?? 2, strokeStyle: e.strokeStyle ?? 'solid',
      roughness: 1, opacity: e.opacity ?? 100,
      roundness: e.type === 'rectangle' && e.roundness ? { type: 3 } : null,
      boundElements: backrefs[e.id] ?? null });
    if (e.label != null && labelText(e.label)) {
      const t = labelText(e.label), fs = labelFs(e.label);
      const w = textW(t, fs), h = textH(t, fs);
      const [cx, cy] = [e.x + e.width / 2, e.y + e.height / 2];
      out.push(textEl(e.id + '_label', cx - w / 2, cy - h / 2, t, fs, 'center', 'middle', e.id, typeof e.label === 'object' ? e.label.fontFamily : undefined));
    }
  } else if (e.type === 'arrow' || e.type === 'line') {
    const xs = e.points.map((p) => p[0]), ys = e.points.map((p) => p[1]);
    out.push({ ...base(e.id), type: e.type, x: e.x, y: e.y,
      width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys),
      strokeColor: e.strokeColor ?? '#1e1e1e', backgroundColor: 'transparent',
      fillStyle: 'solid', strokeWidth: e.strokeWidth ?? 2, strokeStyle: e.strokeStyle ?? 'solid',
      roughness: 1, opacity: 100, roundness: null,
      points: e.points, lastCommittedPoint: null,
      startBinding: e.type === 'arrow' && e.startBinding ? { elementId: e.startBinding.elementId, focus: 0, gap: 4, fixedPoint: e.startBinding.fixedPoint } : null,
      endBinding: e.type === 'arrow' && e.endBinding ? { elementId: e.endBinding.elementId, focus: 0, gap: 4, fixedPoint: e.endBinding.fixedPoint } : null,
      startArrowhead: null, endArrowhead: e.type === 'arrow' ? 'arrow' : null,
      ...(e.type === 'line' ? { polygon: e.polygon ?? false } : {}),
      boundElements: backrefs[e.id] ?? null });
    if (e.label != null && labelText(e.label)) {
      const [mx, my] = labelPos(e);
      const t = labelText(e.label), fs = labelFs(e.label);
      const w = textW(t, fs), h = textH(t, fs);
      out.push(textEl(e.id + '_label', mx - w / 2, my - h / 2, t, fs, 'center', 'middle', e.id, typeof e.label === 'object' ? e.label.fontFamily : undefined));
    }
  }
}

writeFileSync(outPath, JSON.stringify({
  type: 'excalidraw', version: 2, source: 'https://excalidraw.com',
  elements: out, appState: { viewBackgroundColor: '#ffffff', gridSize: null }, files: {},
}, null, 1));
console.log(`wrote ${outPath} (${out.length} elements)`);
