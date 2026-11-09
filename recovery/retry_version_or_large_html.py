#!/usr/bin/env python3
"""Narrow additive retry of old source-version and oversized-page failures.

Reuses completed 4 source shards; downloads only IDs previously rejected by
overstrict header or HTML size. No speculative Pine editing, no protected access.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,urllib.parse,urllib.error
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from recover_public_strategy_sources import http_get,canonical_publication,IMPORT,DECL

VALID_STATES={"SOURCE_VERSION_HEADER_MISSING","RECOVERY_ERROR"}
VERSION_ANY=re.compile(r"(?m)^\s*//\s*@version\s*=\s*(\d+)\b")
VERSION_CORRECT=re.compile(r"(?m)^\s*//@version\s*=\s*([456])\b")
MAX_PAGE=10000000
MAX_SOURCE=550000

def retry(row,folder):
    old_state=row["recovery_state"]
    if old_state not in VALID_STATES:return row
    if row["original_access"] in ("2","3"):return row
    sid=row["script_id"]
    updated=dict(row)
    updated["error"]=""
    try:
        pub=row["pub_id"]
        if old_state=="RECOVERY_ERROR":
            url=row["tradingview_url"]
            page=http_get(url,MAX_PAGE).decode("utf-8",errors="replace")
            if sid not in page:raise ValueError("SCRIPT_ID_NOT_FOUND_ON_PUBLIC_PAGE")
            ids=canonical_publication(page)
            if len(ids)!=1:raise ValueError("AMBIGUOUS_OR_MISSING_PUBLICATION_ID")
            pub="PUB;"+ids[0]
        if not re.fullmatch(r"PUB;[A-Za-z0-9]{9,80}",pub):
            raise ValueError("PUBLICATION_ID_INVALID")
        srcurl="https://pine-facade.tradingview.com/pine-facade/get/"+urllib.parse.quote(pub,safe="")+"/last"
        payload=json.loads(http_get(srcurl,750000))
        source=payload.get("source")
        if not isinstance(source,str) or not source.strip():
            raise ValueError("PINE_SOURCE_EMPTY")
        raw=source.encode("utf-8")
        if len(raw)>MAX_SOURCE:raise ValueError("PINE_SOURCE_EXCEEDS_MAX")
        declarations=list(DECL.finditer(source))
        if len(declarations)!=1 or declarations[0].group(1)!="strategy":
            raise ValueError("SOURCE_NOT_EXACTLY_ONE_STRATEGY")
        match=VERSION_ANY.search(source)
        version=match.group(1) if match else ""
        canonical=VERSION_CORRECT.search(source) is not None
        target=folder/"recovered"/sid;target.mkdir(parents=True,exist_ok=True)
        (target/"strategy.pine").write_bytes(raw)
        checksum=hashlib.sha256(raw).hexdigest()
        updated.update({
            "recovery_state":"OFFICIAL_OPEN_SOURCE_RETRIEVED" if canonical else "OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW",
            "pub_id":pub,"pine_sha256":checksum,"source_bytes":len(raw),
            "pine_version":version,"direct_imports":" | ".join(IMPORT.findall(source)),
            "source_path":f"recovered/{sid}/strategy.pine","access_reason":"",
        })
        manifest={
            "script_id":sid,"source_url":updated["tradingview_url"],"facade_pub_id":pub,
            "source_origin":"TradingView public Pine publication",
            "source_sha256":checksum,"raw_bytes":len(raw),
            "original_source_preserved":True,
            "version_annotation":version or "UNKNOWN_DEFAULT",
            "version_annotation_canonical":canonical,
            "direct_imports":IMPORT.findall(source),
            "library_closure_status":"PENDING" if IMPORT.search(source) else "NO_IMPORTS",
            "source_rights_state":"REVIEW_REQUIRED",
            "python_conversion":"NOT_RUN",
            "tradingview_parity_verified":False,
            "recovery_reason":"VERSION_FILTER_RELAXED_OR_HTML_LIMIT_INCREASED",
            "retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
        }
        (target/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        return updated
    except urllib.error.HTTPError as e:
        updated["error"]="RETRY_HTTP_"+str(e.code)
        updated["recovery_state"]="RETRY_ACCESS_GATED" if e.code in (401,403) else "RETRY_HTTP_ERROR"
    except Exception as e:
        updated["error"]=type(e).__name__+":"+str(e)[:180]
        updated["recovery_state"]="RETRY_SOURCE_FAILED"
    return updated

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--shard-dir",required=True)
    args=parser.parse_args()
    base=Path(args.shard_dir)
    current=base/"status.csv"
    rows=list(csv.DictReader(current.open(encoding="utf-8-sig",newline="")))
    if len(rows) not in (884,885):raise ValueError("WRONG_SHARD_ROWS")
    targets=sum(x["recovery_state"] in VALID_STATES for x in rows)
    count=0
    for i,r in enumerate(rows):
        if r["recovery_state"] not in VALID_STATES:continue
        rows[i]=retry(r,base);count+=1
        time.sleep(0.65)
        if count%25==0:print("RETRY_PROGRESS",count,targets,flush=True)
    (base/"original_recovery_summary.json").write_text(
        (base/"summary.json").read_text(encoding="utf-8"),encoding="utf-8")
    with current.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    counts=dict(Counter(x["recovery_state"] for x in rows))
    summary={"rows":len(rows),"retry_targets":targets,"retried":count,
             "source_state_counts":counts,"protected_original_never_requested":True}
    (base/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RETRY_SHARD_FINAL",json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
