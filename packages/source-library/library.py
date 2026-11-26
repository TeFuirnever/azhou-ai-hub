"""Maintenance commands for Azhou Source Library."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from catalog import Catalog
from collect import Candidate, CollectionError, SOURCES, discover, fetch, read_article
from ingest import discover_json, import_batch

STATUS_LABELS = {"updated": "有更新", "no_updates": "无更新", "failed": "抓取失败"}


def private_path(path):
    directory = path.expanduser().resolve()
    if any((parent / ".git").exists() for parent in (directory, *directory.parents)):
        raise CollectionError("private archive and backup directories must be outside Git checkouts")
    return directory


def preview(source, url=None, fetcher=None, *, json_config=None):
    if json_config is not None:
        return discover_json(source, json_config, fetcher).candidates
    if url:
        article, _, _, _ = read_article(SOURCES[source], url, fetcher or fetch)
        return [Candidate(article["url"], article["title"], article["published"])]
    if not any(key in SOURCES[source] for key in ("feed", "lists")):
        raise CollectionError("this source is checked by article link; supply --url")
    return discover(SOURCES[source]) if fetcher is None else discover(SOURCES[source], fetcher)


def sync(catalog, sources, url=None, fetcher=None, *, json_config=None):
    results = {}
    for source in sources:
        try:
            candidates = preview(source, url, fetcher, json_config=json_config)
        except CollectionError as exc:
            catalog.record_failure(source, str(exc))
            results[source] = {"status": "failed", "label": STATUS_LABELS["failed"], "reason": str(exc)}
        else:
            added = catalog.record_discovery(source, candidates)
            status = "updated" if added else "no_updates"
            results[source] = {"status": status, "label": STATUS_LABELS[status], "found": len(candidates), "added": added}
    return results


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="private archive data directory")
    sub = parser.add_subparsers(dest="action", required=True)
    commands = sub.add_parser("preview", help="try the source parser without opening the private catalog")
    commands.add_argument("source", choices=SOURCES)
    preview_input = commands.add_mutually_exclusive_group()
    preview_input.add_argument("--url")
    preview_input.add_argument("--json-config", type=Path, help="read one registered source's JSON listing")
    commands = sub.add_parser("sync", help="discover candidates and update the source status")
    commands.add_argument("source", choices=[*SOURCES, "all"])
    sync_input = commands.add_mutually_exclusive_group()
    sync_input.add_argument("--url")
    sync_input.add_argument("--json-config", type=Path, help="read one registered source's JSON listing")
    commands = sub.add_parser("import-json", help="register candidates from an AIHOT-format batch file")
    commands.add_argument("file", type=Path)
    commands.add_argument("--dry-run", action="store_true", help="validate the batch and display a preview")
    sub.add_parser("status", help="show the latest formal collection results")
    sub.add_parser("list", help="show candidates, publication approvals and completeness")
    commands = sub.add_parser("inspect", help="view private article metadata, retained body and revision")
    commands.add_argument("id")
    commands.add_argument("--revision")
    commands = sub.add_parser("archive", help="retain a selected publisher article in the private catalog")
    commands.add_argument("source", choices=SOURCES)
    commands.add_argument("url")
    archive_input = commands.add_mutually_exclusive_group(required=True)
    archive_input.add_argument("--saved-html", type=Path, help="import previously saved HTML")
    archive_input.add_argument("--fetch-original", action="store_true", help="fetch this official article once")
    commands.add_argument("--include-images", action="store_true", help="also retain allowed images when the basis covers them")
    commands.add_argument("--basis", required=True)
    commands = sub.add_parser("review", help="approve exactly the fields and revision eligible for release")
    commands.add_argument("id")
    commands.add_argument("scope", choices=["link", "full"])
    commands.add_argument("--basis", required=True)
    commands.add_argument("--note", required=True)
    commands.add_argument("--revision")
    commands.add_argument("--kind", choices=["article", "announcement", "research"], default="article")
    commands = sub.add_parser("withdraw")
    commands.add_argument("id")
    commands = sub.add_parser("export", help="write an approved-only bundle for editorial review")
    commands.add_argument("target", type=Path)
    commands = sub.add_parser("backup", help="verify and copy the private database and referenced objects")
    commands.add_argument("target", type=Path)
    args = parser.parse_args()
    read_only = args.action == "preview" or (args.action == "import-json" and args.dry_run)
    if not read_only and args.data is None:
        parser.error("--data is required for maintenance commands")
    if args.action == "sync" and args.source == "all" and args.url:
        parser.error("use --url with a single source")
    if args.action == "sync" and args.source == "all" and args.json_config is not None:
        parser.error("use --json-config with a single source")
    if args.action == "archive" and args.include_images and not args.fetch_original:
        parser.error("--include-images requires --fetch-original")
    return args


def run_import(args):
    batch = import_batch(args.file)
    outcome = {
        "source": batch.source,
        "received": batch.received,
        "eligible": len(batch.candidates),
        "skipped": batch.skipped,
        "duplicates": batch.duplicates,
    }
    if args.dry_run:
        return {**outcome, "preview": [asdict(item) for item in batch.candidates[:20]]}
    with Catalog(private_path(args.data)) as store:
        added = store.record_discovery(batch.source, batch.candidates, update_source_status=False)
    return {**outcome, "added": added, "already_known": len(batch.candidates) - added}


def run(args):
    if args.action == "preview":
        rows = preview(args.source, args.url, json_config=getattr(args, "json_config", None))
        return {"found": len(rows), "preview": [asdict(row) for row in rows[:20]]}
    if args.action == "import-json":
        return run_import(args)
    with Catalog(private_path(args.data)) as store:
        if args.action == "status":
            return [dict(row, label=STATUS_LABELS[row["status"]]) for row in store.runs()]
        if args.action == "list":
            return store.entries()
        if args.action == "inspect":
            return store.inspect(args.id, args.revision)
        if args.action == "sync":
            sources = [choice for choice in SOURCES if choice != "mimo"] if args.source == "all" else [args.source]
            return sync(store, sources, args.url, json_config=args.json_config)
        if args.action == "archive":
            if args.saved_html is None:
                return store.archive(args.source, args.url, args.basis, fetch, keep_images=args.include_images)

            def saved_page(url, _hosts, limit=8_000_000):
                with args.saved_html.expanduser().open("rb") as source:
                    raw = source.read(limit + 1)
                if len(raw) > limit:
                    raise CollectionError("saved page exceeded the byte limit")
                return raw, url, "text/html"

            return store.archive(args.source, args.url, args.basis, saved_page, keep_images=False)
        if args.action == "review":
            store.approve(args.id, args.scope, args.basis, args.note, args.revision, args.kind)
            return {"approved": args.id, "scope": args.scope}
        if args.action == "withdraw":
            store.withdraw(args.id)
            return {"withdrawn": args.id}
        if args.action == "backup":
            store.backup(private_path(args.target))
            return {"backup": str(args.target)}
        return {"exported": store.export(args.target), "path": str(args.target)}


if __name__ == "__main__":
    try:
        args = parse_args()
        result = run(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.action == "sync" and any(row["status"] == "failed" for row in result.values()):
            raise SystemExit(1)
    except (CollectionError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
