import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import site from "../_data/site.js";
import { startBuiltSite } from "../test-support/built-site.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifact = join(root, "site/_site", site.askAzhouDownloadPath);
const packagePath = "skills/super-ask-azhou";
const git = args => execFileSync("git", args, { cwd: root });

test("the site serves exactly the committed Ask Azhou package and license", async t => {
  const server = await startBuiltSite();
  t.after(() => server.close());
  const url = server.url(site.askAzhouDownloadPath);
  const response = await fetch(url);
  assert.equal(response.status, 200, url);
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), await readFile(artifact));

  const entries = execFileSync("tar", ["-tzf", artifact], { encoding: "utf8" }).trim().split("\n");
  const files = git(["ls-tree", "-r", "--name-only", "HEAD", "--", "LICENSE", packagePath])
    .toString().trim().split("\n");
  assert.ok(files.includes(`${packagePath}/SKILL.md`));
  assert.deepEqual(entries.filter(entry => !entry.endsWith("/")).sort(), files.sort());
  for (const file of files) {
    assert.deepEqual(execFileSync("tar", ["-xOzf", artifact, file]), git(["show", `HEAD:${file}`]), file);
  }
});
