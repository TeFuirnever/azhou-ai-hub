"""Adapt AIHOT JSON inputs to the Source Library's candidate contract."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from collect import Candidate, CollectionError, SOURCES, article_url, as_date, fetch_listing, http_url, normalized_url

INPUT_LIMIT = 8_000_000
CONFIG_LIMIT = 64_000
CONFIG_FIELDS = {"url", "itemsPath", "titlePaths", "urlTemplate", "urlTemplateFallback", "publishedAtPath"}
PROJECTION = Path(__file__).with_name("candidate-input.mjs")


@dataclass(frozen=True)
class CandidateBatch:
    source: str
    received: int
    candidates: list[Candidate]
    skipped: int
    duplicates: int


def input_text(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CollectionError("JSON input must be UTF-8") from exc


def read_text(path, limit=INPUT_LIMIT):
    with Path(path).expanduser().open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise CollectionError("JSON input exceeded the byte limit")
    return input_text(raw)


def project(mode, text, config=None):
    try:
        completed = subprocess.run(
            ["node", str(PROJECTION)], input=json.dumps({"mode": mode, "text": text, "config": config}),
            capture_output=True, encoding="utf-8", timeout=15,
        )
    except OSError as exc:
        raise CollectionError("JSON sources and batch imports require Node.js 22.20 or later") from exc
    except subprocess.TimeoutExpired as exc:
        raise CollectionError("JSON candidate parsing timed out") from exc
    try:
        result = json.loads(completed.stdout)
    except ValueError as exc:
        raise CollectionError("could not run the JSON parser; use Node.js 22.20 or later") from exc
    if completed.returncode:
        raise CollectionError(result.get("error", "JSON candidate parsing failed"))
    return result


def normalize_batch(key, result, base_url=""):
    source = SOURCES[key]
    kept = {}
    duplicates = 0
    for item in result["candidates"]:
        title = " ".join(item["title"].split())
        raw_url = item["url"]
        if not title or any(character.isspace() for character in raw_url):
            continue
        try:
            url = urljoin(base_url, raw_url)
        except ValueError:
            continue
        if not article_url(source, url):
            continue
        try:
            title.encode("utf-8")
            url.encode("utf-8")
        except UnicodeEncodeError:
            continue
        identity = normalized_url(url)
        if identity in kept:
            duplicates += 1
            continue
        date = item.get("publishedAt")
        kept[identity] = Candidate(url, title, as_date(date.strip()) if isinstance(date, str) else None)
    received = result["received"]
    if received and not kept:
        raise CollectionError("no candidates matched the registered source's article URLs and required fields")
    return CandidateBatch(key, received, list(kept.values()), received - len(kept) - duplicates, duplicates)


def import_batch(path):
    result = project("external", read_text(path))
    source = result["sourceId"]
    if source not in SOURCES:
        raise CollectionError("external batch sourceId is not registered")
    return normalize_batch(source, result)


def read_source_config(key, path):
    try:
        config = json.loads(read_text(path, CONFIG_LIMIT))
    except json.JSONDecodeError as exc:
        raise CollectionError("source config is not valid JSON") from exc
    if not isinstance(config, dict) or set(config) - CONFIG_FIELDS:
        raise CollectionError("JSON source config has unsupported fields")
    if any(not isinstance(val, str) for name, val in config.items() if name != "titlePaths"):
        raise CollectionError("JSON source config fields must be strings, except titlePaths")
    titles = config.get("titlePaths")
    if not isinstance(titles, list) or not titles or not all(isinstance(path, str) and path for path in titles):
        raise CollectionError("JSON source config requires a nonempty array of titlePaths")
    if not config.get("urlTemplate"):
        raise CollectionError("JSON source config requires urlTemplate")
    source = SOURCES[key]
    hosts = {urlsplit(url).hostname for url in [source["home"], *source["articles"], *source.get("lists", [])]}
    if "feed" in source:
        hosts.add(urlsplit(source["feed"]).hostname)
    endpoint = config.get("url", "")
    if not http_url(endpoint) or urlsplit(endpoint).hostname not in hosts:
        raise CollectionError("JSON endpoint must use HTTPS on a registered source host")
    return config


def discover_json(key, path, fetcher=None):
    config = read_source_config(key, path)
    endpoint = config["url"]
    raw, landed, mime = (fetcher or fetch_listing)(endpoint, {urlsplit(endpoint).hostname})
    if mime != "application/json" and not mime.endswith("+json"):
        raise CollectionError("JSON source did not return an application/json or +json response")
    result = project("listing", input_text(raw), config)
    return normalize_batch(key, result, landed)
