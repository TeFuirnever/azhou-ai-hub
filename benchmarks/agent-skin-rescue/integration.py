"""Compose the offline candidate without granting host execution authority."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import plistlib
import shutil
import stat
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
WORKTREE = SOURCE.parents[1]


def _admit(root, binding, producer, output, scope):
    root, output = Path(root), Path(output)
    if scope != "fixture-only":
        raise ValueError("only explicit fixture scope is accepted")
    if (not root.is_absolute() or ".." in root.parts or root.resolve() != root
            or not root.is_relative_to(WORKTREE / ".scratch")):
        raise ValueError("resources must be in this worktree's private evidence")
    info = root.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError("resource root must be private and owned")
    if (not output.is_absolute() or ".." in output.parts or output == root
            or not output.is_relative_to(root) or output.parent.resolve() != output.parent
            or output.exists() or output.is_symlink()):
        raise ValueError("output must be a new canonical child of resource evidence")
    inputs = []
    for value in (binding, producer):
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        if ".." in path.parts or not path.is_relative_to(root) or path.resolve() != path:
            raise ValueError("proof input outside resource evidence")
        inputs.append(path)
    return root, *inputs, output


def _source_manifest():
    names = subprocess.check_output(
        ["git", "--no-optional-locks", "ls-files", "--", "benchmarks/agent-skin-rescue"],
        cwd=WORKTREE, text=True, encoding="utf-8",
    ).splitlines()
    return {name: hashlib.sha256((WORKTREE / name).read_bytes()).hexdigest() for name in names}


def run(root, binding, producer, output, *, scope="fixture-only"):
    root, binding, producer, output = _admit(root, binding, producer, output, scope)
    # Imports occur after admission so a host request cannot even initialize collaborators.
    from isolation import Isolation
    from launcher import Supervisor
    from command_log import SignalLatch
    from offline_runtime import json_new, sha
    from registration import observe_installation

    output.mkdir(mode=0o700)
    source_inputs = _source_manifest()
    summary = {"kind": "A", "scope": "offline synthetic chain only", "status": "failed",
               "source_inputs": source_inputs, "hostValidation": "not_run",
               "hostLaunchAllowed": False, "historicalResultsInherited": False,
               "originalProducerSHA256": sha(producer)}
    command_results = []

    def record(value):
        json_new(output / "result.json", value, root=WORKTREE)

    try:
        isolation = Isolation(output)
        layout = isolation.prepare_layout(output / "private-layout")
        environment = isolation.child_environment(os.environ, layout)
        plan = isolation.launch_plan(layout, "/Applications/ZCode.app/Contents/MacOS/ZCode")
        if plan["hostLaunchAllowed"]:
            raise ValueError("offline plan unexpectedly granted host authority")
        json_new(output / "isolation-plan.json", plan, root=WORKTREE)
        bundle = output / "synthetic.app"
        for suffix in ("Contents/MacOS", "Contents/Resources"):
            (bundle / suffix).mkdir(mode=0o700, parents=True, exist_ok=False)
        info = {"CFBundleIdentifier": "invalid.synthetic.rescue", "CFBundleShortVersionString": "1",
                "CFBundleVersion": "1", "CFBundleExecutable": "SyntheticFixture"}
        for path, data in (
            (bundle / "Contents/Info.plist", plistlib.dumps(info)),
            (bundle / "Contents/MacOS/SyntheticFixture", b"synthetic bytes; never executable\n"),
            (bundle / "Contents/Resources/app.asar", b"synthetic archive; not a host\n"),
        ):
            with path.open("xb") as handle:
                handle.write(data)
            os.chmod(path, 0o600)
        registration = observe_installation(bundle, synthetic=True, root=WORKTREE)
        if registration["hostLaunchAllowed"] or registration["strictSignature"]["status"] != "not-run":
            raise ValueError("synthetic registration cannot validate a host")
        json_new(output / "synthetic-registration.json", registration, root=WORKTREE)
        command_root = output / "commands"
        command_root.mkdir(mode=0o700)
        with SignalLatch() as stop:
            supervisor = Supervisor(command_root, interruption=stop, root=WORKTREE)
            checker, checker_case = supervisor.run(
                "resource-proof",
                [sys.executable, "-B", str(SOURCE / "rebind/check_binding.py"),
                 "--root", str(root), "--binding", str(binding), "--producer", str(producer)],
                environment=environment, timeout=60,
            )
            command_results.append((checker, checker_case))
            if not checker["successful"]:
                raise ValueError("resource proof did not complete successfully")
            handoff, handoff_case = supervisor.fixture(
                "owned-handoff", "hold", handoff=lambda offer: json.loads(json.dumps(offer)),
                environment=environment, timeout=10,
            )
            command_results.append((handoff, handoff_case))
            if not handoff["successful"]:
                raise ValueError("controlled handoff did not complete successfully")
            request = output / "runtime-request.json"
            json_new(request, {
                "schema": "offline-runtime-request.v1", "scope": "fixture-only", "root": str(root),
                "binding": {"path": str(binding.relative_to(root)), "sha256": sha(binding)},
                "producer": {"path": str(producer.relative_to(root)), "sha256": sha(producer)},
            }, root=WORKTREE)
            runtime_output = command_root / "runtime-output"
            node = shutil.which("node")
            if not node:
                raise ValueError("Node runtime unavailable")
            runtime, runtime_case = supervisor.run(
                "single-context-runtime",
                [node, str(SOURCE / "runtime/offline.mjs"), "--request", str(request),
                 "--out", str(runtime_output)], environment=environment, timeout=60,
            )
            command_results.append((runtime, runtime_case))
            if not runtime["successful"]:
                raise ValueError("controlled runtime command did not complete successfully")
            runtime_result = json.loads((runtime_output / "result.json").read_bytes())
            if (runtime_result.get("status") != "passed"
                    or runtime_result.get("hostValidation") != "not_run"):
                raise ValueError("runtime result is not an offline fixture success")
            producer_paths = [case / "command-result.json" for _, case in command_results]
            hashes = {str(path): sha(path) for path in producer_paths}
            archive_request = output / "archive-request.json"
            json_new(archive_request, {
                "scope": "offline-archive-only",
                "producers": [{"path": str(path), "sha256": digest} for path, digest in
                              ((Path(path), digest) for path, digest in hashes.items())],
            }, root=WORKTREE)
            archive_output = command_root / "archive-output"
            archived, archived_case = supervisor.run(
                "later-archive",
                [sys.executable, "-B", str(SOURCE / "archive.py"), "--request", str(archive_request),
                 "--out", str(archive_output)], environment=environment, timeout=30,
            )
            command_results.append((archived, archived_case))
            archive_result = json.loads((archive_output / "result.json").read_bytes())
            if not archived["successful"] or archive_result["status"] != "complete":
                raise ValueError("later archive is incomplete")
            if any(sha(Path(path)) != digest for path, digest in hashes.items()):
                raise ValueError("archive mutated an immutable command producer")
            summary.update(runtime=runtime_result, archive=archive_result,
                           producer_receipts=hashes, isolation_layout=layout,
                           synthetic_registration_scope=registration["scope"])
        if source_inputs != _source_manifest() or sha(producer) != summary["originalProducerSHA256"]:
            raise ValueError("source or original producer changed during composition")
        summary.update(status="passed", commands=[
            {"receipt": str(case / "command-result.json"), "sha256": sha(case / "command-result.json"),
             "kind": value["kind"], "exit_code": value["exit_code"], "successful": value["successful"]}
            for value, case in command_results
        ], source_inputs_unchanged=True, originalProducerUnchanged=True)
        record(summary)
        return summary
    except BaseException as error:
        summary.update(error={"type": type(error).__name__},
                       commands=[{"case": str(case), "kind": value.get("kind"),
                                  "exit_code": value.get("exit_code"),
                                  "successful": value.get("successful")}
                                 for value, case in command_results])
        record(summary)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--producer", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scope", default="fixture-only")
    args = parser.parse_args()
    result = run(args.root, args.binding, args.producer, args.out, scope=args.scope)
    print(json.dumps({"status": result["status"], "scope": result["scope"],
                      "hostValidation": result["hostValidation"]}))
