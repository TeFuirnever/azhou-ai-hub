"""Keep Windows path components stable while publishing a managed receipt record."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


class _FileTime(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


class _FileInformation(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("creation", _FileTime), ("access", _FileTime), ("write", _FileTime),
        ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD), ("size_low", wintypes.DWORD),
        ("links", wintypes.DWORD), ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD),
    ]


class PathGuard:
    """Pin every path component without granting other handles delete access."""

    def __init__(self) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._open = kernel.CreateFileW
        self._open.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                               wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self._open.restype = wintypes.HANDLE
        self._info = kernel.GetFileInformationByHandle
        self._info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInformation)]
        self._info.restype = wintypes.BOOL
        self._close = kernel.CloseHandle
        self._close.argtypes = [wintypes.HANDLE]
        self._close.restype = wintypes.BOOL
        self._handles: list[int] = []
        self._paths: set[Path] = set()

    def hold(self, path: Path, *, directory: bool) -> None:
        path = path.absolute()
        for parent in reversed(path.parents):
            if parent not in self._paths:
                self._hold_one(parent, directory=True)
        if path not in self._paths:
            self._hold_one(path, directory=directory)

    def _hold_one(self, path: Path, *, directory: bool) -> None:
        # Attribute-only handles do not enforce sharing; request read data or directory listing.
        handle = self._open(str(path), 0x1 | 0x80, 0x1 | 0x2, None, 3, 0x02000000 | 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handles.append(handle)
        info = _FileInformation()
        if not self._info(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
            raise OSError(f"unsafe path component: {path}")
        self._paths.add(path)

    def __enter__(self) -> PathGuard:
        return self

    def __exit__(self, *_args: object) -> None:
        for handle in reversed(self._handles):
            self._close(handle)
