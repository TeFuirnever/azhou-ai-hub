#!/usr/bin/env python3
"""Dependency-free policy checks for the public repository surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SHA_PIN = re.compile(r"^[0-9a-f]{40}$")
MARKDOWN_LINK = re.compile(
    r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+[\"'][^)]*)?\)"
)
ACTION_USE = re.compile(r"^\s*-\s+uses:\s*(?P<action>[^#\s]+)", re.MULTILINE)
SECRET_PATTERNS = (
    ("aws-access-key", re.compile(rb"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("github-classic-token", re.compile(rb"gh[pousr]_[A-Za-z0-9]{36,255}")),
    ("github-fine-grained-token", re.compile(rb"github_pat_[A-Za-z0-9_]{40,255}")),
    ("google-api-key", re.compile(rb"AIza[0-9A-Za-z_-]{35}")),
    ("private-key", re.compile(rb"-----BEGIN (?:EC |OPENSSH |RSA )?PRIVATE KEY-----")),
)

REQUIRED_PATHS = (
    ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/skill-request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/release.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/dependency-review.yml",
    ".github/workflows/release.yml",
    ".github/workflows/scorecard.yml",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "LICENSE",
    "README.md",
    "README.zh-CN.md",
    "SECURITY.md",
    "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/skill-standard.md",
    "skills/excalidraw-diagram/SKILL.md",
    "skills/repo-pedant/SKILL.md",
)

INSTALLABLE_SKILL_PATHS = {
    "skills/excalidraw-diagram/SKILL.md",
    "skills/repo-pedant/SKILL.md",
}

BASELINE_HASHES = {
    "benchmarks/repo-pedant/upstream/neat-freak/SKILL.snapshot.md": "dfa7ba124e896ae16d8cec21071fbeb10841f2d1b497a46c85c6bed6fc89bbf5",
    "benchmarks/repo-pedant/upstream/neat-freak/references/agent-paths.md": "7e739076a005599463cd77e4b2deff22502c8cb1f97d258bc02c115ceafbe50f",
    "benchmarks/repo-pedant/upstream/neat-freak/references/sync-matrix.md": "0dc219f53695d722e69b82e3c1e5573937c110ec625311f78f1e811c049079eb",
}


def public_files(root: Path = ROOT) -> list[Path]:
    """Return tracked and not-ignored untracked files."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    names = [item for item in result.stdout.decode().split("\0") if item]
    return [root / name for name in sorted(set(names))]


def check_required(root: Path) -> list[str]:
    return [f"required public file missing: {name}" for name in REQUIRED_PATHS if not (root / name).is_file()]


def check_skill_discovery(files: list[Path], root: Path) -> list[str]:
    actual = {path.relative_to(root).as_posix() for path in files if path.name == "SKILL.md"}
    errors = [f"installable skill missing: {path}" for path in sorted(INSTALLABLE_SKILL_PATHS - actual)]
    errors.extend(f"unexpected installable skill: {path}" for path in sorted(actual - INSTALLABLE_SKILL_PATHS))
    return errors


def check_json(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for path in files:
        if path.suffix != ".json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON {path.relative_to(root)}: {exc}")
    return errors


def relative_markdown_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in MARKDOWN_LINK.finditer(text):
        raw = match.group("target").strip("<>")
        parsed = urlsplit(raw)
        if parsed.scheme or raw.startswith("#"):
            continue
        targets.append(unquote(parsed.path))
    return targets


def check_markdown_links(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    root_resolved = root.resolve()
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        try:
            targets = relative_markdown_targets(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read Markdown {path.relative_to(root)}: {exc}")
            continue
        for target in targets:
            if not target:
                continue
            if target.startswith("/"):
                errors.append(f"absolute local link in {path.relative_to(root)}: {target}")
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root_resolved)
            except ValueError:
                errors.append(f"link escapes repository in {path.relative_to(root)}: {target}")
                continue
            if not resolved.exists():
                errors.append(f"broken local link in {path.relative_to(root)}: {target}")
    return errors


def check_action_pins(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    workflow_root = root / ".github" / "workflows"
    for path in files:
        if path.parent != workflow_root or path.suffix not in {".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for match in ACTION_USE.finditer(text):
            action = match.group("action")
            if action.startswith("./"):
                continue
            if action.startswith("docker://"):
                if "@sha256:" not in action:
                    errors.append(f"container action is not digest-pinned in {path.relative_to(root)}: {action}")
                continue
            if "@" not in action or not SHA_PIN.fullmatch(action.rsplit("@", 1)[1]):
                errors.append(f"action is not commit-SHA pinned in {path.relative_to(root)}: {action}")
    return errors


def check_public_boundaries(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        lowered = rel.lower()
        if lowered.endswith("agents/openai.yaml"):
            errors.append(f"vendor-specific package metadata is forbidden: {rel}")
        if "/history/raw/" in f"/{lowered}" or "/history/local/" in f"/{lowered}":
            errors.append(f"private history surface is public: {rel}")
        try:
            size = path.stat().st_size
        except OSError as exc:
            errors.append(f"cannot stat {rel}: {exc}")
            continue
        if size >= 100_000_000:
            errors.append(f"file exceeds GitHub's 100 MB limit: {rel} ({size} bytes)")
    return errors


def check_secret_patterns(files: list[Path], root: Path) -> list[str]:
    """Reject high-confidence credential shapes without printing their values."""
    errors: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"cannot scan {rel}: {exc}")
            continue
        if b"\0" in data[:8192]:
            continue
        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(data):
                line = data.count(b"\n", 0, match.start()) + 1
                errors.append(f"secret-like value ({label}) in {rel}:{line}")
    return errors


def check_provenance(root: Path) -> list[str]:
    errors: list[str] = []
    for rel, expected in BASELINE_HASHES.items():
        path = root / rel
        if not path.is_file():
            errors.append(f"neat-freak provenance snapshot missing: {rel}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"neat-freak provenance snapshot changed: {rel}")

    bundle = root / "skills/excalidraw-diagram/references/vendor/excalidraw-all.esm.js"
    if bundle.is_file() and b"Bundled license information" not in bundle.read_bytes():
        errors.append("vendored Excalidraw bundle lost its bundled-license block")
    return errors


def run_checks(root: Path = ROOT) -> list[str]:
    files = public_files(root)
    errors: list[str] = []
    errors.extend(check_required(root))
    errors.extend(check_skill_discovery(files, root))
    errors.extend(check_json(files, root))
    errors.extend(check_markdown_links(files, root))
    errors.extend(check_action_pins(files, root))
    errors.extend(check_public_boundaries(files, root))
    errors.extend(check_secret_patterns(files, root))
    errors.extend(check_provenance(root))
    return errors


def main() -> int:
    errors = run_checks()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"repository policy failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"repository policy passed: {len(public_files())} public files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
