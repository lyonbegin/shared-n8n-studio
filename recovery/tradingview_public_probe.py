#!/usr/bin/env python3
"""Public-only TradingView source recovery probe; metadata only; no bypasses."""
import csv, json, os, re, urllib.request, urllib.error
from pathlib import Path
from html import unescape
sample=["06wt9GNj","06zatx1k","095hwTxJ","2lGyzYkC","4N7k2rJQ",
        "XuywwObg","gLvESVRY","iCRFM0LS","sf4Hf10r",
        "08R4aSqS","09joRRrB","0CdpxY6o"]
root=Path("source_4428/strategy_4428_result")
rows={r["script_id"]:r for r in csv.DictReader(
    (root/"strategy_4428_source_status.csv").open(encoding="utf-8-sig"))}
results=[]
for sid in sample:
    row=rows[sid]
    url=row["tradingview_url"] or ("https://www.tradingview.com/script/"+sid+"/")
    result={"script_id":sid,"original_access":row["original_access"],
            "old_state":row["source_state"],"http":None,"content_length":None}
    try:
        req=urllib.request.Request(url,headers={
          "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
          "Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"})
        with urllib.request.urlopen(req,timeout=15) as r:
            html=r.read(1200000).decode("utf-8",errors="replace")
            result["http"]=r.status
            result["content_length"]=len(html)
            result["script_id_visible"]=sid in html
            for key in ["source-code","sourceCode","code-content","pine-script","Pine Script","//@version",
                        "&#47;&#47;@version","scriptSource","isOpenSource","protected","invite-only"]:
                result["token_"+key]=key.lower() in html.lower()
            result["version_literal_count"]=len(re.findall(r"//\s*@version\s*=",html))
            result["pre_elements"]=len(re.findall(r"<pre\b",html,re.I))
            result["code_elements"]=len(re.findall(r"<code\b",html,re.I))
            for pat in [r'(<pre\b[^>]*>[\s\S]{0,300})',r'(\/\/\s*@version[=\s][0-9][\s\S]{0,300})']:
                m=re.search(pat,html,re.I)
                if m:result["safe_sample"]=re.sub(r"[\r\n\t]+"," ",m.group(1))[:240]
    except urllib.error.HTTPError as e:
        result["http"]=e.code
        result["error"]="HTTP_"+str(e.code)
    except Exception as e:result["error"]=type(e).__name__+":"+str(e)[:160]
    results.append(result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
Path("recovery_probe.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
