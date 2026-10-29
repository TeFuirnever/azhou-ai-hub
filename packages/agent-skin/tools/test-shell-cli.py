#!/usr/bin/env python3
"""Exercise the public Bash entry points against isolated package fixtures."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import tempfile
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
SHELL_SOURCES = (
    "tools/build-macos.sh",
    "tools/install-macos.sh",
    "tools/build-extension.sh",
    "预览动画.command",
    "扩展启动Codex.command",
)


def write_executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def make_fixture(root: Path, *, missing: str | None = None, build_symlink: bool = False,
                 icon_size: int = 1024, missing_private: bool = False) -> Path:
    root.mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "Native").mkdir()
    (root / "assets/private/app-icon").mkdir(parents=True)
    (root / "assets/private").mkdir(exist_ok=True)
    (root / "hub-package.json").write_bytes((PACKAGE / "hub-package.json").read_bytes())
    (root / "theme-config.json").write_bytes((PACKAGE / "theme-config.json").read_bytes())
    for name in ("verify-artifacts.py", "build-preflight.py"):
        source = PACKAGE / "tools" / name
        if source.is_file():
            shutil.copy2(source, root / "tools" / name)
    for name in ("App.swift", "Wallpaper.swift", "InstallRegistry.swift", "InstallRegistryCore.swift"):
        (root / "Native" / name).write_text("// shell fixture\n", encoding="utf-8")
    for name in ("working.png", "scene.js", "wallpaper-scene-q-v3.png", "entry-avatar.png"):
        (root / "assets/private" / name).write_bytes(b"fixture\n")
    icon = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
            + struct.pack(">II", icon_size, icon_size))
    (root / "assets/private/app-icon/source.png").write_bytes(icon)
    (root / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
    (root / ".gitignore").write_text("/.build/\n/assets/private/\n", encoding="utf-8")
    if build_symlink:
        external_build = root.parent / (root.name + "-external-build")
        external_build.mkdir()
        (root / ".build").symlink_to(external_build, target_is_directory=True)
    else:
        (root / ".build").mkdir()
    if missing:
        (root / "assets/private" / missing).unlink(missing_ok=True)
    if missing_private:
        shutil.rmtree(root / "assets/private")
    return root


def fake_tools(bin_dir: Path) -> None:
    common = '''#!/bin/bash
set -u
printf '%s\\t%s\\t%s\\n' "${0##*/}" "$PWD" "$*" >> "${EVENT_LOG:?}"
'''
    write_executable(bin_dir / "xcrun", common + '''
output=""
while (($#)); do
  if [[ "$1" == "-o" && $# -ge 2 ]]; then output="$2"; break; fi
  shift
done
if [[ -n "$output" ]]; then : > "$output"; fi
exit "${FAKE_XCRUN_EXIT:-0}"
''')
    write_executable(bin_dir / "sips", common + '''
output=""
while (($#)); do
  if [[ "$1" == "--out" && $# -ge 2 ]]; then output="$2"; break; fi
  shift
done
[[ -n "$output" ]] || exit 90
: > "$output"
exit "${FAKE_SIPS_EXIT:-0}"
''')
    write_executable(bin_dir / "iconutil", common + '''
output=""
while (($#)); do
  if [[ "$1" == "-o" && $# -ge 2 ]]; then output="$2"; break; fi
  shift
done
[[ -n "$output" ]] || exit 90
: > "$output"
exit "${FAKE_ICONUTIL_EXIT:-0}"
''')
    write_executable(bin_dir / "codesign", common + '''
exit "${FAKE_CODESIGN_EXIT:-0}"
''')
    write_executable(bin_dir / "plutil", common + '''
exit "${FAKE_PLUTIL_EXIT:-0}"
''')
    write_executable(bin_dir / "open", common + '''
exit "${FAKE_OPEN_EXIT:-0}"
''')
    write_executable(bin_dir / "git", common + '''
case "${1:-}" in
  ls-files) printf '%s' "${FAKE_GIT_TRACKED:-}"; exit 0 ;;
  check-ignore) exit "${FAKE_GIT_UNIGNORED_EXIT:-0}" ;;
  *) exit 91 ;;
esac
''')
    real_python = shutil.which("python3")
    if not real_python:
        raise RuntimeError("python3 is required for shell CLI fixture tests")
    write_executable(bin_dir / "python3", common + '''
if [[ "${1:-}" == "-c" ]]; then exec "${REAL_PYTHON3:?}" "$@"; fi
case "${1:-}" in
  tools/build-preflight.py) exec "${REAL_PYTHON3:?}" "$@" ;;
  tools/verify-artifacts.py)
    case "${2:-}" in
      --write-bundle-info) mkdir -p "$3/Contents"; : > "$3/Contents/Info.plist" ;;
      --write-marker) mkdir -p "$3/Contents/Resources"; : > "$3/Contents/Resources/azhou-build.json" ;;
      --publish)
        if [[ "${FAKE_PRESERVE_STAGE:-0}" == "1" ]]; then
          : > "$(dirname "$3")/.preserve-original"
        fi
        ;;
      --check-inputs) ;;
      *) exit 92 ;;
    esac
    exit 0
    ;;
  tools/build-wallpaper.py|tools/build-startup.py) exit 0 ;;
  tools/install-macos.py) exit "${FAKE_INSTALLER_EXIT:-0}" ;;
  *) exit 93 ;;
esac
''')
    write_executable(bin_dir / "bash", common + '''
if [[ "${FAKE_BASH_CAPTURE:-0}" == "1" ]]; then
  exit "${FAKE_BASH_EXIT:-0}"
fi
case "${1:-}" in
  tools/build-macos.sh) shift; exec "$AGENT_SKIN_TEST_BASH" "$AGENT_SKIN_TEST_SOURCE_ROOT/tools/build-macos.sh" "$@" ;;
  tools/install-macos.sh) shift; exec "$AGENT_SKIN_TEST_BASH" "$AGENT_SKIN_TEST_SOURCE_ROOT/tools/install-macos.sh" "$@" ;;
  *) exec "$AGENT_SKIN_TEST_BASH" "$@" ;;
esac
''')


def shell_driver(source_root: Path, cases: list[dict[str, object]], output_root: Path,
                 test_bash: str) -> str:
    lines = [
        "#!/bin/bash",
        "set -uo pipefail",
        "AGENT_SKIN_TEST_SOURCE_ROOT=" + shlex.quote(str(source_root)),
        "AGENT_SKIN_TEST_BASH=" + shlex.quote(test_bash),
        "export AGENT_SKIN_TEST_SOURCE_ROOT",
        "export AGENT_SKIN_TEST_BASH",
        "cd() {",
        '  case "${1:-}" in',
        '    "$AGENT_SKIN_TEST_SOURCE_ROOT"|"$AGENT_SKIN_TEST_SOURCE_ROOT/tools/..") builtin cd "$AGENT_SKIN_TEST_FIXTURE_ROOT" ;;',
        '    *) builtin cd "$@" ;;',
        "  esac",
        "}",
        "export -f cd",
        "run_case() {",
        "  local name=$1; shift",
        "  local case_dir=" + shlex.quote(str(output_root)) + '/"$name"',
        '  mkdir -p "$case_dir"',
        '  if "$@" > "$case_dir/stdout" 2> "$case_dir/stderr"; then',
        '    printf "0\\n" > "$case_dir/status"',
        "  else",
        '    printf "%s\\n" "$?" > "$case_dir/status"',
        "  fi",
        "}",
    ]
    source_dir = source_root / "tools"
    entrypoints = {
        "build": str(source_dir / "build-macos.sh"),
        "install": str(source_dir / "install-macos.sh"),
        "extension": str(source_dir / "build-extension.sh"),
        "preview": str(source_root / "预览动画.command"),
        "codex": str(source_root / "扩展启动Codex.command"),
    }
    for case in cases:
        name = str(case["name"])
        environment = dict(case["environment"])
        environment["AGENT_SKIN_TEST_FIXTURE_ROOT"] = str(case["fixture"])
        environment["EVENT_LOG"] = str(output_root / name / "events.log")
        environment["REAL_PYTHON3"] = str(shutil.which("python3"))
        environment.setdefault("AZHOU_BUILD_SYSTEM_BIN", str(case["system_bin"]))
        command = [test_bash, entrypoints[str(case["entrypoint"])], *case["args"]]
        invocation = ["env", *(f"{key}={value}" for key, value in environment.items()), *command]
        lines.append("run_case " + shlex.quote(name) + " " + " ".join(shlex.quote(item) for item in invocation))
    lines.append("exit 0")
    return "\n".join(lines) + "\n"


def read_coverage(raw_coverage: dict[str, list[int | None]]) -> dict[str, dict[str, dict[str, int]]]:
    coverage_by_path = {Path(path).resolve(): lines for path, lines in raw_coverage.items()}
    files: dict[str, dict[str, dict[str, int]]] = {}
    for relative in SHELL_SOURCES:
        source = (PACKAGE / relative).resolve()
        if source not in coverage_by_path:
            raise RuntimeError(
                f"Bashcov result did not include canonical production source: {relative}; "
                f"observed={sorted(str(path) for path in coverage_by_path)}"
            )
        line_data = coverage_by_path[source]
        executable = [count for count in line_data if count is not None]
        files[relative] = {
            "lines": {
                "count": len(executable),
                "covered": sum(1 for count in executable if count > 0),
            }
        }
        if not files[relative]["lines"]["covered"]:
            raise RuntimeError(f"Bashcov reported no executed lines for canonical production source: {relative}")
    return {"files": files}


def assert_read_coverage_preserves_raw_zeros() -> None:
    with tempfile.TemporaryDirectory(prefix="shell-coverage-self-check-") as temporary:
        package = Path(temporary)
        source = package / "source.sh"
        source_lines: list[str] = []
        raw_counts: list[int] = []
        for _ in range(6):
            source_lines.extend(("command \\", "  continuation"))
            raw_counts.extend((1, 0))
        source_lines.extend(f"command {index}" for index in range(53))
        raw_counts.extend([1] * 53)
        source.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        with patch(__name__ + ".PACKAGE", package), patch(__name__ + ".SHELL_SOURCES", ("source.sh",)):
            report = read_coverage({str(source.resolve()): raw_counts})
    actual = report["files"]["source.sh"]["lines"]
    if actual != {"count": 65, "covered": 59}:
        raise AssertionError(f"read_coverage changed raw 59/65 Bashcov counts: {actual!r}")


def assert_case(output_root: Path, name: str, status: int, *, stdout: str = "",
                stderr: str = "", events: tuple[str, ...] = (), absent: tuple[str, ...] = ()) -> list[str]:
    case_dir = output_root / name
    if not (case_dir / "status").is_file():
        raise RuntimeError(f"{name}: shell driver did not record a result; generated={sorted(path.name for path in output_root.iterdir())}")
    actual = int((case_dir / "status").read_text(encoding="utf-8").strip())
    out = (case_dir / "stdout").read_text(encoding="utf-8", errors="replace")
    err = (case_dir / "stderr").read_text(encoding="utf-8", errors="replace")
    event_text = ((case_dir / "events.log").read_text(encoding="utf-8", errors="replace")
                  if (case_dir / "events.log").exists() else "")
    assert actual == status, f"{name}: expected exit {status}, got {actual}; stdout={out!r}; stderr={err!r}"
    assert stdout in out, f"{name}: expected stdout to contain {stdout!r}; got {out!r}"
    assert stderr in err, f"{name}: expected stderr to contain {stderr!r}; got {err!r}"
    for event in events:
        assert event in event_text, f"{name}: expected event {event!r}; got {event_text!r}"
    for event in absent:
        assert event not in event_text, f"{name}: unexpected event {event!r}; got {event_text!r}"
    return event_text.splitlines()


def run_suite(report_path: Path) -> dict[str, object]:
    assert_read_coverage_preserves_raw_zeros()
    bashcov = shutil.which("bashcov")
    if not bashcov:
        raise RuntimeError("bashcov is required; install the pinned compatible gem in the task-local GEM_HOME")
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to run the pinned Bashcov coverage engine")
    test_bash = os.environ.get("BASHCOV_BASH_PATH") or shutil.which("bash")
    if not test_bash or not Path(test_bash).is_file():
        raise RuntimeError("BASHCOV_BASH_PATH must point to Bash 4.1 or newer for complete nested-shell coverage")
    test_bash = str(Path(test_bash).resolve())
    with tempfile.TemporaryDirectory(prefix="a-", dir="/tmp") as temporary:
        temporary_root = Path(temporary)
        source_alias = temporary_root / "p"
        source_alias.symlink_to(PACKAGE, target_is_directory=True)
        fixtures_root = temporary_root / "f"
        fixtures_root.mkdir()
        output_root = temporary_root / "r"
        output_root.mkdir()
        case_specs: list[dict[str, object]] = []

        def add_case(name: str, entrypoint: str, args: tuple[str, ...] = (), *,
                     environment: dict[str, str] | None = None, missing: str | None = None,
                     build_symlink: bool = False, icon_size: int = 1024,
                     missing_private: bool = False) -> Path:
            fixture = make_fixture(fixtures_root / f"f{len(case_specs)}", missing=missing,
                                   build_symlink=build_symlink, icon_size=icon_size,
                                   missing_private=missing_private)
            bin_dir = fixture / ".build/sys tools"
            bin_dir.mkdir(parents=True, exist_ok=True)
            fake_tools(bin_dir)
            test_bin = fixture / ".build/fake-bin"
            test_bin.mkdir()
            for tool_name in ("python3", "git", "bash", "codesign", "plutil", "open"):
                shutil.copy2(bin_dir / tool_name, test_bin / tool_name)
            path = str(test_bin) + os.pathsep + os.environ.get("PATH", "")
            case_env = {
                "PATH": path,
                "FAKE_BASH_CAPTURE": "0",
                "FAKE_BASH_EXIT": "0",
                **(environment or {}),
            }
            case_specs.append({
                "name": name,
                "entrypoint": entrypoint,
                "args": args,
                "environment": case_env,
                "fixture": fixture,
                "system_bin": bin_dir,
            })
            return fixture

        add_case("missing-input", "build", missing="working.png")
        add_case("missing-private-directory", "build", missing_private=True)
        add_case("missing-scene-script", "build", missing="scene.js")
        add_case("missing-wallpaper-scene", "build", missing="wallpaper-scene-q-v3.png")
        add_case("invalid-system-bin", "build", environment={
            "AZHOU_BUILD_SYSTEM_BIN": str(temporary_root / "not a tools directory"),
        })
        add_case("preflight-symlink", "build", build_symlink=True)
        add_case("preflight-tracked", "build", environment={"FAKE_GIT_TRACKED": "assets/private/secret.png"})
        add_case("preflight-ignore", "build", environment={"FAKE_GIT_UNIGNORED_EXIT": "1"})
        add_case("preflight-bad-icon", "build", icon_size=256)
        add_case("build-success", "build")
        add_case("build-preserve-stage", "build", environment={"FAKE_PRESERVE_STAGE": "1"})
        add_case("build-xcrun-failure", "build", environment={"FAKE_XCRUN_EXIT": "18"})
        add_case("build-codesign-failure", "build", environment={"FAKE_CODESIGN_EXIT": "19"})
        add_case("install-check", "install", ("--check",), environment={"FAKE_INSTALLER_EXIT": "23"})
        add_case("install-help", "install", ("--help",))
        add_case("install-short-help", "install", ("-h",))
        add_case("install-success-build", "install", environment={"FAKE_INSTALLER_EXIT": "29"})
        add_case("install-build-failure", "install", environment={"FAKE_XCRUN_EXIT": "25"})
        add_case("extension-args", "extension", ("alpha", "two words"), environment={
            "FAKE_BASH_CAPTURE": "1", "FAKE_BASH_EXIT": "31",
        })
        add_case("extension-build", "extension")
        add_case("preview-success", "preview")
        add_case("preview-failure", "preview", environment={"FAKE_OPEN_EXIT": "32"})
        add_case("codex-launch-failure", "codex", environment={
            "FAKE_BASH_CAPTURE": "1", "FAKE_BASH_EXIT": "33",
        })

        driver = temporary_root / "shell-suite.sh"
        driver.write_text(shell_driver(source_alias, case_specs, output_root, test_bash), encoding="utf-8")
        driver.chmod(0o755)

        bashcov_runner = r'''require "bashcov"
require "json"
Bashcov.bash_path = ENV.fetch("BASHCOV_BASH_PATH", Bashcov.bash_path)
Bashcov.send(:remove_const, :BASH_VERSION)
bash_version_command = %q!printf '%s.%s' "${BASH_VERSINFO[0]}" "${BASH_VERSINFO[1]}"!
Bashcov.const_set(:BASH_VERSION, IO.popen([Bashcov.bash_path, "-c", bash_version_command]) { |pipe| pipe.read })
raise "BASHCOV_BASH_PATH must support BASH_XTRACEFD (Bash 4.1 or newer)" unless Bashcov.bash_xtracefd?
Bashcov.root_directory = ARGV.fetch(0)
Bashcov.skip_uncovered = false
Dir.chdir(ARGV.fetch(2))
ENV["PWD"] = ARGV.fetch(2)
runner = Bashcov::Runner.new([Bashcov.bash_path, ARGV.fetch(1)])
status = runner.run
puts JSON.generate({"status" => status.exitstatus, "coverage" => runner.result})
exit status.exitstatus
'''
        env = os.environ.copy()
        env["BASHCOV_BASH_PATH"] = test_bash
        result = subprocess.run([ruby, "-e", bashcov_runner, str(PACKAGE), str(driver), str(source_alias)], cwd=PACKAGE,
                                env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", check=False)
        if result.returncode:
            raise RuntimeError(
                f"Bashcov shell suite failed ({result.returncode}).\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        try:
            coverage_run = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Bashcov did not emit source data: {result.stdout!r}") from error
        if coverage_run.get("status") != 0:
            raise RuntimeError(f"Bashcov shell driver returned status {coverage_run.get('status')}")
        missing_results = [str(case["name"]) for case in case_specs
                           if not (output_root / str(case["name"]) / "status").is_file()]
        if missing_results:
            raise RuntimeError(
                f"Bashcov completed but the shell driver did not record cases {missing_results}.\n"
                f"driver:\n{driver.read_text(encoding='utf-8')}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        expected_cases = {
            "missing-input": (1, "", "缺少本地阿舟素材", (), ("xcrun", "build-preflight.py")),
            "missing-private-directory": (1, "", "缺少本地阿舟素材", (), ("xcrun", "build-preflight.py")),
            "missing-scene-script": (1, "", "缺少本地阿舟素材", (), ("xcrun", "build-preflight.py")),
            "missing-wallpaper-scene": (1, "", "缺少本地阿舟素材", (), ("xcrun", "build-preflight.py")),
            "invalid-system-bin": (1, "", "AZHOU_BUILD_SYSTEM_BIN", (), ("build-preflight.py", "xcrun")),
            "preflight-symlink": (1, "", "拒绝通过符号链接构建", ("build-preflight.py",), ("xcrun",)),
            "preflight-tracked": (1, "", "私有素材、构建或验收产物进入 Git 跟踪范围", ("ls-files",), ("xcrun",)),
            "preflight-ignore": (1, "", "缺少私有产物 ignore 规则", ("check-ignore",), ("xcrun",)),
            "preflight-bad-icon": (1, "", "至少 1024×1024", ("check-ignore",), ("xcrun",)),
            "build-success": (0, "构建完成", "", (
                "xcrun", "sips", "iconutil", "codesign", "azhou-install-registry",
                "Native/InstallRegistry.swift Native/InstallRegistryCore.swift",
                "-framework AppKit -framework CoreServices",
            ), ()),
            "build-preserve-stage": (0, "", "原子回滚未完成", ("--publish",), ()),
            "build-xcrun-failure": (18, "", "", ("xcrun",), ("codesign", "--publish")),
            "build-codesign-failure": (19, "", "", ("codesign",), ("--publish",)),
            "install-check": (23, "", "", ("tools/install-macos.py --check",), ("xcrun",)),
            "install-help": (0, "", "", ("tools/install-macos.py --help",), ("xcrun",)),
            "install-short-help": (0, "", "", ("tools/install-macos.py -h",), ("xcrun",)),
            "install-success-build": (29, "构建完成", "", ("codesign", "tools/install-macos.py"), ()),
            "install-build-failure": (25, "", "", ("xcrun",), ("tools/install-macos.py", "codesign")),
            "extension-args": (31, "", "", ("bash\t", "tools/build-macos.sh alpha two words"), ("xcrun",)),
            "extension-build": (0, "构建完成", "", ("xcrun",), ()),
            "preview-success": (0, "", "", ("open\t", "index.html"), ()),
            "preview-failure": (32, "", "", ("open\t", "index.html"), ()),
            "codex-launch-failure": (33, "", "", ("bash\t", "tools/install-macos.sh --open"), ("xcrun",)),
        }
        for name, (status, stdout, stderr, events, absent) in expected_cases.items():
            assert_case(output_root, name, status, stdout=stdout, stderr=stderr,
                        events=events, absent=absent)

        build_success = output_root / "build-success"
        build_stdout = (build_success / "stdout").read_text(encoding="utf-8", errors="replace")
        assert "~/Applications/" in build_stdout, "build hint did not include the user Applications install path"
        build_events = (build_success / "events.log").read_text(encoding="utf-8", errors="replace").splitlines()
        icon_events = [line for line in build_events if line.startswith("sips\t")]
        assert len(icon_events) == 10, f"expected 10 icon resize calls, got {len(icon_events)}"
        for size in (16, 32, 128, 256, 512):
            base_name = f"icon_{size}x{size}.png"
            retina_name = f"icon_{size}x{size}@2x.png"
            assert any(line.split("\t", 2)[-1].startswith(f"-z {size} {size} ")
                       and line.endswith(base_name) for line in icon_events), \
                f"missing {size}x icon resize: {icon_events!r}"
            pixels = size * 2
            assert any(line.split("\t", 2)[-1].startswith(f"-z {pixels} {pixels} ")
                       and line.endswith(retina_name) for line in icon_events), \
                f"missing {size}x@2x icon resize: {icon_events!r}"

        # Assertions that depend on event ordering or filesystem cleanup.
        install_events = (output_root / "install-success-build/events.log").read_text(
            encoding="utf-8", errors="replace").splitlines()
        assert install_events.index(next(line for line in install_events if "codesign" in line)) < \
            install_events.index(next(line for line in install_events if "install-macos.py" in line)), \
            "installer ran before successful build/signing"
        for name in ("build-xcrun-failure", "install-build-failure"):
            fixture = next(Path(case["fixture"]) for case in case_specs if case["name"] == name)
            assert not list((fixture / ".build").glob("azhou-stage.*")), f"{name}: failed stage was not cleaned"
        for name in ("preview-success", "preview-failure"):
            event = (output_root / name / "events.log").read_text(
                encoding="utf-8", errors="replace").splitlines()[0]
            assert event.split("\t", 2)[1] == str(next(Path(case["fixture"]) for case in case_specs if case["name"] == name)), \
                f"{name}: preview did not anchor its working directory to its package"
            assert event.endswith("index.html"), f"{name}: preview did not open the package index.html"
        extension_event = (output_root / "extension-args/events.log").read_text(encoding="utf-8", errors="replace")
        assert extension_event.rstrip().endswith("tools/build-macos.sh alpha two words"), \
            f"build extension did not forward its positional arguments: {extension_event!r}"
        codex_event = (output_root / "codex-launch-failure/events.log").read_text(encoding="utf-8", errors="replace")
        assert codex_event.rstrip().endswith("tools/install-macos.sh --open"), \
            "Codex launcher did not dispatch to the install entry with --open"

        report = read_coverage(coverage_run["coverage"])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.with_suffix(".raw.json").write_text(
            json.dumps(coverage_run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path,
                        help="write Bash line coverage JSON to this path")
    args = parser.parse_args()
    try:
        report = run_suite(args.report.resolve())
    except (AssertionError, OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        parser.exit(1, f"shell CLI suite failed: {error}\n")
    total = sum(item["lines"]["count"] for item in report["files"].values())
    covered = sum(item["lines"]["covered"] for item in report["files"].values())
    print(f"shell CLI PASS: {covered}/{total} Bash executable lines covered across {len(SHELL_SOURCES)} production sources")
    print(f"report: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
