import re, requests, urllib.parse
from bs4 import BeautifulSoup
from collections import Counter
urls=[
 "https://www.tradingview.com/u/FuturesTeller/#published-scripts",
 "https://www.tradingview.com/script/qXp6AwrJ-FT-Strategy-Engine-Template/",
 "https://www.tradingview.com/scripts/?script_type=indicators",
]
s=requests.Session();s.headers["User-Agent"]="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
for url in urls:
 try:
  r=s.get(url,timeout=30)
  soup=BeautifulSoup(r.text,"html.parser")
  anchors=[a.get("href","") for a in soup.select("a[href]")]
  sc=[x for x in anchors if re.search(r"/script/[A-Za-z0-9]{8}-",x)]
  print("\nURL",url,"HTTP",r.status_code,"bytes",len(r.content),"title",soup.title.get_text(" ",strip=True) if soup.title else "")
  print("script links",len(sc),"unique",len(set(sc)),"samples",list(dict.fromkeys(sc))[:8])
  print("profile links",len([x for x in anchors if "/u/" in x]),"samples",list(dict.fromkeys(x for x in anchors if "/u/" in x))[:6])
  print("pagination",list(dict.fromkeys(x for x in anchors if "page" in x))[:8])
  for pat in ("published-scripts","script_type","scriptId","scripts_list","publishedScripts","userId","pagination","__NEXT_DATA__","/script/"):
   print("TAG",pat,"COUNT",r.text.count(pat))
  print("profile_dom",[(n, len(soup.select(n))) for n in ("main","article","a[href*=script]","[data-name]")])
 except Exception as e:print("ERROR",url,repr(e))
