#!/usr/bin/env python3
"""Real PYNE runtime smoke of complete, exact-version public Library bundles.

Native transpilation status is ALWAYS 'not done'; Runtime interpret success
means Pine executed via Python bridge, not source-to-source conversion.
No TradingView parity can be claimed from synthetic OHLCV bars.
"""
from __future__ import annotations
from collections import Counter
import argparse,json,subprocess,sys,traceback
from pathlib import Path

CHILD=r'''
import json,sys,runpy
from pathlib import Path
f=Path(sys.argv[1]);name=sys.argv[2]
try:
 ns=runpy.run_path(str(f))
 bars=[{"time":1700000000000+i*86400000,
 "open":float(100+i),"high":float(102+i),
 "low":float(99+i),"close":float(101+i),"volume":float(1000+i*2)}
 for i in range(40)]
 r=ns["execute"](bars,symbol="TEST")
 err=r.get("error") if isinstance(r,dict) else None
 obj={"id":name,
    "status":"PYNE_RUNTIME_SUCCESS_NO_TV_PARITY" if not err else "PYNE_RUNTIME_RESPONSE_ERROR",
    "error":str(err)[:550] if err else "",
    "runtime_backend":r.get("auto_backend") if isinstance(r,dict) else None}
except Exception as e:
 obj={"id":name,"status":"PYNE_RUNTIME_EXCEPTION",
      "error":type(e).__name__+":"+str(e)[:550]}
print("CHILD_RESULT_JSON="+json.dumps(obj,ensure_ascii=False))
'''
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--root",default="exact_library_result")
 p.add_argument("--limit",type=int,default=0)
 p.add_argument("--timeout",type=int,default=12)
 args=p.parse_args()
 root=Path(args.root)
 manifests=sorted(root.glob("strategies/*/manifest.json"))
 complete=[x for x in manifests if json.loads(x.read_text())["runtime_adapter_created"]]
 if args.limit:complete=complete[:args.limit]
 out=[]
 for i,m in enumerate(complete,1):
  sid=m.parent.name;file=m.parent/"runtime_adapter.py"
  try:
   # Isolated child gives time bounds and prevents shared strategy state.
   proc=subprocess.run([sys.executable,"-c",CHILD,str(file),sid],
           capture_output=True,text=True,timeout=args.timeout,cwd=str(Path.cwd()))
   text=proc.stdout
   line=next((x.split("CHILD_RESULT_JSON=",1)[1] for x in text.splitlines()
             if x.startswith("CHILD_RESULT_JSON=")),None)
   if not line:
    v={"id":sid,"status":"PYNE_SUBPROCESS_FAILED",
       "error":proc.stderr[-500:] or text[-500:],"exit":proc.returncode}
   else:v=json.loads(line)
  except subprocess.TimeoutExpired:
   v={"id":sid,"status":"PYNE_RUNTIME_TIMEOUT","error":""}
  v["native_python_transpiled"]=False
  v["tradingview_parity_verified"]=False
  out.append(v)
  print("REAL_LIBRARY_RUNTIME",json.dumps(v,ensure_ascii=False),flush=True)
 result={"examined_complete_dependency_strategies":len(out),
         "status_counts":dict(Counter(x["status"] for x in out)),
         "native_python_transpiled_count":0,
         "tradingview_parity_verified_count":0}
 (root/"real_library_runtime_status.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
 (root/"real_library_runtime_summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print("REAL_LIBRARY_RUNTIME_FINAL",json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
