"""Direct discovery contracts below the doctor's mocked catalog boundary."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from scripts import codex_skill_discovery as discovery


class CatalogValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        self.entry = {
            "name": "sample",
            "path": str(self.project / "skill space" / "SKILL.md"),
            "scope": "repo",
            "enabled": True,
        }

    def catalog(self, *, skills=None, errors=None, cwd=None):
        return {"data": [{
            "cwd": str(self.project) if cwd is None else cwd,
            "skills": [self.entry] if skills is None else skills,
            "errors": [] if errors is None else errors,
        }]}

    def read(self, catalog):
        with mock.patch.object(discovery, "_catalog", mock.AsyncMock(return_value=catalog)) as probe:
            result = discovery.read_skills(self.project, {"sample"})
        probe.assert_awaited_once_with(self.project)
        return result

    def test_requested_entries_preserve_disabled_state_and_duplicates(self) -> None:
        disabled = {**self.entry, "enabled": False}
        other_copy = {**self.entry, "path": str(self.project / "second" / "SKILL.md"), "scope": "user"}
        unrelated = {"name": "unrelated", "path": "not-requested", "enabled": "not-requested"}
        entries, complete = self.read(self.catalog(skills=[disabled, unrelated, other_copy]))
        self.assertEqual([disabled, other_copy], entries)
        self.assertTrue(complete)

    def test_catalog_errors_retain_found_entries_but_mark_absence_unverified(self) -> None:
        errors = [{"path": str(self.project / "unreadable"), "message": "permission denied"}]
        self.assertEqual(([self.entry], False), self.read(self.catalog(errors=errors)))
        self.assertEqual(([], False), self.read(self.catalog(skills=[], errors=errors)))
        self.assertEqual(([], True), self.read(self.catalog(skills=[])))

    def test_rejects_wrong_project_and_malformed_catalog_shapes(self) -> None:
        cases = [
            {}, {"data": []}, {"data": [self.catalog()["data"][0]] * 2},
            {"data": [None]}, self.catalog(cwd=str(self.project / "other")),
            {"data": [{"cwd": str(self.project), "skills": {}, "errors": []}]},
            {"data": [{"cwd": str(self.project), "skills": [], "errors": None}]},
        ]
        for value in cases:
            with self.subTest(catalog=value), self.assertRaises(discovery.DiscoveryError):
                self.read(value)

    def test_rejects_invalid_selected_skill_metadata_without_truthiness_coercion(self) -> None:
        cases = [
            None, {"name": 123},
            {**self.entry, "path": "relative/SKILL.md"},
            {**self.entry, "scope": None},
            {**self.entry, "enabled": 1},
            {**self.entry, "enabled": "false"},
        ]
        for entry in cases:
            with self.subTest(entry=entry), self.assertRaises(discovery.DiscoveryError):
                self.read(self.catalog(skills=[entry]))

    def test_probe_errors_have_actionable_discovery_failures(self) -> None:
        cases = [
            (FileNotFoundError("missing codex"), "CLI is unavailable"),
            (TimeoutError(), "within 10 seconds"),
            (OSError("broken pipe"), "Could not read"),
            (ValueError("invalid JSON"), "Could not read"),
        ]
        for error, message in cases:
            with self.subTest(error=error), mock.patch.object(
                discovery, "_catalog", mock.AsyncMock(side_effect=error)
            ):
                with self.assertRaisesRegex(discovery.DiscoveryError, message) as caught:
                    discovery.read_skills(self.project, {"sample"})
                self.assertIs(error, caught.exception.__cause__)


class CatalogProtocolTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def process(*messages, eof=True):
        stdout = asyncio.StreamReader()
        for message in messages:
            stdout.feed_data((json.dumps(message) + "\n").encode("utf-8"))
        if eof:
            stdout.feed_eof()
        return SimpleNamespace(
            stdout=stdout,
            stdin=SimpleNamespace(write=mock.Mock(), drain=mock.AsyncMock()),
            wait=mock.AsyncMock(return_value=0),
        )

    async def test_receive_ignores_notifications_and_unrelated_request_ids(self) -> None:
        result = {"data": [{"cwd": "selected-project"}]}
        process = self.process(
            {"method": "notice", "params": {"message": "starting"}},
            {"id": 99, "result": {"data": ["unrelated"]}},
            {"id": 2, "result": result},
        )
        self.assertEqual(result, await discovery._receive(process, 2))

    async def test_receive_rejects_protocol_and_result_shapes(self) -> None:
        for message in [[], {"id": 2, "error": {"code": -1}}, {"id": 2, "result": []}]:
            with self.subTest(message=message), self.assertRaises(discovery.DiscoveryError):
                await discovery._receive(self.process(message), 2)

    async def test_receive_reports_eof_without_the_requested_response(self) -> None:
        with self.assertRaisesRegex(discovery.DiscoveryError, "closed the connection"):
            await discovery._receive(self.process({"id": 1, "result": {}}), 2)

    async def test_catalog_handshake_is_project_scoped_and_always_closes_process(self) -> None:
        project = Path(tempfile.gettempdir()).resolve() / "catalog project"
        result = {"data": []}
        process = self.process({"id": 1, "result": {}}, {"id": 2, "result": result})
        transport = SimpleNamespace(close=mock.Mock())
        spawn = mock.AsyncMock(return_value=(transport, object()))
        loop = asyncio.get_running_loop()
        with mock.patch.object(loop, "subprocess_exec", spawn), mock.patch.object(
            discovery.asyncio.subprocess, "Process", return_value=process
        ):
            self.assertEqual(result, await discovery._catalog(project))
        arguments = spawn.await_args
        self.assertEqual(("codex", "app-server", "--stdio"), arguments.args[1:])
        self.assertEqual(project, arguments.kwargs["cwd"])
        sent = [json.loads(call.args[0]) for call in process.stdin.write.call_args_list]
        self.assertEqual(["initialize", "initialized", "skills/list"], [message["method"] for message in sent])
        self.assertEqual({"cwds": [str(project)], "forceReload": True}, sent[-1]["params"])
        self.assertEqual(3, process.stdin.drain.await_count)
        transport.close.assert_called_once_with()
        process.wait.assert_awaited_once_with()

    async def test_catalog_cleans_up_protocol_failure_write_failure_and_timeout(self) -> None:
        for failure in ["protocol", "write", "timeout"]:
            with self.subTest(failure=failure):
                process = self.process(eof=False) if failure == "timeout" else self.process({"id": 1, "error": {}})
                expected = discovery.DiscoveryError
                if failure == "write":
                    process.stdin.drain.side_effect = BrokenPipeError("closed")
                    expected = BrokenPipeError
                elif failure == "timeout":
                    expected = TimeoutError
                transport = SimpleNamespace(close=mock.Mock())
                loop = asyncio.get_running_loop()
                with mock.patch.object(loop, "subprocess_exec", mock.AsyncMock(return_value=(transport, object()))), mock.patch.object(
                    discovery.asyncio.subprocess, "Process", return_value=process
                ), mock.patch.object(discovery, "CATALOG_TIMEOUT_SECONDS", 0 if failure == "timeout" else 10):
                    with self.assertRaises(expected):
                        await discovery._catalog(Path(tempfile.gettempdir()).resolve())
                transport.close.assert_called_once_with()
                process.wait.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
