// Shadow-aware read-only CDP DOM probe for a launched ZCode instance (design
// doc L4/F5: replaces the shadow-blind .local probes with a git-owned tool).
// The sidebar entry chip lives inside an open shadow root, so textContent/
// innerHTML/document.querySelectorAll are blind to it; the chip is probed via
// [data-agent-skin-entry].shadowRoot instead (P5.1). Every expression sent to
// the page is a pure read (getter calls only) - nothing here may change page
// state. Import as ESM (probeDom and helpers) or run as a CLI:
//   node tools/probe_dom.mjs [--receipt PATH] [--port N] [--timeout MS]
// Exit 0: probe completed (verdicts on the JSON are the caller's job).
// Exit 2: infrastructure failure (receipt/page/CDP unreachable).
import fs from 'node:fs';
import http from 'node:http';
import { fileURLToPath } from 'node:url';

export const PROBE_SCHEMA = 1;
export const PROBE_KIND = 'zcode-dom-probe';
// Written by Native/App.swift makeZCodeDriver: pid/launchTime/port/executableSHA256.
export const DEFAULT_RECEIPT = 'Library/Application Support/Azhou AI Lab/ZCode/launch-receipt.json';
export const DEFAULT_TIMEOUT_MS = 10000;
const RENDERER_SUFFIX = '/out/renderer/index.html';

export function defaultReceiptPath(home = process.env.HOME) {
  if (!home) throw new Error('receipt-path-unknown-home');
  return `${home}/${DEFAULT_RECEIPT}`;
}

// Parse and validate a launch receipt body; throws stable error codes.
export function parseReceipt(text) {
  let value;
  try { value = JSON.parse(String(text)); } catch { throw new Error('receipt-not-json'); }
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('receipt-not-object');
  const port = value.port, pid = value.pid;
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('receipt-port-invalid');
  if (!Number.isInteger(pid) || pid < 1) throw new Error('receipt-pid-invalid');
  const executableSHA256 = value.executableSHA256;
  if (typeof executableSHA256 !== 'string' || !/^[0-9a-f]{64}$/.test(executableSHA256)) {
    throw new Error('receipt-sha-invalid');
  }
  const launchTime = value.launchTime;
  if (typeof launchTime !== 'number' || !Number.isFinite(launchTime) || launchTime <= 0) {
    throw new Error('receipt-launch-time-invalid');
  }
  return { port, pid, launchTime, executableSHA256 };
}

export function readReceipt(path = defaultReceiptPath()) {
  let text;
  try { text = fs.readFileSync(path, 'utf8'); } catch { throw new Error('receipt-unreadable:' + path); }
  const receipt = parseReceipt(text);
  receipt.path = String(path);
  return receipt;
}

// Renderer page targets of the packaged ZCode index; query/hash-insensitive
// (rc35: CDP URLs carry ?locale=..., exact-suffix matching found zero pages).
export function rendererPages(targets) {
  if (!Array.isArray(targets)) return [];
  return targets.filter(target => {
    if (!target || target.type !== 'page' || typeof target.url !== 'string') return false;
    const url = target.url.split('?')[0].split('#')[0];
    return url.startsWith('file://') && url.endsWith(RENDERER_SUFFIX);
  });
}

// Read-only page expressions. Each is an IIFE over document that only calls
// getters; none of them assign, call setters, or dispatch events.
export const READ_EXPRESSIONS = Object.freeze({
  // Both ZCode wallpaper surfaces carry data-azhou-zcode-wallpaper-surface
  // (extension/hosts/zcode.mjs): #root (full window) and main (main pane).
  wallpaperSurfaces: `(() => {
    const rect = (node) => { const r = node.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) }; };
    const root = document.getElementById('root');
    return Array.from(document.querySelectorAll('[data-azhou-zcode-wallpaper-surface]')).map((node) => ({
      tag: node.tagName, role: node === root ? 'root' : (node.tagName === 'MAIN' ? 'main' : 'other'),
      marker: node.getAttribute('data-azhou-zcode-wallpaper-surface'), rect: rect(node),
    }));
  })()`,
  documentWallpaper: `document.documentElement.getAttribute('data-azhou-wallpaper')`,
  // The entry chip: host span in the light DOM, label/avatar/aria inside its
  // open shadow root. Probing the light DOM for the label is a known false
  // negative - the shadow boundary must be crossed here.
  entryChip: `(() => {
    const host = document.querySelector('[data-agent-skin-entry]');
    if (!host) return { found: false, shadowRoot: false, reason: 'host-not-in-light-dom' };
    const shadow = host.shadowRoot;
    const rectOf = (node) => { const r = node.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) }; };
    if (!shadow) return { found: true, shadowRoot: false, attribute: host.getAttribute('data-agent-skin-entry'),
      reason: 'no-open-shadow-root', rect: rectOf(host), inSidebar: host.closest('aside[data-testid="sidebar"]') !== null };
    const button = shadow.querySelector('button');
    const label = shadow.querySelector('.lbl');
    const avatar = shadow.querySelector('img');
    const rect = rectOf(host);
    return {
      found: true, shadowRoot: true, attribute: host.getAttribute('data-agent-skin-entry'),
      label: label ? label.textContent : null,
      ariaLabel: button ? button.getAttribute('aria-label') : null,
      title: button ? button.getAttribute('title') : null,
      avatar: avatar ? { present: true, complete: avatar.complete,
        naturalWidth: avatar.naturalWidth, naturalHeight: avatar.naturalHeight,
        srcKind: String(avatar.getAttribute('src') || '').startsWith('data:image/png;base64,') ? 'data-url' : 'other' }
        : { present: false, complete: false, naturalWidth: 0, naturalHeight: 0, srcKind: 'none' },
      rect,
      visible: rect.width > 0 && rect.height > 0,
      inSidebar: host.closest('aside[data-testid="sidebar"]') !== null,
      sidebarCount: document.querySelectorAll('aside[data-testid="sidebar"]').length,
      pageVisible: document.visibilityState,
    };
  })()`,
});

export function httpGetJson(host, port, path, timeoutMs = DEFAULT_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const request = http.get({ host, port, path, timeout: timeoutMs }, response => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', chunk => { body += chunk; });
      response.on('end', () => {
        try { resolve(JSON.parse(body)); } catch { reject(new Error('targets-not-json')); }
      });
    });
    request.on('error', error => reject(error));
    request.on('timeout', () => { request.destroy(); reject(new Error('http-timeout:' + path)); });
  });
}

// Minimal CDP client over the global WebSocket (Node >= 22).
export function openCdp(webSocketDebuggerUrl, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  let sequence = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    let message;
    try { message = JSON.parse(String(event.data)); } catch { return; }
    const entry = pending.get(message.id);
    if (!entry) return;
    pending.delete(message.id);
    clearTimeout(entry.timer);
    if (message.error) entry.reject(new Error('cdp-error:' + JSON.stringify(message.error).slice(0, 200)));
    else entry.resolve(message.result);
  });
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('cdp-timeout:' + method)); }, timeoutMs);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const opened = new Promise((resolve, reject) => {
    socket.addEventListener('open', () => resolve());
    socket.addEventListener('error', () => reject(new Error('cdp-socket-error')));
  });
  const close = () => { try { socket.close(); } catch { /* already closed */ } };
  return { call, opened, close };
}

// Evaluate a read-only expression and return its JSON value.
export async function evaluateReadonly(cdp, expression) {
  const result = await cdp.call('Runtime.evaluate', { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error('evaluate-failed:' + expression.slice(0, 60));
  return result.result.value;
}

// Probe a live ZCode renderer. Options: receiptPath | port, host, timeoutMs.
// Resolves with the probe JSON (verdict-free); rejects on infrastructure errors.
export async function probeDom(options = {}) {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const host = options.host ?? '127.0.0.1';
  const receipt = options.port ? { port: options.port, path: null } : readReceipt(options.receiptPath);
  const targets = await httpGetJson(host, receipt.port, '/json', timeoutMs);
  const pages = rendererPages(targets);
  if (pages.length !== 1) throw new Error('renderer-page-not-unique:' + pages.length);
  const page = pages[0];
  const cdp = openCdp(page.webSocketDebuggerUrl, timeoutMs);
  try {
    await cdp.opened;
    const surfaces = await evaluateReadonly(cdp, READ_EXPRESSIONS.wallpaperSurfaces);
    const documentElement = await evaluateReadonly(cdp, READ_EXPRESSIONS.documentWallpaper);
    const entry = await evaluateReadonly(cdp, READ_EXPRESSIONS.entryChip);
    return {
      kind: PROBE_KIND, schema: PROBE_SCHEMA, port: receipt.port,
      page: { url: page.url, targetId: page.id ?? null, receiptPath: receipt.path },
      wallpaper: { documentElement, surfaces },
      entry,
      probedAt: Date.now(),
    };
  } finally {
    cdp.close();
  }
}

function parseArguments(argv) {
  const options = { timeoutMs: DEFAULT_TIMEOUT_MS };
  for (let index = 2; index < argv.length; index += 1) {
    const argument = argv[index];
    const next = () => {
      if (index + 1 >= argv.length) throw new Error('option-missing-value:' + argument);
      index += 1;
      return argv[index];
    };
    if (argument === '--receipt') options.receiptPath = next();
    else if (argument === '--port') options.port = Number.parseInt(next(), 10);
    else if (argument === '--timeout') options.timeoutMs = Number.parseInt(next(), 10);
    else throw new Error('option-unknown:' + argument);
  }
  if (options.port !== undefined && !Number.isInteger(options.port)) throw new Error('option-port-invalid');
  return options;
}

export async function main(argv = process.argv) {
  let options;
  try { options = parseArguments(argv); } catch (error) {
    console.error(String(error.message));
    return 2;
  }
  try {
    const probe = await probeDom(options);
    console.log(JSON.stringify(probe));
    return 0;
  } catch (error) {
    console.error(String(error.message || error));
    return 2;
  }
}

const invokedPath = process.argv[1] ? fileURLToPath(import.meta.url) === process.argv[1] : false;
if (invokedPath) {
  main().then(code => process.exit(code), error => { console.error(String(error)); process.exit(2); });
}
