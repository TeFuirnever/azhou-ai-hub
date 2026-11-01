#!/usr/bin/env node
// Build the harness trees from pristine upstream plus the patch queue.
//
//   node tools/build-harness.mjs [--target claude-code] [--out harness]
//
// `pstack/` is pristine upstream and is never written. `patches/series` names
// each patch in apply order. Each patch is one upstream defect we carry until
// its cursor/plugins pull request merges, at which point the patch file is
// deleted and its series line dropped.
//
// The build copies pristine source and the upstream generator into a scratch
// root so `generate-pstack-harness-trees.mjs` runs unmodified against the
// patched tree. Forking the generator would trade a patch queue for a fork.

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PRISTINE = join(ROOT, "pstack");
const PATCHES = join(ROOT, "patches");
const SCRATCH = join(ROOT, ".build-harness");

const args = process.argv.slice(2);
const outIndex = args.indexOf("--out");
const outDir = join(ROOT, outIndex >= 0 ? args[outIndex + 1] : "harness");

function fail(message) {
  console.error(`build-harness: ${message}`);
  process.exit(1);
}

if (!existsSync(PRISTINE)) fail(`pristine tree missing at ${PRISTINE}`);

const seriesPath = join(PATCHES, "series");
const series = existsSync(seriesPath)
  ? readFileSync(seriesPath, "utf8")
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"))
  : [];

for (const name of series) {
  if (!existsSync(join(PATCHES, name))) fail(`series names ${name}, which does not exist`);
}

rmSync(SCRATCH, { recursive: true, force: true });
mkdirSync(join(SCRATCH, "scripts"), { recursive: true });
cpSync(PRISTINE, join(SCRATCH, "pstack"), { recursive: true });
cpSync(
  join(ROOT, "scripts", "generate-pstack-harness-trees.mjs"),
  join(SCRATCH, "scripts", "generate-pstack-harness-trees.mjs"),
);

for (const name of series) {
  // git resolves patch paths against the repository root and silently skips
  // every path outside the directory it runs from, still exiting 0. The scratch
  // is nested inside this repository, so without the pinned work tree each patch
  // is skipped and the build reports a pristine tree as patched.
  const result = spawnSync(
    "git",
    [
      "--work-tree",
      SCRATCH,
      "apply",
      "--whitespace=nowarn",
      join(PATCHES, name),
    ],
    {
      cwd: SCRATCH,
      stdio: ["ignore", "pipe", "pipe"],
    }
  );
  if (result.status !== 0) {
    const detail = (result.stderr || "").toString().trim();
    fail(`patch ${name} does not apply. Rebase it against the current pristine tree.\n${detail}`);
  }
  console.log(`applied ${name}`);
}

const generated = spawnSync("node", ["scripts/generate-pstack-harness-trees.mjs"], {
  cwd: SCRATCH,
  stdio: ["ignore", "inherit", "inherit"],
});
if (generated.status !== 0) fail("upstream generator failed");

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });
cpSync(join(SCRATCH, "harness"), outDir, { recursive: true });
rmSync(SCRATCH, { recursive: true, force: true });

console.log(`harness trees written to ${outDir} from ${series.length} patch(es)`);
