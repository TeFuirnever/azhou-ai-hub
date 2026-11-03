#!/usr/bin/env python3
"""Exercise canonical fixed-target CDP against an owned loopback fixture only."""
from pathlib import Path
import argparse,platform,socketserver,socket,threading,json,hashlib,base64,struct,subprocess,datetime,os,time
ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--profile-directory',type=Path);args=parser.parse_args()
 out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
 profiles=args.profile_directory.resolve() if args.profile_directory else out
 profiles.mkdir(parents=True,exist_ok=True)
 base=ROOT/'Native';canonical=[base/n for n in ['App.swift','Wallpaper.swift','SkinHostContract.swift','CodexSkinDriver.swift','ZCodeSkinDriver.swift','ZCodeSkinRuntime.swift']]
 snapshots={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in canonical}
 test=base/'ZCodeTransportTests.swift'
 argv=['/usr/bin/swiftc','-DAGENT_SKIN_NATIVE_EVENT_TESTS','-target',platform.machine()+'-apple-macos13.0','-profile-generate','-profile-coverage-mapping','-module-cache-path',str(out/'module-cache'),*(str(p) for p in canonical),str(test),'-o',str(out/'transport-fixture'),'-framework','AppKit','-framework','WebKit']
 r=subprocess.run(argv,capture_output=True,timeout=90);(out/'compile.stdout').write_bytes(r.stdout);(out/'compile.stderr').write_bytes(r.stderr)
 if r.returncode:raise RuntimeError('canonical transport fixture compilation failed: '+r.stderr.decode())
 log=[];mode='normal'
 def exact(c,n):
  b=b''
  while len(b)<n:
   z=c.recv(n-len(b))
   if not z:raise EOFError
   b+=z
  return b
 def recvframe(c):
  h=exact(c,2);n=h[1]&127
  if n==126:n=struct.unpack('!H',exact(c,2))[0]
  if n==127:n=struct.unpack('!Q',exact(c,8))[0]
  assert n<1048576
  mask=exact(c,4) if h[1]&128 else None;b=exact(c,n)
  if mask:b=bytes(x^mask[i%4] for i,x in enumerate(b))
  return h[0]&15,b
 def send(c,o):
  b=json.dumps(o).encode();h=bytes([129,len(b)]) if len(b)<126 else bytes([129,126])+struct.pack('!H',len(b));c.sendall(h+b)
 class Handler(socketserver.BaseRequestHandler):
  def handle(self):
   case=case_state;mode=case['mode']
   c=self.request;c.settimeout(6);data=b''
   try:
    while b'\r\n\r\n' not in data:
     z=c.recv(4096)
     if not z:return
     data+=z
     assert len(data)<65536
    line=data.split(b'\r\n')[0].decode();path=line.split()[1];log.append({'path':path,'mode':mode})
    if path=='/blackhole' or (mode in ['send-timeout','send-cancel'] and path!='/json/list'):
     while c.recv(4096):pass
     return
    if path=='/json/list':
     if mode=='slow-http': time.sleep(0.60)
     url='file:///fixture/index.html?windowKind=main'
     good={'id':'TARGET1','type':'page','url':url,'webSocketDebuggerUrl':f'ws://127.0.0.1:{self.server.server_address[1]}/devtools/page/TARGET1'}
     if case['started'] is None: case['started']=time.monotonic()
     elapsed=time.monotonic()-case['started']
     if mode in ('empty','timeout','cancel','hot-empty') and (mode not in ('empty',) or elapsed<0.35): pages=[]
     elif mode=='blank' and elapsed<0.35: pages=[{'id':'BLANK','type':'page','url':'about:blank'}]
     elif mode=='login': pages=[{'id':'LOGIN','type':'page','url':'file:///fixture/login.html'}]
     elif mode=='external': pages=[{'id':'OTHER','type':'page','url':'file:///other/index.html'}]
     elif mode=='ambiguous': pages=[good,dict(good,id='TARGET2')]
     else: pages=[good]
     log.append({'discovery_mode':mode,'elapsed':elapsed,'count':len(pages)})
     body=json.dumps(pages).encode();c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body);return
    headers=dict(x.split(b':',1) for x in data.split(b'\r\n')[1:] if b':' in x);key=next(v.strip() for k,v in headers.items() if k.lower()==b'sec-websocket-key');accept=base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest());c.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
    changed=False
    while True:
     opcode,b=recvframe(c)
     if opcode==8:return
     if opcode==9:c.sendall(bytes([138,len(b)])+b);continue
     if path=='/quiet' or mode in ['receive-timeout','receive-cancel']:continue
     m=json.loads(b);method=m['method'];log.append({'method':method,'mode':mode,'uniqueContextId':m.get('params',{}).get('uniqueContextId')})
     if method=='Runtime.enable':send(c,{'method':'Runtime.executionContextCreated','params':{'context':{'id':1,'uniqueId':'context-1','auxData':{'isDefault':True,'frameId':'FRAME1'}}}})
     if method=='Page.getFrameTree':result={'frameTree':{'frame':{'id':'FRAME1','url':'file:///fixture/index.html?windowKind=main'+('&locale=drift' if changed and mode=='url-drift' else '')}}}
     elif method in ('Runtime.evaluate','Runtime.callFunctionOn'):
      changed=True
      if mode=='context-drift':send(c,{'method':'Runtime.executionContextsCleared','params':{}})
      result={'result':{'value':{'fixture':True,'installed':True}}}
     else:result={}
     send(c,{'id':m['id'],'result':result})
   except (EOFError,ConnectionError,socket.timeout):pass
   except Exception as e:log.append({'fixture_error':type(e).__name__})
 class Server(socketserver.ThreadingTCPServer):allow_reuse_address=True;daemon_threads=True
 server=Server(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();records=[]
 try:
  for m in ['send-timeout','receive-timeout','send-cancel','receive-cancel','normal','context-drift','url-drift','empty','blank','login','external','ambiguous','timeout','slow-http','cancel','hot-empty','guard-error-late','guard-return-late','guard-cancel-late']:
   mode=m;case_state={'mode':m,'started':None};start=datetime.datetime.now(datetime.timezone.utc).isoformat();r=subprocess.run([str(out/'transport-fixture'),m,str(server.server_address[1])],capture_output=True,timeout=10,env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','LLVM_PROFILE_FILE':str(profiles/('zcode-transport-'+m+'-%p.profraw'))})
   (out/(m+'.stdout')).write_bytes(r.stdout);(out/(m+'.stderr')).write_bytes(r.stderr)
   row={'case':m,'started_at':start,'native_exit':r.returncode,'stdout':r.stdout.decode(),'stderr':r.stderr.decode()};records.append(row)
   if r.returncode:break
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in snapshots.items()),'canonical source changed while compiling/running'
 (out/'mock-protocol.json').write_text(json.dumps(log,indent=2)+'\n')
 report={'canonical_source_sha256':snapshots,'source_bytes_unchanged_after':True,'canonical_compiled_complete':True,'sourceLocation_used':False,'compile_exit':0,'cases':records,'host_executed':False,'real_OS_queries':False,'passed':len(records)==19 and all(x['native_exit']==0 for x in records)}
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));return 0 if report['passed'] else 1

if __name__=='__main__':
 raise SystemExit(main())
