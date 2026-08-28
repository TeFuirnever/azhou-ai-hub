#!/usr/bin/env python3
"""Dependency-free policy checks for the public repository surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
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
RUNTIME_DEFAULT_PATTERN = re.compile(
    r"\b(?:DEFAULT_[A-Z0-9_]*(?:STORE|STATE|ROOT|DIR|PATH)|default)\s*=\s*"
    r"[\"'](?P<path>\.[^\"']+)[\"']"
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
    "assets/skills/llm-wiki-effect.png",
    "assets/skills/super-caveman-effect.png",
    "SECURITY.md",
    "SUPPORT.md",
    "THIRD_PARTY_NOTICES.md",
    "treehouse.toml",
    "docs/worktree-policy.md",
    "docs/skill-standard.md",
    "docs/foundations.md",
    "scripts/azhou_hub.py",
    "skills/super-caveman/SKILL.md",
    "skills/excalidraw-diagram/SKILL.md",
    "skills/llm-wiki/SKILL.md",
    "skills/repo-pedant/SKILL.md",
)

INSTALLABLE_SKILL_PATHS = {
    "skills/super-caveman/SKILL.md",
    "skills/excalidraw-diagram/SKILL.md",
    "skills/azhou-doctor/SKILL.md",
    "skills/azhou-info/SKILL.md",
    "skills/azhou-setup/SKILL.md",
    "skills/azhou-verify/SKILL.md",
    "skills/repo-pedant/SKILL.md",
}
REPOSITORY_EXTENSION_SKILL_PATHS = {
    "skills/llm-wiki/SKILL.md",
}

SKILL_BRAND_CONTRACTS = {
    "skills/azhou-doctor/SKILL.md": {
        "display_name": "Azhou Doctor",
        "motto": "先诊断，不越权修复。",
        "startup": "🦊 阿舟 · Azhou Doctor 启动｜mode=doctor｜scope=<checkout>",
    },
    "skills/azhou-info/SKILL.md": {
        "display_name": "Azhou Info",
        "motto": "只报告仓库能证明的事实。",
        "startup": "🦊 阿舟 · Azhou Info 启动｜mode=<info|version>｜scope=<checkout>",
    },
    "skills/azhou-setup/SKILL.md": {
        "display_name": "Azhou Setup",
        "motto": "先看计划，再按同一计划执行。",
        "startup": "🦊 阿舟 · Azhou Setup 启动｜mode=<setup|repair|migrate|uninstall>｜scope=<checkout>",
    },
    "skills/azhou-verify/SKILL.md": {
        "display_name": "Azhou Verify",
        "motto": "完整 gate 跑完，结论才成立。",
        "startup": "🦊 阿舟 · Azhou Verify 启动｜mode=verify｜scope=<checkout>",
    },
    "skills/excalidraw-diagram/SKILL.md": {
        "display_name": "Excalidraw Diagram",
        "motto": "先让结构讲清关系，再让文字补充证据。",
        "startup": "🦊 阿舟 · Excalidraw Diagram 启动｜mode=<create|edit|render|export>｜deliverable=<format>｜scope=<diagram>",
        "brand_path": "skills/excalidraw-diagram/references/brand-layer.md",
    },
    "skills/llm-wiki/SKILL.md": {
        "display_name": "LLM Wiki",
        "motto": "知识要留得住，也要经得起查证。",
        "startup": "🦊 阿舟 · LLM Wiki 启动｜operation=<operation>｜scope=<project-root>",
        "brand_path": "skills/llm-wiki/references/brand-layer.md",
    },
    "skills/repo-pedant/SKILL.md": {
        "display_name": "Repo Pedant",
        "motto": "代码是唯一现役答案，其他都要对齐。",
        "startup": "🦊 阿舟 · Repo Pedant 启动｜mode=<mode>｜scope=<repo>",
        "brand_path": "skills/repo-pedant/references/brand-layer.md",
    },
    "skills/super-caveman/SKILL.md": {
        "display_name": "Super Caveman",
        "motto": "少说话，技术信号不丢。",
        "startup": "🦊 阿舟 · Super Caveman 启动｜mode=<operation>｜scope=<target>",
        "brand_path": "skills/super-caveman/references/brand-layer.md",
    },
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
    paths = [root / name for name in sorted(set(names))]
    return [path for path in paths if path.exists() or path.is_symlink()]


def check_required(root: Path) -> list[str]:
    return [f"required public file missing: {name}" for name in REQUIRED_PATHS if not (root / name).is_file()]


def check_treehouse_config(root: Path) -> list[str]:
    path = root / "treehouse.toml"
    if not path.is_file():
        return []
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        return [f"treehouse config is invalid TOML: {exc}"]

    errors: list[str] = []
    max_trees = config.get("max_trees")
    if isinstance(max_trees, bool) or not isinstance(max_trees, int) or not 1 <= max_trees <= 4:
        errors.append("treehouse max_trees must be an integer from 1 through 4")
    if config.get("vcs") != "git":
        errors.append("treehouse vcs must be git")
    if "hooks" in config:
        errors.append("treehouse repo config must not define hooks; use reviewed user-level hooks")
    if config.get("root") not in (None, ""):
        errors.append("treehouse repo config must not pin a machine-specific pool root")
    return errors


def check_skill_discovery(files: list[Path], root: Path) -> list[str]:
    actual = {path.relative_to(root).as_posix() for path in files if path.name == "SKILL.md"}
    repository_extensions = {
        path for path in REPOSITORY_EXTENSION_SKILL_PATHS if (root / path).is_file()
    }
    expected = INSTALLABLE_SKILL_PATHS | repository_extensions
    errors = [f"installable skill missing: {path}" for path in sorted(expected - actual)]
    errors.extend(f"unexpected installable skill: {path}" for path in sorted(actual - expected))
    return errors


def check_skill_brand_contract(root: Path) -> list[str]:
    """Enforce the shared display identity without homogenizing domain stages."""
    expected = INSTALLABLE_SKILL_PATHS | REPOSITORY_EXTENSION_SKILL_PATHS
    contracted = set(SKILL_BRAND_CONTRACTS)
    errors = [f"skill brand contract missing: {path}" for path in sorted(expected - contracted)]
    errors.extend(f"unexpected skill brand contract: {path}" for path in sorted(contracted - expected))

    for relative, contract in sorted(SKILL_BRAND_CONTRACTS.items()):
        skill_path = root / relative
        if not skill_path.is_file():
            continue
        try:
            skill = skill_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read skill brand surface {relative}: {exc}")
            continue

        combined = skill
        brand_relative = contract.get("brand_path")
        if brand_relative:
            brand_path = root / brand_relative
            if not brand_path.is_file():
                errors.append(f"skill brand layer missing: {brand_relative}")
                continue
            try:
                brand = brand_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"cannot read skill brand layer {brand_relative}: {exc}")
                continue
            combined += "\n" + brand
            if contract["startup"] not in brand:
                errors.append(f"skill brand startup drift: {brand_relative}")

        display_name = contract["display_name"]
        if f"🦊 阿舟 · {display_name}" not in combined:
            errors.append(f"skill brand identity missing: {relative}")
        if contract["motto"] not in combined:
            errors.append(f"skill brand motto missing: {relative}")
        if contract["startup"] not in combined:
            errors.append(f"skill brand startup drift: {relative}")

        for marker, label in (
            ("✅ 验证通过", "success marker"),
            ("❌ 验证失败", "failure marker"),
            ("🔒 阿舟暂停这一项", "hold marker"),
        ):
            if marker not in combined:
                errors.append(f"skill brand {label} missing: {relative}")
        if "Emoji" not in combined:
            errors.append(f"skill brand emoji boundary missing: {relative}")
        if not any(marker in combined for marker in ("原始证据", "raw evidence")):
            errors.append(f"skill brand raw-evidence boundary missing: {relative}")
        if not any(marker in combined for marker in ("host 不支持 Unicode", "Host 不支持 Unicode", "A host without Unicode")):
            errors.append(f"skill brand Unicode fallback missing: {relative}")
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


def check_runtime_state_contract(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    ignore = root / ".gitignore"
    try:
        ignored = ignore.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"cannot read .gitignore for runtime-state policy: {exc}")
    else:
        if ".azhou/" not in ignored:
            errors.append("repository .gitignore must contain .azhou/")

    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix != ".py" or not relative.startswith(("scripts/", "skills/")):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot inspect runtime-state defaults in {relative}: {exc}")
            continue
        for line_number, line in enumerate(lines, 1):
            for match in RUNTIME_DEFAULT_PATTERN.finditer(line):
                value = match.group("path")
                if value == ".azhou" or value.startswith(".azhou/"):
                    continue
                errors.append(
                    "Azhou runtime state must use .azhou/<skill-name>/ or .azhou/hub/: "
                    f"{relative}:{line_number} defaults to {value}"
                )
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
    errors.extend(check_treehouse_config(root))
    errors.extend(check_skill_discovery(files, root))
    errors.extend(check_skill_brand_contract(root))
    errors.extend(check_json(files, root))
    errors.extend(check_markdown_links(files, root))
    errors.extend(check_action_pins(files, root))
    errors.extend(check_public_boundaries(files, root))
    errors.extend(check_runtime_state_contract(files, root))
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
