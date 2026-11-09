#!/usr/bin/env python3
"""Diagnostic: is authenticated GitHub public code search available on GITHUB_TOKEN?
This queries *only public GitHub code search*; never requests TradingView closed code.
"""
import os,json,urllib.request,urllib.parse,urllib.error
out=[]
for sid in ["06zatx1k","095hwTxJ","09joRRrB"]:
    q='"'+sid+'"'
    uri="https://api.github.com/search/code?q="+urllib.parse.quote(q)
    headers={"Accept":"application/vnd.github+json",
             "User-Agent":"strategy960-public-source-audit/1",
             "X-GitHub-Api-Version":"2022-11-28"}
    if os.environ.get("GH_TOKEN"):headers["Authorization"]="Bearer "+os.environ["GH_TOKEN"]
    try:
        with urllib.request.urlopen(urllib.request.Request(uri,headers=headers),timeout=15) as resp:
            data=json.load(resp)
        items=data.get("items",[])
        row={"id":sid,"http":200,"total":data.get("total_count"),
             "candidate_files":[{"repo":x.get("repository",{}).get("full_name"),
                                 "path":x.get("path"),"html_url":x.get("html_url")} for x in items[:10]]}
    except urllib.error.HTTPError as e:
        body=e.read(2500).decode(errors="replace")
        row={"id":sid,"http":e.code,"error":body[:650]}
    except Exception as e:
        row={"id":sid,"error":str(e)[:350]}
    out.append(row)
    print("PUBLIC_SEARCH_PROBE",json.dumps(row,ensure_ascii=False),flush=True)
from pathlib import Path
Path("protected960_gitcode_search_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
