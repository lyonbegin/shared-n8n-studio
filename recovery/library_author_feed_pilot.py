import json,re,hashlib,urllib.request,urllib.parse,time
HEAD={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36","Accept":"application/json","Origin":"https://www.tradingview.com"}
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=25) as resp:
  return json.load(resp)
for author,name,version in [("PineCoders","ConditionalAverages",2),("jason5480","chrono_utils",7),("TradingView","ta",7)]:
 try:
  endpoint="https://www.tradingview.com/api/v1/scripts/?"+urllib.parse.urlencode({"by":author,"q":name,"page":1,"per_page":24})
  feed=get(endpoint);items=feed.get("results",[])
  print("AUTHOR_RESULT",author,name,"count",len(items),"page_count",feed.get("page_count"),flush=True)
  ok=[]
  for item in items:
   if item.get("script_type") not in ("library","libraries") or item.get("script_access")!=1 or int(item.get("version") or 0)<version:continue
   pid=item.get("script_id_part")
   try:
    url="https://pine-facade.tradingview.com/pine-facade/get/"+urllib.parse.quote(pid,safe="")+"/"+str(version)
    result=get(url);source=result.get("source","")
    m=re.search("(?m)^\\s*library\\s*\\(\\s*['\\\"]([^'\\\"]+)",source)
    print("SOURCE_RESULT",author,name,pid,"requested",version,"returned",result.get("version"),"decl",m.group(1) if m else None,"bytes",len(source.encode()),"sha256",hashlib.sha256(source.encode()).hexdigest()[:16],flush=True)
    if m and m.group(1)==name:ok.append(pid)
   except Exception as exc:print("LIB_SOURCE_ERROR",name,type(exc).__name__,str(exc)[:160],flush=True)
  print("RESOLVED",author,name,ok,flush=True)
 except Exception as exc:print("AUTHOR_ERROR",author,name,type(exc).__name__,str(exc)[:180],flush=True)
