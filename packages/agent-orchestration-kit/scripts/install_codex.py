#!/usr/bin/env python3
"""Transactional, user-scoped Codex installation. Python 3.11+, stdlib only."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- ASTRA-LUNA-ORCHESTRATOR:BEGIN -->"
END = "<!-- ASTRA-LUNA-ORCHESTRATOR:END -->"
PROFILE = "azhou-balanced"
ROLE_MODELS = {
    "explorer": ("gpt-6-luna", "max"),
    "worker": ("gpt-6-luna", "max"),
    "tester": ("gpt-6-luna", "max"),
    "researcher": ("gpt-6-luna", "max"),
    "reviewer": ("gpt-6.1-sol", "high"),
    "astra-specialist": ("gpt-6-astra", "medium"),
}
SETTINGS = {
    "model": "gpt-6.1-sol",
    "model_reasoning_effort": "high",
    "service_tier": "default",
    "agents.enabled": True,
    "agents.max_concurrent_threads_per_session": 4,
    "agents.default_subagent_model": "gpt-6-luna",
    "agents.default_subagent_reasoning_effort": "max",
}
MANAGED = tuple(SETTINGS) + ("agents.max_threads",)


class InstallError(Exception):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def lookup(doc, key):
    node = doc
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return {"present": False}
        node = node[part]
    return {"present": True, "value": node}


def set_value(doc, key, value):
    parts = key.split(".")
    node = doc
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise InstallError(f"Conflicting table for {key}")
    if value["present"]:
        node[parts[-1]] = value["value"]
    else:
        node.pop(parts[-1], None)


def statements(text):
    """Locate TOML statements without rewriting any unrelated text.

    tomllib remains the semantic parser. This scanner only tracks statement
    boundaries (including multiline strings/arrays) for lossless scalar edits.
    """
    start = i = depth = 0
    quote = None
    comment = False
    while i < len(text):
        c = text[i]
        if comment:
            if c == "\n":
                comment = False
            else:
                i += 1
                continue
        elif quote:
            if quote[0] == '"' and c == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                i += len(quote)
                if len(quote) == 3:
                    while i < len(text) and text[i] == quote[0]:
                        i += 1
                quote = None
                continue
            i += 1
            continue
        elif c in "\"'":
            quote = c * 3 if text.startswith(c * 3, i) else c
            i += len(quote)
            continue
        elif c == "#":
            comment = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        if c == "\n" and depth == 0:
            yield start, i + 1, text[start:i + 1]
            start = i + 1
        i += 1
    if start < len(text):
        yield start, len(text), text[start:]


def leaf_paths(doc, prefix=()):
    if isinstance(doc, dict):
        for key, value in doc.items():
            yield from leaf_paths(value, prefix + (key,))
    else:
        yield prefix


def outside_position(text, target):
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if quote == '"' and c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == target:
            return i
        i += 1
    return len(text)


def merge_config(text, settings=SETTINGS):
    """Parse, edit only owned scalars, and independently reparse the result."""
    before = tomllib.loads(text)
    expected = copy.deepcopy(before)
    for key in MANAGED:
        set_value(expected, key, {"present": key in settings, "value": settings.get(key)})
    section = ()
    array_table = False
    found = {}
    edits = []
    agents_insert = None
    root_end = len(text)
    dotted_agents = False
    for start, end, statement in statements(text):
        body = statement.strip()
        if not body or body.startswith("#"):
            continue
        if body.startswith("["):
            root_end = min(root_end, start)
            array_table = body.startswith("[[")
            # Header names may be quoted and contain dots; tomllib decodes them.
            stop = outside_position(body, "#")
            header = body[:stop].strip()
            key = header[2:-2] if array_table else header[1:-1]
            decoded = tomllib.loads(key + " = 0")
            section = next(leaf_paths(decoded))
            if section == ("agents",) and not array_table:
                agents_insert = end
            continue
        parsed = tomllib.loads(statement)
        paths = list(leaf_paths(parsed))
        for relative in paths:
            path = ".".join(section + relative)
            if path not in MANAGED:
                continue
            if array_table or len(paths) != 1:
                raise InstallError(f"Use ordinary scalar/table syntax for owned setting {path}; no files written")
            # Inline tables with a single leaf are still aggregate assignments.
            eq = outside_position(statement, "=")
            key_doc = tomllib.loads(statement[:eq].strip() + " = 0")
            if next(leaf_paths(key_doc)) != relative:
                raise InstallError(f"Inline table contains owned setting {path}; expand it before installing")
            if path in found:
                raise InstallError(f"Ambiguous owned setting {path}")
            found[path] = True
            dotted_agents |= not section and relative[0] == "agents"
            if path not in settings:
                pos = outside_position(statement, "#")
                replacement = statement[pos:] if pos < len(statement) else ""
                edits.append((start, end, replacement))
            elif lookup(before, path) != {"present": True, "value": settings[path]}:
                pos = outside_position(statement, "#")
                value_end = len(statement[:pos].rstrip())
                value_start = eq + 1
                while value_start < value_end and statement[value_start].isspace():
                    value_start += 1
                edits.append((start + value_start, start + value_end, json.dumps(settings[path])))
    for key in MANAGED:
        if lookup(before, key)["present"] and key not in found:
            raise InstallError(f"Cannot losslessly locate owned setting {key}; no files written")
    missing_root = [k for k in settings if "." not in k and k not in found]
    missing_agents = [k for k in settings if k.startswith("agents.") and k not in found]
    newline = "\r\n" if "\r\n" in text else "\n"
    root_add = "".join(f"{k} = {json.dumps(settings[k])}{newline}" for k in missing_root)
    if agents_insert is None and dotted_agents:
        root_add += "".join(f"{k} = {json.dumps(settings[k])}{newline}" for k in missing_agents)
    elif missing_agents:
        block = "".join(f"{k.split('.', 1)[1]} = {json.dumps(settings[k])}{newline}" for k in missing_agents)
        if agents_insert is None:
            separator = "" if not text or text.endswith("\n") else newline
            edits.append((len(text), len(text), separator + newline + "[agents]" + newline + block))
        else:
            edits.append((agents_insert, agents_insert, block))
    if root_add:
        if root_end and text[root_end - 1:root_end] != "\n":
            root_add = newline + root_add
        edits.append((root_end, root_end, root_add))
    for start, end, replacement in sorted(edits, key=lambda item: (item[0], item[1]), reverse=True):
        text = text[:start] + replacement + text[end:]
    if tomllib.loads(text) != expected:
        raise InstallError("Merged TOML did not preserve unrelated configuration")
    return text


def owned_block(text):
    if not text.count(BEGIN) and not text.count(END):
        return None
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
        raise InstallError("Malformed or repeated orchestration instruction markers")
    return text[text.index(BEGIN):text.index(END) + len(END)]


def regular_bytes(path):
    if path.is_symlink():
        raise InstallError(f"Refusing symbolic link at managed path: {path}")
    if path.exists():
        if not path.is_file():
            raise InstallError(f"Expected regular file: {path}")
        return path.read_bytes()
    return None


def check_parents(path):
    for parent in path.parents:
        if parent.is_symlink():
            # Canonical system paths (/var -> /private/var on macOS) are resolved
            # by the caller. User-owned symlinks must be reviewed explicitly.
            raise InstallError(f"Symbolic link in installation path: {parent}")
        if parent.exists() and not parent.is_dir():
            raise InstallError(f"Expected directory: {parent}")


def source_files(root):
    profile = root / "profiles" / PROFILE
    def read_source(path):
        check_parents(path)
        raw = regular_bytes(path)
        if raw is None:
            raise InstallError(f"Missing source file: {path}")
        return raw
    config = tomllib.loads(read_source(profile / "codex/config.toml").decode())
    expected_config = {}
    for key, value in SETTINGS.items():
        set_value(expected_config, key, {"present": True, "value": value})
    if config != expected_config:
        raise InstallError("azhou-balanced defaults do not match the supported model contract")
    roles = profile / "codex/agents"
    if {p.stem for p in roles.glob("*.toml")} != set(ROLE_MODELS):
        raise InstallError("Missing or unexpected source role files")
    files = {}
    for name, (model, effort) in ROLE_MODELS.items():
        path = roles / f"{name}.toml"
        raw = read_source(path)
        role = tomllib.loads(raw.decode())
        if (role.get("name"), role.get("model"), role.get("model_reasoning_effort")) != (name, model, effort):
            raise InstallError(f"Invalid source role: {name}")
        if not role.get("description") or not role.get("developer_instructions"):
            raise InstallError(f"Incomplete source role: {name}")
        if any(k in role for k in ("sandbox_mode", "approval_policy", "model_provider", "mcp_servers")):
            raise InstallError(f"Unsupported session-level setting in source role: {name}")
        files[f"agents/{name}.toml"] = raw
    files["skill"] = read_source(profile / "agents/skills/astra-orchestrator/SKILL.md")
    frontmatter = re.match(rb"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", files["skill"], re.S)
    if not frontmatter or not re.search(rb"(?m)^name:\s*astra-orchestrator\s*$", frontmatter[1]) or not re.search(rb"(?m)^description:\s*\S", frontmatter[1]):
        raise InstallError("Missing or invalid astra-orchestrator Skill")
    instructions = read_source(profile / "AGENTS.md").decode()
    block = owned_block(instructions)
    if block is None or block.strip() != instructions.strip():
        raise InstallError("Source instructions must contain exactly the managed block")
    files["instructions"] = block.encode()
    legacy = json.loads(read_source(profile / "legacy-hashes.json"))["files"]
    return files, legacy


def build_plan(root, codex_home, skills_dir):
    """Preflight only: reads files and returns a fully reviewable write plan."""
    files, legacy = source_files(root)
    config_path = codex_home / "config.toml"
    instructions_path = codex_home / "AGENTS.md"
    state_path = codex_home / "agent-orchestration-kit/state.json"
    transaction = codex_home / ".agent-orchestration-kit-transaction"
    if transaction.exists() or transaction.is_symlink():
        raise InstallError(f"Unfinished transaction at {transaction}; inspect it and run --recover with the same target paths")
    targets = {key: codex_home / key for key in files if key.startswith("agents/")}
    targets["skill"] = skills_dir / "astra-orchestrator/SKILL.md"
    for path in [config_path, instructions_path, state_path, *targets.values()]:
        check_parents(path)
        regular_bytes(path)
    raw_config = regular_bytes(config_path)
    text = raw_config.decode() if raw_config is not None else ""
    config = tomllib.loads(text)
    raw_state = regular_bytes(state_path)
    state = json.loads(raw_state) if raw_state else None
    if state and (state.get("schema") != 1 or state.get("project") != "agent-orchestration-kit"):
        raise InstallError("Unrecognized installation ownership record")
    if state and state.get("targets") != {k: str(v) for k, v in targets.items()}:
        raise InstallError("Installed target paths changed; inspect the ownership record before migration")
    if state:
        for key, value in state["applied_config"].items():
            if lookup(config, key) != value:
                raise InstallError(f"User-modified owned configuration: {key}")
    # The actual name inside TOML, not the filename, controls role identity.
    role_dir = codex_home / "agents"
    if role_dir.exists():
        for path in role_dir.rglob("*.toml"):
            if not path.is_file():
                raise InstallError(f"Invalid role file type: {path}")
            role = tomllib.loads(regular_bytes(path).decode())
            name = role.get("name")
            if name in ROLE_MODELS and path != targets[f"agents/{name}.toml"]:
                raise InstallError(f"Role name collision: {name} is defined in {path}")
    for key in ROLE_MODELS:
        if key in config.get("agents", {}):
            raise InstallError(f"Legacy inline role conflicts with standalone role: agents.{key}")
    for item in config.get("skills", {}).get("config", []):
        if item.get("enabled") is False and Path(item.get("path", "")).expanduser().resolve() == targets["skill"].resolve():
            raise InstallError("The installed Skill is explicitly disabled in personal configuration")
    changes = {}
    watched = {}
    hashes = {}
    adopted = state.get("adopted_existing", []) if state else []
    for key, path in targets.items():
        before = regular_bytes(path)
        desired = files[key]
        digest = sha(before) if before is not None else None
        if state:
            if digest != state["files"].get(key):
                raise InstallError(f"User-modified or missing installed file: {path}")
        elif before is not None:
            if digest not in (sha(desired), legacy.get(key)):
                raise InstallError(f"Unowned or modified file would be overwritten: {path}")
            adopted.append(key)
        hashes[key] = sha(desired)
        watched[path] = before
        if before != desired:
            changes[path] = desired
    before_instructions = regular_bytes(instructions_path)
    instructions = before_instructions.decode() if before_instructions is not None else ""
    block = owned_block(instructions)
    if state:
        if block is None or sha(block.encode()) != state["files"].get("instructions"):
            raise InstallError("User-modified or missing installed instruction block")
    elif block is not None and sha(block.encode()) not in (sha(files["instructions"]), legacy.get("instructions")):
        raise InstallError("Unowned or modified instruction block")
    desired_block = files["instructions"].decode()
    if block is not None:
        result = instructions.replace(block, desired_block, 1)
    else:
        separator = "\n\n" if instructions else ""
        result = instructions + separator + desired_block + "\n"
    hashes["instructions"] = sha(files["instructions"])
    merged = merge_config(text).encode()
    watched.update({config_path: raw_config, instructions_path: before_instructions, state_path: raw_state})
    if merged != raw_config:
        changes[config_path] = merged
    if result.encode() != before_instructions:
        changes[instructions_path] = result.encode()
    original = state["original_config"] if state else {k: lookup(config, k) for k in MANAGED}
    manifest = {
        "schema": 1,
        "project": "agent-orchestration-kit",
        "profile": PROFILE,
        "source_digest": sha(b"".join(k.encode() + b"\0" + files[k] for k in sorted(files))),
        "targets": {k: str(v) for k, v in targets.items()},
        "files": hashes,
        "applied_config": {k: {"present": k in SETTINGS, "value": SETTINGS[k]} if k in SETTINGS else {"present": False} for k in MANAGED},
        "original_config": original,
        "adopted_existing": sorted(adopted),
    }
    if state:
        if "original_instruction_block" in state:
            manifest["original_instruction_block"] = state["original_instruction_block"]
    elif block is not None:
        manifest["original_instruction_block"] = block
    content = json_bytes(manifest)
    if content != raw_state:
        changes[state_path] = content
    return {"changes": changes, "watched": watched, "transaction": transaction,
            "config_text": merged.decode(), "roles": {k: files[f"agents/{k}.toml"] for k in ROLE_MODELS},
            "skill_path": targets["skill"], "manifest": manifest}


def atomic_write(path, data, mode=0o600):
    fd, name = tempfile.mkstemp(prefix=".aok-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def missing_directories(paths):
    result = set()
    for path in paths:
        for directory in path.parents:
            if not directory.exists():
                result.add(directory)
    return sorted(result, key=lambda p: len(p.parts))


def restore(journal, transaction):
    # Refuse to clobber edits made by a different actor since our write.
    for item in journal["files"]:
        current = regular_bytes(Path(item["path"]))
        original = base64.b64decode(item["before"]) if item["before"] is not None else None
        if current != original and (current is None or sha(current) != item["after_sha256"]):
            raise InstallError(f"Concurrent edit prevents automatic rollback: {item['path']}; recovery journal retained")
    for item in reversed(journal["files"]):
        path = Path(item["path"])
        before = base64.b64decode(item["before"]) if item["before"] is not None else None
        if before is None:
            if path.exists():
                path.unlink()
        elif regular_bytes(path) != before:
            atomic_write(path, before, item["mode"])
    shutil.rmtree(transaction)
    for directory in reversed(journal["created_directories"]):
        try:
            Path(directory).rmdir()
        except OSError:
            pass


def apply_plan(plan, verify=lambda: None, write=atomic_write):
    """Commit all changed files, or restore exact originals on failure.

    `write` and `verify` are injected by independent fault tests. A temporary
    journal survives abnormal termination; a successful run removes it.
    """
    for path, before in plan["watched"].items():
        check_parents(path)
        if regular_bytes(path) != before:
            raise InstallError(f"File changed after preflight: {path}")
    if not plan["changes"]:
        verify()
        return 0
    tx = plan["transaction"]
    dirs = missing_directories([*plan["changes"], tx / "journal.json"])
    # Create the target root only after every read-only preflight passed.
    tx.parent.mkdir(parents=True, exist_ok=True)
    try:
        tx.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise InstallError(f"Another installation or recovery transaction exists: {tx}") from exc
    journal = {"schema": 1, "created_directories": [str(p) for p in dirs if p != tx], "files": []}
    for path, desired in plan["changes"].items():
        original = plan["watched"][path]
        journal["files"].append({"path": str(path), "before": base64.b64encode(original).decode() if original is not None else None,
                                 "mode": stat.S_IMODE(path.stat().st_mode) if original is not None else 0o600,
                                 "after_sha256": sha(desired)})
    try:
        atomic_write(tx / "journal.json", json_bytes(journal))
        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)
        for item in journal["files"]:
            path = Path(item["path"])
            check_parents(path)
            if regular_bytes(path) != plan["watched"][path]:
                raise InstallError(f"File changed during installation: {path}")
            write(path, plan["changes"][path], item["mode"])
        verify()
    except BaseException as exc:
        try:
            restore(journal, tx)
        except BaseException as rollback_error:
            raise InstallError(f"Install failed ({exc}); rollback needs attention: {rollback_error}") from exc
        raise InstallError(f"Install failed; all touched files restored: {exc}") from exc
    shutil.rmtree(tx)
    return len(plan["changes"])


def recover(codex_home, skills_dir):
    tx = codex_home / ".agent-orchestration-kit-transaction"
    check_parents(tx / "journal.json")
    data = regular_bytes(tx / "journal.json")
    if data is None:
        raise InstallError("No readable recovery journal exists")
    journal = json.loads(data)
    allowed = {codex_home / "config.toml", codex_home / "AGENTS.md", codex_home / "agent-orchestration-kit/state.json", skills_dir / "astra-orchestrator/SKILL.md"}
    allowed.update(codex_home / f"agents/{name}.toml" for name in ROLE_MODELS)
    if journal.get("schema") != 1 or any(Path(item["path"]) not in allowed for item in journal["files"]):
        raise InstallError("Recovery journal contains an unexpected target; inspect manually")
    allowed_dirs = {p for target in allowed for p in target.parents if p != Path(p.anchor)}
    if any(Path(p) not in allowed_dirs for p in journal["created_directories"]):
        raise InstallError("Unexpected recovery directory; inspect manually")
    restore(journal, tx)


def main():
    parser = argparse.ArgumentParser(description="Install agent-orchestration-kit's azhou-balanced Codex profile for this user")
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--skills-dir", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--codex-bin", help="Explicit Codex runtime; default prefers the macOS App runtime")
    parser.add_argument("--dry-run", action="store_true", help="Run preflight and print changes without installing")
    parser.add_argument("--recover", action="store_true", help="Restore a retained interrupted transaction, then exit")
    args = parser.parse_args()
    try:
        # Reject user symlinks before canonicalizing macOS system path aliases.
        for raw in [args.codex_home, args.skills_dir]:
            if raw.is_symlink() or raw.parent.is_symlink():
                raise InstallError(f"Review symbolic installation root before installing: {raw}")
        codex_home = args.codex_home.expanduser().absolute().resolve()
        skills_dir = args.skills_dir.expanduser().absolute().resolve()
        if args.recover:
            recover(codex_home, skills_dir)
            print("Interrupted installation restored. Re-run ./setup.sh when ready.")
            return 0
        from codex_native import select_runtime, preflight_runtime, validate_config, verify_native
        runtime = select_runtime(args.codex_bin)
        preflight_runtime(runtime)
        plan = build_plan(ROOT, codex_home, skills_dir)
        validate_config(runtime, plan["config_text"], plan["roles"])
        print(json.dumps({"profile": PROFILE, "runtime": runtime, "codex_home": str(codex_home),
                          "skill": str(plan["skill_path"]), "changed_files": [str(p) for p in plan["changes"]]}, indent=2))
        if args.dry_run:
            print("Preflight passed; no target files written.")
            return 0
        evidence = {}
        def verify():
            evidence.update(verify_native(runtime, codex_home, ROOT, ROLE_MODELS, plan["skill_path"], SETTINGS))
        count = apply_plan(plan, verify)
        print(json.dumps({"changed_files_count": count, "native_discovery": evidence}, indent=2))
        print("Installed. Defaults apply to new Codex sessions; active sessions and their permissions are unchanged.")
        print("Read-only role instructions are behavioral; native permissions are inherited from the parent session.")
        return 0
    except (InstallError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
