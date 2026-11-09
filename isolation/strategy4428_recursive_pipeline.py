#!/usr/bin/env python3
"""Strategy-only (4428 IDs) source, recursive import, package, PYNE audit.

All library versions must be backed by independently auditable pinned original
source (URL + SHA-256 + namespace/name/version). No substitutions. Each strategy
has a complete *copy* of all its dependencies when obtainable. Public/private
and multi-strategy classification is metadata only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

# Clone of the already isolated project-owned WF02 source, never production.
sys.path.insert(0,os.environ.get("WF02_ADAPTER_DIR",""))
from investment_pynecomp import scan_imports, resolve_imports, dependency_lock, sha, PyneCompBlocked
from investment_free_pyne import compile_pine, FreePineBlocked, status as pyne_status

MAX_BYTES=512*1024
REF_RE=re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/([0-9]+)$")
HEADER_RE=re.compile(r"(?m)^\s*//@version\s*=\s*[456]\b")
LIB_DECL_RE=re.compile(r'(?m)^\s*library\s*\(\s*["\x27]([^"\x27]+)["\x27]')
STATUS_FIELDS=[
    "script_id","title","tradingview_url","strategy_source_status",
    "source_sha256","source_bytes","direct_import_count","transitive_import_count",
    "library_resolution_status","missing_libraries","resolved_libraries",
    "dependency_lock_hash","conversion_status","python_bytes","python_sha256",
    "error","package_path"
]
def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")

def hashed(data):
    return hashlib.sha256(data).hexdigest()

def catalog_rows(csvpath):
    with open(csvpath,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=4428 or len({r["script_id"] for r in rows})!=4428:
        raise ValueError("SOURCE_ARTIFACT_NOT_4428_UNIQUE_STRATEGIES")
    if any(not re.fullmatch(r"[A-Za-z0-9]{8}",r["script_id"]) for r in rows):
        raise ValueError("INVALID_SCRIPT_IDS")
    return rows

def load_registry(path):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    data=d.get("libraries",{})
    if not isinstance(data,dict):raise ValueError("LIBRARY_REGISTRY_MUST_BE_MAPPING")
    return data

def verified_library_source(name,registry,cache,attempts):
    if name in cache:return cache[name]
    if name in attempts:return None
    attempts.add(name)
    info=registry.get(name)
    if not isinstance(info,dict):
        cache[name]=None
        return None
    match=REF_RE.fullmatch(name)
    if not match:raise ValueError("INVALID_IMPORT_NAME:"+name)
    namespace,libname,version=match.groups()
    uri=str(info.get("raw_url") or "")
    expected=str(info.get("sha256") or "").lower()
    if info.get("namespace")!=namespace or info.get("name")!=libname or str(info.get("version"))!=version:
        raise ValueError("LIBRARY_REGISTRY_ID_VERSION_MISMATCH:"+name)
    if not re.fullmatch(r"[0-9a-f]{64}",expected):
        raise ValueError("LIBRARY_REGISTRY_MISSING_SHA256:"+name)
    url=urllib.parse.urlparse(uri)
    if url.scheme!="https" or url.hostname not in {"raw.githubusercontent.com","github.com","www.tradingview.com","tradingview.com"} or url.username or url.password:
        raise ValueError("LIBRARY_REGISTRY_URL_NOT_APPROVED:"+name)
    if url.hostname=="raw.githubusercontent.com":
        parts=url.path.strip("/").split("/")
        if len(parts)<5 or not re.fullmatch(r"[0-9a-f]{40}",parts[2]):
            raise ValueError("LIBRARY_SOURCE_MUST_USE_PINNED_GIT_SHA:"+name)
    req=urllib.request.Request(uri,headers={"User-Agent":"stock-automation-library-pinner/1"})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            data=response.read(MAX_BYTES+1)
    except Exception as e:
        raise ValueError("LIBRARY_DOWNLOAD_FAILED:"+name+":"+type(e).__name__)
    if not data or len(data)>MAX_BYTES:
        raise ValueError("LIBRARY_EMPTY_OR_OVERSIZED:"+name)
    if hashed(data)!=expected:
        raise ValueError("LIBRARY_SHA256_MISMATCH:"+name)
    code=data.decode("utf-8-sig")
    if not HEADER_RE.search(code):
        raise ValueError("LIBRARY_MISSING_PINE_VERSION:"+name)
    declared=LIB_DECL_RE.search(code)
    if not declared or declared.group(1)!=libname:
        raise ValueError("LIBRARY_DECLARATION_MISMATCH:"+name)
    entry={"kind":"library","source_id":"/".join([namespace,libname]),
           "version_key":version,"source_sha256":sha(code),
           "pine_code":code,"origin_url":uri,
           "publication_url":info.get("publication_url",""),
           "rights_metadata":info.get("rights_metadata","NOT_REVIEWED")}
    cache[name]=entry
    return entry

def library_audit(script,registry,global_cache):
    direct=scan_imports(script)
    attempts=set()
    missing=set()
    def loader(ref):
        try:
            obj=verified_library_source(ref,registry,global_cache,attempts)
        except Exception as e:
            missing.add(ref+" ["+str(e)[:140]+"]")
            return None
        if obj is None:missing.add(ref+" [EXACT_SOURCE_NOT_IN_REGISTRY]")
        return obj
    try:
        closure=resolve_imports(script,loader)
        resolution="COMPLETE"
    except PyneCompBlocked as e:
        closure=[]
        resolution="INCOMPLETE:"+e.code
    # If at least one is missing, inspect every resolvable import separately
    # so the error report includes all immediate and transitive missing refs.
    if resolution!="COMPLETE":
        seen=set()
        def walk(ref):
            if ref in seen:return
            seen.add(ref)
            obj=loader(ref)
            if obj:
                for nxt in scan_imports(obj["pine_code"]):
                    walk(nxt)
        for item in direct: walk(item)
    return direct,closure,resolution,sorted(missing)

def emit_wrapper(dst,strategy,closure,source_sha,lock):
    """Python runtime wrapper, NOT a native Pine->Python transpilation."""
    libraries=[]
    for lib in closure:
        namespace,name,version=lib["import_name"].split("/")
        libraries.append({"namespace":namespace,"name":name,
                          "version":int(version),"source":lib["pine_code"]})
    data=json.dumps(libraries,ensure_ascii=False)
    code=(
      "# PYNE runtime wrapper: Pine sources embedded, NOT native transpilation\n"
      "# Source sha256: "+source_sha+"\n# Dependency lock: "+lock+"\n"
      "import json\nfrom pynescript.runtime import Runtime\n"
      "STRATEGY_SOURCE="+repr(strategy)+"\n"
      "LIBRARY_SOURCES=json.loads("+repr(data)+")\n"
      "def run(bars,symbol='TEST'):\n"
      "    return Runtime(symbol=symbol).run(STRATEGY_SOURCE,bars,\n"
      "      mode='auto',libraries=LIBRARY_SOURCES)\n"
    )
    dst.write_text(code,encoding="utf-8")

def work_row(row,root,output,registry,libcache,do_convert=True):
    sid=row["script_id"]
    pkg=output/"strategies"/sid
    pkg.mkdir(parents=True,exist_ok=True)
    source_state=row["source_state"]
    st={
      "strategy_id":sid,"title":row.get("script_title",""),
      "tradingview_url":row.get("tradingview_url",""),
      "original_source_status":source_state,
      "source_provenance":row.get("source_provenance",""),
      "source_identity_verified_against_tv":row.get("source_identity_verified_against_tv","False")=="True",
      "rights_state":row.get("rights_state","PENDING_REVIEW"),
      "strategy_pine_sha256":None,
      "direct_imports":[],"resolved_libraries":[],"missing_libraries":[],
      "library_resolution_status":"NOT_STARTED",
      "dependency_lock_hash":None,
      "conversion_status":"NOT_STARTED",
      "conversion_validated":False,
      "tradingview_parity_verified":False,
      "shared_library_metadata_only":True,
      "source_catalog_id":"TV_4428_20261108",
    }
    result={k:"" for k in STATUS_FIELDS}
    result.update(script_id=sid,title=row.get("script_title",""),
                  tradingview_url=row.get("tradingview_url",""),
                  strategy_source_status=source_state,package_path=f"strategies/{sid}")
    try:
        if source_state!="PINE_RETRIEVED_FROM_PINNED_MIRROR":
            st["library_resolution_status"]="BLOCKED_NO_STRATEGY_PINE"
            st["conversion_status"]="BLOCKED_NO_STRATEGY_PINE"
            result.update(library_resolution_status=st["library_resolution_status"],
                          conversion_status=st["conversion_status"])
        else:
            original=root/row["local_pine_path"]
            raw=original.read_bytes()
            if hashed(raw)!=row["pine_sha256"]:
                raise ValueError("ORIGINAL_PINE_SHA256_MISMATCH")
            if len(raw)>MAX_BYTES or not raw:
                raise ValueError("STRATEGY_PINE_INVALID_SIZE")
            code=raw.decode("utf-8-sig")
            if not HEADER_RE.search(code) or not re.search(r"(?m)^\s*strategy\s*\(",code):
                raise ValueError("STRATEGY_PINE_DECLARATION_MISSING")
            orig=pkg/"original";orig.mkdir(exist_ok=True)
            shutil.copyfile(original,orig/"strategy.pine")
            st["strategy_pine_sha256"]=hashed(raw)
            result.update(source_sha256=hashed(raw),source_bytes=str(len(raw)))
            direct,closure,resolution,missing=library_audit(code,registry,libcache)
            st["direct_imports"]=direct;st["missing_libraries"]=missing
            st["library_resolution_status"]=resolution
            result.update(direct_import_count=len(direct),transitive_import_count=len(closure),
                          library_resolution_status=resolution,
                          missing_libraries=" | ".join(missing))
            if resolution=="COMPLETE":
                libs=[]
                for lib in closure:
                    ns,name,version=lib["import_name"].split("/")
                    rel=f"libraries/{ns}/{name}/{version}.pine"
                    target=pkg/rel
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_text(lib["pine_code"],encoding="utf-8")
                    libs.append({"import_name":lib["import_name"],
                        "library_path":rel,
                        "sha256":lib["source_sha256"],
                        "source_url":lib.get("origin_url",""),
                        "publication_url":lib.get("publication_url",""),
                        "direct":lib["import_name"] in direct,
                        "commons_status":"UNKNOWN_UNTIL_CROSS_STRATEGY_AGGREGATION"})
                st["resolved_libraries"]=libs
                lock=dependency_lock(closure)
                st["dependency_lock_hash"]=lock
                result.update(resolved_libraries=" | ".join(x["import_name"] for x in libs),
                              dependency_lock_hash=lock,
                              transitive_import_count=len(libs))
                write_json(pkg/"dependency_graph.json",{
                    "strategy_id":sid,"direct_imports":direct,"closure":libs,
                    "edge_semantics":"Pine imports version-pinned, no version substitution"})
                convdir=pkg/"conversion";convdir.mkdir(exist_ok=True)
                if direct:
                    emit_wrapper(convdir/"runtime_wrapper.py",code,closure,st["strategy_pine_sha256"],lock)
                    st["conversion_status"]="PYNE_RUNTIME_WRAPPER_NOT_NATIVE_PYTHON"
                    # Keep the exact native compilation gate separate.
                    result["conversion_status"]=st["conversion_status"]
                elif do_convert:
                    try:
                        py=compile_pine(code,expected_sha=sha(code),timeout=45)
                        (convdir/"generated.py").write_text(py,encoding="utf-8")
                        st["conversion_status"]="PYTHON_GENERATED_UNVALIDATED"
                        st["python_sha256"]=sha(py)
                        result.update(conversion_status=st["conversion_status"],
                                      python_sha256=sha(py),python_bytes=len(py.encode()))
                    except FreePineBlocked as exc:
                        st["conversion_status"]=exc.code
                        result["conversion_status"]=exc.code
                else:
                    st["conversion_status"]="NOT_RUN"
                    result["conversion_status"]="NOT_RUN"
            else:
                st["conversion_status"]="BLOCKED_INCOMPLETE_LIBRARY_DEPENDENCIES"
                result.update(conversion_status=st["conversion_status"])
    except Exception as e:
        st["conversion_status"]="ERROR_"+type(e).__name__
        st["error"]=str(e)[:350]
        result.update(conversion_status=st["conversion_status"],error=st["error"])
    write_json(pkg/"manifest.json",st)
    return result

def save_rows(path,rows):
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,STATUS_FIELDS,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def run_shard(args):
    src=Path(args.source_root)
    allrows=catalog_rows(src/"strategy_4428_source_status.csv")
    idx=int(args.shard)
    if idx<0 or idx>=args.shards:raise ValueError("INVALID_SHARD")
    selected=[r for i,r in enumerate(allrows) if i%args.shards==idx]
    registry=load_registry(args.library_registry)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    libcache={};results=[]
    for i,row in enumerate(selected,1):
        results.append(work_row(row,src,out,registry,libcache,not args.skip_convert))
        if i%50==0 or i==len(selected):
            print("SHARD_PROGRESS",idx,i,len(selected),flush=True)
    save_rows(out/"status.csv",results)
    summary={
        "shard":idx,"shards":args.shards,"processed_ids":len(selected),
        "source_state_counts":dict(Counter(x["strategy_source_status"] for x in results)),
        "dependency_state_counts":dict(Counter(x["library_resolution_status"] for x in results)),
        "conversion_state_counts":dict(Counter(x["conversion_status"] for x in results)),
        "direct_import_occurrences":sum(int(x["direct_import_count"] or 0) for x in results),
        "resolved_library_occurrences":sum(int(x["transitive_import_count"] or 0) for x in results),
        "registry_entries":len(registry),
        "pyne":pyne_status(),
        "error_policy":"Never substitute missing Pine or library versions",
    }
    write_json(out/"shard_summary.json",summary)
    print("SHARD_RESULT",json.dumps(summary,ensure_ascii=False),flush=True)

def aggregate(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    # Artifacts are downloaded into a common folder using pattern + merge-multiple.
    shards=[Path(x) for x in sorted(args.shard_root.glob("shard-*/status.csv"))]
    if not shards:
        # artifact merge-multiple mode with each shard under distinct directory
        shards=sorted(args.shard_root.rglob("status.csv"))
    rows=[]
    for file in shards:
        with open(file,encoding="utf-8-sig",newline="") as f:rows.extend(csv.DictReader(f))
    if len(rows)!=4428 or len({x["script_id"] for x in rows})!=4428:
        raise ValueError(f"AGGREGATE_MISSING_IDS got={len(rows)} distinct={len({x['script_id'] for x in rows})}")
    save_rows(out/"strategy_4428_full_status.csv",sorted(rows,key=lambda x:x["script_id"]))
    usages=defaultdict(set)
    for row in rows:
        imports=set()
        for part in (row["resolved_libraries"],row["missing_libraries"]):
            for token in part.split(" | "):
                ref=token.split(" [")[0].strip()
                if REF_RE.fullmatch(ref): imports.add(ref)
        for lib in imports:usages[lib].add(row["script_id"])
    with (out/"library_shared_metadata.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(["exact_import_ref","observed_strategy_count","observed_in_strategy_ids",
                    "classification","metadata_only"])
        for lib,ids in sorted(usages.items()):
            w.writerow([lib,len(ids)," | ".join(sorted(ids)),
               "MULTI_STRATEGY_REFERENCE" if len(ids)>1 else "SINGLE_STRATEGY_OBSERVED","True"])
    summary={
        "input_unique_strategy_ids":len(rows),
        "pine_source_count":sum(x["strategy_source_status"]=="PINE_RETRIEVED_FROM_PINNED_MIRROR" for x in rows),
        "dependency_state_counts":dict(Counter(x["library_resolution_status"] for x in rows)),
        "conversion_state_counts":dict(Counter(x["conversion_status"] for x in rows)),
        "unique_referenced_libraries":len(usages),
        "repeated_library_references":sum(len(v)>1 for v in usages.values()),
        "verified_retrieval_note":"Pinned public mirror is not official TradingView revision parity",
        "library_completion_note":"Every library must have a pinned exact source and version; missing sources never substituted",
    }
    write_json(out/"summary.json",summary)
    print("STRATEGY_4428_FINAL",json.dumps(summary,ensure_ascii=False),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["shard","aggregate"],required=True)
    p.add_argument("--source-root",default="source_4428")
    p.add_argument("--library-registry",default="isolation/library_source_registry.json")
    p.add_argument("--output",required=True)
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--shards",type=int,default=4)
    p.add_argument("--skip-convert",action="store_true")
    p.add_argument("--shard-root",type=Path,default=Path("collected"))
    args=p.parse_args()
    if args.mode=="shard":run_shard(args)
    else:aggregate(args)
if __name__=="__main__":
    main()
