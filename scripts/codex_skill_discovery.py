"""Read the Codex skill catalog for an explicitly selected project."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TypedDict


class SkillEntry(TypedDict):
    name: str
    path: str
    scope: str
    enabled: bool


class DiscoveryError(RuntimeError):
    """Codex could not provide usable discovery evidence."""


async def _receive(process: asyncio.subprocess.Process, request_id: int) -> dict:
    assert process.stdout is not None
    while line := await process.stdout.readline():
        reply = json.loads(line)
        if not isinstance(reply, dict):
            raise DiscoveryError("Codex returned an invalid protocol message")
        if reply.get("id") == request_id:
            result = reply.get("result")
            if not isinstance(result, dict):
                raise DiscoveryError("Codex rejected the discovery request or returned an invalid result")
            return result
    raise DiscoveryError("Codex closed the connection before returning discovery results")


async def _catalog(project: Path) -> dict:
    process = await asyncio.create_subprocess_exec(
        "codex", "app-server", "--stdio", cwd=project,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=2 * 1024 * 1024,
    )
    assert process.stdin is not None

    async def send(message: dict) -> None:
        process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        await process.stdin.drain()

    try:
        async with asyncio.timeout(10):
            await send({
                "id": 1, "method": "initialize",
                "params": {"clientInfo": {"name": "azhou-hub-doctor", "version": "1"}},
            })
            await _receive(process, 1)
            await send({"method": "initialized"})
            await send({
                "id": 2, "method": "skills/list",
                "params": {"cwds": [str(project)], "forceReload": True},
            })
            return await _receive(process, 2)
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.communicate()


def read_skills(project: Path, names: set[str]) -> list[SkillEntry]:
    try:
        result = asyncio.run(_catalog(project))
    except FileNotFoundError as exc:
        raise DiscoveryError("Codex CLI is unavailable. Make the codex executable available in this terminal.") from exc
    except TimeoutError as exc:
        raise DiscoveryError("Codex did not return its skill catalog within 10 seconds.") from exc
    except (OSError, ValueError) as exc:
        raise DiscoveryError("Could not read the Codex skill catalog.") from exc

    rows = result.get("data")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise DiscoveryError("Codex did not return a catalog for the requested project.")
    row = rows[0]
    if row.get("cwd") != str(project) or not isinstance(row.get("skills"), list):
        raise DiscoveryError("Codex returned a catalog for an unexpected project.")
    if row.get("errors") and not row["skills"]:
        raise DiscoveryError("Codex reported catalog errors and returned no skills.")

    entries: list[SkillEntry] = []
    for skill in row["skills"]:
        if not isinstance(skill, dict) or not isinstance(skill.get("name"), str):
            raise DiscoveryError("Codex returned an invalid skill entry.")
        if skill["name"] not in names:
            continue
        path, scope, enabled = skill.get("path"), skill.get("scope"), skill.get("enabled")
        if not isinstance(path, str) or not Path(path).is_absolute() or not isinstance(scope, str) or not isinstance(enabled, bool):
            raise DiscoveryError("Codex returned an invalid path, scope, or enabled state.")
        entries.append(SkillEntry(name=skill["name"], path=path, scope=scope, enabled=enabled))
    if row.get("errors") and names.difference(entry["name"] for entry in entries):
        raise DiscoveryError("Codex reported catalog errors. Missing entries could not be verified.")
    return entries
