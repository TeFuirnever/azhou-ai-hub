#!/usr/bin/env python3
"""Persist portable Spec Relay review state inside an HTML artifact."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any
import uuid


SCHEMA = "spec-relay.html-state.v1"
DISPOSITIONS = {"accepted", "rejected", "deferred", "needs_clarification"}
UNRESOLVED_DISPOSITIONS = {"deferred", "needs_clarification"}
STATE_PATTERN = re.compile(
    r'<script\s+type="application/json"\s+id="spec-relay-state">\s*(.*?)\s*</script>',
    re.DOTALL,
)
LEDGER_PATTERN = re.compile(
    r"<!-- spec-relay-ledger:start -->.*?<!-- spec-relay-ledger:end -->",
    re.DOTALL,
)
REVIEW_ID_PATTERN = re.compile(r'data-review-id=["\']([^"\']+)["\']')
FEEDBACK_ID_PATTERN = re.compile(r"FB-\d{3,}")
REVIEW_STATUSES = {"draft", "in_review", "approved", "held"}


class RelayStateError(ValueError):
    """Raised when an HTML packet violates the Spec Relay contract."""


def _read(path: Path) -> str:
    if not path.is_file():
        raise RelayStateError(f"HTML file not found: {path}")
    return path.read_text(encoding="utf-8")


def _atomic_write(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.spec-relay.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        try:
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _state_revision(state: dict[str, Any]) -> int:
    revision = state.get("state_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise RelayStateError("state_revision must be a non-negative integer")
    return revision


def _assert_expected_revision(state: dict[str, Any], expected_revision: int) -> None:
    actual_revision = _state_revision(state)
    if actual_revision != expected_revision:
        raise RelayStateError(
            f"stale state revision: expected {expected_revision}, current {actual_revision}"
        )


def _recompute_unresolved(state: dict[str, Any]) -> None:
    feedback = state.get("feedback")
    if not isinstance(feedback, list):
        raise RelayStateError("feedback must be a list")
    state["unresolved"] = sorted(
        item["feedback_id"]
        for item in feedback
        if isinstance(item, dict) and item.get("disposition") in UNRESOLVED_DISPOSITIONS
    )


def _advance_state(state: dict[str, Any], updated_at: str | None) -> None:
    state["state_revision"] = _state_revision(state) + 1
    state["updated_at"] = updated_at or _utc_now()


def _safe_json(state: dict[str, Any]) -> str:
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
    return payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _load_state(html: str) -> dict[str, Any]:
    matches = STATE_PATTERN.findall(html)
    if len(matches) != 1:
        raise RelayStateError(f"expected one spec-relay-state block, found {len(matches)}")
    try:
        state = json.loads(matches[0])
    except (ValueError, RecursionError) as exc:
        raise RelayStateError(f"invalid embedded state JSON: {exc}") from exc
    if not isinstance(state, dict):
        raise RelayStateError("embedded state must be a JSON object")
    return state


def _render_ledger(feedback: list[dict[str, Any]]) -> str:
    counts = {disposition: 0 for disposition in sorted(DISPOSITIONS)}
    for item in feedback:
        disposition = str(item.get("disposition", ""))
        if disposition in counts:
            counts[disposition] += 1
    unresolved_count = counts["deferred"] + counts["needs_clarification"]
    if feedback:
        cards = []
        for item in feedback:
            disposition = escape(str(item["disposition"]), quote=True)
            cards.append(
                '<li class="spec-relay-feedback-card" data-feedback-id="{feedback_id}">'
                '<header class="spec-relay-feedback-card__header">'
                '<code class="spec-relay-feedback-id">{feedback_id}</code>'
                '<span class="spec-relay-feedback-status spec-relay-feedback-status--{disposition}">'
                "{disposition}</span></header>"
                '<blockquote class="spec-relay-feedback-comment">{comment}</blockquote>'
                '<dl class="spec-relay-feedback-meta">'
                '<div><dt>Target</dt><dd>{target}</dd></div>'
                '<div><dt>Selection</dt><dd>{selection}</dd></div>'
                '<div><dt>Owner</dt><dd>{owner}</dd></div>'
                '<div><dt>Source change</dt><dd>{source_change}</dd></div>'
                '<div><dt>Created</dt><dd>{created_at}</dd></div>'
                '<div><dt>Updated</dt><dd>{updated_at}</dd></div>'
                '</dl><div class="spec-relay-feedback-rationale">'
                '<strong>Disposition rationale</strong><p>{rationale}</p></div></li>'.format(
                    feedback_id=escape(str(item["feedback_id"]), quote=True),
                    disposition=disposition,
                    target=escape(str(item["target"])),
                    comment=escape(str(item["comment"])),
                    selection=escape(str(item["selection"])),
                    rationale=escape(str(item["rationale"])),
                    owner=escape(str(item["owner"])),
                    source_change=escape(str(item["source_change"])),
                    created_at=escape(str(item["created_at"])),
                    updated_at=escape(str(item["updated_at"])),
                )
            )
        body = '<ol class="spec-relay-feedback-list">\n' + "\n".join(cards) + "\n</ol>"
    else:
        body = (
            '<div class="spec-relay-feedback-empty" data-feedback-empty="true">'
            "No persisted feedback yet.</div>"
        )
    return (
        '<!-- spec-relay-ledger:start -->\n'
        '<style id="spec-relay-feedback-style">\n'
        '#spec-relay-feedback-ledger{--sr-bg:var(--color-base-100,#fff);'
        '--sr-fg:var(--color-base-content,#172033);'
        '--sr-muted:color-mix(in srgb,var(--sr-fg) 68%,transparent);'
        '--sr-border:color-mix(in srgb,var(--sr-fg) 14%,transparent);'
        '--sr-accent:var(--color-primary,#2563eb);color:var(--sr-fg);background:var(--sr-bg);'
        'border:1px solid var(--sr-border);border-radius:1rem;padding:clamp(1rem,3vw,1.5rem);'
        'font:inherit;min-width:0;box-sizing:border-box;width:min(calc(100% - 2rem),72rem);'
        'margin:clamp(1rem,4vw,3rem) auto}#spec-relay-feedback-ledger *{box-sizing:border-box}'
        '.spec-relay-feedback-header{display:flex;align-items:flex-start;justify-content:space-between;'
        'gap:1rem;flex-wrap:wrap}.spec-relay-feedback-eyebrow{margin:0 0 .25rem;color:var(--sr-accent);'
        'font-size:.75rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}'
        '#spec-relay-feedback-title{margin:0;font-size:clamp(1.25rem,4vw,1.75rem);line-height:1.2}'
        '.spec-relay-feedback-summary{margin:0;color:var(--sr-muted);font-size:.875rem}'
        '.spec-relay-feedback-list{display:grid;grid-template-columns:minmax(0,1fr);gap:.875rem;'
        'list-style:none;margin:1rem 0 0;padding:0;min-width:0}'
        '.spec-relay-feedback-card{min-width:0;border:1px solid var(--sr-border);border-radius:.875rem;'
        'padding:1rem;background:color-mix(in srgb,var(--sr-bg) 96%,var(--sr-accent) 4%)}'
        '.spec-relay-feedback-card__header{display:flex;align-items:center;justify-content:space-between;'
        'gap:.75rem;flex-wrap:wrap}.spec-relay-feedback-id{font:700 .8125rem/1.4 ui-monospace,SFMono-Regular,'
        'Menlo,monospace;color:var(--sr-accent);overflow-wrap:anywhere}'
        '.spec-relay-feedback-status{border-radius:999px;padding:.25rem .625rem;font-size:.75rem;'
        'font-weight:800;overflow-wrap:anywhere}.spec-relay-feedback-status--accepted{background:#dcfce7;color:#166534}'
        '.spec-relay-feedback-status--rejected{background:#fee2e2;color:#991b1b}'
        '.spec-relay-feedback-status--deferred{background:#fef3c7;color:#92400e}'
        '.spec-relay-feedback-status--needs_clarification{background:#dbeafe;color:#1e40af}'
        '.spec-relay-feedback-comment{margin:.875rem 0;padding:.75rem 1rem;border-inline-start:.25rem solid '
        'var(--sr-accent);background:var(--sr-bg);border-radius:.25rem .625rem .625rem .25rem;'
        'white-space:pre-wrap;overflow-wrap:anywhere}.spec-relay-feedback-meta{display:grid;'
        'grid-template-columns:repeat(2,minmax(0,1fr));gap:.625rem;margin:0}'
        '.spec-relay-feedback-meta div{min-width:0}.spec-relay-feedback-meta dt{color:var(--sr-muted);'
        'font-size:.6875rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase}'
        '.spec-relay-feedback-meta dd{margin:.125rem 0 0;overflow-wrap:anywhere}'
        '.spec-relay-feedback-rationale{margin-top:.75rem;padding-top:.75rem;border-top:1px solid var(--sr-border);'
        'min-width:0}.spec-relay-feedback-rationale strong{font-size:.75rem}.spec-relay-feedback-rationale p{'
        'margin:.25rem 0 0;white-space:pre-wrap;overflow-wrap:anywhere}.spec-relay-feedback-empty{'
        'margin-top:1rem;padding:1rem;border:1px dashed var(--sr-border);border-radius:.75rem;'
        'color:var(--sr-muted);text-align:center}@media(max-width:36rem){.spec-relay-feedback-meta{'
        'grid-template-columns:minmax(0,1fr)}#spec-relay-feedback-ledger{border-radius:.75rem}}\n'
        "</style>\n"
        '<section id="spec-relay-feedback-ledger" data-review-id="RELAY-FEEDBACK" '
        'aria-labelledby="spec-relay-feedback-title">\n'
        '<header class="spec-relay-feedback-header"><div><p class="spec-relay-feedback-eyebrow">'
        'Spec Relay</p><h2 id="spec-relay-feedback-title">Review feedback</h2></div>'
        f'<p class="spec-relay-feedback-summary">{len(feedback)} comments · '
        f"{unresolved_count} unresolved</p></header>\n{body}\n</section>\n"
        "<!-- spec-relay-ledger:end -->"
    )


def _state_block(state: dict[str, Any]) -> str:
    return (
        '<script type="application/json" id="spec-relay-state">\n'
        f"{_safe_json(state)}\n"
        "</script>"
    )


def _replace_packet_state(html: str, state: dict[str, Any]) -> str:
    feedback = state.get("feedback", [])
    if not isinstance(feedback, list):
        raise RelayStateError("feedback must be a list")
    updated = STATE_PATTERN.sub(lambda _: _state_block(state), html, count=1)
    if not LEDGER_PATTERN.search(updated):
        raise RelayStateError("spec-relay feedback ledger markers are missing")
    return LEDGER_PATTERN.sub(lambda _: _render_ledger(feedback), updated, count=1)


def _inject_packet_state(html: str, state: dict[str, Any]) -> str:
    if STATE_PATTERN.search(html) or LEDGER_PATTERN.search(html):
        raise RelayStateError("Spec Relay state already exists")
    insertion = f"{_render_ledger([])}\n{_state_block(state)}\n"
    body_close = re.search(r"</body\s*>", html, re.IGNORECASE)
    if body_close:
        return html[: body_close.start()] + insertion + html[body_close.start() :]
    return html + "\n" + insertion


def _review_ids(html: str) -> list[str]:
    return REVIEW_ID_PATTERN.findall(html)


def _validation_errors(
    html: str, state: dict[str, Any], *, check_ledger: bool = True
) -> list[str]:
    errors: list[str] = []
    if state.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if not isinstance(state.get("packet_id"), str) or not state["packet_id"]:
        errors.append("packet_id must be a non-empty string")
    revision = state.get("state_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        errors.append("state_revision must be a non-negative integer")
    for field in ("handoff_to", "updated_at"):
        if not isinstance(state.get(field), str) or not state[field]:
            errors.append(f"{field} must be a non-empty string")
    source = state.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        for field in ("spec", "revision", "review_goal", "review_status"):
            if not isinstance(source.get(field), str) or not source[field]:
                errors.append(f"source.{field} must be a non-empty string")
        review_status = source.get("review_status")
        if not isinstance(review_status, str) or review_status not in REVIEW_STATUSES:
            errors.append("source.review_status is invalid")

    review_ids = _review_ids(html)
    if len(review_ids) != len(set(review_ids)):
        errors.append("data-review-id values must be unique")
    review_id_set = set(review_ids)

    feedback = state.get("feedback")
    if not isinstance(feedback, list):
        errors.append("feedback must be a list")
        feedback = []
    feedback_ids: list[str] = []
    for index, item in enumerate(feedback):
        prefix = f"feedback[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        feedback_id = item.get("feedback_id")
        if not isinstance(feedback_id, str) or not FEEDBACK_ID_PATTERN.fullmatch(feedback_id):
            errors.append(f"{prefix}.feedback_id must match FB-###")
        else:
            feedback_ids.append(feedback_id)
        for field in (
            "target",
            "comment",
            "selection",
            "disposition",
            "rationale",
            "source_change",
            "owner",
            "created_at",
            "updated_at",
        ):
            if not isinstance(item.get(field), str) or not item[field]:
                errors.append(f"{prefix}.{field} must be a non-empty string")
        target = item.get("target")
        selection = item.get("selection")
        target_resolves = isinstance(target, str) and target in review_id_set
        if not target_resolves and selection in (None, "", "none"):
            errors.append(f"{prefix} target does not resolve and has no selection")
        disposition = item.get("disposition")
        if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
            errors.append(f"{prefix}.disposition is invalid")
    if len(feedback_ids) != len(set(feedback_ids)):
        errors.append("feedback_id values must be unique")

    expected_unresolved = sorted(
        item["feedback_id"]
        for item in feedback
        if isinstance(item, dict)
        and isinstance(item.get("disposition"), str)
        and item.get("disposition") in UNRESOLVED_DISPOSITIONS
        and isinstance(item.get("feedback_id"), str)
    )
    unresolved = state.get("unresolved")
    if unresolved != expected_unresolved:
        errors.append("unresolved must equal deferred and needs_clarification feedback IDs")
    if check_ledger:
        ledger_match = LEDGER_PATTERN.search(html)
        if not ledger_match:
            errors.append("spec-relay feedback ledger markers are missing")
        else:
            try:
                expected_ledger = _render_ledger(feedback)
            except (KeyError, TypeError, AttributeError):
                expected_ledger = None
            if expected_ledger is not None and ledger_match.group(0) != expected_ledger:
                errors.append("visible ledger must be the exact projection of embedded feedback")
    return errors


def _persist_state(path: Path, html: str, state: dict[str, Any]) -> None:
    updated = _replace_packet_state(html, state)
    errors = _validation_errors(updated, state)
    if errors:
        raise RelayStateError("; ".join(errors))
    _atomic_write(path, updated)


def command_init(args: argparse.Namespace) -> None:
    path = Path(args.html)
    html = _read(path)
    updated_at = args.updated_at or _utc_now()
    state = {
        "feedback": [],
        "handoff_to": args.handoff_to,
        "packet_id": args.packet_id or str(uuid.uuid4()),
        "schema": SCHEMA,
        "source": {
            "review_goal": args.review_goal,
            "review_status": args.review_status,
            "revision": args.source_revision,
            "spec": args.source_spec,
        },
        "state_revision": 0,
        "unresolved": [],
        "updated_at": updated_at,
    }
    updated = _inject_packet_state(html, state)
    errors = _validation_errors(updated, state)
    if errors:
        raise RelayStateError("; ".join(errors))
    _atomic_write(path, updated)
    print(f"initialized {SCHEMA}: {path}")


def command_add_feedback(args: argparse.Namespace) -> None:
    path = Path(args.html)
    html = _read(path)
    state = _load_state(html)
    existing_errors = _validation_errors(html, state)
    if existing_errors:
        raise RelayStateError("existing packet is invalid: " + "; ".join(existing_errors))
    _assert_expected_revision(state, args.expected_revision)
    feedback = state["feedback"]
    if any(item.get("feedback_id") == args.feedback_id for item in feedback):
        raise RelayStateError(f"duplicate feedback_id: {args.feedback_id}")
    created_at = args.created_at or _utc_now()
    feedback.append(
        {
            "comment": args.comment,
            "created_at": created_at,
            "disposition": args.disposition,
            "feedback_id": args.feedback_id,
            "owner": args.owner,
            "rationale": args.rationale,
            "selection": args.selection,
            "source_change": args.source_change,
            "target": args.target,
            "updated_at": args.updated_at or created_at,
        }
    )
    _recompute_unresolved(state)
    _advance_state(state, args.updated_at)
    _persist_state(path, html, state)
    print(f"persisted {args.feedback_id}: {path}")


def command_update_feedback(args: argparse.Namespace) -> None:
    path = Path(args.html)
    html = _read(path)
    state = _load_state(html)
    existing_errors = _validation_errors(html, state)
    if existing_errors:
        raise RelayStateError("existing packet is invalid: " + "; ".join(existing_errors))
    _assert_expected_revision(state, args.expected_revision)
    changes = {
        "comment": args.comment,
        "selection": args.selection,
        "disposition": args.disposition,
        "rationale": args.rationale,
        "source_change": args.source_change,
        "owner": args.owner,
    }
    if not any(value is not None for value in changes.values()):
        raise RelayStateError("update-feedback requires at least one changed field")
    item = next(
        (entry for entry in state["feedback"] if entry["feedback_id"] == args.feedback_id),
        None,
    )
    if item is None:
        raise RelayStateError(f"feedback_id not found: {args.feedback_id}")
    for field, value in changes.items():
        if value is not None:
            item[field] = value
    item["updated_at"] = args.updated_at or _utc_now()
    _recompute_unresolved(state)
    _advance_state(state, item["updated_at"])
    _persist_state(path, html, state)
    print(f"updated {args.feedback_id}: {path}")


def command_update_metadata(args: argparse.Namespace) -> None:
    path = Path(args.html)
    html = _read(path)
    state = _load_state(html)
    existing_errors = _validation_errors(html, state)
    if existing_errors:
        raise RelayStateError("existing packet is invalid: " + "; ".join(existing_errors))
    _assert_expected_revision(state, args.expected_revision)
    changes = {
        "revision": args.source_revision,
        "review_goal": args.review_goal,
        "review_status": args.review_status,
    }
    if args.handoff_to is None and not any(value is not None for value in changes.values()):
        raise RelayStateError("update-metadata requires at least one changed field")
    for field, value in changes.items():
        if value is not None:
            state["source"][field] = value
    if args.handoff_to is not None:
        state["handoff_to"] = args.handoff_to
    _advance_state(state, args.updated_at)
    _persist_state(path, html, state)
    print(f"updated packet metadata: {path}")


def command_refresh_ledger(args: argparse.Namespace) -> None:
    path = Path(args.html)
    html = _read(path)
    state = _load_state(html)
    existing_errors = _validation_errors(html, state, check_ledger=False)
    if existing_errors:
        raise RelayStateError("existing packet state is invalid: " + "; ".join(existing_errors))
    _assert_expected_revision(state, args.expected_revision)
    _advance_state(state, args.updated_at)
    _persist_state(path, html, state)
    print(f"refreshed visible ledger: {path}")


def command_validate(args: argparse.Namespace) -> None:
    path = Path(args.html)
    html = _read(path)
    state = _load_state(html)
    errors = _validation_errors(html, state)
    if errors:
        raise RelayStateError("; ".join(errors))
    print(
        f"valid {SCHEMA}: packet={state['packet_id']} revision={state['state_revision']} "
        f"feedback={len(state['feedback'])} unresolved={len(state['unresolved'])}"
    )


def command_show(args: argparse.Namespace) -> None:
    state = _load_state(_read(Path(args.html)))
    print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="embed an empty relay state and visible ledger")
    init.add_argument("html")
    init.add_argument("--source-spec", required=True)
    init.add_argument("--source-revision", required=True)
    init.add_argument("--review-goal", required=True)
    init.add_argument("--review-status", choices=("draft", "in_review", "approved", "held"), required=True)
    init.add_argument("--handoff-to", default="unassigned")
    init.add_argument("--packet-id")
    init.add_argument("--updated-at")
    init.set_defaults(handler=command_init)

    add = subparsers.add_parser("add-feedback", help="persist one feedback item inside the HTML")
    add.add_argument("html")
    add.add_argument("--feedback-id", required=True)
    add.add_argument("--expected-revision", required=True, type=int)
    add.add_argument("--target", required=True)
    add.add_argument("--comment", required=True)
    add.add_argument("--selection", default="none")
    add.add_argument("--disposition", choices=sorted(DISPOSITIONS), required=True)
    add.add_argument("--rationale", required=True)
    add.add_argument("--source-change", default="none")
    add.add_argument("--owner", default="unassigned")
    add.add_argument("--created-at")
    add.add_argument("--updated-at")
    add.set_defaults(handler=command_add_feedback)

    update_feedback = subparsers.add_parser(
        "update-feedback", help="revise one feedback item and its disposition"
    )
    update_feedback.add_argument("html")
    update_feedback.add_argument("--feedback-id", required=True)
    update_feedback.add_argument("--expected-revision", required=True, type=int)
    update_feedback.add_argument("--comment")
    update_feedback.add_argument("--selection")
    update_feedback.add_argument("--disposition", choices=sorted(DISPOSITIONS))
    update_feedback.add_argument("--rationale")
    update_feedback.add_argument("--source-change")
    update_feedback.add_argument("--owner")
    update_feedback.add_argument("--updated-at")
    update_feedback.set_defaults(handler=command_update_feedback)

    update_metadata = subparsers.add_parser(
        "update-metadata", help="revise handoff and source review metadata"
    )
    update_metadata.add_argument("html")
    update_metadata.add_argument("--expected-revision", required=True, type=int)
    update_metadata.add_argument("--source-revision")
    update_metadata.add_argument("--review-goal")
    update_metadata.add_argument("--review-status", choices=sorted(REVIEW_STATUSES))
    update_metadata.add_argument("--handoff-to")
    update_metadata.add_argument("--updated-at")
    update_metadata.set_defaults(handler=command_update_metadata)

    refresh_ledger = subparsers.add_parser(
        "refresh-ledger", help="regenerate a stale or altered visible ledger from embedded state"
    )
    refresh_ledger.add_argument("html")
    refresh_ledger.add_argument("--expected-revision", required=True, type=int)
    refresh_ledger.add_argument("--updated-at")
    refresh_ledger.set_defaults(handler=command_refresh_ledger)

    validate = subparsers.add_parser("validate", help="validate embedded and visible relay state")
    validate.add_argument("html")
    validate.set_defaults(handler=command_validate)

    show = subparsers.add_parser("show", help="print embedded relay state as JSON")
    show.add_argument("html")
    show.set_defaults(handler=command_show)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except RelayStateError as exc:
        print(f"spec-relay: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
