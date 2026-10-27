#!/usr/bin/env python3
"""Native, non-inference Codex validation and discovery (stdlib only)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import re
import select
import shutil
import subprocess
import tempfile
import time
import tomllib


def run(command, *, cwd=None, env=None, timeout=30):
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Native Codex command could not finish: {' '.join(command[:3])}") from exc
    if result.returncode:
        # Do not print full config or diagnostics that might contain credentials.
        raise RuntimeError(f"Native Codex command failed ({result.returncode}): {' '.join(command[:3])}; inspect the selected runtime/config")
    return result.stdout


def version(path):
    text = run([str(path), "--version"], timeout=10).strip()
    if not re.fullmatch(r"codex-cli \d+\.\d+\.\d+[^\s]*", text):
        raise RuntimeError(f"Not a recognized Codex executable: {path}")
    return text


def select_runtime(explicit=None):
    path_bin = shutil.which("codex")
    alternative = None
    if path_bin:
        try:
            path_version = version(path_bin)
        except RuntimeError:
            path_version = "unrecognized or unavailable (not selected automatically when an App exists)"
        alternative = {"path": str(Path(path_bin).resolve()), "version": path_version}
    if explicit:
        selected = shutil.which(explicit) if os.sep not in explicit else explicit
        if not selected or not Path(selected).is_file() or not os.access(selected, os.X_OK):
            raise RuntimeError(f"Selected Codex executable is missing or not executable: {explicit}")
        selected, source = Path(selected).resolve(), "explicit"
    else:
        apps = []
        for parent in (Path("/Applications"), Path.home() / "Applications"):
            for name in ("ChatGPT.app", "Codex.app"):
                bundle = parent / name
                info = bundle / "Contents/Info.plist"
                if not info.is_file():
                    continue
                with info.open("rb") as stream:
                    metadata = plistlib.load(stream)
                if metadata.get("CFBundleIdentifier") != "com.openai.codex":
                    continue
                binary = bundle / "Contents/Resources/codex-cli/bin/codex"
                if binary.is_file() and os.access(binary, os.X_OK):
                    apps.append(binary.resolve())
        apps = list(dict.fromkeys(apps))
        if len(apps) > 1:
            raise RuntimeError("Multiple Codex App runtimes found; select one explicitly with --codex-bin")
        if apps:
            selected, source = apps[0], "macos-app"
        elif path_bin:
            selected, source = Path(path_bin).resolve(), "PATH"
        else:
            raise RuntimeError("No Codex App or PATH runtime found; install Codex or pass --codex-bin")
    return {"path": str(selected), "version": version(selected), "source": source, "path_runtime": alternative}


def preflight_runtime(runtime):
    binary = runtime["path"]
    help_text = run([binary, "app-server", "--help"])
    if "--print-startup-config" not in help_text or "--stdio" not in help_text:
        raise RuntimeError("The selected Codex runtime lacks required native config/discovery capabilities")
    run([binary, "debug", "prompt-input", "--help"])


def native_env(codex_home):
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    return env


def validate_config(runtime, config_text, role_files=None):
    # The host parses a staged candidate, never the live target during preflight.
    parsed = tomllib.loads(config_text)
    with tempfile.TemporaryDirectory(prefix="aok-native-preflight-") as name:
        directory = Path(name).resolve()
        (directory / "config.toml").write_text(config_text)
        if role_files:
            (directory / "agents").mkdir()
            for role, raw in role_files.items():
                if not re.fullmatch(r"[a-z][a-z0-9-]*", role):
                    raise RuntimeError("Invalid staged role name")
                (directory / "agents" / f"{role}.toml").write_bytes(raw)
        # --print-startup-config only reports requirements in the tested build.
        # Use real config/read and the rendered spawn schema instead.
        with NativeReader(runtime, directory, directory) as reader:
            result = reader.request("config/read", {"cwd": str(directory), "includeLayers": False})["config"]
            keys = ("model", "model_reasoning_effort", "service_tier", "agents.enabled",
                    "agents.max_concurrent_threads_per_session", "agents.default_subagent_model",
                    "agents.default_subagent_reasoning_effort")
            if any(get_value(result, key) != get_value(parsed, key) for key in keys):
                raise RuntimeError("Native staged configuration differs from the candidate settings")
        if role_files:
            expected = {}
            for role, raw in role_files.items():
                data = tomllib.loads(raw.decode())
                expected[role] = (data["model"], data["model_reasoning_effort"])
            prompt = json.loads(run([runtime["path"], "debug", "prompt-input", "Staged role validation only."],
                                    cwd=directory, env=native_env(directory), timeout=45))
            role_evidence(prompt, expected)


class NativeReader:
    """A private stdio app-server. Never attaches to the user's active daemon."""
    def __init__(self, runtime, codex_home, cwd):
        self.errors = tempfile.TemporaryFile()
        self.process = subprocess.Popen([runtime["path"], "app-server", "--stdio"],
                                        cwd=cwd, env=native_env(codex_home), stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.errors, bufsize=0)
        self.buffer = b""
        self.sequence = 0

    def request(self, method, params):
        self.sequence += 1
        ident = self.sequence
        self.process.stdin.write((json.dumps({"id": ident, "method": method, "params": params}) + "\n").encode())
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("id") != ident:
                    continue
                if "error" in event:
                    raise RuntimeError(f"Native {method} failed with code {event['error'].get('code')}")
                return event.get("result")
            ready, _, _ = select.select([self.process.stdout], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                break
            data = os.read(self.process.stdout.fileno(), 65536)
            if not data:
                raise RuntimeError(f"Native app-server exited while reading {method}")
            self.buffer += data
        raise RuntimeError(f"Native {method} timed out; no model request was sent")

    def __enter__(self):
        try:
            self.request("initialize", {"clientInfo": {"name": "agent_orchestration_kit", "version": "1"},
                                        "capabilities": {"experimentalApi": True}})
            self.process.stdin.write(b'{"method":"initialized"}\n')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process.stdout.close()
        self.errors.close()


def get_value(config, dotted):
    node = config
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def role_evidence(prompt, expected_roles):
    descriptions = []
    def walk(node):
        if isinstance(node, dict):
            agent_type = node.get("properties", {}).get("agent_type", {})
            if isinstance(agent_type, dict) and "Available roles:" in agent_type.get("description", ""):
                descriptions.append(agent_type["description"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    for item in prompt:
        if item.get("type") == "additional_tools" and item.get("role") == "developer":
            walk(item.get("tools", []))
    if len(descriptions) != 1:
        raise RuntimeError("Native prompt lacks an unambiguous agent_type tool schema")
    roles = []
    for name, (model, effort) in expected_roles.items():
        blocks = re.findall(r"(?ms)^" + re.escape(name) + r": \{\n(.*?)^\}", descriptions[0])
        if len(blocks) != 1 or f"model is set to `{model}`" not in blocks[0] or f"reasoning effort is set to `{effort}`" not in blocks[0]:
            raise RuntimeError(f"Native prompt does not expose the expected named role: {name}")
        roles.append({"name": name, "model": model, "reasoning_effort": effort,
                      "evidence": "native debug prompt-input agent_type tool schema"})
    return roles


def verify_native(runtime, codex_home, cwd, expected_roles, expected_skill_path, expected_config):
    with NativeReader(runtime, codex_home, cwd) as reader:
        config = reader.request("config/read", {"cwd": str(cwd), "includeLayers": False})["config"]
        observed = {key: get_value(config, key) for key in expected_config}
        if observed != expected_config:
            mismatches = [key for key in expected_config if observed[key] != expected_config[key]]
            raise RuntimeError("Native configuration differs from the installation: " + ", ".join(mismatches))
        result = reader.request("skills/list", {"cwds": [str(cwd)], "forceReload": True})
        matches = [skill for entry in result["data"] for skill in entry["skills"]
                   if skill["name"] == "astra-orchestrator"]
        matching = [skill for skill in matches if Path(skill["path"]).resolve() == expected_skill_path.resolve()]
        if len(matches) != 1 or len(matching) != 1 or not matching[0]["enabled"]:
            raise RuntimeError("Native Skill discovery is missing, disabled, or ambiguous")
        skill = {key: matching[0][key] for key in ("name", "path", "scope", "enabled")}
    # This native debug command renders the prompt; it does not invoke a model.
    prompt = json.loads(run([runtime["path"], "debug", "prompt-input", "Installation discovery only."],
                            cwd=cwd, env=native_env(codex_home), timeout=45))
    roles = role_evidence(prompt, expected_roles)
    if "<!-- ASTRA-LUNA-ORCHESTRATOR:BEGIN -->" not in json.dumps(prompt):
        raise RuntimeError("The native prompt did not load the installed instruction block")
    return {"config_read": observed, "roles": roles, "skill": skill, "instruction_block_loaded": True,
            "inference_requests": 0, "permission_semantics": "subagents inherit parent permissions"}
