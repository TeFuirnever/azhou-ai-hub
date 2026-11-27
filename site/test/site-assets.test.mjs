import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const siteDir = join(dirname(fileURLToPath(import.meta.url)), "..");

function pngSize(file) {
  const buf = readFileSync(file);
  assert.equal(buf.subarray(0, 8).toString("hex"), "89504e470d0a1a0a", `Expected PNG signature in ${file}`);
  assert.equal(buf.subarray(12, 16).toString("ascii"), "IHDR", `Expected IHDR chunk in ${file}`);
  return {
    width: buf.readUInt32BE(16),
    height: buf.readUInt32BE(20),
  };
}

test("extracted Azhou cursor PNGs exist with 1x (32px) and 2x (64px) dimensions", () => {
  for (const name of ["arrow", "pointer", "text", "grab", "grabbing"]) {
    assert.deepEqual(pngSize(join(siteDir, "assets", "cursors", `${name}.png`)), { width: 32, height: 32 });
    assert.deepEqual(pngSize(join(siteDir, "assets", "cursors", `${name}@2x.png`)), { width: 64, height: 64 });
  }
});

test("Azhou avatar and Apple touch icon PNGs match their advertised sizes", () => {
  const artwork = join(siteDir, "..", "assets", "site");
  assert.deepEqual(pngSize(join(artwork, "azhou-avatar.png")), { width: 64, height: 64 });
  assert.deepEqual(pngSize(join(artwork, "apple-touch-icon.png")), { width: 180, height: 180 });
});

test("homepage preserves required section anchors", () => {
  const home = readFileSync(join(siteDir, "_includes", "home.njk"), "utf8");
  for (const anchor of ["install", "cursor-theme", "capabilities", "sources"]) {
    assert.match(home, new RegExp(`id="${anchor}"`), `Missing anchor #${anchor} in home.njk`);
  }
});

test("site templates load zero external font stylesheets", () => {
  for (const template of ["base.njk", "home.njk"]) {
    const html = readFileSync(join(siteDir, "_includes", template), "utf8");
    const links = html.match(/<link\b[^>]*>/gi) ?? [];
    for (const tag of links) {
      assert.ok(!/fonts\.googleapis|fonts\.gstatic|font-faces|rel=["']stylesheet["'][^>]*https?:/i.test(tag),
        `Unexpected external font link in ${template}: ${tag}`);
    }
  }
});
