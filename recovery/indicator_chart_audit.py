#!/usr/bin/env python3
"""Evidence collection for all 29,462 known TradingView indicator publications.

Reuse the verified 4,428-Strategy chart extractor. A page, embedded ticker,
TradingView asset class, timeframe, and preview image are independently audited.
Do not classify failed URLs as direction-only or as verified financial cases.
"""
import argparse, concurrent.futures, json, pathlib, re, time, collections, datetime
from tradingview_pub_chart_3393_audit import fetch_one

ROOT = pathlib.Path(__file__).resolve().parent
SOURCES = (ROOT / 'tv_indicator_manifest_0.tsv', ROOT / 'tv_indicator_manifest_1.tsv')

def load_all():
    entries = {}
    for source in SOURCES:
        for number, line in enumerate(source.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            sid, path = line.split('\t', 1)
            assert re.fullmatch(r'[A-Za-z0-9]{8}', sid), (source, number, sid)
            assert path.startswith(sid+'/') or path.startswith(sid+'-'), (source, number, path)
            assert sid not in entries, ('Duplicate ID', sid)
            entries[sid] = 'https://www.tradingview.com/script/' + path
    assert len(entries) == 29462, f'Expected 29,462 unique indicators, got {len(entries)}'
    return sorted(entries.items())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard', type=int, required=True)
    ap.add_argument('--shards', type=int, default=24)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    assert args.shards > 0 and 0 <= args.shard < args.shards
    out = pathlib.Path(args.out)
    (out/'charts').mkdir(parents=True, exist_ok=True)
    cases = [case for i, case in enumerate(load_all()) if i % args.shards == args.shard]
    results = {}
    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(fetch_one, case, out):case for case in cases}
        for i, future in enumerate(concurrent.futures.as_completed(jobs), 1):
            sid,url = jobs[future]
            try:
                record = future.result()
            except Exception as exc:
                record = {'script_id':sid,'original_url':url,'page_verified':False,
                  'published_ticker':'','published_tv_type':'','published_timeframe':'',
                  'image_downloaded':False,'error':str(exc)[:240]}
            record['reviewed_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            record['chart_evidence_status'] = (
                'TICKER_AND_IMAGE_VERIFIED' if
                record.get('page_verified') and record.get('published_ticker') and
                record.get('published_tv_type') and record.get('image_downloaded')
                else 'UNVERIFIED_RETRY_NEEDED')
            results[sid] = record
            if i % 100 == 0:
                ok=sum(x['chart_evidence_status']=='TICKER_AND_IMAGE_VERIFIED' for x in results.values())
                print(f'SHARD {args.shard}/{args.shards} {i}/{len(cases)} checked={ok}',flush=True)
    assert len(results) == len(cases)
    counts = collections.Counter(x['chart_evidence_status'] for x in results.values())
    types = collections.Counter(x.get('published_tv_type','') for x in results.values())
    summary = {'shard':args.shard,'shards':args.shards,'total':len(cases),
        'evidence_count':dict(counts),'asset_types':dict(types),
        'duration_seconds':round(time.monotonic()-t0,2),
        'source':'TradingView original publication page and published chart image'}
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf8')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print('FINAL',json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
