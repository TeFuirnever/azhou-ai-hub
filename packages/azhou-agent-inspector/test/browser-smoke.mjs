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
  const usage = (effectiveTps) => ({
    state: "complete", effectiveTps, durationMs: 2000, outputTokens: 364,
    ttftMs: 200, cacheHitPercent: 75, responses: 2,
  });
  let refreshed = false;
  window.addEventListener("message", event => {
    if (event.source !== frame.contentWindow || event.data?.jsonrpc !== "2.0") return;
    const { method, id, params } = event.data;
    if (method === "ui/initialize") {
      send({ id, result: { protocolVersion: "2026-01-26", hostCapabilities: {} } });
    } else if (method === "ui/notifications/initialized") {
      send({ method: "ui/notifications/tool-result", params: { structuredContent: usage(42.5) } });
    } else if (method === "tools/call" && params.name === "session_performance") {
      refreshed = true;
      send({ id, result: { structuredContent: { state: "interrupted", lastCompleted: usage(182) } } });
    }
  });
  frame.src = "/codex-panel";
  document.body.append(frame);
  const text = (selector) => frame.contentDocument?.querySelector(selector)?.textContent;
  checkUi(async () => {
    await until(() => text("#rows .rate") === "42.5 tok/s", "Codex did not render the initial tool result");
    await until(() => text("#rows").includes("75%"), "Codex did not render cache hit rate");
    frame.contentDocument.querySelector("#refresh").click();
    await until(() => refreshed && text("#rows .rate") === "182 tok/s", "Codex refresh did not render the replacement sample");
    await until(() => text("#state").includes("上一已完成轮"), "Codex lost the previous-turn label after interruption");
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
