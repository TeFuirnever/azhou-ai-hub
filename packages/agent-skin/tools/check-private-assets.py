#!/usr/bin/env python3
"""L0 private-asset manifest gate (design doc L0, incident families P3.4/P10.1).

assets/private artwork is intentionally untracked, so a worktree used to learn
about missing build-critical artwork only late inside a build. The expected-file
manifest itself ships in Git at tools/private-assets.MANIFEST.expected (outside
the ignored assets tree, which repository policy keeps free of tracked files),
so every checkout can run this gate per PR: one entry per line ("<path relative
to the package root>" optionally followed by a 64-hex sha256 baseline). A
missing or malformed manifest is always red. Wherever assets/private carries
any artwork, every entry is strictly checked (existence, non-symlink form,
optional sha256 baseline) and any miss is red with a maintainer-worktree copy
hint - a partial or drifted artwork copy fails at layer 0 (P3.4/P10.1). An
artwork-free checkout (the CI shape: no untracked artwork to observe) is green
with an explicit fresh-checkout mode and note instead of a structural red;
copying the artwork in switches the same gate to strict mode. Exit 0 on green,
1 on any red; stdout carries the self-proving JSON report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_RELATIVE = 'tools/private-assets.MANIFEST.expected'
PRIVATE_PREFIX = 'assets/private/'
REPORT_SCHEMA = 'agent-skin-private-assets/v1'
SHA256_PATTERN = re.compile(r'[0-9a-f]{64}')
HINT = ('私有素材不进 Git：请从维护者 worktree 搬运 assets/private 下的素材文件'
        f'（预期清单 {MANIFEST_RELATIVE} 已随仓库提供），再重跑本检查。')
FRESH_CHECKOUT_NOTE = (
    'assets/private carries no artwork: private artwork is untracked by design, so '
    'per-file existence and sha256 checks are not observable in this checkout. Copy '
    'assets/private artwork from the maintainer worktree and this gate switches to '
    'strict mode; a partial copy fails red here.'
)


def parse_manifest(text: str) -> tuple[list[dict], list[str]]:
    """Parse MANIFEST.expected lines into entries; report every bad line.

    The manifest must be self-proving like the journals: a malformed line is a
    problem, never silently skipped. Entries carry the package-relative path
    and the optional sha256 baseline (None when unrecorded).
    """
    entries: list[dict] = []
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        statement = line.split('#', 1)[0].strip()
        if not statement:
            continue
        parts = statement.split()
        if len(parts) > 2:
            problems.append(f'line {number}: expected "<path> [sha256]", got {len(parts)} fields')
            continue
        path = parts[0]
        baseline = parts[1] if len(parts) == 2 else None
        if not path.startswith(PRIVATE_PREFIX) or path == PRIVATE_PREFIX:
            problems.append(f'line {number}: {path} must be a relative path inside assets/private')
            continue
        if Path(path).is_absolute() or '..' in Path(path).parts:
            problems.append(f'line {number}: {path} must not be absolute or escape assets/private')
            continue
        if baseline is not None and SHA256_PATTERN.fullmatch(baseline) is None:
            problems.append(f'line {number}: baseline must be 64 lowercase hex digits, got {baseline}')
            continue
        entries.append({'path': path, 'sha256': baseline})
    seen: set[str] = set()
    for entry in entries:
        if entry['path'] in seen:
            problems.append(f'duplicate manifest entry: {entry["path"]}')
        seen.add(entry['path'])
    return entries, problems


def check_assets(root: Path, entries: list[dict]) -> dict:
    """Existence, non-symlink form and optional sha256 verdict per entry."""
    root = Path(root)
    checks = []
    for entry in entries:
        path = root / entry['path']
        problems = []
        observed = None
        if path.is_symlink():
            problems.append(f'{entry["path"]}: symlink refused; provide the real file')
        elif not path.is_file():
            problems.append(f'{entry["path"]}: missing; {HINT}')
        else:
            with path.open('rb') as stream:
                observed = hashlib.file_digest(stream, 'sha256').hexdigest()
            if entry['sha256'] is not None and observed != entry['sha256']:
                problems.append(f'{entry["path"]}: sha256 mismatch, expected {entry["sha256"]}, '
                                f'observed {observed}; if the artwork was replaced on purpose, '
                                f'record the new baseline in {MANIFEST_RELATIVE}')
        checks.append({'path': entry['path'], 'expected': entry['sha256'],
                       'observed': observed, 'passed': not problems, 'problems': problems})
    return {'kind': 'private-assets', 'schema': REPORT_SCHEMA,
            'manifest': MANIFEST_RELATIVE, 'passed': all(item['passed'] for item in checks),
            'checks': checks}


def artwork_present(root: Path) -> bool:
    """True when assets/private holds any entry at all (the manifest lives in
    tools/ and ships in Git, so anything found here is untracked artwork).

    Fail-closed on an unreadable directory: a directory we cannot list cannot
    prove the artwork absent, so strict checks run and any listed entry that
    cannot be read fails them.
    """
    private = Path(root) / 'assets/private'
    if not private.is_dir():
        return False
    try:
        return any(True for _ in private.iterdir())
    except OSError:
        return True


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    root = Path(root)
    manifest = root / MANIFEST_RELATIVE
    if not manifest.is_file():
        report = {'kind': 'private-assets', 'schema': REPORT_SCHEMA,
                  'manifest': MANIFEST_RELATIVE, 'passed': False,
                  'problems': [f'{MANIFEST_RELATIVE}: missing; {HINT}'], 'checks': []}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    entries, problems = parse_manifest(manifest.read_text(encoding='utf-8'))
    if not problems and not entries:
        problems = [f'{MANIFEST_RELATIVE} lists no assets; it must enumerate the private build inputs']
    strict = artwork_present(root)
    if strict:
        report = check_assets(root, entries)
    else:
        report = {'kind': 'private-assets', 'schema': REPORT_SCHEMA,
                  'manifest': MANIFEST_RELATIVE, 'passed': not problems,
                  'checks': [], 'note': FRESH_CHECKOUT_NOTE}
    report['mode'] = 'strict' if strict else 'fresh-checkout'
    if problems:
        report['passed'] = False
        report['manifestProblems'] = problems
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
