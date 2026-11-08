#!/usr/bin/env python3
"""Continual public Strategy+Indicator discovery: listing -> authors -> merge.

Uses the observed TradingView published-scripts response:
  /api/v1/scripts/?page=N&per_page=24&by=AUTHOR&q=
The catalog is deliberately limited to Strategy and Indicator as independent
items. Library entries are counted only as optional dependency references.
"""
import argparse
import csv
import datetime as dt
import json
import re
import time
import urllib.parse
import zipfile
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HOST = "https://www.tradingview.com"
KINDS = ("strategy", "indicator")
TOPIC_PATHS = ("xauusd", "indicators", "scalp", "pinescript", "heatmap", "gold",
               "strategy", "smart-money-concepts", "reversal", "vwap",
               "supertrend", "scalping", "nq1!", "ionqstock",
               "elliottwaves", "zigzag", "weeklypivots")
ID_PATTERN = re.compile(r"/script/([a-zA-Z0-9]{8})(?:[-/?#]|$)")
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockAutomationCatalog/2.0)",
                   "Accept-Language": "en-US,en;q=0.9"}


def load_lines(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_lines(path, items):
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def script_id(url):
    match = ID_PATTERN.search(url or "")
    return match.group(1) if match else None


def normalized_type(value):
    v = str(value or "").casefold()
    if v in ("indicator", "indicators"):
        return "indicator"
    if v in ("strategy", "strategies"):
        return "strategy"
    if v in ("library", "libraries"):
        return "library"
    return "unknown"


def from_api(x):
    user = x.get("user") or {}
    url = x.get("chart_url") or ""
    return {
        "id": script_id(url), "url": url,
        "title": x.get("name") or "",
        "type": normalized_type(x.get("script_type")),
        "author": user.get("username") or "",
        "description_preview": x.get("description") or "",
        "created_at": x.get("created_at"),
        "updated_at": x.get("updated_at"),
        "access": x.get("script_access"),
        "source": "author_api",
    }


def from_baseline_strategy(x):
    url = x.get("url") or ""
    return {
        "id": x.get("script_id") or script_id(url),
        "url": url,
        "title": x.get("title") or x.get("listing_title") or "",
        "type": "strategy",
        "author": x.get("author") or "",
        "description_preview": x.get("listing_description") or "",
        "created_at": None, "updated_at": None,
        "access": None, "source": "baseline_strategy",
    }


def fetch(session, url, delay, params=None):
    time.sleep(max(0.8, delay))
    r = session.get(url, params=params, timeout=40)
    r.raise_for_status()
    return r


def listing_scan(session, category, page_limit, delay, errors):
    discovered = {}
    scanned = []
    repeated = 0
    for page in range(1, page_limit + 1):
        if category.startswith("topic:"):
            slug = category.split(":", 1)[1]
            if slug not in TOPIC_PATHS:
                raise ValueError("Unsupported topic: " + slug)
            path = "/scripts/%s/" % slug if page == 1 else "/scripts/%s/page-%d/" % (slug, page)
            params = None
        elif category in ("editors-picks", "followed-authors"):
            path = "/scripts/%s/" % category if page == 1 else "/scripts/%s/page-%d/" % (category, page)
            params = None
        else:
            path = "/scripts/" if page == 1 else "/scripts/page-%d/" % page
            params = {"script_type": category} if category != "all" else None
        url = HOST + path
        try:
            response = fetch(session, url, delay, params=params)
            # 'followed-authors' is personalized. Anonymous users are redirected
            # to /accounts/signin/; never mislabel the login page or a redirected
            # editors-picks page as followed authors content.
            final_path = urllib.parse.urlparse(response.url).path
            if category == "followed-authors" and not final_path.startswith("/scripts/followed-authors/"):
                scanned.append({"category": category, "page": page, "status": "requires_authentication",
                                "final_url": response.url, "new_ids": 0})
                print("CHANNEL_LOGIN_REQUIRED", category, response.url, flush=True)
                break
            if category == "editors-picks" and not final_path.startswith("/scripts/editors-picks/"):
                raise RuntimeError("Editors Picks redirected unexpectedly to " + response.url)
            if category.startswith("topic:"):
                slug = category.split(":", 1)[1]
                required = "/scripts/" + slug + "/"
                if not urllib.parse.unquote(final_path).lower().startswith(required.lower()):
                    raise RuntimeError("Topic page redirected unexpectedly: " + response.url)
            soup = BeautifulSoup(response.text, "html.parser")
            if category.startswith("topic:") and page == 1 and not soup.select("article"):
                scanned.append({"category":category, "page":page, "new_ids":0, "status":"empty_topic"})
                print("TOPIC_EMPTY", category, response.url, flush=True)
                break
            new = 0
            for article in soup.select("article"):
                a = article.select_one('a[data-qa-id="ui-lib-card-link-title"][href*="/script/"]')
                if not a:
                    continue
                uri = urllib.parse.urljoin(HOST, a.get("href") or "")
                sid = script_id(uri)
                if not sid:
                    continue
                # The badge is the site's actual published type. Do not infer type from title.
                badge = article.select_one('[class*="badge"] [class*="content"]')
                typ = normalized_type(badge.get_text(" ", strip=True) if badge else "")
                author_link = article.select_one('address a[href*="/u/"]')
                author = ""
                if author_link:
                    match = re.search(r"/u/([^/?#]+)/?", author_link.get("href", ""))
                    if match:
                        author = urllib.parse.unquote(match.group(1))
                desc = article.select_one('a[data-qa-id="ui-lib-card-link-paragraph"]')
                item = {
                    "id": sid, "url": uri.split("#")[0], "title": a.get_text(" ", strip=True),
                    "type": typ, "author": author,
                    "description_preview": desc.get_text(" ", strip=True) if desc else "",
                    "created_at": None, "updated_at": None, "access": None,
                    "source": "listing_" + category,
                }
                if sid not in discovered:
                    discovered[sid] = item
                    new += 1
            scanned.append({"category": category, "page": page, "new_ids": new})
            print("LIST", category, page, "new", new, "total", len(discovered), flush=True)
            repeated = repeated + 1 if new == 0 else 0
            if repeated >= 2:
                break
        except requests.HTTPError as exc:
            if page > 1 and exc.response is not None and exc.response.status_code == 404:
                scanned.append({"category": category, "page": page, "status": "end_404", "new_ids": 0})
                print("LIST_END_404", category, page, flush=True)
                break
            errors.append({"stage": "listing", "category": category, "page": page, "error": repr(exc)})
            print("LIST_ERROR", category, page, repr(exc), flush=True)
            break
        except Exception as exc:
            errors.append({"stage": "listing", "category": category, "page": page, "error": repr(exc)})
            print("LIST_ERROR", category, page, repr(exc), flush=True)
            break
    return list(discovered.values()), scanned


def gather_author(session, author, delay):
    fetched = []
    page = 1
    expected = None
    while True:
        obj = fetch(session, HOST + "/api/v1/scripts/", delay, params={
            "page": page, "per_page": 24, "by": author, "q": ""
        }).json()
        if not isinstance(obj, dict) or not isinstance(obj.get("results"), list):
            raise ValueError("invalid author API structure")
        if expected is None:
            expected = obj.get("count")
        fetched.extend(obj["results"])
        nxt = obj.get("next")
        print("AUTHOR_PAGE", author, page, len(obj["results"]), "expected", expected, flush=True)
        if not nxt:
            break
        page += 1
        if page > 1000:
            raise RuntimeError("author pagination safety bound")
    ids = [x.get("id") for x in fetched]
    good = isinstance(expected, int) and expected == len(ids) and len(set(ids)) == len(ids)
    return fetched, {"author": author, "expected": expected, "received": len(ids),
                     "pages": page, "complete": good}


def merge_record(current, newer):
    if not current:
        return newer
    # Prefer actual API type to unverified HTML type.
    if newer.get("source") == "author_api":
        result = {**current, **newer}
        if not result.get("description_preview"):
            result["description_preview"] = current.get("description_preview") or ""
        return result
    for key in ("title", "author", "url", "description_preview"):
        if not current.get(key) and newer.get(key):
            current[key] = newer[key]
    if current.get("type") not in KINDS and newer.get("type") in KINDS:
        current["type"] = newer["type"]
    return current



# The recursive stage is deliberately distinct from the old scheduled/partial main.
# Each author page can lead to references to further authors, which are enqueued.
# Author-only pages normally contain the author's own scripts; the community
# feed and explicit /u/<username> links are therefore essential extra edges.
from collections import deque
import os
import re as _re

LINKED_AUTHOR = _re.compile(r"(?:https?://(?:www\.)?tradingview\.com)?/u/([A-Za-z0-9_-]{2,64})/?", _re.I)
MENTIONED_AUTHOR = _re.compile(r"(?<!\w)@([A-Za-z][A-Za-z0-9_-]{2,40})\b")
EXCLUDED_AUTHORS = {"tradingview", "telegram", "youtube", "gmail", "discord", "instagram", "facebook", "twitter", "everyone"}

def linked_authors(text, mentions=False):
    refs=set(LINKED_AUTHOR.findall(str(text or "")))
    if mentions:
        refs.update(MENTIONED_AUTHOR.findall(str(text or "")))
    return {x for x in refs if x.lower() not in EXCLUDED_AUTHORS}

def save_progress(out, stored, processed, waiting, reports, errors, discovered, feed_pages):
    records=sorted((v for v in stored.values() if v.get("type") in KINDS and v.get("id")),key=lambda x:(x["type"], x["id"]))
    write_lines(out/"master.jsonl",records)
    for kind,name in (("strategy","strategies"),("indicator","indicators")):
        subset=[x for x in records if x["type"]==kind]
        write_lines(out/(name+".jsonl"),subset)
        columns=["id","title","url","type","author","description_preview","created_at","updated_at","access","source"]
        with open(out/(name+".csv"),"w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore")
            writer.writeheader();writer.writerows(subset)
    write_lines(out/"author_coverage.jsonl",reports)
    write_lines(out/"errors.jsonl",errors)
    write_lines(out/"author_discovery_edges.jsonl",discovered)
    write_lines(out/"listing_pages.jsonl",feed_pages)
    (out/"frontier.json").write_text(json.dumps({
      "processed":sorted(processed),"pending":list(waiting),
      "updated_at":dt.datetime.now(dt.timezone.utc).isoformat()
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return records

def recursive_run(args,session=None):
    session=session or requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    stored={}
    for row in load_lines(Path(args.baseline)):
        item=from_baseline_strategy(row)
        if item["id"]:stored[item["id"]]=merge_record(stored.get(item["id"]),item)
    for file in (args.author_baseline,args.latest):
        for item in load_lines(Path(file)):
            sid=item.get("id")
            if sid and item.get("type") in KINDS:
                stored[sid]=merge_record(stored.get(sid),item)
    original_strategy_ids={key for key,x in stored.items() if x.get("type")=="strategy"}
    original_indicator_ids={key for key,x in stored.items() if x.get("type")=="indicator"}
    previous_reports=load_lines(Path(args.processed_authors_file))
    processed={x["author"] for x in previous_reports if x.get("complete") is True and x.get("author")}
    completed_at_start=len(processed)
    waiting=deque();queued=set()
    discovered=[];reports=list(previous_reports);errors=[];feed_pages=[]
    def enqueue(author,source):
        if not author or not _re.fullmatch(r"[A-Za-z0-9_-]{2,64}",str(author)):
            return False
        author=str(author)
        if author.lower() in EXCLUDED_AUTHORS:return False
        if author not in processed and author not in queued:
            waiting.append(author);queued.add(author)
            discovered.append({"author":author,"source":source,"new":True})
            return True
        return False
    for item in stored.values():
        enqueue(item.get("author"),"existing_master")
        for name in linked_authors(item.get("description_preview"),args.mentions):
            enqueue(name,"existing_script_reference")
    if not args.skip_feeds:
        for kind in ("strategies","indicators","all","editors-picks","followed-authors", *(("topic:" + slug) for slug in TOPIC_PATHS)):
            found,pages=listing_scan(session,kind,args.page_limit,args.delay,errors)
            feed_pages.extend(pages)
            for item in found:
                sid=item.get("id")
                if sid and item.get("type") in KINDS:
                    stored[sid]=merge_record(stored.get(sid),item)
                enqueue(item.get("author"),"public_"+kind+"_feed")
                for name in linked_authors(item.get("description_preview"),args.mentions):
                    enqueue(name,"public_"+kind+"_description")
    start=time.monotonic();done_since_checkpoint=0
    while waiting:
        if args.max_runtime and time.monotonic()-start>args.max_runtime:
            print("RUN_TIME_BOUNDARY_NOT_EXHAUSTED",len(waiting),flush=True)
            break
        name=waiting.popleft();queued.discard(name)
        if name in processed:continue
        last_error=None;items=[];report=None
        for attempt in range(1,4):
            try:
                items,report=gather_author(session,name,args.delay)
                if not report.get("complete"):raise ValueError("Author count mismatch")
                last_error=None;break
            except Exception as exc:
                last_error=str(exc)
                print("RETRY_AUTHOR",name,attempt,last_error,flush=True)
                time.sleep(min(15,attempt*3))
        if last_error:
            errors.append({"stage":"author","author":name,"error":last_error})
            reports.append({"author":name,"complete":False,"error":last_error})
        else:
            processed.add(name);reports.append(report)
            for raw in items:
                item=from_api(raw)
                sid=item.get("id")
                if sid and item.get("type") in KINDS:
                    stored[sid]=merge_record(stored.get(sid),item)
                enqueue(item.get("author"),"api_publisher")
                for ref in linked_authors(item.get("description_preview"),args.mentions):
                    enqueue(ref,"api_description_reference")
        done_since_checkpoint+=1
        if done_since_checkpoint>=args.checkpoint_every:
            save_progress(out,stored,processed,waiting,reports,errors,discovered,feed_pages)
            done_since_checkpoint=0
            print("CHECKPOINT",len(processed),"PENDING",len(waiting),"ERRORS",len(errors),flush=True)
        if args.test_authors and len(processed)-completed_at_start>=args.test_authors:
            break
    records=save_progress(out,stored,processed,waiting,reports,errors,discovered,feed_pages)
    kinds=Counter(x["type"] for x in records)
    state=("INCOMPLETE_ERRORS" if errors else
           "INCOMPLETE_FRONTIER" if waiting else "FRONTIER_EXHAUSTED")
    manifest={
      "finished_at":dt.datetime.now(dt.timezone.utc).isoformat(),
      "state":state,
      "state_definition":"All discovered author references processed; not proof of whole TradingView population",
      "strategies":kinds["strategy"],"indicators":kinds["indicator"],
      "new_strategies":len({x["id"] for x in records if x["type"]=="strategy"}-original_strategy_ids),
      "new_indicators":len({x["id"] for x in records if x["type"]=="indicator"}-original_indicator_ids),
      "authors_processed":len(processed),"authors_processed_this_run":len(processed)-completed_at_start,
      "authors_processed_from_prior_runs":completed_at_start,
      "authors_discovered":len({r["author"] for r in discovered}),
      "pending_authors":len(waiting),"authors_failed":len({e["author"] for e in errors if e.get("stage")=="author"}),
      "error_count":len(errors),"feed_pages":len(feed_pages),
      "followed_authors_requires_login":any(x.get("status")=="requires_authentication" for x in feed_pages),
      "source_channels":sorted({x.get("category") for x in feed_pages}),
      "topics_requested":list(TOPIC_PATHS),
      "topic_page_counts":{slug:sum(x.get("category") == "topic:" + slug for x in feed_pages)
                           for slug in TOPIC_PATHS},
      "descriptions":"List previews only for newly found items; full descriptions not fetched",
      "notification":"GitHub native workflow_run completion issue notification"
    }
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"README.md").write_text(
      "# Strategy / Indicator 신규 제작자 재귀 수집\n\n"
      "기존 11000개 → 제작자 조회 → 스크립트에서 새 제작자 발견 → 대기열 추가를 반복하여 대기열 소진 시 종료합니다.\n"
      "Strategy와 Indicator는 별도 CSV/JSONL로 보관합니다. Library는 수집 결과에서 제외합니다.\n"
      "공개 피드 및 자료에 명시적으로 연결된 제작자만 발견하므로, 대기열 소진과 TradingView 전수 확보는 동일하지 않습니다.\n"
      "새로운 스크립트의 설명은 상세 설명이 아니라 목록 요약입니다.\n",encoding="utf-8")
    with zipfile.ZipFile(out/"recursive_catalog.zip","w",zipfile.ZIP_DEFLATED) as z:
        for f in out.iterdir():
            if f.is_file() and f.name!="recursive_catalog.zip":z.write(f,f.name)
    print("RECURSIVE_MANIFEST",json.dumps(manifest,ensure_ascii=False),flush=True)
    return manifest

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline",default="source_catalog/scripts_with_descriptions.jsonl")
    p.add_argument("--author-baseline",default="previous_authors/all.jsonl")
    p.add_argument("--latest",default="previous_cycle/master.jsonl")
    p.add_argument("--page-limit",type=int,default=200)
    p.add_argument("--processed-authors-file",default="previous_recursive/author_coverage.jsonl")
    p.add_argument("--delay",type=float,default=1.5)
    p.add_argument("--checkpoint-every",type=int,default=50)
    p.add_argument("--max-runtime",type=int,default=18000)
    p.add_argument("--test-authors",type=int,default=0)
    p.add_argument("--mentions",action="store_true")
    p.add_argument("--skip-feeds",action="store_true")
    p.add_argument("--output",default="tradingview_recursive_output")
    args=p.parse_args()
    m=recursive_run(args)
    if m["state"]!="FRONTIER_EXHAUSTED":
        raise SystemExit("Recursive collection incomplete, see manifest")

if __name__=="__main__":main()
