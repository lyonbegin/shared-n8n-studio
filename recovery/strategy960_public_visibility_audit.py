#!/usr/bin/env python3
"""Audit all 960 restricted Strategy publications with ordinary public GET only.

Never request Pine source, private APIs, user credentials, cookies, gated
content, or reverse-engineer code. Public author-provided GitHub links are
UNVERIFIED references, not identical source claims.
"""
import argparse,csv,html,json,re,time,urllib.request,urllib.error
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
HEADERS={
  "User-Agent":"Mozilla/5.0 (compatible; StockAutomation-PublicMetadataAudit/1.0)",
  "Accept":"text/html,application/xhtml+xml",
  "Accept-Language":"en-US,en;q=0.9"
}
OUTPUT_FIELDS=["script_id","title","tradingview_url","catalog_visibility","source_code_visibility",
               "public_page_http","page_title","script_id_present","paid_space_text_present",
               "source_code_retrieved","independently_published_code_verified","author_public_github_links_unverified",
               "current_visibility_verified","public_page_error"]
def parse_links(page):
    raw=[]
    for url in re.findall(r'(?:https?:)?(?:\\?/\\?/|\/\/)github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^\s"<>&\\]{0,130})?',page,re.I):
        clean=html.unescape(url).replace("\\/","/").strip(')"\\')
        if clean.startswith("//"):clean="https:"+clean
        parsed=urlparse(clean)
        if parsed.hostname=="github.com" and len(parsed.path.split("/"))>=3:
            raw.append(clean[:240])
    return list(dict.fromkeys(raw))[:10]
def examine(row):
    expected="PROTECTED" if row["original_access"]=="2" else "INVITE_ONLY"
    sid=row["script_id"]
    url=row.get("tradingview_url") or f"https://www.tradingview.com/script/{sid}/"
    item={
      "script_id":sid,"title":row.get("script_title",""),
      "tradingview_url":url,"catalog_visibility":expected,
      "source_code_visibility":"AUTHOR_ONLY_PER_TRADINGVIEW_DOCUMENTATION",
      "public_page_http":"","page_title":"","script_id_present":"False",
      "paid_space_text_present":"False","source_code_retrieved":"False",
      "independently_published_code_verified":"False",
      "author_public_github_links_unverified":"",
      "current_visibility_verified":"NO_REQUIRES_CANONICAL_AUTHOR_METADATA",
      "public_page_error":""
    }
    if not url.startswith("https://www.tradingview.com/script/"+sid):
        item["public_page_error"]="URL_MISMATCH_CATALOG_ID"
        return item
    try:
        req=urllib.request.Request(url,headers=HEADERS)
        with urllib.request.urlopen(req,timeout=20) as response:
            item["public_page_http"]=str(response.status)
            raw=response.read(3600001)
            if len(raw)>3600000:
                item["public_page_error"]="PAGE_EXCEEDS_3_6MB"
                return item
        page=raw.decode("utf-8","replace")
        item["script_id_present"]=str(sid in page)
        mt=re.search(r'<meta\s+[^>]*property=["\x27]og:title["\x27][^>]*content=["\x27]([^"\x27]{1,220})',page,re.I)
        if mt:item["page_title"]=html.unescape(mt.group(1))
        else:
            title=re.search(r'<title>([^<]{1,220})</title>',page,re.I)
            if title:item["page_title"]=html.unescape(title.group(1))
        item["paid_space_text_present"]=str(bool(re.search(r'Available in Paid Space|paid space|invite.only',page,re.I)))
        links=parse_links(page)
        item["author_public_github_links_unverified"]=" | ".join(links)
    except urllib.error.HTTPError as exc:
        item["public_page_http"]=str(exc.code)
        item["public_page_error"]="HTTP_"+str(exc.code)
    except Exception as exc:
        item["public_page_error"]=type(exc).__name__+":"+str(exc)[:120]
    return item
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--shard",type=int,default=0)
    ap.add_argument("--shards",type=int,default=4)
    ap.add_argument("--delay",type=float,default=0.5)
    args=ap.parse_args()
    with open(args.input,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=4428 or len(set(r["script_id"] for r in rows))!=4428:
        raise ValueError("BAD_CATALOG_4428")
    selected=[r for r in rows if r["original_access"] in ("2","3")]
    if len(selected)!=960 or Counter(r["original_access"] for r in selected)!={"2":452,"3":508}:
        raise ValueError("BAD_RESTRICTED_SET_EXPECTED_452_508")
    batch=[r for i,r in enumerate(selected) if i%args.shards==args.shard]
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,row in enumerate(batch,1):
        results.append(examine(row))
        if i%40==0 or i==len(batch):
            print("AUDIT_PROGRESS",args.shard,i,len(batch),flush=True)
        time.sleep(max(0.2,args.delay))
    with (out/"public_visibility_audit.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,OUTPUT_FIELDS);w.writeheader();w.writerows(results)
    summary={"shard":args.shard,"items":len(results),
        "catalog_types":dict(Counter(x["catalog_visibility"] for x in results)),
        "page_http":dict(Counter(x["public_page_http"] for x in results)),
        "source_code_retrieved":0,"source_code_public_fetch_attempted":False,
        "classification_limitation":"Public HTML and original access codes; author-only source cannot be fetched",
        "github_links_are_only_unverified_public_navigation_evidence":True}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("AUDIT_FINAL",json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
