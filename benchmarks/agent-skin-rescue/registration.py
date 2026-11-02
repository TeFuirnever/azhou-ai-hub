"""Read only three public installation files; never inspects daily user state."""
from pathlib import Path
import ast,hashlib,os,plistlib,stat
L=Path(__file__).resolve().parent
from datetime import datetime,timezone
def utc():return datetime.now(timezone.utc).isoformat()
ACTUAL_BUNDLE=Path('/Applications/ZCode.app')


def expected_installation(expected=None):
    if expected is None:
        return {'scope':'no-historical-baseline-provided','expected':None}
    required={'bundle_id','version','build','info_sha256','executable_sha256','app_asar_sha256'}
    if not isinstance(expected,dict) or set(expected)!=required:
        raise ValueError('explicit baseline must declare exactly six metadata and SHA fields')
    return {'scope':'caller-provided-baseline-not-current-validation','expected':dict(expected)}


def _read(path,bundle,*,retain=False):
    relative=path.relative_to(bundle)
    if '..' in relative.parts:raise ValueError('installation path escapes bundle')
    descriptors=[];directories=[]
    directory_key=lambda s:(s.st_dev,s.st_ino,s.st_uid,s.st_mode)
    file_key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)
    try:
        current=os.open(bundle,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        descriptors.append(current);bundle_identity=directory_key(os.fstat(current))
        for part in relative.parts[:-1]:
            named=os.stat(part,dir_fd=current,follow_symlinks=False)
            if not stat.S_ISDIR(named.st_mode):raise ValueError('installation directory is not an ordinary directory')
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current)
            descriptors.append(next_fd)
            if directory_key(named)!=directory_key(os.fstat(next_fd)):raise ValueError('installation directory changed during open')
            directories.append((current,part,next_fd,directory_key(named)));current=next_fd
        fd=os.open(relative.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=current);descriptors.append(fd)
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):raise ValueError('installation input is not regular')
        data=[];digest=hashlib.sha256();size=0
        while part:=os.read(fd,1024*1024):
            digest.update(part);size+=len(part)
            if retain:
                if size>1024*1024:raise ValueError('installation metadata exceeds observation bound')
                data.append(part)
        after=os.fstat(fd);named=os.stat(relative.name,dir_fd=current,follow_symlinks=False)
        if file_key(before)!=file_key(after) or file_key(before)!=file_key(named):raise ValueError('installation input changed during observation')
        for parent,name,child,expected in directories:
            if directory_key(os.fstat(child))!=expected or directory_key(os.stat(name,dir_fd=parent,follow_symlinks=False))!=expected:
                raise ValueError('installation directory binding changed during observation')
        if directory_key(os.stat(bundle,follow_symlinks=False))!=bundle_identity:raise ValueError('bundle binding changed during observation')
        return b''.join(data),{'path':str(path),'resolvedPath':str(path),'sha256':digest.hexdigest(),'bytes':size,'identity':list(file_key(after))}
    except OSError as exc:
        raise ValueError('installation descriptor could not be bound without following links') from exc
    finally:
        for descriptor in reversed(descriptors):os.close(descriptor)


def fingerprint_file(path,*,root):
    """Hash one ordinary file through a no-follow descriptor chain under root."""
    path,root=Path(path),Path(root)
    if (not path.is_absolute() or not root.is_absolute() or root.resolve()!=root
            or not path.is_relative_to(root) or '..' in path.relative_to(root).parts):
        raise ValueError('fingerprint input outside explicit canonical scope')
    return _read(path,root)[1]


def observe_installation(bundle,*,synthetic=False,root=None,expected=None):
    root=Path(root) if root is not None else L.parents[1]
    if root.resolve()!=L.parents[1]:raise ValueError('scope must be this source worktree')
    bundle=Path(bundle)
    if not bundle.is_absolute() or bundle.resolve()!=bundle or bundle.is_symlink():raise ValueError('bundle must be canonical')
    if synthetic:
        if not bundle.is_relative_to(root/'.scratch'):raise ValueError('synthetic bundle outside worktree evidence')
    elif bundle!=ACTUAL_BUNDLE:raise ValueError('actual mode only reads registered ZCode bundle')
    info_bytes,info_record=_read(bundle/'Contents/Info.plist',bundle,retain=True);info=plistlib.loads(info_bytes)
    executable=info['CFBundleExecutable']
    if not isinstance(executable,str) or not executable or Path(executable).name!=executable or executable in {'.','..'}:raise ValueError('invalid bundle executable')
    _,exe_record=_read(bundle/'Contents/MacOS'/executable,bundle)
    _,asar_record=_read(bundle/'Contents/Resources/app.asar',bundle)
    metadata={'bundle_id':info.get('CFBundleIdentifier'),'version':info.get('CFBundleShortVersionString'),'build':info.get('CFBundleVersion'),'executable':executable}
    historical=expected_installation(expected);expected=historical['expected']
    comparisons={} if expected is None else {k:metadata[k]==expected[k] for k in ('bundle_id','version','build')}
    if expected is not None:
        comparisons.update(info_sha256=info_record['sha256']==expected['info_sha256'],executable_sha256=exe_record['sha256']==expected['executable_sha256'],app_asar_sha256=asar_record['sha256']==expected['app_asar_sha256'])
    return {'kind':'A','observed_at':utc(),'scope':'synthetic-bundle' if synthetic else 'current-public-installation-files-only','bundle':str(bundle),'metadata':metadata,'files':[info_record,exe_record,asar_record],'historicalBaseline':historical,'matchesHistoricalFilesAndMetadata':all(comparisons.values()) if comparisons else None,'comparisons':comparisons,'strictSignature':{'status':'not-run','existingEvidence':'failed; no waiver or repair','team':'unverified in this observation'},'nativeInstallRegistry':{'status':'not-read','reason':'daily application state is outside scope; candidate schema source is separately fingerprinted'},'hostLaunchAllowed':False}
