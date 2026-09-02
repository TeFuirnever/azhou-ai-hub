#!/usr/bin/env python3
"""Bounded, deterministic mutation fuzzer for the spec-relay HTML state parser.

The fuzzer drives the parser read path (``_load_state`` + ``_validation_errors``)
with mutated packets and asserts the parser's own contract: only
``RelayStateError`` may escape; any other exception, or a hang, is a crash.

Stdlib only: no new runtime dependency for skills or CI beyond Python itself.
Deterministic given ``--seed``: the same seed replays the same inputs, so a
crash logged with its seed and input file reproduces exactly.

Local run::

    python3 scripts/fuzz_relay_state.py --seconds 30

CI run is bounded twice: ``timeout-minutes`` on the job and ``--seconds`` inside
the harness. Crashes are written to a system temp directory (never committed).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
import signal
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELAY_STATE = ROOT / "skills" / "spec-relay" / "scripts" / "relay_state.py"
STATE_BLOCK = re.compile(
    r'<script\s+type="application/json"\s+id="spec-relay-state">\s*(.*?)\s*</script>',
    re.DOTALL,
)
MAX_PAYLOAD_BYTES = 64 * 1024
MAX_CRASHES = 10
PER_INPUT_SECONDS = 1.0


def load_module():
    spec = importlib.util.spec_from_file_location("relay_state", RELAY_STATE)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load module: {RELAY_STATE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_state(module: Any) -> dict[str, Any]:
    """One valid feedback item, mirroring the owning package's test corpus."""
    feedback = [
        {
            "comment": "Confirm the latency budget",
            "created_at": "2026-08-24T08:00:00Z",
            "disposition": "deferred",
            "feedback_id": "FB-001",
            "owner": "platform",
            "rationale": "benchmark pending",
            "selection": "none",
            "source_change": "none",
            "target": "REQ-001",
            "updated_at": "2026-08-24T08:00:00Z",
        }
    ]
    return {
        "feedback": feedback,
        "handoff_to": "engineering",
        "packet_id": "00000000-0000-4000-8000-000000000000",
        "schema": module.SCHEMA,
        "source": {
            "review_goal": "approve scope",
            "review_status": "in_review",
            "revision": "abc123",
            "spec": "docs/spec.md",
        },
        "state_revision": 1,
        "unresolved": ["FB-001"],
        "updated_at": "2026-08-24T08:00:00Z",
    }


def build_seeds(module: Any) -> list[str]:
    """Corpus spans valid packets and malformed wrappers around them."""
    state = seed_state(module)
    packet = module._inject_packet_state(
        '<!doctype html><html><body><main data-review-id="REQ-001">Requirement</main></body></html>',
        state,
    )
    empty = module._inject_packet_state(
        '<!doctype html><html><body><main data-review-id="REQ-001">Requirement</main></body></html>',
        {**state, "feedback": [], "unresolved": [], "state_revision": 0},
    )
    broken = (
        '<!doctype html><html><body>'
        '<script type="application/json" id="spec-relay-state">{</script>'
        "</body></html>"
    )
    doubled = packet.replace("</body>", '<script type="application/json" id="spec-relay-state">{}</script></body>')
    plain = '<!doctype html><html><body><main data-review-id="REQ-001">R</main></body></html>'
    return [packet, empty, broken, doubled, plain]


def mutate_text(rng: random.Random, text: str) -> str:
    """Byte-level mutation of the embedded JSON text."""
    operations = [
        "flip",
        "insert",
        "delete",
        "duplicate",
        "deep_nest",
        "huge_int",
    ]
    out = list(text)
    for _ in range(rng.randint(1, 6)):
        operation = rng.choice(operations)
        if not out:
            out = list('{"feedback": []}')
        position = rng.randrange(len(out))
        if operation == "flip":
            out[position] = rng.choice('{}[]",:0123456789truNelnl -')
        elif operation == "insert":
            out.insert(position, rng.choice('{}[]",:0123456789 \t\n-'))
        elif operation == "delete":
            del out[position]
        elif operation == "duplicate":
            chunk = out[position : position + rng.randint(1, 24)]
            out[position:position] = chunk
        elif operation == "deep_nest":
            depth = rng.randint(50, 150_000)
            out[position:position] = list("[" * depth + "]" * depth)
        elif operation == "huge_int":
            out[position:position] = list("9" * rng.randint(10, 6_000))
        if len(out) > MAX_PAYLOAD_BYTES:
            break
    return "".join(out)


def mutate_state_object(rng: random.Random, state: dict[str, Any]) -> dict[str, Any]:
    """Structural mutation: retype, remove, or replace values anywhere in state."""
    state = json.loads(json.dumps(state))  # private deep copy of the clean seed
    paths: list[list[Any]] = []

    def collect(node: Any, path: list[Any]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child = [*path, key]
                paths.append(child)
                collect(value, child)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                child = [*path, index]
                paths.append(child)
                collect(value, child)

    collect(state, [])
    if not paths:
        return state
    for _ in range(rng.randint(1, 3)):
        path = rng.choice(paths)
        node: Any = state
        walked = True
        for step in path:
            if isinstance(step, int) and isinstance(node, list):
                if step >= len(node):
                    walked = False
                    break
                node = node[step]
            elif isinstance(node, dict) and step in node:
                node = node[step]
            else:
                walked = False
                break
        if not walked:
            continue
        parent = state
        for step in path[:-1]:
            parent = parent[step] if isinstance(parent, dict) else parent[step]
        key = path[-1]
        replacement: Any = rng.choice(
            [
                None,
                True,
                0,
                -1,
                2**63,
                1.5,
                "",
                [],
                {},
                ["deferred"],
                {"nested": True},
                "x" * rng.randint(1, 4096),
                10_000 * ["deferred"],
            ]
        )
        try:
            parent[key] = replacement
        except (IndexError, KeyError, TypeError):
            continue
    return state


def rewrap(module: Any, html: str, state: dict[str, Any]) -> str:
    """Write a mutated state back into the packet's state block."""
    block = (
        '<script type="application/json" id="spec-relay-state">\n'
        + json.dumps(state, ensure_ascii=False, sort_keys=True)
        + "\n</script>"
    )
    if STATE_BLOCK.search(html):
        return STATE_BLOCK.sub(lambda _: block, html, count=1)
    return html + "\n" + block


def wrap_html(rng: random.Random, html: str) -> str:
    """Wrapper-level mutation of the whole packet."""
    operation = rng.choice(["strip_markers", "append_junk", "none"])
    if operation == "strip_markers":
        return html.replace("<!-- spec-relay-ledger:start -->", "")
    if operation == "append_junk":
        return html + "<!--" + "junk" * rng.randint(1, 64) + "-->"
    return html


def make_input(rng: random.Random, module: Any, seeds: list[str], clean_state: dict[str, Any]) -> str:
    mode = rng.random()
    if mode < 0.25:
        return wrap_html(rng, rng.choice(seeds))
    if mode < 0.65:
        html = rng.choice(seeds)
        match = STATE_BLOCK.search(html)
        payload = match.group(1) if match else "{}"
        mutated = mutate_text(rng, payload)
        if STATE_BLOCK.search(html):
            block = f'<script type="application/json" id="spec-relay-state">\n{mutated}\n</script>'
            return STATE_BLOCK.sub(lambda _: block, html, count=1)
        return html
    html = rng.choice(seeds)
    return rewrap(module, html, mutate_state_object(rng, clean_state))


def probe(module: Any, html: str) -> str | None:
    """Return a crash label when the parser violates its contract, else None."""

    def timeout(signum: int, frame: Any) -> None:
        raise TimeoutError()

    previous = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, PER_INPUT_SECONDS)
    try:
        try:
            state = module._load_state(html)
            module._validation_errors(html, state)
        except module.RelayStateError:
            return None
        except TimeoutError:
            return "per-input deadline exceeded"
        except Exception as exc:  # noqa: BLE001 - the oracle IS this catch
            return f"{type(exc).__name__}: {exc}"[:300]
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=30.0, help="wall-clock budget")
    parser.add_argument("--max-inputs", type=int, default=200_000, help="input cap")
    parser.add_argument("--seed", type=int, default=None, help="replay seed (printed)")
    parser.add_argument(
        "--crash-dir",
        type=Path,
        default=None,
        help="where crash inputs are written (default: fresh temp dir)",
    )
    arguments = parser.parse_args(argv)
    if arguments.seconds <= 0 or arguments.max_inputs <= 0:
        parser.error("--seconds and --max-inputs must be positive")
    module = load_module()
    seeds = build_seeds(module)
    clean_state = seed_state(module)
    rng = random.Random(arguments.seed)
    if arguments.crash_dir is None:
        crash_dir = Path(tempfile.mkdtemp(prefix="relay-state-fuzz-"))
    else:
        arguments.crash_dir.mkdir(parents=True, exist_ok=True)
        crash_dir = arguments.crash_dir
    crashes: dict[str, str] = {}
    inputs = 0
    deadline = time.monotonic() + arguments.seconds
    while inputs < arguments.max_inputs and time.monotonic() < deadline:
        html = make_input(rng, module, seeds, clean_state)
        inputs += 1
        label = probe(module, html)
        if label is None:
            continue
        signature = label.split(":", 1)[0]
        if signature not in crashes:
            if len(crashes) >= MAX_CRASHES:
                continue
            crash_path = crash_dir / f"crash-{len(crashes)}-{signature}.txt"
            crash_path.write_text(html, encoding="utf-8")
            crashes[signature] = str(crash_path)
            print(f"CRASH {signature}: {label}", file=sys.stderr)
            print(f"  input: {crash_path}", file=sys.stderr)
            print(f"  seed:  {arguments.seed}", file=sys.stderr)
    elapsed = arguments.seconds - (deadline - time.monotonic())
    print(
        f"fuzz relay_state: inputs={inputs} elapsed={elapsed:.1f}s "
        f"crashes={len(crashes)} seed={arguments.seed} corpus={len(seeds)} crash_dir={crash_dir}"
    )
    return 1 if crashes else 0


if __name__ == "__main__":
    raise SystemExit(main())
