#!/usr/bin/env python3
"""Permanent reverse-scan gate for the retired surfaces of spec #442.

The decommission cut retired three objects by physical deletion:
``packages/agent-orchestration-kit/`` (the model router), the legacy
``packages/codex-startup-animation/`` source root, and agent-skin's ZCode
host layer (decision record HUB-RET-001). A clean cut is checked, not
asserted: this gate fails deterministically when a live reference to any
of the three objects re-enters the public repository surface, so a
resurrection cannot ride in silently with an unrelated change.

Exactly two exemption classes exist (ticket #448, spec #442 hard bar):

1. Frozen identifiers — installed-state/protocol identity strings that
   installed Codex/DSH 0.9.0 migrations depend on keep their historical
   names, together with the one-line provenance comments at those sites.
   They are masked before the token search, so the same words anywhere
   else still fail.
2. Historical original text — evidence receipts, CHANGELOG history and
   the dated record trees (decisions, design, research, specs) are
   immutable records, and the retirement narrative published with the cut
   (README exit statement, historical provenance/support/notices rows) is
   frozen text. Record trees are exempt by prefix; frozen narrative
   fragments are exempt as exact path-scoped literals, so editing the
   wording forces a conscious exemption update instead of silent drift.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

# Retired object 1 (deleted with ticket #445) and retired object 2 (deleted
# with ticket #446). Any tracked or not-ignored untracked file under these
# roots is a resurrection regardless of its content.
RETIRED_PACKAGE_ROOTS = (
    "packages/agent-orchestration-kit/",
    "packages/codex-startup-animation/",
)

# Retired object 3: agent-skin's ZCode host layer, deleted with ticket #444.
# The shared core and the Codex/DSH hosts survive; only these host-layer
# files must never come back.
RETIRED_AGENT_SKIN_ZCODE_FILES = (
    "packages/agent-skin/Native/ZCodeSkinDriver.swift",
    "packages/agent-skin/Native/ZCodeSkinRuntime.swift",
    "packages/agent-skin/Native/ZCodeSkinDriverTests.swift",
    "packages/agent-skin/Native/ZCodeTransportTests.swift",
    "packages/agent-skin/extension/hosts/zcode.mjs",
    "packages/agent-skin/tools/test-zcode-native.py",
    "packages/agent-skin/tools/test-zcode-runtime.py",
    "packages/agent-skin/tools/test-zcode-transport.py",
    "packages/agent-skin/tools/zcode-adapter.unit.test.mjs",
    "packages/agent-skin/tools/native-zcode-expressions.unit.test.mjs",
    "packages/agent-skin/docs/offline-acceptance-runbook.md",
)

# Live-reference tokens for the three retired objects. Kept precise on
# purpose: the bare word "zcode" stays out because the zcode *harness*
# (skills under ZCode, pstack targets, session-store adapters) is a living,
# publicly declared surface unrelated to agent-skin's retired host layer,
# and the frozen identifier strings below are masked before this search.
RETIRED_REFERENCE_TOKENS = (
    # agent-orchestration-kit: package name, deleted adapter script stem,
    # and the deleted Kit-shared coexistence verdict seam (#445).
    ("agent-orchestration-kit", re.compile(r"(?<![\w-])agent-orchestration-kit(?![\w-])")),
    ("integration_model_router", re.compile(r"(?<![\w/])integration_model_router(?!\w)")),
    ("pstack_coexistence", re.compile(r"(?<!\w)pstack_coexistence(?!\w)")),
    # codex-startup-animation: the legacy source root's name (#446). Path
    # mentions ("packages/codex-startup-animation/") match on purpose.
    ("codex-startup-animation", re.compile(r"(?<![\w-])codex-startup-animation(?![\w-])")),
    # agent-skin ZCode host surface: driver/runtime/transport symbols, the
    # page-adapter path, the controller owner id, and the deleted test and
    # runbook stems (#444).
    ("ZCodeSkin", re.compile(r"ZCodeSkin")),
    ("ZCodeRuntime", re.compile(r"ZCodeRuntime")),
    ("ZCodeTransport", re.compile(r"ZCodeTransport")),
    ("hosts/zcode.mjs", re.compile(r"hosts/zcode\.mjs")),
    ("azhou-zcode-startup", re.compile(r"(?<![\w-])azhou-zcode-startup(?![\w-])")),
    ("zcode-adapter", re.compile(r"(?<![\w-])zcode-adapter")),
    ("test-zcode-", re.compile(r"(?<![\w-])test-zcode-")),
    ("native-zcode-", re.compile(r"(?<![\w-])native-zcode-")),
    ("offline-acceptance-runbook", re.compile(r"(?<![\w-])offline-acceptance-runbook")),
    # agent-orchestration-kit prose names: the product name in either
    # spelling and the hyphenated router/routing nouns. The spaced phrase
    # "model router" stays out on purpose: it is ordinary English for any
    # model-facing router (super-ask-azhou describes the text "a model
    # router sees"), not the retired package.
    ("Orchestration Kit", re.compile(r"Orchestrat(?:or|ion)\s+Kit(?![\w-])")),
    ("model-router", re.compile(r"(?<![\w-])model-rout(?:er|ing)(?![\w-])", re.IGNORECASE)),
)

# Markdown-only live-reference tokens. The bare product noun "Kit" is
# precise in prose (docs called the retired package "the Kit") but collides
# with vendored code and minified bundles, so it is matched only in Markdown.
# "Cursor Team Kit" is a living pstack upstream component and stays allowed;
# compounds such as "Kit-owned" or "cursor-team-kit" do not match.
MARKDOWN_ONLY_REFERENCE_TOKENS = (
    ("Kit", re.compile(r"(?<![\w-])(?<!Team )Kit(?![\w-])")),
)

# Exemption class 1 — frozen identifiers. Installed Codex/DSH 0.9.0 state
# migrates onto these exact historical strings (naming freeze, HUB-RET-001
# decision 2), so they are masked in every scanned file: the owner/project
# id, the Pet receipt owner id, and the two immutable source-origin
# pointers recorded by the package provenance.
FROZEN_IDENTITY_STRINGS = (
    "azhou.codex-startup-animation",
    "codex-startup-animation/native-pet-v1",
    "panding999/codex-startup-animation",
    "TeFuirnever/codex-startup-animation",
)

# Exemption class 1 (site comments) — the one-line "inherited from"
# provenance notes the freeze contract mandates at each frozen-identifier
# site. Path-scoped: the same words in any other file still fail.
FROZEN_SITE_FRAGMENTS = {
    "packages/agent-skin/Native/InstallRegistryCore.swift": (
        "inherited from codex-startup-animation",
    ),
    "packages/agent-skin/Native/Wallpaper.swift": (
        "inherited from codex-startup-animation",
    ),
    "packages/agent-skin/extension/renderer.mjs": (
        "inherited from codex-startup-animation",
    ),
    "packages/agent-skin/tools/install-macos.py": (
        "inherited from codex-startup-animation",
    ),
    "packages/agent-skin/tools/verify-artifacts.py": (
        "inherited from codex-startup-animation",
    ),
}

# Exemption class 2 — historical original text, exempt by prefix. Evidence
# receipts (root and package-local) and CHANGELOG history are immutable
# records; the dated decisions/design/research/specs trees are superseded
# records kept as history (same boundary the rename-residue check draws).
HISTORY_PATH_PREFIXES = (
    "evidence/",
    "packages/agent-skin/evidence/",
    "docs/decisions/",
    "docs/design/",
    "docs/research/",
    "docs/specs/",
)
HISTORY_FILES = (
    "CHANGELOG.md",
)

# Exemption class 2 (frozen narrative) — the retirement statements
# published with the cut in otherwise-live documents: the README exit
# statement and Pet-ownership notes (#447), the historical provenance,
# support, integrations and architecture rows, and the package's own
# provenance/migration records. Exact path-scoped literals: any other
# occurrence of a retired name in these same files still fails, and
# rewording a frozen statement turns the gate red until the exemption is
# consciously updated.
FROZEN_NARRATIVE_FRAGMENTS = {
    "README.md": (
        "Legacy `codex-startup-animation` package",
        "the legacy `codex-startup-animation` source",
        "**Agent Orchestration Kit (model router)**",
        "the model-router Hub entry",
        "the Kit's own uninstaller",
    ),
    "README.zh-CN.md": (
        "旧 `codex-startup-animation` 包",
        "旧 `codex-startup-animation` 源目录",
        "**Agent Orchestration Kit（model router）**",
        "model-router Hub 入口",
        "装过 model-router 的用户",
    ),
    "GLOSSARY.md": (
        "ZCode/Kit/旧包痕迹",
    ),
    "THIRD_PARTY_NOTICES.md": (
        "Agent Orchestration Kit (retired; historical row)",
    ),
    "docs/architecture.md": (
        "The legacy `codex-startup-animation` source",
    ),
    "docs/integration-provenance.md": (
        "`packages/codex-startup-animation/`",
        "Agent Orchestration Kit, a local continuation of",
        "The Agent Orchestration Kit model-router entry is retired",
        "Agent Orchestration Kit selected code/profile (retired)",
    ),
    "docs/integrations.md": (
        "`packages/codex-startup-animation/`",
    ),
    "docs/support-matrix.md": (
        "then-canonical `codex-startup-animation` source root",
        "since-deleted `codex-startup-animation` root",
        "the since-retired Agent Orchestration Kit",
        "Agent Orchestration Kit `azhou-balanced` (retired 2026-11-12",
        "its `model-router` Hub entry",
        "the Kit's own path",
        "the retired Agent Orchestration Kit (",
    ),
    "packages/agent-skin/README.md": (
        "`packages/codex-startup-animation/`",
    ),
    "packages/agent-skin/UPSTREAM.md": (
        "`packages/codex-startup-animation/`",
    ),
    "packages/agent-skin/MIGRATION-INVENTORY.md": (
        "`packages/codex-startup-animation/`",
    ),
}

# Gate self-reference: these files hold the retired-identifier definitions,
# allowlists and test fixtures themselves, so they must be able to spell the
# identifiers (same exemption the legacy-broadcast check grants its own
# definition file).
GATE_DEFINITION_PATHS = (
    "scripts/check_repository.py",
    "scripts/check_retired_surfaces.py",
    "tests/test_check_repository.py",
    "tests/test_check_retired_surfaces.py",
)


def _public_files(root: Path = ROOT) -> list[Path]:
    """Return tracked and not-ignored untracked files (check_repository parity)."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    names = [item for item in result.stdout.decode().split("\0") if item]
    paths = [root / name for name in sorted(set(names))]
    return [path for path in paths if path.exists() or path.is_symlink()]


def _exempt(relative: str) -> bool:
    return (
        relative in HISTORY_FILES
        or relative in GATE_DEFINITION_PATHS
        or relative.startswith(HISTORY_PATH_PREFIXES)
    )


def check_retired_surface_references(files: list[Path], root: Path) -> list[str]:
    """Fail on any live reference to the three retired objects of spec #442."""
    errors: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if relative.startswith(RETIRED_PACKAGE_ROOTS) or relative in RETIRED_AGENT_SKIN_ZCODE_FILES:
            errors.append(f"retired surface resurrected: {relative}")
            continue
        if _exempt(relative):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        masks = (
            FROZEN_IDENTITY_STRINGS
            + FROZEN_SITE_FRAGMENTS.get(relative, ())
            + FROZEN_NARRATIVE_FRAGMENTS.get(relative, ())
        )
        tokens = RETIRED_REFERENCE_TOKENS
        if relative.endswith(".md"):
            tokens = tokens + MARKDOWN_ONLY_REFERENCE_TOKENS
        for line_number, line in enumerate(text.splitlines(), 1):
            masked = line
            for literal in masks:
                masked = masked.replace(literal, "")
            for label, pattern in tokens:
                if pattern.search(masked):
                    errors.append(
                        f"retired-surface reference: {relative}:{line_number}: {label}"
                    )
    return errors


def run_checks(root: Path = ROOT) -> list[str]:
    return check_retired_surface_references(_public_files(root), root)


def main() -> int:
    errors = run_checks()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"retired-surface reverse scan failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"retired-surface reverse scan passed: {len(_public_files())} public files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
