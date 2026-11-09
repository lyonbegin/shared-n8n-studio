#!/usr/bin/env python3
"""Compile recovered open Pine with the already pinned free hoox-PYNE.

Every byte of official source remains untouched; annotation-normalized input
is a separate derived file with independent SHA. Library-bearing Pine is never
reported as native converted until exact dependency closure is available.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,os,re,sys
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone

sys.path.insert(0,os.environ.get("WF02_ADAPTER_DIR",""))
from investment_pynecomp import scan_imports,sha
from investment_free_pyne import compile_pine,FreePineBlocked,status as pyne_status

HDR=re.compile(r"(?m)^(\s*)//\s+@version\s*=\s*([456])\s*$")
STATES={"OFFICIAL_OPEN_SOURCE_RETRIEVED","OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW"}
FIELDNAMES=["script_id","original_status","pine_sha256","import_count","imports",
 "conversion_status","python_sha256","python_bytes","derived_sha256","reason"]
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--source-root",required=True)
 p.add_argument("--output",required=True)
 p.add_argument("--compile-timeout",type=int,default=30)
 args=p.parse_args()
 src=Path(args.source_root)
 rows=list(csv.DictReader((src/"status.csv").open(encoding="utf-8-sig",newline="")))
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 results=[]
 for i,row in enumerate(rows,1):
    sid=row["script_id"]
    item={"script_id":sid,"original_status":row["recovery_state"],
          "pine_sha256":row["pine_sha256"],"import_count":0,"imports":"",
          "conversion_status":"SOURCE_NOT_RECOVERED","python_sha256":"","python_bytes":0,
          "derived_sha256":"","reason":""}
    if row["recovery_state"] not in STATES:
        results.append(item);continue
    try:
        loc=src/row["source_path"]
        raw=loc.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row["pine_sha256"]:
            raise ValueError("OFFICIAL_SOURCE_SHA_MISMATCH")
        code=raw.decode("utf-8")
        imports=scan_imports(code)
        item["import_count"]=len(imports)
        item["imports"]=" | ".join(imports)
        dest=out/"strategies"/sid
        (dest/"original").mkdir(parents=True,exist_ok=True)
        (dest/"original"/"strategy.pine").write_bytes(raw)
        if imports:
            item["conversion_status"]="BLOCKED_RECURSIVE_LIBRARY_SOURCES_NOT_YET_ACQUIRED"
            item["reason"]=" | ".join(imports)
        elif row["recovery_state"]=="OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW" and not HDR.search(code):
            item["conversion_status"]="PYNE_FREE_SOURCE_VERSION_REVIEW_REQUIRED"
            item["reason"]="Verbatim public Pine archived; native free emitter accepts v4-v6. No inferred revision."
        else:
            convert_input=code
            if row["recovery_state"]=="OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW":
                convert_input,count=HDR.subn(r"//@version=\2",code,count=1)
                if count!=1:raise ValueError("ANNOTATION_CANNOT_BE_SAFELY_NORMALIZED")
                (dest/"derived").mkdir(exist_ok=True)
                (dest/"derived"/"compile_input.pine").write_text(convert_input,encoding="utf-8")
                item["derived_sha256"]=sha(convert_input)
            try:
                py=compile_pine(convert_input,expected_sha=sha(convert_input),
                                timeout=args.compile_timeout)
                (dest/"conversion").mkdir(exist_ok=True)
                (dest/"conversion"/"generated.py").write_text(py,encoding="utf-8")
                item["conversion_status"]="PYTHON_GENERATED_FROM_DERIVED_PINE_UNVALIDATED" if item["derived_sha256"] else "PYTHON_GENERATED_UNVALIDATED"
                item["python_sha256"]=sha(py)
                item["python_bytes"]=len(py.encode("utf-8"))
            except FreePineBlocked as e:
                item["conversion_status"]=e.code
                item["reason"]="native emit failed, unvalidated"
        manifest={
          "script_id":sid,"raw_strategy_source_sha256":item["pine_sha256"],
          "compile_source_sha256":item["derived_sha256"] or item["pine_sha256"],
          "normalization_applied":bool(item["derived_sha256"]),
          "direct_imports":imports,
          "recursive_dependencies_complete":not bool(imports),
          "conversion_status":item["conversion_status"],
          "python_sha256":item["python_sha256"],"parity_verified":False,
          "original_source_preserved":True,
          "rights_state":"UNVERIFIED",
          "updated_at":datetime.now(timezone.utc).isoformat(),
        }
        (dest/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    except Exception as e:
        item["conversion_status"]="ERROR_"+type(e).__name__
        item["reason"]=str(e)[:260]
    results.append(item)
    if i%40==0 or i==len(rows):
        print("CONVERSION_PROGRESS",i,len(rows),flush=True)
 with (out/"conversion_status.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,FIELDNAMES);w.writeheader();w.writerows(results)
 info={"processed":len(rows),"states":dict(Counter(x["conversion_status"] for x in results)),
       "pyne":pyne_status(),"tradingview_parity_verified_count":0}
 (out/"summary.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
 print("CONVERSION_FINAL",json.dumps(info,ensure_ascii=False),flush=True)
if __name__=="__main__":
 main()
