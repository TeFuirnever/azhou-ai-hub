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
const [panel, panelArt, dashboard, artwork] = await Promise.all([
  readFile(new URL("panel.html", codex), "utf8"),
  readFile(new URL("azhou.webp", codex), "base64"),
  readFile(new URL("index.html", zcode), "utf8"),
  readFile(new URL("azhou.webp", zcode)),
]);

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
    ttftMs: 200, cacheHitPercent: 75, responses: 2,
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
    await until(() => panel("header img")?.naturalWidth === panel("header img")?.naturalHeight &&
      panel("header img").naturalWidth > 0, "Codex did not load the square portrait");
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
  const lane = (sessionId, rate) => ({
    sessionId, label: "Smoke " + sessionId, model: "Fixture", cwd: "/fixtures/" + sessionId,
    status: "active", latest: { tokPerSec: rate, outputTokens: 200, genMs: 1000, completedAt: Date.now() },
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
const zcodeCheck = `${harness}<script>
  const value = (id) => document.getElementById(id).textContent;
  checkUi(async () => {
    await until(() => value("dName") === "Smoke B" && Number(value("dRate")) === 200, "ZCode did not follow the focused session");
    await until(() => value("cpu") === "—" && value("mem") === "4.0 / 8 GB", "ZCode did not render memory when CPU was unavailable");
    document.querySelector("#lanes .lane").click();
    await until(() => value("dName") === "Smoke A" && Number(value("dRate")) === 100, "ZCode did not switch the focused session");
    empty = true;
    await until(() => value("dName") === "No sessions" && value("dRate") === "--" &&
      !value("dDir") && !value("dModel") && value("cCum") === "--" &&
      document.getElementById("follow").hidden, "ZCode kept details from an expired session");
  });
</script>`;

const routes = {
  "/codex": codexPage,
  "/codex-panel": panel.replace("__ART__", panelArt),
  "/zcode": dashboard.replace("<head>", "<head>" + zcodeHost).replace("</body>", zcodeCheck + "</body>"),
  "/azhou.webp": artwork,
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
