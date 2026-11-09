#!/usr/bin/env python3
"""Conservative native Python emission proof for an actual library-backed Strategy.

Never alter original library or Strategy. Restrict experimental inlining to one
audited exact dependency and one exported Pine function, then invoke free
hoox-pyne's genuine native Python emitter on the derived Pine script.
This is NOT evidence of TradingView result parity.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path("/tmp/wf02-isolated/n8n/editor-adapter")))
from investment_free_pyne import compile_pine,FreePineBlocked
from investment_pynecomp import sha

SID="CJesxF5m"
REF="MightyZinger/Chikou/3"
IMPORT_RE=re.compile(r'(?m)^[ \t]*import[ \t]+MightyZinger/Chikou/3[ \t]+as[ \t]+filter[ \t]*\r?\n')
EXPORT_RE=re.compile(r"(?m)^export[ \t]+chikou\s*\(")

def get_function(pine):
 lines=pine.splitlines(keepends=True)
 starts=[i for i,line in enumerate(lines) if EXPORT_RE.match(line)]
 if len(starts)!=1:raise ValueError("EXPECTED_EXACTLY_ONE_EXPORT_CHIKOU")
 begin=starts[0];end=begin+1
 while end<len(lines):
  l=lines[end]
  if not l.strip() or l.lstrip().startswith("//"):
   end+=1;continue
  if l[0] not in (" ","\t"):
   break
  end+=1
 block="".join(lines[begin:end])
 if "\n    " not in block:raise ValueError("FUNCTION_BODY_NOT_FOUND")
 return re.sub(r"^export\s+chikou","filter_chikou",block,count=1)

def find_strategy_end(source):
 m=re.search(r"(?m)^[ \t]*strategy\s*\(",source)
 if not m:raise ValueError("STRATEGY_HEADER_NOT_FOUND")
 depth=0;in_quote=None;escaped=False
 for i in range(m.end()-1,len(source)):
  c=source[i]
  if in_quote:
   if escaped:escaped=False
   elif c=="\\":escaped=True
   elif c==in_quote:in_quote=None
   continue
  if c in ("'",'"'):in_quote=c
  elif c=="(":depth+=1
  elif c==")":
   depth-=1
   if depth==0:return i+1
 raise ValueError("UNCLOSED_STRATEGY_HEADER")

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--root",default="source_library_v1")
 p.add_argument("--out",default="native_inline_experiment")
 args=p.parse_args()
 root=Path(args.root)/"strategies"/SID
 strategy=(root/"strategy.pine").read_text(encoding="utf-8-sig")
 library=(root/"libraries"/"MightyZinger"/"Chikou"/"3.pine").read_text(encoding="utf-8-sig")
 manifest=json.loads((root/"manifest.json").read_text())
 if manifest["status"]!="DEPENDENCY_COMPLETE_EXECUTION_NOT_VALIDATED":
  raise ValueError("DEPENDENCIES_NOT_COMPLETE")
 if manifest["direct_imports"]!=[REF] or manifest["transitive_imports"]!=[REF]:
  raise ValueError("UNEXPECTED_DEPENDENCY_CLOSURE")
 lib_decl=re.search(r'(?m)^[ \t]*library\s*\(\s*["\x27]([^"\x27]+)',library)
 if not lib_decl or lib_decl.group(1)!="Chikou":raise ValueError("LIBRARY_TITLE_MISMATCH")
 source_sha=hashlib.sha256(strategy.encode()).hexdigest()
 lib_sha=hashlib.sha256(library.encode()).hexdigest()
 expected=next(x["sha256"] for x in manifest["libraries"] if x["ref"]==REF)
 if lib_sha!=expected:raise ValueError("LIBRARY_HASH_MISMATCH")
 fn=get_function(library)
 cleaned,n=IMPORT_RE.subn("",strategy,count=1)
 if n!=1:raise ValueError("EXPECTED_ONE_UNMODIFIED_IMPORT")
 cleaned,n=re.subn(r"\bfilter\s*\.\s*chikou\b","filter_chikou",cleaned)
 if n<1:raise ValueError("EXPORTED_FUNCTION_NOT_CALLED")
 insertion=find_strategy_end(cleaned)
 merged=cleaned[:insertion]+"\n\n"+fn+"\n"+cleaned[insertion:]
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 (out/"derived_inline.pine").write_text(merged,encoding="utf-8")
 row={"strategy_id":SID,"library_ref":REF,"source_strategy_sha256":source_sha,
      "source_library_sha256":lib_sha,"derived_inline_sha256":sha(merged),
      "function_reference_rewrites":n,
      "source_files_immutable":True,"tradingview_parity_verified":False}
 try:
  code=compile_pine(merged,expected_sha=sha(merged),timeout=30)
  (out/"generated.py").write_text(code,encoding="utf-8")
  row.update({"status":"NATIVE_PYTHON_EMITTED_FROM_DERIVED_PINE_UNVALIDATED",
              "python_sha256":sha(code),"python_bytes":len(code.encode())})
 except FreePineBlocked as e:
  row.update({"status":"NATIVE_COMPILATION_BLOCKED",
             "reason":e.code})
 (out/"result.json").write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding="utf-8")
 print("REAL_NATIVE_INLINE_RESULT",json.dumps(row,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
