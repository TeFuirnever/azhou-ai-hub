"""Collect and normalize public publisher pages without writing to the catalog."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bs4 import BeautifulSoup, Comment
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

source_settings = json.loads(Path(__file__).with_name("sources.json").read_text(encoding="utf-8"))
public_sources = json.loads(
    (Path(__file__).resolve().parents[2] / "site/library-content/sources.json").read_text(encoding="utf-8")
)
if source_settings.keys() != public_sources.keys():
    raise ValueError("collector settings must match the public source directory")
SOURCES = {key: {**public_sources[key], **settings} for key, settings in source_settings.items()}
TRACKING = {"ref", "fbclid", "gclid"}
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "image/avif": "avif"}
BODY_TAGS = frozenset(
    "a abbr b blockquote br caption cite code dd del details div dl dt em figcaption figure "
    "h1 h2 h3 h4 h5 h6 hr i img kbd li mark ol p pre q s samp span strong sub summary sup "
    "table tbody td th thead tfoot tr ul var".split()
)


class CollectionError(ValueError):
    pass


def http_url(value):
    try:
        parts = urlsplit(value)
        return bool(parts.scheme == "https" and parts.hostname and not parts.username
                    and not parts.password and parts.port in (None, 443))
    except ValueError:
        return False


def normalized_url(value):
    parts = urlsplit(value)
    pairs = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
             if key.casefold() not in TRACKING and not key.casefold().startswith("utm_")]
    return urlunsplit(("https", parts.hostname, parts.path.rstrip("/") or "/", urlencode(pairs), ""))


def article_url(source, url):
    if not http_url(url):
        return False
    value = urlsplit(url)
    for prefix in source["articles"]:
        base = urlsplit(prefix)
        if value.hostname == base.hostname and value.path.startswith(base.path):
            if value.path[len(base.path):].strip("/"):
                return True
    return False


class SourceRedirects(HTTPRedirectHandler):
    def __init__(self, allowed):
        self.allowed = allowed

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not http_url(newurl) or urlsplit(newurl).hostname not in self.allowed:
            raise CollectionError("upstream redirected outside the configured hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, hosts, limit=8_000_000):
    if not http_url(url) or urlsplit(url).hostname not in hosts:
        raise CollectionError("URL is outside the configured hosts")
    request = Request(url, headers={"User-Agent": "AzhouSourceLibrary/0.1"})
    try:
        with build_opener(SourceRedirects(hosts)).open(request, timeout=20) as response:
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise CollectionError("response exceeded the byte limit")
            return raw, response.geturl(), response.headers.get_content_type()
    except (URLError, TimeoutError, OSError) as exc:
        raise CollectionError(f"request failed: {exc}") from exc


def as_date(value):
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None
    for parser in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            return parser(value).isoformat()
        except (ValueError, TypeError):
            continue
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str
    published: str | None = None


def from_feed(source, raw):
    try:
        root = ElementTree.fromstring(raw)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise CollectionError("unreadable RSS or Atom") from exc
    channel = root.find("channel")
    if root.tag == "rss" and channel is not None:
        rows = [(item.findtext("link"), item.findtext("title"), item.findtext("pubDate"))
                for item in channel.findall("item")]
    elif root.tag == "{http://www.w3.org/2005/Atom}feed":
        ns = {"a": "http://www.w3.org/2005/Atom"}
        rows = []
        for entry in root.findall("a:entry", ns):
            link = next((tag.get("href") for tag in entry.findall("a:link", ns)
                         if tag.get("rel", "alternate") == "alternate"), None)
            rows.append((link, entry.findtext("a:title", namespaces=ns),
                         entry.findtext("a:published", namespaces=ns)))
    else:
        raise CollectionError("response does not contain an RSS or Atom feed")
    results = [Candidate(url, title.strip(), as_date(date)) for url, title, date in rows
               if url and title and title.strip() and article_url(source, url)]
    if rows and not results:
        raise CollectionError("feed entries did not match the article rules")
    return results


def from_list(source, raw, url):
    soup = BeautifulSoup(raw, "html.parser")
    candidates = {}
    for link in (soup.select_one("main") or soup).select("a[href]"):
        target = urljoin(url, link["href"])
        if not article_url(source, target):
            continue
        heading = link.select_one("h2, h3, h4")
        title = (heading or link).get_text(" ", strip=True) or link.get("aria-label", "").strip()
        if not title or title.casefold() in {"read more", "learn more", "all research", "查看详情", "了解更多", "→"}:
            continue
        time = link.select_one("time")
        date = as_date(time.get("datetime") or time.get_text(strip=True)) if time else None
        if not date and link.get("aria-label"):
            match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", link.parent.get_text(" ", strip=True))
            date = as_date(match.group()) if match else None
        key = normalized_url(target)
        if key not in candidates or date and not candidates[key].published:
            candidates[key] = Candidate(target, title, date)
    if not candidates:
        raise CollectionError("expected article links were absent from the list")
    return list(candidates.values())


def from_zhipu_research(source, raw, url):
    # The visible cards are buttons. The publisher ships their IDs in Next.js data.
    soup = BeautifulSoup(raw, "html.parser")
    decoder = json.JSONDecoder()
    chunks = []
    for script in soup.find_all("script"):
        match = re.match(r"\s*self\.__next_f\.push\(", script.get_text())
        if not match:
            continue
        try:
            values, _ = decoder.raw_decode(script.get_text(), match.end())
        except ValueError:
            continue
        if isinstance(values, list) and len(values) == 2 and values[0] == 1 and isinstance(values[1], str):
            chunks.append(values[1])
    data = "".join(chunks)
    marker = re.search(r'"blogsItems"\s*:\s*', data)
    if not marker:
        raise CollectionError("expected Zhipu research data was absent")
    try:
        entries, _ = decoder.raw_decode(data, marker.end())
    except ValueError as exc:
        raise CollectionError("Zhipu research data could not be parsed") from exc
    if not isinstance(entries, list) or not entries:
        raise CollectionError("Zhipu research list was not recognized")
    rows = []
    for item in entries:
        if isinstance(item, dict) and isinstance(item.get("id"), int) and item.get("title_zh"):
            target = urljoin(url.rstrip("/") + "/", str(item["id"]))
            if article_url(source, target):
                rows.append(Candidate(target, item["title_zh"], as_date(item.get("createAt"))))
    if not rows:
        raise CollectionError("Zhipu research articles did not match the source format")
    return rows


def discover(source, fetcher=fetch):
    candidates = {}
    for url in ([source["feed"]] if "feed" in source else source.get("lists", [])):
        raw, landed, _ = fetcher(url, {urlsplit(url).hostname})
        if "feed" in source:
            current = from_feed(source, raw)
        elif source.get("list_format") == "zhipu-research":
            current = from_zhipu_research(source, raw, landed)
        else:
            current = from_list(source, raw, landed)
        for candidate in current:
            candidates.setdefault(normalized_url(candidate.url), candidate)
    return list(candidates.values())


def read_article(source, url, fetcher=fetch):
    if not article_url(source, url):
        raise CollectionError("URL does not match the configured article paths")
    raw, landed, mime = fetcher(url, {urlsplit(value).hostname for value in source["articles"]})
    if mime not in {"text/html", "application/xhtml+xml"} or not article_url(source, landed):
        raise CollectionError("response is outside the configured article format or paths")
    soup = BeautifulSoup(raw, "html.parser")
    meta = {tag.get("property") or tag.get("name"): tag.get("content") for tag in soup.select("meta[content]")}
    heading = soup.select_one("main h1, article h1, h1")
    body = next((node for selector in source["body"].split(",")
                 if (node := soup.select_one(selector)) is not None), None)
    if body is None or not heading or not body.select_one("p, li, h2, h3, pre"):
        raise CollectionError("expected article heading or body was absent")
    canon = soup.select_one("link[rel=canonical][href]")
    proposed = urljoin(landed, canon["href"]) if canon else landed
    identity = normalized_url(proposed if article_url(source, proposed) else landed)
    time = soup.select_one("article time, main time, time")
    published = as_date(meta.get("article:published_time"))
    if not published and time:
        published = as_date(time.get("datetime") or time.get_text(strip=True))
    lang = soup.html.get("lang", "en") if soup.html else "en"
    return {
        "url": identity, "original_url": url, "title": heading.get_text(" ", strip=True),
        "published": published, "author": meta.get("author"),
        "lang": "zh" if lang.casefold().startswith("zh") else "en",
    }, body, raw, landed


def clean_body(body, page_url, archive_image):
    missing = []
    for comment in body.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for block in body.select("script, style, nav, button, noscript, template, form, [hidden]"):
        if block.parent:
            block.decompose()
    for block in body.select("iframe, video, audio, object, embed, svg, canvas"):
        if block.parent:
            value = block.get("src") or block.get("aria-label") or block.name
            missing.append(f"embedded media: {value}")
            block.replace_with(block.get("aria-label") or "")
    for tag in list(body.find_all(True)):
        attrs = tag.attrs
        tag.attrs = {}
        if tag.name not in BODY_TAGS:
            tag.unwrap()
            continue
        if "id" in attrs and re.fullmatch(r"[\w.:-]+", attrs["id"]):
            tag["id"] = attrs["id"]
        if tag.name == "a" and attrs.get("href"):
            reference = attrs["href"]
            if re.fullmatch(r"#[\w.:-]+", reference):
                tag["href"] = reference
            else:
                href = urljoin(page_url, reference)
                if http_url(href):
                    tag["href"] = href
        if tag.name in {"td", "th"}:
            for name in ("colspan", "rowspan"):
                if str(attrs.get(name, "")).isdigit():
                    tag[name] = attrs[name]
        if tag.name == "img":
            url = urljoin(page_url, attrs.get("data-src") or attrs.get("src") or "")
            try:
                if not url or url == page_url:
                    raise CollectionError("no image address")
                tag["src"] = archive_image(url)
                tag["alt"] = attrs.get("alt", "")
            except CollectionError:
                missing.append(f"image: {url}")
                tag.replace_with(attrs.get("alt") or "")
    return body.decode_contents(), missing


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
