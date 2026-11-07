#!/usr/bin/env python3
"""TradingView public Strategy-only listing crawler. Archive first; classify later."""
import argparse,csv,datetime as dt,json,re,time,urllib.parse,urllib.robotparser,zipfile
from pathlib import Path
import requests
from bs4 import BeautifulSoup
BASE="https://www.tradingview.com"
UA="StockAutomationCatalog/1.0 (public descriptions only)"
TYPES=("strategies",)
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def clean(s):return re.sub(r"\s+"," ",s or "").strip()
def canonical(href):
    x=urllib.parse.urlparse(urllib.parse.urljoin(BASE,href))
    if x.netloc not in ("www.tradingview.com","tradingview.com","kr.tradingview.com"):return
    m=re.match(r"/script/([A-Za-z0-9]{6,})-([^/?#]+)/?",x.path)
    if m:return BASE+"/script/"+m[1]+"-"+m[2]+"/"
def listurl(kind,page):
    return BASE+("/scripts/" if page==1 else f"/scripts/page-{page}/")+("" if kind=="all" else "?script_type="+kind)
def soupify(html):
    s=BeautifulSoup(html,"html.parser")
    for x in s(["script","style","noscript","svg"]):x.decompose()
    return s
def parse_listing(html,kind,page):
    s=soupify(html);found={}
    for a in s.select('a[href*="/script/"]'):
        url=canonical(a.get("href",""))
        if not url:continue
        card=a.find_parent(["article","li"]) or a.parent
        title=clean(a.get_text(" ",strip=True))[:400]
        desc=clean(card.get_text(" ",strip=True) if card else "")[:30000]
        if not title and not desc:continue
        old=found.get(url)
        if old is None or len(desc)>len(old["listing_description"]):
            found[url]={"url":url,"listing_type":kind,"listing_page":page,"listing_title":title,"listing_description":desc}
    return list(found.values())
def parse_detail(html):
    s=soupify(html)
    title=clean(s.h1.get_text(" ",strip=True)) if s.h1 else ""
    if not title:
        m=s.find("meta",property="og:title");title=clean(m.get("content","")) if m else ""
    candidates=[clean(x.get_text("\n",strip=True)) for selector in ('[data-name="script-description"]','article','main') for x in s.select(selector)[:1]]
    description=max(candidates,key=len) if candidates else ""
    if not description:
        m=s.find("meta",attrs={"name":"description"});description=clean(m.get("content","")) if m else ""
    authors=[clean(a.get_text(" ",strip=True)) for a in s.select('a[href^="/u/"]')]
    return {"title":title,"description":description[:250000],"author":next((x for x in authors if x),"" )}
def savejsonl(path,rows):
    with open(path,"w",encoding="utf-8") as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+"\n")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--max-pages",type=int,default=300)
    p.add_argument("--delay",type=float,default=2.5)
    p.add_argument("--output",default="tradingview_catalog_output")
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    robots=urllib.robotparser.RobotFileParser(BASE+"/robots.txt")
    robots_ok=True
    try:robots.read()
    except Exception:robots_ok=False
    s=requests.Session();s.headers.update({"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"})
    errors=[];listpages=[];found={};blocked=False
    def fetch(url):
        nonlocal blocked
        if blocked:return None,None,"previous_access_block"
        if not robots_ok:return None,None,"robots_unavailable"
        if not robots.can_fetch(UA,url):return None,None,"robots_disallowed"
        time.sleep(max(1,a.delay))
        try:
            r=s.get(url,timeout=30)
            if r.status_code in (401,403,429):blocked=True
            if r.status_code!=200:return r.status_code,None,"http_"+str(r.status_code)
            if "html" not in r.headers.get("Content-Type","text/html"):return 200,None,"not_html"
            return 200,r.text,""
        except requests.RequestException as e:return None,None,str(e)
    for kind in TYPES:
        blank=0
        for page in range(1,a.max_pages+1):
            url=listurl(kind,page);code,html,error=fetch(url)
            rows=parse_listing(html,kind,page) if html else [];new=0
            for r in rows:
                if r["url"] not in found:found[r["url"]]=r;new+=1
            listpages.append(dict(url=url,kind=kind,page=page,status=code,count=len(rows),new=new,error=error))
            if error:errors.append(dict(stage="list",url=url,error=error))
            print("LIST",kind,page,code,len(rows),new,error,flush=True)
            blank=blank+1 if not new else 0
            if blank>=2 or blocked or error in ("robots_disallowed","robots_unavailable"):break
        if blocked:break
    records=list(found.values());savejsonl(out/"listing_discovery.jsonl",records)
    details=[]
    for r in records:
        code,html,error=fetch(r["url"]);row={**r,"script_id":r["url"].split("/")[4].split("-",1)[0],
             "slug":r["url"].split("/")[4].split("-",1)[1],"title":"","author":"","description":"",
             "status":code,"fetched_at":now(),"error":error}
        if html:row.update(parse_detail(html))
        if error:errors.append(dict(stage="detail",url=r["url"],error=error))
        details.append(row)
        if len(details)%50==0:print("DETAIL",len(details),"/",len(records),flush=True)
        if blocked:break
    savejsonl(out/"scripts_with_descriptions.jsonl",details)
    with open(out/"scripts_with_descriptions.csv","w",newline="",encoding="utf-8-sig") as f:
        fields=["url","script_id","slug","listing_type","listing_page","listing_title","listing_description","title","author","description","status","fetched_at","error"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(details)
    savejsonl(out/"listing_pages.jsonl",listpages);savejsonl(out/"errors.jsonl",errors)
    m=dict(created_at=now(),source=BASE+"/scripts/?script_type=strategies",types=TYPES,max_pages=a.max_pages,
           discovered_unique=len(records),details_attempted=len(details),
           detail_descriptions=sum(bool(x["description"]) for x in details),
           listing_pages=len(listpages),errors=len(errors),blocked=blocked,
           coverage="PARTIAL_NOT_PROVEN_COMPLETE",classification_performed=False,
           note="Strategy-only listing traversal; no keyword filters or detail-count cap. Public page limits and access failures are tracked; full coverage not asserted.")
    (out/"manifest.json").write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding="utf-8")
    (out/"README.md").write_text("# TradingView 공개 Strategy 전용 원문 수집\n\nStrategy 유형 페이지만 순회하고 해당 목록에 등장한 스크립트의 상세 페이지를 **발견한 만큼 전부** 조회합니다. Indicator와 Library 별도 수집은 하지 않습니다.\n\n키워드 검색/사전 분류를 사용하지 않습니다. 페이지 제한 도달 또는 공개 목록 접근 제한 때문에 전수 완료는 증명되지 않았습니다.\n\n원본 URL, 작성자, 설명과 각 호출의 상태는 csv/jsonl 및 manifest에 기록됩니다.\n",encoding="utf-8")
    with zipfile.ZipFile(out/"tradingview_catalog_raw.zip","w",zipfile.ZIP_DEFLATED) as z:
        for x in out.iterdir():
            if x.is_file() and x.name!="tradingview_catalog_raw.zip":z.write(x,x.name)
    print("MANIFEST",json.dumps(m,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
