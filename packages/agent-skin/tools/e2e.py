#!/usr/bin/env python3
"""Single E2E entry for the Agent Skin test system (design doc runner discipline,
incident families P8.1/P8.2/P10.1).

--layer quick|cold|daily|all. quick is the per-PR gate: the L0 private-asset
manifest check plus the two E2E-family unit suites (tools/test-e2e-tools.py,
tools/test-ship-zcode.py), wired per PR as an agent-skin suite of
scripts/verify_packages.py. cold and daily delegate to tools/e2e-cold-start.py
and tools/e2e-daily.py in --plan mode, which starts no process; a real run
needs an explicit --execute and prints a loud warning first. all is
quick+cold+daily in that order (cheapest layer first, fail fast).

Runner discipline, both born from the build-36 fake-green incident: the first
action asserts that the git toplevel of the current working directory equals
this worktree (git rev-parse --show-toplevel, P8.1), and every child runs
without any intermediate pipe so its exit code reaches the caller untouched -
the runner exits with the first failing child's exact exit code (P8.2). Every
run appends its own record (layer, command, exit code, duration) to
.local/e2e-run.jsonl: the test system meets its own observability bar.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
RUN_JOURNAL_RELATIVE = '.local/e2e-run.jsonl'
RUN_SCHEMA = 'agent-skin-e2e-run/v1'
# quick = L0 private-asset gate + the E2E-family unit suites (E1 and E2/E3 stages).
UNIT_STEPS = {'unit-e2e-tools': 'test-e2e-tools.py', 'unit-ship-zcode': 'test-ship-zcode.py'}
PLAN_STEPS = {'cold-start': 'e2e-cold-start.py', 'daily-start': 'e2e-daily.py'}
LAYERS = {
    'quick': ('private-assets', *UNIT_STEPS),
    'cold': ('cold-start',),
    'daily': ('daily-start',),
    'all': ('private-assets', *UNIT_STEPS, *PLAN_STEPS),
}
EXECUTE_WARNINGS = (
    '真实运行（--execute）：cold 将启动启动器与 ZCode，daily 将触碰已装日常入口。',
    '这不是 plan 演练；确认当前宿主与工作区就是目标后再继续。',
)
MISSING_TOOL_EXIT = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def process_status(returncode: int) -> int:
    """Map a subprocess returncode to a process exit status (signals become 128+n)."""
    return returncode if returncode >= 0 else 128 - returncode


def layer_commands(layer: str, *, execute: bool) -> dict[str, tuple[Path, list[str]]]:
    """Script path and command per step id; plan mode unless --execute was given."""
    mode = '--execute' if execute else '--plan'
    commands: dict[str, tuple[Path, list[str]]] = {
        'private-assets': (TOOLS / 'check-private-assets.py',
                           [sys.executable, '-B', str(TOOLS / 'check-private-assets.py')]),
    }
    for step, script in UNIT_STEPS.items():
        commands[step] = (TOOLS / script, [sys.executable, '-B', str(TOOLS / script)])
    for step, script in PLAN_STEPS.items():
        commands[step] = (TOOLS / script, [sys.executable, '-B', str(TOOLS / script), mode])
    return {step: commands[step] for step in LAYERS[layer]}


def git_toplevel(directory: Path) -> tuple[Path | None, str | None]:
    """git rev-parse --show-toplevel of a directory; (None, reason) on failure."""
    completed = subprocess.run(['git', '-C', str(directory), 'rev-parse', '--show-toplevel'],
                               capture_output=True, text=True, check=False)
    output = completed.stdout.strip()
    if completed.returncode == 0 and output:
        return Path(output).resolve(), None
    reasons = [line for line in completed.stderr.splitlines() if line.strip()]
    return None, reasons[-1] if reasons else 'git rev-parse --show-toplevel failed'


def worktree_verdict(cwd: Path, runner_home: Path = ROOT) -> dict:
    """cwd's git toplevel must equal this runner's worktree (P8.1, build 36).

    Comparing toplevels (not raw cwd) lets the runner start from any
    subdirectory of the worktree while still refusing a main-checkout launch.
    """
    expected, expected_problem = git_toplevel(runner_home)
    observed, observed_problem = git_toplevel(cwd)
    problems = []
    if expected_problem:
        problems.append(f'cannot resolve the runner worktree: {expected_problem}')
    if observed_problem:
        problems.append(f'cwd is not inside a usable git work tree: {observed_problem}')
    if expected is not None and observed is not None and expected != observed:
        problems.append(f'cwd belongs to another checkout: expected {expected}, observed {observed}; '
                        'build-36 lesson: tests must run inside the changed worktree')
    return {'check': 'worktree', 'passed': not problems,
            'expected': str(expected) if expected else None,
            'observed': str(observed) if observed else None, 'problems': problems}


def run_step(step: str, command: list[str]) -> dict:
    """Run one child with inherited stdio - no pipe can eat its exit code."""
    started = time.monotonic()
    completed = subprocess.run(command, cwd=str(ROOT), check=False)
    return {'id': step, 'command': command, 'exitCode': completed.returncode,
            'durationSeconds': round(time.monotonic() - started, 3)}


def append_run_record(record_path: Path, record: dict) -> None:
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with record_path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')


def main(argv: list[str] | None = None, *, cwd: Path | None = None,
         root: Path = ROOT, record_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layer', required=True, choices=tuple(LAYERS),
                        help='quick: L0 asset gate + unit suites; cold/daily: plan mode '
                             'unless --execute; all: quick+cold+daily')
    parser.add_argument('--execute', action='store_true',
                        help='real run for cold/daily (starts the launcher, ZCode and the '
                             'installed daily app; prints a loud warning first)')
    options = parser.parse_args(argv)
    current = Path(cwd) if cwd is not None else Path.cwd()
    journal = record_path if record_path is not None else Path(root) / RUN_JOURNAL_RELATIVE
    clock = time.monotonic()
    record = {'schema': RUN_SCHEMA, 'startedAt': now_iso(), 'layer': options.layer,
              'executed': options.execute,
              'command': ['e2e.py', *(sys.argv[1:] if argv is None else argv)],
              'steps': [], 'exitCode': 0, 'durationSeconds': 0.0}

    verdict = worktree_verdict(current, Path(root))
    record['worktree'] = verdict
    if not verdict['passed']:
        for problem in verdict['problems']:
            print(f'[e2e] RED worktree: {problem}', file=sys.stderr)
        record['exitCode'] = 1
        record['durationSeconds'] = round(time.monotonic() - clock, 3)
        append_run_record(journal, record)
        return 1

    if options.layer == 'quick':
        pass
    elif options.execute:
        for warning in EXECUTE_WARNINGS:
            print(f'!!! {warning} !!!', file=sys.stderr)
    else:
        print('[e2e] plan 模式（默认）：不启动任何进程；真实运行需显式 --execute。', file=sys.stderr)

    exit_code = 0
    for step, (script, command) in layer_commands(options.layer, execute=options.execute).items():
        print(f'[e2e] {options.layer}/{step}: {" ".join(command)}', file=sys.stderr)
        if not script.is_file():
            problem = f'tool missing: {script}（该层依赖的工具未落地，判红不判绿）'
            print(f'[e2e] RED {step}: {problem}', file=sys.stderr)
            record['steps'].append({'id': step, 'command': command, 'exitCode': MISSING_TOOL_EXIT,
                                    'durationSeconds': 0.0, 'problems': [problem]})
            exit_code = MISSING_TOOL_EXIT
            break
        outcome = run_step(step, command)
        record['steps'].append(outcome)
        if outcome['exitCode'] != 0:
            exit_code = process_status(outcome['exitCode'])
            break

    record['exitCode'] = exit_code
    record['durationSeconds'] = round(time.monotonic() - clock, 3)
    append_run_record(journal, record)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
