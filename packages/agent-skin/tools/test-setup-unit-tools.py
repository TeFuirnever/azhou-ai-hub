#!/usr/bin/env python3
"""Prepare pinned local Bash and Bashcov tools for Agent Skin unit coverage."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASH_VERSION = "5.2.37"
BASHCOV_VERSION = "1.7.0"
BASH_SOURCE_URL = f"https://ftp.gnu.org/gnu/bash/bash-{BASH_VERSION}.tar.gz"
MAX_BUILD_JOBS = 4


class SetupError(RuntimeError):
    """The pinned local coverage tools could not be prepared safely."""


@dataclass(frozen=True)
class ToolPaths:
    bashcov_bash_path: Path
    gem_home: Path

    @property
    def gem_path(self) -> Path:
        return self.gem_home

    @property
    def gem_bin(self) -> Path:
        return self.gem_home / "bin"

    def as_json(self) -> dict[str, str]:
        return {
            "bashcov_bash_path": str(self.bashcov_bash_path),
            "gem_home": str(self.gem_home),
            "gem_path": str(self.gem_path),
            "gem_bin": str(self.gem_bin),
            "bash_version": BASH_VERSION,
            "bashcov_version": BASHCOV_VERSION,
        }


def paths_for(root: Path = ROOT) -> ToolPaths:
    local_root = root.resolve()
    return ToolPaths(
        bashcov_bash_path=local_root / ".build" / "bash-5.2.37" / "bin" / "bash",
        gem_home=local_root / ".build" / "shell-gems",
    )


def run_command(command: list[str], *, cwd: Path | None = None,
                env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        raise SetupError(f"could not run {command[0]}: {error}") from error


def command_output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout or ""


def run_checked(command: list[str], *, cwd: Path | None = None,
                env: dict[str, str] | None = None,
                runner=None) -> subprocess.CompletedProcess[str]:
    execute = runner or run_command
    result = execute(command, cwd=cwd, env=env)
    if result.returncode:
        tail = "\n".join(command_output(result).splitlines()[-50:])
        detail = f"\nlast output:\n{tail}" if tail else ""
        raise SetupError(f"command failed ({result.returncode}): {' '.join(command)}{detail}")
    return result


def parse_bash_version(output: str) -> str:
    match = re.search(r"GNU bash, version (\d+\.\d+\.\d+)", output, re.IGNORECASE)
    if not match:
        raise SetupError("the selected shell did not report a GNU Bash version")
    return match.group(1)


def require_bash_version(binary: Path, *, runner=None) -> str:
    if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
        raise SetupError(f"expected an executable local Bash file: {binary}")
    execute = runner or run_command
    result = execute([str(binary), "--version"])
    if result.returncode:
        raise SetupError(f"could not read Bash version from {binary}: {command_output(result).strip()}")
    actual = parse_bash_version(command_output(result))
    if actual != BASH_VERSION:
        raise SetupError(f"expected GNU Bash {BASH_VERSION} at {binary}, found {actual}")
    return actual


def validate_bash_archive(archive_path: Path) -> None:
    expected_root = f"bash-{BASH_VERSION}"
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as error:
        raise SetupError(f"invalid GNU Bash source archive {archive_path}: {error}") from error
    if not members:
        raise SetupError(f"GNU Bash source archive is empty: {archive_path}")
    for member in members:
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts or not name.parts or name.parts[0] != expected_root:
            raise SetupError(f"unsafe path in GNU Bash source archive: {member.name}")
        if member.issym() or member.islnk() or not (member.isdir() or member.isreg()):
            raise SetupError(f"unexpected non-file member in GNU Bash source archive: {member.name}")
    if not any(member.name == f"{expected_root}/configure" for member in members):
        raise SetupError(f"GNU Bash source archive has no {expected_root}/configure script")


def download_bash_archive(archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(BASH_SOURCE_URL, headers={"User-Agent": "Azhou-Agent-Skin-unit-coverage"})
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=archive_path.parent, prefix="bash-source-", delete=False) as temporary:
            temporary_name = temporary.name
            total = 0
            with urlopen(request, timeout=90) as response:
                if response.status != 200:
                    raise SetupError(f"GNU Bash source download returned HTTP {response.status}")
                content_length = response.headers.get("Content-Length")
                while chunk := response.read(1024 * 1024):
                    temporary.write(chunk)
                    total += len(chunk)
        temporary_path = Path(temporary_name)
        if content_length and total != int(content_length):
            raise SetupError(
                f"GNU Bash {BASH_VERSION} download was truncated: expected {content_length} bytes, got {total}"
            )
        validate_bash_archive(temporary_path)
        os.replace(temporary_path, archive_path)
    except SetupError:
        raise
    except Exception as error:
        raise SetupError(f"could not download {BASH_SOURCE_URL}: {error}") from error
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def extract_bash_source(archive_path: Path, tools_dir: Path, source_dir: Path) -> None:
    validate_bash_archive(archive_path)
    if source_dir.exists():
        raise SetupError(f"Bash source directory already exists but is not ready: {source_dir}")
    tools_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(tools_dir)
    except (OSError, tarfile.TarError) as error:
        raise SetupError(f"could not extract GNU Bash source: {error}") from error
    if not (source_dir / "configure").is_file():
        raise SetupError(f"GNU Bash source extraction did not produce {source_dir / 'configure'}")


def bounded_build_jobs(cpu_count: int | None = None) -> int:
    return max(1, min(MAX_BUILD_JOBS, cpu_count or 1))


def build_bash(source_dir: Path, prefix: Path, *, runner=None) -> None:
    execute = runner or run_command
    run_checked(
        ["./configure", f"--prefix={prefix}", "--without-bash-malloc", "--disable-nls"],
        cwd=source_dir,
        runner=execute,
    )
    run_checked(["make", f"-j{bounded_build_jobs(os.cpu_count())}"], cwd=source_dir, runner=execute)


def ensure_bash(root: Path = ROOT, *, runner=None, downloader=None, builder=None) -> Path:
    paths = paths_for(root)
    if paths.bashcov_bash_path.exists():
        require_bash_version(paths.bashcov_bash_path, runner=runner)
        return paths.bashcov_bash_path

    tools_dir = paths.bashcov_bash_path.parents[2] / "tools"
    source_dir = tools_dir / f"bash-{BASH_VERSION}"
    source_binary = source_dir / "bash"
    if source_binary.exists():
        require_bash_version(source_binary, runner=runner)
    else:
        archive_path = tools_dir / f"bash-{BASH_VERSION}.tar.gz"
        if archive_path.is_file():
            try:
                validate_bash_archive(archive_path)
            except SetupError:
                fetch = downloader or download_bash_archive
                fetch(archive_path)
        else:
            fetch = downloader or download_bash_archive
            fetch(archive_path)
        if not source_dir.exists():
            extract_bash_source(archive_path, tools_dir, source_dir)
        elif not (source_dir / "configure").is_file():
            raise SetupError(f"incomplete GNU Bash source tree: {source_dir}")
        compile_bash = builder or build_bash
        compile_bash(source_dir, paths.bashcov_bash_path.parents[1], runner=runner)
        require_bash_version(source_binary, runner=runner)

    destination = paths.bashcov_bash_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source_binary, destination)
        destination.chmod(destination.stat().st_mode | 0o111)
    except OSError as error:
        raise SetupError(f"could not place local Bash at {destination}: {error}") from error
    require_bash_version(destination, runner=runner)
    return destination


def gem_environment(gem_home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["GEM_HOME"] = str(gem_home)
    environment["GEM_PATH"] = str(gem_home)
    return environment


def bashcov_version(gem_home: Path, ruby: str, *, runner=None) -> str | None:
    executable = gem_home / "bin" / "bashcov"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        return None
    execute = runner or run_command
    result = execute(
        [ruby, "-e", 'require "bashcov"; print Bashcov::VERSION'],
        env=gem_environment(gem_home),
    )
    if result.returncode:
        return None
    return command_output(result).strip()


def ensure_bashcov(root: Path = ROOT, *, runner=None,
                   ruby_executable: str | None = None, gem_executable: str | None = None) -> Path:
    gem_home = paths_for(root).gem_home
    ruby = ruby_executable or shutil.which("ruby")
    gem = gem_executable or shutil.which("gem")
    if not ruby:
        raise SetupError("Ruby is required for Bashcov; no system Ruby change was attempted")

    current = bashcov_version(gem_home, ruby, runner=runner)
    if current == BASHCOV_VERSION:
        return gem_home
    if not gem:
        raise SetupError("RubyGems is required to install the pinned local Bashcov dependency")

    gem_home.mkdir(parents=True, exist_ok=True)
    run_checked(
        [ruby, gem, "install", "bashcov", "--version", BASHCOV_VERSION,
         "--install-dir", str(gem_home), "--no-document"],
        env=gem_environment(gem_home),
        runner=runner,
    )
    installed = bashcov_version(gem_home, ruby, runner=runner)
    if installed != BASHCOV_VERSION:
        actual = installed or "unavailable"
        raise SetupError(
            f"Bashcov must load as {BASHCOV_VERSION} from {gem_home}; found {actual}"
        )
    return gem_home


def prepare_tools(root: Path = ROOT, *, runner=None, downloader=None, builder=None,
                  ruby_executable: str | None = None,
                  gem_executable: str | None = None) -> ToolPaths:
    ensure_bashcov(root, runner=runner, ruby_executable=ruby_executable,
                   gem_executable=gem_executable)
    ensure_bash(root, runner=runner, downloader=downloader, builder=builder)
    return paths_for(root)


def _single_line(value: str, label: str) -> str:
    if any(character in value for character in ("\n", "\r", "\0")):
        raise SetupError(f"{label} must fit on one GitHub environment-file line")
    return value


def github_environment_lines(paths: ToolPaths) -> list[str]:
    values = (
        ("BASHCOV_BASH_PATH", paths.bashcov_bash_path),
        ("GEM_HOME", paths.gem_home),
        ("GEM_PATH", paths.gem_path),
    )
    return [f"{key}={_single_line(str(value), key)}" for key, value in values]


def github_path_line(paths: ToolPaths) -> str:
    return _single_line(str(paths.gem_bin), "GEM_HOME/bin")


def _append_lines(path: Path, lines: list[str]) -> None:
    if not path.is_file():
        raise SetupError(f"GitHub environment file does not exist: {path}")
    try:
        with path.open("a", encoding="utf-8", newline="\n") as output:
            for line in lines:
                output.write(line + "\n")
    except OSError as error:
        raise SetupError(f"could not write GitHub environment file {path}: {error}") from error


def write_github_exports(paths: ToolPaths, env_file: Path | None,
                         path_files: list[Path]) -> None:
    env_lines = github_environment_lines(paths) if env_file else []
    path_line = github_path_line(paths) if path_files else ""
    if env_file:
        _append_lines(env_file, env_lines)
    for path_file in path_files:
        _append_lines(path_file, [path_line])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-env", type=Path,
                        help="append BASHCOV_BASH_PATH, GEM_HOME, and GEM_PATH to this runner env file")
    parser.add_argument("--github-path", action="append", type=Path, default=[],
                        help="append GEM_HOME/bin to this runner path file; may be repeated")
    args = parser.parse_args()
    if args.github_env and not args.github_path:
        parser.error("--github-env requires at least one --github-path")
    try:
        paths = prepare_tools()
        write_github_exports(paths, args.github_env, args.github_path)
    except (OSError, SetupError, ValueError) as error:
        parser.exit(1, f"unit tool setup failed: {error}\n")
    print(json.dumps(paths.as_json(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
