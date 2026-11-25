import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);
const codex = new URL("../plugins/azhou-agent-inspector/", import.meta.url);
const zcode = new URL("../plugins/zcode/dashboard/", import.meta.url);
const [panel, panelArt, wallpaper, dashboard, artwork, zcodeWallpaper] = await Promise.all([
  readFile(new URL("panel.html", codex), "utf8"),
  readFile(new URL("azhou.webp", codex), "base64"),
  readFile(new URL("wallpaper.webp", codex), "base64"),
  readFile(new URL("index.html", zcode), "utf8"),
  readFile(new URL("azhou.webp", zcode)),
  readFile(new URL("wallpaper.webp", zcode)),
]);
assert.equal(artwork.toString("base64"), panelArt, "The two dashboards use the same portrait");
assert.equal(zcodeWallpaper.toString("base64"), wallpaper, "The two dashboards use the same wallpaper");

const harness = `
<output id="smoke-result" data-result="pending"></output>
<script>
  async function until(predicate, description) {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (predicate()) return;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    throw new Error(description);
  }
  async function checkUi(check) {
    const output = document.querySelector("#smoke-result");
    try {
      await check();
      output.dataset.result = "pass";
    } catch (error) {
      output.dataset.result = "fail";
      output.textContent = error.message;
    }
  }
</script>`;

const codexPage = `<!doctype html><body>${harness}<script>
  const frame = document.createElement("iframe");
  const send = (message) => frame.contentWindow.postMessage({ jsonrpc: "2.0", ...message }, "*");
  const push = (data) => send({ method: "ui/notifications/tool-result", params: { structuredContent: data } });
  const usage = (effectiveTps) => ({
    state: "complete", effectiveTps, durationMs: 2000, outputTokens: 364,
    ttftMs: 200, cacheHitPercent: 75, contextUsagePercent: 40.5, responses: 2,
  });
  let refreshMode = "interrupted";
  window.addEventListener("message", event => {
    if (event.source !== frame.contentWindow || event.data?.jsonrpc !== "2.0") return;
    const { method, id, params } = event.data;
    if (method === "ui/initialize") {
      send({ id, result: { protocolVersion: "2026-01-26", hostCapabilities: {} } });
    } else if (method === "ui/notifications/initialized") {
      push(usage(42.5));
    } else if (method === "tools/call" && params.name === "session_performance") {
      if (refreshMode === "failed") {
        send({ id, error: { code: -32603, message: "Fixture failure" } });
      } else if (refreshMode === "switch") {
        push({ state: "empty" });
        send({ id, result: { structuredContent: usage(999) } });
      } else {
        send({ id, result: { structuredContent: { state: "interrupted", lastCompleted: usage(182) } } });
      }
    }
  });
  frame.src = "/codex-panel";
  frame.style.cssText = "width: 280px; height: 420px; border: 0";
  document.body.append(frame);
  const panel = (selector) => frame.contentDocument?.querySelector(selector);
  const text = (selector) => panel(selector)?.textContent;
  checkUi(async () => {
    await until(() => text(".rate") === "42.5 tok/s", "Codex did not render the initial tool result");
    await until(() => text("[data-metric=cacheHitPercent]") === "75%", "Codex did not render cache hit rate");
    const performance = panel("#performance");
    for (const expected of ["速度（整轮） 42.5 tok/s", "缓存命中 75%", "Context 占用 40.5%", "Memory —"]) {
      if (!performance.title.includes(expected)) throw new Error("Codex performance hover omitted " + expected);
    }
    performance.click();
    if (!performance.parentElement.open) throw new Error("Codex did not expose performance to click and keyboard users");
    await until(() => panel("header img")?.naturalWidth === panel("header img")?.naturalHeight &&
      panel("header img").naturalWidth > 0, "Codex did not load the square portrait");
    const backdrop = frame.contentWindow.getComputedStyle(panel("body")).backgroundImage;
    const wallpaperUrl = backdrop.match(/data:image\\/webp;base64,[A-Za-z0-9+/=]+/)?.[0];
    if (!wallpaperUrl) throw new Error("Codex did not apply the bundled wallpaper");
    const wallpaperImage = new frame.contentWindow.Image();
    wallpaperImage.src = wallpaperUrl;
    await wallpaperImage.decode();
    const duration = panel("[data-metric=durationMs]").getBoundingClientRect();
    const rate = panel(".rate").getBoundingClientRect();
    const sameColumn = Math.abs(duration.left - rate.left) < 1;
    if (sameColumn ? rate.top < duration.bottom : Math.abs(duration.bottom - rate.bottom) > 1) {
      throw new Error("Codex key metrics overlapped or lost their alignment");
    }
    panel("#refresh").click();
    await until(() => text(".rate") === "182 tok/s", "Codex refresh did not render the replacement sample");
    await until(() => !panel("#round").hidden && text("#round").includes("上一已完成轮"),
      "Codex lost the previous-turn label after interruption");

    refreshMode = "failed";
    panel("#refresh").click();
    await until(() => text("#feedback").includes("刷新失败") && !panel("#refresh").disabled,
      "Codex did not recover from a failed refresh");
    if (text(".rate") !== "182 tok/s") throw new Error("A failed refresh cleared the last valid snapshot");

    refreshMode = "switch";
    panel("#refresh").click();
    await until(() => !panel("#refresh").disabled, "Codex refresh did not finish after a new host result");
    if (!panel("#snapshot").hidden || !text("#state").includes("尚无可用")) {
      throw new Error("Late refresh response restored the previous session's metrics");
    }

    push({ state: "running", lastCompleted: { ...usage(12345.6), durationMs: 9725112,
      outputTokens: 123456789012, ttftMs: null, cacheHitPercent: 0 } });
    await until(() => text(".rate") === "12,345.6 tok/s" && !panel("#snapshot").hidden,
      "Codex did not update when host data returned");
    if (text("[data-metric=ttftMs]") !== "—" || text("[data-metric=cacheHitPercent]") !== "0%" ||
        panel("#round").hidden || !text("#state").includes("进行中")) {
      throw new Error("Codex lost the running state, missing value, or measured zero");
    }
    const root = frame.contentDocument.documentElement;
    for (const width of [240, 280, 320, 684]) {
      frame.style.width = width + "px";
      for (const fontSize of ["100%", "200%"]) {
        root.style.fontSize = fontSize;
        if (root.scrollWidth > root.clientWidth) throw new Error("Codex sidebar overflow at " + width + "px / " + fontSize);
        const refresh = panel("#refresh").getBoundingClientRect();
        if (refresh.right > width || refresh.width === 0) throw new Error("Codex refresh button moved off-screen");
      }
    }
  });
</script>`;

const zcodeHost = `<script>
  let empty = false;
  window.addEventListener("message", (event) => { if (event.data === "smoke-empty") empty = true; });
  const lane = (sessionId, rate) => ({
    sessionId, label: "Smoke " + sessionId, model: "Fixture", cwd: "/fixtures/" + sessionId,
    status: "active", latest: { tokPerSec: rate, outputTokens: 200, genMs: 1000, completedAt: Date.now() },
    turn: { tokPerSec: rate, totalMs: rate * 10, genMs: 600, ttftMs: 100, totalOutput: 200,
      totalReasoning: 0, requests: 1, rated: true, peak: rate },
    session: { avg: rate, max: rate, totalOutput: 200, totalReasoning: 0, requests: 1 },
    history: [rate - 2, rate],
  });
  window.zcode = {
    locale: "en-US",
    ready: async () => {},
    async callTool(name) {
      if (name === "metrics") return { structuredContent: { system: {
        cpuPercent: null, memUsedMB: 4096, memTotalMB: 8192, memPercent: 50,
        hostUptimeHours: 1, platform: "fixture", cpuCores: 4,
      } } };
      return { structuredContent: empty
        ? { sessions: [], total: 0 }
        : { sessions: [lane("A", 100), lane("B", 200)], total: 2, focusedSessionId: "B" } };
    },
  };
</script>`;
const zcodePage = `<!doctype html><body>${harness}<iframe title="ZCode dashboard" src="/zcode-panel"></iframe><script>
  const frame = document.querySelector("iframe");
  const doc = () => frame.contentDocument;
  const value = (id) => doc()?.getElementById(id)?.textContent;
  checkUi(async () => {
    await until(() => value("dName") === "Smoke B" && Number(value("dRate")) === 200, "ZCode did not follow the focused session");
    if (value("dDuration") !== "2.0 s") throw new Error("ZCode did not show the focused turn duration");
    const portrait = doc().querySelector(".brand img");
    await until(() => portrait.naturalWidth > 0, "ZCode portrait did not load");
    if (!portrait.naturalWidth || portrait.naturalWidth !== portrait.naturalHeight) {
      throw new Error("ZCode did not load the square portrait");
    }
    const wallpaper = new frame.contentWindow.Image();
    wallpaper.src = "./wallpaper.webp";
    await until(() => wallpaper.naturalWidth > 0, "ZCode wallpaper did not load");
    const root = doc().documentElement;
    const startTheme = root.dataset.theme;
    for (const theme of ["light", "dark"]) {
      if (root.dataset.theme !== theme) doc().getElementById("themeBtn").click();
      const backdrop = frame.contentWindow.getComputedStyle(doc().body, "::before").backgroundImage;
      if (root.dataset.theme !== theme || !backdrop.includes("wallpaper.webp")) {
        throw new Error("ZCode did not apply its wallpaper in " + theme);
      }
      for (const width of [240, 360, 684, 920, 1200]) {
        frame.style.width = width + "px";
        for (const fontSize of ["100%", "200%"]) {
          root.style.fontSize = fontSize;
          if (root.scrollWidth > root.clientWidth + 1) {
            throw new Error("ZCode dashboard overflow at " + width + "px / " + fontSize + " / " + theme);
          }
          const duration = doc().querySelector("#dDuration").getBoundingClientRect();
          if (width <= 920 && duration.top >= doc().querySelector(".session-list").getBoundingClientRect().top) {
            throw new Error("ZCode did not prioritize the selected session's metrics in the narrow pane");
          }
          const rate = doc().querySelector(".hero .rate").getBoundingClientRect();
          const stacked = Math.abs(duration.left - rate.left) < 1;
          if (stacked ? rate.top < duration.bottom : Math.abs(duration.bottom - rate.bottom) > 1) {
            throw new Error("ZCode primary metrics overlapped or lost their alignment");
          }
          if (fontSize === "100%" && (width === 240 && !stacked || width === 1200 && stacked)) {
            throw new Error("ZCode primary metrics did not adapt to the available width");
          }
        }
      }
    }
    root.style.removeProperty("font-size");
    if (root.dataset.theme !== startTheme) doc().getElementById("themeBtn").click();
    await until(() => value("cpu") === "—" && value("mem") === "4.0 / 8 GB", "ZCode did not render memory when CPU was unavailable");
    doc().querySelector("#lanes .lane").click();
    await until(() => value("dName") === "Smoke A" && Number(value("dRate")) === 100, "ZCode did not switch the focused session");
    frame.contentWindow.postMessage("smoke-empty", "*");
    await until(() => value("dName") === "No sessions" && value("dRate") === "—" && value("dDuration") === "—" &&
      !value("dDir") && !value("dModel") && value("cCum") === "--" &&
      doc().getElementById("follow").hidden, "ZCode kept details from an expired session");
  });
</script>`;

const routes = {
  "/codex": codexPage,
  "/codex-panel": panel.replace("__ART__", panelArt).replace("__WALLPAPER__", wallpaper),
  "/zcode": zcodePage,
  "/zcode-panel": dashboard.replace("<head>", "<head>" + zcodeHost),
  "/azhou.webp": artwork,
  "/wallpaper.webp": zcodeWallpaper,
};
const server = createServer((request, response) => {
  const body = Object.hasOwn(routes, request.url) ? routes[request.url] : null;
  const contentType = Buffer.isBuffer(body) ? "image/webp" : "text/html; charset=utf-8";
  response.writeHead(body ? 200 : 404, { "content-type": contentType });
  response.end(body);
});
const profile = await mkdtemp(join(tmpdir(), "azhou-browser-smoke-"));
try {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const { port } = server.address();
  for (const host of ["codex", "zcode"]) {
    const { stdout } = await run(process.env.CHROME_BIN || "google-chrome", [
      "--headless", "--no-first-run", "--disable-background-networking",
      `--user-data-dir=${join(profile, host)}`, "--virtual-time-budget=12000",
      "--dump-dom", `http://127.0.0.1:${port}/${host}`,
    ], { timeout: 30_000, maxBuffer: 4_000_000 });
    const result = stdout.match(/<output id="smoke-result"[^>]*>[\s\S]*?<\/output>/)?.[0];
    assert.match(result ?? "", /data-result="pass"/, `${host} browser smoke: ${result ?? "no DOM result"}`);
    console.log(`PASS: ${host} browser smoke`);
  }
} finally {
  server.close();
  await rm(profile, { recursive: true, force: true });
}
