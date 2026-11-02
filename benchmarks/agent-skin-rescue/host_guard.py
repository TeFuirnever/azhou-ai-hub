"""Generate and bind fail-closed Seatbelt file policies; never spawn a process."""
from pathlib import Path
import hashlib
import json
import os
import stat
import sys

WORKTREE = Path(__file__).resolve().parents[2]
ACTUAL_BUNDLE = Path("/Applications/ZCode.app")
DYLD_READ_ROOTS = {Path(value).resolve() for value in (
    "/System/Volumes/Preboot/Cryptexes/OS", "/System/Cryptexes/OS") if Path(value).is_dir()}
PUBLIC_READ_ROOTS = {Path("/System/Library"), Path("/usr/lib"), *DYLD_READ_ROOTS}
HELPER_NAMES = ("ZCode Helper", "ZCode Helper (GPU)", "ZCode Helper (Plugin)", "ZCode Helper (Renderer)")


def _absolute(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\0" in str(path):
        raise ValueError("canonical absolute path required")
    return path


def _inside(path, root):
    return path == root or path.is_relative_to(root)


def _overlap(left, right):
    return _inside(left, right) or _inside(right, left)


def _directory(value):
    path = _absolute(value)
    info = path.lstat()
    if path.resolve() != path or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("canonical owned directory required")
    return path, info


def _file(value):
    path = _absolute(value)
    if path.parent.resolve() != path.parent:
        raise ValueError("file parent alias refused")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("regular single-link input required")
        data = b""
        while part := os.read(fd, 1024 * 1024):
            data += part
        after = os.fstat(fd)
        named = path.lstat()
        identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        if identity(before) != identity(after) or identity(before) != identity(named):
            raise ValueError("input changed during binding")
    finally:
        os.close(fd)
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "device": before.st_dev, "inode": before.st_ino}


def compile_policy(run_root, *, original_bundle, read_roots, executable_paths,
                   read_files=(), protected_paths=(), scope="actual-target-preparation"):
    """Return SBPL plus bindings. This grants no authority to launch a host."""
    if scope not in {"actual-target-preparation", "fixture-only"}:
        raise ValueError("unrecognized scope")
    run, info = _directory(run_root)
    if not run.is_relative_to(WORKTREE / ".scratch") or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("run must be a private owned worktree evidence directory")
    if any(run.iterdir()):
        raise ValueError("fresh empty run required; preexisting aliases refused")
    bundle, _ = _directory(original_bundle)
    if _overlap(run, bundle):
        raise ValueError("run and original bundle must be disjoint")
    if scope == "actual-target-preparation" and bundle != ACTUAL_BUNDLE:
        raise ValueError("actual target is fixed to the original ZCode bundle")
    if scope == "fixture-only" and not bundle.is_relative_to(WORKTREE / ".scratch"):
        raise ValueError("synthetic bundle must be task-owned evidence")
    roots = {_absolute(value) for value in read_roots}
    permitted = set(PUBLIC_READ_ROOTS)
    if scope == "fixture-only":
        permitted.add(Path(sys.base_prefix).resolve())
    if not roots.issubset(permitted):
        raise ValueError("read roots exceed fixed public dependencies")
    for root in roots:
        if root.resolve() != root or not root.is_dir():
            raise ValueError("public dependency root is not canonical")
    protected = {_absolute(value) for value in protected_paths}
    if scope != "fixture-only" and protected:
        raise ValueError("actual default-deny policy does not probe arbitrary private paths")
    for path in protected:
        if (not path.is_relative_to(WORKTREE / ".scratch")
                or path.parent.resolve() != path.parent or not path.parent.is_dir()
                or path.is_symlink()):
            raise ValueError("protected fixture path must have canonical owned-evidence ancestry")
    for path in protected:
        if any(_overlap(path, allowed) for allowed in [run, bundle, *roots]):
            raise ValueError("protected paths overlap an authorized root")
    file_paths = [_absolute(value) for value in read_files]
    if scope != "fixture-only" and file_paths:
        raise ValueError("actual policy has no arbitrary exact read files")
    for path in file_paths:
        if path.parent != run.parent or any(_overlap(path, p) for p in protected):
            raise ValueError("fixture helper must be an exact sibling file outside protected paths")
        if path.parent.resolve() != path.parent or path.is_symlink():
            raise ValueError("fixture read file alias refused")
    files = [_file(path) for path in file_paths]
    executables = [_absolute(value) for value in executable_paths]
    if len(executables) != len(set(executables)) or not executables:
        raise ValueError("unique exact executable allowlist required")
    if scope == "fixture-only":
        interpreter = Path(sys.executable).resolve()
        python_helper = Path(sys.base_prefix).resolve() / "Resources/Python.app/Contents/MacOS/Python"
        allowed_python = {interpreter}
        if python_helper.is_file(): allowed_python.add(python_helper.resolve())
        if interpreter not in executables or not set(executables).issubset(allowed_python):
            raise ValueError("fixture execution is restricted to this Python interpreter and its exact framework helper")
    else:
        main = bundle / "Contents/MacOS/ZCode"
        allowed = {main, *(bundle / ("Contents/Frameworks/" + name + ".app/Contents/MacOS/" + name)
                            for name in HELPER_NAMES)}
        if main not in executables or not set(executables).issubset(allowed):
            raise ValueError("host executable allowlist exceeds fixed main/helper paths")
    bound_exec = [_file(value) for value in executables]
    for executable in executables:
        if scope == "fixture-only" and not any(_inside(executable, p) for p in roots):
            raise ValueError("interpreter read dependency is not declared")
        if any(_overlap(executable, p) for p in protected):
            raise ValueError("executable overlaps protected path")
    q = lambda value: json.dumps(str(value), ensure_ascii=True)
    filters = lambda values, kind: " ".join("(" + kind + " " + q(p) + ")" for p in sorted(values))
    lines = [
        "(version 1)", "(deny default)", "(deny network*)", "(deny mach-lookup)",
        "(deny file-link file-clone)", "(deny file-write-create (vnode-type SYMLINK))",
        "(allow file-read* file-test-existence (literal \"/\"))",
        "(allow system-fcntl (fcntl-command F_ADDFILESIGS_RETURN F_CHECK_LV F_GETPATH))",
        "(with-filter (mac-policy-name \"Sandbox\") (allow system-mac-syscall (mac-syscall-number 2)))",
        "(allow syscall*)", "(allow sysctl-read)", "(allow signal (target self))", "(allow process-fork)",
        "(allow file-read* (literal \"/dev/random\") (literal \"/dev/urandom\"))",
        "(allow file-read* file-write-data (literal \"/dev/null\"))",
        "(allow process-exec " + filters(executables, "literal") + ")",
        "(allow file-read* " + filters([*roots, bundle, run], "subpath") + ")",
        "(allow file-map-executable " + filters([*roots, bundle], "subpath") + ")",
        "(allow file-write* (subpath " + q(run) + "))",
        "(deny file-write* (subpath " + q(bundle) + ") (literal " + q(bundle.parent) + "))",
    ]
    lines.append("(allow file-read-metadata file-test-existence " + filters([run, bundle, *roots, *executables, *(Path(i["path"]) for i in files)], "path-ancestors") + ")")
    if files:
        lines.append("(allow file-read* " + filters([Path(i["path"]) for i in files], "literal") + ")")
    if protected:
        lines.append("(deny file-read* file-write* " + filters(protected, "subpath") + ")")
    text = "\n".join(lines) + "\n"
    manifest = {
        "scope": scope, "hostLaunchAllowed": False, "hostReady": False,
        "policy_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "run": {"path": str(run), "device": info.st_dev, "inode": info.st_ino,
                "uid": info.st_uid, "mode": oct(stat.S_IMODE(info.st_mode)), "initially_empty": True},
        "original_bundle": str(bundle), "original_parent_write_denied": str(bundle.parent),
        "public_read_roots": [str(p) for p in sorted(roots)], "exact_read_files": files,
        "exact_executables": bound_exec, "protected_paths": [str(p) for p in sorted(protected)],
        "basic_runtime_exceptions": ["syscall dispatch; independent file/exec/Mach/network operations remain filtered", "self signal", "declared-path ancestor metadata only", "read-only random devices and /dev/null discard stdio", "public dyld Cryptex roots, root directory descriptor and exact loader fcntl/sandbox-status query"],
        "limitations": [
            "Profile generation is not host launch authorization or a compatibility result.",
            "Mach lookup and network default denied; GUI, default Chrome, OAuth and Keychain compatibility unverified.",
            "Existing independent brokers or already-open descriptors are not magically confined.",
            "Runner must use exact bound policy text, close inherited descriptors and declare stdio exceptions.",
            "Fresh-run check is not a defense against concurrent same-UID ancestor replacement.",
            "Preexisting aliases in public read dependency trees are not proven absent by these executable bindings.",
        ],
    }
    return text, manifest
