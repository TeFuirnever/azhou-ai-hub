#!/usr/bin/env python3
"""Generate the ask-azhou routing index from the canonical skills manifest.

The router catalog block inside ``skills/ask-azhou/SKILL.md`` is machine
generated from every ``skills/*/SKILL.md`` frontmatter description - the
same text a model router sees. The upstream hand-written prose map drifted
without any check noticing; this generator plus the generated-index parity
gate in ``scripts/check_repository.py`` close that structurally: adding,
renaming, or re-describing a canonical skill makes the checked-in block
stale and the gate red until the block is regenerated.

Usage from the checkout root:

    python skills/ask-azhou/scripts/generate_routing_index.py            # regenerate
    python skills/ask-azhou/scripts/generate_routing_index.py --check    # verify only

Dependency-free; standard library only. Fails closed on any frontmatter
shape it does not understand.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


BEGIN_MARKER = "<!-- generated-routing-index:begin -->"
END_MARKER = "<!-- generated-routing-index:end -->"
FRONTMATTER_PATTERN = re.compile(r"^---\n(?P<frontmatter>.*?)\n---\n", re.DOTALL)
FRONTMATTER_LINE_PATTERN = re.compile(r"^(?P<key>name|description|invocation):(?P<value>.*)$")
ROUTER_RELATIVE = "skills/ask-azhou/SKILL.md"


class GenerationError(RuntimeError):
    """Raised when the manifest or the router block cannot be trusted."""


def parse_frontmatter(path: Path) -> tuple[str, str]:
    """Return (name, description) from one SKILL.md, failing closed."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GenerationError(f"cannot read {path}: {exc}") from exc
    match = FRONTMATTER_PATTERN.match(text)
    if match is None:
        raise GenerationError(f"frontmatter block missing: {path}")
    name: str | None = None
    description: str | None = None
    for line in match.group("frontmatter").splitlines():
        if not line.strip():
            continue
        pair = FRONTMATTER_LINE_PATTERN.match(line)
        if pair is None:
            raise GenerationError(f"unsupported frontmatter line in {path}: {line.strip()!r}")
        key = pair.group("key")
        value = pair.group("value").strip()
        if not value:
            raise GenerationError(f"empty frontmatter value for {key!r} in {path}")
        if key == "name":
            name = value
        elif key == "description":
            description = value
    if name is None or description is None:
        raise GenerationError(f"frontmatter must declare name and description: {path}")
    return name, description


def catalog_entries(root: Path) -> list[tuple[str, str]]:
    """Return (name, description) for every skills/*/SKILL.md, sorted by name."""
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        raise GenerationError(f"cannot locate the skills directory below {root}; pass --root")
    entries: list[tuple[str, str]] = []
    for package in sorted(skills_dir.iterdir(), key=lambda item: item.name):
        skill = package / "SKILL.md"
        if not package.is_dir() or not skill.is_file():
            continue
        name, description = parse_frontmatter(skill)
        if name != package.name:
            raise GenerationError(
                f"frontmatter name {name!r} does not match the package folder {package.name!r}: {skill}"
            )
        entries.append((name, description))
    if not entries:
        raise GenerationError(f"no canonical SKILL.md packages found below {skills_dir}")
    return entries


def render_block(entries: list[tuple[str, str]]) -> str:
    return "".join(f"- `{name}` — {description}\n" for name, description in entries)


def splice(text: str, block: str, source: Path) -> str:
    """Replace the text between the markers with the rendered block."""
    begin = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if begin == -1 or end == -1:
        raise GenerationError(
            f"generated-index markers missing in {source}; expected {BEGIN_MARKER} ... {END_MARKER}"
        )
    if text.find(BEGIN_MARKER, begin + 1) != -1 or text.find(END_MARKER, end + 1) != -1:
        raise GenerationError(f"duplicated generated-index markers in {source}")
    if end < begin:
        raise GenerationError(f"generated-index markers are out of order in {source}")
    prefix = text[: begin + len(BEGIN_MARKER)]
    suffix = text[end:]
    return f"{prefix}\n{block}{suffix}"


def regenerate(root: Path) -> str:
    """Return the router text with a current generated index block."""
    router = root / ROUTER_RELATIVE
    if not router.is_file():
        raise GenerationError(f"router skill missing: {router}")
    try:
        text = router.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GenerationError(f"cannot read {router}: {exc}") from exc
    return splice(text, render_block(catalog_entries(root)), router)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="checkout root that owns the skills/ directory (default: this script's checkout)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the checked-in block matches the manifest without writing",
    )
    args = parser.parse_args(argv)
    root = args.root.expanduser()
    try:
        current = regenerate(root)
        router = root / ROUTER_RELATIVE
        if args.check:
            try:
                checked = router.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise GenerationError(f"cannot read {router}: {exc}") from exc
            if checked != current:
                print(
                    "routing index is stale; regenerate with "
                    "python skills/ask-azhou/scripts/generate_routing_index.py",
                    file=sys.stderr,
                )
                return 1
            print("routing index is current")
            return 0
        try:
            router.write_text(current, encoding="utf-8")
        except OSError as exc:
            raise GenerationError(f"cannot write {router}: {exc}") from exc
        print(f"routing index regenerated: {router}")
        return 0
    except GenerationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
