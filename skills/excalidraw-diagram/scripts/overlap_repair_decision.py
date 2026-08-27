#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import overlap_contract as c
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def main():
 ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True); d=sub.add_parser("decide"); d.add_argument("--detector","--current",dest="detector",required=True); d.add_argument("--round","--audit-round",dest="round",type=int,required=True); d.add_argument("--attempt","--repair-attempt",dest="attempt",type=int,required=True); d.add_argument("--edit-applied",default="false"); d.add_argument("--scene-digest"); d.add_argument("--previous-detector"); d.add_argument("--previous-decision"); d.add_argument("--output",required=True); a=ap.parse_args()
 try:
  if a.cmd=="decide":
   if a.edit_applied not in {"true","false"}: raise c.ContractError("E_SCHEMA")
   edit=a.edit_applied == "true"; c.verify_sidecar(a.detector); cur=load(a.detector); c.validate_record(cur)
   pd=load(a.previous_detector) if a.previous_detector else None; px=load(a.previous_decision) if a.previous_decision else None
   if a.previous_detector: c.verify_sidecar(a.previous_detector); c.validate_record(pd)
   if a.previous_decision: c.verify_sidecar(a.previous_decision); c.validate_record(px)
   out=c.decision(cur,a.round,a.attempt,edit,a.scene_digest,pd,px); c.write_atomic(a.output,out)
  return 0
 except c.ContractError as e: print(str(e),file=sys.stderr); return 2
 except ValueError as e: print(f"E_SCHEMA: {e}",file=sys.stderr); return 2
 except (OSError,KeyError,TypeError) as e: print(f"E_IO: {e}",file=sys.stderr); return 3
if __name__=="__main__": sys.exit(main())
