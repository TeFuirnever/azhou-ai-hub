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
const [panel, panelArt, wallpaper, dashboard, artwork, zcodeWallpaper, manifest, overlay] = await Promise.all([
  readFile(new URL("panel.html", codex), "utf8"),
  readFile(new URL("azhou.webp", codex), "base64"),
  readFile(new URL("wallpaper.webp", codex), "base64"),
  readFile(new URL("index.html", zcode), "utf8"),
  readFile(new URL("azhou.webp", zcode)),
  readFile(new URL("wallpaper.webp", zcode)),
  readFile(new URL(".codex-plugin/plugin.json", codex), "utf8"),
  readFile(new URL("overlay/overlay.html", zcode), "utf8"),
]);
assert.equal(artwork.toString("base64"), panelArt, "The two dashboards use the same portrait");
assert.equal(zcodeWallpaper.toString("base64"), wallpaper, "The two dashboards use the same wallpaper");

const harness = `
<output id="smoke-result" data-result="pending"></output>
<script>
  async function until(predicate, description, attempts = 100) {
    for (let attempt = 0; attempt < attempts; attempt++) {
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
    for (const expected of ["首个 token 等待 0.2 秒", "缓存命中 75%", "Context 占用 40.5%"]) {
      if (!performance.title.includes(expected)) throw new Error("Codex performance hover omitted " + expected);
    }
    if (performance.title.includes("Memory") || performance.title.includes("42.5 tok/s")) {
      throw new Error("Codex repeated or invented metrics in its performance details");
    }
    performance.click();
    if (!performance.parentElement.open) throw new Error("Codex did not expose performance details on click");
    performance.click();
    if (performance.parentElement.open) throw new Error("Codex performance details did not close");
    performance.click();
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
    panel("#refresh").focus();
    panel("#refresh").click();
    if (text("#feedback") !== "正在刷新…" || panel("#refresh").getAttribute("aria-disabled") !== "true") {
      throw new Error("Codex did not show that refresh was pending");
    }
    await until(() => text(".rate") === "182 tok/s" && text("#feedback") === "已刷新。", "Codex refresh did not render the replacement sample");
    await until(() => !panel("#round").hidden && text("#round").includes("上一已完成轮"),
      "Codex lost the previous-turn label after interruption");

    if (frame.contentDocument.activeElement !== panel("#refresh")) throw new Error("Codex refresh stole focus");

    refreshMode = "failed";
    panel("#refresh").click();
    await until(() => text("#feedback").includes("刷新失败") && !panel("#refresh").hasAttribute("aria-disabled"),
      "Codex did not recover from a failed refresh");
    if (text(".rate") !== "182 tok/s") throw new Error("A failed refresh cleared the last valid snapshot");

    refreshMode = "switch";
    panel("#refresh").click();
    await until(() => !panel("#refresh").hasAttribute("aria-disabled"), "Codex refresh did not finish after a new host result");
    if (!panel("#snapshot").hidden || !text("#state").includes("尚无可用")) {
      throw new Error("Late refresh response restored the previous session's metrics");
    }

    push({ state: "running", lastCompleted: { ...usage(12345.6), durationMs: 9725112,
      outputTokens: 123456789012, ttftMs: null, cacheHitPercent: 0 } });
    await until(() => text(".rate") === "12,345.6 tok/s" && !panel("#snapshot").hidden,
      "Codex did not update when host data returned");
    if (panel("[data-metric=ttftMs]").parentElement.getClientRects().length ||
        !panel("[data-metric=cacheHitPercent]").parentElement.getClientRects().length || text("[data-metric=cacheHitPercent]") !== "0%" ||
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
  let focusedSessionId = "B";
  let slowSessionRead;
  let failMetrics = true;
  window.smoke = { reads: 0, metrics: 0, hold: false,
    release() { slowSessionRead?.(); },
    failMetrics() { failMetrics = true; },
    recoverMetrics() { failMetrics = false; },
  };
  window.addEventListener("message", (event) => {
    if (event.data?.type === "smoke-focus") focusedSessionId = event.data.sessionId;
  });
  const lane = (sessionId, rate, requestRate) => ({
    sessionId, label: "Smoke " + sessionId, model: "Fixture", cwd: "/fixtures/" + sessionId, requestRate,
    status: "active", latest: { tokPerSec: rate, outputTokens: 200, genMs: 1000, completedAt: Date.now() },
    turn: { tokPerSec: rate, totalMs: rate * 10, genMs: sessionId === "A" ? 600 : 0,
      ttftMs: sessionId === "A" ? 100 : null, totalOutput: 200,
      totalReasoning: 0, requests: 1, rated: true, peak: rate },
    session: { avg: rate, max: rate, totalOutput: 200, totalReasoning: 0, requests: 1 },
    history: [rate - 2, rate],
  });
  window.zcode = {
    locale: "en-US",
    ready: async () => {},
    async callTool(name) {
      if (name === "artwork") return { structuredContent: {
        portrait: "data:image/webp;base64,${panelArt}",
        wallpaper: "data:image/webp;base64,${wallpaper}",
      } };
      if (name === "metrics") {
        window.smoke.metrics += 1;
        if (failMetrics) throw new Error("metrics unavailable");
        return { structuredContent: { system: {
          cpuPercent: null, memUsedMB: 4096, memTotalMB: 8192, memPercent: 50,
          hostUptimeHours: 1, platform: "fixture", cpuCores: 4,
        } } };
      }
      window.smoke.reads += 1;
      const recent = lane("A", 100, 125);
      const focusedSession = focusedSessionId === "B" ? lane("B", 200)
        : focusedSessionId === "A" ? recent : null;
      const result = { structuredContent: { sessions: [recent], total: 2, focusedSessionId, focusedSession } };
      if (window.smoke.hold) {
        window.smoke.hold = false;
        await new Promise(resolve => { slowSessionRead = resolve; });
      }
      return result;
    },
  };
</script>`;
const zcodePage = `<!doctype html><body>${harness}<iframe title="ZCode dashboard" src="/zcode-panel"></iframe><script>
  const frame = document.querySelector("iframe");
  const doc = () => frame.contentDocument;
  const value = (id) => doc()?.getElementById(id)?.textContent;
  checkUi(async () => {
    await until(() => value("dName") === "Smoke B" && Number(value("dRate")) === 200, "ZCode did not follow the focused session");
    await until(() => value("resourceStatus") === "System resources unavailable", "ZCode did not report first resource read failure");
    if (!doc().getElementById("resourceReadings").hidden) throw new Error("ZCode displayed placeholders after the first resource read failed");
    frame.contentWindow.smoke.recoverMetrics();
    doc().dispatchEvent(new frame.contentWindow.Event("visibilitychange"));
    if (value("dDuration") !== "2.0 s") throw new Error("ZCode did not show the focused turn duration");
    if (doc().querySelector(".session-list, #lanes, #follow")) {
      throw new Error("ZCode rendered a second session navigation list");
    }
    if (value("dSub").includes("Turn generation rate")) {
      throw new Error("ZCode repeated the turn rate already shown in the headline");
    }
    const details = doc().getElementById("performanceDetails");
    const summary = details.querySelector("summary");
    if (details.hidden || details.open || summary.textContent !== "Performance details") {
      throw new Error("ZCode did not start with a closed performance disclosure");
    }
    summary.focus();
    summary.click();
    const detailLabels = [...doc().querySelectorAll("#dSub dt")].map(term => term.textContent);
    if (!details.open || detailLabels.includes("TTFT") || detailLabels.includes("Generation") || !value("dSub").includes("reasoning0 tok")) {
      throw new Error("ZCode did not expose measured values including zero while omitting missing values");
    }
    const detailList = doc().querySelector("#dSub dl");
    const selection = doc().getSelection();
    selection.selectAllChildren(detailList);
    const selectedText = selection.toString();
    const initialReads = frame.contentWindow.smoke.reads;
    await until(() => frame.contentWindow.smoke.reads >= initialReads + 2, "ZCode did not refresh the same session");
    if (!selectedText || selection.toString() !== selectedText || doc().activeElement !== summary || !details.open) {
      throw new Error("A ZCode refresh disturbed the current disclosure, focus, or selected text");
    }
    selection.removeAllRanges();
    summary.click();
    if (details.open) throw new Error("ZCode performance details did not close");
    const portrait = doc().querySelector(".brand img");
    await until(() => portrait.naturalWidth > 0, "ZCode portrait did not load");
    if (!portrait.naturalWidth || portrait.naturalWidth !== portrait.naturalHeight) {
      throw new Error("ZCode did not load the square portrait");
    }
    const wallpaper = new frame.contentWindow.Image();
    wallpaper.src = "data:image/webp;base64,${wallpaper}";
    await until(() => wallpaper.naturalWidth > 0, "ZCode wallpaper did not load");
    const root = doc().documentElement;
    const startTheme = root.dataset.theme;
    for (const theme of ["light", "dark"]) {
      if (root.dataset.theme !== theme) doc().getElementById("themeBtn").click();
      const backdrop = frame.contentWindow.getComputedStyle(doc().body, "::before").backgroundImage;
      if (root.dataset.theme !== theme || !backdrop.includes("data:image/webp;base64,")) {
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
    frame.contentWindow.postMessage({type: "smoke-focus", sessionId: "A"}, "*");
    await until(() => value("dName") === "Smoke A" && Number(value("dRate")) === 125, "Dashboard did not follow a ZCode session change");
    const turnRate = [...doc().querySelectorAll("#dSub dt")].find(term => term.textContent === "Turn generation rate");
    if (turnRate?.nextElementSibling?.textContent !== "100.0 tok/s") {
      throw new Error("ZCode hid the turn rate while the headline showed the request rate");
    }
    frame.contentWindow.postMessage({type: "smoke-focus", sessionId: "no-usage"}, "*");
    await until(() => value("dName") === "No session data" && value("dRate") === "—" && value("dDuration") === "—" &&
      !value("dDir") && !value("dModel") && value("cCum") === "--", "An empty session displayed stats from a different session");
    if (!doc().querySelector(".hero").hidden || !doc().querySelector(".session-history").hidden ||
        !details.hidden || !doc().getElementById("dEmpty").hidden) {
      throw new Error("An empty session showed placeholders or an unrelated request status");
    }
    frame.contentWindow.postMessage({type: "smoke-focus", sessionId: null}, "*");
    await until(() => value("dName") === "Smoke A", "An unscoped dashboard did not show the latest session");

    const host = frame.contentWindow.smoke;
    const before = host.reads;
    host.hold = true;
    host.failMetrics();
    await until(() => host.reads > before, "ZCode did not start the held request");
    await new Promise(resolve => setTimeout(resolve, 1250));
    if (host.reads !== before + 1) throw new Error("ZCode overlapped reads of the same session data");
    frame.contentWindow.postMessage({type: "smoke-focus", sessionId: "B"}, "*");
    await until(() => value("resourceStatus").includes("last reading"),
      "ZCode did not label stale resource readings on failure");
    if (value("mem") !== "4.0 / 8 GB") throw new Error("A failed resource read cleared the last valid data");
    host.recoverMetrics();
    doc().dispatchEvent(new frame.contentWindow.Event("visibilitychange"));
    await until(() => !value("resourceStatus").includes("last reading"),
      "ZCode did not refresh resources as soon as it became visible");
    await until(() => value("liveTxt") === "Disconnected", "ZCode did not report its timed-out session read", 320);
    await until(() => value("dName") === "Smoke B", "ZCode did not recover after a session read timed out");
    host.release();
    await new Promise(resolve => setTimeout(resolve, 50));
    if (value("dName") !== "Smoke B") throw new Error("ZCode applied a response after its deadline");
  });
</script>`;

const overlayHost = `<script>
  window.smoke = { reads: 0, fail: false };
  window.fetch = async () => {
    const rate = 150 + ++window.smoke.reads;
    const data = location.search ? { status: "no-data" } : {
      status: "idle", turn: { tokPerSec: rate, totalOutput: 200, requests: 1 },
      history: [100, rate],
    };
    return { ok: !window.smoke.fail, json: async () => data };
  };
</script>`;
const overlayPage = `<!doctype html><body>${harness}<iframe title="Overlay" src="/overlay-panel"></iframe><script>
  const frame = document.querySelector("iframe");
  const byId = id => frame.contentDocument?.getElementById(id);
  checkUi(async () => {
    await until(() => byId("num")?.textContent === "151", "Overlay did not load its first reading");
    const state = byId("state"), pause = byId("btnPause"), refresh = byId("btnRefresh"), spark = byId("btnSpark");
    const host = frame.contentWindow.smoke;
    pause.click();
    refresh.click();
    await until(() => byId("num").textContent === "152", "Overlay did not refresh while paused");
    if (state.textContent !== "已暂停" || pause.getAttribute("aria-pressed") !== "true") {
      throw new Error("One-shot refresh resumed automatic polling");
    }
    await new Promise(resolve => setTimeout(resolve, 1200));
    if (host.reads !== 2) throw new Error("Paused overlay kept polling");
    spark.click();
    const points = byId("sparkline").getAttribute("points");
    spark.click();
    spark.click();
    if (!points || byId("sparkline").getAttribute("points") !== points || spark.getAttribute("aria-pressed") !== "true") {
      throw new Error("Overlay did not restore the cached sparkline while paused");
    }
    host.fail = true;
    refresh.click();
    await until(() => state.textContent.includes("刷新失败"), "Overlay did not announce manual refresh failure");
    if (byId("num").textContent !== "152") throw new Error("Overlay replaced its last reading on failure");
    host.fail = false;
    Object.defineProperty(frame.contentDocument, "hidden", { value: true });
    pause.click();
    await until(() => host.reads >= 5 && state.textContent === "空闲", "Overlay did not resume polling in the background");
    frame.src = "/overlay-panel?style=line";
    await until(() => byId("info")?.textContent === "暂无会话数据", "Overlay line mode did not render the empty state");
    if (byId("btnSpark").getClientRects().length) throw new Error("Line mode exposed a control with no effect");
  });
</script>`;

const routes = {
  "/codex": codexPage,
  "/codex-panel": panel.replace("__ART__", panelArt).replace("__WALLPAPER__", wallpaper)
    .replace("__PLUGIN_VERSION__", JSON.stringify(JSON.parse(manifest).version)),
  "/zcode": zcodePage,
  "/zcode-panel": dashboard.replace("<head>", "<head>" + zcodeHost),
  "/overlay": overlayPage,
  "/overlay-panel": overlay.replace("<head>", "<head>" + overlayHost),
};
const server = createServer((request, response) => {
  const pathname = new URL(request.url, "http://127.0.0.1").pathname;
  const body = Object.hasOwn(routes, pathname) ? routes[pathname] : null;
  const contentType = Buffer.isBuffer(body) ? "image/webp" : "text/html; charset=utf-8";
  response.writeHead(body ? 200 : 404, { "content-type": contentType });
  response.end(body);
});
const profile = await mkdtemp(join(tmpdir(), "azhou-browser-smoke-"));
try {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const { port } = server.address();
  for (const host of ["codex", "zcode", "overlay"]) {
    const { stdout } = await run(process.env.CHROME_BIN || "google-chrome", [
      "--headless", "--no-first-run", "--disable-background-networking",
      `--user-data-dir=${join(profile, host)}`, "--virtual-time-budget=18000",
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
