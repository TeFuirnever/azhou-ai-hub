from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "repo-pedant" / "scripts" / "validate_evidence_bundle.py"
SPEC = importlib.util.spec_from_file_location("validate_evidence_bundle", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def report() -> dict:
    runs = []
    outcomes = ("tool_failure_signal", "insufficient_evidence", "receipt_emitted")
    invocations = ("explicit_user", "skill_tool", "explicit_user")
    for index, runtime in enumerate(MODULE.RUNTIMES):
        runs.append(
            {
                "run_id": f"{index + 1:016x}",
                "runtime": runtime,
                "origin": runtime if runtime == "zcode" else None,
                "session_digest": f"{index + 11:016x}",
                "source_digest": f"{index + 21:016x}",
                "session_started_at": "2026-08-23T00:00:00Z",
                "request_digest": f"{index + 31:016x}",
                "invocation_kind": invocations[index],
                "assistant_messages": 1,
                "tool_calls_heuristic": 0,
                "mutation_calls_heuristic": 0,
                "destructive_calls_heuristic": 0,
                "failed_tool_outputs_heuristic": int(index == 0),
                "user_corrections_heuristic": 0,
                "aborted": False,
                "receipt_present": index == 2,
                "outcome_signal": outcomes[index],
            }
        )
    return {
        "schema_version": "repo-pedant.history.v1",
        "generated_at": "2026-08-23T00:00:00+00:00",
        "skill_names": ["neat-freak", "repo-pedant"],
        "privacy": {
            "raw_text_included": False,
            "excerpts_redacted_and_truncated": False,
            "identifiers_hashed": True,
            "transcripts_treated_as_untrusted": True,
        },
        "runtime_coverage": {
            runtime: {"files_scanned": 1, "parse_errors": 0, "runs_found": 1, "limit_per_runtime": 20}
            for runtime in MODULE.RUNTIMES
        },
        "runs_found": 3,
        "outcome_counts": {outcome: 1 for outcome in outcomes},
        "runs": runs,
    }


RECEIPT = """## 🦊 阿舟 · Repo Pedant receipt

> 🧹 代码是唯一现役答案，其他都要对齐。

- Schema: repo-pedant.receipt.v2
- Status: complete_with_holds
- Mode: evolve
- Scope: synthetic fixture

### 🧭 Current truth
- Current truth: code and checks

### 🧹 Changed
- Changed: docs
- Reminders: none

### ✅ Verification
- Verified: ./verify.sh

### 🔒 Boundaries
- Holds: human promotion

### ➡️ Next action
- Next action: approve or reject promotion

### 🧠 Learning
- Learning signal: stale_fact — synthetic evidence
"""
PRIOR_BRANDED_RECEIPT = RECEIPT.replace(
    "## 🦊 阿舟 · Repo Pedant receipt",
    "## 🦊 阿舟 · Repo-pedant receipt",
)

LEGACY_RECEIPT = """## Repo-pedant receipt
- Mode: audit
- Scope: synthetic fixture
- Current truth: code and checks
- Changed: none
- Reminders: none
- Verified: read-only audit
- Holds: none
- Learning signal: none — synthetic evidence
"""


class ValidateEvidenceBundleTest(unittest.TestCase):
    def test_valid_report_with_all_runtimes(self) -> None:
        self.assertEqual([], MODULE.validate_report(report(), required_runtimes=MODULE.RUNTIMES))

    def test_count_mismatch_fails(self) -> None:
        value = report()
        value["runs_found"] = 4
        errors = MODULE.validate_report(value)
        self.assertTrue(any("runs array length" in error for error in errors))

    def test_excerpts_are_opt_in_and_privacy_labeled(self) -> None:
        value = copy.deepcopy(report())
        value["runs"][0]["request_excerpt"] = "redacted"
        value["privacy"]["raw_text_included"] = True
        value["privacy"]["excerpts_redacted_and_truncated"] = True
        self.assertTrue(any("--allow-excerpts" in error for error in MODULE.validate_report(value)))
        self.assertEqual([], MODULE.validate_report(value, allow_excerpts=True))

    def test_receipt_requires_stable_fields(self) -> None:
        self.assertEqual([], MODULE.validate_receipt(RECEIPT))
        errors = MODULE.validate_receipt(RECEIPT.replace("- Holds: human promotion\n", ""))
        self.assertTrue(any("receipt.Holds" in error for error in errors))

    def test_legacy_receipt_remains_valid(self) -> None:
        self.assertEqual([], MODULE.validate_receipt(LEGACY_RECEIPT))

    def test_prior_branded_receipt_remains_valid(self) -> None:
        self.assertEqual([], MODULE.validate_receipt(PRIOR_BRANDED_RECEIPT))

    def test_branded_receipt_enforces_machine_status_invariants(self) -> None:
        emoji_status = RECEIPT.replace("- Status: complete_with_holds", "- Status: 🟡 收齐，但有挂起")
        self.assertTrue(any("receipt.Status: unsupported" in error for error in MODULE.validate_receipt(emoji_status)))

        false_complete = RECEIPT.replace("- Status: complete_with_holds", "- Status: complete")
        self.assertTrue(any("complete requires Holds: none" in error for error in MODULE.validate_receipt(false_complete)))

        audit_changed = RECEIPT.replace("- Status: complete_with_holds", "- Status: audit_only").replace(
            "- Mode: evolve", "- Mode: audit"
        )
        self.assertTrue(any("audit_only requires" in error for error in MODULE.validate_receipt(audit_changed)))

        failed_without_action = RECEIPT.replace("- Status: complete_with_holds", "- Status: failed").replace(
            "- Next action: approve or reject promotion", "- Next action: none"
        )
        self.assertTrue(any("failed requires" in error for error in MODULE.validate_receipt(failed_without_action)))


if __name__ == "__main__":
    unittest.main()
