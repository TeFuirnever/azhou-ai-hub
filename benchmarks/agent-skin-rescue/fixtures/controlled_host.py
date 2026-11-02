"""Bounded synthetic child; never loads an App, profile, or credential."""
import json,os,sys,time,signal
from pathlib import Path
case=Path(os.environ['CHAIN_CASE']);mode=os.environ['CHAIN_MODE'];nonce=os.environ['CHAIN_NONCE']
def new(name,value):
 fd=os.open(case/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:os.write(fd,json.dumps(value).encode());os.fsync(fd)
 finally:os.close(fd)
os.write(1,b'controlled stdout\x00\xff\r\n');os.write(2,b'controlled stderr\xfe\r\n')
if mode=='artifacts':
 out=Path(sys.argv[sys.argv.index('--out')+1]);out.mkdir(mode=0o700)
 fd=os.open(out/'payload.bin',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:os.write(fd,b'produced\x00\xff\r\n');os.fsync(fd)
 finally:os.close(fd)
if mode=='failure':raise SystemExit(37)
if mode in ('hold','partial','ignore-term'):
 if mode=='ignore-term':signal.signal(signal.SIGTERM,signal.SIG_IGN)
 if mode=='partial':
  fd=os.open(case/'partial.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,b'{"partial":');os.close(fd)
 new('ready.json',{'pid':os.getpid(),'nonce':nonce,'scope':'synthetic-child'})
 end=time.monotonic()+(.4 if mode=='ignore-term' else 3)
 while time.monotonic()<end:
  if mode!='ignore-term' and (case/'release.json').is_file():break
  time.sleep(.01)
 if mode=='partial':raise SystemExit(23)
new('observation.json',{'scope':'synthetic-child','pid':os.getpid(),'nonce':nonce,'env':{k:os.environ.get(k) for k in ['HOME','TMPDIR','ZCODE_DATA_BASE_DIR','ZCODE_DESKTOP_USER_DATA_DIR','ZCODE_DESKTOP_SESSION_DATA_DIR']},'app_logs':os.environ.get('CHAIN_APP_LOGS')})
