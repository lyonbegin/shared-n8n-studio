#!/usr/bin/env python3
"""Read public TradingView Pine sources by publication ID, no private/protected bypass."""
import csv,hashlib,json,re,urllib.request,urllib.error,urllib.parse
from pathlib import Path

SAMPLES=["06wt9GNj","08R4aSqS","07CF7RMb","06zatx1k","09joRRrB","095hwTxJ","2lGyzYkC","4N7k2rJQ","XuywwObg","gLvESVRY","iCRFM0LS","sf4Hf10r"]
rows={x["script_id"]:x for x in csv.DictReader(Path("source_4428/strategy_4428_result/strategy_4428_source_status.csv").open(encoding="utf-8-sig"))}
hdr={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
     "Origin":"https://www.tradingview.com"}
out=[];dest=Path("source_recovery_probe_sources");dest.mkdir(exist_ok=True)
for sid in SAMPLES:
    row=rows[sid];obj={"id":sid,"access":row["original_access"],"previous":row["source_state"]}
    if str(row["original_access"]) in ["2","3"]:
        obj["state"]="DECLARED_NOT_OPEN_SKIP_NO_REQUEST"
        out.append(obj);print(json.dumps(obj),flush=True);continue
    try:
        req=urllib.request.Request(row["tradingview_url"],headers=hdr)
        with urllib.request.urlopen(req,timeout=25) as r:
            html=r.read(2200000).decode("utf-8","replace")
        patterns=[
          r'"script_id_part"\s*:\s*"PUB;([0-9A-Za-z]+)"',
          r'"scriptIdPart"\s*:\s*"PUB;([0-9A-Za-z]+)"',
          r'\\"script_id_part\\"\s*:\s*\\"PUB;([0-9A-Za-z]+)\\"']
        vals=[]
        for p in patterns:
            vals.extend(re.findall(p,html))
        vals=list(dict.fromkeys(vals))
        obj["publication_candidates"]=len(vals)
        obj["publication_prefixes"]=[v[:6] for v in vals[:2]]
        if not vals:
            obj["state"]="NO_CANONICAL_PUB_ID"
        else:
            pid="PUB;"+vals[0]
            target="https://pine-facade.tradingview.com/pine-facade/get/"+urllib.parse.quote(pid,safe="")+"/last"
            req=urllib.request.Request(target,headers=hdr)
            try:
                with urllib.request.urlopen(req,timeout=25) as r:
                    data=r.read(750000)
                    obj["source_status_code"]=r.status
                payload=json.loads(data)
                source=payload.get("source")
                if not isinstance(source,str) or not source.strip():
                    obj["state"]="FACADE_HAS_NO_SOURCE"
                elif not re.search(r"(?m)^\s*(?:strategy|indicator|library)\s*\(",source):
                    obj["state"]="SOURCE_DECLARATION_MISSING"
                else:
                    obj["state"]="PINE_RETRIEVED_FACADE"
                    obj["source_chars"]=len(source)
                    obj["sha256"]=hashlib.sha256(source.encode("utf-8")).hexdigest()
                    obj["pine_type"]=(re.search(r"(?m)^\s*(strategy|indicator|library)\s*\(",source)).group(1)
                    (dest/(sid+".pine")).write_text(source,encoding="utf-8")
            except urllib.error.HTTPError as e:
                obj["source_status_code"]=e.code
                obj["state"]="FACADE_SOURCE_GATED" if e.code in (401,403) else "FACADE_HTTP_"+str(e.code)
    except Exception as e:
        obj["state"]="FETCH_ERROR"
        obj["error"]=type(e).__name__+":"+str(e)[:160]
    out.append(obj)
    print(json.dumps(obj,ensure_ascii=False),flush=True)
Path("facade_pilot.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
