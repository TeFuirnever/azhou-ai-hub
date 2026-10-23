#!/usr/bin/env python3
"""Migrate every canonical package to the super- brand prefix.

Idempotent. Directory renames, cross-references, assets, demos, benchmarks,
description azhou injection (except promotion-frozen super-caveman), and the
check_repository / skill-standard brand-prefix contract.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RENAMES: dict[str, str] = {
    "arch-doc": "super-arch-doc",
    "archify": "super-archify",
    "asd-ste100": "super-asd-ste100",
    "ask-azhou": "super-ask-azhou",
    "autoresearch": "super-autoresearch",
    "azhou-doctor": "super-azhou-doctor",
    "azhou-info": "super-azhou-info",
    "azhou-setup": "super-azhou-setup",
    "azhou-verify": "super-azhou-verify",
    "eli5": "super-eli5",
    "excalidraw-diagram": "super-excalidraw-diagram",
    "session-insights": "super-session-insights",
}

RENAME_ORDER = sorted(RENAMES.items(), key=lambda item: len(item[0]), reverse=True)

SKIP_DIR_NAMES = {
    ".git",
    ".azhou",
    ".treehouse",
    ".zcode",
    ".omx",
    ".hypit",
    ".cursor",
    ".claude",
    "compact-adviser",
    "evidence",
    "productions",
    "node_modules",
    ".venv",
}

SKIP_PATH_PREFIXES = (
    "evidence/",
    "done-archive.md",
    "note-archive.md",
    "CHANGELOG.md",
    "compact-adviser/",
    "benchmarks/super-caveman/results/",
    "docs/research/",
    ".azhou/",
)

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".json",
    ".jsonc",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".sh",
    ".mjs",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".svg",
    ".tsv",
    ".csv",
}


def run_git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def skip_path(relative: str) -> bool:
    if any(part in SKIP_DIR_NAMES for part in relative.split("/")):
        return True
    return any(
        relative == prefix.rstrip("/") or relative.startswith(prefix)
        for prefix in SKIP_PATH_PREFIXES
    )


def rewrite_paths_and_tokens(text: str, *, allow_bare_tokens: bool) -> str:
    for old, new in RENAME_ORDER:
        text = text.replace(f"skills/{old}/", f"skills/{new}/")
        text = text.replace(f"skills/{old}", f"skills/{new}")
        text = text.replace(f"benchmarks/{old}/", f"benchmarks/{new}/")
        text = text.replace(f"docs/demos/{old}.md", f"docs/demos/{new}.md")
        text = text.replace(f"{old}-effect.png", f"{new}-effect.png")
        text = text.replace(f"{old}-evidence-card.png", f"{new}-evidence-card.png")
        text = re.sub(rf"(?m)^(name: ){re.escape(old)}$", rf"\g<1>{new}", text)
        text = re.sub(
            rf"(--skill[= ]){re.escape(old)}(?![\w-])",
            rf"\g<1>{new}",
            text,
        )
        if allow_bare_tokens:
            text = re.sub(
                rf"(?<![\w./-]){re.escape(old)}(?![\w-])",
                new,
                text,
            )
    return text


def ensure_azhou_description(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return text
    frontmatter = match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.M)
    if not name_match:
        return text
    name = name_match.group(1).strip()
    if name == "super-caveman":
        return text
    desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.M)
    if not desc_match:
        return text
    description = desc_match.group(1).rstrip()
    if re.search(r"azhou", description, re.I):
        return text
    injected = f"Azhou skill. {description}"
    new_frontmatter = (
        frontmatter[: desc_match.start(1)] + injected + frontmatter[desc_match.end(1) :]
    )
    return text[: match.start(1)] + new_frontmatter + text[match.end(1) :]


def ensure_rename_trigger(text: str) -> str:
    """Keep a stable 'Renamed from <old>' trigger line in each migrated package."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return text
    frontmatter = match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.M)
    if not name_match:
        return text
    new_name = name_match.group(1).strip()
    old_name = None
    for old, new in RENAMES.items():
        if new == new_name:
            old_name = old
            break
    if not old_name:
        return text
    desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.M)
    if not desc_match:
        return text
    description = desc_match.group(1).rstrip()
    if re.search(rf"(?<![\w-]){re.escape(old_name)}(?![\w-])", description):
        return text
    injected = f"Renamed from {old_name} (the old name still triggers this skill). {description}"
    new_frontmatter = (
        frontmatter[: desc_match.start(1)] + injected + frontmatter[desc_match.end(1) :]
    )
    return text[: match.start(1)] + new_frontmatter + text[match.end(1) :]


def rename_paths() -> None:
    for old, new in sorted(RENAMES.items(), key=lambda item: len(item[0]), reverse=True):
        pairs = [
            (ROOT / "skills" / old, ROOT / "skills" / new, f"skills/{old} -> skills/{new}"),
            (
                ROOT / "assets" / "skills" / f"{old}-effect.png",
                ROOT / "assets" / "skills" / f"{new}-effect.png",
                f"assets/skills/{old}-effect.png -> {new}-effect.png",
            ),
            (
                ROOT / "benchmarks" / old,
                ROOT / "benchmarks" / new,
                f"benchmarks/{old} -> benchmarks/{new}",
            ),
            (
                ROOT / "docs" / "demos" / f"{old}.md",
                ROOT / "docs" / "demos" / f"{new}.md",
                f"docs/demos/{old}.md -> {new}.md",
            ),
        ]
        for src, dst, label in pairs:
            if src.exists() and not dst.exists():
                run_git("mv", str(src), str(dst))
                print(f"renamed {label}")


def iter_text_files():
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        if skip_path(relative):
            continue
        path = ROOT / relative
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            "Makefile",
            "treehouse.toml",
            "CLAUDE.md",
            "AGENTS.md",
            "SUPPORT.md",
            "SECURITY.md",
            "LICENSE",
            "GOVERNANCE.md",
            "CONTRIBUTING.md",
            "THIRD_PARTY_NOTICES.md",
        }:
            continue
        yield path, relative


def update_content() -> int:
    changed = 0
    for path, relative in iter_text_files():
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        is_skill_entry = relative.startswith("skills/") and relative.endswith("/SKILL.md")
        # Skill entry files keep bare old-name triggers; everywhere else rewrite tokens.
        updated = rewrite_paths_and_tokens(original, allow_bare_tokens=not is_skill_entry)
        if is_skill_entry:
            updated = ensure_azhou_description(updated)
            updated = ensure_rename_trigger(updated)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        changed += 1
        print(f"updated {relative}")
    return changed


def patch_contract_surfaces() -> None:
    path = ROOT / "scripts" / "check_repository.py"
    text = path.read_text(encoding="utf-8")

    rename_entries = [
        ("repo-pedant", "super-repo-pedant"),
        ("lavish", "super-lavish"),
        ("llm-wiki", "super-llm-wiki"),
        *sorted(RENAMES.items()),
    ]
    text = re.sub(
        r"RENAMED_AWAY_SKILLS = \{.*?\n\}",
        "RENAMED_AWAY_SKILLS = {\n"
        + "".join(f'    "{old}": "{new}",\n' for old, new in rename_entries)
        + "}",
        text,
        count=1,
        flags=re.DOTALL,
    )

    if "canonical package missing super- brand prefix" not in text:
        old_axis = """        if (package.startswith("super-")) != (declared == "adapted"):
            errors.append(f"fidelity prefix mismatch: {relative} classified {declared}")
"""
        new_axis = """        if not package.startswith("super-"):
            errors.append(f"canonical package missing super- brand prefix: {relative}")
"""
        if old_axis not in text:
            raise SystemExit("fidelity prefix binding not found")
        text = text.replace(old_axis, new_axis, 1)

    text = text.replace(
        """    Skill-standard §2.3: `adapted` skills carry the `super-` prefix;
    `original` and `faithful` skills do not. super-caveman's classification""",
        """    Skill-standard §2.3: every canonical package carries the `super-` brand
    prefix. Fidelity no longer selects the package name. super-caveman's classification""",
        1,
    )
    path.write_text(text, encoding="utf-8")
    print("patched scripts/check_repository.py brand-prefix contract")


def patch_skill_standard() -> None:
    path = ROOT / "docs" / "skill-standard.md"
    text = path.read_text(encoding="utf-8")
    if "每个 canonical package 一律使用 `super-` 品牌前缀" in text:
        print("skill-standard already patched")
        return
    old = """### 2.3 Fidelity 轴与命名规则

fidelity 轴按与上游 skill 的血缘关系把 canonical skill 分为三类，判定标准是**能力是否被改造**，与包装层无关：

| 分类 | 定义 | 命名结果 |
|---|---|---|
| `original` | 无上游 skill 血缘：Azhou 原创、仅借用模式零上游字节、或包装未修改的外部运行时 | 保留原名 |
| `faithful` | 原版能力原样保留；本地新增仅限包装/交互层（身份锚点、收据、provenance、setup、边界、frontmatter 规范化） | 保留原名 |
| `adapted` | 原版能力被换栈/换语言重表达、合并、重写，或被扩展增强（在原流程上新增模式、路由、行为超集） | 加 `super-` 前缀 |

品牌锚点、收据、provenance 记录、setup 文档与授权 checkpoint 本身永远不构成 `adapted`；不改变原版承诺行为的输出形态约束属于包装层。

每个 skill 的分类记录在自己的 provenance 记录中（`references/provenance.md`，无上游血缘的 `original` 同样建档），与已锁定的上游证据并列；分类统一写作 `Classification: \\<值>\\`` 单行，后接引证。super-caveman 因晋升摘要绑定整树，其分类（`adapted`，已正确带前缀）暂由 `check_repository.py` 的 `GATE_HELD_FIDELITY` 声明表持有，随下一次 promotion ride 迁入树内 provenance 记录——与 §2.2 调用类的持表安排同一先例。新 skill 引入时分类是 provenance 合同的必备项；仓库 gate 由 `check_fidelity_axis` 机械强制“前缀 ⟺ 分类”（未声明分类即失败），并由 `check_rename_residue` 拒绝改名旧名出现在兼容触发、迁移源、provenance 与历史记录之外的 surface（#176 M4 / #183）。
"""
    # Read exact current section if escaped form differs
    start = text.find("### 2.3 Fidelity 轴与命名规则")
    end = text.find("## 3. 阿舟交互层")
    if start == -1 or end == -1:
        raise SystemExit("skill-standard §2.3 markers not found")
    class_line = "分类统一写作 `Classification: \\`<值>\\`` 单行，后接引证。"
    new = f"""### 2.3 Fidelity 轴与命名规则

每个 canonical package 一律使用 `super-` 品牌前缀目录与 frontmatter `name`（`skills/super-<canonical>/`）。前缀标识阿舟 canonical 包，不再表示 fidelity。

fidelity 轴按与上游 skill 的血缘关系把 canonical skill 分为三类，判定标准是**能力是否被改造**，与包装层无关；分类只写入 provenance，不决定目录名：

| 分类 | 定义 | 命名结果 |
|---|---|---|
| `original` | 无上游 skill 血缘：Azhou 原创、仅借用模式零上游字节、或包装未修改的外部运行时 | 仍用 `super-` 品牌前缀 |
| `faithful` | 原版能力原样保留；本地新增仅限包装/交互层（身份锚点、收据、provenance、setup、边界、frontmatter 规范化） | 仍用 `super-` 品牌前缀 |
| `adapted` | 原版能力被换栈/换语言重表达、合并、重写，或被扩展增强（在原流程上新增模式、路由、行为超集） | 仍用 `super-` 品牌前缀 |

品牌锚点、收据、provenance 记录、setup 文档与授权 checkpoint 本身永远不构成 `adapted`；不改变原版承诺行为的输出形态约束属于包装层。

每个 skill 的分类记录在自己的 provenance 记录中（`references/provenance.md`，无上游血缘的 `original` 同样建档），与已锁定的上游证据并列；{class_line}super-caveman 因晋升摘要绑定整树，其分类（`adapted`）暂由 `check_repository.py` 的 `GATE_HELD_FIDELITY` 声明表持有，随下一次 promotion ride 迁入树内 provenance 记录——与 §2.2 调用类的持表安排同一先例。新 skill 引入时分类是 provenance 合同的必备项；仓库 gate 由 `check_fidelity_axis` 机械强制每个包必须带 `super-` 品牌前缀且声明 fidelity 分类（缺前缀或未声明分类即失败），并由 `check_rename_residue` 拒绝改名旧名出现在兼容触发、迁移源、provenance 与历史记录之外的 surface（#176 M4 / #183）。

"""
    path.write_text(text[:start] + new + text[end:], encoding="utf-8")
    print("patched docs/skill-standard.md §2.3")


def update_installable_lists() -> None:
    path = ROOT / "scripts" / "check_repository.py"
    text = path.read_text(encoding="utf-8")
    skills = sorted(
        p.parent.name
        for p in (ROOT / "skills").glob("*/SKILL.md")
        if p.is_file() and p.parent.name.startswith("super-")
    )
    installable_names = [name for name in skills if name != "super-llm-wiki"]
    installable = "INSTALLABLE_SKILL_PATHS = {\n" + "".join(
        f'    "skills/{name}/SKILL.md",\n' for name in installable_names
    ) + "}"
    text = re.sub(
        r"INSTALLABLE_SKILL_PATHS = \{.*?\n\}",
        installable,
        text,
        count=1,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"REPOSITORY_EXTENSION_SKILL_PATHS = \{.*?\n\}",
        'REPOSITORY_EXTENSION_SKILL_PATHS = {\n    "skills/super-llm-wiki/SKILL.md",\n}',
        text,
        count=1,
        flags=re.DOTALL,
    )
    path.write_text(text, encoding="utf-8")
    print("refreshed INSTALLABLE_SKILL_PATHS from disk")


def main() -> int:
    patch_skill_standard()
    rename_paths()
    changed = update_content()
    patch_contract_surfaces()
    update_installable_lists()
    changed += update_content()
    print(f"content files rewritten: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
