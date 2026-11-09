#!/usr/bin/env python3
"""Recover genuinely open-source TradingView Strategy Pine from public pages.

For prior MISSING/MISMATCH only, no login, protected/invite-only remain gated.
Exact PUB publication ID is selected from current script page hydration, not
any incidental PUB reference. Pine code is saved as private Actions artifact
(not committed to the public repository). Never invent or normalize the
source bytes, use SHA-256 and immutable manifest.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,random,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone

HEADERS={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
         "Accept":"text/html,application/json,*/*","Origin":"https://www.tradingview.com"}
PUB_PATTERNS=[
    re.compile(r'"script_id_part"\s*:\s*"PUB;([a-zA-Z0-9]+)"'),
    re.compile(r'"scriptIdPart"\s*:\s*"PUB;([a-zA-Z0-9]+)"'),
    re.compile(r'\\"script_id_part\\"\s*:\s*\\"PUB;([a-zA-Z0-9]+)\\"'),
]
DECL=re.compile(r"(?m)^\s*(strategy|indicator|library)\s*\(")
IMPORT=re.compile(r"(?m)^\s*import\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\d+)(?:\s+as\s+[A-Za-z0-9_]+)?")
VERSION=re.compile(r"(?m)^\s*//@version\s*=\s*([456])\b")
LOOSE_VERSION=re.compile(r"(?m)^\s*//\s+@version\s*=\s*([456])\b")
MAX_SOURCE_BYTES=550000
FIELDNAMES=["script_id","tradingview_url","original_access","previous_state",
            "recovery_state","pub_id","pine_sha256","source_bytes","pine_version",
            "direct_imports","source_path","access_reason","error"]
def log(row): print("RECOVERY_RESULT",json.dumps(row,ensure_ascii=False),flush=True)
def status_row(item):
    return dict(script_id=item["script_id"],tradingview_url=item.get("tradingview_url",""),
      original_access=item.get("original_access",""),previous_state=item.get("source_state",""),
      recovery_state="",pub_id="",pine_sha256="",source_bytes=0,pine_version="",
      direct_imports="",source_path="",access_reason="",error="")
def http_get(url,limit,accept_json=False):
    for trial in range(3):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=27) as r:
                b=r.read(limit+1)
                if len(b)>limit: raise ValueError("HTTP_PAYLOAD_EXCEEDS_MAX")
                return b
        except urllib.error.HTTPError as e:
            if e.code in (401,403):
                raise
            if e.code not in (429,500,502,503,504) or trial==2:
                raise
            retry=e.headers.get("Retry-After","")
            time.sleep(min(24,max(3, float(retry) if retry.isdigit() else 2**(trial+2))))
        except (TimeoutError,ConnectionError,urllib.error.URLError):
            if trial==2:raise
            time.sleep(3*(trial+1))
def canonical_publication(html):
    ids=[]
    for pat in PUB_PATTERNS:
        ids.extend(pat.findall(html))
    ids=list(dict.fromkeys(ids))
    return ids
def recover(row,out):
    record=status_row(row)
    id=row["script_id"]
    if row["source_state"]=="PINE_RETRIEVED_FROM_PINNED_MIRROR":
        record["recovery_state"]="ALREADY_RETRIEVED_BY_PREVIOUS_WORKFLOW"
        return record
    if row.get("original_access") in ("2","3"):
        record["recovery_state"]="CLOSED_SOURCE_NO_PUBLIC_ACCESS"
        record["access_reason"]="protected" if row["original_access"]=="2" else "invite_only"
        return record
    url=row.get("tradingview_url") or ("https://www.tradingview.com/script/"+id+"/")
    if not url.startswith("https://www.tradingview.com/script/"+id):
        record["recovery_state"]="URL_ID_MISMATCH"
        return record
    try:
        page=http_get(url,2500000).decode("utf-8",errors="replace")
        if id not in page:
            record["recovery_state"]="PAGE_WITHOUT_REQUESTED_ID";return record
        ids=canonical_publication(page)
        if len(ids)!=1:
            record["recovery_state"]="PUB_ID_MISSING_OR_AMBIGUOUS"
            record["error"]="canonical_id_count="+str(len(ids))
            return record
        pub_id="PUB;"+ids[0]
        record["pub_id"]=pub_id
        srcurl="https://pine-facade.tradingview.com/pine-facade/get/"+urllib.parse.quote(pub_id,safe="")+"/last"
        try:
            payload=json.loads(http_get(srcurl,750000))
        except urllib.error.HTTPError as e:
            record["recovery_state"]="FACADE_ACCESS_GATED" if e.code in (401,403) else "FACADE_HTTP_ERROR"
            record["error"]="HTTP_"+str(e.code)
            return record
        pine=payload.get("source")
        if not isinstance(pine,str) or not pine.strip():
            record["recovery_state"]="FACADE_NO_PINE_SOURCE"
            return record
        raw=pine.encode("utf-8")
        if len(raw)>MAX_SOURCE_BYTES:
            record["recovery_state"]="SOURCE_OVERSIZED"
            return record
        matches=list(DECL.finditer(pine))
        if len(matches)!=1 or matches[0].group(1)!="strategy":
            record["recovery_state"]="SOURCE_NOT_SINGLE_STRATEGY"
            record["error"]="declaration_types="+",".join(x.group(1) for x in matches[:6])
            return record
        version=VERSION.search(pine)
        loose=LOOSE_VERSION.search(pine) if not version else None
        if not (version or loose):
            record["recovery_state"]="SOURCE_VERSION_HEADER_MISSING"
            return record
        scriptdir=out/"recovered"/id
        scriptdir.mkdir(parents=True,exist_ok=True)
        local=scriptdir/"strategy.pine"
        local.write_bytes(raw)
        record["recovery_state"]="OFFICIAL_OPEN_SOURCE_RETRIEVED" if version else "OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW"
        record["pine_sha256"]=hashlib.sha256(raw).hexdigest()
        record["source_bytes"]=len(raw)
        record["pine_version"]=version.group(1) if version else loose.group(1)
        record["direct_imports"]=" | ".join(IMPORT.findall(pine))
        record["source_path"]=str(local.relative_to(out))
        manifest={
          "script_id":id,"source_url":url,"facade_pub_id":pub_id,
          "source_origin":"TradingView public publication script source",
          "source_sha256":record["pine_sha256"],"raw_bytes":len(raw),
          "source_is_verbatim":True,"version_comment_canonical":version is not None,
          "import_refs":IMPORT.findall(pine),
          "library_closure_status":"PENDING_RECURSIVE_RESOLUTION" if IMPORT.search(pine) else "NO_EXTERNAL_LIBRARIES",
          "retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
          "rights_status":"PENDING_LICENSE_REVIEW",
          "conversion_status":"NOT_STARTED",
          "strategy_parity_verified":False,
        }
        (scriptdir/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        return record
    except urllib.error.HTTPError as e:
        record["recovery_state"]="PAGE_HTTP_ERROR"
        record["error"]="HTTP_"+str(e.code)
    except Exception as e:
        record["recovery_state"]="RECOVERY_ERROR"
        record["error"]=type(e).__name__+":"+str(e)[:180]
    return record

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--shards",type=int,default=4)
    p.add_argument("--delay",type=float,default=0.65)
    p.add_argument("--limit",type=int,default=0)
    args=p.parse_args()
    rows=list(csv.DictReader(Path(args.input).open(encoding="utf-8-sig",newline="")))
    if len(rows)!=4428 or len({r["script_id"] for r in rows})!=4428:
        raise ValueError("EXPECTED_4428_EXACT_CATALOG_IDS")
    missing=[x for x in rows if x["source_state"]!="PINE_RETRIEVED_FROM_PINNED_MIRROR"]
    if len(missing)!=3537:raise ValueError(f"EXPECTED_3537_OLD_MISSING_GOT_{len(missing)}")
    if args.shard<0 or args.shard>=args.shards:raise ValueError("INVALID_SHARD")
    selected=[x for i,x in enumerate(missing) if i%args.shards==args.shard]
    if args.limit:selected=selected[:args.limit]
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,row in enumerate(selected,1):
        result=recover(row,output);results.append(result)
        if result["recovery_state"]!="CLOSED_SOURCE_NO_PUBLIC_ACCESS":
            time.sleep(max(0.1,args.delay))
        if i%40==0 or i==len(selected):
            print("SHARD_PROGRESS",args.shard,i,len(selected),flush=True)
    with (output/"status.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDNAMES);w.writeheader();w.writerows(results)
    info={"shard":args.shard,"count":len(selected),
          "recovery_state_counts":dict(Counter(x["recovery_state"] for x in results)),
          "source_bytes":sum(int(x["source_bytes"] or 0) for x in results),
          "public_network_requests_only":True,"protected_source_bypass":False}
    (output/"summary.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SHARD_RESULT",json.dumps(info,ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
