from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import time,re,json
u="https://www.tradingview.com/u/FuturesTeller/#published-scripts"
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=["--no-sandbox"])
 page=b.new_page(locale="en-US",viewport={"width":1280,"height":900})
 calls=[]
 def log(req):
  x=req.url
  if any(t in x for t in ("FuturesTeller","scripts","publication","profile","user/")):
   if len(calls)<80:calls.append((req.method,x[:320]))
 page.on("request",log)
 def on_response(response):
  if "/api/v1/scripts/" in response.url:
   try:
    data=response.json()
    print("API_STATUS",response.status,"API_TYPE",type(data).__name__,flush=True)
    if isinstance(data,dict):
     print("API_TOP_KEYS",list(data.keys()),flush=True)
     for key,val in data.items():
      if isinstance(val,list):
       print("API_ARRAY",key,"len",len(val),"first",json.dumps(val[0] if val else {},ensure_ascii=False)[:4500],flush=True)
      elif isinstance(val,dict): print("API_DICT",key,"keys",list(val.keys()),flush=True)
      else: print("API_FIELD",key,str(val)[:300],flush=True)
    elif isinstance(data,list):print("API_ITEMS",len(data),"first",json.dumps(data[0] if data else {},ensure_ascii=False)[:4500],flush=True)
   except Exception as e:print("API_ERR",repr(e),flush=True)
 page.on("response",on_response)
 try:
  page.goto(u,wait_until="domcontentloaded",timeout=45000)
  page.wait_for_timeout(5000)
  print("TITLE",page.title(),"CURRENT_URL",page.url)
  print("TABS",[(x.get_attribute("href"), x.inner_text()[:80]) for x in page.locator('a[href*="script"]').all()[:15]])
  print("SCRIPT_LINKS",page.locator('a[href*="/script/"]').count())
  print("PAGE_TEXT",page.locator("main").first.inner_text()[:1800] if page.locator("main").count() else page.locator("body").inner_text()[:1800])
  for i in range(3):
   page.mouse.wheel(0,2500);page.wait_for_timeout(1200)
  print("AFTER_SCROLL_LINKS",page.locator('a[href*="/script/"]').count())
  print("REQUESTS",json.dumps(calls[-45:],ensure_ascii=False))
  page.screenshot(path="profile_screenshot.png",full_page=False)
 except Exception as e:print("ERROR",repr(e))
 finally:b.close()
