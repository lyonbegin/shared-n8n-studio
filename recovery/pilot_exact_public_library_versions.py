#!/usr/bin/env python3
"""Verify exact TradingView public Library versions; no access bypass."""
import json,re,urllib.request,urllib.error,urllib.parse,hashlib,time
from pathlib import Path
LIBS=[
  ("TradingView/ta/7","https://www.tradingview.com/script/BICzyhq0-ta/"),
  ("TradingView/ta/10","https://www.tradingview.com/script/BICzyhq0-ta/"),
  ("TradingView/ta/14","https://www.tradingview.com/script/BICzyhq0-ta/"),
  ("jason5480/chrono_utils/7","https://www.tradingview.com/script/LFr7gOBH-chrono-utils/"),
  ("jason5480/chrono_utils/8","https://www.tradingview.com/script/LFr7gOBH-chrono-utils/"),
]
hdr={"User-Agent":"Mozilla/5.0 Chrome/130.0","Origin":"https://www.tradingview.com","Accept":"application/json,text/html,*/*"}
def get(url):
  with urllib.request.urlopen(urllib.request.Request(url,headers=hdr),timeout=20) as r:return r.read(1100000).decode("utf-8","replace")
out=[]
for name,url in LIBS:
  user,lib,version=name.split("/")
  row={"import":name,"url":url}
  try:
    page=get(url);ids=list(dict.fromkeys(re.findall(r'"script_id_part"\s*:\s*"PUB;([A-Za-z0-9]+)"',page)))
    row["publication_candidates"]=len(ids)
    if len(ids)!=1:raise ValueError("Publication ID ambiguous")
    pid="PUB;"+ids[0];row["pub_id"]=pid
    for ver in [version,"last"]:
      target="https://pine-facade.tradingview.com/pine-facade/get/"+urllib.parse.quote(pid,safe="")+"/"+ver
      try:
        res=json.loads(get(target));src=res.get("source","")
        row[ver]={"source_bytes":len(src.encode()),"sha256":hashlib.sha256(src.encode()).hexdigest(),"pine_library_title":re.findall(r'(?m)^\s*library\s*\(\s*["\x27]([^"\x27]+)',src)[:2],"imports":re.findall(r"(?m)^\s*import\s+([\w.-]+/[\w.-]+/\d+)",src),"head":src[:170]}
        if src and ver==version:Path("library_pilot_sources").mkdir(exist_ok=True);(Path("library_pilot_sources")/(user+"_"+lib+"_"+version+".pine")).write_text(src,encoding="utf-8")
      except Exception as e:row[ver]={"error":type(e).__name__+": "+str(e)[:130]}
    row["different_exact_vs_last"]=row.get(version,{}).get("sha256")!=row.get("last",{}).get("sha256")
  except Exception as e:row["error"]=type(e).__name__+":"+str(e)[:170]
  out.append(row);print("PILOT_LIBRARY",json.dumps(row,ensure_ascii=False),flush=True);time.sleep(.5)
Path("library_version_pilot.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
