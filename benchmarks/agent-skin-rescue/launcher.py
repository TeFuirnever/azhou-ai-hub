"""Offline candidate supervisor. Host execution is unconditionally disabled."""
from pathlib import Path
import copy,json,os,re,shutil,signal,subprocess,sys,time,uuid
L=Path(__file__).resolve().parent
from offline_runtime import DirectChildIdentity,Journal,json_new,own,sha,utc,validate_result,SupervisorSignal
from command_log import SignalLatch
from registration import fingerprint_file
def bound_sha(path,root):return fingerprint_file(path,root=root)['sha256']


def host_launch(*args,**kwargs):
    raise RuntimeError('HOST EXECUTION DISABLED: signature, isolation, fresh registration and serial window not satisfied')


def private_dir(path,*,root):
    path=own(Path(path),root=root)
    info=path.lstat()
    if not path.is_dir() or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('private directory required')
    return path


class Supervisor:
    """Keeps ownership of each registered direct child through callback and real wait."""
    def __init__(self,directory,interruption=lambda:None,identity_factory=None,*,root=None):
        self.root=Path(root) if root is not None else L.parents[1]
        if self.root.resolve()!=L.parents[1]:raise ValueError('scope must be this source worktree')
        self.directory=private_dir(directory,root=self.root);self.interruption=interruption
        self.identity_factory=identity_factory
        self.scripts={p:bound_sha(own(p,root=self.root),self.root) for p in [L/'fixtures/controlled_host.py',L/'rebind/check_binding.py',L/'runtime/offline.mjs',L/'archive.py'] if p.is_file()}

    def _unchanged(self,path,expected):
        try:return bound_sha(own(path,root=self.root),self.root)==expected
        except (OSError,ValueError):return False

    def _checked_arguments(self,script,argv,fixture_mode):
        fixture=L/'fixtures/controlled_host.py'
        registrations={fixture:({'--request':'file','--out':'new-directory'},set()),
            L/'rebind/check_binding.py':({'--root':'directory','--binding':'file','--producer':'file'},{'--root','--binding','--producer'}),
            L/'runtime/offline.mjs':({'--request':'file','--out':'new-directory'},{'--request','--out'}),
            L/'archive.py':({'--request':'file','--out':'new-directory'},{'--request','--out'})}
        allowed,required=registrations[script]
        if fixture_mode is not None and (script!=fixture or fixture_mode not in {'bytes','failure','hold','partial','ignore-term','artifacts'}):
            raise ValueError('unregistered fixture authority')
        position=2 if len(argv)>2 and argv[1]=='-B' else 1
        arguments=argv[position+1:]
        if len(arguments)%2:raise ValueError('registered arguments require exact flag/path pairs')
        seen=set()
        for flag,value in zip(arguments[::2],arguments[1::2]):
            if flag not in allowed or flag in seen:raise ValueError('unregistered or repeated command argument')
            seen.add(flag);path=own(Path(value),root=self.root)
            if allowed[flag]=='file' and not path.is_file():raise ValueError('registered input file is missing')
            if allowed[flag]=='directory':private_dir(path,root=self.root)
            if allowed[flag]=='new-directory' and (not path.is_relative_to(self.directory) or path.exists()):
                raise ValueError('output must be a new supervised directory')
        if required-seen:raise ValueError('required registered arguments are missing')

    def fixture(self,label,mode,*,handoff=None,environment=None,timeout=4):
        if mode not in {'bytes','failure','hold','partial','ignore-term'}:raise ValueError('unregistered controlled mode')
        return self.run(label,[sys.executable,'-B',str(L/'fixtures/controlled_host.py')],environment=environment,timeout=timeout,handoff=handoff,fixture_mode=mode)

    def run(self,label,argv,*,environment=None,timeout=20,handoff=None,fixture_mode=None):
        argv=[str(x) for x in argv]
        if not re.fullmatch('[a-z][a-z0-9-]{0,50}',label):raise ValueError('invalid command label')
        if not 0<timeout<=60:raise ValueError('offline command budget invalid')
        script=Path(argv[2] if len(argv)>2 and argv[1]=='-B' else argv[1]) if len(argv)>1 else None
        expected_exe=Path(sys.executable).resolve() if script and script.suffix=='.py' else Path(shutil.which('node') or '/missing').resolve()
        actual_exe=Path(shutil.which(argv[0]) or argv[0]).resolve()
        if script not in self.scripts or not self._unchanged(script,self.scripts[script]) or actual_exe!=expected_exe:
            raise ValueError('only pinned registered offline commands may run')
        if handoff and script!=L/'fixtures/controlled_host.py':raise ValueError('handoff only for controlled fixture')
        self._checked_arguments(script,argv,fixture_mode)
        if environment:
            allowed={'PATH','LANG','LC_ALL','LC_CTYPE','USER','LOGNAME','SHELL','__CF_USER_TEXT_ENCODING','HOME','TMPDIR','ZCODE_DATA_BASE_DIR','ZCODE_DESKTOP_USER_DATA_DIR','ZCODE_DESKTOP_SESSION_DATA_DIR','CHAIN_APP_LOGS'}
            if set(environment)-allowed:raise ValueError('unreviewed child environment key')
            for key in ('HOME','TMPDIR'):
                if key in environment:private_dir(Path(environment[key]),root=self.root)
        argument_inputs=[{'path':str(Path(a).relative_to(self.root)),'sha256':bound_sha(own(Path(a),root=self.root),self.root)} for a in argv if Path(a).is_absolute() and Path(a).is_relative_to(self.root) and Path(a).is_file()]
        output_dir=Path(argv[argv.index('--out')+1]) if '--out' in argv else None
        if output_dir is not None:
            own(output_dir,root=self.root)
            if not output_dir.is_relative_to(self.directory) or output_dir.exists() or output_dir==self.directory/label:raise ValueError('output must be a new separate supervised directory')
            private_dir(output_dir.parent,root=self.root)
        case=self.directory/label;case.mkdir(mode=0o700);private_dir(case,root=self.root)
        nonce=uuid.uuid4().hex;cid=str(uuid.uuid4());started=utc();events=Journal(case/'events.jsonl',argv,cid,root=self.root)
        errors=[]
        def emit(event,**kw):
            try:events.emit(event,**kw)
            except BaseException as exc:errors.append({'event':event,'type':type(exc).__name__,'message':str(exc)})
        env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','LC_CTYPE') if k in os.environ}
        if environment:
            allowed={'PATH','LANG','LC_ALL','LC_CTYPE','USER','LOGNAME','SHELL','__CF_USER_TEXT_ENCODING','HOME','TMPDIR','ZCODE_DATA_BASE_DIR','ZCODE_DESKTOP_USER_DATA_DIR','ZCODE_DESKTOP_SESSION_DATA_DIR','CHAIN_APP_LOGS'}
            if set(environment)-allowed:raise ValueError('unreviewed child environment key')
            env.update(environment)
        for key,dirname in [('HOME','home'),('TMPDIR','tmp')]:
            if key not in env:
                (case/dirname).mkdir(mode=0o700);env[key]=str(case/dirname)
            private_dir(Path(env[key]),root=self.root)
        if fixture_mode:env.update(CHAIN_CASE=str(case),CHAIN_MODE=fixture_mode,CHAIN_NONCE=nonce)
        env['PYTHONDONTWRITEBYTECODE']='1'
        child=None;code=None;operation_error=None;timed_out=False;cleanup='not_needed';identity_state='not_checked';handoff_state='not_offered'
        out=err=None
        identity=self.identity_factory() if self.identity_factory else (DirectChildIdentity() if actual_exe==Path(sys.executable).resolve() else DirectChildIdentity(str(actual_exe)))
        try:
            out=os.open(case/'stdout.raw',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            err=os.open(case/'stderr.raw',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            emit('spawn_intent',authority='synthetic-only',cleanup_owner='supervisor')
            if self.interruption() is not None:raise SupervisorSignal(self.interruption())
            child=subprocess.Popen(argv,cwd=case,env=env,stdout=out,stderr=err,close_fds=True,start_new_session=True)
            emit('spawned_unverified',pid=child.pid)
            if fixture_mode in {'hold','partial','ignore-term'}:
                deadline=time.monotonic()+1.5
                while not (case/'ready.json').is_file():
                    if self.interruption() is not None:raise SupervisorSignal(self.interruption())
                    if time.monotonic()>deadline:raise TimeoutError('controlled fixture readiness')
                    time.sleep(.005)
                ready=json.loads((case/'ready.json').read_bytes())
                if ready!={'pid':child.pid,'nonce':nonce,'scope':'synthetic-child'}:raise ValueError('fixture ready mismatch')
                if not identity.verify(child):raise ValueError('direct child identity unverified')
                identity_state='verified-direct-synthetic-child'
                offer={'schema':'offline-handoff.v1','authority':'synthetic-probe-only','command_id':cid,'pid':child.pid,'nonce':nonce,'cleanup_owner':'supervisor','ready':{'path':str(case/'ready.json'),'sha256':bound_sha(case/'ready.json',self.root)}}
                json_new(case/'handoff-offer.json',offer,root=self.root);handoff_state='offered';emit('handoff_offered',pid=child.pid)
                ack=handoff(copy.deepcopy(offer),case) if handoff and getattr(handoff,'accepts_case',False) else handoff(copy.deepcopy(offer)) if handoff else copy.deepcopy(offer)
                if ack!=offer:raise ValueError('handoff acknowledgment mismatch')
                if not identity.verify(child):raise ValueError('identity changed during handoff')
                json_new(case/'handoff-accepted.json',ack,root=self.root);handoff_state='accepted-supervisor-retains-ownership';emit('handoff_accepted',pid=child.pid)
                json_new(case/'release.json',{'nonce':nonce,'authority':'supervisor'},root=self.root)
            deadline=time.monotonic()+timeout
            while True:
                if self.interruption() is not None:raise SupervisorSignal(self.interruption())
                remaining=deadline-time.monotonic()
                if remaining<=0:timed_out=True;break
                try:code=child.wait(timeout=min(.1,remaining));break
                except subprocess.TimeoutExpired:pass
        except BaseException as exc:
            operation_error={'type':type(exc).__name__,'message':str(exc),'signal':getattr(exc,'signum',None)};emit('operation_error',error=operation_error)
        finally:
            # A signal is latched by the caller and cannot interrupt this owned cleanup.
            if child is not None and child.returncode is None:
                try:
                    if identity.verify(child):child.terminate();cleanup='terminate-sent-wait-unverified';emit('terminate_sent',pid=child.pid)
                    else:cleanup='identity-unverified-no-signal'
                except (OSError,ChildProcessError) as exc:
                    cleanup='identity-unavailable-no-signal';errors.append({'event':'cleanup_identity','type':type(exc).__name__,'message':str(exc)})
                try:
                    code=child.wait(timeout=5)
                    if cleanup=='terminate-sent-wait-unverified':cleanup='direct-child-exited-descendants-unverified'
                except (subprocess.TimeoutExpired,OSError) as exc:errors.append({'event':'cleanup_wait','type':type(exc).__name__,'message':str(exc)});code=None
            if child is not None and child.returncode is not None:code=child.returncode;emit('wait_observed',pid=child.pid,returncode=code)
            for fd in (out,err):
                if fd is not None:
                    try:os.fsync(fd)
                    except OSError as exc:errors.append({'event':'raw_fsync','type':type(exc).__name__,'message':str(exc)})
                    finally:
                        try:os.close(fd)
                        except OSError as exc:errors.append({'event':'raw_close','type':type(exc).__name__,'message':str(exc)})
            try:events.close()
            except OSError as exc:errors.append({'event':'journal_close','type':type(exc).__name__,'message':str(exc)})
        state='exit_unknown' if child is not None and code is None else 'not_started' if code is None else 'timed_out' if timed_out else 'signaled' if code<0 else 'exited'
        artifacts=[{'source_path':str(p.relative_to(self.root)),'source_sha256':bound_sha(p,self.root),'relation':'produced','file_state':'partial' if p.name=='partial.json' else 'present'} for p in [case/'ready.json',case/'observation.json',case/'partial.json'] if p.is_file()]
        if output_dir is not None:
            try:
                private_dir(output_dir,root=self.root)
                for product in sorted(output_dir.rglob('*')):
                    if product.is_symlink():raise ValueError('produced artifact contains a symlink')
                    if product.is_file():
                        artifacts.append({'source_path':str(product.relative_to(self.root)),'source_sha256':bound_sha(own(product,root=self.root),self.root),'relation':'produced','file_state':'present' if state=='exited' and code==0 and operation_error is None else 'partial-unverified'})
            except (OSError,ValueError) as exc:
                errors.append({'event':'declared_output','type':type(exc).__name__,'message':str(exc)})
        script_unchanged=self._unchanged(script,self.scripts[script])
        argument_inputs_unchanged=all(self._unchanged(self.root/a['path'],a['sha256']) for a in argument_inputs)
        if not script_unchanged:errors.append({'event':'script_input','type':'InputDrift','message':'pinned script changed or became unavailable after wait'})
        if not argument_inputs_unchanged:errors.append({'event':'argument_input','type':'InputDrift','message':'argument input changed or became unavailable after wait'})
        result={'kind':'C' if code is not None else 'E','command_id':cid,'started_at':started,'observed_at':utc(),'argv':argv,'cwd':str(case),'exit_code':code,'signal':-code if code is not None and code<0 else None,'execution_state':state,'error':operation_error,'cleanup':cleanup,'identity':identity_state,'handoff_state':handoff_state,'evidence_errors':errors,'successful':state=='exited' and code==0 and operation_error is None and not errors,'argument_inputs':argument_inputs,'argument_inputs_unchanged':argument_inputs_unchanged,'script_input':{'path':str(script.relative_to(self.root)),'sha256':self.scripts[script],'unchanged':script_unchanged},'outputs':{'mode':'separate','stability':'wait-observed' if code is not None else 'unverified-live-writer','raw_files':[{'path':str(p.relative_to(self.root)),'sha256':bound_sha(p,self.root)} for p in [case/'stdout.raw',case/'stderr.raw'] if p.is_file()]},'events':{'path':str(events.path.relative_to(self.root)),'sha256':bound_sha(events.path,self.root)},'artifacts':artifacts,'supervisor_artifacts':[{'path':str(p.relative_to(self.root)),'sha256':bound_sha(p,self.root),'relation':'supervisor-produced-not-child'} for p in [case/'handoff-offer.json',case/'handoff-accepted.json',case/'release.json'] if p.is_file()],'scope':'offline synthetic only; no host acceptance'}
        result['successful']=result['successful'] and result['script_input']['unchanged'] and result['argument_inputs_unchanged'];validate_result(result);json_new(case/'command-result.json',result,root=self.root)
        return result,case
