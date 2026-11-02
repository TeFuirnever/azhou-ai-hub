"""Binary command capture and immutable receipts for isolated offline checks.

Restores the historical command log with an explicit filesystem scope. C receipts
require an observed native wait; E records cannot establish command completion.
"""
from pathlib import Path
import math
import hashlib
import stat
import os
import shutil
import signal
import subprocess
import sys
import time

from offline_runtime import (DirectChildIdentity, SupervisorSignal, json_new,
                             own, scope_root, sha, utc, validate_result)

def wait_for_check(process, timeout, identity, interruption=lambda: None):
    """Own only this directly spawned check; unknown identity never authorizes a signal."""
    code = None
    error = None
    timed_out = False
    cleanup = "not_needed"
    deadline = time.monotonic() + timeout
    try:
        while True:
            if interruption() is not None:
                raise SupervisorSignal(interruption())
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                code = process.wait(timeout=min(0.1, remaining))
                break
            except subprocess.TimeoutExpired:
                pass
    except BaseException as exc:
        error = {"type":type(exc).__name__, "message":str(exc), "signal":getattr(exc,"signum",None)}
    finally:
        if process.returncode is None:
            try:
                if identity.verify(process):
                    process.terminate()
                    cleanup = "terminate_sent_wait_unverified"
                else:
                    cleanup = "identity_unverified_no_signal"
            except (OSError, ChildProcessError) as exc:
                cleanup = "identity_unavailable_no_signal"
                if error is None: error = {"type":type(exc).__name__,"message":str(exc),"signal":None}
            try:
                code = process.wait(timeout=5)
                if cleanup == "terminate_sent_wait_unverified":
                    cleanup = "direct_check_exited_descendants_unverified"
            except (subprocess.TimeoutExpired, OSError) as exc:
                code = None
                if error is None: error = {"type":type(exc).__name__,"message":str(exc),"signal":None}
        else:
            code = process.returncode
    return {"exit_code":code,"signal":-code if code is not None and code<0 else None,
            "execution_state":"timed_out" if timed_out else ("exit_unknown" if code is None else ("signaled" if code<0 else "exited")),
            "error":error,"cleanup":cleanup}


class SignalLatch:
    """Retain the first termination signal through owned cleanup."""
    def __enter__(self):
        self.first = None
        self.previous = {sig: signal.getsignal(sig)
                         for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        def receive(signum, frame):
            if self.first is None:
                self.first = signum
        for sig in self.previous:
            signal.signal(sig, receive)
        return lambda: self.first

    def __exit__(self, *exc):
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)
        if self.first is not None and (not exc or exc[0] is None):
            raise SupervisorSignal(self.first)


class CommandLog:
    def __init__(self, directory, inputs, interruption=lambda: None, *, root, stage=None):
        self.root = scope_root(root)
        self.directory = own(directory, root=self.root)
        self.stage = own(stage if stage is not None else self.root, root=self.root)
        if not self.directory.is_dir() or not self.stage.is_dir():
            raise ValueError("command and stage directories must exist")
        self.inputs = [dict(item) for item in inputs]
        for item in self.inputs:
            relative = Path(item['path'])
            if relative.is_absolute():
                raise ValueError("registered input paths must be scope-relative")
            own(self.root / relative, root=self.root)
        self.counter = 0
        self.interruption = interruption

    def stable(self):
        try:
            return all(self._stable_digest(own(self.root / item['path'], root=self.root)) == item['sha256']
                       for item in self.inputs)
        except (OSError, ValueError):
            return False

    @staticmethod
    def _stable_digest(path):
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('registered input is not a regular file')
            digest = hashlib.sha256()
            while data := os.read(descriptor, 65536):
                digest.update(data)
            after = os.fstat(descriptor)
            named = Path(path).stat(follow_symlinks=False)
            fields = ('st_dev', 'st_ino', 'st_uid', 'st_mode', 'st_nlink',
                      'st_size', 'st_mtime_ns', 'st_ctime_ns')
            if any(getattr(before, field) != getattr(after, field)
                   or getattr(before, field) != getattr(named, field) for field in fields):
                raise ValueError('registered input changed while checking stability')
            return digest.hexdigest()
        finally:
            os.close(descriptor)

    def _postcheck(self, items, phase, errors):
        unchanged = True
        fields = ('st_dev', 'st_ino', 'st_uid', 'st_mode', 'st_nlink',
                  'st_size', 'st_mtime_ns', 'st_ctime_ns')
        for item in items:
            descriptor = None
            try:
                path = own(self.root / item['path'], root=self.root)
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError('registered input is no longer a regular file')
                digest = hashlib.sha256()
                while data := os.read(descriptor, 65536):
                    digest.update(data)
                after = os.fstat(descriptor)
                named = path.stat(follow_symlinks=False)
                if (any(getattr(before, field) != getattr(after, field)
                        or getattr(before, field) != getattr(named, field) for field in fields)
                        or digest.hexdigest() != item['sha256']):
                    raise ValueError('registered input changed during command or postcheck')
            except (OSError, ValueError) as exc:
                unchanged = False
                errors.append({'phase': phase, 'path': item['path'],
                               'type': type(exc).__name__, 'message': str(exc)})
            finally:
                if descriptor is not None:
                    os.close(descriptor)
        return unchanged

    def _environment(self, case, provided):
        environment = {key: os.environ[key]
                       for key in ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE') if key in os.environ}
        private_paths = {'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SWIFT_MODULECACHE_PATH',
                         'CLANG_MODULE_CACHE_PATH', 'XDG_CACHE_HOME'}
        allowed = private_paths | {'PATH', 'LANG', 'LC_ALL', 'LC_CTYPE',
                                   'PYTHONDONTWRITEBYTECODE', 'PYTHONPATH', 'SDKROOT', 'DEVELOPER_DIR'}
        for name in ('home', 'tmp'):
            (case / name).mkdir(mode=0o700)
        environment.update(HOME=str(case / 'home'), TMPDIR=str(case / 'tmp'),
                           PYTHONDONTWRITEBYTECODE='1')
        if provided is not None:
            if set(provided) - allowed:
                raise ValueError("unsupported environment keys; do not inherit daily configuration")
            for key, value in provided.items():
                if not isinstance(value, str) or '\0' in value:
                    raise ValueError("environment values must be NUL-free strings")
                if key in private_paths:
                    own(Path(value), root=self.root)
                if key == 'PYTHONPATH':
                    for component in value.split(os.pathsep):
                        own(Path(component), root=self.root)
                environment[key] = value
        return environment

    def record(self, argv, *args, **kwargs):
        if self.interruption() is not None:
            raise SupervisorSignal(self.interruption())
        allowed = {'cwd', 'env', 'timeout', 'check', 'text', 'encoding', 'errors',
                   'capture_output', 'artifact_paths'}
        if args or set(kwargs) - allowed:
            raise ValueError("unsupported command shape")
        if not isinstance(argv, (list, tuple)) or not argv:
            raise ValueError("argv must be an explicit non-empty sequence")
        argv = [str(value) for value in argv]
        if any('\0' in value for value in argv):
            raise ValueError("NUL in command argument")
        executable = Path(argv[0])
        if (executable.name in {'open', 'osascript', 'launchctl'}
                or '.app' in executable.parts or any(x.endswith('.app') for x in executable.parts)):
            raise ValueError("host application execution is disabled")
        timeout = kwargs.get('timeout', 240)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("a finite positive timeout is required")
        if not self.stable():
            raise ValueError("registered input drift before command")
        case = self.directory / str(self.counter)
        self.counter += 1
        case.mkdir(mode=0o700)
        cwd = own(Path(kwargs.get('cwd', self.directory)), root=self.root)
        environment = self._environment(case, kwargs.get('env'))
        argument_inputs = [{'path': str(Path(value).relative_to(self.root)), 'sha256': sha(Path(value))}
                           for value in argv
                           if Path(value).is_absolute() and Path(value).is_relative_to(self.stage)
                           and Path(value).is_file() and own(Path(value), root=self.root)]
        started = utc()
        waited = {'exit_code': None, 'signal': None, 'execution_state': 'not_started',
                  'error': None, 'cleanup': 'not_needed'}
        original_error = None
        paths = [case / 'stdout.raw', case / 'stderr.raw']
        with paths[0].open('xb') as out, paths[1].open('xb') as err:
            for path in paths:
                path.chmod(0o600)
            try:
                child = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=out,
                                         stderr=err, start_new_session=True, close_fds=True)
                expected = shutil.which(argv[0]) if not executable.is_absolute() else argv[0]
                identity = (DirectChildIdentity() if expected is not None
                            and Path(expected).resolve() == Path(sys.executable).resolve()
                            else DirectChildIdentity(str(Path(expected or argv[0]).resolve())))
                waited = wait_for_check(child, timeout, identity, self.interruption)
            except OSError as exc:
                original_error = exc
                waited['error'] = {'type': type(exc).__name__, 'message': str(exc), 'signal': None}
            out.flush()
            err.flush()
            os.fsync(out.fileno())
            os.fsync(err.fileno())
        code = waited['exit_code']
        evidence_errors = []
        produced = list(kwargs.get('artifact_paths', []))
        if '-o' in argv and argv.index('-o') + 1 < len(argv):
            produced.append(Path(argv[argv.index('-o') + 1]))
        if executable.name == 'build-startup-assets':
            produced.extend(Path(value) for value in argv[3:])
        artifacts = []
        for value in produced:
            try:
                path = own(Path(value), root=self.root)
                if path.is_file() and path.is_relative_to(self.stage):
                    artifacts.append({'source_path': str(path.relative_to(self.root)),
                                      'source_sha256': sha(path), 'relation': 'produced',
                                      'file_state': 'present' if code == 0 else 'partial-unverified'})
            except (OSError, ValueError) as exc:
                evidence_errors.append({'phase': 'artifact_postcheck', 'path': str(value),
                                        'type': type(exc).__name__, 'message': str(exc)})
        arguments_unchanged = self._postcheck(argument_inputs, 'argument_input_postcheck', evidence_errors)
        unchanged = self._postcheck(self.inputs, 'registered_input_postcheck', evidence_errors)
        receipt = {'kind': 'C' if code is not None else 'E', 'started_at': started,
                   'observed_at': utc(), 'argv': argv, 'cwd': str(cwd), **waited,
                   'inputs': self.inputs, 'argument_inputs': argument_inputs,
                   'argument_inputs_unchanged': arguments_unchanged, 'inputs_unchanged': unchanged,
                   'evidence_errors': evidence_errors, 'evidence_complete': not evidence_errors,
                   'outputs': {'mode': 'separate', 'raw_files':
                               [{'path': str(path.relative_to(self.root)), 'sha256': sha(path)} for path in paths]},
                   'artifacts': artifacts, 'scope': 'offline project-private candidate; not host evidence'}
        validate_result(receipt)
        json_new(case / 'command.json', receipt, root=self.root)
        if original_error is not None:
            raise original_error
        if not unchanged or not arguments_unchanged or evidence_errors:
            raise ValueError("registered input drift or artifact evidence incomplete; stopped")
        output, error = (path.read_bytes() for path in paths)
        if kwargs.get('text') or kwargs.get('encoding'):
            output = output.decode(kwargs.get('encoding') or 'utf-8', errors=kwargs.get('errors') or 'strict')
            error = error.decode(kwargs.get('encoding') or 'utf-8', errors=kwargs.get('errors') or 'strict')
        if self.interruption() is not None:
            raise SupervisorSignal(self.interruption())
        if code is None or waited['execution_state'] == 'timed_out':
            raise subprocess.TimeoutExpired(argv, timeout, output, error)
        if kwargs.get('check') and (code != 0 or waited['error'] is not None):
            raise subprocess.CalledProcessError(code, argv, output, error)
        return subprocess.CompletedProcess(argv, code, output, error)

    def check_output(self, argv, **kwargs):
        return self.record(argv, check=True, **kwargs).stdout
