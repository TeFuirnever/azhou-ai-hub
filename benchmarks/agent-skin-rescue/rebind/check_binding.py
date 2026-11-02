"""Verify immutable resource and producer bytes; never launch or connect to a host."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from offline_runtime import validate_result


def verify_binding(binding_path, producer_path, *, root):
    root = Path(root)
    if not root.is_absolute() or root.resolve() != root or not root.is_dir():
        raise ValueError("unsafe candidate root")
    observed = {}

    def read(path):
        path = Path(path)
        if not path.is_absolute():
            path = root / path
        if ".." in path.parts or path == root or not path.is_relative_to(root) or path.resolve() != path:
            raise ValueError("path outside registered candidate")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("candidate input is not a regular file")
            chunks = []
            while chunk := os.read(fd, 1024 * 1024):
                chunks.append(chunk)
            after = os.fstat(fd)
            named = path.stat(follow_symlinks=False)
            identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
            if identity(before) != identity(after) or identity(after) != identity(named):
                raise ValueError("candidate input changed while reading")
        finally:
            os.close(fd)
        data = b"".join(chunks)
        digest = hashlib.sha256(data).hexdigest()
        if str(path) in observed and observed[str(path)] != digest:
            raise ValueError("candidate input changed between reads")
        observed[str(path)] = digest
        return data

    def check(path, expected):
        actual = hashlib.sha256(read(path)).hexdigest()
        if actual != expected:
            raise ValueError("digest mismatch: " + str(path))

    binding_path = Path(binding_path)
    producer_path = Path(producer_path)
    bb, pb = read(binding_path), read(producer_path)
    binding, producer = json.loads(bb), json.loads(pb)

    def completed(record):
        try:
            validate_result(record)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid completion receipt") from error
        if (record.get("kind") != "C" or record.get("execution_state") != "exited"
                or type(record.get("exit_code")) is not int or record["exit_code"] != 0
                or record.get("error") is not None or not record.get("inputs_unchanged")
                or not record.get("argument_inputs_unchanged")
                or record.get("evidence_complete") is not True
                or record.get("evidence_errors") != []):
            raise ValueError("producer command is not successfully completed with fixed inputs")
        for field in ["inputs", "argument_inputs"]:
            for item in record.get(field, []):
                check(item["path"], item["sha256"])
        for item in record["outputs"]["raw_files"]:
            check(item["path"], item["sha256"])
        for item in record.get("artifacts", []):
            check(item["source_path"], item["source_sha256"])

    completed(producer)
    relative_binding = str(binding_path.relative_to(root)) if binding_path.is_absolute() else str(binding_path)
    links = [item for item in producer.get("artifacts", [])
             if item.get("source_path") == relative_binding
             and item.get("relation") == "produced"
             and item.get("source_sha256") == hashlib.sha256(bb).hexdigest()]
    if len(links) != 1:
        raise ValueError("binding is not uniquely linked to producer")
    for item in binding["inputs"]:
        check(item["path"], item["sha256"])
    source = Path(binding["source_stage"])
    for relative, expected in binding["source_inputs"].items():
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("unsafe source input")
        check(source / relative, expected)
    for key in ["base_payload", "startup_manifest", "wallpaper", "normal_default_payload", "normal_default_manifest"]:
        if key in binding:
            check(binding[key]["path"], binding[key]["sha256"])
    for item in binding["wrappers"].values():
        check(item["path"], item["sha256"])
    commands = binding["commands"]
    if len(commands) != binding["command_count"] or len({item["path"] for item in commands}) != len(commands):
        raise ValueError("missing or repeated tool command receipt")
    for item in commands:
        check(item["path"], item["sha256"])
        completed(json.loads(read(item["path"])))
    # Revalidate every descriptor-backed byte observation before emitting proof.
    for path, digest in list(observed.items()):
        check(path, digest)
    return {"kind": "A", "status": "verified-resources-only", "source_commit": binding["source_commit"],
            "source_inputs": binding["source_inputs"], "base_payload": binding["base_payload"],
            "startup_manifest": binding["startup_manifest"], "wrappers": binding["wrappers"],
            "binding_sha256": hashlib.sha256(bb).hexdigest(),
            "producer_receipt_sha256": hashlib.sha256(pb).hexdigest(),
            "command_count": len(commands), "host_validation": "not_run",
            "lease": "declaration only; no live lease/status check", "scope": "resource bytes and VM fixtures only"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--producer", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_binding(args.binding, args.producer, root=args.root), sort_keys=True))
