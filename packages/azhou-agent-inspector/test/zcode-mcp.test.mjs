import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const server = fileURLToPath(new URL("../plugins/zcode/mcp/tps-server.mjs", import.meta.url));
const initialize = { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2024-11-05" } };
const tools = { jsonrpc: "2.0", id: 2, method: "tools/list" };
const snapshot = { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "tps_snapshot" } };

function exchange(input, nodeOptions = []) {
  const result = spawnSync(process.execPath, [...nodeOptions, server], {
    input, encoding: "utf8", timeout: 5000, env: { ...process.env, TPS_URL: "" },
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

test("ZCode MCP answers a newline-delimited client using newline JSON", () => {
  const input = [initialize, tools, snapshot].map((request) => JSON.stringify(request)).join("\n") + "\n";
  const deniedUptime = 'import os from "node:os"; os.uptime = () => { throw new Error("restricted"); };';
  const replies = exchange(input, ["--import", "data:text/javascript," + encodeURIComponent(deniedUptime)])
    .trim().split("\n").map((line) => JSON.parse(line));
  assert.deepEqual(replies.map((reply) => reply.id), [1, 2, 3]);
  assert.equal(replies[0].result.serverInfo.name, "azhou-agent-inspector");
  assert.ok(replies[1].result.tools.some((tool) => tool.name === "tps_snapshot"));
  assert.equal(replies[2].result.isError, false);
  assert.match(replies[2].result.content[0].text, /demo/);
  assert.match(replies[2].result.content[0].text, /主机运行时长[^:]*: —/);
});

test("existing Content-Length clients still receive frames", () => {
  const frame = (request) => {
    const body = JSON.stringify(request);
    return `Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`;
  };
  let output = Buffer.from(exchange(frame(initialize) + frame(tools)));
  for (const expected of [1, 2]) {
    const end = output.indexOf("\r\n\r\n");
    assert.ok(end > 0);
    const match = /^Content-Length: (\d+)$/.exec(output.subarray(0, end).toString());
    assert.ok(match);
    const bodyEnd = end + 4 + Number(match[1]);
    assert.equal(JSON.parse(output.subarray(end + 4, bodyEnd)).id, expected);
    output = output.subarray(bodyEnd);
  }
  assert.equal(output.length, 0);
});
