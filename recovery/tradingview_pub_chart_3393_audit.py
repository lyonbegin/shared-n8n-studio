#!/usr/bin/env python3
"""Fetch original TradingView publication chart metadata, screenshot evidence, one ID at a time.
This verifies published chart metadata; it does NOT validate profitability or Python trade parity.
"""
import argparse,concurrent.futures,html,json,re,threading,time,urllib.request,urllib.error,os
from pathlib import Path
import hashlib

def get(url,timeout=18,maxbytes=3500000):
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        'Accept-Language':'en-US,en;q=0.9','Accept':'text/html,image/avif,image/webp,image/apng,*/*;q=0.8'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read(maxbytes),r.headers.get('content-type','')

def collect_manifests(roots):
    d={}
    for root in roots:
        for f in Path(root).rglob('manifest.json'):
            try:
                x=json.loads(f.read_text('utf-8'))
                sid=x.get('script_id') or x.get('strategy_id')
                if not sid or not re.fullmatch(r'[a-zA-Z0-9]{8}',sid):continue
                url=x.get('source_url') or x.get('tradingview_url')
                if not url:continue
                if sid not in d:d[sid]=url
            except Exception:continue
    return d

def group_match(pattern,s,default=''):
    m=re.search(pattern,s)
    return html.unescape(m.group(1)) if m else default

def fetch_one(case,out):
    sid,url=case
    rec={'script_id':sid,'original_url':url,'published_ticker':'','published_timeframe':'',
         'published_tv_type':'','published_exchange':'','ticker_title':'','chart_image_url':'',
         'page_verified':False,'image_downloaded':False,'error':'','evidence_type':'',
         'source':'TradingView publication embedded chart metadata'}
    text=''
    for target in (url, f'https://www.tradingview.com/script/{sid}/'):
        try:
            raw,ct=get(target,maxbytes=4000000)
            text=raw.decode('utf-8','replace')
            if 'pro_symbol' not in text:raise RuntimeError('No embedded publication symbol in page')
            rec['page_verified']=True
            rec['page_url']=target
            break
        except Exception as e:
            rec['error']=str(e)[:180]
    if not text:return rec
    rec['published_ticker']=group_match(r'"symbol":\{"pro_symbol":"([^"]+)"',text)
    rec['published_timeframe']=group_match(r'"interval":"([^"]+)"',text)
    rec['published_tv_type']=group_match(r'"symbol":\{"pro_symbol":"[^"]+","short_name":"[^"]*","exchange":"[^"]*","type":"([^"]+)"',text)
    rec['published_exchange']=group_match(r'"symbol":\{"pro_symbol":"[^"]+","short_name":"[^"]*","exchange":"([^"]+)"',text)
    rec['ticker_title']=group_match(r'"ticker_title":"([^"]+)"',text)
    webp=group_match(r'"webp_url":"([^"]+)"',text).replace('\\/','/')
    if webp:
        rec['chart_image_url']=webp.replace('_mid.webp','.png')
        try:
            blob,ct=get(webp,timeout=14,maxbytes=700000)
            if 'image' not in ct or len(blob)<1000:raise RuntimeError('Not an image')
            dest=out/'charts'/f'{sid}.webp'
            dest.write_bytes(blob)
            rec['image_downloaded']=True
            rec['image_sha256']=hashlib.sha256(blob).hexdigest()
            rec['image_size']=len(blob)
        except Exception as e:
            rec['image_error']=str(e)[:150]
    if rec['published_ticker'] and rec['published_timeframe']:
        rec['evidence_type']='published_embedded_chart_symbol_interval'
    else:
        rec['error']='Missing symbol or interval in publication HTML'
    return rec

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sources',nargs='+',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--shard',type=int,required=True)
    p.add_argument('--shards',type=int,required=True)
    p.add_argument('--workers',type=int,default=4)
    a=p.parse_args()
    out=Path(a.out);(out/'charts').mkdir(parents=True,exist_ok=True)
    docs=collect_manifests(a.sources)
    print('ALL_SOURCE_IDS',len(docs),flush=True)
    cases=[c for i,c in enumerate(sorted(docs.items())) if i%a.shards==a.shard]
    print('SHARD',a.shard,'CASES',len(cases),flush=True)
    result={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs={pool.submit(fetch_one,c,out):c for c in cases}
        for done,f in enumerate(concurrent.futures.as_completed(futs),1):
            rec=f.result()
            result[rec['script_id']]=rec
            if done%40==0:print('PROGRESS',done,'/',len(cases),'PAGE_SUCCESS',sum(x['page_verified'] for x in result.values()),flush=True)
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    summ={'shard':a.shard,'cases':len(cases),'page_verified':sum(x['page_verified'] for x in result.values()),
          'ticker_and_timeframe':sum(bool(x['published_ticker'] and x['published_timeframe']) for x in result.values()),
          'image_downloaded':sum(x['image_downloaded'] for x in result.values())}
    (out/'summary.json').write_text(json.dumps(summ,indent=2))
    print('SUMMARY',summ,flush=True)

if __name__=='__main__':main()
