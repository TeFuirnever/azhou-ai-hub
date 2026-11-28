import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

export async function until(predicate, description, timeout = 10_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const value = await predicate();
    if (value) return value;
    await delay(25);
  }
  throw new Error(`Timed out: ${description}`);
}

// A fresh headless process, profile and browser context keep these checks apart
// from personal browser sessions. CDP supplies real input and permission APIs.
export async function launchChrome() {
  const profile = await mkdtemp(join(tmpdir(), "azhou-site-browser-"));
  // Headless runners may have no physical mouse. Match the desktop input this suite sends.
  // Chromium's pointer and hover bitfields use 4 for fine and 2 for hover.
  const desktopPointer = "--blink-settings=primaryPointerType=4,availablePointerTypes=4,primaryHoverType=2,availableHoverTypes=2";
  const args = ["--headless", "--no-first-run", "--disable-background-networking",
    "--disable-dev-shm-usage", "--remote-debugging-port=0", desktopPointer, `--user-data-dir=${profile}`, "about:blank"];
  if (process.getuid?.() === 0) args.push("--no-sandbox");
  const child = spawn(process.env.CHROME_BIN || "google-chrome", args, { stdio: ["ignore", "ignore", "pipe"] });
  let exited = false, startupError, stderr = "", socket;
  const closed = new Promise(resolve => child.once("close", () => { exited = true; resolve(); }));
  child.once("error", error => { startupError = error; });
  child.stderr.on("data", bytes => { stderr = (stderr + bytes).slice(-8000); });
  const pending = new Map(), listeners = new Set();
  let sequence = 0;
  const close = async () => {
    socket?.close();
    if (!exited) child.kill("SIGTERM");
    const timer = setTimeout(() => { if (!exited) child.kill("SIGKILL"); }, 3000);
    try { await closed; } finally { clearTimeout(timer); }
    await rm(profile, { recursive: true, force: true });
  };
  try {
    const endpoint = await until(async () => {
      if (startupError) throw startupError;
      if (exited) throw new Error(`Chrome exited before opening CDP: ${stderr}`);
      try {
        const [port, path] = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).trim().split("\n");
        return port && path ? `ws://127.0.0.1:${port}${path}` : false;
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
        return false;
      }
    }, "Chrome debugging endpoint", 15_000);
    socket = new WebSocket(endpoint);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Chrome WebSocket connection timed out")), 10_000);
      socket.addEventListener("open", () => { clearTimeout(timer); resolve(); }, { once: true });
      socket.addEventListener("error", () => { clearTimeout(timer); reject(new Error("Chrome WebSocket connection failed")); }, { once: true });
    });
    socket.addEventListener("message", ({ data }) => {
      const message = JSON.parse(data);
      if (message.id) {
        const request = pending.get(message.id);
        if (!request) return;
        pending.delete(message.id);
        clearTimeout(request.timer);
        if (message.error) request.reject(new Error(`${request.method}: ${message.error.message}`));
        else request.resolve(message.result);
      } else {
        for (const listener of listeners) listener(message);
      }
    });
    socket.addEventListener("close", () => {
      for (const request of pending.values()) {
        clearTimeout(request.timer);
        request.reject(new Error(`Chrome disconnected during ${request.method}`));
      }
      pending.clear();
    });
    const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
      if (socket.readyState !== WebSocket.OPEN) return reject(new Error(`Chrome is not connected: ${method}`));
      const id = ++sequence;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`CDP timed out: ${method}`));
      }, 10_000);
      pending.set(id, { resolve, reject, timer, method });
      socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
    return {
      close,
      version: await send("Browser.getVersion"),
      async page(origin, { javascript = true, width = 1200 } = {}) {
        const { browserContextId } = await send("Target.createBrowserContext");
        try {
          const { targetId } = await send("Target.createTarget", { url: "about:blank", browserContextId });
          const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
          const command = (method, params) => send(method, params, sessionId);
          const responses = [], exceptions = [], loaded = new Set();
          const sessions = new Set([sessionId]);
          const listener = message => {
            if (!sessions.has(message.sessionId)) return;
            if (message.method === "Target.attachedToTarget") {
              const worker = message.params.sessionId;
              sessions.add(worker);
              // Pagefind fetches its WASM and fragments from a worker. Observe
              // that target before resuming it so an empty page-only network
              // log cannot conceal a missing or substituted real index.
              (async () => {
                await send("Network.enable", {}, worker);
                await send("Runtime.enable", {}, worker);
                await send("Network.setBlockedURLs", { urls: ["https://*"] }, worker);
                await send("Runtime.runIfWaitingForDebugger", {}, worker);
              })().catch(error => exceptions.push({ text: error.message }));
            }
            if (message.method === "Network.responseReceived") responses.push(message.params.response);
            if (message.method === "Runtime.exceptionThrown") exceptions.push(message.params.exceptionDetails);
            if (message.method === "Page.lifecycleEvent" && message.params.name === "load") loaded.add(message.params.loaderId);
          };
          listeners.add(listener);
          await command("Page.enable");
          await command("Page.setLifecycleEventsEnabled", { enabled: true });
          await command("Runtime.enable");
          await command("DOM.enable");
          await command("Network.enable");
          await command("Network.setBlockedURLs", { urls: ["https://*"] });
          await command("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: true, flatten: true });
          await command("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
          await command("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
          await command("Emulation.setScriptExecutionDisabled", { value: !javascript });
          const node = async selector => {
            const { root } = await command("DOM.getDocument");
            const { nodeId } = await command("DOM.querySelector", { nodeId: root.nodeId, selector });
            assert.ok(nodeId, `Missing browser element: ${selector}`);
            return nodeId;
          };
          const attributes = async selector => {
            const { attributes: list } = await command("DOM.getAttributes", { nodeId: await node(selector) });
            return Object.fromEntries(Array.from({ length: list.length / 2 }, (_, i) => [list[i * 2], list[i * 2 + 1]]));
          };
          const evaluate = async expression => {
            const result = await command("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
            if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
            return result.result.value;
          };
          return {
            command, evaluate, attributes, responses, exceptions,
            async navigate(url) {
              assert.equal(new URL(url).origin, origin, "Browser smoke navigation stays on its local server");
              const result = await command("Page.navigate", { url });
              assert.equal(result.errorText, undefined, `Navigation failed: ${url}`);
              await until(() => loaded.has(result.loaderId), `page load: ${url}`);
              await until(async () => {
                try { return (await attributes("html")).lang; } catch { return false; }
              }, `document loaded: ${url}`);
              await command("Page.bringToFront");
            },
            async permission(name, setting) {
              await send("Browser.setPermission", { browserContextId, origin, permission: { name }, setting });
            },
            async click(selector) {
              const nodeId = await node(selector);
              await command("DOM.scrollIntoViewIfNeeded", { nodeId });
              const { model } = await command("DOM.getBoxModel", { nodeId });
              const [x1, y1, x2, y2, x3, y3, x4, y4] = model.content;
              assert.ok(model.width > 0 && model.height > 0, `Element is not visible: ${selector}`);
              const point = { x: (x1 + x2 + x3 + x4) / 4, y: (y1 + y2 + y3 + y4) / 4, button: "left", clickCount: 1 };
              await command("Input.dispatchMouseEvent", { type: "mousePressed", ...point });
              await command("Input.dispatchMouseEvent", { type: "mouseReleased", ...point });
            },
            async key(key) {
              const keys = { Tab: ["Tab", 9], Enter: ["Enter", 13], " ": ["Space", 32] };
              const [code, windowsVirtualKeyCode] = keys[key];
              const text = key === "Enter" ? "\r" : key === " " ? " " : "";
              await command("Input.dispatchKeyEvent", { type: "keyDown", key, code, windowsVirtualKeyCode, text });
              await command("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode });
            },
            async selectText(selector) {
              const nodeId = await node(selector);
              await command("DOM.scrollIntoViewIfNeeded", { nodeId });
              const { quads } = await command("DOM.getContentQuads", { nodeId });
              assert.ok(quads.length, `Text must have visible geometry: ${selector}`);
              const first = quads[0], last = quads.at(-1);
              const start = { x: first[0], y: (first[1] + first[7]) / 2 };
              const end = { x: last[2], y: (last[3] + last[5]) / 2 };
              await command("Input.dispatchMouseEvent", { type: "mousePressed", ...start, button: "left", clickCount: 1 });
              await command("Input.dispatchMouseEvent", { type: "mouseMoved", ...end, button: "left", buttons: 1 });
              await command("Input.dispatchMouseEvent", { type: "mouseReleased", ...end, button: "left", clickCount: 1 });
              return evaluate("getSelection().toString().trim()");
            },
            async html(selector) {
              return (await command("DOM.getOuterHTML", { nodeId: await node(selector) })).outerHTML;
            },
            async box(selector) { return (await command("DOM.getBoxModel", { nodeId: await node(selector) })).model; },
            async close() {
              listeners.delete(listener);
              await send("Target.disposeBrowserContext", { browserContextId });
            },
          };
        } catch (error) {
          await send("Target.disposeBrowserContext", { browserContextId }).catch(() => {});
          throw error;
        }
      },
    };
  } catch (error) {
    await close();
    throw error;
  }
}
