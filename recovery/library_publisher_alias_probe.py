"""Read-only diagnosis: whether old TradingView username redirects to a new publisher."""
import urllib.request,urllib.error,json,re,urllib.parse
HD={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0","Accept":"text/html,application/json"}
result=[]
for username in ["HeWhoMustNotBeNamed","Trendoscope","tbiktag","tbtkg","ZoomerXeus","jason5480"]:
 for typ in ["profile","author_feed"]:
  url=("https://www.tradingview.com/u/"+username+"/") if typ=="profile" else ("https://www.tradingview.com/api/v1/scripts/?"+urllib.parse.urlencode({"by":username,"q":"arrays" if "HeWho" in username or username=="Trendoscope" else "", "page":1,"per_page":24}))
  try:
   req=urllib.request.Request(url,headers=HD)
   with urllib.request.urlopen(req,timeout=20) as resp:
    body=resp.read(1500000);code=resp.status;final=resp.url
   row={"username":username,"kind":typ,"http":code,"final_url":final}
   if typ=="author_feed":
    data=json.loads(body);row["count"]=data.get("count");row["items"]=[{"name":x.get("name"),"user":(x.get("user") or {}).get("username"),"url":x.get("chart_url"),"type":x.get("script_type")} for x in data.get("results",[])[:12]]
  except Exception as e:row={"username":username,"kind":typ,"error":type(e).__name__+":"+str(e)[:160]}
  result.append(row);print("ALIAS_CHECK",json.dumps(row,ensure_ascii=False),flush=True)
from pathlib import Path
Path("publisher_alias_probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
