"""Private catalog and publication approvals."""

import hashlib
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

from collect import CollectionError, IMAGE_TYPES, SOURCES, clean_body, normalized_url, read_article, timestamp

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY, url TEXT UNIQUE NOT NULL, original_url TEXT NOT NULL,
    title TEXT NOT NULL, published TEXT, author TEXT, lang TEXT, first_exported TEXT,
    latest_revision TEXT
);
CREATE TABLE IF NOT EXISTS aliases (
    url TEXT PRIMARY KEY, article_id TEXT NOT NULL REFERENCES articles(id)
);
CREATE TABLE IF NOT EXISTS sources (
    source TEXT NOT NULL, article_id TEXT NOT NULL REFERENCES articles(id),
    PRIMARY KEY (source, article_id)
);
CREATE TABLE IF NOT EXISTS source_runs (
    source TEXT PRIMARY KEY, status TEXT NOT NULL, attempted TEXT NOT NULL,
    last_success TEXT, added INTEGER, reason TEXT
);
CREATE TABLE IF NOT EXISTS revisions (
    article_id TEXT NOT NULL REFERENCES articles(id), digest TEXT NOT NULL,
    captured TEXT NOT NULL, raw_object TEXT NOT NULL, retention_basis TEXT NOT NULL,
    body TEXT NOT NULL, media TEXT NOT NULL, missing TEXT NOT NULL, metadata TEXT,
    PRIMARY KEY (article_id, digest)
);
CREATE TABLE IF NOT EXISTS approvals (
    article_id TEXT PRIMARY KEY REFERENCES articles(id), scope TEXT NOT NULL,
    basis TEXT NOT NULL, snapshot TEXT NOT NULL, reviewed TEXT NOT NULL
);
"""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Catalog:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "catalog.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            articles = {column["name"] for column in self.db.execute("PRAGMA table_info(articles)")}
            if "latest_revision" not in articles:
                self.db.execute("ALTER TABLE articles ADD COLUMN latest_revision TEXT")
                self.db.execute("""UPDATE articles SET latest_revision=(
                    SELECT digest FROM revisions WHERE article_id=articles.id ORDER BY rowid DESC LIMIT 1
                )""")
            revisions = {column["name"] for column in self.db.execute("PRAGMA table_info(revisions)")}
            if "metadata" not in revisions:
                self.db.execute("ALTER TABLE revisions ADD COLUMN metadata TEXT")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def lookup(self, url):
        entry = self.db.execute("SELECT article_id FROM aliases WHERE url=?", (normalized_url(url),)).fetchone()
        return entry["article_id"] if entry else None

    def note(self, source, url, title, published):
        key = normalized_url(url)
        article_id = self.lookup(url) or digest(key.encode())[:24]
        self.db.execute(
            "INSERT OR IGNORE INTO articles(id,url,original_url,title,published) VALUES (?,?,?,?,?)",
            (article_id, key, url, title, published),
        )
        self.db.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (key, article_id))
        changed = self.db.execute("INSERT OR IGNORE INTO sources VALUES (?,?)", (source, article_id)).rowcount
        return article_id, changed

    def record_discovery(self, source, candidates, *, update_source_status=True):
        with self.db:
            added = sum(self.note(source, c.url, c.title, c.published)[1] for c in candidates)
            if update_source_status:
                now = timestamp()
                self.db.execute(
                    "INSERT OR REPLACE INTO source_runs VALUES (?,?,?,?,?,NULL)",
                    (source, "updated" if added else "no_updates", now, now, added),
                )
        return added

    def record_failure(self, source, reason):
        with self.db:
            self.db.execute(
                """INSERT INTO source_runs(source,status,attempted,reason) VALUES (?,'failed',?,?)
                   ON CONFLICT(source) DO UPDATE SET status='failed',
                       attempted=excluded.attempted, reason=excluded.reason, added=NULL""",
                (source, timestamp(), reason),
            )

    def runs(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM source_runs ORDER BY source")]

    def entries(self):
        return [dict(row) for row in self.db.execute(
            """SELECT a.*, group_concat(s.source) AS sources, p.scope, p.basis, r.missing
               FROM articles a JOIN sources s ON a.id=s.article_id
               LEFT JOIN approvals p ON a.id=p.article_id
               LEFT JOIN revisions r ON r.article_id=a.id AND r.digest=a.latest_revision
               GROUP BY a.id ORDER BY a.published DESC,a.title"""
        )]

    def put_object(self, raw, suffix):
        name = f"{digest(raw)}.{suffix}"
        directory = self.root / "objects"
        directory.mkdir(mode=0o700, exist_ok=True)
        target = directory / name
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temp:
                temp.write(raw)
                temp_name = Path(temp.name)
            temp_name.replace(target)
        return name

    def archive(self, source_key, url, basis, fetcher, *, keep_images=True):
        if not basis.strip():
            raise CollectionError("provide the basis for retaining this article")
        source = SOURCES[source_key]
        article, body, raw, landed = read_article(source, url, fetcher)
        media = {}
        media_hosts = set(source.get("media", []))
        media_hosts.add(urlsplit(landed).hostname)

        def archive_image(image_url):
            if not keep_images:
                raise CollectionError("image retrieval was not selected")
            if image_url not in media:
                image, _, mime = fetcher(image_url, media_hosts, limit=8_000_000)
                if mime not in IMAGE_TYPES:
                    raise CollectionError(f"unsupported media format {mime}")
                media[image_url] = self.put_object(image, IMAGE_TYPES[mime])
            return "/media/" + media[image_url]

        html, missing = clean_body(body, landed, archive_image)
        raw_object = self.put_object(raw, "html")
        images = sorted(set(media.values()))
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            canonical_id = self.lookup(article["url"])
            original_id = self.lookup(url)
            if canonical_id and original_id and original_id != canonical_id:
                self.merge_unreviewed_alias(original_id, canonical_id)
            known_id = canonical_id or original_id
            if known_id:
                self.db.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (article["url"], known_id))
            if not known_id:
                self.note(source_key, url, article["title"], article["published"])
                known_id = self.lookup(url)
                self.db.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (article["url"], known_id))
            article_id, _ = self.note(source_key, article["url"], article["title"], article["published"])
            self.db.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (normalized_url(url), article_id))
            previous = self.db.execute("SELECT published FROM articles WHERE id=?", (article_id,)).fetchone()
            metadata = {name: article[name] for name in ("url", "title", "published", "author", "lang")}
            metadata["published"] = metadata["published"] or previous["published"]
            content_digest = digest(json_text([metadata, html, images, missing]).encode())
            self.db.execute(
                """INSERT OR IGNORE INTO revisions
                   (article_id,digest,captured,raw_object,retention_basis,body,media,missing,metadata)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (article_id, content_digest, timestamp(), raw_object, basis, html,
                 json_text(images), json_text(missing), json_text(metadata)),
            )
            self.db.execute(
                """UPDATE articles SET url=?,title=?,published=?,author=?,lang=?,latest_revision=? WHERE id=?""",
                (metadata["url"], metadata["title"], metadata["published"], metadata["author"],
                 metadata["lang"], content_digest, article_id),
            )
        return {"id": article_id, "revision": content_digest, "missing": missing,
                "completeness": "partial" if missing else "complete"}

    def merge_unreviewed_alias(self, duplicate, canonical):
        for table in ("approvals", "revisions"):
            if self.db.execute(f"SELECT 1 FROM {table} WHERE article_id=? LIMIT 1", (duplicate,)).fetchone():
                raise CollectionError("both URLs have separate records; resolve the existing archive before merging")
        self.db.execute("INSERT OR IGNORE INTO sources SELECT source,? FROM sources WHERE article_id=?",
                        (canonical, duplicate))
        self.db.execute("DELETE FROM sources WHERE article_id=?", (duplicate,))
        self.db.execute("UPDATE aliases SET article_id=? WHERE article_id=?", (canonical, duplicate))
        self.db.execute("DELETE FROM articles WHERE id=?", (duplicate,))

    def inspect(self, article_id, revision=None):
        entry = self.db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        if entry is None:
            raise CollectionError("article was not found")
        selected = revision or entry["latest_revision"]
        if selected:
            saved = self.db.execute(
                "SELECT * FROM revisions WHERE article_id=? AND digest=?", (article_id, selected)
            ).fetchone()
        else:
            saved = self.db.execute(
                "SELECT * FROM revisions WHERE article_id=? ORDER BY rowid DESC LIMIT 1", (article_id,)
            ).fetchone()
        if revision and saved is None:
            raise CollectionError("revision was not found")
        if saved is None:
            return dict(entry, completeness="metadata", revision=None)
        item = dict(saved)
        item.update(media=json.loads(item["media"]), missing=json.loads(item["missing"]),
                    metadata=json.loads(item["metadata"]) if item["metadata"] else None)
        fields = dict(entry)
        fields.update(item["metadata"] or {})
        return dict(fields, completeness="partial" if item["missing"] else "complete", revision=item)

    def backup(self, target):
        destination = Path(target).expanduser().resolve()
        if destination.exists() or self.root in destination.parents:
            raise CollectionError("backup requires a new directory outside the private archive")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as work:
            backup = Path(work) / "private"
            backup.mkdir(mode=0o700)
            with closing(sqlite3.connect(backup / "catalog.sqlite3")) as database:
                self.db.backup(database)
                objects = set()
                database.row_factory = sqlite3.Row
                for row in database.execute("SELECT raw_object,media FROM revisions"):
                    objects.add(row["raw_object"])
                    objects.update(json.loads(row["media"]))
            (backup / "objects").mkdir(mode=0o700)
            for name in objects:
                raw = (self.root / "objects" / name).read_bytes()
                if digest(raw) != name.split(".")[0]:
                    raise CollectionError(f"archived object failed verification: {name}")
                (backup / "objects" / name).write_bytes(raw)
            backup.rename(destination)

    def approve(self, article_id, scope, basis, note, revision=None, kind="article"):
        entry = self.db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        if not entry or not basis.strip():
            raise CollectionError("choose an existing article and provide the publication basis")
        fields = {name: entry[name] for name in ("id", "url", "title", "published", "author", "lang")}
        fields.update(scope=scope, note=note, kind=kind, lang=fields["lang"] or "en")
        if scope == "full":
            saved = self.db.execute(
                "SELECT * FROM revisions WHERE article_id=? AND digest=?", (article_id, revision)
            ).fetchone()
            if not saved:
                raise CollectionError("full approval requires the digest of a reviewed revision")
            if saved["metadata"] is None:
                raise CollectionError("archive the saved page again to record version metadata before full approval")
            fields.update(json.loads(saved["metadata"]))
            fields.update(body=saved["body"], media=json.loads(saved["media"]), missing=json.loads(saved["missing"]))
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO approvals VALUES (?,?,?,?,?)",
                            (article_id, scope, basis, json_text(fields), timestamp()))

    def withdraw(self, article_id):
        with self.db:
            self.db.execute("DELETE FROM approvals WHERE article_id=?", (article_id,))

    def export(self, target):
        destination = Path(target).expanduser().resolve()
        if destination.exists() or destination == self.root or self.root in destination.parents:
            raise CollectionError("export requires a new directory outside the private archive")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as work:
            content = Path(work) / "public"
            content.mkdir()
            (content / "media").mkdir()
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                items = []
                now = timestamp()
                for approval in self.db.execute(
                    """SELECT p.snapshot,a.id,a.first_exported FROM approvals p
                       JOIN articles a ON p.article_id=a.id ORDER BY a.id"""
                ).fetchall():
                    item = json.loads(approval["snapshot"])
                    item["first_published"] = approval["first_exported"] or now
                    self.db.execute("UPDATE articles SET first_exported=? WHERE id=?",
                                    (item["first_published"], item["id"]))
                    item["sources"] = [row["source"] for row in self.db.execute(
                        "SELECT source FROM sources WHERE article_id=? ORDER BY source", (item["id"],)
                    )]
                    for name in item.pop("media", []):
                        source = self.root / "objects" / name
                        if digest(source.read_bytes()) != name.split(".")[0]:
                            raise CollectionError(f"archived media failed verification: {name}")
                        shutil.copyfile(source, content / "media" / name)
                    items.append(item)
                (content / "manifest.json").write_text(json_text({
                    "sources": {key: {name: row[name] for name in ("name", "home")} for key, row in SOURCES.items()},
                    "articles": items,
                }) + "\n", encoding="utf-8")
                content.rename(destination)
        return len(items)
