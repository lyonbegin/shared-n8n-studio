#!/usr/bin/env python3
"""Bounded equivalence test: original Pine+exact imported Libraries vs inlined Pine.

Uses identical 48 synthetic bars. It is ONLY internal PYNE equivalence, not
TradingView parity, and not proof of semantic equivalence for untested inputs.
Never execute generated native Python directly as untrusted input.
"""
import json,os,sys,subprocess,argparse,hashlib
from pathlib import Path
from collections import Counter

CHILD=r'''
import sys,json,hashlib
from pathlib import Path
from pynescript.runtime import Runtime
source=Path(sys.argv[1]);derived=Path(sys.argv[2])
manifest=json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
libs=[]
for x in manifest["libraries"]:
 p=Path(sys.argv[3]).parent/"libraries"/(x["ref"]+".pine")
 raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=x["sha256"]:
  raise ValueError("LIBRARY_BYTES_SHA256_FAILED")
 owner,name,version=x["ref"].split("/")
 libs.append({"namespace":owner,"name":name,"version":int(version),"source":raw.decode("utf-8-sig")})
original=source.read_bytes()
if hashlib.sha256(original).hexdigest()!=manifest["strategy_sha256"]:
 raise ValueError("STRATEGY_ORIGINAL_BYTES_SHA256_FAILED")
pine=original.decode("utf-8-sig")
derived_text=derived.read_text(encoding="utf-8")
bars=[{"time":1700000000000+i*86400000,
       "open":100.0+i*.35,"high":101.5+i*.35,
       "low":99.5+i*.35,"close":100.4+i*.35,
       "volume":900+i*7.0} for i in range(48)]
def run(code,dep):
 try:
  return Runtime(symbol="TEST").run(code,bars,mode="interpret",libraries=dep)
 except Exception as e:
  return {"error":type(e).__name__+":"+str(e)[:330]}
def present(result):
 if not isinstance(result,dict):return {"error":"NOT_DICT"}
 ret={k:result.get(k) for k in ["error","series","orders","trades","strategy","equity"] if k in result}
 return ret
a=present(run(pine,libs));b=present(run(derived_text,[]))
if a.get("error") or b.get("error"):
 status="RUNTIME_ERROR_UNDETERMINED"
elif a==b and any(k in a for k in ("series","orders","trades","strategy","equity")):
 status="INTERNAL_PYNE_BARS_PARITY_MATCH"
elif a==b:
 status="NO_COMPARABLE_OUTPUT"
else:
 status="PYNE_INTERNAL_MISMATCH"
obj={"id":sys.argv[4],"status":status,
     "original_keys":sorted(a.keys()),"derived_keys":sorted(b.keys()),
     "original_error":str(a.get("error",""))[:180],
     "derived_error":str(b.get("error",""))[:180],
     "same_data":a==b,
     "tradingview_parity_verified":False}
print("RESULT_JSON="+json.dumps(obj,ensure_ascii=False,default=str))
'''
def run():
 p=argparse.ArgumentParser()
 p.add_argument("--bundles",required=True)
 p.add_argument("--inline",required=True)
 p.add_argument("--output",required=True)
 p.add_argument("--timeout",type=int,default=15)
 p.add_argument("--shard",type=int,default=0)
 p.add_argument("--shards",type=int,default=2)
 args=p.parse_args()
 bundles=Path(args.bundles);inline=Path(args.inline)
 paths=sorted(inline.glob("strategies/*/generated.py"))
 paths=[p for i,p in enumerate(paths) if i%args.shards==args.shard]
 outputs=[]
 for path in paths:
  sid=path.parent.name
  f=bundles/"strategies"/sid
  try:
   proc=subprocess.run([sys.executable,"-c",CHILD,
      str(f/"strategy.pine"),str(path.parent/"derived_inline.pine"),str(f/"manifest.json"),sid],
      capture_output=True,text=True,timeout=args.timeout)
   line=next((s.split("RESULT_JSON=",1)[1] for s in proc.stdout.splitlines()
              if s.startswith("RESULT_JSON=")),None)
   value=json.loads(line) if line else {"id":sid,"status":"CHILD_FAILED",
      "error":proc.stderr[-300:]}
  except subprocess.TimeoutExpired:
   value={"id":sid,"status":"INTERNAL_PYNE_TIMEOUT"}
  outputs.append(value)
  print("PARITY_CASE",json.dumps(value,ensure_ascii=False),flush=True)
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 report={"checked":len(outputs),"states":dict(Counter(x["status"] for x in outputs)),
         "tradingview_parity_verified":0,
         "comparison_basis":"same source version, identical 48 synthetic OHLCV bars; source+libraries against inlined source, both interpreted by PYNE"}
 (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 (out/"case_results.json").write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding="utf-8")
 print("PARITY_FINAL",json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":run()
