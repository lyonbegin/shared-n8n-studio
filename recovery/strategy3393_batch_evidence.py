#!/usr/bin/env python3
"""100-item evidence batches, resumable GitHub checkpoints. Not a semantic/TV parity claim."""
import argparse,ast,collections,csv,hashlib,json,re,subprocess,time
from pathlib import Path

ID=re.compile(r'^[0-9A-Za-z]{8}$')
FUNCTIONS={x:re.compile(p,re.I) for x,p in {
'EMA':r'\b(?:ta\.)?ema\s*\(','SMA':r'\b(?:ta\.)?sma\s*\(',
'RSI':r'\b(?:ta\.)?rsi\s*\(','STOCH':r'\b(?:ta\.)?stoch\s*\(',
'ATR':r'\b(?:ta\.)?atr\s*\(','MACD':r'\b(?:ta\.)?macd\s*\(',
'VWAP':r'\b(?:ta\.)?vwap\s*\(','ADX':r'\b(?:ta\.)?adx\s*\(',
'CORRELATION':r'\b(?:ta\.)?correlation\s*\(','BOLLINGER':r'\b(?:ta\.)?bb\s*\(',
'EXTERNAL_SYMBOL':r'\b(?:request\.)?security\s*\(',
'SESSION':r'\binput\.session\s*\(','SUPER_TREND':r'\b(?:ta\.)?supertrend\s*\('
}.items()}
CLASS87={x:re.compile(p,re.I) for x,p in {
'S001':r'box spread','S002':r'put.call parity',
'S003':r'cash.and.carry|futures basis',
'S016':r'calendar spread|term structure|contango|backwardation',
'S017':r'fx carry|interest rate differential','S020':r'iron condor',
'S022':r'covered call','S024':r'gamma scalping',
'S026':r'dispersion|implied correlation',
'S028':r'cointegration|pairs trading','S042':r'iv term structure',
'S070':r'treasury basis|cheapest.to.deliver|ctd',
'S078':r'cds.{0,20}basis'
}.items()}

def hashit(buf):return hashlib.sha256(buf).hexdigest()
def indexed(root):
    src,gen,manifest={},{},{}
    for p in sorted(Path(root).rglob('*')):
        if not p.is_file():continue
        parts=p.parts
        if p.name=='generated.py':
            sid=p.parent.name if ID.fullmatch(p.parent.name) else (p.parent.parent.name if ID.fullmatch(p.parent.parent.name) else '')
            if sid:gen.setdefault(sid,p)
        elif p.name in ('strategy.pine','original.pine'):
            sid=parts[-3] if p.name=='strategy.pine' and len(parts)>2 and parts[-2]=='original' else parts[-2]
            if ID.fullmatch(sid):src.setdefault(sid,p)
        elif p.name=='manifest.json' and ID.fullmatch(parts[-2]):
            manifest.setdefault(parts[-2],p)
    return src,gen,manifest

def cites(src,pat,limit=6):
    ret=[]
    for i,ln in enumerate(src.splitlines(),1):
        v=ln.strip()
        if not v or v.startswith('//'):continue
        if re.search(pat,ln,re.I):
            ret.append({'line':i,'pine':v[:270]})
            if len(ret)==limit:break
    return ret

def asset(row):
    sym=(row.get('published_ticker') or '').upper()
    typ=(row.get('published_tv_type') or '').lower()
    label=(row.get('ticker_title') or '').lower()
    ticker=sym.split(':')[-1]
    if not sym:return '종목 확인 대기','HOLD_MISSING_SYMBOL'
    if typ=='swap' or re.search(r'BTC|XBT|ETH|SOL|LINK|DOGE|USDT|USDC|XRP|BNB',ticker) or sym.startswith(('BINANCE:','BYBIT:','COINBASE:','BITMEX:','OKX:')):
        return '암호화폐','EXCLUDE_CRYPTO'
    if typ in ('stock','dr'):return '주식','EXCLUDE_STOCK'
    if any(v in ticker for v in ('XAU','XAG','XPT','XPD','GC1!','SI1!')) or any(x in label for x in ('gold','silver','platinum','palladium')):
        return '귀금속','INCLUDE_ASSET'
    if typ=='forex':return '외환','INCLUDE_ASSET'
    if typ=='commodity' or any(v in ticker for v in ('FCPO','ZC1!','ZS1!','ZW1!','CL1!','NG1!','HG1!')):
        return '원자재·농산물·에너지','INCLUDE_ASSET'
    if typ=='futures':
        if any(x in ticker for x in ('ES1!','MES1!','NQ1!','MNQ1!','YM1!','RTY1!')):
            return '주가지수선물','INCLUDE_INDEX_FUTURE_POLICY'
        return '선물 기초자산 조사','HOLD_UNDERLYING'
    return '기초자산 조사','HOLD_UNDERLYING'

def analyze(rank,sid,src,py,manifest,chart):
    s=src.read_bytes();p=py.read_bytes()
    text=s.decode('utf-8','replace')
    clean='\n'.join(x.split('//')[0] for x in text.splitlines() if not x.strip().startswith('//'))
    try:ast.parse(p.decode('utf-8','replace')); astok=True
    except SyntaxError:astok=False
    a,decision=asset(chart)
    title=manifest.get('title','') or ''
    if not title:
        mm=re.search(r'\bstrategy\s*\(\s*["\x27]([^"\x27]+)',text)
        title=mm.group(1) if mm else ''
    url=manifest.get('source_url') or manifest.get('tradingview_url') or ('https://www.tradingview.com/script/'+sid+'/')
    xref=list(dict.fromkeys(re.findall(r'\b(?:request\.)?security\s*\(\s*["\x27]([^"\x27]+)',clean)))
    e=cites(text,r'\bstrategy\.(?:entry|order)\s*\(')
    x=cites(text,r'\bstrategy\.(?:exit|close|close_all)\s*\(')
    features=[k for k,rx in FUNCTIONS.items() if rx.search(clean)]
    hints=[k for k,rx in CLASS87.items() if rx.search((title+' '+text[:8000]))]
    flaws=[]
    if not e:flaws.append('진입 주문코드 확인 필요')
    if not x:flaws.append('명시적 청산코드 확인 필요')
    if re.search(r'lookahead\s*=\s*barmerge\.lookahead_on',clean):flaws.append('미래참조 설정 주의')
    if 'security(' in clean:flaws.append('외부시세/상위시간봉 리페인팅 검토')
    if not astok:flaws.append('Python AST 실패')
    return {
      'rank':rank,'script_id':sid,'title':title,'original_url':url,
      'published_ticker':chart.get('published_ticker',''),
      'published_timeframe':chart.get('published_timeframe',''),
      'chart_image_url':chart.get('chart_image_url',''),
      'published_chart_page_verified':bool(chart.get('page_verified')),
      'asset_class':a,'decision':decision,
      'pine_sha256':hashit(s),'python_sha256':hashit(p),
      'pine_file':str(src),'python_file':str(py),'python_ast_ok':astok,
      'entry_evidence':e,'exit_evidence':x,
      'features':features,'external_symbol_refs':xref[:20],
      '87_candidate_keyword_only':hints,'risks':flaws,
      'multi_leg_real_order_verified':False,
      'new_category_candidate':a+' / 개별 매매논리 심층검토 필요',
      'reuse_modules':features,
      'cross_asset_combination_verified':False,
      'analysis_level':'PROGRAMMATIC_PINE_EVIDENCE',
      'semantic_deep_review_complete':rank<=20,
      'tradingview_python_order_parity_verified':False,
      'strategy_profitability_verified':False,
      'production_ready':False
    }

def write_batch(out,rows,errors,lo,hi):
    folder=out/'batches';folder.mkdir(parents=True,exist_ok=True)
    key=f'{lo:04d}-{hi:04d}'
    data=folder/(key+'.jsonl')
    data.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
    cols=['rank','script_id','title','published_ticker','published_timeframe','asset_class','decision',
          'features','external_symbol_refs','87_candidate_keyword_only','risks','analysis_level','original_url']
    with (folder/(key+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader()
        for row in rows:
            item={**row}
            for col in ('features','external_symbol_refs','87_candidate_keyword_only','risks'):
                item[col]='; '.join(item[col])
            w.writerow(item)
    (folder/(key+'.errors.json')).write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'first':lo,'last':hi,'expected':hi-lo+1,'written':len(rows),
        'errors':len(errors),'ticker_verified':sum(bool(x['published_ticker']) for x in rows),
        'asset_counts':dict(collections.Counter(x['decision'] for x in rows)),
        'source_sha256':hashit(data.read_bytes()),'semantic_review_completed':False,
        'programmatic_review_completed':len(rows)==hi-lo+1 and not errors}
    (folder/(key+'.summary.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

def persist(output,key):
    subprocess.run(['git','add',str(output)],check=True)
    changes=subprocess.run(['git','diff','--cached','--quiet'])
    if changes.returncode==0:return
    subprocess.run(['git','-c','user.name=strategy3393-batch-bot','-c','user.email=github-actions[bot]@users.noreply.github.com',
                    'commit','-m','Analysis 3393: checkpoint '+key],check=True)
    for attempt in range(3):
        done=subprocess.run(['git','push','origin','HEAD'],capture_output=True,text=True)
        if done.returncode==0:return
        print('PUSH_RETRY',attempt,done.stderr[-200:],flush=True)
        time.sleep(2+attempt*2)
        subprocess.run(['git','pull','--rebase'],check=True)
    raise RuntimeError('Unable to persist GitHub batch '+key)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',required=True);ap.add_argument('--chart',required=True)
    ap.add_argument('--out',default='analysis3393');ap.add_argument('--git-persist',action='store_true')
    args=ap.parse_args()
    src,py,manifest=indexed(args.input)
    ids=sorted(py)
    assert len(ids)==3393,('Expected exactly 3393 unique successful code files',len(ids))
    assert ids[:3]==['02yfhjiz','03zgCMqx','04erUlJM'],ids[:3]
    charts=json.loads(Path(args.chart).read_text(encoding='utf-8'))
    out=Path(args.out)
    complete=0
    for lo in range(21,3394,100):
        hi=min(3393,lo+99);key=f'{lo:04d}-{hi:04d}'
        summary_path=out/'batches'/(key+'.summary.json')
        if summary_path.exists():
            summary=json.loads(summary_path.read_text(encoding='utf-8'))
            if summary.get('written')==hi-lo+1 and summary.get('errors')==0:
                data=out/'batches'/(key+'.jsonl')
                if data.exists() and hashit(data.read_bytes())==summary['source_sha256']:
                    complete+=1;print('CHECKPOINT_EXISTS',key,flush=True);continue
        rows=[];errors=[]
        for rank in range(lo,hi+1):
            sid=ids[rank-1]
            try:
                if sid not in src:raise RuntimeError('No Pine original')
                m=json.loads(manifest[sid].read_text()) if sid in manifest else {}
                rows.append(analyze(rank,sid,src[sid],py[sid],m,charts.get(sid,{})))
            except Exception as ex:errors.append({'rank':rank,'script_id':sid,'error':str(ex),'retry_required':True})
        summary=write_batch(out,rows,errors,lo,hi)
        status={'total':3393,'previous_manual_review':20,'batch_size':100,'processed_to':hi,
            'batches_completed':complete+1,'stage':'PROGRAMMATIC_CODE_EVIDENCE',
            'manual_semantic_review_complete':20,'completed_by_model_semantic_analysis':0,
            'remaining_for_deep_semantic_review':3373,
            'tv_python_order_parity_verified':0,'automatic_user_approval_required':False}
        out.mkdir(exist_ok=True)
        (out/'progress.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
        print('BATCH',key,summary,flush=True)
        if args.git_persist:persist(out,key)
        if errors:raise RuntimeError('Failed cases must be retried: '+str(errors[:3]))
        complete+=1
    print('ALL_CHECKPOINTS_DONE',complete,flush=True)
if __name__=='__main__':main()
