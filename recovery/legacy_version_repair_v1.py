#!/usr/bin/env python3
"""Isolated, provenance-preserving hoox-PYNE attempts for legacy Strategy Pine.
Generated Python from migrated syntax is EXPERIMENTAL: never TradingView parity.
Original Pine is never overwritten and unsupported semantics are fail-closed.
"""
from __future__ import annotations
import argparse,ast,csv,hashlib,json,re,os,sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,os.environ.get("WF02_ADAPTER_DIR",""))
from investment_free_pyne import compile_pine,FreePineBlocked

VERSION=re.compile(r"(?m)^\s*//\s*@version\s*=\s*([0-9]+)\s*$")
IMPORT=re.compile(r"(?m)^\s*import\s+\S+")
DECL=re.compile(r"(?m)^\s*strategy\s*\(")
HASH=lambda raw: hashlib.sha256(raw).hexdigest()

def derive(source):
    """Only perform an explicit, reviewable *syntax probe*, not semantic migration."""
    m=VERSION.search(source)
    version=int(m.group(1)) if m else 1
    if version>=7:raise ValueError("PINE_FUTURE_VERSION")
    if version in (1,2):
        # V2 default security() lookahead differs from V3+ and v2 self references
        # require a state-variable rewrite. Never silently change either.
        if re.search(r"(?<![.\w])security\s*\(",source):
            raise ValueError("LEGACY_V2_SECURITY_LOOKAHEAD_REQUIRES_SEMANTIC_MIGRATION")
        for line in source.splitlines():
            mm=re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+)",line)
            if mm and re.search(r"\b"+re.escape(mm.group(1))+r"\s*\[",mm.group(2)):
                raise ValueError("LEGACY_V2_SELF_REFERENCE_REQUIRES_SEMANTIC_MIGRATION")
    if version in (1,2,3):
        derived=VERSION.sub("//@version=4",source,count=1) if m else "//@version=4\n"+source
        changes=["PINE_VERSION_SYNTAX_PROBE_"+str(version)+"_TO_4"]
    elif not re.search(r"(?m)^\s*//@version=[456]\s*$",source):
        derived=VERSION.sub("//@version="+str(version),source,count=1)
        changes=["CANONICALIZE_VERSION_COMMENT_ONLY"]
    else:
        derived=source
        changes=[]
    return derived,version,changes

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sources",required=True)
    p.add_argument("--audit",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--shards",type=int,default=4)
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--timeout",type=int,default=30)
    args=p.parse_args()
    if not 0<=args.shard<args.shards:raise ValueError("INVALID_SHARD")
    with open(args.audit,encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=4428 or len({x["script_id"] for x in rows})!=4428:
        raise ValueError("AUDIT_NOT_4428_UNIQUE")
    sources={}
    for f in Path(args.sources).rglob("recovered/*/strategy.pine"):
        sid=f.parent.name
        if sid in sources:raise ValueError("DUPLICATE_SOURCE:"+sid)
        sources[sid]=f
    pending=[r for r in rows if r["source_status"] in
             ("OFFICIAL_OPEN_SOURCE_RETRIEVED","OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW")
             and r["python_conversion_status"] not in
             ("PYTHON_GENERATED_UNVALIDATED","PYTHON_GENERATED_FROM_DERIVED_PINE_UNVALIDATED")
             and not r.get("import_refs")]
    pending=sorted(pending,key=lambda x:x["script_id"])
    selected=[r for i,r in enumerate(pending) if i%args.shards==args.shard]
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    status=[]
    for index,row in enumerate(selected,1):
        sid=row["script_id"]
        record={"script_id":sid,"status":"NOT_STARTED",
                "source_sha256":row["original_sha256"],
                "derived_sha256":"","python_sha256":"","pine_version":"",
                "changes":[],"reason":"","parity_verified":False,
                "strategy_orders_equivalent":False}
        try:
            f=sources.get(sid)
            if not f:raise ValueError("SOURCE_NOT_IN_IMMUTABLE_RECOVERY_PACKAGE")
            original=f.read_bytes()
            if HASH(original)!=record["source_sha256"]:
                raise ValueError("OFFICIAL_SOURCE_SHA256_MISMATCH")
            pine=original.decode("utf-8-sig")
            if not DECL.search(pine):raise ValueError("STRATEGY_DECLARATION_MISSING")
            if IMPORT.search(pine):raise ValueError("EXTERNAL_LIBRARY_NOT_ALLOWED_IN_LEGACY_JOB")
            derived,version,changes=derive(pine)
            record["pine_version"]=version
            record["changes"]=changes
            d=out/"strategies"/sid
            d.mkdir(parents=True,exist_ok=True)
            (d/"original.pine").write_bytes(original)
            (d/"derived_probe.pine").write_text(derived,encoding="utf-8")
            record["derived_sha256"]=HASH(derived.encode())
            generated=compile_pine(derived,expected_sha=record["derived_sha256"],timeout=args.timeout)
            # The adapter already checks the AST and execution entrypoint.
            assert ast.parse(generated)
            (d/"generated.py").write_text(generated,encoding="utf-8")
            record["python_sha256"]=HASH(generated.encode())
            record["status"]="EXPERIMENTAL_LEGACY_PYTHON_GENERATED_UNVALIDATED" if changes else "PYTHON_GENERATED_UNVALIDATED"
        except FreePineBlocked as exc:
            record["status"]="COMPILER_BLOCKED";record["reason"]=exc.code
        except Exception as exc:
            record["status"]="SEMANTIC_REVIEW_OR_SOURCE_BLOCKED"
            record["reason"]=str(exc)[:180]
        status.append(record)
        if index%25==0:print("LEGACY_PROGRESS",args.shard,index,len(selected),flush=True)
    (out/"results.json").write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"shard":args.shard,"total_candidates_across_shards":len(pending),
        "processed":len(selected),"states":dict(Counter(x["status"] for x in status)),
        "verbatim_sources_preserved":True,"tradingview_parity_verified":0,
        "experimental_outputs_must_not_be_promoted_to_paper":True}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LEGACY_REPAIR_FINAL",json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
