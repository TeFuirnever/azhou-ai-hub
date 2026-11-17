"""Opt-in, bounded Python execution observations for development diagnostics."""

import json
import os
import stat
import sys


fifo = os.environ.get('SSI_RECORDER_FIFO')
target = os.environ.get('SSI_RECORDER_TARGET')
operations = frozenset(('validate-evidence', 'validate-reflection', 'review-citations', 'render'))


def emit(event):
    try:
        flags = os.O_WRONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(fifo, flags)
        try:
            if stat.S_ISFIFO(os.fstat(fd).st_mode):
                os.write(fd, (json.dumps(event, separators=(',', ':')) + '\n').encode())
        finally:
            os.close(fd)
    except OSError:
        pass


def audit(event, args):
    if event == 'subprocess.Popen':
        emit({'event': 'subprocess_attempt', 'pid': os.getpid()})


if fifo and target:
    sys.addaudithook(audit)
    emit({'event': 'python_start', 'pid': os.getpid()})
    if len(sys.argv) > 1 and sys.argv[1] in operations and os.path.realpath(sys.argv[0]) == os.path.realpath(target):
        emit({'event': 'target_start', 'pid': os.getpid(), 'operation': sys.argv[1]})
