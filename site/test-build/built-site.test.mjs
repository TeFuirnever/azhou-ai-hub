import assert from "node:assert/strict";
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { parseHTML } from "linkedom";
import { checkBuiltSite } from "../test-support/check-built-site.mjs";
import library from "../_data/sourceLibrary.js";
import site from "../_data/site.js";

const built = fileURLToPath(new URL("../_site/", import.meta.url));
async function damagedBuild(t) {
  const root = await mkdtemp(join(tmpdir(), "azhou-built-site-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await cp(built, root, { recursive: true });
  return root;
}

test("the public build serves every RSS feed, subscription page, article and required resource", async t => {
  const result = await checkBuiltSite();
  assert.equal(result.feeds, library.channels.length + 1);
  assert.equal(result.pages, 4 + library.sourcePages.length);
  assert.equal(result.articles, library.entries.length);
  t.diagnostic(JSON.stringify(result));
});

test("the build gate rejects a feed that was not emitted instead of accepting a 404 fallback", async t => {
  const root = await damagedBuild(t);
  await rm(join(root, "library/rss.xml"));
  await assert.rejects(checkBuiltSite({ root }), /HTTP 404:.*library\/rss\.xml/);
});

test("the build gate rejects malformed RSS even when HTTP returns 200", async t => {
  const root = await damagedBuild(t);
  const path = join(root, "library/rss.xml");
  const xml = await readFile(path, "utf8");
  await writeFile(path, xml.replace("<title>", "<title>invalid & entity "));
  await assert.rejects(checkBuiltSite({ root }), /invalid RSS.*library\/rss\.xml/);
});

test("the build gate rejects subscription URLs that lose the GitHub Pages project prefix", async t => {
  const root = await damagedBuild(t);
  const path = join(root, "index.html");
  const html = await readFile(path, "utf8");
  const wrong = new URL(site.siteUrl).origin + "/library/rss.xml";
  await writeFile(path, html.replaceAll(site.siteUrl + "/library/rss.xml", wrong));
  await assert.rejects(checkBuiltSite({ root }), /RSS links:/);
});

test("the build gate rejects missing subscription metadata rather than passing an empty loop", async t => {
  const root = await damagedBuild(t);
  const path = join(root, "index.html");
  const { document } = parseHTML(await readFile(path, "utf8"));
  for (const element of document.querySelectorAll('link[rel="alternate"][type="application/rss+xml"], details.rss-subscribe')) {
    element.remove();
  }
  await writeFile(path, document.toString());
  await assert.rejects(checkBuiltSite({ root }), /Missing RSS autodiscovery:/);
});

test("RSS autodiscovery cannot mask a missing visible feed link", async t => {
  const root = await damagedBuild(t);
  const path = join(root, "index.html");
  const { document } = parseHTML(await readFile(path, "utf8"));
  document.querySelector(".rss-panel > a[href]").remove();
  await writeFile(path, document.toString());
  await assert.rejects(checkBuiltSite({ root }), /Expected one RSS feed link per panel:/);
});

test("required styles and copy modules cannot disappear from one page", async t => {
  for (const selector of ['link[rel="stylesheet"]', 'script[src$="/copy-control.js"]']) {
    const root = await damagedBuild(t);
    const path = join(root, "index.html");
    const { document } = parseHTML(await readFile(path, "utf8"));
    document.querySelector(selector).remove();
    await writeFile(path, document.toString());
    await assert.rejects(checkBuiltSite({ root }), /Required RSS (stylesheet|copy module):/);
  }
});
