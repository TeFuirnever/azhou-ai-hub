#!/usr/bin/env python3
"""Compile and run the ZCode driver contract with synthetic ports; never launch a host."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sources = [root / 'Native' / name for name in
               ('SkinHostContract.swift', 'ZCodeSkinDriver.swift', 'ZCodeSkinDriverTests.swift')]
    records = []
    with tempfile.TemporaryDirectory(prefix='zcode-native-contract-') as temp:
        executable = Path(temp) / 'zcode-contract'
        commands = [['/usr/bin/swiftc', *(str(p) for p in sources), '-o', str(executable)],
                    [str(executable)]]
        for stage, command in zip(('compile', 'synthetic-run'), commands):
            start = datetime.datetime.now(datetime.timezone.utc).isoformat()
            result = subprocess.run(command, capture_output=True, timeout=120)
            record = dict(stage=stage, started_at=start,
                          ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          native_wait_exit=result.returncode,
                          stdout=result.stdout.decode('utf-8'), stderr=result.stderr.decode('utf-8'),
                          real_host_executed=False)
            records.append(record)
            if result.returncode:
                break
    report = dict(scope='synthetic ZCode native contract, not host acceptance',
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                  records=records, passed=len(records) == 2 and all(r['native_wait_exit'] == 0 for r in records))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
