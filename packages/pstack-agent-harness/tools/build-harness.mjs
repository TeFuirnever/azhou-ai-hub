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

import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
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
  // A failed build must not leave a half-assembled tree behind for the
  // repository checks to mistake for shipped source.
  rmSync(SCRATCH, { recursive: true, force: true });
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

// A component can ship agents beside its skills, as thermos does. They join
// pstack's own agents rather than replacing them, and the same pristine
// directory feeds the build as the skills above.
const AGENTS = join(SCRATCH, "pstack", "agents");
for (const from of [
  join(ROOT, "components/cursor-team-kit/agents"),
  join(ROOT, "components/thermos/agents"),
  join(ROOT, "hub-agents"),
]) {
  if (existsSync(from)) cpSync(from, AGENTS, { recursive: true });
}

// Upstream ships one harness adapter, for Claude Code. Adapter documents for
// other runtimes are this Hub's work and sit beside the pristine tree so a
// re-import of pstack/ replaces nothing of ours.
const ADAPTERS = join(SCRATCH, "pstack", "docs", "harness");
if (existsSync(join(ROOT, "hub-adapters"))) {
  mkdirSync(ADAPTERS, { recursive: true });
  cpSync(join(ROOT, "hub-adapters"), ADAPTERS, { recursive: true });
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

// Everything below assembles surfaces the upstream generator does not emit.
// A failure here drops the partial outDir, keeping the invariant that a failed
// build leaves no half-assembled tree for the repository checks to mistake for
// shipped source.
let assembled;
try {
  // hub-runtime/ holds hand-written surfaces. hooks/ carries the session
  // routing scripts; every tree gets the same directory because each runtime's
  // manifest (hooks.json for Claude Code, codex-hooks.json for Codex,
  // copilot-hooks.json for Copilot) picks its own file out of it.
  const HOOKS = join(ROOT, "hub-runtime", "hooks");
  if (!existsSync(HOOKS)) throw new Error(`hub hooks missing at ${HOOKS}`);

  const trees = readdirSync(join(outDir, "pstack"), { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);
  for (const tree of trees) cpSync(HOOKS, join(outDir, "pstack", tree, "hooks"), { recursive: true });

  // Codex installs the plugin through a `.codex-plugin/` manifest plus one
  // slash-command prompt per registered skill. The prompts are mechanical
  // artifacts of each skill's frontmatter, so the build writes them instead of
  // the repository storing hand-edited copies. Only the skills the port
  // registered as commands are listed; the unlisted ones are deliberately not
  // exposed on Codex.
  const PROMPT_SKILLS = [
    "architect",
    "arena",
    "automate-me",
    "babysit",
    "benchmark-checklist",
    "blast-radius",
    "bro",
    "correct",
    "create-formal-verification-skill",
    "create-verification-skill",
    "deslop",
    "figure-it-out",
    "fix-ci",
    "fix-merge-conflicts",
    "get-pr-comments",
    "how",
    "in-your-own-words",
    "interrogate",
    "ketchup",
    "maintain-formal-verification-skill",
    "maintain-verification-skill",
    "make-pr-easy-to-review",
    "no-comments",
    "poteto-help",
    "poteto-mode",
    "recall",
    "reflect",
    "setup-pstack",
    "sharpen",
    "show-me-your-work",
    "swarm",
    "tdd",
    "teach",
    "technical-writing",
    "thermo-nuclear-code-quality-review",
    "thermo-nuclear-review",
    "thermos",
    "typescript-best-practices",
    "unslop",
    "what-did-i-get-done",
    "why",
  ];

  const codexTree = join(outDir, "pstack", "codex");
  if (!trees.includes("codex")) throw new Error("no codex tree to install the Codex plugin surface into");
  mkdirSync(join(codexTree, ".codex-plugin"), { recursive: true });

  // The manifest keeps the identity fields of the tree's own plugin.json, so a
  // version bump in pstack/plugin.json reaches the Codex manifest without a
  // second edit. The interface block is this Hub's display text; the icon
  // paths the old pstack-claude manifest carried are dropped because the trees
  // ship no assets/ directory.
  const manifest = JSON.parse(readFileSync(join(codexTree, "plugin.json"), "utf8"));
  writeFileSync(
    join(codexTree, ".codex-plugin", "plugin.json"),
    `${JSON.stringify(
      {
        name: manifest.name,
        version: manifest.version,
        description: manifest.description,
        author: manifest.author,
        homepage: manifest.homepage,
        repository: manifest.repository,
        license: manifest.license,
        keywords: manifest.keywords,
        skills: "./skills/",
        hooks: "./hooks/codex-hooks.json",
        interface: {
          displayName: "pstack",
          shortDescription:
            "Rigorous, parallelizable agent workflows: go deep first, write less, verify everything",
          longDescription:
            "pstack guides agent work through poteto-mode's principles, parallel design exploration (architect/arena), adversarial multi-model review (interrogate), root-cause debugging, prose deslopping, and verified delivery. Skills are shared with the Claude Code build; on Codex, tool names resolve via the codex-tools mapping.",
          developerName: "Michael Denyer (port of Lauren Tan's pstack)",
          category: "Developer Tools",
          capabilities: ["Interactive", "Read", "Write"],
          defaultPrompt: ["Work on this in poteto-mode.", "Interrogate this diff with multiple models."],
          websiteURL: manifest.homepage,
          brandColor: "#7C3AED",
        },
      },
      null,
      2,
    )}\n`,
  );

  // A frontmatter description is a plain or double-quoted single-line scalar.
  // Anything else (folded, block, multi-line) fails the build rather than
  // shipping a truncated command description.
  function skillDescription(skill) {
    const frontmatter =
      readFileSync(join(codexTree, "skills", skill, "SKILL.md"), "utf8").match(/^---\n([\s\S]*?)\n---/)?.[1];
    if (frontmatter === undefined) throw new Error(`skills/${skill}/SKILL.md has no frontmatter`);
    const value = frontmatter.match(/^description:(.*)$/m)?.[1]?.trim();
    if (value === undefined || value === "") throw new Error(`skills/${skill}/SKILL.md has no description`);
    if (value.startsWith('"')) {
      if (!value.endsWith('"') || value.length < 3) {
        throw new Error(`skills/${skill}/SKILL.md has a multi-line description`);
      }
      const unquoted = value.slice(1, -1);
      if (/\\(?!["\\])/.test(unquoted)) {
        throw new Error(`skills/${skill}/SKILL.md description uses an escape beyond \\" and \\\\`);
      }
      return unquoted.replace(/\\"/g, '"').replace(/\\\\/g, "\\");
    }
    return value;
  }

  const prompts = join(codexTree, ".codex-plugin", "prompts");
  mkdirSync(prompts, { recursive: true });
  let written = 0;
  for (const skill of PROMPT_SKILLS) {
    if (!existsSync(join(codexTree, "skills", skill, "SKILL.md"))) {
      throw new Error(`${skill} is registered for a Codex prompt but is not in the assembled tree`);
    }
    writeFileSync(
      join(prompts, `${skill}.md`),
      `---\nname: ${skill}\ndescription: ${JSON.stringify(skillDescription(skill))}\n` +
        `disable-model-invocation: true\n---\n\nInvoke the \`${skill}\` skill and follow it.\n`,
    );
    written += 1;
  }

  // ZCode installs the plugin with its skills bundled. The payload declares
  // the same root-level skills directory the host's official github,
  // zcode-guide and visualize plugins use, so ZCode needs no symlinks in the
  // shared skills root (`~/.agents/skills`) to serve the 68 skills. The
  // bundled bodies are the `zcode/` tree variant, and the payload carries
  // the whole serving surface they reference — skills/, agents/, README.md,
  // docs/guide/ and docs/harness/zcode.md — so every relative link resolves
  // inside the installed plugin. The
  // local-marketplace layout and the `commands`/`skills` manifest pointers
  // were proven against zcode 0.17.1 (2026-11-03) and the bundled-skills
  // shape against the official plugins cache (2026-11-14). The tree's
  // hooks/ and plugin.json/.claude-plugin identity files stay out: a `hooks`
  // field has no proven declaration format, and the payload identity is
  // .zcode-plugin/plugin.json.
  const ZCODE_MARKETPLACE = "azhou-hub";
  const zcodeRoot = join(outDir, "pstack", "zcode-plugin");
  // No version layer: the local-source installer copies the plugin directory
  // into its own cache version folder, so the manifest must sit at the
  // directory root (zcode 0.17.1, observed 2026-11-03).
  const zcodeBundle = join(zcodeRoot, "pstack-azhouzhou");
  mkdirSync(join(zcodeBundle, ".zcode-plugin"), { recursive: true });
  mkdirSync(join(zcodeBundle, "commands"), { recursive: true });
  writeFileSync(
    join(zcodeBundle, ".zcode-plugin", "plugin.json"),
    `${JSON.stringify(
      {
        name: manifest.name,
        version: manifest.version,
        description: manifest.description,
        author: manifest.author,
        license: manifest.license,
        commands: "commands",
        skills: "skills",
      },
      null,
      2,
    )}\n`,
  );
  for (const skill of PROMPT_SKILLS) {
    writeFileSync(
      join(zcodeBundle, "commands", `${skill}.md`),
      `---\ndescription: ${JSON.stringify(skillDescription(skill))}\n---\n\nInvoke the \`${skill}\` skill and follow it.\n`,
    );
  }
  const zcodeTree = join(outDir, "pstack", "zcode");
  cpSync(join(zcodeTree, "skills"), join(zcodeBundle, "skills"), { recursive: true });
  const zcodeSkills = readdirSync(join(zcodeBundle, "skills"), { withFileTypes: true })
    .filter((entry) => entry.isDirectory()).length;
  cpSync(join(zcodeTree, "agents"), join(zcodeBundle, "agents"), { recursive: true });
  cpSync(join(zcodeTree, "README.md"), join(zcodeBundle, "README.md"));
  mkdirSync(join(zcodeBundle, "docs", "harness"), { recursive: true });
  cpSync(join(zcodeTree, "docs", "harness", "zcode.md"), join(zcodeBundle, "docs", "harness", "zcode.md"));
  cpSync(join(zcodeTree, "docs", "guide"), join(zcodeBundle, "docs", "guide"), { recursive: true });
  cpSync(join(codexTree, "LICENSE"), join(zcodeBundle, "LICENSE"));
  // The payload is a standalone distribution unit installed far from the
  // package root, so the bundled Cursor Team Kit and thermos skills must
  // carry their component notices with them: both MIT licenses require the
  // copyright and permission notices to accompany copies, and NOTICE.md
  // chains to NOTICE-skills.md and the two component LICENSE files.
  for (const notice of ["NOTICE.md", "NOTICE-skills.md", "LICENSE-cursor-team-kit", "LICENSE-thermos"]) {
    cpSync(join(ROOT, notice), join(zcodeBundle, notice));
  }
  writeFileSync(
    join(zcodeRoot, "marketplace.json"),
    `${JSON.stringify(
      {
        name: ZCODE_MARKETPLACE,
        plugins: [
          {
            // No `source` object: zcode then resolves the plugin directory that
            // sits beside this marketplace.json, which is the one proven local
            // install path (zcode 0.17.1, source-validated 2026-11-03).
            name: manifest.name,
            description: manifest.description,
          },
        ],
      },
      null,
      2,
    )}\n`,
  );

  assembled = { trees: trees.length, prompts: written, zcodeCommands: written, zcodeSkills };
} catch (error) {
  rmSync(outDir, { recursive: true, force: true });
  fail(`harness assembly failed: ${error.message}`);
}

rmSync(SCRATCH, { recursive: true, force: true });

console.log(
  `harness trees written to ${outDir} from ${series.length} patch(es), ` +
    `hooks assembled into ${assembled.trees} tree(s), ${assembled.prompts} Codex prompts, ` +
    `${assembled.zcodeCommands} ZCode commands, ${assembled.zcodeSkills} bundled ZCode skills`,
);
