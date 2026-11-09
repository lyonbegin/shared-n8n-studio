#!/usr/bin/env python3
"""Conservative native Pine Library flattening and hoox-PYNE emission.

Only non-transitive, function-only Library imports. Original source SHA is
verified before deriving Pine. Runtime wrappers are NEVER counted as
native-transpiled. Generated Python remains unvalidated until bar/position
parity checks.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re,sys,csv
from pathlib import Path

sys.path.insert(0,"/tmp/wf02-isolated/n8n/editor-adapter")
from investment_free_pyne import compile_pine,FreePineBlocked
from investment_pynecomp import sha

IMPORT=re.compile(r"(?m)^[ \t]*import[ \t]+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\d+)(?:[ \t]+as[ \t]+([A-Za-z_]\w*))?[ \t]*(?:\r?\n|$)")
EXPORT=re.compile(r"(?m)^export[ \t]+(?:method|type|enum)\b")
DECL_LINE=re.compile(r"^(?:export[ \t]+)?([A-Za-z_]\w*)\s*\([^\n]*\)\s*=>\s*(?://.*)?$")
STRATEGY=re.compile(r"(?m)^[ \t]*strategy\s*\(")
def psha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def strategy_header_end(source):
 m=STRATEGY.search(source)
 if not m:raise ValueError("DECLARATION_NOT_FOUND")
 quote=None;escape=False;depth=0
 for i in range(m.end()-1,len(source)):
  ch=source[i]
  if quote:
   if escape:escape=False
   elif ch=="\\":escape=True
   elif ch==quote:quote=None
   continue
  if ch in ('"',"'"):quote=ch
  elif ch=="(":depth+=1
  elif ch==")":
   depth-=1
   if depth==0:return i+1
 raise ValueError("STRATEGY_PARENS_UNCLOSED")

def functions_only(library):
 """Only extract *functions*, never declaration/initialization side effects."""
 if EXPORT.search(library):raise ValueError("UDT_METHOD_OR_ENUM_EXPORT_NOT_SAFELY_INLINEABLE")
 lines=library.splitlines(keepends=True)
 starts=[]
 # Functions must have an unambiguous top-level single-line signature.
 for i,l in enumerate(lines):
  if not l.strip() or l[0] in (" ","\t") or l.lstrip().startswith("//"):continue
  m=DECL_LINE.fullmatch(l.rstrip("\r\n"))
  if m:starts.append((i,m.group(1),l.startswith("export ")))
  elif l.startswith("export "):raise ValueError("MULTILINE_OR_COMPLEX_EXPORT")
 if not starts:raise ValueError("NO_FUNCTION_DECLARATIONS")
 blocks=[]
 for i,name,exp in starts:
  end=i+1
  while end<len(lines):
   line=lines[end]
   if not line.strip() or line.lstrip().startswith("//"):
    end+=1;continue
   if line[0] not in (" ","\t"):break
   end+=1
  blocks.append((name,exp,"".join(lines[i:end])))
 return blocks

def flatten(root):
 manifest=json.loads((root/"manifest.json").read_text())
 if manifest["status"]!="DEPENDENCY_COMPLETE_EXECUTION_NOT_VALIDATED":
  raise ValueError("DEPENDENCY_CLOSURE_INCOMPLETE")
 strategy=(root/"strategy.pine").read_text(encoding="utf-8-sig")
 raw_imports=list(IMPORT.finditer(strategy))
 if not raw_imports:raise ValueError("NO_IMPORTS")
 direct=manifest["direct_imports"]
 refs=[x.group(1) for x in raw_imports]
 if sorted(set(refs))!=sorted(set(direct)):
  raise ValueError("DIRECT_IMPORTS_DONT_MATCH_MANIFEST")
 if sorted(set(refs))!=sorted(set(manifest["transitive_imports"])):
  raise ValueError("TRANSITIVE_IMPORTS_REQUIRE_RUNTIME_LINKER")
 if len(raw_imports)>2:raise ValueError("MAX_TWO_DIRECT_LIBRARIES_PER_PROOF")
 exports=[]
 code=strategy
 for match in raw_imports:
  ref,alias=match.group(1),match.group(2)
  publisher,name,version=ref.split("/")
  alias=alias or name
  info=next((x for x in manifest["libraries"] if x["ref"]==ref),None)
  if not info:raise ValueError("MANIFEST_LIBRARY_NOT_FOUND")
  path=root/"libraries"/publisher/name/(version+".pine")
  if not path.is_file() or psha(path)!=info["sha256"]:
   raise ValueError("EXACT_LIBRARY_SOURCE_HASH_MISMATCH")
  lib=path.read_text(encoding="utf-8-sig")
  decl=re.search(r'\blibrary\s*\(\s*(?:title\s*=\s*)?["\x27]([^"\x27]+)',lib)
  if not decl or decl.group(1)!=name:
   raise ValueError("ACTUAL_LIBRARY_TITLE_INVALID")
  if re.search(r"(?m)^\s*import\s+",lib):
   raise ValueError("NESTED_LIBRARY_REFERENCE")
  functions=functions_only(lib)
  names=[x[0] for x in functions]
  exposed={x[0] for x in functions if x[1]}
  if not exposed:raise ValueError("NO_EXPORTED_LIBRARY_FUNCTIONS")
  used=re.findall(r"\b"+re.escape(alias)+r"\s*\.\s*([A-Za-z_]\w*)",code)
  if any(fn not in exposed for fn in used):
   raise ValueError("USES_NON_FUNCTION_EXPORT_OR_MISSING_FUNCTION")
  if not used:
   raise ValueError("STRATEGY_DOES_NOT_REFERENCE_LIBRARY_FUNCTION")
  for fname,exported,body in functions:
   pref=alias+"__"+fname
   body=re.sub(r"^export[ \t]+","",body,count=1)
   body=re.sub(r"(?m)^"+re.escape(fname)+r"(\s*\()",
                lambda m:pref+m.group(1),body,count=1)
   # Calls between helper/export functions must retain namespace isolation.
   for inner in names:
    body=re.sub(r"(?<![\w.])"+re.escape(inner)+r"(\s*\()",
                lambda m,x=inner:alias+"__"+x+m.group(1),body)
   exports.append((ref,pref,body))
  code=re.sub(r"\b"+re.escape(alias)+r"\s*\.\s*([A-Za-z_]\w*)",
              lambda m:alias+"__"+m.group(1),code)
 # Removing import lines leaves original strategy source otherwise identical.
 code=IMPORT.sub("",code)
 insertion=strategy_header_end(code)
 funcs="\n\n".join(x[2] for x in exports)
 code=code[:insertion]+"\n\n"+funcs+"\n\n"+code[insertion:]
 return code,exports

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--root",default="source_library_v2")
 p.add_argument("--out",default="native_inline_results")
 p.add_argument("--shard",type=int,default=0)
 p.add_argument("--shards",type=int,default=2)
 args=p.parse_args()
 root=Path(args.root);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 manifests=sorted(root.glob("strategies/*/manifest.json"))
 targets=[x for x in manifests if json.loads(x.read_text())["status"].startswith("DEPENDENCY_COMPLETE")]
 if args.shard<0 or args.shard>=args.shards:raise ValueError("SHARD_INVALID")
 targets=[x for i,x in enumerate(targets) if i%args.shards==args.shard]
 rows=[]
 for m in targets:
  sid=m.parent.name
  result={"id":sid,"status":"","error":"","pine_sha256":"",
          "generated_python_sha256":"","generated_python_bytes":0,
          "tradingview_parity_verified":False}
  try:
   derived,funcs=flatten(m.parent)
   directory=out/"strategies"/sid
   directory.mkdir(parents=True,exist_ok=True)
   (directory/"derived_inline.pine").write_text(derived,encoding="utf-8")
   result["pine_sha256"]=sha(derived)
   result["inlined_functions"]=[x[1] for x in funcs]
   try:
    py=compile_pine(derived,expected_sha=sha(derived),timeout=25)
    (directory/"generated.py").write_text(py,encoding="utf-8")
    result["status"]="NATIVE_PYTHON_EMITTED_UNVALIDATED"
    result["generated_python_sha256"]=sha(py)
    result["generated_python_bytes"]=len(py.encode())
   except FreePineBlocked as e:
    result["status"]="NATIVE_EMITTER_BLOCKED"
    result["error"]=e.code
  except Exception as e:
   result["status"]="FLATTENING_NOT_SUPPORTED"
   result["error"]=type(e).__name__+":"+str(e)[:210]
  rows.append(result)
  print("NATIVE_INLINE_CASE",json.dumps(result,ensure_ascii=False),flush=True)
 totals={"count":len(rows),"statuses":dict(collections.Counter(x["status"] for x in rows)),
         "native_python_output":sum(x["status"]=="NATIVE_PYTHON_EMITTED_UNVALIDATED" for x in rows),
         "parity_verified":0,"no_live_strategy_code_edited":True}
 (out/"result.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
 (out/"summary.json").write_text(json.dumps(totals,ensure_ascii=False,indent=2),encoding="utf-8")
 print("NATIVE_INLINE_BATCH_FINAL",json.dumps(totals,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
