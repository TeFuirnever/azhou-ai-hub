"""Offline isolation plans. No process execution or shared-system operations."""
from pathlib import Path
import hashlib
import os
import stat
ROOT_KEYS = {'home': 'home', 'tmp': 'tmp', 'business': 'business', 'electron_user': 'electron-user', 'electron_session': 'electron-session', 'logs': 'logs', 'empty_workspace': 'empty-workspace'}
ENVIRONMENT_PATHS = {'HOME': 'home', 'TMPDIR': 'tmp', 'ZCODE_DATA_BASE_DIR': 'business', 'ZCODE_DESKTOP_USER_DATA_DIR': 'electron_user', 'ZCODE_DESKTOP_SESSION_DATA_DIR': 'electron_session'}
ZCODE_EXECUTABLE = '/Applications/ZCode.app/Contents/MacOS/ZCode'

class Isolation:
    """Private filesystem layout checks; no host execution authority."""

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_absolute() or '..' in self.root.parts or self.root.resolve() != self.root:
            raise ValueError('evidence root must be an absolute path without symlinks')
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 448:
            raise ValueError('evidence root must be private and owned')
        self._root_identity = self._identity(info)

    def _path(self, value):
        path = Path(value)
        if not path.is_absolute() or '..' in path.parts or path == self.root or (not path.is_relative_to(self.root)):
            raise ValueError('path outside exclusive full-chain candidate')
        return path

    def _identity(self, info):
        return [info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode)]

    def _open_directory(self, value):
        path = Path(value)
        if path != self.root:
            self._path(path)
        if self.root.resolve() != self.root:
            raise ValueError('candidate root contains a symlink')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(self.root, flags)
        try:
            if self._identity(os.fstat(fd)) != self._root_identity:
                raise ValueError('evidence root identity changed')
            for part in path.relative_to(self.root).parts:
                next_fd = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
                info = os.fstat(fd)
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 448:
                    raise ValueError('directory owner or private mode mismatch')
            info = os.fstat(fd)
            named = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 448 or (self._identity(info) != self._identity(named)):
                raise ValueError('directory path no longer identifies descriptor')
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _expected(self, run):
        paths = {key: str(run / suffix) for (key, suffix) in ROOT_KEYS.items()}
        paths['app_logs'] = str(run / 'business/.zcode/v2/logs')
        return paths

    def prepare_layout(self, run):
        """Create one new private layout; all parents must already exist privately."""
        run = self._path(run)
        parent_fd = self._open_directory(run.parent)
        try:
            os.mkdir(run.name, 448, dir_fd=parent_fd)
            fd = os.open(run.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                for suffix in ROOT_KEYS.values():
                    os.mkdir(suffix, 448, dir_fd=fd)
                business_fd = os.open('business', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    for part in ('.zcode', 'v2', 'logs'):
                        os.mkdir(part, 448, dir_fd=business_fd)
                        next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=business_fd)
                        os.close(business_fd)
                        business_fd = next_fd
                finally:
                    os.close(business_fd)
            finally:
                os.close(fd)
        finally:
            os.close(parent_fd)
        paths = self._expected(run)
        directories = [str(run), *paths.values(), str(run / 'business/.zcode'), str(run / 'business/.zcode/v2')]
        identities = {}
        for name in directories:
            bound = self._open_directory(name)
            try:
                identities[name] = self._identity(os.fstat(bound))
            finally:
                os.close(bound)
        result = {'schema': 'offline-isolation-layout.v1', 'run': str(run), **paths, 'directories': directories, 'directory_identities': identities, 'boundary': 'private filesystem candidate; not a same-UID security sandbox'}
        self.validate_layout(result)
        return result

    def validate_layout(self, layout):
        run = self._path(layout['run'])
        expected = self._expected(run)
        if any((layout.get(key) != value for (key, value) in expected.items())):
            raise ValueError('layout roots were replaced')
        directories = [str(run), *expected.values(), str(run / 'business/.zcode'), str(run / 'business/.zcode/v2')]
        if layout.get('directories') != directories or set(layout.get('directory_identities', {})) != set(directories):
            raise ValueError('incomplete layout identity declaration')
        for name in directories:
            bound = self._open_directory(name)
            try:
                if self._identity(os.fstat(bound)) != layout['directory_identities'][name]:
                    raise ValueError('layout directory identity changed')
            finally:
                os.close(bound)
        home_fd = self._open_directory(layout['home'])
        try:
            try:
                os.stat('.zcode', dir_fd=home_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('bootstrap HOME configuration fallback is not empty')
        finally:
            os.close(home_fd)
        return True

    def child_environment(self, parent, layout):
        """Return a child-only allowlist; never mutate the caller's environment."""
        self.validate_layout(layout)
        result = {key: parent[key] for key in ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE') if key in parent}
        if any((not isinstance(value, str) or '\x00' in value for value in result.values())):
            raise ValueError('invalid environment value')
        result.update({key: layout[value] for (key, value) in ENVIRONMENT_PATHS.items()})
        return result

    def launch_plan(self, layout, executable, *, configuration_guard=None, port=None):
        """Build a non-executable plan. Nothing supplied can authorize a host launch."""
        self.validate_layout(layout)
        if str(executable) != ZCODE_EXECUTABLE:
            raise ValueError('unexpected executable in ZCode plan')
        if port is not None and (type(port) is not int or not 1 <= port <= 65535):
            raise ValueError('fresh loopback port must be an integer')
        guard = {'status': 'unverified', 'scope': 'historical packaged source only'}
        blockers = ['host-execution-disabled', 'strict-signature-not-revalidated', 'new-serial-window-not-confirmed', 'actual-electron-home-data-log-paths-unverified', 'protocol-browser-security-storage-unverified', 'application-log-custody-unverified']
        if configuration_guard is None:
            blockers.append('bootstrap-source-guard-unverified')
        else:
            guard = self._check_configuration_guard(configuration_guard)
        return {'schema': 'offline-isolation-plan.v1', 'authority': 'offline-plan-only', 'hostLaunchAllowed': False, 'argv': [str(executable), '--remote-debugging-port=' + str(port)] if port is not None else None, 'cwd': layout['empty_workspace'], 'environmentPaths': {key: layout[value] for (key, value) in ENVIRONMENT_PATHS.items()}, 'expectedApplicationLogs': layout['app_logs'], 'supervisorLogs': layout['logs'], 'localSettingsGuard': 'new-HOME-.zcode-absent-without-content-read', 'configurationGuard': guard, 'actualElectronPaths': 'unverified', 'sharedBoundaries': {'protocolHandler': 'unverified', 'externalBrowser': 'unverified', 'oauth': 'unverified', 'securityStorage': 'unverified'}, 'blockers': blockers, 'limits': ['private HOME is not a separate macOS user or Keychain', 'directory checks do not prevent adversarial same-UID ancestor renames after return', 'a static path expectation does not prove pre-launch absence of shared effects']}

    def validate_fixture_observation(self, layout, observation):
        """Check a caller-supplied synthetic observation, never attest a real host."""
        self.validate_layout(layout)
        if observation.get('scope') != 'synthetic-child':
            raise ValueError('only an explicitly synthetic observation is accepted')
        actual = observation.get('env')
        expected = {key: layout[value] for (key, value) in ENVIRONMENT_PATHS.items()}
        if not isinstance(actual, dict) or any((actual.get(key) != value for (key, value) in expected.items())):
            raise ValueError('synthetic child environment path mismatch')
        if observation.get('app_logs') != layout['app_logs']:
            raise ValueError('synthetic child log expectation mismatch')
        return {'schema': 'offline-isolation-observation.v1', 'status': 'synthetic-match', 'scope': 'synthetic-child', 'observed_environment': expected, 'app_logs': layout['app_logs'], 'host_validation': 'not_run', 'origin': 'caller-supplied observation; enclosing command must bind its actual producer'}

    def _check_configuration_guard(self, configuration_guard):
        if not isinstance(configuration_guard, dict) or set(configuration_guard) != {'path', 'sha256'} or (not isinstance(configuration_guard['sha256'], str)) or (len(configuration_guard['sha256']) != 64) or any((c not in '0123456789abcdef' for c in configuration_guard['sha256'])):
            raise ValueError('untrusted bootstrap source guard')
        path = self._path(configuration_guard['path'])
        parent = self._open_directory(path.parent)
        fd = None
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            before = os.fstat(fd)

            def identity(info):
                return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)
            if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_mode & 63 or (before.st_nlink != 1):
                raise ValueError('untrusted static source permissions')
            data = b''
            while (part := os.read(fd, 65536)):
                data += part
                if len(data) > 1048576:
                    raise ValueError('static source metadata exceeds bound')
            if identity(before) != identity(os.fstat(fd)) or identity(before) != identity(os.stat(path.name, dir_fd=parent, follow_symlinks=False)) or hashlib.sha256(data).hexdigest() != configuration_guard['sha256']:
                raise ValueError('untrusted bootstrap source guard')
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)
        return {'status': 'caller-supplied-static-checked', 'scope': 'supplied metadata only; never host authority', **configuration_guard}
