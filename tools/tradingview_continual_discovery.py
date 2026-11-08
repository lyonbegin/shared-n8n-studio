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
ID_PATTERN = re.compile(r"/script/([a-zA-Z0-9]{8})-")
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
        path = "/scripts/" if page == 1 else "/scripts/page-%d/" % page
        url = HOST + path
        params = {"script_type": category} if category != "all" else None
        try:
            html = fetch(session, url, delay, params=params).text
            soup = BeautifulSoup(html, "html.parser")
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", default="source_catalog/scripts_with_descriptions.jsonl")
    p.add_argument("--author-baseline", default="previous_authors/all.jsonl")
    p.add_argument("--latest", default="previous_cycle/master.jsonl")
    p.add_argument("--author-manifest", default="previous_authors/authors_coverage.jsonl")
    p.add_argument("--latest-manifest", default="previous_cycle/author_coverage.jsonl")
    p.add_argument("--page-limit", type=int, default=200)
    p.add_argument("--max-new-authors", type=int, default=5000)
    p.add_argument("--refresh-authors", type=int, default=50)
    p.add_argument("--delay", type=float, default=1.4)
    p.add_argument("--mode", choices=["smoke", "full"], default="full")
    p.add_argument("--output", default="tradingview_continual_output")
    a = p.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    stored = {}
    errors = []
    initial = load_lines(Path(a.baseline))
    prior = load_lines(Path(a.author_baseline))
    previous = load_lines(Path(a.latest))
    for row in initial:
        rec = from_baseline_strategy(row)
        if rec["id"]:
            stored[rec["id"]] = merge_record(stored.get(rec["id"]), rec)
    for row in prior + previous:
        sid = row.get("id")
        if sid:
            stored[sid] = merge_record(stored.get(sid), row)
    old_strategies = {k for k, v in stored.items() if v.get("type") == "strategy"}
    old_indicators = {k for k, v in stored.items() if v.get("type") == "indicator"}
    # Discover authors with ALL published feeds; retain only Strategy/Indicator records.
    # Libraries are not independently archived in the output master.
    page_limit = min(a.page_limit, 2) if a.mode == "smoke" else a.page_limit
    public_feed = []
    scanned = []
    for category in ("strategies", "indicators", "all"):
        data, pages = listing_scan(session, category, page_limit, a.delay, errors)
        scanned += pages
        public_feed += data
    existing_authors = {x.get("author", "") for x in stored.values() if x.get("author")}
    discovered_authors = {x.get("author", "") for x in public_feed if x.get("author")}
    candidates = sorted(discovered_authors - existing_authors)
    if a.mode == "smoke":
        candidates = candidates[:3]
        refresh = []
    else:
        candidates = candidates[:a.max_new_authors]
        old_authors = sorted(existing_authors)
        count = min(len(old_authors), max(0, a.refresh_authors))
        offset = ((dt.datetime.now(dt.timezone.utc).date() - dt.date(2026, 1, 1)).days * max(1,count)) % max(1,len(old_authors))
        refresh = [old_authors[(offset + i) % len(old_authors)] for i in range(count)]
    candidates = list(dict.fromkeys(candidates + refresh))
    print("DISCOVERED_AUTHORS", len(discovered_authors), "OLD_AUTHORS", len(existing_authors),
          "NEW_AUTHORS_IN_BATCH", len(candidates), flush=True)
    for item in public_feed:
        if item["id"] and item["type"] in KINDS:
            stored[item["id"]] = merge_record(stored.get(item["id"]), item)
    # This first phase collects newly discovered authors; pre-existing authors are
    # refreshed by the original full author workflow and can be imported as baseline.
    profile_report = []
    for index, author in enumerate(candidates):
        try:
            items, report = gather_author(session, author, a.delay)
            profile_report.append(report)
            for raw in items:
                rec = from_api(raw)
                if rec["id"] and rec["type"] in KINDS:
                    stored[rec["id"]] = merge_record(stored.get(rec["id"]), rec)
        except Exception as exc:
            errors.append({"stage": "profile", "author": author, "error": repr(exc)})
            profile_report.append({"author": author, "complete": False, "error": repr(exc)})
        if (index + 1) % 25 == 0:
            print("PROFILES_PROGRESS", index + 1, "/", len(candidates), flush=True)
    retained = sorted((v for v in stored.values() if v.get("type") in KINDS), key=lambda x: (x.get("type", ""), x.get("id", "")))
    strategies = [v for v in retained if v["type"] == "strategy"]
    indicators = [v for v in retained if v["type"] == "indicator"]
    write_lines(out / "master.jsonl", retained)
    write_lines(out / "strategies.jsonl", strategies)
    write_lines(out / "indicators.jsonl", indicators)
    write_lines(out / "author_coverage.jsonl", profile_report)
    write_lines(out / "listing_pages.jsonl", scanned)
    write_lines(out / "errors.jsonl", errors)
    columns = ["id", "title", "url", "type", "author", "description_preview", "created_at", "updated_at", "access", "source"]
    for name, items in (("strategies.csv", strategies), ("indicators.csv", indicators)):
        with (out / name).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            w.writeheader()
            w.writerows(items)
    coverage = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PARTIAL_NOT_PROVEN_EXHAUSTIVE",
        "mode": a.mode, "existing_strategy_count": len(old_strategies),
        "existing_indicator_count": len(old_indicators),
        "unique_strategies": len(strategies), "unique_indicators": len(indicators),
        "new_strategy_ids": len({x["id"] for x in strategies} - old_strategies),
        "new_indicator_ids": len({x["id"] for x in indicators} - old_indicators),
        "authors_newly_found_in_feed": len(discovered_authors - existing_authors),
        "authors_processed": len(profile_report),
        "existing_authors_refreshed": len(refresh),
        "authors_complete": sum(bool(x.get("complete")) for x in profile_report),
        "listing_pages_scanned": len(scanned), "errors": len(errors),
        "description_status": "previews_only_for_new_items; full details require separate fetch",
        "note": "No keyword search. Full completeness remains unverified due public feed caps.",
    }
    (out / "manifest.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "README.md").write_text(
        "# Strategy + Indicator continuous discovery\n\n"
        "Community listing -> new published authors -> all author pages -> ID dedupe -> export.\n"
        "Records from the previous cycle are preserved. Libraries are excluded.\n"
        "New descriptions are previews only; detailed extraction is a separate step.\n"
        "A successful run does not prove every TradingView script exists in the resulting archive.\n", encoding="utf-8")
    with zipfile.ZipFile(out / "master_catalog.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for path in out.iterdir():
            if path.is_file() and path.name != "master_catalog.zip":
                z.write(path, path.name)
    print("MANIFEST", json.dumps(coverage, ensure_ascii=False), flush=True)
    if errors and a.mode == "smoke":
        raise SystemExit("Smoke collection errors; inspect errors.jsonl")


if __name__ == "__main__":
    main()
