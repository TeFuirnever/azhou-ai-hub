"""Cross-platform fake Codex CLI for integration tests."""
from __future__ import annotations

import os
from pathlib import Path
import sys


FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, pathlib, shutil, sys
h = pathlib.Path(os.environ['CODEX_HOME'])
a = sys.argv[2:-1]
state = h / 'native-marketplace.json'
log = h / 'native-operations.jsonl'
h.mkdir(parents=True, exist_ok=True)
with log.open('a') as out:
    out.write(json.dumps(a)+'\n')
def source():
    return json.loads(state.read_text())['source']
def installed():
    return h / 'plugins/cache/pstack-claude/pstack/0.9.102'
if a[:2] == ['marketplace', 'add']:
    assert pathlib.Path(a[2]).is_absolute()
    assert not a[2].startswith('https:')
    state.write_text(json.dumps({'source': a[2]}))
    print(json.dumps({'marketplaceName': 'pstack-claude', 'installedRoot': a[2], 'alreadyAdded': False}))
elif a == ['add', 'pstack@pstack-claude']:
    if os.environ.get('PSTACK_TEST_FAIL_PLUGIN'):
        sys.exit('fixture plugin installation failure')
    shutil.copytree(pathlib.Path(source())/'plugins/pstack', installed(), dirs_exist_ok=True)
    print(json.dumps({'pluginId': 'pstack@pstack-claude', 'version': '0.9.102', 'installedPath': str(installed())}))
elif a == ['marketplace', 'list']:
    entries = [{'name':'pstack-claude', 'root':source(), 'marketplaceSource':{'sourceType':'local','source':source()}}] if state.exists() else []
    print(json.dumps({'marketplaces':entries}))
elif a == ['list', '--marketplace', 'pstack-claude'] or a == ['list']:
    entries = [{'pluginId':'pstack@pstack-claude','name':'pstack','marketplaceName':'pstack-claude','installed':True,'enabled':True,'source':{'source':'local','path':str(pathlib.Path(source())/'plugins/pstack')},'marketplaceSource':{'sourceType':'local','source':source()}}] if installed().exists() else []
    print(json.dumps({'installed':entries,'available':[]}))
elif a == ['remove', 'pstack@pstack-claude']:
    shutil.rmtree(installed())
    print(json.dumps({'removed':True}))
elif a == ['marketplace', 'remove', 'pstack-claude']:
    state.unlink()
    print(json.dumps({'removed':True}))
else:
    sys.exit('unexpected command: '+repr(a))
'''


def install_fake_codex(binary: Path, *, failure: str | None = None) -> Path:
    """Install a runnable fake CLI and return its path for ``codex_bin``."""
    binary = Path(binary)
    source = FAKE_CODEX if failure is None else f"#!/usr/bin/env python3\nimport sys\nsys.exit({failure!r})\n"

    if os.name == "nt":
        launcher = binary.with_suffix(".cmd")
        script = launcher.with_suffix(".py")
        script.write_text(source, encoding="utf-8")
        launcher.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" %*\r\nexit /b %ERRORLEVEL%\r\n',
            encoding="utf-8",
        )
        return launcher

    binary.write_text(source, encoding="utf-8")
    binary.chmod(0o700)
    return binary
