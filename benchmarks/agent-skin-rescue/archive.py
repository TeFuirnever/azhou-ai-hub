"""Separate later archive command; never edits a completed producer receipt."""
from pathlib import Path
import argparse,json,sys
L=Path(__file__).resolve().parent;R=L.parents[1]
from offline_runtime import own,json_new,sha,validate_result,utc
from archive_raw import copy_raw

def archive(request,out,*,root=None):
 root=Path(root) if root is not None else R
 if root.resolve()!=R:raise ValueError('scope must be this source worktree')
 request=own(Path(request),root=root);out=own(Path(out),root=root)
 if not request.is_relative_to(root) or not out.is_relative_to(root):raise ValueError('outside candidate scope')
 data=json.loads(request.read_bytes())
 if data.get('scope')!='offline-archive-only':raise ValueError('archive authority invalid')
 if not isinstance(data.get('producers'),list) or not data['producers']:raise ValueError('archive requires explicit producer receipts')
 out.mkdir(mode=0o700);records=[]
 for i,item in enumerate(data['producers']):
  producer=own(Path(item['path']),root=root)
  if sha(producer)!=item['sha256']:raise ValueError('producer receipt drift')
  value=json.loads(producer.read_bytes());validate_result(value)
  if value['kind']!='C' or value['outputs'].get('stability')!='wait-observed' or not value['outputs'].get('raw_files'):raise ValueError('live or unknown output cannot be archived as stable')
  for j,raw in enumerate(value['outputs']['raw_files']):
   source=own(root/raw['path'],root=root);result=copy_raw(source,out/f'{i}-{j}.raw',producer,root=root)
   if result['producer_receipt_sha256']!=item['sha256']:raise ValueError('producer receipt identity drift')
   json_new(out/f'{i}-{j}-archive.json',result,root=root);records.append(result)
  if sha(producer)!=item['sha256']:raise ValueError('immutable producer changed')
 summary={'kind':'A','observed_at':utc(),'scope':'later archive only; source command success is separate','status':'complete' if all(x['status']=='complete' for x in records) else 'partial-failed','records':records,'originalProducersUnchanged':True}
 json_new(out/'result.json',summary,root=root)
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--out',required=True);a=p.parse_args();x=archive(a.request,a.out);print(json.dumps({'status':x['status'],'count':len(x['records'])}));raise SystemExit(0 if x['status']=='complete' else 1)
