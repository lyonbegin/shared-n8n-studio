#!/usr/bin/env python3
"""Conservative transitive pure-function Library linker, isolated free PYNE.

Preserve exact Pine/Library originals; only derived code is changed.
Reject unknown types, methods, exports and source hash mismatches.
Do not claim TradingView parity or native Python if emit fails.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,'/tmp/wf02-isolated/n8n/editor-adapter')
from investment_free_pyne import compile_pine,FreePineBlocked
from investment_pynecomp import sha
from try_native_inline_batch import IMPORT,functions_only,strategy_header_end

def hashfile(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unique(ref,func):return 'L'+hashlib.sha256(ref.encode()).hexdigest()[:12]+'__'+func
def parsed_imports(source):return [(m.group(1),m.group(2) or m.group(1).split('/')[1]) for m in IMPORT.finditer(source)]

def inject(root):
 m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
 if not m['status'].startswith('DEPENDENCY_COMPLETE'):raise ValueError('CLOSURE_INCOMPLETE')
 source=(root/'strategy.pine').read_text(encoding='utf-8-sig')
 imp=parsed_imports(source)
 directrefs={x[0] for x in imp}
 if not directrefs:raise ValueError('NO_IMPORTS')
 meta={x['ref']:x for x in m['libraries']}
 if not directrefs.issubset(meta):raise ValueError('DIRECT_DEPENDENCIES_MISSING')
 if len(set(meta)-directrefs)==0:raise ValueError('NOT_TRANSITIVE')
 modules={};pending=set();order=[]
 def walk(ref):
  if ref in modules:return
  if ref in pending:raise ValueError('CYCLIC_LIBRARY_IMPORT')
  if ref not in meta:raise ValueError('MISSING_LIBRARY:'+ref)
  pending.add(ref)
  user,name,version=ref.split('/')
  path=root/'libraries'/user/name/(version+'.pine')
  if not path.is_file() or hashfile(path)!=meta[ref]['sha256']:
   raise ValueError('SOURCE_SHA256_INCORRECT:'+ref)
  text=path.read_text(encoding='utf-8-sig')
  raw_exports=functions_only(text)
  names={x[0] for x in raw_exports}
  exported={x[0] for x in raw_exports if x[1]}
  if not exported:raise ValueError('NO_EXPORTED_FUNCTIONS:'+ref)
  imports=parsed_imports(text)
  modules[ref]={'text':text,'functions':raw_exports,'names':names,'exported':exported,'imports':imports}
  for dep,_ in imports:walk(dep)
  pending.remove(ref);order.append(ref)
 for ref,_ in imp:walk(ref)
 if len(modules)>8:raise ValueError('TRANSITIVE_LIBRARY_COUNT_EXCEEDS_SAFE_LIMIT')
 def rewrite_calls(code,imports):
  for ref,alias in imports:
   dep=modules[ref]
   pattern=r'\b'+re.escape(alias)+r'\s*\.\s*([A-Za-z_]\w*)'
   used=re.findall(pattern,code)
   if any(x not in dep['exported'] for x in used):raise ValueError('NON_FUNCTION_EXPORTED_SYMBOL:'+ref)
   code=re.sub(pattern,lambda m:unique(ref,m.group(1)),code)
  return code
 blocks=[]
 for ref in order:
  mod=modules[ref]
  for fname,exposed,block in mod['functions']:
   block=re.sub(r'^export[ \t]+','',block,count=1)
   for inner in sorted(mod['names'],key=len,reverse=True):
    block=re.sub(r'(?<![A-Za-z0-9_.])'+re.escape(inner)+r'(\s*\()',
                 lambda m,x=inner:unique(ref,x)+m.group(1),block)
   block=rewrite_calls(block,mod['imports'])
   blocks.append(block)
 code=rewrite_calls(source,imp)
 code=IMPORT.sub('',code)
 if IMPORT.search(code):raise ValueError('UNREMOVED_IMPORT')
 at=strategy_header_end(code)
 combined=code[:at]+'\n\n'+'\n\n'.join(blocks)+'\n\n'+code[at:]
 if IMPORT.search(combined):raise ValueError('INJECTED_IMPORT_UNEXPECTED')
 return combined,order

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--root',required=True);p.add_argument('--out',required=True)
 p.add_argument('--shard',type=int,default=0);p.add_argument('--shards',type=int,default=2)
 args=p.parse_args();root=Path(args.root);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 cases=[]
 for i,manifest in enumerate(sorted(root.glob('strategies/*/manifest.json'))):
  if i%args.shards!=args.shard:continue
  row={'id':manifest.parent.name,'status':'','error':'','generated_python_sha256':'',
       'generated_python_bytes':0,'derived_pine_sha256':'','parity_verified':False}
  try:
   derived,deps=inject(manifest.parent)
   directory=out/'strategies'/row['id'];directory.mkdir(parents=True,exist_ok=True)
   (directory/'derived_inline.pine').write_text(derived,encoding='utf-8')
   row['derived_pine_sha256']=sha(derived);row['linked_library_refs']=deps
   try:
    code=compile_pine(derived,expected_sha=sha(derived),timeout=35)
    (directory/'generated.py').write_text(code,encoding='utf-8')
    row['status']='NATIVE_PYTHON_EMITTED_UNVALIDATED'
    row['generated_python_sha256']=sha(code)
    row['generated_python_bytes']=len(code.encode('utf-8'))
   except FreePineBlocked as e:
    row['status']='NATIVE_PYNE_COMPILE_BLOCKED';row['error']=e.code
  except Exception as e:
   row['status']='UNSAFE_OR_UNSUPPORTED';row['error']=type(e).__name__+':'+str(e)[:220]
  cases.append(row)
  print('TRANSITIVE_CASE',json.dumps(row,ensure_ascii=False),flush=True)
 counts=dict(collections.Counter(x['status'] for x in cases))
 report={'count':len(cases),'status_counts':counts,
         'native_python_emitted':counts.get('NATIVE_PYTHON_EMITTED_UNVALIDATED',0),
         'source_originals_modified':False,'tradingview_parity_verified':0}
 (out/'result.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print('TRANSITIVE_FINAL',json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
