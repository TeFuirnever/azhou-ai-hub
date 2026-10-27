import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "GPT6-SolMax-LunaMax": "max",
    "GPT6-SolMedium-LunaMax": "medium",
}
LUNA_ROLES = ("explorer", "researcher", "tester", "worker")
PREVIOUS_PROFILES = {
    "pro": ("gpt-6-astra", "medium", "max", 4),
    "plus": ("gpt-6-luna", "max", "medium", 4),
    "pro-max-2-subagents": ("gpt-6-astra", "medium", "max", 2),
    "plus-max-2-subagents": ("gpt-6-luna", "max", "medium", 2),
}


class SolProfileTests(unittest.TestCase):
    def test_profile_models_and_roles(self):
        for profile, effort in PROFILES.items():
            with self.subTest(profile=profile):
                directory = ROOT / "profiles" / profile
                config = tomllib.loads((directory / "codex" / "config.toml").read_text())
                self.assertEqual(config["model"], "gpt-6.1-sol")
                self.assertEqual(config["model_reasoning_effort"], effort)
                self.assertEqual(config["sandbox_mode"], "workspace-write")
                self.assertTrue(config["agents"]["enabled"])
                self.assertEqual(config["agents"]["default_subagent_model"], "gpt-6-luna")
                self.assertEqual(config["agents"]["default_subagent_reasoning_effort"], "max")
                self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 4)
                for role in LUNA_ROLES:
                    agent = tomllib.loads(
                        (directory / "codex" / "agents" / f"{role}.toml").read_text()
                    )
                    self.assertEqual(agent["name"], role)
                    self.assertEqual(agent["model"], "gpt-6-luna")
                    self.assertEqual(agent["model_reasoning_effort"], "max")
                    expected_mode = "workspace-write" if role in ("worker", "tester") else "read-only"
                    self.assertEqual(agent["sandbox_mode"], expected_mode)
                reviewer = tomllib.loads(
                    (directory / "codex" / "agents" / "reviewer.toml").read_text()
                )
                self.assertEqual(reviewer["model"], "gpt-6.1-sol")
                self.assertEqual(reviewer["model_reasoning_effort"], effort)
                self.assertEqual(reviewer["sandbox_mode"], "read-only")
                skill = (
                    directory / "agents" / "skills" / "astra-orchestrator" / "SKILL.md"
                ).read_text()
                self.assertIn(f"root: `gpt-6.1-sol` at `{effort}` reasoning", skill)
                self.assertIn(
                    "explorer, worker, tester, researcher: `gpt-6-luna` at `max` reasoning",
                    skill,
                )

    def test_installers_select_profiles(self):
        installers = [("shell", ["sh", str(ROOT / "setup.sh"), "--project"])]
        if shutil.which("pwsh"):
            installers.append(("powershell", ["pwsh", "-NoProfile", "-File", str(ROOT / "setup.ps1")]))
        choices = (
            ("5", "GPT6-SolMax-LunaMax"),
            ("6", "GPT6-SolMedium-LunaMax"),
            ("GPT6-SolMax-LunaMax", "GPT6-SolMax-LunaMax"),
            ("GPT6-SolMedium-LunaMax", "GPT6-SolMedium-LunaMax"),
            ("gpt6-SolMax-LunaMax", "GPT6-SolMax-LunaMax"),
            ("gpt6-SolMedium-LunaMax", "GPT6-SolMedium-LunaMax"),
        )
        for installer, command in installers:
            for choice, profile in choices:
                with self.subTest(installer=installer, choice=choice), tempfile.TemporaryDirectory() as target:
                    result = subprocess.run(
                        command, input=f"{target}\n{choice}\n\n\n\n", text=True, capture_output=True
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("Select Profile [1-7] (default 7):", result.stdout)
                    self.assertIn(f"profile: {profile}", result.stdout)
                    self.assertIn(f") {profile} -", result.stdout)
                    source = ROOT / "profiles" / profile
                    for component in (
                        Path(".codex/config.toml"),
                        Path(".codex/agents/reviewer.toml"),
                        Path(".agents/skills/astra-orchestrator/SKILL.md"),
                    ):
                        source_component = source / component.parts[0][1:]
                        self.assertEqual(
                            (Path(target) / component).read_text(),
                            (source_component / Path(*component.parts[1:])).read_text(),
                        )


class PreviousProfileTests(unittest.TestCase):
    def test_models_and_roles(self):
        for profile, (root_model, root_effort, luna_effort, limit) in PREVIOUS_PROFILES.items():
            with self.subTest(profile=profile):
                directory = ROOT / "profiles" / profile
                config = tomllib.loads((directory / "codex" / "config.toml").read_text())
                self.assertEqual(config["model"], root_model)
                self.assertEqual(config["model_reasoning_effort"], root_effort)
                self.assertEqual(config["agents"]["default_subagent_model"], "gpt-6-luna")
                self.assertEqual(config["agents"]["default_subagent_reasoning_effort"], luna_effort)
                self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], limit)
                for role in LUNA_ROLES:
                    agent = tomllib.loads(
                        (directory / "codex" / "agents" / f"{role}.toml").read_text()
                    )
                    self.assertEqual(agent["model"], "gpt-6-luna")
                    self.assertEqual(agent["model_reasoning_effort"], luna_effort)
                reviewer = tomllib.loads(
                    (directory / "codex" / "agents" / "reviewer.toml").read_text()
                )
                self.assertEqual(reviewer["model"], "gpt-6-astra")
                self.assertEqual(reviewer["model_reasoning_effort"], "low")
                skill = (
                    directory / "agents" / "skills" / "astra-orchestrator" / "SKILL.md"
                ).read_text()
                self.assertNotIn("gpt-5.6-luna", skill)
                self.assertNotIn("GPT-5.6 Luna", skill)
                self.assertIn(f"`gpt-6-luna` at `{luna_effort}` reasoning", skill)

    def test_installers_select_previous_profiles(self):
        installers = [("shell", ["sh", str(ROOT / "setup.sh"), "--project"])]
        if shutil.which("pwsh"):
            installers.append(("powershell", ["pwsh", "-NoProfile", "-File", str(ROOT / "setup.ps1")]))
        for installer, command in installers:
            for choice, profile in enumerate(PREVIOUS_PROFILES, start=1):
                with self.subTest(installer=installer, profile=profile), tempfile.TemporaryDirectory() as target:
                    result = subprocess.run(
                        command, input=f"{target}\n{choice}\n\n\n\n", text=True, capture_output=True
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(f"profile: {profile}", result.stdout)
                    menu_line = next(line for line in result.stdout.splitlines() if line.startswith(f"  {choice}) "))
                    self.assertIn("GPT-6 Luna", menu_line)
                    source = ROOT / "profiles" / profile
                    for component in (
                        Path(".codex/config.toml"),
                        Path(".codex/agents/worker.toml"),
                        Path(".agents/skills/astra-orchestrator/SKILL.md"),
                    ):
                        source_component = source / component.parts[0][1:]
                        self.assertEqual(
                            (Path(target) / component).read_text(),
                            (source_component / Path(*component.parts[1:])).read_text(),
                        )


class BalancedProfileTests(unittest.TestCase):
    def test_balanced_contract(self):
        directory = ROOT / "profiles" / "azhou-balanced"
        config = tomllib.loads((directory / "codex/config.toml").read_text())
        self.assertEqual(config["model"], "gpt-6.1-sol")
        self.assertEqual(config["model_reasoning_effort"], "high")
        self.assertEqual(config["service_tier"], "default")
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 4)
        for role in (*LUNA_ROLES, "reviewer", "astra-specialist"):
            agent = tomllib.loads((directory / "codex/agents" / f"{role}.toml").read_text())
            expected = ("gpt-6-luna", "max") if role in LUNA_ROLES else (("gpt-6.1-sol", "high") if role == "reviewer" else ("gpt-6-astra", "medium"))
            self.assertEqual((agent["model"], agent["model_reasoning_effort"]), expected)
            self.assertEqual(agent["name"], role)
            self.assertNotIn("sandbox_mode", agent)
        self.assertNotIn("/Users/", (directory / "AGENTS.md").read_text())

    def test_balanced_coexistence_rules(self):
        directory = ROOT / "profiles" / "azhou-balanced"
        instructions = (directory / "AGENTS.md").read_text()
        skill = (directory / "agents" / "skills" / "astra-orchestrator" / "SKILL.md").read_text()
        for text in (instructions, skill):
            self.assertIn("that workflow owns the task's decomposition, stages, child dispatch, and verification", text)
            self.assertIn("A status question or an added constraint within the same task keeps", text)
            self.assertIn("returns to these defaults", text)
            self.assertIn("running children to a recoverable boundary", text)
            self.assertIn("no orchestrator chains into another" if text is instructions
                          else "never chains into another orchestrator", text)
        self.assertIn("leave the active root model unchanged", instructions)
        self.assertIn("a selected custom-role file overrides the explicit fields it sets", skill)
        self.assertIn("do not attach a named role to them", skill)

    def test_balanced_project_selection_and_default(self):
        for choice in ("7", "azhou-balanced", ""):
            with self.subTest(choice=choice), tempfile.TemporaryDirectory() as target:
                result = subprocess.run(["sh", str(ROOT / "setup.sh"), "--project"], input=f"{target}\n{choice}\n\n\n\n", text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("profile: azhou-balanced", result.stdout)
                config = tomllib.loads((Path(target) / ".codex/config.toml").read_text())
                self.assertEqual(config["model"], "gpt-6.1-sol")
                self.assertEqual(config["model_reasoning_effort"], "high")
                self.assertTrue((Path(target) / ".codex/agents/astra-specialist.toml").is_file())


if __name__ == "__main__":
    unittest.main()
