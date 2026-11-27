import assert from "node:assert/strict";
import test from "node:test";

import { expectStatus, renderPage, settle, sourceLibrary, startPage } from "../test-support/copy-page.mjs";

const pages = [
  { kind: "home" }, { kind: "empty-home" }, { kind: "library" }, { kind: "skills" },
  ...sourceLibrary.channels.map(source => ({ kind: "source", sourceId: source.id })),
];

for (const lang of ["zh", "en"]) {
  for (const { kind, sourceId } of pages) {
    test(`${lang} ${kind}${sourceId ? `/${sourceId}` : ""}: each copy writes once and only updates its own status, including repeat clicks`, async t => {
      t.mock.timers.enable({ apis: ["setTimeout"] });
      const page = startPage(renderPage(kind, lang, sourceId));
      assert.ok(page.controls.length > 0, "Exercise actual copy controls");
      if (kind === "home") assert.equal(page.controls.length, 4, "RSS, install prompt, install command, terminal example");
      for (const control of page.controls) {
        assert.equal(control.actions.hidden, false);
        for (let repeat = 0; repeat < 2; repeat++) {
          const snapshot = other => [other.message.textContent, other.status.dataset.state ?? ""];
          const before = page.controls.map(snapshot);
          const count = page.writes.length;
          control.button.click();
          assert.equal(page.writes.length, count + 1, `One handler owns ${control.button.dataset.copy}`);
          assert.equal(page.writes.at(-1).text, control.source.textContent);
          await settle(page.writes.at(-1));
          expectStatus(control, "success", lang);
          page.controls.forEach((other, i) => {
            if (other !== control) assert.deepEqual(snapshot(other), before[i], "Do not announce in a neighboring control");
          });
        }
        t.mock.timers.tick(3500);
        expectStatus(control, "", lang);
      }
    });
  }

  for (const clipboard of [false, "missing-write"]) {
    test(`${lang}: missing Clipboard ${clipboard === false ? "API" : "writeText"} leaves every copy action hidden and its text available`, t => {
      t.mock.timers.enable({ apis: ["setTimeout"] });
      for (const { kind, sourceId } of pages) {
        const page = startPage(renderPage(kind, lang, sourceId), { clipboard });
        assert.ok(page.controls.length > 0);
        for (const control of page.controls) {
          assert.equal(control.actions.hidden, true);
          assert.ok(control.source.textContent.trim());
          assert.equal(control.source.closest("[hidden]"), null);
          expectStatus(control, "", lang);
        }
      }
    });
  }

  // Both production handlers share these contracts but have different DOM
  // owners. Run them together on the homepage to catch cross-binding regressions.
  for (const target of ["rss-all-url", "try-prompt"]) {
    function setup(t) {
      t.mock.timers.enable({ apis: ["setTimeout"] });
      const page = startPage(renderPage("home", lang));
      return { ...page, control: page.controls.find(item => item.button.dataset.copy === target) };
    }

    test(`${lang} ${target}: denied writes retain manual recovery and a retry can succeed`, async t => {
      const page = setup(t);
      const { control } = page;
      const text = control.source.textContent;
      control.button.click();
      assert.equal(page.writes.length, 1);
      assert.equal(page.writes[0].text, text);
      await settle(page.writes[0], "error");
      expectStatus(control, "error", lang);
      t.mock.timers.tick(5000);
      expectStatus(control, "error", lang);
      assert.equal(control.source.textContent, text);
      for (const other of page.controls) if (other !== control) expectStatus(other, "", lang);
      control.button.click();
      assert.equal(page.writes.length, 2);
      await settle(page.writes[1]);
      expectStatus(control, "success", lang);
    });

    test(`${lang} ${target}: pending and reset timers belong to the current attempt`, async t => {
      const { control, writes } = setup(t);
      control.button.click();
      t.mock.timers.tick(119);
      expectStatus(control, "", lang);
      t.mock.timers.tick(1);
      expectStatus(control, "pending", lang);
      await settle(writes[0]);
      expectStatus(control, "success", lang);
      t.mock.timers.tick(3400);
      control.button.click();
      t.mock.timers.tick(120);
      expectStatus(control, "pending", lang); // Crosses the previous success's reset deadline.
      t.mock.timers.tick(5000);
      expectStatus(control, "pending", lang);
      await settle(writes[1]);
      t.mock.timers.tick(3499);
      expectStatus(control, "success", lang);
      t.mock.timers.tick(1);
      expectStatus(control, "", lang);
      control.button.click();
      await settle(writes[2]);
      t.mock.timers.tick(120);
      expectStatus(control, "success", lang); // Fast success must not flash a later pending state.
    });

    test(`${lang} ${target}: an older completion cannot cancel the next attempt's pending feedback`, async t => {
      const { control, writes } = setup(t);
      control.button.click();
      t.mock.timers.tick(60);
      control.button.click();
      assert.equal(writes.length, 2);
      await settle(writes[0]);
      expectStatus(control, "", lang);
      t.mock.timers.tick(119);
      expectStatus(control, "", lang);
      t.mock.timers.tick(1);
      expectStatus(control, "pending", lang);
      await settle(writes[1]);
      expectStatus(control, "success", lang);
    });

    for (const latest of ["success", "error"]) {
      test(`${lang} ${target}: an older ${latest === "success" ? "failure" : "success"} cannot overwrite the latest ${latest}`, async t => {
        const { control, writes } = setup(t);
        control.button.click();
        t.mock.timers.tick(120);
        expectStatus(control, "pending", lang);
        control.button.click();
        assert.equal(writes.length, 2);
        await settle(writes[1], latest);
        expectStatus(control, latest, lang);
        await settle(writes[0], latest === "success" ? "error" : "success");
        expectStatus(control, latest, lang);
        t.mock.timers.tick(5000);
        expectStatus(control, latest === "success" ? "" : "error", lang);
      });
    }
  }
}
