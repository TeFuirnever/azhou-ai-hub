from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "super-caveman" / "SKILL.md"
MODES = ROOT / "skills" / "super-caveman" / "references" / "modes.md"
SETUP = ROOT / "skills" / "super-caveman" / "references" / "setup.md"
RESPONSE_CASES = ROOT / "benchmarks" / "super-caveman" / "response-cases.json"
CAPABILITY_MAP = ROOT / "benchmarks" / "super-caveman" / "capability-map.json"


class SuperCavemanAdhdContractTest(unittest.TestCase):
    def test_setup_check_commands_do_not_finalize_recovery_evidence(self) -> None:
        setup = SETUP.read_text(encoding="utf-8")
        check_block = setup.split("Check commands before changing a file:", 1)[1].split("```", 2)[1]

        self.assertIn("finalize --help", check_block)
        self.assertNotIn("finalize /absolute/path", check_block)

    def test_open_work_ends_with_action_startable_within_two_minutes(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("under two minutes", modes)
        self.assertIn("Opening the named file counts", modes)

    def test_host_plan_tool_carries_multi_step_state_once(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("one item per step", modes)
        self.assertIn("at most one item in progress", modes)
        self.assertIn("Do not repeat the full checklist in prose", modes)
        self.assertIn("Name the active step's concrete work", modes)
        self.assertIn("Never label the active step complete because an earlier task is done", modes)

    def test_task_content_wins_over_response_shape(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("Task content wins", modes)
        self.assertIn("delete or distort the requested answer", modes)
        self.assertIn("two to four ranked options", modes)
        self.assertIn("return exactly that many numbered options", modes)
        self.assertIn("do not add a fourth option", modes)

    def test_stop_request_confirms_once_then_restores_default_style(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("Confirm deactivation in one line", modes)
        self.assertIn("Super Caveman and ADHD response shaping are off", modes)
        self.assertIn("return to the default response style immediately", modes)

    def test_pre_send_cleanup_preserves_uncertainty_and_removes_idioms(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("Keep a hedge that carries real uncertainty", modes)
        self.assertIn("Replace every idiom with literal language", modes)
        self.assertIn("contacting a person and reviewing evidence are separate actions", modes)
        self.assertIn("output two separate numbered actions", modes)
        self.assertIn("Never merge them with `with`", modes)

    def test_debugging_fix_requires_explicit_verification_action(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("an explicit verification action and expected success signal", modes)
        self.assertIn("Naming the fix is not verification", modes)

    def test_pre_send_rejects_compound_next_action(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("inspect the final next action", modes)
        self.assertIn("Keep only the first executable action", modes)
        self.assertIn("Do not append repair or verification", modes)
        self.assertIn("place status first and the next action last", modes)

    def test_complete_pinned_adhd_behavior_precedes_caveman_compression(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")

        self.assertIn("fully adopt the pinned `i-have-adhd` output-behavior contract", skill)
        self.assertIn("then apply Caveman compression", skill)

    def test_capability_map_records_full_behavior_adoption(self) -> None:
        response_style = json.loads(CAPABILITY_MAP.read_text(encoding="utf-8"))["response_style"]

        self.assertEqual("i_have_adhd", response_style["source"])
        self.assertEqual("fully-adopted", response_style["status"])
        self.assertEqual("references/modes.md", response_style["surface"])
        self.assertIn("plugin installation", response_style["reason"])

    def test_response_benchmark_covers_every_added_adhd_semantic(self) -> None:
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        cases = {case["id"]: case for case in payload["cases"]}

        expected = {
            "under-two-minute-next-action": "progress",
            "host-plan-tool-state": "planning",
            "task-wins-options": "user-preference",
            "stop-mode-default-style": "mode-control",
            "uncertainty-and-idiom": "pre-send",
        }
        self.assertEqual(expected.keys(), expected.keys() & cases.keys())
        for case_id, category in expected.items():
            case = cases[case_id]
            self.assertEqual(category, case["category"])
            self.assertGreaterEqual(len(case["criteria"]), 2)
            self.assertTrue(all(criterion.endswith(".") for criterion in case["criteria"]))

    def test_harness_time_estimates_name_the_executor(self) -> None:
        modes = MODES.read_text(encoding="utf-8")

        self.assertIn("Point each time estimate at whoever will execute the step", modes)

    def test_plan_case_requires_tool_call_evidence_and_executor_estimate(self) -> None:
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        case = next(case for case in payload["cases"] if case["id"] == "host-plan-tool-state")
        criteria = " ".join(case["criteria"])

        self.assertEqual("plan_tool_call", case["fixture"]["required_evidence"])
        self.assertIn("A prose-only checklist fails", criteria)
        self.assertIn("agent-owned backfill", criteria)

    def test_options_case_puts_the_recommendation_first(self) -> None:
        modes = MODES.read_text(encoding="utf-8")
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        case = next(case for case in payload["cases"] if case["id"] == "task-wins-options")

        self.assertIn("recommended option first", modes)
        self.assertIn("first option is explicitly recommended", " ".join(case["criteria"]))

    def test_direct_answer_case_rejects_an_unrelated_tangent(self) -> None:
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        case = next(case for case in payload["cases"] if case["id"] == "direct-answer")

        self.assertIn("unrelated", case["prompt"])
        self.assertIn("adding that tangent fails", " ".join(case["criteria"]))

    def test_complex_plan_case_rejects_lists_longer_than_five_items(self) -> None:
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        case = next(case for case in payload["cases"] if case["id"] == "complex-plan")

        self.assertIn("seven required concerns", case["prompt"])
        self.assertIn("six or more items fails", " ".join(case["criteria"]))

    def test_debugging_case_stops_patching_after_three_failed_iterations(self) -> None:
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        case = next(case for case in payload["cases"] if case["id"] == "debugging-cause")
        criteria = " ".join(case["criteria"])

        self.assertEqual(3, case["fixture"]["prior_failed_iterations"])
        self.assertEqual("patching_to_diagnosis", case["fixture"]["required_transition"])
        self.assertIn("plausible questioned assumption", criteria)
        self.assertIn("asks exactly one diagnostic question", criteria)
        self.assertIn("another patch attempt fails", criteria)

    def test_response_cases_close_state_transition_and_action_false_passes(self) -> None:
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        cases = {case["id"]: case for case in payload["cases"]}

        next_action = cases["under-two-minute-next-action"]
        self.assertIn("Step 2 of 4 is complete", next_action["prompt"])
        self.assertIn("Step 3", next_action["prompt"])
        stop = cases["stop-mode-default-style"]
        self.assertEqual("full", stop["fixture"]["initial_mode"])
        uncertainty = " ".join(cases["uncertainty-and-idiom"]["criteria"])
        self.assertIn("checking the logs", uncertainty)

    def test_multi_step_fixture_maps_completed_and_active_steps_explicitly(self) -> None:
        payload = json.loads(RESPONSE_CASES.read_text(encoding="utf-8"))
        case = next(case for case in payload["cases"] if case["id"] == "multi-step-progress")

        self.assertIn("Step 2, the schema change, is complete", case["prompt"])
        self.assertIn("Step 3 is backfilling", case["prompt"])


if __name__ == "__main__":
    unittest.main()
