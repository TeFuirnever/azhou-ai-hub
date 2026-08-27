#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import overlap_contract as c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command_or_scene", nargs="?")
    ap.add_argument("scene", nargs="?")
    ap.add_argument("--scene", dest="scene_opt")
    ap.add_argument("--margin", type=float, default=3.0)
    ap.add_argument("--output")
    args = ap.parse_args()
    detect_mode = args.command_or_scene == "detect"
    scene = args.scene_opt or (args.scene if detect_mode else args.command_or_scene)

    try:
        if not scene:
            raise c.ContractError("E_SCHEMA")
        raw = json.loads(Path(scene).read_text(encoding="utf-8"))
        record = c.detect_scene(raw, args.margin)
        if detect_mode or args.output:
            if not args.output:
                raise c.ContractError("E_OUTPUT")
            c.write_atomic(args.output, record)
            return 1 if record["state"] == "issues" else 0

        elements = raw.get("elements", [])
        rectangles = [
            element
            for element in elements
            if isinstance(element, dict) and element.get("type") == "rectangle"
        ]

        def icon_prefix(identifier):
            bits = identifier.split("_")
            return "_".join(bits[:2]) if len(bits) > 1 else identifier

        def label(rectangle):
            for bound_element in rectangle.get("boundElements") or []:
                if bound_element.get("type") == "text":
                    text_element = next(
                        (
                            element
                            for element in elements
                            if element.get("id") == bound_element.get("id")
                        ),
                        None,
                    )
                    if text_element:
                        return str(text_element.get("text", "")).split("\n")[0][:30]
            return str(rectangle.get("id", ""))[:12]

        # Legacy mode retains the human-readable labels, exemptions and fix hints.
        visible_issues = 0
        for issue in record["issues"]:
            ids = issue["subject_ids"]
            if issue["code"] == "TEXT_TEXT":
                first = next(element for element in elements if element.get("id") == ids[0])
                second = next(element for element in elements if element.get("id") == ids[1])
                print(
                    f"TEXT-TEXT: {first.get('text', '')[:20]!r} <-> "
                    f"{second.get('text', '')[:20]!r} — fixes: move one label | "
                    "shorten wording | wrap with \\n"
                )
                visible_issues += 1
            elif issue["code"] == "NESTING":
                child = next(element for element in elements if element.get("id") == ids[0])
                parent = next(element for element in elements if element.get("id") == ids[1])
                print(
                    f"NESTING: [{label(child)}] pokes out of [{label(parent)}] — "
                    "fixes: resize child to fit | move child fully outside | "
                    "grow parent with 50-60px padding"
                )
                visible_issues += 1
            else:
                rectangle = next(rect for rect in rectangles if rect.get("id") == ids[0])
                element = next(item for item in elements if item.get("id") == ids[1])
                same_group = set(element.get("groupIds") or []) & set(
                    rectangle.get("groupIds") or []
                )
                same_icon = icon_prefix(element.get("id", "")) == icon_prefix(
                    rectangle.get("id", "")
                )
                if same_group or same_icon:
                    continue
                text = element.get("text", element.get("id", "")[:14])
                text = text.replace(chr(10), "/")[:30]
                print(
                    f"STRADDLE: [{label(rectangle)}] <- {element.get('type')} "
                    f"'{text}' — fixes: move element fully inside/outside | "
                    "shrink an inflated declared width to the rendered text"
                )
                visible_issues += 1
        print(f"GEOMETRY ISSUES: {visible_issues}")
        return 1 if visible_issues else 0
    except c.ContractError as error:
        print(str(error), file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"E_SCHEMA: {error}", file=sys.stderr)
        return 2
    except (OSError, KeyError, TypeError, AttributeError) as error:
        print(f"E_IO: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
