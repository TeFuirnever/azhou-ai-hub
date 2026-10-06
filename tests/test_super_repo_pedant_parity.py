from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-repo-pedant"
SKILL_TEXT = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
PARITY = json.loads((ROOT / "benchmarks" / "super-repo-pedant" / "neat-freak-parity.json").read_text(encoding="utf-8"))
REGRESSIONS = json.loads((ROOT / "benchmarks" / "super-repo-pedant" / "regression-map.json").read_text(encoding="utf-8"))["regressions"]
TRIGGER_CASES = json.loads((ROOT / "benchmarks" / "super-repo-pedant" / "trigger-cases.json").read_text(encoding="utf-8"))
CONTRACT_TEXT = (SKILL_DIR / "references" / "neat-freak-compatibility.md").read_text(encoding="utf-8")
PROVENANCE_TEXT = (SKILL_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
AUDIT_TEXT = (ROOT / "docs" / "research" / "2026-10-07-neat-freak-v3-capability-audit.md").read_text(encoding="utf-8")
PIN_COMMIT = "bab178311a65f93ffd073e4fdebc9911eae35791"
V3_OBSERVATION_COMMIT = "322346ded8129436b3f64707789a73e732ae24d9"
AUDIT_DOC_RELPATH = "docs/research/2026-10-07-neat-freak-v3-capability-audit.md"


class RepoPedantParityTest(unittest.TestCase):
    def test_no_original_capability_remains_unrestored(self) -> None:
        self.assertEqual(28, len(PARITY["capabilities"]))
        allowed = {"preserved", "restored", "conflict_replaced", "disadvantage_replaced"}
        self.assertFalse([item for item in PARITY["capabilities"] if item["status"] not in allowed])
        self.assertFalse([item for item in PARITY["capabilities"] if item["regression"] not in REGRESSIONS])
        for item in PARITY["capabilities"]:
            if item["status"].endswith("_replaced"):
                self.assertTrue(item.get("replacement"), item["id"])

    def test_full_trigger_vocabulary_and_inferred_reminder_contract(self) -> None:
        frontmatter = re.match(r"^---\n(?P<body>.*?)\n---", SKILL_TEXT, re.DOTALL).group("body")
        for phrase in (
            "sync up",
            "tidy or clean up docs",
            "update memory",
            "/sync",
            "/neat",
            "同步一下",
            "整理文档",
            "整理一下",
            "更新记忆",
            "梳理一下",
            "收尾",
            "这个阶段做完了",
            "新人能直接上手",
            "bare tidy/整理",
        ):
            self.assertIn(phrase, frontmatter)
        self.assertIn("只提醒一次", SKILL_TEXT)
        self.assertIn("不创建状态、不修改文件", SKILL_TEXT)
        self.assertIn("普通实现、重构或整改请求", SKILL_TEXT)
        self.assertIn("仅提到 super-repo-pedant", SKILL_TEXT)
        self.assertIn("不视为收尾授权", SKILL_TEXT)

        outcomes = {case["id"]: case["expected"] for case in TRIGGER_CASES["cases"]}
        self.assertEqual("reconcile", outcomes["bare-tidy"])
        self.assertEqual("audit", outcomes["explicit-audit"])
        self.assertEqual("evolve", outcomes["explicit-evolve"])
        self.assertEqual("normal_task_then_optional_reminder", outcomes["ordinary-policy-edit"])
        self.assertEqual("normal_task_then_optional_reminder", outcomes["function-refactor"])
        self.assertEqual("remind_only", outcomes["inferred-milestone"])

    def test_detailed_consumer_matrix_and_semantic_checks_are_mandatory(self) -> None:
        impact = (SKILL_DIR / "references" / "impact-matrix.md").read_text(encoding="utf-8")
        for role in ("integration/setup", "architecture", "runbook", "handoff/changelog/current status"):
            self.assertIn(role, impact)
        for changed in ("API, route, CLI, SDK", "Environment variable", "Database table", "Deployment/infrastructure"):
            self.assertIn(changed, impact)
        inventory = (SKILL_DIR / "scripts" / "inventory_knowledge.py").read_text(encoding="utf-8")
        for check in (
            "semantic_paths_commands",
            "semantic_readme_setup",
            "semantic_memory_links",
            "propagation_reviewed",
            "relative_time_reviewed",
        ):
            self.assertIn(check, inventory)

    def test_no_new_facts_still_requires_drift_audit(self) -> None:
        self.assertIn("即使本次对话没有新事实", SKILL_TEXT)
        self.assertIn("上次收尾遗漏", SKILL_TEXT)

    def test_runtime_candidates_are_concrete_but_verified(self) -> None:
        runtime = (SKILL_DIR / "references" / "runtime-history.md").read_text(encoding="utf-8")
        for candidate in (
            "~/.claude/projects/<encoded-project>/memory/MEMORY.md",
            "$CODEX_HOME/AGENTS.md",
            "~/.config/opencode/",
            "~/.openclaw/",
        ):
            self.assertIn(candidate, runtime)
        self.assertIn("discovery candidates, not ownership proof", runtime)

    def test_current_additions_remain_present(self) -> None:
        for phrase in (
            "代码是唯一现役答案",
            "audit",
            "reconcile",
            "handoff",
            "evolve",
            "项目 memory",
            "CHECKPOINT",
        ):
            self.assertIn(phrase, SKILL_TEXT)
        self.assertTrue((SKILL_DIR / "scripts" / "collect_agent_history.py").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "validate_evidence_bundle.py").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "closeout_hook.py").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "manage_evolution.py").is_file())

    def test_contract_v2_records_upstream_v3_delta_without_rebaselining(self) -> None:
        # Positive controls: contract v2 documents the audited upstream v3 delta.
        self.assertIn("Contract version: v2 (2026-10-07)", CONTRACT_TEXT)
        self.assertIn("## Baseline and upstream v3 delta", CONTRACT_TEXT)
        self.assertIn(V3_OBSERVATION_COMMIT, CONTRACT_TEXT)
        self.assertIn("equivalent evolution", CONTRACT_TEXT)
        self.assertIn(AUDIT_DOC_RELPATH, CONTRACT_TEXT)
        self.assertIn(V3_OBSERVATION_COMMIT, PROVENANCE_TEXT)
        self.assertIn(AUDIT_DOC_RELPATH, PROVENANCE_TEXT)
        # The audit document exists and carries the per-capability ledger the contract cites.
        self.assertTrue((ROOT / AUDIT_DOC_RELPATH).is_file())
        self.assertIn("pin `bab17831` 语义", AUDIT_TEXT)
        for verdict_count in ("kept 20", "changed 8", "removed 0"):
            self.assertIn(verdict_count, AUDIT_TEXT)
        self.assertIn(V3_OBSERVATION_COMMIT, AUDIT_TEXT)
        # Negative controls: the ledger stays bound to the pinned baseline; v3 is
        # recorded as an observation baseline, never adopted as the implementation baseline.
        self.assertIn(PIN_COMMIT, CONTRACT_TEXT)
        self.assertIn("Every ledger row below is judged against this baseline", CONTRACT_TEXT)
        self.assertIn("not new mandatory rows", CONTRACT_TEXT)
        self.assertIn(PIN_COMMIT, PROVENANCE_TEXT)
        self.assertIn("The implementation baseline stays at the pin above", PROVENANCE_TEXT)
        self.assertEqual(28, len(PARITY["capabilities"]))
        self.assertIn("## Required original behavior", CONTRACT_TEXT)
        # The bare-tidy trigger divergence is recorded, not silently adopted from v3.
        self.assertEqual("reconcile", {case["id"]: case["expected"] for case in TRIGGER_CASES["cases"]}["bare-tidy"])
        self.assertIn("bare-tidy", CONTRACT_TEXT)


if __name__ == "__main__":
    unittest.main()
