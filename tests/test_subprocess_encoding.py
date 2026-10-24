"""Anti-regression guard for issue #287: text-mode subprocess calls pin utf-8.

``subprocess.run/check_output/Popen/check_call`` called with ``text=True`` but
without an explicit ``encoding`` decodes child output with the host locale, so
the same test or script corrupts output (or raises ``UnicodeDecodeError``) on
hosts whose default encoding is not UTF-8, e.g. Windows cp936/cp1252.

对应 issue #287:非保护面禁止回潮 —— 任何 ``text=True`` 调用必须同时写
``encoding="utf-8"``。钉住面(revision-beb0568c 晋级记录的 reviewed_blobs,
测试运行时动态读取,将来晋级记录更新后保护面自动跟随)与 vendored/upstream
面留给晋级流程处理,本测试不保护。
"""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]

# Repository-owned Python surfaces this guard walks. ``skills/*/scripts`` is
# appended at walk time because each skill is an independent package.
SCAN_ROOTS = ("tests", "benchmarks", "scripts")

# The four subprocess entry points whose text mode requires an explicit codec.
TEXT_MODE_CALLS = {"run", "check_output", "Popen", "check_call"}

# Latest super-caveman promotion record. Its reviewed_blobs pin the public
# surface; they are read at test runtime so the protected set follows the
# record instead of a frozen path list.
PROMOTION_RECORD = (
    ROOT / "benchmarks" / "super-caveman" / "results" / "revision-beb0568c-exact-diff-approval.json"
)

# 静态排除表(issue #287 界定结果,逐路径注明理由)。规则含义:
#   规则1 = 路径在 revision-beb0568c reviewed_blobs 钉住面内 —— 改字节即挂
#           promotion check 与 CI,encoding 修整必须随晋级流程一起走
#           (这些路径同时会被运行时读取的钉住面命中,此处显式留底理由);
#   规则2 = super-caveman 晋级体系自有面 —— 门禁裁判本体及其测试,留给晋级流程。
PATH_EXCLUSIONS = {
    # 规则1:在 revision-beb0568c reviewed_blobs 钉住面内(路径精确匹配),改字节即挂 check 与 CI。
    "benchmarks/super-arch-doc/run_case.py":
        "规则1:在 revision-beb0568c reviewed_blobs 钉住面内(路径精确匹配),改字节即挂 check 与 CI。",
    # 规则1+2:钉住面内,且属 super-caveman 晋级体系自有面(门禁裁判本体)。
    "benchmarks/super-caveman/benchmark.py":
        "规则1+2:在 reviewed_blobs 钉住面内,且属 super-caveman 晋级体系自有面(门禁裁判本体)。",
    # 规则1:在 reviewed_blobs 钉住面内。
    "benchmarks/super-excalidraw-diagram/ordinary-model-floor/benchmark.py":
        "规则1:在 reviewed_blobs 钉住面内。",
    "scripts/azhou_hub.py": "规则1:在 reviewed_blobs 钉住面内。",
    "skills/super-excalidraw-diagram/scripts/visual-check.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_azhou_hub.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_azhou_verify_gate_report.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_check_repository.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_eli5_audience_assertion.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_excalidraw_benchmark.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_excalidraw_playwright_runtime.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_excalidraw_sandbox_fallback.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_session_insights_benchmark.py": "规则1:在 reviewed_blobs 钉住面内。",
    "tests/test_verify_final_verdict.py": "规则1:在 reviewed_blobs 钉住面内。",
    # 规则1+2:钉住面内,且文件名含 super_caveman(晋级体系自有测试面)。
    "tests/test_super_caveman_benchmark.py":
        "规则1+2:在 reviewed_blobs 钉住面内,且文件名含 super_caveman(晋级体系自有测试面)。",
    # 规则2:文件名含 super_caveman,晋级体系自有面,虽经核对不在 reviewed_blobs 内仍留给晋级流程。
    "tests/test_super_caveman.py":
        "规则2:文件名含 super_caveman,晋级体系自有面,虽经核对不在 reviewed_blobs 内仍留给晋级流程。",
    # 规则2:文件名含 super_caveman,晋级体系自有面。
    "tests/test_super_caveman_claude_adapter.py": "规则2:文件名含 super_caveman,晋级体系自有面。",
    "tests/test_super_caveman_codex_adapter.py": "规则2:文件名含 super_caveman,晋级体系自有面。",
    "tests/test_super_caveman_codex_adapter_lifecycle.py": "规则2:文件名含 super_caveman,晋级体系自有面。",
    "tests/test_super_caveman_zcode_adapter.py": "规则2:文件名含 super_caveman,晋级体系自有面。",
}


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

    def _pinned_paths(self) -> set[str]:
        self.assertTrue(PROMOTION_RECORD.is_file(), f"missing promotion record: {PROMOTION_RECORD}")
        record = json.loads(PROMOTION_RECORD.read_text(encoding="utf-8"))
        blobs = record["reviewed_blobs"]
        self.assertIsInstance(blobs, list)
        paths = set()
        for blob in blobs:
            self.assertIsInstance(blob, dict, blob)
            self.assertIn("path", blob)
            paths.add(blob["path"])
        return paths

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
        excluded = set(PATH_EXCLUSIONS) | self._pinned_paths()
        violations: list[str] = []
        checked = 0
        for path in self._iter_scan_files():
            relative = path.relative_to(ROOT).as_posix()
            if "super-caveman" in path.name or "super_caveman" in path.name:
                continue  # 晋级体系自有面(规则2)
            if relative in excluded:
                continue  # 晋级钉住面(规则1)或静态排除表
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
