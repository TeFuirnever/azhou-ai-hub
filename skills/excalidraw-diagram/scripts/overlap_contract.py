#!/usr/bin/env python3
"""Closed, deterministic overlap records and replayable audit transitions."""
from __future__ import annotations
import hashlib,json,math,os,re,tempfile
from decimal import Decimal,ROUND_HALF_EVEN
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from excalidraw_lib import _elem_bounds
AUDIT_VERSION='excalidraw.overlap-audit.v1'; CHAIN_VERSION='excalidraw.overlap-chain-manifest.v1'; RECEIPT_VERSION='excalidraw.overlap-receipt.v1'
GATES_VERSION='excalidraw.overlap-gates.v1'; VISUAL_VERSION='excalidraw.overlap-visual-review.v1'; DISPOSITIONS_VERSION='excalidraw.overlap-dispositions.v1'
MAX_ROUNDS=4; MAX_ATTEMPTS=3; HEX64=re.compile(r'[0-9a-f]{64}\Z')
class ContractError(Exception):
 def __init__(self,code,message=''): self.code=code; super().__init__(code+(': '+message if message else ''))
def _finite(x):
 if isinstance(x,bool): return False
 try:return math.isfinite(float(x))
 except (TypeError,ValueError,OverflowError):return False
def canonical_bytes(v):
 def clean(x):
  if isinstance(x,float) and not math.isfinite(x):raise ContractError('E_NONFINITE')
  if isinstance(x,dict):
   if any(not isinstance(k,str) for k in x):raise ContractError('E_SCHEMA')
   return {k:clean(y) for k,y in x.items()}
  if isinstance(x,list):return [clean(y) for y in x]
  return x
 try:return json.dumps(clean(v),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 except (TypeError,ValueError,OverflowError) as e:raise ContractError('E_SCHEMA',str(e))
def digest(v):return hashlib.sha256(canonical_bytes(v)).hexdigest()
def _hex(x,code='E_SCHEMA'):
 if not isinstance(x,str) or not HEX64.fullmatch(x):raise ContractError(code)
def sidecar_for(path):
 p=Path(path)
 if p.name.endswith('.sha256'):raise ContractError('E_SIDECAR_NAME')
 if p.suffix != '.json':raise ContractError('E_SIDECAR_NAME')
 return Path(str(p)+'.sha256')
def read_sidecar(path):
 p=sidecar_for(path)
 if not p.exists():raise ContractError('E_SIDECAR_MISSING')
 try:t=p.read_bytes().decode('ascii')
 except UnicodeDecodeError:raise ContractError('E_SIDECAR_FORMAT')
 if not re.fullmatch(r'[0-9a-f]{64}\n',t):raise ContractError('E_SIDECAR_FORMAT')
 return t[:-1]
def verify_sidecar(path):
 p=Path(path)
 if p.name.endswith('.sha256'):raise ContractError('E_SIDECAR_NAME')
 if not p.exists():raise ContractError('E_IO')
 got=read_sidecar(p); want=hashlib.sha256(p.read_bytes()).hexdigest()
 if got!=want:raise ContractError('E_SIDECAR_MISMATCH')
 return want
def write_atomic(path,value,no_clobber=True):
 p=Path(path); sp=sidecar_for(p); data=canonical_bytes(value); side=(hashlib.sha256(data).hexdigest()+'\n').encode(); p.parent.mkdir(parents=True,exist_ok=True)
 if no_clobber and (p.exists() or sp.exists()):raise ContractError('E_SIDECAR_DUPLICATE' if sp.exists() else 'E_OUTPUT_EXISTS')
 tmp=[]; installed=[]
 try:
  for target,payload in ((p,data),(sp,side)):
   fd,n=tempfile.mkstemp(prefix='.'+target.name+'.',dir=str(target.parent));tmp.append(n)
   with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
  if no_clobber:
   if p.exists() or sp.exists():raise ContractError('E_SIDECAR_DUPLICATE')
   os.link(tmp[0],p);installed.append(p);os.link(tmp[1],sp);installed.append(sp)
  else:os.replace(tmp[0],p);installed.append(p);os.replace(tmp[1],sp);installed.append(sp)
  return hashlib.sha256(data).hexdigest()
 except FileExistsError:raise ContractError('E_SIDECAR_DUPLICATE')
 except ContractError:raise
 except OSError as e:raise ContractError('E_IO',str(e))
 finally:
  for n in tmp:
   try:os.unlink(n)
   except FileNotFoundError:pass
  if len(installed)==1:
   try:installed[0].unlink()
   except FileNotFoundError:pass
def _q(x):
 if not _finite(x):raise ContractError('E_NONFINITE')
 try:return int(Decimal(str(x)).quantize(Decimal('0.001'),rounding=ROUND_HALF_EVEN)*1000)
 except ArithmeticError:raise ContractError('E_NONFINITE')
def _bounds(e):
 if not isinstance(e,dict):raise ContractError('E_SCHEMA')
 try:
  for key in ('x','y','width','height'):
   if key not in e or not _finite(e[key]):raise ContractError('E_NONFINITE')
  x0,y0,x1,y1=_elem_bounds(e)
  if not all(_finite(value) for value in (x0,y0,x1,y1)):raise ContractError('E_NONFINITE')
  return _q(x0),_q(y0),_q(x1),_q(y1)
 except ContractError: raise
 except (KeyError,TypeError,ValueError,OverflowError): raise ContractError('E_SCHEMA')
def _id(e):
 x=e.get('id') if isinstance(e,dict) else None
 if not isinstance(x,str) or not x:raise ContractError('E_SCHEMA')
 return x
def _issue(code,ids,evidence,severity):
 if code=='TEXT_TEXT' and ids!=sorted(ids):raise ContractError('E_INVALID_ROLE')
 if not isinstance(ids,list) or len(ids)!=2 or len(set(ids))!=2 or any(not isinstance(x,str) or not x for x in ids):raise ContractError('E_INVALID_ROLE')
 if not isinstance(severity,int) or isinstance(severity,bool) or severity<0:raise ContractError('E_SCHEMA')
 return {'code':code,'subject_ids':ids,'severity':severity,'evidence':evidence,'issue_key':code+':'+':'.join(ids),'identity_digest':digest({'code':code,'subject_ids':ids}),'evidence_digest':digest(evidence)}
def detect_scene(scene,margin=3.0):
 if not isinstance(scene,dict) or not isinstance(scene.get('elements'),list) or not _finite(margin) or margin<0:raise ContractError('E_SCHEMA')
 es=scene['elements']; [_id(e) or _bounds(e) for e in es]
 for e in es:_bounds(e)
 rs=[e for e in es if e.get('type')=='rectangle']; ts=[e for e in es if e.get('type')=='text']; out=[]; tol=1000; inner=_q(margin)
 for i,a0 in enumerate(ts):
  a=_bounds(a0)
  for b0 in ts[i+1:]:
   b=_bounds(b0);ox=min(a[2],b[2])-max(a[0],b[0]);oy=min(a[3],b[3])-max(a[1],b[1])
   if ox>2000 and oy>2000:out.append(_issue('TEXT_TEXT',sorted([_id(a0),_id(b0)]),{'overlap_x':ox,'overlap_y':oy},max(0,min(ox-2000,oy-2000))))
 for c0 in rs:
  c=_bounds(c0)
  for p0 in rs:
   if c0 is p0:continue
   p=_bounds(p0);ix=min(c[2],p[2])-max(c[0],p[0]);iy=min(c[3],p[3])-max(c[1],p[1])
   semantic = {_id(c0), _id(p0)} == {'child','parent'}
   if ix>2000 and iy>2000 and (semantic or abs(c0.get('width',0)*c0.get('height',0))<abs(p0.get('width',0)*p0.get('height',0))):
    if semantic and _id(c0)=='parent': continue
    if c == p: continue
    l=max(0,p[0]-tol-c[0]);t=max(0,p[1]-tol-c[1]);r=max(0,c[2]-p[2]);b=max(0,c[3]-p[3]);inside=l+t+r+b;outside=max(0,min(ix-3000,iy-3000));out.append(_issue('NESTING',[_id(c0),_id(p0)],{'left':l,'top':t,'right':r,'bottom':b,'inside':inside,'outside':outside},min(inside,outside)))
 for r0 in rs:
  r=_bounds(r0)
  for e0 in es:
   if e0 is r0 or e0.get('type') in {'rectangle','arrow','line','freedraw'}:continue
   e=_bounds(e0);corners=[(e[0],e[1]),(e[2],e[1]),(e[2],e[3]),(e[0],e[3])];ins=[r[0]+inner<x<r[2]-inner and r[1]+inner<y<r[3]-inner for x,y in corners]
   if any(ins) and not all(ins):
    ix0,iy0,ix1,iy1=r[0]+inner,r[1]+inner,r[2]-inner,r[3]-inner
    dx=[ix0-e[0],ix1-e[2]];dy=[iy0-e[1],iy1-e[3]];dist=lambda q:0 if q[0]<=0<=q[1] else min(abs(q[0]),abs(q[1]));inside=dist(dx)+dist(dy);outside=min(max(0,e[2]-r[0]),max(0,r[2]-e[0]),max(0,e[3]-r[1]),max(0,r[3]-e[1]));out.append(_issue('STRADDLE',[_id(r0),_id(e0)],{'inside':inside,'outside':outside,'dx_inside':dx,'dy_inside':dy},min(inside,outside)))
 out.sort(key=lambda i:(i['code'],i['subject_ids']));return {'record_type':'detector','schema_version':AUDIT_VERSION,'state':'issues' if out else 'clean','scene_digest':digest(scene),'issues':out}
def value_map(r):return {i['issue_key']:1+int(i['severity']) for i in r.get('issues',[])}
def pareto(a,b):
 ks=sorted(set(value_map(a))|set(value_map(b)));x=[value_map(a).get(k,0) for k in ks];y=[value_map(b).get(k,0) for k in ks]
 if all(j<=i for i,j in zip(x,y)) and any(j<i for i,j in zip(x,y)):return 'improved'
 if all(j>=i for i,j in zip(x,y)) and any(j>i for i,j in zip(x,y)):return 'regressed'
 if x==y:return 'unchanged'
 return 'incomparable'
def _issue_validate(i):
 keys={'code','subject_ids','severity','evidence','issue_key','identity_digest','evidence_digest'}
 if not isinstance(i,dict) or set(i)!=keys:raise ContractError('E_SCHEMA')
 code,ids=i['code'],i['subject_ids'];exp={'TEXT_TEXT':{'overlap_x','overlap_y'},'NESTING':{'left','top','right','bottom','inside','outside'},'STRADDLE':{'inside','outside','dx_inside','dy_inside'}}.get(code)
 if exp is None or not isinstance(ids,list) or len(ids)!=2 or len(set(ids))!=2 or any(not isinstance(x,str) for x in ids) or code=='TEXT_TEXT' and ids!=sorted(ids):raise ContractError('E_INVALID_ROLE')
 if set(i['evidence'])!=exp:raise ContractError('E_SCHEMA')
 for k,v in i['evidence'].items():
  if k in {'dx_inside','dy_inside'}:
   if not isinstance(v,list) or len(v)!=2 or any(not isinstance(x,int) or isinstance(x,bool) for x in v):raise ContractError('E_SCHEMA')
  elif not isinstance(v,int) or isinstance(v,bool) or v<0:raise ContractError('E_SCHEMA')
 if not isinstance(i['severity'],int) or isinstance(i['severity'],bool) or i['severity']<0:raise ContractError('E_SCHEMA')
 if i['issue_key']!=code+':'+':'.join(ids) or i['identity_digest']!=digest({'code':code,'subject_ids':ids}) or i['evidence_digest']!=digest(i['evidence']):raise ContractError('E_DIGEST_MISMATCH')
def validate_record(o):
 if not isinstance(o,dict) or o.get('schema_version')!=AUDIT_VERSION:raise ContractError('E_SCHEMA')
 if o.get('record_type')=='detector':
  if set(o)!={'record_type','schema_version','state','scene_digest','issues'}:raise ContractError('E_SCHEMA')
  _hex(o['scene_digest']);
  if o['state'] not in {'clean','issues','error'} or not isinstance(o['issues'],list):raise ContractError('E_SCHEMA')
  seen=set()
  for i in o['issues']:_issue_validate(i); key=i['issue_key']; (key in seen) and (_ for _ in ()).throw(ContractError('E_INVALID_ROLE'));seen.add(key)
  if o['state'] in {'clean','error'} and o['issues']:raise ContractError('E_SCHEMA')
  if o['state']=='issues' and not o['issues']:raise ContractError('E_SCHEMA')
  return True
 if o.get('record_type')=='decision':
  req={'record_type','schema_version','round','attempt','edit_applied','scene_digest','detector_digest','previous_detector_digest','previous_decision_digest','decision','repair_allowed','progress_relation'}
  if set(o)!=req:raise ContractError('E_SCHEMA')
  if not isinstance(o['round'],int) or not 1<=o['round']<=4:raise ContractError('E_INVALID_ROUND')
  if not isinstance(o['attempt'],int) or not 0<=o['attempt']<=3:raise ContractError('E_INVALID_ATTEMPT')
  if not isinstance(o['edit_applied'],bool):raise ContractError('E_SCHEMA')
  _hex(o['scene_digest']);_hex(o['detector_digest'])
  for k in ('previous_detector_digest','previous_decision_digest'):
   if o[k] is not None:_hex(o[k])
  if o['decision'] not in {'error','clean','continue','stalled','exhausted'} or o['progress_relation'] not in {'not_compared','improved','regressed','unchanged','incomparable'}:raise ContractError('E_SCHEMA')
  if o['decision'] in {'error','clean','exhausted'} and (o['repair_allowed'] is not False or o['progress_relation']!='not_compared'):raise ContractError('E_SCHEMA')
  if o['decision']=='continue' and o['repair_allowed'] is not True:raise ContractError('E_SCHEMA')
  if o['decision']=='stalled' and o['repair_allowed'] is not False:raise ContractError('E_SCHEMA')
  return True
 raise ContractError('E_SCHEMA')
def decision(detector,round_no=1,attempt=0,edit_applied=False,scene_digest=None,previous_detector=None,previous_decision=None):
 if not isinstance(edit_applied,bool):raise ContractError('E_SCHEMA')
 if not isinstance(round_no,int) or not 1<=round_no<=4:raise ContractError('E_INVALID_ROUND')
 if not isinstance(attempt,int) or not 0<=attempt<=3:raise ContractError('E_INVALID_ATTEMPT')
 validate_record(detector)
 cur=detector['scene_digest']
 if scene_digest is not None and scene_digest!=cur:raise ContractError('E_INVALID_TRANSITION')
 if round_no==1:
  if attempt != 0: raise ContractError('E_INVALID_ATTEMPT')
  if edit_applied or previous_detector is not None or previous_decision is not None:raise ContractError('E_INVALID_ROUND')
  rel='not_compared'
 else:
  if not isinstance(previous_detector,dict) or not isinstance(previous_decision,dict):raise ContractError('E_INVALID_ROUND')
  validate_record(previous_detector);validate_record(previous_decision)
  if previous_decision.get('decision')!='continue' or previous_decision.get('repair_allowed') is not True:raise ContractError('E_INVALID_TRANSITION')
  if previous_decision.get('round')!=round_no-1:raise ContractError('E_INVALID_ROUND')
  if previous_decision.get('detector_digest')!=digest(previous_detector) or previous_decision.get('scene_digest')!=previous_detector['scene_digest']:raise ContractError('E_DIGEST_MISMATCH')
  if edit_applied:
   if attempt!=previous_decision['attempt']+1 or cur==previous_detector['scene_digest']:raise ContractError('E_INVALID_ATTEMPT')
  elif attempt!=previous_decision['attempt'] or cur!=previous_detector['scene_digest']:raise ContractError('E_INVALID_ATTEMPT')
  rel=pareto(previous_detector,detector)
 state=detector['state']
 if state=='error':dec,allow,rel='error',False,'not_compared'
 elif state=='clean':dec,allow,rel='clean',False,'not_compared'
 elif attempt>=3:dec,allow,rel='exhausted',False,'not_compared'
 elif round_no>1 and rel!='improved':dec,allow='stalled',False
 else:dec,allow='continue',True
 return {'record_type':'decision','schema_version':AUDIT_VERSION,'round':round_no,'attempt':attempt,'edit_applied':edit_applied,'scene_digest':cur,'detector_digest':digest(detector),'previous_detector_digest':digest(previous_detector) if previous_detector else None,'previous_decision_digest':digest(previous_decision) if previous_decision else None,'decision':dec,'repair_allowed':allow,'progress_relation':rel}
def _holds(value):
 if not isinstance(value,list) or any(not isinstance(item,str) for item in value):raise ContractError('E_SCHEMA')
 return value
def _aux(kind,o):
 ver={'gates':GATES_VERSION,'visual_review':VISUAL_VERSION,'dispositions':DISPOSITIONS_VERSION,'chain_manifest':CHAIN_VERSION}[kind]
 if not isinstance(o,dict) or o.get('schema_version')!=ver:raise ContractError('E_SCHEMA')
 if kind=='gates':
  if set(o)!={'record_type','schema_version','gates','holds'} or o.get('record_type')!='gates' or not isinstance(o.get('gates'),list):raise ContractError('E_SCHEMA')
  _holds(o['holds'])
  for g in o['gates']:
   if set(g)!={'name','status','applicable'} or not isinstance(g['name'],str) or g['status'] not in {'PASS','FAIL','NOT_RUN'} or not isinstance(g['applicable'],bool):raise ContractError('E_SCHEMA')
 elif kind=='visual_review':
  if set(o)!={'record_type','schema_version','status','reviewer'} or o.get('record_type')!='visual_review' or o.get('status') not in {'pass','fail','not_run'} or not isinstance(o.get('reviewer'),str) or not o['reviewer']:raise ContractError('E_SCHEMA')
 elif kind=='dispositions':
  if set(o)!={'record_type','schema_version','dispositions'} or o.get('record_type')!='dispositions' or not isinstance(o.get('dispositions'),list):raise ContractError('E_SCHEMA')
  for d in o['dispositions']:
   if set(d)!={'issue_key','impact','name','reason','evidence'} or d['impact'] not in {'non_blocking','blocking'} or any(not isinstance(d[k],str) or not d[k] for k in ('issue_key','name','reason','evidence')):raise ContractError('E_SCHEMA')
 else:
  if set(o)!={'record_type','schema_version','rounds','holds'} or o.get('record_type')!='chain_manifest' or not isinstance(o.get('rounds'),list) or not 1<=len(o['rounds'])<=4:raise ContractError('E_SCHEMA')
  _holds(o['holds'])
  for n,r in enumerate(o['rounds'],1):
   allowed={'round','detector_path','decision_path','detector_sidecar','decision_sidecar'}
   if set(r)!=allowed or r['round']!=n:raise ContractError('E_INVALID_ROUND')
   if not all(isinstance(r[k],str) for k in ('detector_path','decision_path','detector_sidecar','decision_sidecar')):raise ContractError('E_SCHEMA')
   if not r['detector_path'].endswith('.json') or not r['decision_path'].endswith('.json') or not r['detector_sidecar'].endswith('.json.sha256') or not r['decision_sidecar'].endswith('.json.sha256'):raise ContractError('E_SIDECAR_NAME')
  paths=[(r['detector_path'],r['decision_path']) for r in o['rounds']]
  flat=[x for pair in paths for x in pair]
  if len(set(flat))!=len(flat):raise ContractError('E_INVALID_ROUND')
 return True
def seal(kind,record):
 _aux(kind,record)
 if kind=='chain_manifest':
  for r in record['rounds']:
   for p in (r['detector_path'],r['decision_path']):verify_sidecar(p)
   if r['detector_sidecar']!=str(sidecar_for(r['detector_path'])) or r['decision_sidecar']!=str(sidecar_for(r['decision_path'])):raise ContractError('E_SIDECAR_NAME')
 return record
def replay_chain(chain):
 if not isinstance(chain,list) or not 1<=len(chain)<=4:raise ContractError('E_INVALID_ROUND')
 pd=px=None
 for n,item in enumerate(chain,1):
  if set(item)!={'round','detector','decision'} or item['round']!=n:raise ContractError('E_INVALID_ROUND')
  if set(item['detector'])!={'projection','digest'} or set(item['decision'])!={'projection','digest'}:raise ContractError('E_SCHEMA')
  d,x=item['detector']['projection'],item['decision']['projection'];validate_record(d);validate_record(x)
  if item['detector']['digest']!=digest(d) or item['decision']['digest']!=digest(x):raise ContractError('E_DIGEST_MISMATCH')
  if x!=decision(d,n,x['attempt'],x['edit_applied'],x['scene_digest'],pd,px):raise ContractError('E_INVALID_TRANSITION')
  if n<len(chain) and x['decision']!='continue':raise ContractError('E_INVALID_TRANSITION')
  pd,px=d,x
 return pd,px
def map_status(det,dec,gates,visual,dispositions,holds=None):
 holds=[] if holds is None else holds
 if any(g.get('applicable',True) and g.get('status')!='PASS' for g in gates.get('gates',[])) or visual.get('status')!='pass':return 'failed',None
 ds=dispositions.get('dispositions',[])
 if dec['decision']=='clean' and det['state']=='clean' and not holds and not ds:return 'complete',None
 keys=[i['issue_key'] for i in det.get('issues',[])]
 if dec['decision']=='stalled' and det['state']=='issues' and not holds and len(ds)==len(keys) and sorted(d.get('issue_key') for d in ds)==sorted(keys) and len({d['issue_key'] for d in ds})==len(ds) and all(d.get('impact')=='non_blocking' for d in ds):return 'complete_with_holds',None
 return 'failed','nonterminal_chain_closed_as_failed' if dec['decision']=='continue' else None
def main():
 import argparse,sys
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True);s=sp.add_parser('seal');s.add_argument('--kind',required=True);s.add_argument('--record',required=True);s.add_argument('--output',required=True);a=ap.parse_args()
 try:
  o=json.loads(Path(a.record).read_text());verify_sidecar(a.record);seal(a.kind,o);write_atomic(a.output,o);return 0
 except ContractError as e:print(str(e),file=sys.stderr);return 2
 except (OSError,ValueError,TypeError,KeyError) as e:print('E_IO: '+str(e),file=sys.stderr);return 3
if __name__=='__main__':import sys;sys.exit(main())
