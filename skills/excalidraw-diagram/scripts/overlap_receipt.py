#!/usr/bin/env python3
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import overlap_contract as c
def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def _projection(z):
 if not isinstance(z,dict) or set(z)!={'projection','digest'} or z['digest']!=c.digest(z['projection']):raise c.ContractError('E_DIGEST_MISMATCH')
 return z['projection']
def validate_machine(path):
 rec=load(path);c.verify_sidecar(path)
 req={'record_type','schema_version','status','audit_chain','final_detector_digest','final_decision_digest','gates','visual_review','dispositions','holds','mapping_reason'}
 if set(rec)!=req or rec['record_type']!='receipt' or rec['schema_version']!=c.RECEIPT_VERSION or rec['status'] not in {'complete','complete_with_holds','failed'}:raise c.ContractError('E_SCHEMA')
 c._holds(rec['holds'])
 d,x=c.replay_chain(rec['audit_chain'])
 if rec['final_detector_digest']!=c.digest(d) or rec['final_decision_digest']!=c.digest(x):raise c.ContractError('E_INVALID_TRANSITION')
 gates,visual,disp=_projection(rec['gates']),_projection(rec['visual_review']),_projection(rec['dispositions'])
 c._aux('gates',gates);c._aux('visual_review',visual);c._aux('dispositions',disp)
 status,reason=c.map_status(d,x,gates,visual,disp,rec['holds'])
 if rec['status']!=status or rec['mapping_reason']!=reason:raise c.ContractError('E_INVALID_MAPPING')
 return rec
def _machine_entry(path):
 p=Path(path);return p,c.verify_sidecar(p)
def build(a):
 man=load(a.chain_manifest);c.verify_sidecar(a.chain_manifest);c.seal('chain_manifest',man);chain=[]
 for row in man['rounds']:
  dp,xp=Path(row['detector_path']),Path(row['decision_path']);c.verify_sidecar(dp);c.verify_sidecar(xp);d,x=load(dp),load(xp);c.validate_record(d);c.validate_record(x)
  chain.append({'round':row['round'],'detector':{'projection':d,'digest':c.digest(d)},'decision':{'projection':x,'digest':c.digest(x)}})
 d,x=c.replay_chain(chain)
 gates,visual,disp=load(a.gates),load(a.visual_review),load(a.dispositions)
 for p in (a.gates,a.visual_review,a.dispositions):c.verify_sidecar(p)
 c._aux('gates',gates);c._aux('visual_review',visual);c._aux('dispositions',disp)
 status,reason=c.map_status(d,x,gates,visual,disp,man.get('holds',[]))
 wrap=lambda z:{'projection':z,'digest':c.digest(z)}
 rec={'record_type':'receipt','schema_version':c.RECEIPT_VERSION,'status':status,'audit_chain':chain,'final_detector_digest':c.digest(d),'final_decision_digest':c.digest(x),'gates':wrap(gates),'visual_review':wrap(visual),'dispositions':wrap(disp),'holds':man.get('holds',[]),'mapping_reason':reason}
 c.write_atomic(a.output,rec);return 0
def markdown(a):
 rec=validate_machine(a.receipt);text=Path(a.markdown).read_text(encoding='utf-8')
 if text.count('excalidraw-diagram.receipt.v1')!=1:raise c.ContractError('E_MARKER')
 def one(label):
  vals=re.findall(r'^'+re.escape(label)+r': (.+)$',text,re.M)
  if len(vals)!=1:raise c.ContractError('E_MARKDOWN_MISMATCH')
  return vals[0].strip()
 cited=Path(one('Machine receipt'));sha=one('Machine sidecar SHA');status=one('Machine status')
 resolved_cited = cited if cited.is_absolute() else Path(a.markdown).parent / cited
 if resolved_cited.resolve()!=Path(a.receipt).resolve() or sha!=c.verify_sidecar(a.receipt) or status!=rec['status']:raise c.ContractError('E_MARKDOWN_MISMATCH')
 return 0
def main():
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True);b=sp.add_parser('build');b.add_argument('--chain-manifest',required=True);b.add_argument('--gates',required=True);b.add_argument('--visual-review',required=True);b.add_argument('--dispositions',required=True);b.add_argument('--output',required=True);v=sp.add_parser('validate');v.add_argument('--receipt',required=True);m=sp.add_parser('validate-markdown');m.add_argument('--markdown',required=True);m.add_argument('--receipt',required=True);a=ap.parse_args()
 try:
  if a.cmd=='build':return build(a)
  if a.cmd=='validate':validate_machine(a.receipt);return 0
  return markdown(a)
 except c.ContractError as e:print(str(e),file=sys.stderr);return 2
 except ValueError as e:print('E_SCHEMA: '+str(e),file=sys.stderr);return 2
 except (OSError,TypeError,KeyError,AttributeError) as e:print('E_IO: '+str(e),file=sys.stderr);return 3
if __name__=='__main__':sys.exit(main())
