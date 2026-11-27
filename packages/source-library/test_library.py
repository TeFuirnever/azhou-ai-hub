import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from catalog import Catalog
from collect import CollectionError, SOURCES, from_feed, from_list, from_zhipu_research
from library import parse_args, preview, run, sync

URL = "https://openai.com/index/library-fixture/"
ALIAS = "https://openai.com/index/library-alias/"
OTHER = "https://openai.com/index/new-fixture/"
IMAGE = "https://cdn.openai.com/library-test.png"
FEED = SOURCES["openai"]["feed"]
PRIVATE = "marker-private-body-hard-to-guess"


def rss(*urls):
    entries = "".join(f"<item><title>Fixture</title><link>{url}</link></item>" for url in urls)
    return f'<rss version="2.0"><channel>{entries}</channel></rss>'.encode()


def html(content, canonical=URL):
    return f"""<!doctype html><html lang="en"><head>
    <link rel="canonical" href="{canonical}"><meta name="author" content="Test author"></head>
    <body><main><article><h1>Archive fixture</h1>
    <time datetime="2025-01-01">January 1, 2025</time>
    <p>{content}</p><figure><img src="{IMAGE}" alt="chart"><figcaption>Caption</figcaption></figure>
    <pre id="snippet"><code>print(1)</code></pre><table><tr><td>A</td></tr></table>
    <a href="#snippet">View the example</a>
    <a href="javascript:alert(1)" onclick="alert(1)">Unsafe example</a>
    <script>never-export</script></article></main></body></html>""".encode()


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Catalog(self.root / "private")
        self.addCleanup(self.store.db.close)
        self.responses = {
            FEED: (rss(URL), FEED, "application/rss+xml"),
            URL: (html(PRIVATE), URL, "text/html"),
            IMAGE: (b"fixture image", IMAGE, "image/png"),
        }

    def fetch(self, url, hosts, limit=None):
        from urllib.parse import urlsplit
        self.assertIn(urlsplit(url).netloc, hosts)
        value = self.responses.get(url, CollectionError("upstream timed out"))
        if isinstance(value, CollectionError):
            raise value
        return value

    def test_preview_and_formal_collection_have_the_same_candidates(self):
        from argparse import Namespace
        from library import run
        nonexistent = self.root / "preview-private"
        with patch("library.preview", wraps=lambda key, url, **kwargs: preview(key, url, self.fetch, **kwargs)):
            outcome = run(Namespace(action="preview", data=nonexistent, source="openai", url=None))
        self.assertFalse(nonexistent.exists())
        self.assertEqual(self.store.entries(), [])
        self.assertEqual(self.store.runs(), [])
        sync(self.store, ["openai"], fetcher=self.fetch)
        self.assertEqual(self.store.entries()[0]["original_url"], outcome["preview"][0]["url"])

    def test_saved_page_import_keeps_text_without_requesting_media(self):
        from argparse import Namespace
        from library import run

        selected = self.root / "saved.html"
        selected.write_bytes(html(PRIVATE))
        with patch("library.fetch", side_effect=AssertionError("unexpected network request")):
            result = run(Namespace(action="archive", data=self.store.root, source="openai",
                                   url=URL, saved_html=selected, basis="Fixture for private review"))
        revision = self.store.inspect(result["id"])["revision"]
        self.assertIn(PRIVATE, revision["body"])
        self.assertIn("Caption", revision["body"])
        self.assertEqual(revision["media"], [])

    def test_manual_fetch_retains_selected_article_and_requires_media_opt_in(self):
        argv = ["library.py", "--data", str(self.store.root), "archive", "openai", URL,
                "--fetch-original", "--basis", "Fixture retention grant"]
        with patch("sys.argv", argv):
            args = parse_args()
        with patch("library.fetch", wraps=self.fetch) as request:
            result = run(args)
            self.assertEqual([call.args[0] for call in request.call_args_list], [URL])
        revision = self.store.inspect(result["id"])["revision"]
        self.assertIn(PRIVATE, revision["body"])
        self.assertEqual(revision["retention_basis"], args.basis)
        self.assertEqual((self.store.root / "objects" / revision["raw_object"]).read_bytes(), html(PRIVATE))
        self.assertEqual(revision["media"], [])
        self.assertIn(f"image: {IMAGE}", result["missing"])
        self.assertEqual(self.store.export(self.root / "no-approval"), 0)

        with patch("sys.argv", [*argv, "--include-images"]):
            args = parse_args()
        with patch("library.fetch", wraps=self.fetch) as request:
            result_with_image = run(args)
            self.assertEqual([call.args[0] for call in request.call_args_list], [URL, IMAGE])
        self.assertEqual(result_with_image["id"], result["id"])
        self.assertEqual(result_with_image["completeness"], "complete")
        self.assertNotEqual(result_with_image["revision"], result["revision"])

    def test_manual_sync_retries_transient_listing_once(self):
        failure = CollectionError("temporary upstream error")
        failure.__cause__ = HTTPError(FEED, 503, "Unavailable", Message(), None)
        replies = [failure, self.responses[FEED]]
        with patch("collect.fetch", side_effect=replies) as request, patch("collect.sleep") as delay:
            outcome = sync(self.store, ["openai"])
        self.assertEqual(outcome["openai"]["status"], "updated")
        self.assertEqual(request.call_count, 2)
        self.assertLess(request.call_args.kwargs["timeout"], 20)
        delay.assert_called_once_with(1)

    def test_manual_sync_respects_retry_after_and_reports_failure(self):
        headers = Message()
        headers["Retry-After"] = "60"
        failure = CollectionError("temporarily unavailable; retry later")
        failure.__cause__ = HTTPError(FEED, 503, "Unavailable", headers, None)
        with patch("collect.fetch", side_effect=failure) as request, patch("collect.sleep") as delay:
            outcome = sync(self.store, ["openai"])
        self.assertEqual(outcome["openai"]["status"], "failed")
        self.assertEqual(self.store.runs()[0]["reason"], str(failure))
        request.assert_called_once()
        delay.assert_not_called()

    def test_json_source_preview_and_sync_reuse_existing_identity(self):
        endpoint = "https://openai.com/news/index.json"
        config = self.root / "config.json"
        config.write_text(json.dumps({
            "url": endpoint, "itemsPath": "data.0.articles",
            "titlePaths": ["display.title", "title"],
            "urlTemplate": "{raw:href}", "urlTemplateFallback": "/index/{slug}/",
            "publishedAtPath": "date",
        }))
        payload = {"data": [{"articles": [
            {"display": {"title": "Existing"}, "href": URL + "?utm_source=json"},
            {"title": "New candidate", "slug": "new-fixture", "date": "2026-11-26"},
        ]}]}
        self.assertEqual(sync(self.store, ["openai"], fetcher=self.fetch)["openai"]["added"], 1)
        scratch = self.root / "no-preview-catalog"
        with patch("ingest.fetch_listing", return_value=(json.dumps(payload).encode(), endpoint, "application/json")) as fetch:
            with patch("sys.argv", ["library.py", "--data", str(scratch), "preview", "openai", "--json-config", str(config)]):
                result = run(parse_args())
            self.assertFalse(scratch.exists())
            self.assertEqual(result["found"], 2)
            self.assertEqual(result["preview"][1]["published"], "2026-11-26")
            self.assertEqual(sync(self.store, ["openai"], json_config=config)["openai"]["added"], 1)
            self.assertEqual(sync(self.store, ["openai"], json_config=config)["openai"]["status"], "no_updates")
        fetch.assert_called_with(endpoint, {"openai.com"})
        self.assertEqual(len(self.store.entries()), 2)
        self.assertEqual(self.store.export(self.root / "no-json-approval"), 0)

    def test_external_batch_is_offline_and_candidate_only(self):
        payload = self.root / "batch.json"
        payload.write_text(json.dumps({"sourceId": "openai", "sourceName": "Fixture crawler", "items": [
            {"title": "Existing", "url": URL},
            {"title": "New candidate", "url": OTHER, "publishedAt": "2026-11-26T08:00:00+08:00",
             "body": PRIVATE, "scope": "full", "raw": {"_aihot": {"backfill": True}}},
            {"title": "Duplicate", "url": OTHER + "?utm_source=crawler"},
            {"title": "Outside source", "url": "https://example.org/index/new"},
            {"title": "Malformed URL", "url": "https://[invalid"},
            {"url": ALIAS},
        ]}))
        sync(self.store, ["openai"], fetcher=self.fetch)
        before_runs = self.store.runs()
        argv = ["library.py", "--data", str(self.store.root), "import-json", str(payload)]
        with patch("ingest.fetch_listing", side_effect=AssertionError("unexpected network request")):
            with patch("sys.argv", [*argv, "--dry-run"]):
                previewed = run(parse_args())
            self.assertEqual(len(self.store.entries()), 1)
            self.assertEqual((previewed["received"], previewed["eligible"], previewed["skipped"],
                              previewed["duplicates"]), (6, 2, 3, 1))
            with patch("sys.argv", argv):
                result = run(parse_args())
                repeated = run(parse_args())
        self.assertEqual((result["added"], result["already_known"]), (1, 1))
        self.assertEqual(repeated["added"], 0)
        self.assertEqual(self.store.runs(), before_runs)
        entry = next(entry for entry in self.store.entries() if entry["url"] == OTHER.rstrip("/"))
        self.assertEqual(entry["published"], "2026-11-26T08:00:00+08:00")
        self.assertIsNone(entry["scope"])
        self.assertIsNone(self.store.inspect(entry["id"])["revision"])
        self.assertEqual(self.store.export(self.root / "before-approval"), 0)
        self.store.approve(entry["id"], "link", "fixture use", "Editorial note")
        output = self.root / "after-approval"
        self.assertEqual(self.store.export(output), 1)
        self.assertNotIn(PRIVATE, (output / "manifest.json").read_text())

    def test_bad_external_batches_leave_catalog_unopened(self):
        path = self.root / "rejected.json"
        target = self.root / "unopened"
        item = {"title": "Fixture", "url": URL}
        cases = [
            ({"sourceId": "unknown", "items": [item]}, "sourceId is not registered"),
            ({"sourceId": "openai", "items": [item] * 51}, "max 50"),
            ({"sourceId": "openai", "items": [{"title": "Missing URL"}]}, "no candidates matched"),
        ]
        for payload, error in cases:
            with self.subTest(error=error):
                path.write_text(json.dumps(payload))
                with patch("sys.argv", ["library.py", "--data", str(target), "import-json", str(path)]):
                    with self.assertRaisesRegex(CollectionError, error):
                        run(parse_args())
                self.assertFalse(target.exists())

    def test_json_config_or_response_error_is_not_no_updates(self):
        config = self.root / "config.json"
        settings = {"url": "https://another.example/feed.json", "itemsPath": "items",
                    "titlePaths": ["title"], "urlTemplate": "{raw:url}"}
        config.write_text(json.dumps(settings))
        with patch("ingest.fetch_listing") as fetch:
            outcome = sync(self.store, ["openai"], json_config=config)["openai"]
            self.assertEqual(outcome["status"], "failed")
            fetch.assert_not_called()
        settings["url"] = "https://openai.com/news/feed.json"
        config.write_text(json.dumps(settings))
        with patch("ingest.fetch_listing", return_value=(b'{"error":"upstream"}', settings["url"], "application/json")):
            outcome = sync(self.store, ["openai"], json_config=config)["openai"]
            self.assertEqual(outcome["status"], "failed")
            self.assertIn("did not select an array", outcome["reason"])

    def test_cli_keeps_private_storage_outside_git_checkouts(self):
        from argparse import Namespace
        from library import run

        checkout = self.root / "checkout"
        checkout.mkdir()
        (checkout / ".git").touch()
        target = checkout / "archive"
        with self.assertRaisesRegex(CollectionError, "outside Git checkouts"):
            run(Namespace(action="list", data=target))
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(CollectionError, "outside Git checkouts"):
            run(Namespace(action="backup", data=self.store.root, target=target))
        self.assertFalse(target.exists())

    def test_manual_source_without_input_is_usage_error(self):
        from contextlib import redirect_stderr
        from io import StringIO

        target = self.root / "unopened"
        for action in ("preview", "sync"):
            with self.subTest(action=action):
                command = ["library.py", "--data", str(target), action, "mimo"]
                diagnostic = StringIO()
                with patch("sys.argv", command), redirect_stderr(diagnostic):
                    with self.assertRaises(SystemExit) as raised:
                        run(parse_args())
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("add --url <official article URL>", diagnostic.getvalue())
                self.assertFalse(target.exists())

    def test_unchanged_failure_invalid_response_and_recovery(self):
        self.assertEqual(sync(self.store, ["openai"], fetcher=self.fetch)["openai"]["status"], "updated")
        self.assertEqual(sync(self.store, ["openai"], fetcher=self.fetch)["openai"]["status"], "no_updates")
        succeeded = self.store.runs()[0]["last_success"]
        self.responses[FEED] = CollectionError("upstream timed out")
        self.assertEqual(sync(self.store, ["openai"], fetcher=self.fetch)["openai"]["status"], "failed")
        self.assertEqual(self.store.runs()[0]["last_success"], succeeded)
        self.responses[FEED] = (b"<html></html>", FEED, "text/html")
        self.assertEqual(sync(self.store, ["openai"], fetcher=self.fetch)["openai"]["status"], "failed")
        self.assertEqual(len(self.store.entries()), 1)
        self.responses[FEED] = (rss(URL, OTHER), FEED, "application/rss+xml")
        self.assertEqual(sync(self.store, ["openai"], fetcher=self.fetch)["openai"]["added"], 1)
        self.assertEqual(len(self.store.entries()), 2)

    def test_list_prefers_candidates_and_reports_template_failure(self):
        base = "https://www.kimi.ai/blog/"
        valid = b'<main><a href="/contact">Contact</a><a href="/blog/article"><h3>Valid article</h3></a></main>'
        [item] = from_list(SOURCES["kimi"], valid, base)
        self.assertEqual(item.url, base + "article")
        self.assertEqual(item.title, "Valid article")
        with self.assertRaises(CollectionError):
            from_list(SOURCES["kimi"], b'<main><a href="/contact">Contact</a></main>', base)
        with self.assertRaises(CollectionError):
            from_feed(SOURCES["openai"], b'<!DOCTYPE rss [<!ENTITY a "bad">]><rss><channel>&a;</channel></rss>')

    def test_lists_extract_labels_and_structured_publisher_entries(self):
        kimi = "https://www.kimi.ai/blog/"
        card = b'<main><div><a href="/blog/test" aria-label="Fixture news"></a><span>2026-10-10</span></div></main>'
        [item] = from_list(SOURCES["kimi"], card, kimi)
        self.assertEqual((item.title, item.published), ("Fixture news", "2026-10-10"))
        zhipu = SOURCES["zhipu"]["lists"][0]
        data = json.dumps({"blogsItems": [{"id": 1, "title_zh": "示例", "createAt": "2026-10-10"}]})
        markup = f"<script>self.__next_f.push({json.dumps([1, data])})</script>".encode()
        [item] = from_zhipu_research(SOURCES["zhipu"], markup, zhipu)
        self.assertEqual((item.url, item.title), (zhipu + "/1", "示例"))
        with self.assertRaises(CollectionError):
            from_zhipu_research(SOURCES["zhipu"], b"<html></html>", zhipu)

    def test_archive_approval_export_revisions_and_withdrawal(self):
        entry = self.store.archive("openai", URL, "local fixture", self.fetch)
        article_id = entry["id"]
        self.assertEqual(entry["completeness"], "complete")
        self.store.approve(article_id, "link", "local fixture", "Public overview")
        first = self.root / "first"
        self.store.export(first)
        metadata = (first / "manifest.json").read_text()
        self.assertNotIn(PRIVATE, metadata)
        self.assertEqual(list((first / "media").iterdir()), [])
        self.store.approve(article_id, "full", "local fixture", "Public overview", entry["revision"])
        self.responses[URL] = (html("new pending version"), URL, "text/html")
        newer = self.store.archive("openai", URL, "local fixture", self.fetch)
        self.assertNotEqual(entry["revision"], newer["revision"])
        second = self.root / "second"
        self.store.export(second)
        [public] = json.loads((second / "manifest.json").read_text())["articles"]
        [previous] = json.loads(metadata)["articles"]
        self.assertEqual(public["first_published"], previous["first_published"])
        self.assertIn(PRIVATE, public["body"])
        self.assertIn("<figcaption>Caption</figcaption>", public["body"])
        self.assertIn("<code>print(1)</code>", public["body"])
        self.assertIn('href="#snippet"', public["body"])
        self.assertIn("<table>", public["body"])
        self.assertNotIn("javascript:", public["body"])
        self.assertNotIn("new pending version", public["body"])
        self.assertEqual(len(list((second / "media").iterdir())), 1)
        def withdraw(*options):
            with patch("sys.argv", ["library.py", "--data", str(self.store.root),
                                    "withdraw", article_id, *options]):
                return run(parse_args())

        database = self.store.root / "catalog.sqlite3"
        before = database.read_bytes()
        with patch("sys.stderr"):
            with self.assertRaises(SystemExit) as legacy:
                withdraw()
        self.assertEqual(legacy.exception.code, 2)
        preview = withdraw("--preview")
        self.assertEqual(preview["scope"], "full")
        self.assertEqual(database.read_bytes(), before)
        self.store.approve(article_id, "link", "local fixture", "New review")
        with self.assertRaisesRegex(CollectionError, "approval changed"):
            withdraw("--apply", preview["plan_id"])
        current = withdraw("--preview")
        self.assertEqual(current["scope"], "link")
        self.assertEqual(withdraw("--apply", current["plan_id"])["withdrawn"], article_id)
        self.assertEqual(withdraw("--preview")["status"], "no_approval")
        self.assertEqual(self.store.inspect(article_id, newer["revision"])["revision"]["digest"], newer["revision"])
        third = self.root / "third"
        self.assertEqual(self.store.export(third), 0)
        self.assertEqual(list((third / "media").iterdir()), [])

    def test_canonical_alias_merges_candidates_and_preserves_stable_id(self):
        self.responses[FEED] = (rss(URL, ALIAS), FEED, "application/rss+xml")
        self.responses[ALIAS] = (html(PRIVATE), ALIAS, "text/html")
        sync(self.store, ["openai"], fetcher=self.fetch)
        canonical = self.store.lookup(URL)
        saved = self.store.archive("openai", ALIAS, "local fixture", self.fetch)
        self.assertEqual(saved["id"], canonical)
        self.assertEqual(self.store.lookup(ALIAS), canonical)
        self.assertEqual(len(self.store.entries()), 1)
        self.assertEqual(sync(self.store, ["openai"], fetcher=self.fetch)["openai"]["added"], 0)

    def test_full_approval_uses_the_requested_revisions_metadata(self):
        original = self.store.archive("openai", URL, "local fixture", self.fetch)
        updated = html(PRIVATE).replace(b"Archive fixture", b"Updated title").replace(b"Test author", b"New author")
        self.responses[URL] = (updated, URL, "text/html")
        latest = self.store.archive("openai", URL, "local fixture", self.fetch)
        self.assertNotEqual(original["revision"], latest["revision"])
        previous = self.store.inspect(original["id"], original["revision"])
        self.assertEqual((previous["title"], previous["author"]), ("Archive fixture", "Test author"))
        self.store.approve(original["id"], "full", "local fixture", "Public overview", original["revision"])
        exported = self.root / "metadata-export"
        self.store.export(exported)
        [item] = json.loads((exported / "manifest.json").read_text())["articles"]
        self.assertEqual((item["title"], item["author"]), ("Archive fixture", "Test author"))

    def test_reimport_of_an_old_revision_becomes_latest(self):
        original = self.store.archive("openai", URL, "local fixture", self.fetch)
        prior_media = self.responses[IMAGE]
        self.responses[IMAGE] = CollectionError("fixture image unavailable")
        interim = self.store.archive("openai", URL, "local fixture", self.fetch)
        self.assertNotEqual(original["revision"], interim["revision"])
        self.responses[IMAGE] = prior_media
        reverted = self.store.archive("openai", URL, "local fixture", self.fetch)
        self.assertEqual(original["revision"], reverted["revision"])
        entry = self.store.inspect(original["id"])
        self.assertEqual(entry["revision"]["digest"], original["revision"])
        self.assertEqual(self.store.entries()[0]["missing"], "[]")

    def test_restore_preserves_links_approvals_and_media(self):
        saved = self.store.archive("openai", URL, "local fixture", self.fetch)
        self.store.approve(saved["id"], "full", "local fixture", "Public overview", saved["revision"])
        initial = self.root / "initial"
        self.store.export(initial)
        restored = self.root / "restored"
        self.store.backup(restored)
        rebuilt = self.root / "rebuilt"
        with Catalog(restored) as reopened:
            reopened.export(rebuilt)
        self.assertEqual((initial / "manifest.json").read_bytes(), (rebuilt / "manifest.json").read_bytes())
        self.assertEqual(list((initial / "media").iterdir())[0].read_bytes(),
                         list((rebuilt / "media").iterdir())[0].read_bytes())

    def test_missing_image_is_recorded_without_losing_text(self):
        self.responses[IMAGE] = CollectionError("fixture image unavailable")
        saved = self.store.archive("openai", URL, "local fixture", self.fetch)
        self.assertEqual(saved["completeness"], "partial")
        entry = self.store.inspect(saved["id"])
        self.assertIn(IMAGE, entry["revision"]["missing"][0])
        self.assertIn(PRIVATE, entry["revision"]["body"])
        self.assertEqual(entry["revision"]["media"], [])


if __name__ == "__main__":
    unittest.main()
