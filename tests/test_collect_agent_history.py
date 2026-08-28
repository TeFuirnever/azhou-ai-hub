from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "repo-pedant" / "scripts" / "collect_agent_history.py"
SPEC = importlib.util.spec_from_file_location("collect_agent_history", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def codex_message(role: str, text: str) -> dict:
    content_type = "output_text" if role == "assistant" else "input_text"
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": content_type, "text": text}],
        },
    }


class CollectAgentHistoryTest(unittest.TestCase):
    def empty_roots(self, parent: Path) -> dict[str, Path]:
        return {runtime: parent / runtime for runtime in MODULE.RUNTIMES}

    def write_codex(self, root: Path, records: list[dict]) -> None:
        target = root / "sessions" / "2026" / "08" / "23"
        target.mkdir(parents=True)
        (target / "rollout-test.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in records),
            encoding="utf-8",
        )

    def write_claude(self, root: Path, records: list[dict]) -> None:
        target = root / "projects" / "project-a"
        target.mkdir(parents=True)
        (target / "session-test.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in records),
            encoding="utf-8",
        )

    def write_zcode(self, root: Path, messages: list[dict]) -> None:
        target = root / "v2" / "sessions" / "workspace-a"
        target.mkdir(parents=True)
        data = {
            "meta": {
                "taskId": "zcode-session-1",
                "createdAt": 1787443200000,
                "migrationSource": "claude",
            },
            "messages": messages,
        }
        (target / "session-test.json").write_text(json.dumps(data), encoding="utf-8")

    def test_codex_filters_wrappers_and_counts_outcome_signals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    {"type": "session_meta", "payload": {"id": "codex-session-1", "timestamp": "2026-08-23T00:00:00Z"}},
                    codex_message("user", "<recommended_plugins>contains $neat-freak</recommended_plugins>"),
                    codex_message("user", "收尾这个工作区"),
                    codex_message("user", "[$neat-freak](/Users/person/.agents/skills/neat-freak/SKILL.md)"),
                    codex_message("assistant", "开始处理"),
                    {
                        "type": "response_item",
                        "payload": {"type": "custom_tool_call", "name": "exec", "input": "rm -rf /private/tmp/exact-target"},
                    },
                    {
                        "type": "response_item",
                        "payload": {"type": "custom_tool_call_output", "output": '{"exit_code":1}'},
                    },
                    codex_message("assistant", "完成"),
                    codex_message("user", "不对，越界删除了"),
                    codex_message("assistant", "已恢复"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            run = report["runs"][0]
            self.assertEqual("codex", run["runtime"])
            self.assertEqual(1, run["tool_calls_heuristic"])
            self.assertEqual(1, run["destructive_calls_heuristic"])
            self.assertEqual(1, run["failed_tool_outputs_heuristic"])
            self.assertEqual("user_corrected", run["outcome_signal"])
            self.assertNotIn("request_excerpt", run)
            self.assertNotIn("codex-session-1", json.dumps(report))

    def test_claude_detects_skill_tool_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_claude(
                roots["claude"],
                [
                    {
                        "type": "user",
                        "sessionId": "claude-session-1",
                        "timestamp": "2026-08-23T00:00:00Z",
                        "message": {"role": "user", "content": "这个阶段做完了，整理仓库"},
                    },
                    {
                        "type": "assistant",
                        "sessionId": "claude-session-1",
                        "timestamp": "2026-08-23T00:00:01Z",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "neat-freak"}}],
                        },
                    },
                    {
                        "type": "assistant",
                        "sessionId": "claude-session-1",
                        "timestamp": "2026-08-23T00:00:02Z",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "## Repo-pedant receipt\n- Mode: reconcile"}],
                        },
                    },
                ],
            )

            report = MODULE.collect(roots, ("claude",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            run = report["runs"][0]
            self.assertEqual("claude", run["runtime"])
            self.assertEqual("skill_tool", run["invocation_kind"])
            self.assertTrue(run["receipt_present"])
            self.assertEqual("receipt_emitted", run["outcome_signal"])

    def test_zcode_detects_explicit_command_and_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_zcode(
                roots["zcode"],
                [
                    {"role": "user", "timestamp": 1787443200000, "content": "整理完成的改动 /neat-freak"},
                    {"role": "assistant", "timestamp": 1787443201000, "content": "## 同步完成\n已对齐"},
                ],
            )

            report = MODULE.collect(roots, ("zcode",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            run = report["runs"][0]
            self.assertEqual("zcode", run["runtime"])
            self.assertEqual("claude", run["origin"])
            self.assertEqual("explicit_user", run["invocation_kind"])
            self.assertEqual("receipt_emitted", run["outcome_signal"])

    def test_opt_in_excerpts_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    codex_message("user", "整理 /Users/person/secret at https://example.com token=secret123456"),
                    codex_message("user", "$repo-pedant"),
                    codex_message("assistant", "## Repo-pedant receipt\n- Mode: audit"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant"}, 20, True)
            excerpt = report["runs"][0]["request_excerpt"]

            self.assertIn("<path>", excerpt)
            self.assertIn("<url>", excerpt)
            self.assertIn("<secret>", excerpt)
            self.assertNotIn("person", excerpt)

    def test_injected_skill_body_is_not_an_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    codex_message("user", "Base directory for this skill: /tmp\n# Repo Pedant\n/repo-pedant"),
                    codex_message("assistant", "loaded"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant"}, 20, False)

            self.assertEqual(0, report["runs_found"])

    def test_legacy_receipt_can_infer_a_run_without_invocation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    codex_message("user", "这个阶段做完了，整理文档"),
                    codex_message("assistant", "检查仓库"),
                    codex_message("assistant", "## 同步完成\n已对齐"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            run = report["runs"][0]
            self.assertEqual("receipt_inferred", run["invocation_kind"])
            self.assertTrue(run["receipt_present"])

    def test_branded_receipt_can_infer_a_run_without_invocation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    codex_message("user", "这个阶段做完了，整理文档"),
                    codex_message("assistant", "🦊 阿舟 · Repo Pedant 启动｜mode=reconcile｜scope=/repo"),
                    codex_message("assistant", "## 🦊 阿舟 · Repo-pedant receipt\n- Schema: repo-pedant.receipt.v2"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            self.assertEqual("receipt_inferred", report["runs"][0]["invocation_kind"])
            self.assertTrue(report["runs"][0]["receipt_present"])

    def test_canonical_branded_receipt_can_infer_a_run_without_invocation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    codex_message("user", "这个阶段做完了，整理文档"),
                    codex_message("assistant", "🦊 阿舟 · Repo Pedant 启动｜mode=reconcile｜scope=/repo"),
                    codex_message("assistant", "## 🦊 阿舟 · Repo Pedant receipt\n- Schema: repo-pedant.receipt.v2"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            self.assertEqual("receipt_inferred", report["runs"][0]["invocation_kind"])
            self.assertTrue(report["runs"][0]["receipt_present"])

    def test_codex_can_infer_cleanup_from_skill_file_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    codex_message("user", "这个阶段做完了，整理一下"),
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "input": "sed -n '1,220p' /Users/person/.agents/skills/neat-freak/SKILL.md",
                        },
                    },
                    codex_message("assistant", "已处理"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            self.assertEqual("skill_file_read", report["runs"][0]["invocation_kind"])

    def test_codex_event_messages_preserve_explicit_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    {"type": "event_msg", "payload": {"type": "user_message", "message": "收尾 $neat-freak"}},
                    {"type": "event_msg", "payload": {"type": "agent_message", "message": "正在检查"}},
                    {"type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "## 同步完成\n已对齐"}},
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            self.assertEqual("explicit_user", report["runs"][0]["invocation_kind"])
            self.assertTrue(report["runs"][0]["receipt_present"])

    def test_codex_skill_xml_is_invocation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = self.empty_roots(Path(directory))
            self.write_codex(
                roots["codex"],
                [
                    codex_message("user", "整理一下这个阶段"),
                    codex_message("user", "<skill><name>neat-freak</name><path>/private/skill/SKILL.md</path></skill>"),
                    codex_message("assistant", "已处理"),
                ],
            )

            report = MODULE.collect(roots, ("codex",), {"repo-pedant", "neat-freak"}, 20, False)

            self.assertEqual(1, report["runs_found"])
            self.assertEqual("explicit_user", report["runs"][0]["invocation_kind"])


if __name__ == "__main__":
    unittest.main()
