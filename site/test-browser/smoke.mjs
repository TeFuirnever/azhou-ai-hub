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
      await until(() => page.evaluate(`document.readyState === "complete" &&
        location.pathname === ${JSON.stringify(support)} && location.hash === "#get-help"`),
        "Help opens at the right section");
      const visibleLinks = await page.evaluate(`[...document.querySelectorAll("main a")]
        .filter(link => link.getClientRects().length).map(link => link.href)`);
      const expectedLinks = [discovery, ...["/discussions", "/issues/new?template=bug.yml", "/security/advisories/new"]
        .map(target => site.githubUrl + target)];
      for (const href of expectedLinks) {
        assert.ok(visibleLinks.includes(href), `The ${href} action is visible`);
      }
      await page.click("#switch-language");
      const other = lang === "en" ? "zh" : "en";
      const translated = site.pathPrefix + site.routes[other].support.slice(1);
      await until(() => page.evaluate(`document.readyState === "complete" &&
        location.pathname === ${JSON.stringify(translated)} && location.hash === "#get-help"`),
        "Changing language keeps the help section");
    });
    const skillsPath = site.routes[lang].skills;

    const installCommand = `npx skills add ${site.siteUrl}${site.askAzhouDownloadPath} --agent codex`;
    for (const entry of [`${site.routes[lang].home}#install`, `${skillsPath}#super-ask-azhou`]) {
      await check(`${lang}: copy the Ask Azhou download command from ${entry} at ${width}px`, { width }, entry, async page => {
        const manual = '[data-manual-install="super-ask-azhou"]';
        const source = "#install-super-ask-azhou";
        await page.permission("clipboard-read", "granted");
        await page.permission("clipboard-write", "granted");
        if (!await isOpen(page, manual)) await page.click(`${manual} > summary`);
        await page.click('button[data-copy="install-super-ask-azhou"]');
        assert.equal(await page.evaluate(`document.querySelector("${source}").textContent`), installCommand);
        assert.equal(await page.evaluate("navigator.clipboard.readText()"), installCommand);
        assert.ok(await page.evaluate(`document.querySelector("${source}").parentElement.scrollWidth <=
          document.querySelector("${source}").parentElement.clientWidth + 1`), "The command fits without horizontal scrolling");
      });
    }
    await check(`${lang}: install prompt opens on clipboard denial`, { width }, `${site.routes[lang].home}#install`, async page => {
      const prompt = "#agent-install-super-ask-azhou";
      const fallback = ".home-setup-copy [data-copy-fallback]";
      const copy = 'button[data-copy="agent-install-super-ask-azhou"]';
      await until(() => page.evaluate(`document.querySelector('${copy}').getClientRects().length > 0`), "Install copy button is ready");
      assert.equal(await isOpen(page, fallback), false, "The raw prompt stays closed normally");
      await page.permission("clipboard-write", "denied");
      await page.click(copy);
      await until(() => isOpen(page, fallback), "Denied copy opens the manual prompt");
      assert.ok(await page.evaluate(`document.querySelector('${prompt}').getClientRects().length > 0`));
      assert.equal(await page.evaluate(`document.activeElement.matches('${copy}')`), true, "Recovery keeps focus at the action");
    });
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

      await page.click("#clear-skill-search");
      await page.click("#ask-azhou-install-link");
      await until(() => isOpen(page, `${row} > details`), "Ask Azhou opens after clearing search");
      assert.equal(await page.evaluate('document.querySelector("#skill-search").value'), "");
      await page.click("#switch-language");
      const other = lang === "en" ? "zh" : "en";
      const translated = site.pathPrefix + site.routes[other].skills.slice(1);
      const undo = other === "zh" ? "撤销清除" : "Undo clear";
      await until(() => page.evaluate(`document.readyState === "complete" &&
        location.pathname === ${JSON.stringify(translated)} && location.hash === "${row}" &&
        document.querySelector("#clear-skill-search")?.textContent === ${JSON.stringify(undo)}`),
        "Changing language keeps the open Ask Azhou card and the undo action");
      await page.click("#clear-skill-search");
      assert.equal(await page.evaluate('document.querySelector("#skill-search").value'), "super-archify");

      await page.evaluate(`document.querySelector("${row} summary").focus()`);
      await page.key("Enter");
      await page.click("#switch-language");
      const original = site.pathPrefix + skillsPath.slice(1);
      await until(() => page.evaluate(`document.readyState === "complete" && location.pathname === ${JSON.stringify(original)}`),
        "Returns to the original language");
      assert.equal(await page.evaluate("location.hash"), "");
      assert.equal(await page.evaluate(`document.querySelector("${row} > details").open`), false);
      assert.equal(await page.evaluate('document.querySelector("#skill-search").value'), "super-archify");
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
    await check(`${lang}: cursor pendant stays local and respects input preferences`, { width: 1100 }, site.routes[lang].home, async page => {
      const toggle = "[data-cursor-pendant-toggle]";
      const pendant = "[data-cursor-pendant]";
      const grid = ".cursor-demo-grid";
      assert.ok(await page.evaluate('matchMedia("(hover: hover) and (pointer: fine)").matches'),
        "The desktop Chrome fixture must report a fine pointer");
      const hidden = async selector => Object.hasOwn(await page.attributes(selector), "hidden");
      const pressed = async () => (await page.attributes(toggle))["aria-pressed"];
      const setMotion = (value, extra = []) => page.command("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-reduced-motion", value }, ...extra],
      });
      assert.ok(await hidden(toggle), "Reduced motion uses the static preview");
      assert.equal(await page.evaluate(`document.querySelectorAll("${grid} .cursor-demo-tile").length`), 4);
      const download = 'section[aria-labelledby="cursor-theme"] a[download]';
      assert.ok((await page.attributes(download)).href.endsWith("/Azhou-Double-Hug-3.6.1.cape"));
      await setMotion("no-preference");
      await until(async () => !(await hidden(toggle)), "Fine pointer reveals the pendant toggle");
      assert.equal(await pressed(), "false");
      const centerDemo = () => page.evaluate(`(async () => {
        const demo = document.querySelector("${grid}");
        demo.scrollIntoView({ block: "center", behavior: "instant" });
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const { left, top, width, height } = demo.getBoundingClientRect();
        const x = left + width / 2;
        const y = top + height / 2;
        return { left, top, right: left + width, bottom: top + height, x, y,
          reachable: demo.contains(document.elementFromPoint(x, y)) };
      })()`);
      const move = (x, y) => page.command("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
      const clickToggleAndReturnToDemo = async expected => {
        await page.click(toggle);
        assert.equal(await pressed(), expected, "The button accepts an actual mouse click");
        const current = await centerDemo();
        assert.ok(current.reachable, "The demo center is a valid mouse target after scrolling");
        await move(current.x, current.y);
      };
      const point = await centerDemo();
      assert.ok(point.reachable, "The demo center is a valid mouse target");
      await move(point.x, point.y);
      assert.ok(await hidden(pendant), "Moving the pointer cannot enable the pendant");
      await page.evaluate(`document.querySelector("${toggle}").focus({ preventScroll: true })`);
      await page.key("Enter");
      assert.equal(await pressed(), "true");
      assert.ok(await hidden(pendant), "Enabling still waits for movement inside the demo");
      await move(point.x + 8, point.y);
      await until(async () => !(await hidden(pendant)), "The pendant appears with the mouse in the demo");
      await move(point.right - 3, point.bottom - 3);
      await until(() => page.evaluate(`(() => {
        const grid = document.querySelector("${grid}").getBoundingClientRect();
        const pendant = document.querySelector("${pendant}");
        const pos = pendant.getBoundingClientRect();
        return pos.width > 0 && pos.left >= grid.left && pos.right <= grid.right
          && pos.top >= grid.top && pos.bottom <= grid.bottom
          && getComputedStyle(pendant).pointerEvents === "none";
      })()`), "The decorative pendant remains inside the demo at the lower-right edge");

      const grab = "#cursor-demo-grab";
      const target = await page.evaluate(`(() => {
        const rect = document.querySelector("${grab}").getBoundingClientRect();
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
      })()`);
      const mouse = { ...target, button: "left", clickCount: 1 };
      await move(target.x, target.y);
      await page.command("Input.dispatchMouseEvent", { ...mouse, type: "mousePressed" });
      assert.equal((await page.attributes(grab))["data-grabbing"], "true");
      await page.command("Input.dispatchMouseEvent", { ...mouse, type: "mouseReleased" });
      assert.ok(!Object.hasOwn(await page.attributes(grab), "data-grabbing"));
      await move(point.x, point.bottom + 20);
      await until(() => hidden(pendant), "Leaving the demo hides the pendant");
      assert.equal(await pressed(), "true");
      const text = await page.evaluate(`(() => {
        const content = document.querySelector('section[aria-labelledby="cursor-theme"] .home-setup-copy p').firstChild;
        const sample = new Range();
        sample.setStart(content, 0);
        sample.setEnd(content, 8);
        const rect = sample.getBoundingClientRect();
        return { left: rect.left, right: rect.right, y: rect.top + rect.height / 2, expected: sample.toString().trim() };
      })()`);
      const start = { x: text.left + 1, y: text.y };
      const end = { x: text.right - 1, y: text.y };
      await page.command("Input.dispatchMouseEvent", { ...start, type: "mousePressed", button: "left", clickCount: 1 });
      await page.command("Input.dispatchMouseEvent", { ...end, type: "mouseMoved", button: "left", buttons: 1 });
      await page.command("Input.dispatchMouseEvent", { ...end, type: "mouseReleased", button: "left", clickCount: 1 });
      assert.equal(await page.evaluate("getSelection().toString().trim()"), text.expected);

      await move(point.x, point.y);
      await until(async () => !(await hidden(pendant)), "Returning to the demo restores the pendant");
      await setMotion("reduce");
      await until(() => hidden(pendant), "Changing the motion preference hides the active pendant");
      assert.ok(await hidden(toggle));
      await setMotion("no-preference");
      await until(async () => !(await hidden(toggle)), "The toggle returns when preferences allow it");
      assert.equal(await pressed(), "false", "Restoring preferences must not reactivate the pendant");
      await clickToggleAndReturnToDemo("true");
      await until(async () => !(await hidden(pendant)), "Click can enable the pendant again");
      await setMotion("no-preference", [{ name: "forced-colors", value: "active" }]);
      await until(() => hidden(pendant), "Forced colors hides the active pendant");
      assert.ok(await hidden(toggle));
      await setMotion("no-preference");
      await until(async () => !(await hidden(toggle)), "Leaving forced colors restores the toggle");
      assert.equal(await pressed(), "false");
      await clickToggleAndReturnToDemo("true");
      await until(async () => !(await hidden(pendant)), "The pendant can be enabled again after forced colors");
      await clickToggleAndReturnToDemo("false");
      assert.ok(await hidden(pendant), "Closing remains effective on later mouse movement");
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

    const selectedSource = library.entries[0]?.sources[0];
    if (selectedSource) {
      const sourcePath = `${path}sources/${selectedSource}/`;
      await check(`${lang}: return from an article to its source selections`, { width }, sourcePath, async page => {
        const article = ".library-source-content .edition-item:first-child h3 a";
        await page.evaluate(`document.querySelector("${article}").focus()`);
        await page.key("Enter");
        await until(() => page.evaluate(`document.querySelector("#library-return")?.pathname === ${JSON.stringify(site.pathPrefix + sourcePath.slice(1))}`), "Article return points at the originating source");
        await page.evaluate('document.querySelector("#library-return").focus()');
        await page.key("Enter");
        await until(() => page.evaluate(`location.pathname === ${JSON.stringify(site.pathPrefix + sourcePath.slice(1))}`), "Returns to the originating source");
      });
    }

    if (query) {
      await check(`${lang}: built Pagefind index answers a real query`, { width }, `${path}#results-title`, async page => {
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
        const other = lang === "en" ? "zh" : "en";
        const translated = site.pathPrefix + site.routes[other].library.slice(1);
        const draft = " unfinished draft";
        await page.evaluate('document.querySelector("#library-query").focus()');
        await page.command("Input.insertText", { text: draft });
        assert.equal(await page.evaluate('document.querySelector("#library-query").value'), query.query + draft);
        await page.evaluate(`document.querySelector('#library-results [data-entry-id="${query.id}"] h3 a').focus()`);
        await page.key("Enter");
        await until(() => page.evaluate(`document.querySelector("#library-return")?.search.includes("q=")`), "Article remembers its query");
        await page.evaluate('document.querySelector("#switch-language").focus()');
        await page.key("Enter");
        await until(() => page.evaluate(`document.querySelector("#library-return")?.pathname === ${JSON.stringify(translated)} && document.querySelector("#library-return").search.includes("q=")`),
          "The translated article keeps its return query");
        await page.evaluate('document.querySelector("#library-return").focus()');
        await page.key("Enter");
        await until(() => page.evaluate(`location.pathname === ${JSON.stringify(translated)} && document.querySelector("#library-status")?.dataset.state === "done"`),
          "The translated list restores the search results");
        assert.equal(await page.evaluate('document.querySelector("#library-query").value'), query.query + draft);
        assert.equal(await page.evaluate("location.hash"), "#results-title");
        assert.equal(await page.evaluate(`Boolean(document.querySelector('#library-results [data-entry-id="${query.id}"]'))`), true);
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
