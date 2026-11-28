import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { DOMParser } from "linkedom";
import site from "../_data/site.js";
import library from "../_data/sourceLibrary.js";
import { startBuiltSite } from "../test-support/built-site.mjs";
import { launchChrome, until } from "./chrome.mjs";

const server = await startBuiltSite();
let browser;
let passed = 0;
const feed = `${site.siteUrl}/library/rss.xml`;
const statusSelector = '#rss-all [role="status"]';
const isOpen = async (page, selector = "#rss-all") => Object.hasOwn(await page.attributes(selector), "open");

async function check(name, options, path, body) {
  const page = await browser.page(server.origin, options);
  try {
    await page.navigate(server.url(path));
    await body(page);
    assert.deepEqual(page.exceptions, [], `${name}: page JavaScript exceptions`);
    assert.deepEqual(page.responses.filter(response => response.url.startsWith(server.origin) && response.status >= 400)
      .map(response => [response.status, response.url]), [], `${name}: failed local resources`);
    console.log(`PASS: ${name}`);
    passed++;
  } finally {
    await page.close();
  }
}

async function assertFeedVisible(page, id, expected, width) {
  assert.ok(await isOpen(page, `#${id}`), `${id} disclosure must be open`);
  assert.ok((await page.html(`#${id}-url`)).includes(expected), "The visible address matches the canonical feed");
  assert.equal((await page.attributes(`#${id} .rss-panel a`)).href, expected);
  const panel = await page.box(`#${id} .rss-panel`);
  assert.ok(panel.width > 0 && panel.height > 0, "Subscription content must be visible");
  if (width) {
    const xs = panel.border.filter((_, index) => index % 2 === 0);
    assert.ok(Math.min(...xs) >= -1 && Math.max(...xs) <= width + 1,
      `RSS panel must fit the ${width}px viewport: ${xs}`);
  }
}

// Choose a real indexed word from the built article body, preferring a word
// absent from catalog titles/notes. The check stays independent of editorial
// IDs, titles, article count and the exact Pagefind output filenames.
async function searchFixture() {
  if (!library.entries.length) return null;
  const catalog = library.entries.map(entry => `${entry.title} ${entry.note} ${entry.noteEn}`).join(" ").toLowerCase();
  let fallback;
  for (const entry of library.entries) {
    const html = await readFile(new URL(`../_site/library/articles/${entry.id}/index.html`, import.meta.url), "utf8");
    const document = new DOMParser().parseFromString(html, "text/html");
    const body = document.querySelector("[data-pagefind-body]");
    assert.ok(body, `Article ${entry.id} must expose a Pagefind body`);
    for (const ignored of body.querySelectorAll("[data-pagefind-ignore], script, style")) ignored.remove();
    const words = body.textContent.match(/[A-Za-z]{7,}|[\p{Script=Han}]{2,8}/gu) ?? [];
    for (const word of words) {
      fallback ??= { id: entry.id, query: word };
      if (!catalog.includes(word.toLowerCase())) return { id: entry.id, query: word };
    }
  }
  assert.ok(fallback, "The populated library needs an indexed word for its browser search check");
  return fallback;
}

try {
  browser = await launchChrome();
  console.log(`Browser: ${browser.version.product}`);
  const query = await searchFixture();
  for (const lang of ["en", "zh"]) {
    const path = site.routes[lang].library;
    const width = lang === "zh" ? 390 : 1200;
    await check(`${lang}: docs leads to recovery and private reporting at ${width}px`, { width }, site.routes[lang].docs, async page => {
      const support = site.pathPrefix + site.routes[lang].support.slice(1);
      const getHelp = `main a[href="${support}#get-help"]`;
      const discovery = `${site.blobBase}/docs/installation.md#check-that-your-host-finds-the-skill`;
      assert.equal((await page.attributes(`main a[href="${discovery}"]`)).hreflang, "en");
      await page.click(getHelp);
      await until(() => page.evaluate(`location.pathname === ${JSON.stringify(support)} && location.hash === "#get-help"`),
        "Help opens at the right section");
      assert.ok((await page.box(`main a[href="${discovery}"]`)).height > 0, "Recovery link is visible");
      for (const target of ["/discussions", "/issues/new?template=bug.yml", "/security/advisories/new"]) {
        assert.ok((await page.box(`main a[href="${site.githubUrl}${target}"]`)).height > 0,
          `The ${target} action is visible`);
      }
      await page.click("#switch-language");
      const other = lang === "en" ? "zh" : "en";
      const translated = site.pathPrefix + site.routes[other].support.slice(1);
      await until(() => page.evaluate(`location.pathname === ${JSON.stringify(translated)} && location.hash === "#get-help"`),
        "Changing language keeps the help section");
    });
    const skillsPath = site.routes[lang].skills;
    await check(`${lang}: open Ask Azhou without clearing the skill search`, { width }, `${skillsPath}?q=super-archify`, async page => {
      const row = "#super-ask-azhou";
      assert.ok(Object.hasOwn(await page.attributes(row), "hidden"));
      await page.click("#ask-azhou-install-link");
      await until(() => isOpen(page, `${row} > details`), "Ask Azhou card opens");
      assert.equal(await page.evaluate('new URLSearchParams(location.search).get("q")'), "super-archify");
      assert.equal(await page.evaluate('document.querySelector("#skill-search").value'), "super-archify");
      assert.equal((await page.attributes(row)).hidden, undefined);
      await until(() => page.evaluate(`document.querySelector("${row} summary").getBoundingClientRect().bottom <= innerHeight`),
        "Ask Azhou appears in the viewport");
      await page.evaluate(`document.querySelector("${row} summary").focus()`);
      await page.key("Enter");
      await until(async () => Object.hasOwn(await page.attributes(row), "hidden"), "Closing the card restores the filtered list");
      assert.equal(await page.evaluate('document.activeElement.id'), "ask-azhou-install-link");
    });

    const foundation = "#super-azhou-doctor";
    await check(`${lang}: Foundation install shows the local checkout path`, { width }, `${skillsPath}?q=super-archify${foundation}`, async page => {
      const guide = `${site.blobBase}/docs/installation.md#checkout-assisted-setup`;
      const manual = `${foundation} [data-manual-install]`;
      assert.ok(await isOpen(page, `${foundation} > details`));
      assert.ok((await page.html("#agent-install-super-azhou-doctor")).includes(lang === "zh" ? "本地 Hub 仓库" : "local Hub checkout"));
      if (!await isOpen(page, manual)) await page.click(`${manual} > summary`);
      assert.equal((await page.attributes(`${manual} a`)).href, guide);
      assert.equal(await page.evaluate(`document.querySelector("${manual} code") === null`), true,
        "A checkout-only skill does not show the ordinary install command");
      await page.evaluate(`document.querySelector("${foundation} > details > summary").focus()`);
      await page.key("Enter");
      await until(async () => Object.hasOwn(await page.attributes(foundation), "hidden"), "Closing the deep-linked card restores the filter");
      assert.equal(await page.evaluate('document.activeElement.id'), "clear-skill-search");
    });

    await check(`${lang}: homepage RSS opens at ${width}px`, { width }, site.routes[lang].home, async page => {
      await page.click(".rss-subscribe > summary");
      const id = (await page.attributes(".rss-subscribe")).id;
      await until(() => isOpen(page, `#${id}`), "Homepage RSS opens");
      await assertFeedVisible(page, id, feed, width);
    });
    await check(`${lang}: RSS mouse and keyboard activation at ${width}px`, { width }, path, async page => {
      assert.equal(await isOpen(page), false);
      // Tab traverses the rendered document's actual focus order. No click()
      // or keyboard handler is called from page JavaScript.
      for (let count = 0; count < 40; count++) {
        await page.key("Tab");
        if (await page.evaluate('document.activeElement === document.querySelector("#rss-all > summary")')) break;
      }
      assert.equal(await page.evaluate('document.activeElement === document.querySelector("#rss-all > summary")'), true,
        "The subscription summary must be keyboard reachable");
      await page.key("Enter");
      await until(() => isOpen(page), "Enter opens RSS");
      await assertFeedVisible(page, "rss-all", feed, width);
      await page.key(" ");
      await until(async () => !(await isOpen(page)), "Space closes RSS");
      await page.click("#rss-all > summary");
      await until(() => isOpen(page), "Click opens RSS");
      await assertFeedVisible(page, "rss-all", feed, width);
    });

    await check(`${lang}: real clipboard success, denial and retry`, { width }, path, async page => {
      await page.permission("clipboard-read", "granted");
      await page.permission("clipboard-write", "granted");
      await page.evaluate(`navigator.clipboard.writeText(${JSON.stringify(`before-copy-${lang}`)})`);
      await page.click("#rss-all > summary");
      await until(async () => !Object.hasOwn(await page.attributes("#rss-all .copy-actions"), "hidden"), "Clipboard control enabled");
      await page.click('#rss-all [data-copy="rss-all-url"]');
      await until(async () => (await page.attributes(statusSelector))["data-state"] === "success", "Native clipboard write succeeds");
      assert.equal(await page.evaluate("navigator.clipboard.readText()"), feed);
      assert.ok((await page.html(`${statusSelector} [data-copy-message]`)).includes(lang === "zh" ? "已复制" : "Copied"));

      await page.permission("clipboard-read", "denied");
      await page.permission("clipboard-write", "denied");
      await page.click('#rss-all [data-copy="rss-all-url"]');
      await until(async () => (await page.attributes(statusSelector))["data-state"] === "error", "Denied clipboard reports recovery");
      assert.ok((await page.html(`${statusSelector} [data-copy-message]`)).includes(lang === "zh" ? "手动复制" : "Select and copy"));
      await assertFeedVisible(page, "rss-all", feed, width);
      assert.equal(await page.selectText("#rss-all-url"), feed,
        "A native pointer drag can select the complete address after denial");

      await page.permission("clipboard-read", "granted");
      await page.permission("clipboard-write", "granted");
      await page.evaluate(`navigator.clipboard.writeText(${JSON.stringify(`before-retry-${lang}`)})`);
      await page.click('#rss-all [data-copy="rss-all-url"]');
      await until(async () => (await page.attributes(statusSelector))["data-state"] === "success", "Clipboard retry succeeds");
      assert.equal(await page.evaluate("navigator.clipboard.readText()"), feed);
    });

    await check(`${lang}: RSS remains usable with page JavaScript disabled`, { javascript: false, width }, path, async page => {
      assert.equal(await isOpen(page), false);
      await page.click("#rss-all > summary");
      await until(() => isOpen(page), "Native no-JS details opens");
      await assertFeedVisible(page, "rss-all", feed, width);
      assert.ok(Object.hasOwn(await page.attributes("#rss-all .copy-actions"), "hidden"), "No-JS page must keep inactive copy buttons hidden");
      // This case only uses CDP DOM queries; it never reenables JavaScript or
      // executes page expressions to inspect the no-JS result.
    });

    if (library.channels.length) {
      const source = library.channels[0];
      const sourceFeed = `${site.siteUrl}/library/sources/${source.id}/rss.xml`;
      await check(`${lang}: source RSS opens at 390px`, { width: 390 }, `${path}sources/${source.id}/`, async page => {
        await page.click(".rss-subscribe > summary");
        const id = (await page.attributes(".rss-subscribe")).id;
        await until(() => isOpen(page, `#${id}`), "Source RSS opens");
        await assertFeedVisible(page, id, sourceFeed, 390);
      });
    }

    if (query) {
      await check(`${lang}: built Pagefind index answers a real query`, { width }, path, async page => {
        await until(async () => !Object.hasOwn(await page.attributes("#library-search"), "hidden"), "Search script is ready");
        await page.click("#library-query");
        await page.command("Input.insertText", { text: query.query });
        await page.key("Enter");
        await until(async () => (await page.attributes("#library-status"))["data-state"] === "done", "Real indexed search completes");
        assert.equal(await page.evaluate(`Boolean(document.querySelector('#library-results [data-entry-id="${query.id}"] [data-excerpt]'))`), true,
          "The real indexed article and its excerpt must be rendered");
        const loaded = page.responses.filter(response => response.status === 200).map(response => new URL(response.url).pathname);
        assert.ok(loaded.some(path => path === `${site.pathPrefix}pagefind/pagefind.js`), "The real Pagefind entry module must load");
        assert.ok(loaded.some(path => path.startsWith(`${site.pathPrefix}pagefind/wasm.`) && path.endsWith(".pagefind")), `The Pagefind WASM index must load: ${loaded.join(", ")}`);
        assert.ok(loaded.some(path => path.startsWith(`${site.pathPrefix}pagefind/fragment/`)), "Pagefind must retrieve a real article fragment");
      });
    } else {
      console.log(`SKIP: ${lang} Pagefind query (the published library is empty)`);
    }
  }
  console.log(`Browser smoke passed: ${passed} scenarios`);
} finally {
  await browser?.close();
  await server.close();
}
