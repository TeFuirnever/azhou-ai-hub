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

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
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

// Upstream ships pstack, cursor-team-kit and thermos as sibling components of
// one repository, and the distribution is their union. NOTICE-skills.md
// attributes work to those three sources, so each stays pristine in its own
// directory and is assembled here rather than copied into pstack/ by hand.
// hub-skills/ holds work this Hub authors, which must not read as upstream.
const SKILLS = join(SCRATCH, "pstack", "skills");
for (const [source, from] of [
  ["components/cursor-team-kit", join(ROOT, "components/cursor-team-kit/skills")],
  ["components/thermos", join(ROOT, "components/thermos/skills")],
  ["hub-skills", join(ROOT, "hub-skills")],
]) {
  if (existsSync(from)) cpSync(from, SKILLS, { recursive: true });
  else console.log(`skipped ${source}, not present`);
}

cpSync(
  join(ROOT, "scripts", "generate-pstack-harness-trees.mjs"),
  join(SCRATCH, "scripts", "generate-pstack-harness-trees.mjs"),
);

// Paths a patch declares as its subject. `git apply` can skip every one of
// them and still exit 0, so the build reads back those exact files instead of
// trusting the exit status.
function patchTargets(patchPath) {
  return [...readFileSync(patchPath, "utf8").matchAll(/^\+\+\+ b\/(.+)$/gm)].map((m) => m[1]);
}

function digest(root, targets) {
  return targets.map((target) => {
    const file = join(root, target);
    if (!existsSync(file) || statSync(file).isDirectory()) return `${target}:absent`;
    return `${target}:${createHash("sha256").update(readFileSync(file)).digest("hex")}`;
  });
}

for (const name of series) {
  // git resolves patch paths against the repository root and silently skips
  // every path outside the directory it runs from, still exiting 0. The scratch
  // is nested inside this repository, so without the pinned work tree each patch
  // is skipped and the build reports a pristine tree as patched.
  const targets = patchTargets(join(PATCHES, name));
  const before = digest(SCRATCH, targets);
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
  const after = digest(SCRATCH, targets);
  const untouched = targets.filter((_, index) => before[index] === after[index]);
  if (untouched.length === targets.length) {
    fail(
      `patch ${name} applied without changing ${targets.join(", ")}. ` +
        "Either the patch paths do not match the tree or upstream already carries the fix. " +
        "Drop it from patches/series in the second case."
    );
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
