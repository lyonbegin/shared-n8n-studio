#!/usr/bin/env python3
"""Read a pinned public Pine mirror against the user's Strategy-only catalog.

NEVER assume a TradingView script page supplies source. Never fabricate Pine.
Source identity with the current TradingView revision is NOT verified by this
mirror and publication does not automatically grant republishing rights.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "venkatalokeshanne/trading_strategies_indicators"
REV = "a9a6f4a9145de22bacacc24b827fb4095a3a425c"
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/{REV}?recursive=1"
PINNED_RAW = f"https://raw.githubusercontent.com/{REPO}/{REV}/"
UA = "stock-automation-strategy-source-verifier/1.0"
FILE_RE = re.compile(r"^TradingView/strategies/([A-Za-z0-9]{8})(?:[-.][^/]*)?\.pine$", re.I)
VERSION_RE = re.compile(r"(?m)^\s*//@version\s*=\s*([1-6])\b")
STRATEGY_RE = re.compile(r"(?m)^\s*strategy\s*\(")
MAX_BYTES = 512 * 1024
HEADERS = {"User-Agent": UA, "Accept": "application/vnd.github+json"}


def get_bytes(url: str, retries=4):
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=50) as response:
                body = response.read(MAX_BYTES+1 if "/raw/" in url else 4000000)
                return response.status, body
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if attempt == retries - 1:
                raise
            time.sleep(min(12, 2 ** attempt))
    raise RuntimeError("unreachable")


def get_tree():
    status, raw = get_bytes(TREE_URL)
    assert status == 200
    tree = json.loads(raw)["tree"]
    entries = {}
    for f in tree:
        m = FILE_RE.match(f.get("path", ""))
        if not m:
            continue
        sid = m.group(1)
        if f.get("type") == "blob":
            entries.setdefault(sid, []).append(f["path"])
    return entries


def read_catalog(path: Path):
    if path.suffix == '.zip':
        import zipfile
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith('strategies.jsonl')]
            if len(names) != 1:
                raise ValueError('ZIP_MISSING_STRATEGIES_JSONL')
            rows = [json.loads(line) for line in z.open(names[0]) if line.strip()]
    else:
        rows = [json.loads(line) for line in path.open(encoding='utf-8') if line.strip()]
    if len(rows) != 4428 or len({r.get('id') for r in rows}) != 4428 or any(r.get('type') != 'strategy' for r in rows):
        raise ValueError('SOURCE_CATALOG_NOT_EXACTLY_4428_STRATEGIES')
    return rows


def probable_license(code: str):
    preface = code[:3500].lower()
    if 'mozilla public license' in preface or 'mpl-2.0' in preface:
        return 'MPL-2.0_MENTIONED_CHECK_TERMS'
    if 'attribution-noncommercial-sharealike' in preface or 'by-nc-sa' in preface:
        return 'CC_BY_NC_SA_MENTIONED_CHECK_TERMS'
    if 'creative commons' in preface:
        return 'CC_LICENSE_MENTIONED_CHECK_TERMS'
    if 'all rights reserved' in preface:
        return 'ALL_RIGHTS_RESERVED_REVIEW'
    return 'UNSPECIFIED_CHECK_PUBLICATION_RIGHTS'


def collect(row, paths, output: Path):
    sid = row['id']
    obj = {
        'script_id': sid,
        'script_title': row.get('title') or '',
        'tradingview_url': row.get('url') or '',
        'author': row.get('author') or '',
        'description_preview': row.get('description_preview') or '',
        'original_type': 'strategy',
        'original_access': row.get('access'),
        'created_at': row.get('created_at'),
        'source_state': 'NO_PINNED_PUBLIC_PINE_FOUND',
        'pine_mirror_url': '',
        'local_pine_path': '',
        'pine_sha256': '',
        'pine_bytes': 0,
        'pine_lines': 0,
        'pine_version': '',
        'declared_strategy': False,
        'rights_state': 'PENDING_REVIEW',
        'source_identity_verified_against_tv': False,
        'source_provenance': f'public GitHub mirror {REPO}@{REV}',
        'error': '',
        'wf01_n11_n15_n16_persisted': False,
        'wf01_error': '',
    }
    if not paths:
        return obj
    if len(paths) != 1:
        obj['source_state'] = 'AMBIGUOUS_MIRROR_PATHS'
        obj['error'] = ';'.join(paths)[:500]
        return obj
    path = paths[0]
    url = PINNED_RAW+quote(path,safe='/-._')
    obj['pine_mirror_url'] = url
    try:
        _, raw = get_bytes(url)
        if not raw or len(raw) > MAX_BYTES:
            obj['source_state']='EMPTY_OR_TOO_LARGE'
            return obj
        code = raw.decode('utf-8-sig')
        vers = VERSION_RE.search(code)
        if not vers or not STRATEGY_RE.search(code):
            obj['source_state'] = 'SOURCE_HEADER_MISMATCH'
            obj['error'] = 'strategy() or Pine version header not found'
            return obj
        loc=output/'pine_sources'/f'{sid}.pine'
        loc.parent.mkdir(parents=True,exist_ok=True)
        loc.write_bytes(raw)
        obj.update(source_state='PINE_RETRIEVED_FROM_PINNED_MIRROR',
                   local_pine_path=f'pine_sources/{sid}.pine',
                   pine_sha256=hashlib.sha256(raw).hexdigest(),
                   pine_bytes=len(raw),
                   pine_lines=len(code.splitlines()),
                   pine_version=vers.group(1),
                   declared_strategy=True,
                   rights_state=probable_license(code))
    except Exception as exc:
        obj['source_state']='MIRROR_FETCH_FAILED'
        obj['error']=type(exc).__name__+':'+str(exc)[:300]
    return obj


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--catalog', required=True)
    p.add_argument('--output',default='strategy_4428_result')
    p.add_argument('--limit',type=int,default=0,help='0 = all 4428')
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--wf01-adapter',default='',help='n8n/editor-adapter path from Railway source branch')
    args=p.parse_args()
    rows=read_catalog(Path(args.catalog))
    if args.limit: rows=rows[:args.limit]
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    mirror=get_tree()
    print(json.dumps({'stage':'mirror_index','files':sum(len(v) for v in mirror.values()),'input_strategies':len(rows)},ensure_ascii=False),flush=True)
    matches=sum(r['id'] in mirror for r in rows)
    print('EXACT_ID_MIRROR_CANDIDATES',matches,flush=True)
    results={}
    with ThreadPoolExecutor(max_workers=max(1,min(6,args.workers))) as pool:
        tasks={pool.submit(collect,r,mirror.get(r['id'],[]),out):r['id'] for r in rows}
        for i,task in enumerate(as_completed(tasks),1):
            result=task.result()
            results[result['script_id']]=result
            if i%100==0 or i==len(tasks):
                print('PROGRESS',i,'/',len(tasks),flush=True)
    ordered=[results[r['id']] for r in rows]
    if args.wf01_adapter:
        sys.path.insert(0, args.wf01_adapter)
        from investment_node_adapter import execute_node11, execute_node15, execute_node16
        os.environ['STUDIO_DB_PATH']=str((out/'wf01_sources.sqlite').resolve())
        for i, item in enumerate(ordered, 1):
            if item['source_state']!='PINE_RETRIEVED_FROM_PINNED_MIRROR':
                continue
            try:
                pine=(out/item['local_pine_path']).read_text(encoding='utf-8-sig')
                cand={
                    'kind':'strategy','source_id':'TV:'+item['script_id'],
                    'source_url':f'https://www.tradingview.com/script/{item["script_id"]}/',
                    'title':item['script_title'],
                    'version_key':'public-mirror-'+REV[:12]}
                n11=execute_node11({'kind':'strategy','has_candidate':True,
                                    'candidate':cand,'pine_code':pine},workflow_kind='strategy')
                n15=execute_node15(n11,workflow_kind='strategy')
                n16=execute_node16(n15,workflow_kind='strategy')
                assert n16['status']=='PINE_SAVED_CONVERSION_PENDING'
                item['wf01_n11_n15_n16_persisted']=True
            except Exception as exc:
                item['wf01_error']=type(exc).__name__+':'+str(exc)[:250]
            if i%200==0: print('WF01_NODE_PERSIST_PROGRESS',i,flush=True)
    keys=list(ordered[0])
    with (out/'strategy_4428_source_status.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(ordered)
    summary={
        'input_unique_strategy_ids':len(rows),
        'exact_id_mirror_path_candidates':matches,
        'retrieved_source_count':sum(x['source_state']=='PINE_RETRIEVED_FROM_PINNED_MIRROR' for x in ordered),
        'wf01_n11_n15_n16_saved_count':sum(x['wf01_n11_n15_n16_persisted'] for x in ordered),
        'status_counts':{},
        'mirror_revision':REV,
        'rights_note':'Publicly retrievable mirror source is not identity/version or license approval',
        'collection_scope':'Only source files matching an ID in the 4428 strategy catalog, no indicators or libraries',
    }
    for x in ordered:summary['status_counts'][x['source_state']]=summary['status_counts'].get(x['source_state'],0)+1
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'README_KO.txt').write_text('4428개 Strategy 전수 검사. PINE_RETRIEVED_FROM_PINNED_MIRROR만 실제 Pine 파일 존재. 나머지는 없는 코드를 만들지 않았음. Pine 원문은 원본 TradingView 버전 및 라이선스와 동일성 검증 필요.\n',encoding='utf-8')
    print('STRATEGY_4428_SOURCE_COLLECTION_SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
