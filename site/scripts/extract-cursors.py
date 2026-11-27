#!/usr/bin/env python3
"""Extract static 1x (32px) and 2x (64px) PNG cursors from Azhou-Double-Hug-3.6.1.cape."""

from __future__ import annotations

import argparse
import io
import plistlib
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPE_PATH = REPO_ROOT / "assets" / "cursors" / "azhou-double-hug" / "Azhou-Double-Hug-3.6.1.cape"
OUT_DIR = REPO_ROOT / "site" / "assets" / "cursors"

# (output stem, cape cursor key, frame index)
SPECS: list[tuple[str, str, int]] = [
    ("arrow", "com.apple.coregraphics.Arrow", 0),
    ("pointer", "com.apple.cursor.13", 0),
    ("text", "com.apple.coregraphics.IBeam", 0),
    ("grab", "com.apple.cursor.12", 0),
    ("grabbing", "com.apple.cursor.11", 1),
]


def extract_frame(strip_bytes: bytes, size: int, frame_index: int) -> bytes:
    """Crop a single square frame from a vertical sprite strip and return deterministic PNG bytes."""
    with Image.open(io.BytesIO(strip_bytes)) as strip:
        expected_width = size
        if strip.width != expected_width or strip.height < size * (frame_index + 1):
            raise ValueError(
                f"Unexpected strip size {strip.size} for size={size}, frame={frame_index}"
            )
        top = size * frame_index
        frame = strip.crop((0, top, size, top + size)).convert("RGBA")
        buf = io.BytesIO()
        frame.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def expected_outputs(cape_path: Path = CAPE_PATH) -> dict[str, bytes]:
    data = plistlib.loads(cape_path.read_bytes())
    cursors = data["Cursors"]
    outputs: dict[str, bytes] = {}
    for stem, key, frame_index in SPECS:
        entry = cursors[key]
        reps = entry["Representations"]
        if len(reps) < 2:
            raise ValueError(f"Cursor {key} has fewer than 2 representations")
        outputs[f"{stem}.png"] = extract_frame(reps[0], 32, frame_index)
        outputs[f"{stem}@2x.png"] = extract_frame(reps[1], 64, frame_index)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cape", type=Path, default=CAPE_PATH)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that committed cursor PNGs match the extracted outputs.",
    )
    args = parser.parse_args()

    outputs = expected_outputs(args.cape)
    if args.check:
        mismatches: list[str] = []
        for filename, expected in outputs.items():
            target = args.out_dir / filename
            if not target.is_file():
                mismatches.append(f"missing: {target}")
            elif target.read_bytes() != expected:
                mismatches.append(f"stale: {target}")
        if mismatches:
            for msg in mismatches:
                print(msg, file=sys.stderr)
            return 1
        print(f"OK: {len(outputs)} cursor PNGs match {args.cape.name}")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in outputs.items():
        (args.out_dir / filename).write_bytes(payload)
    print(f"Wrote {len(outputs)} cursor PNGs to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
