#!/usr/bin/env python3
"""Synthetic ZCode runtime fixture; no host App/profile access; own test-PID listener metadata only.

C0 owns integration. --binary launches only the supplied canonical test binary
with --zcode-runtime-fixture PORT. REST POST /fixture/mode {mode,reset:true}.
"""
from pathlib import Path
import platform,argparse,base64,datetime,hashlib,json,os,socket,socketserver,struct,subprocess,threading,time,uuid
PAGE='file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html?windowKind=main'
MODES={'ready','complete','before-ready','already-active','badreceipt','absent','late','readylost','dispose-failed'}
class Fixture:
 def __init__(self):self.lock=threading.Lock();self.log=[];self.captured={};self.capture_metadata=None;self.frame_entered=threading.Event();self.frame_release=threading.Event();self.frame_gated=False;self.interleave_enabled=False;self.reset('ready')
 def reset(self,mode):
  if mode not in MODES:raise ValueError('unknown fixture mode')
  self.mode=mode;self.metadata=None;self.present=False;self.status_reads=0;self.disposed=False
 def control(self,value):
  with self.lock:
   mode=value.get('mode','ready');preserve=value.get('reset',True) is False
   if preserve:
    if mode not in MODES:raise ValueError('unknown fixture mode')
    self.mode=mode
   else:self.reset(mode)
   self.log.append({'control_mode':mode,'reset':not preserve})
   return {'mode':self.mode,'synthetic':True}
 def rpc(self,message):
  with self.lock:
   method=message['method'];params=message.get('params',{});self.log.append({'method':method,'mode':self.mode,'uniqueContextId':params.get('uniqueContextId')})
   if method=='Page.getFrameTree':return {'frameTree':{'frame':{'id':'FRAME1','url':PAGE}}}
   if method in ['Runtime.enable','Page.enable']:return {}
   if method=='Runtime.callFunctionOn':
    if params.get('uniqueContextId')!='context-1':return {'_error':'fixture-context-mismatch'}
    metadata=params.get('arguments',[{}])[0].get('value')
    fields={'controllerInstanceID','createdByOperationID','payloadSHA256','documentToken'}
    if not isinstance(metadata,dict) or set(metadata)!=fields or metadata.get('documentToken')!='context-1':return {'_error':'fixture-metadata-invalid'}
    if self.mode=='already-active':
     # Existing instance IDs and operation IDs deliberately differ from this send.
     if self.metadata is None:self.metadata={**metadata,'controllerInstanceID':str(uuid.uuid4()),'createdByOperationID':str(uuid.uuid4())}
    else:self.metadata=dict(metadata)
    self.present=self.mode!='absent';self.status_reads=0;self.disposed=False
    return {'result':{'value':{'installed':True,'alreadyActive':self.mode=='already-active'}}}
   if method=='Runtime.evaluate':
    if params.get('uniqueContextId')!='context-1':return {'_error':'fixture-context-mismatch'}
    expression=params.get('expression','')
    # Capture only exact Runtime.evaluate strings from this owned synthetic
    # ready controller; never factory bytes or any App/user data.
    name='disposeExpression' if 'dispose.call(c)' in expression else 'safeStatusExpression' if 'status.call(c)' in expression else None
    if self.mode=='ready' and name and isinstance(expression,str) and self.present and self.metadata:
     if self.capture_metadata is None and name=='safeStatusExpression':self.capture_metadata=dict(self.metadata)
     if self.capture_metadata==self.metadata and name not in self.captured:self.captured[name]=expression
    # This is a protocol fixture, not a JS interpreter. It discriminates the
    # canonical fixed dispose expression from canonical fixed safeStatus.
    if 'dispose.call(c)' in expression:
     if self.mode=='dispose-failed':return {'result':{'value':{'disposed':False}}}
     absent=not self.present;self.present=False;self.disposed=True
     return {'result':{'value':{'disposed':True,'alreadyAbsent':absent}}}
    if self.mode=='readylost' and self.status_reads>=1:return {'_close':True}
    self.status_reads+=1
    if self.mode=='absent' or not self.present:return {'result':{'value':{'present':False}}}
    if self.metadata is None:return {'result':{'value':{'present':True,'unconfirmed':True}}}
    snapshot=dict(self.metadata)
    if self.mode=='badreceipt':snapshot['controllerInstanceID']=str(uuid.uuid4())
    ready=self.mode in {'ready','already-active','dispose-failed'}
    complete=self.mode in {'complete','before-ready'}
    status={'present':True,'owner':'azhou-zcode-startup','version':1,**snapshot,'ready':ready,'completed':complete,'runId':1,
     'phase':'complete' if complete else 'playing','completion':{'skipped':complete,'beforeReady':self.mode=='before-ready'}}
    return {'result':{'value':status}}
   return {'_error':'unsupported-fixture-method'}

def exact(c,n):
 result=b''
 while len(result)<n:
  part=c.recv(n-len(result))
  if not part:raise EOFError
  result+=part
 return result

def receive(c):
 head=exact(c,2);size=head[1]&127
 if size==126:size=struct.unpack('!H',exact(c,2))[0]
 if size==127:size=struct.unpack('!Q',exact(c,8))[0]
 if size>64*1024*1024:raise ValueError('fixture-frame-too-large')
 mask=exact(c,4) if head[1]&128 else None;data=exact(c,size)
 if mask:data=bytes(x^mask[i%4] for i,x in enumerate(data))
 return head[0]&15,data

def send(c,value):
 data=json.dumps(value).encode();n=len(data)
 head=bytes([129,n]) if n<126 else bytes([129,126])+struct.pack('!H',n) if n<65536 else bytes([129,127])+struct.pack('!Q',n)
 c.sendall(head+data)

class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  c=self.request;c.settimeout(10)
  try:
   header=b''
   while b'\r\n\r\n' not in header:
    part=c.recv(4096)
    if not part:return
    header+=part
    if len(header)>65536:raise ValueError('fixture-http-too-large')
   header,body=header.split(b'\r\n\r\n',1);lines=header.split(b'\r\n');method,path,_=lines[0].decode().split();headers={k.lower():v.strip() for k,v in (l.split(b':',1) for l in lines[1:] if b':' in l)}
   if path.startswith('/fixture/'):
    if path=='/fixture/mode' and method=='POST':
     length=int(headers.get(b'content-length',b'0'))
     if length>4096:raise ValueError('fixture-control-too-large')
     if len(body)<length:body+=exact(c,length-len(body))
     result=self.server.fixture.control(json.loads(body[:length]))
    elif path=='/fixture/frame-entered' and method=='GET':result={'entered':self.server.fixture.frame_entered.is_set()}
    elif path=='/fixture/release-frame' and method=='POST':self.server.fixture.frame_release.set();result={'released':True}
    elif path=='/fixture/state' and method=='GET':
     f=self.server.fixture
     with f.lock:result={'mode':f.mode,'present':f.present,'status_reads':f.status_reads,'disposed':f.disposed,'metadata':f.metadata,'synthetic':True}
    else:raise ValueError('unknown fixture control')
    self.http(c,result);return
   if path=='/json/list':
    self.http(c,[{'id':'TARGET1','type':'page','url':PAGE,'webSocketDebuggerUrl':f'ws://127.0.0.1:{self.server.server_address[1]}/devtools/page/TARGET1'}]);return
   if path!='/devtools/page/TARGET1':raise ValueError('unknown fixture target')
   key=headers[b'sec-websocket-key'];accept=base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest());c.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
   while True:
    opcode,data=receive(c)
    if opcode==8:return
    if opcode==9:c.sendall(bytes([138,len(data)])+data);continue
    request=json.loads(data)
    if self.server.fixture.interleave_enabled and request['method']=='Page.getFrameTree':
     with self.server.fixture.lock:
      first=not self.server.fixture.frame_gated
      if first:self.server.fixture.frame_gated=True
     if first:
      self.server.fixture.frame_entered.set()
      if not self.server.fixture.frame_release.wait(8):raise TimeoutError('gate-not-released')
    if request['method']=='Runtime.enable':send(c,{'method':'Runtime.executionContextCreated','params':{'context':{'id':1,'uniqueId':'context-1','auxData':{'isDefault':True,'frameId':'FRAME1'}}}})
    result=self.server.fixture.rpc(request)
    if result.get('_close'):return
    if '_error' in result:send(c,{'id':request['id'],'error':{'code':-32000,'message':result['_error']}})
    else:send(c,{'id':request['id'],'result':result})
  except (EOFError,ConnectionError,socket.timeout):pass
  except Exception as error:
   with self.server.fixture.lock:self.server.fixture.log.append({'fixture_error':type(error).__name__})
 @staticmethod
 def http(c,value):
  body=json.dumps(value).encode();c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True;daemon_threads=True
 def __init__(self):self.fixture=Fixture();super().__init__(('127.0.0.1',0),Handler)

def selftest():
 f=Fixture();metadata={'controllerInstanceID':str(uuid.uuid4()),'createdByOperationID':str(uuid.uuid4()),'payloadSHA256':'a'*64,'documentToken':'context-1'}
 install={'method':'Runtime.callFunctionOn','params':{'uniqueContextId':'context-1','arguments':[{'value':metadata}]}}
 status={'method':'Runtime.evaluate','params':{'uniqueContextId':'context-1','expression':'safe-status'}};dispose={'method':'Runtime.evaluate','params':{'uniqueContextId':'context-1','expression':'dispose.call(c)'}}
 count=0
 for mode in sorted(MODES):
  f.control({'mode':mode});r=f.rpc(install)['result']['value'];assert r['installed'];s=f.rpc(status)
  if mode=='absent':assert s['result']['value']['present'] is False
  else:
   value=s['result']['value'];assert value['payloadSHA256']==metadata['payloadSHA256'] and value['documentToken']=='context-1'
   if mode=='already-active':assert value['controllerInstanceID']!=metadata['controllerInstanceID'] and value['createdByOperationID']!=metadata['createdByOperationID'] and r['alreadyActive']
   elif mode=='badreceipt':assert value['controllerInstanceID']!=metadata['controllerInstanceID']
   else:assert all(value[k]==v for k,v in metadata.items())
   if mode=='readylost':assert f.rpc(status)=={'_close':True}
  d=f.rpc(dispose)['result']['value'];assert d['disposed']==(mode!='dispose-failed');count+=1
 print(json.dumps({'server_only_synthetic_modes':count,'passed':True,'native_runtime_not_tested':True,'host':False}))

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path);parser.add_argument('--build-canonical',action='store_true');parser.add_argument('--out',type=Path);parser.add_argument('--profile-directory',type=Path);parser.add_argument('--timeout',type=float,default=90);parser.add_argument('--self-test',action='store_true');parser.add_argument('--interleave-test',action='store_true');args=parser.parse_args()
 if args.self_test:selftest();return 0
 if not args.out or (bool(args.binary)==bool(args.build_canonical)):parser.error('--out and exactly one of --binary/--build-canonical are required')
 out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
 native=Path(__file__).resolve().parents[1]/'Native';names=['App.swift','Wallpaper.swift','SkinHostContract.swift','CodexSkinDriver.swift','ZCodeSkinDriver.swift','ZCodeSkinRuntime.swift','StartupNativeTests.swift']
 source_sha={str(native/name):hashlib.sha256((native/name).read_bytes()).hexdigest() for name in names} if args.build_canonical else None
 compile_receipt=None
 if args.build_canonical:
  binary=out/'bin/CanonicalStartupTests';binary.parent.mkdir(mode=0o700)
  argv=['/usr/bin/swiftc','-DAGENT_SKIN_NATIVE_EVENT_TESTS','-target',platform.machine()+'-apple-macos13.0','-module-cache-path',str(out/'module-cache'),*(str(native/name)for name in names),'-o',str(binary),'-framework','AppKit','-framework','WebKit']
  if args.profile_directory:argv[1:1]=['-profile-generate','-profile-coverage-mapping']
  started=datetime.datetime.now(datetime.timezone.utc).isoformat();compiled=subprocess.run(argv,capture_output=True,timeout=120)
  (out/'compile.stdout').write_bytes(compiled.stdout);(out/'compile.stderr').write_bytes(compiled.stderr)
  compile_receipt={'argv':argv,'started_at':started,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'native_exit':compiled.returncode,'canonical_source_sha256':source_sha,'binary_output':str(binary),'not_shared_build_output':True}
  (out/'COMPILE-C.json').write_text(json.dumps(compile_receipt,indent=2)+'\n')
  if compiled.returncode:print(json.dumps(compile_receipt));return 1
  args.binary=binary
 server=Server();server.fixture.interleave_enabled=args.interleave_test;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin'}
 if args.profile_directory:args.profile_directory.mkdir(parents=True,exist_ok=True);env['LLVM_PROFILE_FILE']=str(args.profile_directory.resolve()/'zcode-runtime-fixture-%p.profraw')
 native_flag='--zcode-driver-interleave' if args.interleave_test else '--zcode-runtime-fixture'
 start=datetime.datetime.now(datetime.timezone.utc).isoformat();timed_out=False
 try:
  try:r=subprocess.run([str(args.binary.resolve()),native_flag,str(server.server_address[1])],capture_output=True,timeout=args.timeout,env=env);code=r.returncode;stdout=r.stdout;stderr=r.stderr
  except subprocess.TimeoutExpired as e:timed_out=True;code=None;stdout=e.stdout or b'';stderr=e.stderr or b''
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
 (out/'stdout.bin').write_bytes(stdout);(out/'stderr.bin').write_bytes(stderr);(out/'mock-protocol.json').write_text(json.dumps(server.fixture.log,indent=2)+'\n')
 methods={r.get('method') for r in server.fixture.log};exercised={'Runtime.callFunctionOn','Runtime.evaluate'}<=methods
 captures=server.fixture.captured;metadata=server.fixture.capture_metadata;capture_complete=set(captures)=={'safeStatusExpression','disposeExpression'}
 expression_sha={}
 if capture_complete:
  d=out/'expressions';d.mkdir(mode=0o700)
  for name,expression in captures.items():
   data=expression.encode('utf-8');p=d/('Native-ZCodeRuntime.'+name+'.js');p.open('xb').write(data);expression_sha[name]=hashlib.sha256(data).hexdigest()
  unchanged=source_sha is not None and all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in source_sha.items())
  binding={'schema':'native-runtime-captured-expressions.v1','owner':'azhou-zcode-startup','version':1,'metadata':metadata,'sourceSHAs':expression_sha,
   'captured_from':{'mode':'ready','same_instance_pair':True,'metadataSHA256':hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest(),'transport':'actual Runtime.evaluate request params.expression bytes'},
   'canonical_source_sha256':source_sha,'canonical_source_bytes_unchanged_after':unchanged,'compile_receipt':compile_receipt,'binary_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest(),
   'native_fixture_exit':code,'native_fixture_timed_out':timed_out,'host':False,'factory_captured':False,'App_user_data_captured':False}
  (out/'EXPRESSION-BINDINGS.json').open('x').write(json.dumps(binding,indent=2)+'\n')
 interleave_asserted=False
 if args.interleave_test:
  try:
   value=json.loads(stdout)
   interleave_asserted=value=={'variant':'safe','inspectBusy':True,'launchReady':True,'lockReacquired':True,'realHost':False}
  except (ValueError,TypeError):pass
 result={'argv':[str(args.binary.resolve()),native_flag,'<owned-port>'],'started_at':start,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'native_exit':code,'timed_out':timed_out,'runtime_protocol_exercised':exercised,'server_closed':True,'host_executed':False,'real_OS_queries':not args.interleave_test,'OS_query_scope':('injected fake listener; actual synthetic temp file lock' if args.interleave_test else 'native test binary self-PID listener metadata only'),'expression_count':len(captures),'same_ready_instance_pair':capture_complete,'expression_sha256':expression_sha,'interleave_asserted':interleave_asserted,'passed':(code==0 and not timed_out and interleave_asserted) if args.interleave_test else (code==0 and exercised and capture_complete)}
 (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
