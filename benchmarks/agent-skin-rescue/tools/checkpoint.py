"""Create an exclusive, verified external checkpoint of committed safe rescue source."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile


def checkpoint(repository, destination):
    repository, destination = Path(repository).resolve(), Path(destination).resolve()
    if destination.is_relative_to(repository):
        raise ValueError("checkpoint must be outside the working tree")
    prefix = "benchmarks/agent-skin-rescue"
    changed = subprocess.check_output(
        ["git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=no", "--", prefix],
        cwd=repository, text=True, encoding="utf-8",
    )
    if changed:
        raise ValueError("commit safe rescue source before checkpointing")
    untracked = subprocess.check_output(
        ["git", "--no-optional-locks", "ls-files", "--others", "--exclude-standard", "--", prefix],
        cwd=repository, text=True, encoding="utf-8",
    ).splitlines()
    if any(not name.startswith(prefix + "/.scratch/") for name in untracked):
        raise ValueError("uncommitted safe source is not in the checkpoint")
    head = subprocess.check_output(
        ["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=repository, text=True, encoding="utf-8",
    ).strip()
    archive = subprocess.check_output(
        ["git", "--no-optional-locks", "archive", "--format=tar", head, prefix],
        cwd=repository,
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as handle:
        members = handle.getmembers()
        for member in members:
            path = Path(member.name)
            contained = path.is_relative_to(prefix)
            ancestor = member.isdir() and Path(prefix).is_relative_to(path)
            if path.is_absolute() or ".." in path.parts or not (contained or ancestor):
                raise ValueError("unsafe archive path")
            if not member.isdir() and not member.isfile():
                raise ValueError("archive contains links or special files")
        files = [
            {"path": member.name, "bytes": member.size,
             "sha256": hashlib.sha256(handle.extractfile(member).read()).hexdigest()}
            for member in members if member.isfile()
        ]
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    path = destination / "safe-source.tar"
    with path.open("xb") as handle:
        handle.write(archive)
    os.chmod(path, 0o600)
    digest = hashlib.sha256(archive).hexdigest()
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError("checkpoint reread mismatch")
    manifest = {"commit": head, "archive_sha256": digest, "files": files,
                "scope": "committed safe source; raw evidence and private assets excluded"}
    with (destination / "manifest.json").open("x") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    os.chmod(destination / "manifest.json", 0o600)
    print(json.dumps({"commit": head, "destination": str(destination),
                      "verified_files": len(files), "archive_sha256": digest}))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("destination")
    args = parser.parse_args()
    checkpoint(args.repository, args.destination)
