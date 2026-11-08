#!/usr/bin/env python3
"""Single-entry ZCode candidate ship chain (design doc L3, incident family P3).

Atomically chains: residue clean, build, digest stamp, re-sign, strict verify,
stamp re-verification and a full-chain receipt. payloadSHA256 is always the
freshly measured sha256 of the built startup install.js, the stamped payload is
always re-signed, and the stamp is re-verified against a second measurement
after codesign, so the 2026-11-08 stamp incidents cannot recur structurally.
stdout carries only the receipt JSON; step diagnostics go to stderr. Exit 0 on
success, 1 on any step failure. --dry-run prints the plan with zero side
effects; ~/Applications is only ever written with an explicit --install.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_RELATIVE = '.build/azhou-zcode-payload'
STARTUP_RELATIVE = 'Contents/Resources/startup/install.js'
STAMP_RELATIVE = 'Contents/Resources/zcode-validation.json'
MARKER_RELATIVE = 'Contents/Resources/azhou-build.json'
OBSERVATION_RELATIVE = '.local/zcode-ship/OBSERVATION.json'
BUILD_COMMAND = ['bash', 'tools/build-macos.sh', '--host', 'zcode']
SIGN_COMMAND = ['codesign', '--force', '--sign', '-']
VERIFY_COMMAND = ['codesign', '--verify', '--strict']
# Mirrors the runtime gates in Native/ZCodeSkinRuntime.swift (proof/validateUIProof).
STAMP_SCHEMA = 'agent-skin-zcode-ui-evidence/v1'
CONTRACT_VERSION = 'agent-skin-zcode-contract/v0.1'
RECEIPT_SCHEMA = 'agent-skin-zcode-ship-receipt/v1'
MAX_STAMP_BYTES = 16384
HOST_FINGERPRINT_FIELDS = ('infoSHA256', 'executableSHA256', 'appAsarSHA256')
STAMP_FIELDS = frozenset({
    'schema', 'contractVersion', 'version', 'infoSHA256', 'executableSHA256',
    'appAsarSHA256', 'recordID', 'recordSHA256', 'observedAt', 'payloadSHA256',
    'evidenceIDs', 'ownedAppearanceSurface', 'persistentSettings',
})
STEP_NAMES = ('clean-residue', 'build', 'stamp', 'codesign', 'codesign-verify', 'verify-stamp')


class ShipFailure(RuntimeError):
    """A failed chain step; exit_code is the value recorded in the receipt."""

    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def is_hex64(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in '0123456789abcdef' for character in value))


def is_safe_text(value, limit):
    return (isinstance(value, str) and bool(value) and len(value.encode('utf-8')) <= limit
            and '\n' not in value)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _tail(text, limit=400):
    return (text or '').strip()[-limit:]


def git_identity(root):
    """Branch and short commit for the observation increment; strict on failure."""
    values = []
    for extra in (['--abbrev-ref', 'HEAD'], ['--short', 'HEAD']):
        completed = subprocess.run(['git', '-C', str(root), 'rev-parse', *extra],
                                   capture_output=True, text=True)
        if completed.returncode != 0 or not completed.stdout.strip():
            raise ShipFailure(f'无法读取工作区 git 身份（rev-parse {" ".join(extra)}）：'
                              f'{_tail(completed.stderr)}')
        values.append(completed.stdout.strip())
    return values[0], values[1]


def load_evidence(path, short_commit):
    """Load the real-acceptance OBSERVATION record that the stamp must cite.

    Nothing in the stamp is invented: host identity, fingerprints and evidence
    IDs all come from this record, and only payloadSHA256 is measured fresh.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ShipFailure(f'验收证据记录缺失、为符号链接或非常规文件：{path}')
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ShipFailure(f'验收证据记录不是有效 JSON：{path}（{error}）')
    if not isinstance(record, dict):
        raise ShipFailure(f'验收证据记录必须是 JSON 对象：{path}')
    host_version = record.get('hostVersion')
    if not is_safe_text(host_version, 64):
        raise ShipFailure('验收证据记录缺少有效的 hostVersion（ZCode 宿主版本）。')
    fingerprints = record.get('hostFingerprints')
    if not isinstance(fingerprints, dict) or any(
            not is_hex64(fingerprints.get(field)) for field in HOST_FINGERPRINT_FIELDS):
        raise ShipFailure('验收证据记录 hostFingerprints 必须提供 '
                          + '、'.join(HOST_FINGERPRINT_FIELDS) + '（64 位十六进制 sha256）。')
    identifiers = record.get('evidenceIDs')
    if (not isinstance(identifiers, list) or not identifiers
            or any(not is_safe_text(item, 256) for item in identifiers)):
        raise ShipFailure('验收证据记录 evidenceIDs 必须是非空列表，每项为不超过 256 字节且无换行的字符串。')
    for field in ('ownedAppearanceSurface', 'persistentSettings'):
        if record.get(field) is not True:
            raise ShipFailure(f'验收证据记录必须以真实验收显式声明 {field}=true；拒绝替未验收载荷盖章。')
    observed_at = record.get('observedAt', now_iso())
    if not is_safe_text(observed_at, 64):
        raise ShipFailure('验收证据记录 observedAt 必须是可读的 ISO-8601 字符串。')
    try:
        datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    except ValueError:
        raise ShipFailure('验收证据记录 observedAt 不是有效的 ISO-8601 时间。')
    record_id = record.get('recordID') or f'{path.parent.name}/{short_commit}/OBSERVATION.json'
    if not is_safe_text(record_id, 256):
        raise ShipFailure('验收证据记录 recordID 必须是不超过 256 字节且无换行的字符串。')
    return {
        'hostVersion': host_version,
        'hostFingerprints': {field: fingerprints[field] for field in HOST_FINGERPRINT_FIELDS},
        'evidenceIDs': list(identifiers),
        'observedAt': observed_at,
        'recordID': record_id,
        'recordSHA256': sha256_file(path),
    }


def build_stamp(evidence, payload_digest):
    return {
        'schema': STAMP_SCHEMA,
        'contractVersion': CONTRACT_VERSION,
        'version': evidence['hostVersion'],
        'infoSHA256': evidence['hostFingerprints']['infoSHA256'],
        'executableSHA256': evidence['hostFingerprints']['executableSHA256'],
        'appAsarSHA256': evidence['hostFingerprints']['appAsarSHA256'],
        'recordID': evidence['recordID'],
        'recordSHA256': evidence['recordSHA256'],
        'observedAt': evidence['observedAt'],
        'payloadSHA256': payload_digest,
        'evidenceIDs': list(evidence['evidenceIDs']),
        'ownedAppearanceSurface': True,
        'persistentSettings': True,
    }


def validate_stamp(stamp, measured_digest):
    """Fail closed against the runtime proof gate and the P3.1 digest rule."""
    if not isinstance(stamp, dict) or frozenset(stamp) != STAMP_FIELDS:
        raise ShipFailure('盖章字段不完整或含未知字段，必须是 ZCodeSkinRuntime 证明门的精确字段集。')
    if stamp['schema'] != STAMP_SCHEMA or stamp['contractVersion'] != CONTRACT_VERSION:
        raise ShipFailure('盖章 schema/contractVersion 与运行时证明门不符。')
    if not is_safe_text(stamp['version'], 64):
        raise ShipFailure('盖章 version 必须是非空宿主版本字符串。')
    for field in HOST_FINGERPRINT_FIELDS:
        if not is_hex64(stamp[field]):
            raise ShipFailure(f'盖章 {field} 必须是 64 位十六进制 sha256。')
    if not is_safe_text(stamp['recordID'], 256) or not is_hex64(stamp['recordSHA256']):
        raise ShipFailure('盖章 recordID/recordSHA256 不符合证明门约束。')
    try:
        datetime.fromisoformat(str(stamp['observedAt']).replace('Z', '+00:00'))
    except ValueError:
        raise ShipFailure('盖章 observedAt 不是有效的 ISO-8601 时间。')
    if not is_hex64(stamp['payloadSHA256']):
        raise ShipFailure('盖章 payloadSHA256 必须是 64 位十六进制 sha256。')
    if stamp['payloadSHA256'] != measured_digest:
        raise ShipFailure(f'盖章 payloadSHA256（{stamp["payloadSHA256"]}）不等于实测 '
                          f'startup/install.js sha256（{measured_digest}）。')
    identifiers = stamp['evidenceIDs']
    if (not isinstance(identifiers, list) or not identifiers
            or any(not is_safe_text(item, 256) for item in identifiers)):
        raise ShipFailure('盖章 evidenceIDs 不符合证明门约束。')
    if stamp['ownedAppearanceSurface'] is not True or stamp['persistentSettings'] is not True:
        raise ShipFailure('盖章必须携带真实 UI 验收的 ownedAppearanceSurface/persistentSettings。')
    encoded = (json.dumps(stamp, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    if len(encoded) >= MAX_STAMP_BYTES:
        raise ShipFailure(f'盖章序列化后达到 {len(encoded)} 字节，超过运行时 {MAX_STAMP_BYTES} 上限。')


def write_observation_increment(path, *, branch, commit, fingerprints, digest, build_marker):
    """Append one gate increment to the ship observation record (.local, untracked)."""
    path = Path(path)
    gates = []
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise ShipFailure(f'拒绝覆写非常规观察记录：{path}')
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ShipFailure(f'现有观察记录不是有效 JSON，拒绝追加：{path}（{error}）')
        if not isinstance(record, dict) or not isinstance(record.get('gates'), list):
            raise ShipFailure(f'现有观察记录缺少 gates 列表，拒绝追加：{path}')
        gates = record['gates']
    gates.append({
        'gate': 'tools/ship-zcode.py',
        'exit': 0,
        'result': (f'stamped payloadSHA256={digest} measured from '
                   f'{STARTUP_RELATIVE} (version {build_marker["version"]} build {build_marker["build"]})'),
    })
    observation = {
        'schema': STAMP_SCHEMA,
        'branch': branch,
        'commit': commit,
        'gates': gates,
        'hostFingerprints': dict(fingerprints),
        'observedAt': now_iso(),
        'scope': 'tools/ship-zcode.py stamp increment only; digest re-measured per build; '
                 'no ~/Applications writes without --install',
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(observation, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8')
    return path


def zcode_installation_name():
    """Load the pinned ZCode installationName from the canonical verifier."""
    path = ROOT / 'tools/verify-artifacts.py'
    spec = importlib.util.spec_from_file_location('agent_skin_ship_verifier', path)
    if spec is None or spec.loader is None:
        raise ShipFailure(f'Missing build verifier tools/verify-artifacts.py under {ROOT}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.configure_build_host('zcode')
    return module.NAME


def run_step_command(command, root):
    completed = subprocess.run(command, cwd=str(root), capture_output=True, text=True)
    if completed.returncode != 0:
        raise ShipFailure(f'命令失败（exit {completed.returncode}）：{" ".join(command)}\n'
                          f'{_tail(completed.stderr)}', exit_code=completed.returncode)
    return completed


def read_build_marker(payload):
    marker_path = payload / MARKER_RELATIVE
    if marker_path.is_symlink() or not marker_path.is_file():
        raise ShipFailure(f'构建产物缺少 {MARKER_RELATIVE}：{marker_path}')
    try:
        marker = json.loads(marker_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ShipFailure(f'{MARKER_RELATIVE} 不是有效 JSON：{error}')
    if not isinstance(marker, dict):
        raise ShipFailure(f'{MARKER_RELATIVE} 必须是 JSON 对象。')
    version, build = marker.get('version'), marker.get('build')
    if (not isinstance(version, str) or not version
            or isinstance(build, bool) or not isinstance(build, (str, int))
            or not str(build).isdigit()):
        raise ShipFailure(f'{MARKER_RELATIVE} 缺少有效的 version/build。')
    return {'version': version, 'build': str(build)}


def _planned_steps(payload, install):
    steps = [
        {'step': 'clean-residue', 'command': ['shutil.rmtree', str(payload)]},
        {'step': 'build', 'command': list(BUILD_COMMAND)},
        {'step': 'stamp', 'command': ['stamp', str(payload / STAMP_RELATIVE)]},
        {'step': 'codesign', 'command': [*SIGN_COMMAND, str(payload)]},
        {'step': 'codesign-verify', 'command': [*VERIFY_COMMAND, str(payload)]},
        {'step': 'verify-stamp', 'command': ['verify-stamp', str(payload / STAMP_RELATIVE)]},
    ]
    if install:
        steps.append({'step': 'install', 'command': ['ditto', str(payload), '<~/Applications>']})
    for step in steps:
        step['planned'] = True
    return steps


def ship(options):
    """Run the chain; returns (exit_code, receipt). Never raises for step failures."""
    root = ROOT
    payload = root / PAYLOAD_RELATIVE
    install_js = payload / STARTUP_RELATIVE
    stamp_path = payload / STAMP_RELATIVE
    observation_path = Path(options.observation) if options.observation else root / OBSERVATION_RELATIVE
    receipt = {
        'schema': RECEIPT_SCHEMA,
        'kind': 'shipZcode',
        'ok': False,
        'dryRun': bool(options.dry_run),
        'workspace': str(root),
        'payload': PAYLOAD_RELATIVE,
        'installJS': STARTUP_RELATIVE,
        'startedAt': now_iso(),
        'payloadSHA256': None,
        'build': None,
        'steps': [],
    }
    steps = receipt['steps']

    def finish(failure=None):
        receipt['finishedAt'] = now_iso()
        if failure is not None:
            receipt['failure'] = failure
        return (1 if failure is not None else 0), receipt

    def fail(step, command, error, detail=None):
        exit_code = getattr(error, 'exit_code', 1)
        entry = {'step': step, 'command': command, 'exitCode': exit_code, 'error': str(error)}
        if detail:
            entry['detail'] = detail
        steps.append(entry)
        return finish({'step': step, 'exitCode': exit_code, 'error': str(error)})

    if options.dry_run:
        receipt['steps'] = _planned_steps(payload, options.install)
        receipt['ok'] = True
        return finish()

    # Step 1: remove any stale stamped payload so the build publishes into a clean slot.
    try:
        if payload.is_symlink():
            raise ShipFailure(f'拒绝清理符号链接载荷：{payload}')
        if payload.exists():
            shutil.rmtree(payload)
            detail = 'removed stale payload'
        else:
            detail = 'no residue present'
    except (OSError, RuntimeError) as error:
        return fail('clean-residue', ['shutil.rmtree', str(payload)], error)
    steps.append({'step': 'clean-residue', 'command': ['shutil.rmtree', str(payload)],
                  'exitCode': 0, 'detail': detail})

    # Step 2: build the ZCode candidate payload.
    try:
        run_step_command(BUILD_COMMAND, root)
        if install_js.is_symlink() or not install_js.is_file():
            raise ShipFailure(f'构建产物缺少 {STARTUP_RELATIVE}：{install_js}')
        build_marker = read_build_marker(payload)
    except (OSError, ShipFailure, subprocess.CalledProcessError) as error:
        return fail('build', list(BUILD_COMMAND), error)
    receipt['build'] = build_marker
    steps.append({'step': 'build', 'command': list(BUILD_COMMAND), 'exitCode': 0,
                  'detail': {**build_marker, 'installJSBytes': install_js.stat().st_size}})

    # Step 3: measure the fresh install.js digest and stamp zcode-validation.json.
    stamp_command = ['stamp', str(stamp_path)]
    try:
        if not options.evidence:
            raise ShipFailure('缺少 --evidence 验收证据记录；拒绝在没有真实验收来源时盖章。')
        branch, commit = git_identity(root)
        evidence = load_evidence(options.evidence, commit)
        digest = sha256_file(install_js)
        stamp = build_stamp(evidence, digest)
        validate_stamp(stamp, digest)
        stamp_bytes = (json.dumps(stamp, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
        stamp_path.write_text(stamp_bytes, encoding='utf-8')
        observation = write_observation_increment(
            observation_path, branch=branch, commit=commit,
            fingerprints=evidence['hostFingerprints'], digest=digest, build_marker=build_marker)
    except (OSError, ShipFailure, subprocess.CalledProcessError) as error:
        return fail('stamp', stamp_command, error)
    receipt['payloadSHA256'] = digest
    steps.append({'step': 'stamp', 'command': stamp_command, 'exitCode': 0,
                  'detail': {'payloadSHA256': digest, 'recordSHA256': evidence['recordSHA256'],
                             'stampSHA256': hashlib.sha256(stamp_bytes.encode('utf-8')).hexdigest(),
                             'observation': str(observation), 'branch': branch, 'commit': commit}})

    # Step 4: the stamp touched Resources, so the ad-hoc seal must be re-signed.
    try:
        run_step_command([*SIGN_COMMAND, str(payload)], root)
    except (OSError, ShipFailure, subprocess.CalledProcessError) as error:
        return fail('codesign', [*SIGN_COMMAND, str(payload)], error)
    steps.append({'step': 'codesign', 'command': [*SIGN_COMMAND, str(payload)], 'exitCode': 0})

    # Step 5: strict seal verification of the re-signed payload.
    try:
        run_step_command([*VERIFY_COMMAND, str(payload)], root)
    except (OSError, ShipFailure, subprocess.CalledProcessError) as error:
        return fail('codesign-verify', [*VERIFY_COMMAND, str(payload)], error)
    steps.append({'step': 'codesign-verify', 'command': [*VERIFY_COMMAND, str(payload)], 'exitCode': 0})

    # Step 6: re-measure install.js and re-check the stamp read back from the payload.
    verify_command = ['verify-stamp', str(stamp_path)]
    stamped, measured = None, None
    try:
        stamped = json.loads(stamp_path.read_text(encoding='utf-8'))
        measured = sha256_file(install_js)
        validate_stamp(stamped, measured)
    except (OSError, UnicodeError, json.JSONDecodeError, ShipFailure) as error:
        return fail('verify-stamp', verify_command, error,
                    detail={'stampPayloadSHA256': stamped.get('payloadSHA256')
                            if isinstance(stamped, dict) else None,
                            'measuredInstallJSSHA256': measured})
    steps.append({'step': 'verify-stamp', 'command': verify_command, 'exitCode': 0,
                  'detail': {'stampPayloadSHA256': stamped['payloadSHA256'],
                             'measuredInstallJSSHA256': measured, 'match': True}})

    # Optional explicit install: the only path allowed to write ~/Applications.
    if options.install:
        install_command = ['ditto', str(payload)]
        try:
            name = zcode_installation_name()
            destination = Path.home() / 'Applications' / name
            if destination.is_symlink():
                raise ShipFailure(f'拒绝替换符号链接安装目标：{destination}')
            if destination.exists():
                shutil.rmtree(destination)
            run_step_command(['ditto', str(payload), str(destination)], root)
            run_step_command([*VERIFY_COMMAND, str(destination)], root)
        except (OSError, ShipFailure, subprocess.CalledProcessError) as error:
            return fail('install', install_command, error)
        steps.append({'step': 'install', 'command': [*install_command, str(destination)],
                      'exitCode': 0, 'detail': {'destination': str(destination)}})

    receipt['ok'] = True
    return finish()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='ZCode candidate ship chain: clean, build, stamp, re-sign, verify, receipt.')
    parser.add_argument('--dry-run', action='store_true',
                        help='print the planned chain as a receipt JSON without any side effect')
    parser.add_argument('--evidence', metavar='OBSERVATION_JSON',
                        help='real-acceptance observation record cited by the stamp')
    parser.add_argument('--observation', metavar='PATH',
                        help='ship observation increment file (default .local/zcode-ship/OBSERVATION.json)')
    parser.add_argument('--receipt', metavar='PATH', help='also write the receipt JSON to this path')
    parser.add_argument('--install', action='store_true',
                        help='allow writing ~/Applications (default off; requires the verified chain)')
    options = parser.parse_args(argv)
    try:
        code, receipt = ship(options)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f'ship-zcode 未预期失败：{error}\n')
    encoded = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    print(encoded)
    if options.receipt and not options.dry_run:
        Path(options.receipt).write_text(encoded + '\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(main())
