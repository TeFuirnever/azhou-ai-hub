"""Run unchanged repository gates with private fixtures outside public file inventory."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
WORKTREE = SOURCE.parents[1]
PRIVATE_RUNTIME_PREFIXES = (b".scratch/", b"benchmarks/agent-skin-rescue/.scratch/")


def private_path(value):
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts or path.resolve() != path
            or not path.is_relative_to(WORKTREE / ".scratch")):
        raise ValueError("verification state must be canonical and inside this worktree's scratch")
    return path


def child():
    home, temporary = (private_path(os.environ[name]) for name in ("HOME", "TMPDIR"))
    for path in (home, temporary):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("verification HOME and TMPDIR must be private")
    environment = {key: os.environ[key] for key in
                   ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "HOME", "TMPDIR",
                    "SWIFT_MODULECACHE_PATH", "CLANG_MODULE_CACHE_PATH") if key in os.environ}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    excludes = temporary.parent / "verification-runtime-excludes"
    with excludes.open("x", encoding="utf-8") as handle:
        handle.write("/.scratch/\n/benchmarks/agent-skin-rescue/.scratch/\n")
    os.chmod(excludes, 0o600)
    # Process-local Git configuration. No repository/global config or source is changed.
    environment.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.excludesFile",
                       GIT_CONFIG_VALUE_0=str(excludes),
                       GIT_CEILING_DIRECTORIES=str(temporary))
    tracked = set(subprocess.check_output(
        ["git", "ls-files", "-z", "--cached"], cwd=WORKTREE, env=environment,
    ).split(b"\0")) - {b""}
    public = set(subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=WORKTREE, env=environment,
    ).split(b"\0")) - {b""}
    if not tracked.issubset(public) or any(name.startswith(PRIVATE_RUNTIME_PREFIXES) for name in tracked):
        raise ValueError("runtime exclusion must never hide a tracked source")
    if any(name.startswith(PRIVATE_RUNTIME_PREFIXES) for name in public):
        raise ValueError("private malformed fixtures remained in public inventory")
    metadata = {
        "scope": "all tracked source plus ordinary public files; untracked scratch is private runtime state",
        "tracked_file_count": len(tracked), "all_tracked_files_included": True,
        "runtime_exclusions": ["/.scratch/", "/benchmarks/agent-skin-rescue/.scratch/"], "temporary_git_discovery_ceiling": str(temporary),
        "reason": "independent-project fixtures must not inherit the enclosing repository remote",
        "repository_or_global_git_config_changed": False,
    }
    with (temporary.parent / "verification-scope.json").open("x", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")
    result = subprocess.run(
        [sys.executable, "-B", "scripts/verify.py", "--print-summary"],
        cwd=WORKTREE, env=environment, check=False,
    )
    return result.returncode


def run(output):
    sys.path.insert(0, str(SOURCE))
    from command_log import CommandLog
    output = private_path(output)
    if output.exists() or output.parent.resolve() != output.parent:
        raise ValueError("new verification output required")
    output.mkdir(mode=0o700)
    names = subprocess.check_output(
        ["git", "--no-optional-locks", "ls-files", "--", "benchmarks/agent-skin-rescue"],
        cwd=WORKTREE, text=True, encoding="utf-8",
    ).splitlines()
    names += ["scripts/verify.py", "scripts/check_repository.py", "scripts/verify_packages.py"]
    inputs = [{"path": name, "sha256": hashlib.sha256((WORKTREE / name).read_bytes()).hexdigest()}
              for name in names]
    result = CommandLog(output, inputs, root=WORKTREE).record(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--child"],
        cwd=WORKTREE, timeout=600,
    )
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if not args.child and args.out is None:
        parser.error("--out is required")
    raise SystemExit(child() if args.child else run(args.out))
