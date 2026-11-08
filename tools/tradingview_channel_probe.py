#!/usr/bin/env python3
"""Probe TradingView editors-picks and followed-authors HTML structure without credentials."""
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
BASE="https://www.tradingview.com"
targets=[
 "/scripts/xauusd/",
 "/scripts/indicators/",
 "/scripts/scalp/",
 "/scripts/pinescript/",
 "/scripts/heatmap/",
 "/scripts/gold/",
 "/scripts/strategy/",
 "/scripts/smart-money-concepts/",
 "/scripts/reversal/",
 "/scripts/vwap/",
 "/scripts/supertrend/",
 "/scripts/scalping/",
 "/scripts/nq1!/",
 "/scripts/ionqstock/",
 "/scripts/elliottwaves/",
 "/scripts/zigzag/",
 "/scripts/weeklypivots/",
 "/scripts/editors-picks/",
 "/scripts/xauusd/page-2/",
 "/scripts/xauusd/page-3/",
 "/scripts/indicators/page-2/",
 "/scripts/strategy/page-2/",
 "/scripts/zigzag/page-2/",
 "/scripts/weeklypivots/page-2/",
 "/scripts/ionqstock/page-2/",
 "/scripts/indicators/page-21/",
 "/scripts/indicators/page-22/",
 "/scripts/indicators/page-200/",
 "/scripts/indicators/page-201/",
 "/scripts/strategy/page-21/",
 "/scripts/strategy/page-22/",
 "/scripts/strategy/page-200/",
 "/scripts/strategy/page-201/",
 "/scripts/xauusd/page-21/",
 "/scripts/xauusd/page-22/",
 "/scripts/xauusd/page-200/",
 "/scripts/xauusd/page-201/",
 "/scripts/zigzag/page-21/",
 "/scripts/zigzag/page-22/",
 "/scripts/followed-authors/",
]
s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36","Accept-Language":"en-US,en;q=0.9"})
summary=[]
for path in targets:
 try:
  r=s.get(BASE+path,timeout=35,allow_redirects=True)
  soup=BeautifulSoup(r.text,"html.parser")
  articles=soup.select("article")
  html_links=soup.select('a[href*="/script/"]')
  author_links=soup.select('a[href*="/u/"]')
  detail=[]
  for article in articles[:4]:
   a=article.select_one('a[data-qa-id="ui-lib-card-link-title"][href*="/script/"]')
   badge=article.select_one('[class*="badge"] [class*="content"]')
   author=article.select_one('address a[href*="/u/"]')
   detail.append({"article_classes":article.get("class"),"has_title_selector":bool(a),"title":a.get_text(" ",strip=True)[:80] if a else None,"url":a.get("href") if a else None,"badge":badge.get_text(" ",strip=True)[:80] if badge else None,"author":author.get("href") if author else None,"text_head":article.get_text(" ",strip=True)[:130]})
  pagination_links=list(dict.fromkeys(a.get("href") for a in soup.select('a[href*="/page-"]') if a.get("href")))
  o={"source":path,"pagination_links":pagination_links[:20],"all_pagination_link_count":len(pagination_links),"first_script":html_links[0].get("href") if html_links else None,"last_script":html_links[-1].get("href") if html_links else None,"final_url":r.url,"status":r.status_code,"articles":len(articles),"script_anchors":len(html_links),"author_anchors":len(author_links),"canonical":soup.find("link",rel="canonical").get("href") if soup.find("link",rel="canonical") else None,"cards":detail,"first_link":[{"href":a.get("href"),"text":a.get_text(" ",strip=True)[:60]} for a in html_links[:4]]}
 except Exception as e:o={"source":path,"error":repr(e)}
 summary.append(o)
 print("PROBE",json.dumps(o,ensure_ascii=False),flush=True)
open("tradingview_channel_probe.json","w",encoding="utf-8").write(json.dumps(summary,ensure_ascii=False,indent=2))
