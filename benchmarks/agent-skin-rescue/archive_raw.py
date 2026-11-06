"""Byte-preserving offline archive component. Results are A, never command exits."""
import hashlib
import json
import os
from pathlib import Path
import stat
from offline_runtime import own, json_new, utc, scope_root, validate_result


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_uid, info.st_mode, info.st_nlink)


def directory_identity(info):
    # Directory link counts can change on file creation (including APFS).
    # Bind the inode, owner and permission bits without freezing directory contents.
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode)


def directory(path, *, root):
    path = own(path, root=root)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        named = os.stat(path, follow_symlinks=False)
        if (info.st_uid != os.getuid() or info.st_mode & 0o077
                or directory_identity(info) != directory_identity(named)):
            raise ValueError("directory identity or permissions unverified")
        return fd, directory_identity(info)
    except BaseException:
        os.close(fd)
        raise


def copy_raw(source, destination, producer_receipt, *, after_open=None, writer=os.write, root=None):
    root = scope_root(root)
    source, destination, producer_receipt = [own(p, root=root) for p in (source, destination, producer_receipt)]
    rdir = rfd = None
    try:
        rdir, rid = directory(producer_receipt.parent, root=root)
        rfd = os.open(producer_receipt.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=rdir)
        rbefore = os.fstat(rfd)
        rnamed = os.stat(producer_receipt.name, dir_fd=rdir, follow_symlinks=False)
        if (not stat.S_ISREG(rbefore.st_mode) or rbefore.st_uid != os.getuid()
                or rbefore.st_mode & 0o077 or rbefore.st_nlink != 1
                or identity(rbefore) != identity(rnamed)):
            raise ValueError("producer receipt identity or permissions unverified")
        chunks = []
        while data := os.read(rfd, 65536):
            chunks.append(data)
        receipt_bytes = b"".join(chunks)
        producer = json.loads(receipt_bytes)
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        return _copy_bound(source, destination, producer_receipt, producer, receipt_sha,
                           rdir, rid, rfd, rbefore, after_open=after_open, writer=writer, root=root)
    finally:
        for fd in (rfd, rdir):
            if fd is not None:
                os.close(fd)


def _copy_bound(source, destination, producer_receipt, producer, receipt_sha,
                rdir, rid, rfd, rbefore, *, after_open, writer, root):
    validate_result(producer)
    if producer.get("kind") != "C" or producer.get("exit_code") is None:
        raise ValueError("source producer completion is unverified")
    source_rel = str(source.relative_to(root))
    matches = [x for x in producer["outputs"]["raw_files"] if x["path"] == source_rel]
    if len(matches) != 1:
        raise ValueError("source is not bound to producer bytes")
    sdir = ddir = sfd = dfd = None
    result = {"kind": "A", "observed_at": utc(), "relation": "copied",
              "producer_receipt": str(producer_receipt.relative_to(root)),
              "producer_receipt_sha256": receipt_sha, "source_path": source_rel,
              "archive_path": str(destination.relative_to(root)), "status": "not_started",
              "source_sha256": None, "archive_sha256": None,
              "scope": "synthetic-only; permission bits are not same-UID isolation"}
    try:
        sdir, sid = directory(source.parent, root=root)
        ddir, did = directory(destination.parent, root=root)
        sfd = os.open(source.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=sdir)
        before = os.fstat(sfd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or before.st_mode & 0o077 or before.st_nlink != 1
                or identity(before) != identity(os.stat(source.name, dir_fd=sdir, follow_symlinks=False))):
            raise ValueError("source identity or permissions unverified")
        dfd = os.open(destination.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600, dir_fd=ddir)
        dest_before = os.fstat(dfd)
        dest_identity = (dest_before.st_dev, dest_before.st_ino)
        result["status"] = "partial"
        if after_open:
            after_open(source, destination)
        while True:
            data = os.read(sfd, 65536)
            if not data:
                break
            view = memoryview(data)
            while view:
                n = writer(dfd, view)
                if n <= 0:
                    raise OSError("archive short write")
                view = view[n:]
        os.fsync(dfd)
        dest_written = os.fstat(dfd)
        # Read both bound descriptors, not a potentially replaced pathname.
        import hashlib
        def digest(fd):
            os.lseek(fd, 0, os.SEEK_SET)
            h = hashlib.sha256()
            while data := os.read(fd, 65536):
                h.update(data)
            return h.hexdigest()
        result["source_sha256"], result["archive_sha256"] = digest(sfd), digest(dfd)
        snamed = os.stat(source.name, dir_fd=sdir, follow_symlinks=False)
        dnamed = os.stat(destination.name, dir_fd=ddir, follow_symlinks=False)
        if (identity(before) != identity(os.fstat(sfd)) or identity(before) != identity(snamed)
                or (dnamed.st_dev, dnamed.st_ino) != dest_identity or not stat.S_ISREG(dnamed.st_mode)
                or identity(dest_written) != identity(os.fstat(dfd))
                or identity(dest_written) != identity(dnamed)
                or dnamed.st_uid != dest_before.st_uid or dnamed.st_mode != dest_before.st_mode
                or dnamed.st_uid != os.getuid() or dnamed.st_mode & 0o077 or dnamed.st_nlink != 1
                or result["source_sha256"] != result["archive_sha256"]
                or result["source_sha256"] != matches[0]["sha256"]):
            raise ValueError("source or destination changed during archive")
        rnamed = os.stat(producer_receipt.name, dir_fd=rdir, follow_symlinks=False)
        if (identity(rbefore) != identity(os.fstat(rfd))
                or identity(rbefore) != identity(rnamed)):
            raise ValueError("producer receipt changed during archive")
        for path, fd, expected in [(source.parent, sdir, sid), (destination.parent, ddir, did),
                                   (producer_receipt.parent, rdir, rid)]:
            now = os.stat(path, follow_symlinks=False)
            if (directory_identity(now) != expected or directory_identity(os.fstat(fd)) != expected
                    or not stat.S_ISDIR(now.st_mode)):
                raise ValueError("directory pathname no longer identifies bound fd")
        os.fsync(ddir)
        result["status"] = "complete"
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        for fd in (sfd, dfd, sdir, ddir):
            if fd is not None:
                os.close(fd)
    return result


if __name__ == "__main__":
    raise SystemExit("OFFLINE LIBRARY: direct archival execution disabled")
