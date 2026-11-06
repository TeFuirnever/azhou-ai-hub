"""Run offline component entrypoints with immutable actual-command receipts."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import re
import shutil
import stat
import sys

SOURCE = Path(__file__).resolve().parents[1]
WORKTREE = SOURCE.parents[1]
sys.path.insert(0, str(SOURCE))
from command_log import CommandLog, SignalLatch
from offline_runtime import json_new
from registration import fingerprint_file


def new_output(value):
    value = Path(value)
    if (not value.is_absolute() or value.resolve() != value
            or not value.is_relative_to(WORKTREE / '.scratch') or value.exists()):
        raise ValueError('output must be a new canonical directory inside this worktree .scratch')
    if not value.parent.is_dir() or value.parent.is_symlink():
        raise ValueError('output parent must already exist without links')
    return value


def prepare_only(output, resource):
    module_path = SOURCE / 'browser/run_browser.py'
    spec = importlib.util.spec_from_file_location('component_harness_preparation', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inputs = module.prepare(argparse.Namespace(root=output, resource_root=resource,
        tools=SOURCE, reuse_node_root=None))
    print(json.dumps({'scope': 'harness preparation only; no browser or formal Node execution',
        'inputs': len(inputs), 'browser_status': 'not_run'}))


def run(output, resource):
    output.mkdir(mode=0o700)
    commands = output / 'commands'
    commands.mkdir(mode=0o700)
    package_inputs=[WORKTREE/'packages/agent-skin'/name for name in ['tools/build-startup.py','extension/bootstrap.mjs','extension/renderer.mjs','tools/verify-artifacts.py','hub-package.json']]
    paths=[]
    for directory,folders,files in os.walk(SOURCE,followlinks=False):
        folders[:]=[name for name in folders if name not in {'.scratch','__pycache__'} and not (Path(directory)/name).is_symlink()]
        for name in files:
            path=Path(directory)/name
            if stat.S_ISREG(path.lstat().st_mode):paths.append(path)
    for path in package_inputs:
        if path.exists() and stat.S_ISREG(path.lstat().st_mode):paths.append(path)
    inputs = [{'path': str(path.relative_to(WORKTREE)),
               'sha256': fingerprint_file(path, root=WORKTREE)['sha256']}
              for path in sorted(paths)]
    json_new(output / 'inputs.json', inputs, root=WORKTREE)
    python = sys.executable
    node = shutil.which('node')
    if node is None:
        node = 'node'
    steps = [(name, [python, '-B', str(SOURCE / 'tests' / ('test_' + name + '.py'))], 240)
             for name in ['records', 'archive', 'launcher', 'registration', 'rebind', 'integration']]
    steps += [('isolation', [python, '-B', str(SOURCE / 'tests/test_isolation.py'),
                           '--out', str(output / 'isolation-cases')], 120),
              ('host-guard', [python, '-B', str(SOURCE / 'tests/test_host_guard.py'),
                              '--out', str(output / 'host-guard-cases')], 120),
              ('listener-gate', [python, '-B', str(SOURCE / 'tests/test_listener_gate.py'),
                                 '--out', str(output / 'listener-gate-cases')], 120),
              ('runtime', [node, '--test', '--test-reporter=tap', str(SOURCE / 'tests/test_runtime.mjs')], 180),
              ('harness-preparation', [python, '-B', str(Path(__file__).resolve()),
                   '--out', str(output / 'harness'), '--resource-root', str(resource),
                   '--prepare-only'], 180),
              ('lifecycle-models', [node, str(SOURCE / 'tests/test_browser_models.mjs'),
                   str(output / 'harness/source/tools'), str(output / 'lifecycle-cases')], 120)]
    results = []
    with SignalLatch() as interrupted:
        log = CommandLog(commands, inputs, interrupted, root=WORKTREE, stage=WORKTREE)
        for name, argv, timeout in steps:
            index = log.counter
            item = {'name': name, 'argv': argv, 'status': 'failed'}
            try:
                process = log.record(argv, cwd=WORKTREE, timeout=timeout, check=False)
                item.update(exit_code=process.returncode,
                            status='passed' if process.returncode == 0 else 'failed')
            except Exception as exc:
                item['error'] = {'type': type(exc).__name__, 'message': str(exc)}
            receipt_path = commands / str(index) / 'command.json'
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_bytes())
                item.update(receipt=str(receipt_path.relative_to(output)),
                            kind=receipt['kind'], execution_state=receipt['execution_state'],
                            exit_code=receipt['exit_code'])
                if (receipt['kind'] != 'C' or receipt['execution_state'] != 'exited'
                        or receipt['exit_code'] != 0 or receipt.get('error')
                        or not receipt.get('inputs_unchanged')
                        or not receipt.get('argument_inputs_unchanged')
                        or receipt.get('evidence_errors')):
                    item['status'] = 'failed'
                streams = {p.name: p.read_bytes().decode('utf-8', errors='replace')
                           for p in [receipt_path.parent / 'stdout.raw', receipt_path.parent / 'stderr.raw']}
                count = re.search(r'Ran (\d+) tests? in', streams['stderr.raw'])
                if count:
                    item['python_tests'] = int(count.group(1))
                count = re.search(r'^# tests (\d+)\s*$', streams['stdout.raw'], re.M)
                if count:
                    item['runtime_tests'] = int(count.group(1))
                if name == 'lifecycle-models':
                    for line in reversed(streams['stdout.raw'].splitlines()):
                        try:
                            value = json.loads(line)
                        except ValueError:
                            continue
                        if 'passed' in value:
                            item['model_checks'] = value['passed']
                            break
            results.append(item)
            json_new(output / (name + '.json'), item, root=WORKTREE)
            print(json.dumps(item), flush=True)
    summary = {'scope': 'current offline components; no host or full browser acceptance',
        'status': 'passed' if all(x['status'] == 'passed' for x in results) else 'failed',
        'python_tests': sum(x.get('python_tests', 0) for x in results),
        'runtime_tests': sum(x.get('runtime_tests', 0) for x in results),
        'model_checks': sum(x.get('model_checks', 0) for x in results),
        'harness_prepared': any(x['name'] == 'harness-preparation' and x['status'] == 'passed' for x in results),
        'browser_status': 'not_run', 'formal_node_256': 'not_run', 'results': results}
    json_new(output / 'summary.json', summary, root=WORKTREE)
    print(json.dumps(summary), flush=True)
    return 0 if summary['status'] == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--resource-root', required=True, type=Path)
    parser.add_argument('--prepare-only', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    output = new_output(args.out)
    resource = args.resource_root
    if (not resource.is_absolute() or resource.resolve() != resource
            or resource.is_symlink() or not resource.is_dir()):
        parser.error('resource root must be an existing canonical directory')
    if args.prepare_only:
        prepare_only(output, resource)
        return 0
    return run(output, resource)


if __name__ == '__main__':
    raise SystemExit(main())
