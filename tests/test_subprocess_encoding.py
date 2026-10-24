"""Anti-regression guard for issue #287: text-mode subprocess calls pin utf-8.

``subprocess.run/check_output/Popen/check_call`` called with ``text=True`` but
without an explicit ``encoding`` decodes child output with the host locale, so
the same test or script corrupts output (or raises ``UnicodeDecodeError``) on
hosts whose default encoding is not UTF-8, e.g. Windows cp936/cp1252.

对应 issue #287:所有仓库自有 Python 面禁止回潮 —— 任何 ``text=True`` 调用
必须同时写 ``encoding="utf-8"``。vendored/upstream 面不在本测试范围内。
(super-caveman 晋级体系退役后,原"钉住面随晋级记录"的延期修整理由不再存在,
全部自有面由本守卫直接覆盖。)
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]

# Repository-owned Python surfaces this guard walks. ``skills/*/scripts`` is
# appended at walk time because each skill is an independent package.
SCAN_ROOTS = ("tests", "benchmarks", "scripts")

# The four subprocess entry points whose text mode requires an explicit codec.
TEXT_MODE_CALLS = {"run", "check_output", "Popen", "check_call"}


class SubprocessEncodingTest(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def _iter_scan_files() -> list[Path]:
        bases = [ROOT / name for name in SCAN_ROOTS]
        bases.extend(ROOT.glob("skills/*/scripts"))
        files: list[Path] = []
        for base in bases:
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.py")):
                directories = path.relative_to(ROOT).parts[:-1]
                if any(segment.startswith(".") for segment in directories):
                    continue  # dot-prefixed directory segment (e.g. .venv, .mimocode)
                if "node_modules" in directories or "upstream" in directories:
                    continue  # vendored / upstream trees
                files.append(path)
        return files

    @staticmethod
    def _iter_text_mode_calls(tree: ast.Module):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr in TEXT_MODE_CALLS
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            ):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            text_value = keywords.get("text")
            if isinstance(text_value, ast.Constant) and text_value.value is True:
                yield node, func.attr, keywords

    def test_text_mode_subprocess_calls_pin_utf8_encoding(self) -> None:
        violations: list[str] = []
        checked = 0
        for path in self._iter_scan_files():
            relative = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node, call_name, keywords in self._iter_text_mode_calls(tree):
                checked += 1
                encoding = keywords.get("encoding")
                if isinstance(encoding, ast.Constant) and encoding.value == "utf-8":
                    continue
                found = ast.unparse(encoding) if encoding is not None else "no encoding"
                violations.append(
                    f'{relative}:{node.lineno}: subprocess.{call_name}(text=True) must pass '
                    f'encoding="utf-8" explicitly (found: {found})'
                )
        # The walker must actually reach calls; an empty scan would pass vacuously.
        self.assertGreater(checked, 0)
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
