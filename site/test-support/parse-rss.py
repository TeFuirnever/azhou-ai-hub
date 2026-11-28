"""Strictly parse built RSS with the Python standard library, returning JSON."""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET


def one(parent: ET.Element, name: str) -> ET.Element:
    elements = parent.findall(name)
    if len(elements) != 1:
        raise ValueError(f"expected one {name}, got {len(elements)}")
    return elements[0]


def parse(xml: str) -> dict:
    if "<!DOCTYPE" in xml.upper():
        raise ValueError("RSS must not declare a DTD")
    root = ET.fromstring(xml)
    if root.tag != "rss" or root.get("version") != "2.0":
        raise ValueError("expected RSS 2.0")
    channel = one(root, "channel")
    self_link = one(channel, "{http://www.w3.org/2005/Atom}link")
    if self_link.get("rel") != "self" or self_link.get("type") != "application/rss+xml":
        raise ValueError("expected an RSS self-discovery link")
    return {
        "title": one(channel, "title").text or "",
        "link": one(channel, "link").text or "",
        "description": one(channel, "description").text or "",
        "self": self_link.get("href"),
        "items": [{
            **{name: one(item, name).text or "" for name in
               ("title", "link", "guid", "pubDate", "category", "description")},
            "isPermaLink": one(item, "guid").get("isPermaLink"),
        } for item in channel.findall("item")],
    }


def main() -> None:
    records = json.load(sys.stdin)
    parsed = []
    for record in records:
        try:
            parsed.append(parse(record["xml"]))
        except (ET.ParseError, ValueError) as error:
            raise ValueError(f"invalid RSS at {record['url']}: {error}") from error
    json.dump(parsed, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
