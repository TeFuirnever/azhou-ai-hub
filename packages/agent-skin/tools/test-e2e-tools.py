#!/usr/bin/env python3
"""Unit checks of the E2E tooling's pure verdict logic (L4 family, E2 stage).

Loads tools/e2e-cold-start.py as a module (same convention as
test-functional-verdict.py) and exercises the journal-chain and probe-JSON
assertions with synthetic inputs; no host, no CDP, no process is touched.
E3 (daily-path) and E4 (runner) stages append their suites to this file.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("e2e_cold_start", Path(__file__).with_name("e2e-cold-start.py"))
cold_start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cold_start)


def chain_records(*stages: str, exit_outcome: str = "startup-ready", exit_code: int = 0,
                  extra: tuple[dict, ...] = ()) -> list[dict]:
    """Journal-shaped records: zcode stages ride event='zcode-runtime'."""
    records = [{"schema": cold_start.EVENT_SCHEMA, "event": "zcode-runtime", "stage": stage,
                "seconds": 0.1 * index, "launcherPID": 43374}
               if stage.startswith("zcode-")
               else {"schema": cold_start.EVENT_SCHEMA, "event": stage,
                     "seconds": 0.1 * index, "launcherPID": 43374}
               for index, stage in enumerate(stages)]
    if "launcher-exit" in stages:
        records = [record for record in records if record.get("event") != "launcher-exit"]
        records.append({"schema": cold_start.EVENT_SCHEMA, "event": "launcher-exit",
                        "outcome": exit_outcome, "exitCode": exit_code,
                        "seconds": 9.9, "launcherPID": 43374})
    return [*records, *extra]


FULL_CHAIN = ("launcher-start", "zcode-open-request", "zcode-open-selected-process",
              "zcode-target-summary", "zcode-page-bound", "zcode-controller-ready",
              "startup-ready", "launcher-exit")


def green_probe() -> dict:
    """Probe JSON from tools/probe_dom.mjs for a fully skinned page.

    Mirrors the verified build-41 daily acceptance (2026-11-08): two active
    surfaces (full window 1512x889 + main pane 1171x832) and the entry chip
    probed through its shadow root (label 'Azhou Appearance', avatar, 316x44,
    inside the sidebar).
    """
    return {
        "kind": "zcode-dom-probe", "schema": 1, "port": 64486,
        "wallpaper": {
            "documentElement": "active",
            "surfaces": [
                {"tag": "DIV", "role": "root", "marker": "active",
                 "rect": {"x": 0, "y": 0, "width": 1512, "height": 889}},
                {"tag": "MAIN", "role": "main", "marker": "active",
                 "rect": {"x": 341, "y": 57, "width": 1171, "height": 832}},
            ],
        },
        "entry": {
            "found": True, "shadowRoot": True, "attribute": "appearance",
            "label": "Azhou Appearance", "ariaLabel": "Azhou Appearance",
            "title": "Open appearance settings",
            "avatar": {"present": True, "complete": True, "naturalWidth": 1254,
                       "naturalHeight": 1254, "srcKind": "data-url"},
            "rect": {"x": 14, "y": 168, "width": 316, "height": 44},
            "visible": True, "inSidebar": True, "sidebarCount": 1,
        },
    }


class EventChainTests(unittest.TestCase):
    def test_full_ordered_chain_with_clean_exit_is_green(self):
        verdict = cold_start.assert_event_chain(chain_records(*FULL_CHAIN))
        self.assertTrue(verdict["passed"], verdict["problems"])
        self.assertEqual(verdict["missing"], [])
        self.assertEqual(verdict["refusals"], [])
        self.assertEqual(verdict["chainObserved"], list(FULL_CHAIN))
        report = cold_start.assemble_verdicts(chain_records(*FULL_CHAIN), green_probe())
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["checks"]), 3)

    def test_missing_stage_is_red_and_names_it(self):
        stages = [stage for stage in FULL_CHAIN if stage != "zcode-page-bound"]
        verdict = cold_start.assert_event_chain(chain_records(*stages))
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["missing"], ["zcode-page-bound"])

    def test_zcode_runtime_failed_refusal_is_red(self):
        refusal = ({"schema": cold_start.EVENT_SCHEMA, "event": "zcode-runtime",
                    "stage": "zcode-runtime-failed", "reason": "cdp-deadline",
                    "seconds": 3.2, "launcherPID": 43374},)
        verdict = cold_start.assert_event_chain(chain_records(*FULL_CHAIN, extra=refusal))
        self.assertFalse(verdict["passed"])
        self.assertEqual([item["stage"] for item in verdict["refusals"]], ["zcode-runtime-failed"])
        self.assertEqual(verdict["refusals"][0]["reason"], "cdp-deadline")

    def test_zcode_validate_identity_refused_is_red(self):
        refusal = ({"schema": cold_start.EVENT_SCHEMA, "event": "zcode-runtime",
                    "stage": "zcode-validate-identity-refused", "observed": "unregistered",
                    "expectedPID": 62079, "seconds": 2.4, "launcherPID": 43374},)
        verdict = cold_start.assert_event_chain(chain_records(*FULL_CHAIN, extra=refusal))
        self.assertFalse(verdict["passed"])
        self.assertEqual([item["stage"] for item in verdict["refusals"]],
                         ["zcode-validate-identity-refused"])
        self.assertEqual(verdict["refusals"][0]["observed"], "unregistered")

    def test_out_of_order_chain_is_red(self):
        swapped = list(FULL_CHAIN)
        swapped.remove("zcode-page-bound")
        swapped.insert(swapped.index("zcode-open-selected-process"), "zcode-page-bound")
        verdict = cold_start.assert_event_chain(chain_records(*swapped))
        self.assertFalse(verdict["passed"])
        self.assertTrue(verdict["outOfOrder"], "out-of-order stages must be named")
        self.assertTrue(any("zcode-page-bound" in entry for entry in verdict["outOfOrder"]))

    def test_nonzero_exit_or_wrong_outcome_is_red(self):
        for outcome, code in (("behavior-not-proven", 1), ("activated", 0)):
            verdict = cold_start.assert_event_chain(
                chain_records(*FULL_CHAIN, exit_outcome=outcome, exit_code=code))
            self.assertFalse(verdict["passed"], outcome)

    def test_unparsable_journal_line_fails_the_chain(self):
        lines = [json.dumps(record) for record in chain_records(*FULL_CHAIN)] + ["{not-json"]
        records, problems = cold_start.parse_event_lines(lines)
        self.assertEqual(len(records), len(FULL_CHAIN))
        self.assertEqual(len(problems), 1)
        verdict = cold_start.assert_event_chain(records, problems)
        self.assertFalse(verdict["passed"])
        self.assertIn("journal has unparsable lines", verdict["problems"])

    def test_non_schema_diagnostics_do_not_break_the_chain(self):
        diagnostic = {"event": "lock-error", "errno": 11}
        verdict = cold_start.assert_event_chain(chain_records(*FULL_CHAIN, extra=(diagnostic,)))
        self.assertTrue(verdict["passed"], verdict["problems"])

    def test_seconds_regression_is_red(self):
        records = chain_records(*FULL_CHAIN)
        records[3]["seconds"] = 0.05  # earlier than the preceding record
        verdict = cold_start.assert_event_chain(records)
        self.assertFalse(verdict["passed"])
        self.assertFalse(verdict["secondsMonotonic"])


class ProbeVerdictTests(unittest.TestCase):
    def test_both_surfaces_and_complete_chip_are_green(self):
        wallpaper = cold_start.assert_wallpaper_surfaces(green_probe())
        chip = cold_start.assert_entry_chip(green_probe())
        self.assertTrue(wallpaper["passed"], wallpaper["problems"])
        self.assertTrue(chip["passed"], chip["problems"])

    def test_missing_main_surface_is_red(self):
        probe = green_probe()
        del probe["wallpaper"]["surfaces"][1]
        verdict = cold_start.assert_wallpaper_surfaces(probe)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("main-pane" in problem for problem in verdict["problems"]))

    def test_inactive_document_attribute_is_red(self):
        probe = green_probe()
        probe["wallpaper"]["documentElement"] = None
        verdict = cold_start.assert_wallpaper_surfaces(probe)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("data-azhou-wallpaper" in problem for problem in verdict["problems"]))

    def test_inactive_surface_marker_is_red(self):
        probe = green_probe()
        probe["wallpaper"]["surfaces"][1]["marker"] = None
        verdict = cold_start.assert_wallpaper_surfaces(probe)
        self.assertFalse(verdict["passed"])

    def test_chip_missing_from_light_dom_is_red(self):
        probe = green_probe()
        probe["entry"] = {"found": False, "shadowRoot": False, "reason": "host-not-in-light-dom"}
        verdict = cold_start.assert_entry_chip(probe)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("not found" in problem for problem in verdict["problems"]))

    def test_chip_without_shadow_root_is_red(self):
        probe = green_probe()
        probe["entry"].update({"shadowRoot": False, "label": None, "ariaLabel": None,
                               "avatar": {"present": False}})
        verdict = cold_start.assert_entry_chip(probe)
        self.assertFalse(verdict["passed"])
        for fragment in ("no probed open shadow root", "label text", "aria-label", "avatar"):
            self.assertTrue(any(fragment in problem for problem in verdict["problems"]), fragment)

    def test_chip_outside_sidebar_or_empty_rect_is_red(self):
        probe = green_probe()
        probe["entry"]["inSidebar"] = False
        self.assertFalse(cold_start.assert_entry_chip(probe)["passed"])
        probe = green_probe()
        probe["entry"]["rect"] = {"x": 0, "y": 0, "width": 0, "height": 0}
        self.assertFalse(cold_start.assert_entry_chip(probe)["passed"])

    def test_unloaded_avatar_is_red(self):
        probe = green_probe()
        probe["entry"]["avatar"] = {"present": True, "complete": False,
                                    "naturalWidth": 0, "naturalHeight": 0, "srcKind": "data-url"}
        verdict = cold_start.assert_entry_chip(probe)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("did not load" in problem for problem in verdict["problems"]))

    def test_partial_probe_fails_the_assembled_report(self):
        probe = green_probe()
        probe["wallpaper"]["surfaces"].pop()
        report = cold_start.assemble_verdicts(chain_records(*FULL_CHAIN), probe)
        self.assertFalse(report["passed"])
        self.assertTrue(report["checks"][0]["passed"])  # chain unaffected
        self.assertTrue(report["checks"][2]["passed"])  # chip still green
        self.assertFalse(report["checks"][1]["passed"])  # wallpaper surfaces red


RUNNER_SPEC = importlib.util.spec_from_file_location("e2e_runner", Path(__file__).with_name("e2e.py"))
e2e_runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(e2e_runner)

ASSET_GATE_SPEC = importlib.util.spec_from_file_location(
    "check_private_assets", Path(__file__).with_name("check-private-assets.py"))
private_assets = importlib.util.module_from_spec(ASSET_GATE_SPEC)
ASSET_GATE_SPEC.loader.exec_module(private_assets)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class PrivateAssetManifestTests(unittest.TestCase):
    """E4 L0 gate: missing manifest or missing asset is red at layer 0 (P3.4/P10.1)."""

    @classmethod
    def setUpClass(cls):
        cls.module = private_assets

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-private-assets-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def write_manifest(self, text: str) -> None:
        path = self.root / "tools/private-assets.MANIFEST.expected"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_asset(self, relative: str, payload: bytes = b"private-artwork") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def gate(self) -> tuple[int, dict]:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = self.module.main(argv=[], root=self.root)
        return code, json.loads(captured.getvalue())

    def test_missing_manifest_is_red_with_the_copy_hint(self):
        code, report = self.gate()
        self.assertEqual(code, 1)
        self.assertFalse(report["passed"])
        self.assertIn("维护者 worktree", report["problems"][0])
        self.assertIn("MANIFEST.expected", report["problems"][0])

    def test_missing_listed_asset_is_red_and_names_it(self):
        # A partial artwork copy: one listed file present, one missing. Any
        # artwork in assets/private puts the gate in strict mode, so the
        # missing entry fails red (P3.4) instead of hiding behind the
        # fresh-checkout mode.
        self.write_asset("assets/private/scene.js", b"partial-copy")
        self.write_manifest("assets/private/scene.js\nassets/private/working.png\n")
        code, report = self.gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["mode"], "strict")
        self.assertEqual(report["checks"][1]["path"], "assets/private/working.png")
        self.assertFalse(report["checks"][1]["passed"])
        self.assertIn("missing", report["checks"][1]["problems"][0])

    def test_artwork_free_checkout_is_green_in_fresh_checkout_mode(self):
        # The CI shape: git carries only the tracked manifest, and the
        # untracked artwork is not observable. Green must stay explicit, never
        # silent - the report names the mode and carries the copy note.
        self.write_manifest("assets/private/working.png\n")
        code, report = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(report["passed"])
        self.assertEqual(report["mode"], "fresh-checkout")
        self.assertEqual(report["checks"], [])
        self.assertIn("strict mode", report["note"])

    def test_recorded_sha256_mismatch_is_red_with_both_hashes(self):
        asset = self.write_asset("assets/private/scene.js", b"changed-scene")
        self.write_manifest(f"assets/private/scene.js {'a' * 64}\n")
        code, report = self.gate()
        self.assertEqual(code, 1)
        problem = report["checks"][0]["problems"][0]
        self.assertIn("sha256 mismatch", problem)
        self.assertIn("a" * 64, problem)
        self.assertIn(digest(asset), problem)

    def test_complete_manifest_with_baselines_is_green(self):
        first = self.write_asset("assets/private/working.png", b"artwork-one")
        second = self.write_asset("assets/private/scene.js", b"artwork-two")
        self.write_manifest(f"assets/private/working.png {digest(first)}\n"
                            f"assets/private/scene.js {digest(second)}\n")
        code, report = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(report["passed"])
        self.assertEqual(report["mode"], "strict")
        self.assertEqual([check["observed"] for check in report["checks"]],
                         [digest(first), digest(second)])

    def test_manifest_without_baseline_checks_existence_only(self):
        self.write_asset("assets/private/working.png")
        self.write_manifest("# comment line\n\nassets/private/working.png\n")
        code, report = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(report["passed"])
        self.assertIsNone(report["checks"][0]["expected"])

    def test_symlinked_asset_is_refused_fail_closed(self):
        target = self.root / "elsewhere.png"
        target.write_bytes(b"outside")
        link = self.root / "assets/private/working.png"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        self.write_manifest("assets/private/working.png\n")
        code, report = self.gate()
        self.assertEqual(code, 1)
        self.assertIn("symlink refused", report["checks"][0]["problems"][0])

    def test_malformed_and_duplicate_manifest_lines_are_red(self):
        self.write_asset("assets/private/working.png")
        self.write_manifest("\n/assets/private/absolute.png\n"
                            "assets/private/../escape.png\n"
                            "assets/private/working.png ZZZZ\n"
                            "assets/private/working.png\n"
                            "assets/private/working.png\n")
        code, report = self.gate()
        self.assertEqual(code, 1)
        self.assertEqual(len(report["manifestProblems"]), 4)

    def test_empty_manifest_is_red_not_vacuously_green(self):
        self.write_manifest("# only comments, no entries\n")
        code, report = self.gate()
        self.assertEqual(code, 1)
        self.assertFalse(report["passed"])
        self.assertIn("lists no assets", report["manifestProblems"][0])


class RunnerLayerTests(unittest.TestCase):
    """E4 runner layer map: quick embeds the L0 gate; delegates stay plan-first."""

    @classmethod
    def setUpClass(cls):
        cls.module = e2e_runner

    def test_quick_layer_orders_the_asset_gate_before_the_unit_suites(self):
        steps = self.module.layer_commands("quick", execute=False)
        self.assertEqual(list(steps), ["private-assets", "unit-e2e-tools", "unit-ship-zcode"])
        gate_script, gate_command = steps["private-assets"]
        self.assertEqual(gate_script.name, "check-private-assets.py")
        self.assertNotIn("--plan", gate_command)
        for step, suite in self.module.UNIT_STEPS.items():
            script, command = steps[step]
            self.assertEqual(script.name, suite)
            self.assertNotIn("--plan", command)

    def test_all_layer_is_quick_then_cold_then_daily(self):
        self.assertEqual(list(self.module.layer_commands("all", execute=False)),
                         ["private-assets", "unit-e2e-tools", "unit-ship-zcode",
                          "cold-start", "daily-start"])

    def test_delegate_layers_default_to_plan_and_execute_is_explicit(self):
        for layer, step in (("cold", "cold-start"), ("daily", "daily-start")):
            script, planned = self.module.layer_commands(layer, execute=False)[step]
            self.assertEqual(script.name, self.module.PLAN_STEPS[step])
            self.assertEqual(planned[-1], "--plan")
            _, executed = self.module.layer_commands(layer, execute=True)[step]
            self.assertEqual(executed[-1], "--execute")

    def test_run_step_passes_the_child_exit_code_through(self):
        for code in (0, 3, 7, 42):
            outcome = self.module.run_step("probe", [sys.executable, "-c", f"import sys; sys.exit({code})"])
            self.assertEqual(outcome["exitCode"], code, code)
            self.assertGreaterEqual(outcome["durationSeconds"], 0.0)

    def test_signal_returns_are_mapped_to_128_plus_signal(self):
        self.assertEqual(self.module.process_status(0), 0)
        self.assertEqual(self.module.process_status(7), 7)
        self.assertEqual(self.module.process_status(-9), 137)


class RunnerWorktreeTests(unittest.TestCase):
    """E4 runner worktree discipline: cwd must live in this worktree (P8.1)."""

    @classmethod
    def setUpClass(cls):
        cls.module = e2e_runner

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-e2e-worktree-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()

    def make_repo(self, name: str) -> Path:
        repo = self.base / name
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo

    def test_same_worktree_from_a_subdirectory_is_green(self):
        repo = self.make_repo("worktree")
        nested = repo / "packages/agent-skin/tools"
        nested.mkdir(parents=True)
        verdict = self.module.worktree_verdict(cwd=nested, runner_home=repo)
        self.assertTrue(verdict["problems"] == [] and verdict["passed"], verdict)
        self.assertEqual(verdict["expected"], verdict["observed"])

    def test_foreign_checkout_is_red_with_both_toplevels(self):
        mine, theirs = self.make_repo("mine"), self.make_repo("theirs")
        verdict = self.module.worktree_verdict(cwd=theirs, runner_home=mine)
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["expected"], str(mine.resolve()))
        self.assertEqual(verdict["observed"], str(theirs.resolve()))
        self.assertTrue(any("build-36" in problem or "another checkout" in problem
                            for problem in verdict["problems"]), verdict["problems"])

    def test_cwd_outside_any_git_work_tree_is_red(self):
        plain = self.base / "plain"
        plain.mkdir()
        verdict = self.module.worktree_verdict(cwd=plain, runner_home=self.make_repo("home"))
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("not inside" in problem for problem in verdict["problems"]))

    def test_main_stops_red_before_any_step_and_journals_the_failure(self):
        mine, theirs = self.make_repo("mine"), self.make_repo("theirs")
        journal = self.base / "runs/e2e-run.jsonl"
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            code = self.module.main(["--layer", "quick"], cwd=theirs, root=mine, record_path=journal)
        self.assertEqual(code, 1)
        self.assertIn("RED worktree", errors.getvalue())
        record = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["schema"], self.module.RUN_SCHEMA)
        self.assertEqual(record["layer"], "quick")
        self.assertFalse(record["worktree"]["passed"])
        self.assertEqual(record["exitCode"], 1)
        self.assertEqual(record["steps"], [])  # no child ran from the wrong checkout


class RunnerIntegrationTests(unittest.TestCase):
    """E4 runner through the process boundary: passthrough, journal, fail-closed.

    Builds a synthetic git worktree containing copies of tools/e2e.py and
    tools/check-private-assets.py, stub unit suites and a green asset manifest,
    then runs the real runner as a subprocess the way a caller would.
    """

    @classmethod
    def setUpClass(cls):
        cls.module = e2e_runner

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-e2e-runner-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "synthetic"
        tools = self.root / "tools"
        tools.mkdir(parents=True)
        shutil.copy(Path(__file__).with_name("e2e.py"), tools / "e2e.py")
        shutil.copy(Path(__file__).with_name("check-private-assets.py"), tools / "check-private-assets.py")
        for suite in self.module.UNIT_STEPS.values():
            (tools / suite).write_text('print("stub unit suite ok")\n', encoding="utf-8")
        asset = self.write_asset("assets/private/working.png", b"synthetic-artwork")
        (self.root / "tools/private-assets.MANIFEST.expected").write_text(
            f"assets/private/working.png {digest(asset)}\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def write_asset(self, relative: str, payload: bytes) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def run_runner(self, arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-B", str(self.root / "tools/e2e.py"), *arguments],
                              cwd=str(cwd), capture_output=True, text=True, check=False)

    def last_record(self) -> dict:
        lines = (self.root / ".local/e2e-run.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_green_quick_run_exits_zero_and_journals_itself(self):
        completed = self.run_runner(["--layer", "quick"], cwd=self.root)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"passed": true', completed.stdout)  # child output survived, no pipe eaten it
        record = self.last_record()
        self.assertEqual(record["schema"], self.module.RUN_SCHEMA)
        self.assertEqual(record["layer"], "quick")
        self.assertEqual(record["command"], ["e2e.py", "--layer", "quick"])
        self.assertTrue(record["worktree"]["passed"])
        self.assertEqual(record["exitCode"], 0)
        self.assertIsInstance(record["durationSeconds"], float)
        self.assertEqual([(step["id"], step["exitCode"]) for step in record["steps"]],
                         [("private-assets", 0), ("unit-e2e-tools", 0), ("unit-ship-zcode", 0)])

    def test_failing_unit_suite_exit_code_reaches_the_caller_untouched(self):
        (self.root / "tools/test-ship-zcode.py").write_text(
            'import sys\nprint("stub failing suite")\nsys.exit(5)\n', encoding="utf-8")
        completed = self.run_runner(["--layer", "quick"], cwd=self.root)
        self.assertEqual(completed.returncode, 5)  # the child's own code, nothing remapped
        record = self.last_record()
        self.assertEqual(record["exitCode"], 5)
        self.assertEqual(record["steps"][-1]["id"], "unit-ship-zcode")
        self.assertEqual(record["steps"][-1]["exitCode"], 5)

    def test_missing_delegate_tool_is_red_not_green(self):
        completed = self.run_runner(["--layer", "daily"], cwd=self.root)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("RED daily-start", completed.stderr)
        self.assertIn("tool missing", completed.stderr)
        record = self.last_record()
        self.assertEqual(record["exitCode"], 1)
        self.assertTrue(record["steps"][0]["problems"])

    def test_delegate_plan_mode_is_the_default_and_execute_warns_loudly(self):
        planned = self.run_runner(["--layer", "daily"], cwd=self.root)
        self.assertIn("plan 模式", planned.stderr)
        self.assertNotIn("!!!", planned.stderr)
        executed = self.run_runner(["--layer", "daily", "--execute"], cwd=self.root)
        self.assertIn("!!!", executed.stderr)
        self.assertIn("--execute", executed.stderr)
        self.assertEqual(executed.returncode, 1)  # still the missing-tool red; nothing was started

    def test_wrong_checkout_run_is_red_through_the_process_boundary(self):
        other = self.base / "other-checkout"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        completed = self.run_runner(["--layer", "quick"], cwd=other)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("RED worktree", completed.stderr)
        record = self.last_record()  # journal still lands in the runner's own root
        self.assertEqual(record["exitCode"], 1)
        self.assertEqual(record["steps"], [])


SPEC_DAILY = importlib.util.spec_from_file_location("e2e_daily", Path(__file__).with_name("e2e-daily.py"))
daily = importlib.util.module_from_spec(SPEC_DAILY)
SPEC_DAILY.loader.exec_module(daily)


DAILY_LAUNCHER_PATH = "/Users/guanxueliang/Applications/阿舟 AI 实验室 for ZCode.app"
# The receipt names the ZCode main process, never the launcher (P5.2).
TARGET_PID = 43380
TARGET_PORT = 64486
# Verified ZCode executableSHA256 (Native/ZCodeSkinRuntime.swift contract test).
TARGET_SHA256 = "a9279c2cb198fa58efe564b417ff6717cff388c5fa391c17fc2766a6b1b2121d"
COLD_STAGES = daily.COLD_CHAIN[:-1]  # launcher-exit is appended by the helper
HOT_STAGES = daily.HOT_CHAIN[:-1]


def daily_run_lines(pid: int, stages, *, outcome: str = "startup-ready", exit_code: int = 0,
                    seconds0: float = 0.0) -> list[str]:
    """Journal lines of one launcher run; zcode stages ride event='zcode-runtime'."""
    lines = []
    for index, stage in enumerate(stages):
        record = {"schema": daily.EVENT_SCHEMA, "seconds": seconds0 + 0.1 * index,
                  "launcherPID": pid, "launcherPath": DAILY_LAUNCHER_PATH}
        if stage.startswith("zcode-"):
            record["event"] = "zcode-runtime"
            record["stage"] = stage
        else:
            record["event"] = stage
        if stage == "target-activated":
            record.update({"targetPID": TARGET_PID, "host": "zcode",
                           "evidence": "typed-controller-receipt", "completion_not_inferred": True})
        lines.append(json.dumps(record))
    lines.append(json.dumps({"schema": daily.EVENT_SCHEMA, "event": "launcher-exit",
                             "outcome": outcome, "exitCode": exit_code,
                             "seconds": seconds0 + 9.9, "launcherPID": pid,
                             "launcherPath": DAILY_LAUNCHER_PATH}))
    return lines


def refused_run_lines(pid: int, seconds0: float = 0.0) -> list[str]:
    """A pre-existing refused daily run (the 2026-11-08 morning shape)."""
    return daily_run_lines(pid, ("launcher-start", "zcode-open-request", "zcode-runtime-failed"),
                           outcome="startup-failed", exit_code=1, seconds0=seconds0)


def green_receipt() -> dict:
    return {"pid": TARGET_PID, "port": TARGET_PORT, "launchTime": 834721.5,
            "executableSHA256": TARGET_SHA256}


def lsof_row(*, pid: int = TARGET_PID, port: int = TARGET_PORT, command: str = "ZCode") -> str:
    return (f"{command}  {pid} guanxueliang  38u  IPv6 0x9f8e7d6c5b4a      0t0  "
            f"TCP 127.0.0.1:{port} (LISTEN)")


def only_group(lines: list[str]) -> dict:
    increment = daily.parse_journal_increment(lines)
    if len(increment["groups"]) != 1:
        raise AssertionError(f"expected exactly one launcherPID group, saw {len(increment['groups'])}")
    return increment["groups"][0]


class ReceiptParsingTests(unittest.TestCase):
    """E3 receipt parsing through real text (the --execute L5 entry point).

    The verdict helpers receive pre-parsed dicts everywhere else; these checks
    keep parse_receipt itself honest, because run_daily reads the receipt file
    as text and every --execute path goes through this function first.
    """

    def receipt_text(self, **overrides) -> str:
        payload = {"pid": TARGET_PID, "port": TARGET_PORT, "launchTime": 834721.5,
                   "executableSHA256": TARGET_SHA256, **overrides}
        return json.dumps(payload)

    def assert_receipt_error(self, text: str, code: str) -> None:
        with self.assertRaises(ValueError) as raised:
            daily.parse_receipt(text)
        self.assertEqual(str(raised.exception), code)

    def test_valid_receipt_text_parses_to_the_identity_dict(self):
        parsed = daily.parse_receipt(self.receipt_text())
        self.assertEqual(parsed, green_receipt())
        self.assertIsInstance(parsed["launchTime"], float)

    def test_invalid_receipt_text_is_rejected_with_stable_codes(self):
        self.assert_receipt_error("not json", "receipt-not-json")
        self.assert_receipt_error("[43380, 64486]", "receipt-not-object")
        for port in ("64486", 0, 65536, True):
            self.assert_receipt_error(self.receipt_text(port=port), "receipt-port-invalid")
        for pid in ("43380", 0, True):
            self.assert_receipt_error(self.receipt_text(pid=pid), "receipt-pid-invalid")
        for sha in ("A" * 64, "a" * 63, "", None):
            self.assert_receipt_error(self.receipt_text(executableSHA256=sha), "receipt-sha-invalid")
        for launch_time in (0, -1, "834721.5", float("nan"), False):
            self.assert_receipt_error(self.receipt_text(launchTime=launch_time), "receipt-launch-time-invalid")


class LauncherDefaultTests(unittest.TestCase):
    """E2/E3 default launcher must name the real built binary (build-macos.sh
    native_executable=AzhouZCodeStartup). A mistyped default only explodes at
    --execute time, while --plan stays green - so the name is pinned here."""

    def test_cold_and_daily_defaults_name_the_canonical_binary(self):
        self.assertEqual(cold_start.DEFAULT_LAUNCHER.name, "AzhouZCodeStartup")
        self.assertEqual(daily.DEFAULT_LAUNCHER.name, "AzhouZCodeStartup")
        self.assertEqual(cold_start.DEFAULT_LAUNCHER, daily.DEFAULT_LAUNCHER)


class DailyIncrementTests(unittest.TestCase):
    """E3 family 1 (design L5): journal increment grouped by launcherPID."""

    def test_increment_groups_and_slices_only_new_runs(self):
        noise = refused_run_lines(43374) + refused_run_lines(29378, seconds0=5.0)
        good = daily_run_lines(62070, COLD_STAGES)
        increment = daily.parse_journal_increment(noise + good, start_line=len(noise))
        self.assertEqual(increment["problems"], [])
        self.assertEqual(len(increment["groups"]), 1)  # pre-existing runs stay unattributed
        group = increment["groups"][0]
        self.assertEqual(group["launcherPID"], 62070)
        self.assertEqual(group["startLine"], len(noise) + 1)
        self.assertEqual(group["endLine"], len(noise) + len(good))
        verdict = daily.assert_daily_chain(group, increment["problems"])
        self.assertTrue(verdict["passed"], verdict["problems"])
        self.assertEqual(verdict["launcherPID"], 62070)
        whole = daily.parse_journal_increment(noise + good)  # start_line 0 groups every run
        self.assertEqual([item["launcherPID"] for item in whole["groups"]], [43374, 29378, 62070])

    def test_refused_increment_is_red_and_names_the_refusal(self):
        increment = daily.parse_journal_increment(refused_run_lines(29378))
        verdict = daily.assert_daily_chain(increment["groups"][0], increment["problems"])
        self.assertFalse(verdict["passed"])
        self.assertEqual([item["stage"] for item in verdict["refusals"]], ["zcode-runtime-failed"])
        self.assertTrue(any("refusal events" in problem for problem in verdict["problems"]))

    def test_nonzero_exit_or_missing_stage_is_red(self):
        for stages, outcome, code in ((COLD_STAGES, "startup-ready", 1),
                                      (COLD_STAGES, "activated", 0),
                                      (COLD_STAGES[:-1], "startup-ready", 0)):
            verdict = daily.assert_daily_chain(
                only_group(daily_run_lines(62070, stages, outcome=outcome, exit_code=code)))
            self.assertFalse(verdict["passed"], (stages, outcome, code))
        missing = daily.assert_daily_chain(only_group(daily_run_lines(62070, COLD_STAGES[:-1])))
        self.assertEqual(missing["missing"], ["startup-ready"])


class FourWayAuditTests(unittest.TestCase):
    """E3 family 2 (P6.2/P6.1): receipt, lsof, process and DOM skin must agree."""

    def test_consistent_sides_are_green(self):
        verdict = daily.audit_four_way(receipt=green_receipt(), lsof_lines=[lsof_row()],
                                       process={"pid": TARGET_PID, "alive": True}, probe=green_probe())
        self.assertTrue(verdict["passed"], verdict["problems"])
        self.assertEqual(verdict["sides"], {"receipt": "ok", "lsof": "ok", "process": "ok", "domSkin": "ok"})
        self.assertFalse(verdict["trapState"])
        self.assertIsNone(verdict["advice"])

    def test_trap_state_receipt_without_skin_is_red_with_cold_restart_advice(self):
        probe = green_probe()
        probe["entry"] = {"found": False, "shadowRoot": False, "reason": "host-not-in-light-dom"}
        verdict = daily.audit_four_way(receipt=green_receipt(), lsof_lines=[lsof_row()],
                                       process={"pid": TARGET_PID, "alive": True}, probe=probe)
        self.assertFalse(verdict["passed"])
        self.assertTrue(verdict["trapState"])
        self.assertEqual(verdict["sides"]["domSkin"], "absent")
        self.assertIn("Quit ZCode", verdict["advice"])
        self.assertTrue(any(problem == daily.TRAP_STATE_ADVICE for problem in verdict["problems"]))

    def test_inconsistent_or_missing_sides_are_red(self):
        verdict = daily.audit_four_way(receipt=green_receipt(), lsof_lines=[lsof_row(pid=62079)],
                                       process={"pid": TARGET_PID, "alive": True}, probe=green_probe())
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["sides"]["lsof"], "inconsistent")
        self.assertTrue(any("held by pid" in problem for problem in verdict["problems"]))
        verdict = daily.audit_four_way(receipt=green_receipt(), lsof_lines=[lsof_row()],
                                       process={"pid": TARGET_PID, "alive": False}, probe=green_probe())
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["sides"]["process"], "dead")
        self.assertFalse(verdict["trapState"])
        verdict = daily.audit_four_way(receipt=None, receipt_problem="receipt invalid: receipt-not-json",
                                       lsof_lines=[], process=None, probe=None)
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["sides"]["receipt"], "missing")
        self.assertTrue(any("receipt invalid: receipt-not-json" in problem for problem in verdict["problems"]))


class IdempotentSecondClickTests(unittest.TestCase):
    """E3 family 3 (P7.1 daily face): the second click only activates."""

    def test_second_click_activates_without_replay_is_green(self):
        first = only_group(daily_run_lines(62070, COLD_STAGES))
        second = only_group(daily_run_lines(64502, HOT_STAGES, outcome="activated"))
        verdict = daily.assert_idempotent_second_click(first, second,
                                                       receipt_before=green_receipt(),
                                                       receipt_after=green_receipt())
        self.assertTrue(verdict["passed"], verdict["problems"])
        self.assertEqual(verdict["injectionReplay"], [])
        self.assertFalse(verdict["receiptRewritten"])
        self.assertEqual(verdict["second"]["exits"], [{"outcome": "activated", "exitCode": 0}])

    def test_second_click_replaying_injection_is_red(self):
        first = only_group(daily_run_lines(62070, COLD_STAGES))
        replayed = only_group(daily_run_lines(64502, COLD_STAGES))  # a full cold rerun
        verdict = daily.assert_idempotent_second_click(first, replayed)
        self.assertFalse(verdict["passed"])
        self.assertIn("zcode-open-request", verdict["injectionReplay"])
        self.assertIn("startup-ready", verdict["injectionReplay"])
        self.assertTrue(any("replayed injection stages" in problem for problem in verdict["problems"]))
        self.assertFalse(verdict["second"]["passed"])  # outcome startup-ready != activated

    def test_second_click_bad_exit_or_receipt_rewrite_is_red(self):
        first = only_group(daily_run_lines(62070, COLD_STAGES))
        second = only_group(daily_run_lines(64502, HOT_STAGES, outcome="activated", exit_code=1))
        verdict = daily.assert_idempotent_second_click(first, second)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("exitCode" in problem for problem in verdict["second"]["problems"]))
        rewritten = {**green_receipt(), "pid": 62079}
        verdict = daily.assert_idempotent_second_click(first, second,
                                                       receipt_before=green_receipt(), receipt_after=rewritten)
        self.assertTrue(verdict["receiptRewritten"])
        self.assertTrue(any("receipt was rewritten" in problem for problem in verdict["receiptProblems"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
