import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog import Catalog
from collect import CollectionError, SOURCES, from_feed, from_list, from_zhipu_research
from library import preview, sync

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
        with patch("library.preview", wraps=lambda key, url: preview(key, url, self.fetch)):
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
        self.store.withdraw(article_id)
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
