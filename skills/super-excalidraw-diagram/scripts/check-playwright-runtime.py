#!/usr/bin/env python3
"""Check whether the locked Playwright Chromium executable already exists."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys


async def resolve_executable(async_playwright) -> Path:
    async with async_playwright() as playwright:
        return Path(playwright.chromium.executable_path)


def main() -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Playwright Python is missing; run 'uv sync --frozen' in the references directory",
            file=sys.stderr,
        )
        return 3

    try:
        executable = asyncio.run(resolve_executable(async_playwright))
    except Exception as exc:
        print(f"Playwright runtime check failed: {exc}", file=sys.stderr)
        return 1

    if not executable.is_file():
        print(f"Playwright Chromium is missing: {executable}", file=sys.stderr)
        return 2

    print(f"Playwright Chromium is ready: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
