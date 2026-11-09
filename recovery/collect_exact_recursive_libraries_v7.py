#!/usr/bin/env python3
"""Exact-version public TradingView Pine Library dependency closure for 3,455 Strategies.

Safety invariants:
- Never substitute 'last' for an import's numeric version.
- Never report NATIVE_PYTHON_COMPILED from a PYNE Runtime wrapper.
- Independently preserve original Pine for every Strategy and Library in its
  Strategy package, even when used by 20 other Strategies.
- Fail closed when a Library ID/title/author/version/source cannot be verified.
- Never request protected or invite-only TradingView source.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict,deque
from datetime import datetime,timezone
import hashlib,html,json,os,re,shutil,time
from pathlib import Path
import urllib.request,urllib.parse,urllib.error

IMPORT_RE=re.compile(r"(?m)^\s*import\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[0-9]+)\b")
LIB_RE=re.compile(r"(?m)^[ \t]*library\s*\(\s*(?:title\s*=\s*)?['\"]([^'\"]+)['\"]",re.I)
DECL_RE=re.compile(r"(?m)^\s*(strategy|indicator|library)\s*\(")
PUB_RE=re.compile(r'"script_id_part"\s*:\s*"PUB;([A-Za-z0-9]+)"')
PUBLIC_SLUG=re.compile(r"https://www\.tradingview\.com/script/[A-Za-z0-9]{8}(?:-([A-Za-z0-9-]+))?/?")
TITLE_RE=re.compile(r"<title[^>]*>(.*?)</title>",re.I|re.S)
MAX_PAGE=6_000_000;MAX_SOURCE=700_000
HEADERS={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0",
         "Accept":"text/html,application/json,*/*","Origin":"https://www.tradingview.com"}
# Evidence-backed *historic TradingView username* mapping. Source must still
# match the exact imported library() identifier and numeric version.
# Old HeWhoMustNotBeNamed is explicitly named by the author's own site.
# tbiktag is named on current publisher tbtkg's TradingView publications.
HISTORIC_PUBLISHER_ALIASES={
 ("HeWhoMustNotBeNamed","Trendoscope"):
  "https://trendoscope.com/ (creator identifies old HeWhoMustNotBeNamed name)",
 ("tbiktag","tbtkg"):
  "https://www.tradingview.com/script/XkBwnQ2h-Intrabar-Run-Count-Indicator-tbiktag/",
}
def publisher_identity_matches(asked,published):
 return asked.lower()==published.lower() or any(
  old.lower()==asked.lower() and new.lower()==published.lower()
  for old,new in HISTORIC_PUBLISHER_ALIASES
 )
INDEX_URL="https://raw.githubusercontent.com/OdynBrouwer/Tradingview-Pine-Script-Downloader/d3cee2e0fa94a8a8fd73c9e24b2301add7909a60/analyze/jsons/libraries-urls.json"
SEEDS={
  "TradingView/ta":"https://www.tradingview.com/script/BICzyhq0-ta/",
  "TradingView/RelativeValue":"https://www.tradingview.com/script/cZnSLls2-RelativeValue/",
  "jason5480/chrono_utils":"https://www.tradingview.com/script/LFr7gOBH-chrono-utils/",
  "TradersReality/Traders_Reality_Lib":"https://www.tradingview.com/script/8zgJTM9u-Traders-Reality-Lib/",
  "X4815162342/X48_LibaryStrategyStatus":"https://www.tradingview.com/script/Vg4LmYYm-X48-LibaryStrategyStatus/",
  "Naruephat/Cayoshi_Library":"https://www.tradingview.com/script/iZcjz6AV/",
  "richardgong1988/HanJinSignals26":"https://www.tradingview.com/script/s5waF1z9-HanJinSignals26/",
  "Trading-IQ/ICTlibrary":"https://www.tradingview.com/script/UaWyGzvU-Trading-IQ-ICT-Library/",
  "thequantscience/XGBoostMini":"https://www.tradingview.com/script/SQ2QIdN6-XGBoostMini/",
  "trade-wzrd/TradeWzrdAlerts":"https://www.tradingview.com/script/KGzrNzOr-Trade-Wzrd-Library-Alert-String-Utils/",
}
def sha(b):return hashlib.sha256(b).hexdigest()
def jdump(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
def safe_get(url,limit):
 """Public GET with bounded output. No authentication cookies."""
 for trial in range(3):
  try:
   req=urllib.request.Request(url,headers=HEADERS)
   with urllib.request.urlopen(req,timeout=22) as r:
    b=r.read(limit+1)
    if len(b)>limit:raise ValueError("RESPONSE_TOO_LARGE")
    return b
  except urllib.error.HTTPError as e:
   if e.code not in (429,500,502,503,504) or trial==2:raise
   time.sleep(3*(trial+1))
def normalize(s):return re.sub(r"[^a-z0-9]","",s.lower())
def refs(source):return list(dict.fromkeys(IMPORT_RE.findall(source)))
def library_title(source):
 m=LIB_RE.search(source)
 return m.group(1) if m else ""
def title_author(page):
 m=TITLE_RE.search(page)
 if not m:return None
 title=html.unescape(re.sub("<[^>]*>"," ",m.group(1))).strip()
 for delim in (" — Library by "," – Library by "," - Library by "," by "):
  if delim in title:
   left,right=title.split(delim,1)
   author=right.rsplit(" — TradingView",1)[0].rsplit(" - TradingView",1)[0].strip()
   return left.strip(),author
 return None

def source_catalog(oldroot,newroot):
 found={}
 for root,label,pattern in [
  (Path(oldroot),"PINNED_MIRROR","**/strategies/*/original/strategy.pine"),
  (Path(newroot),"TRADINGVIEW_PUBLIC","**/recovered/*/strategy.pine")]:
  for file in root.glob(pattern):
   sid=file.parent.name if label=="TRADINGVIEW_PUBLIC" else file.parents[1].name
   if not re.fullmatch("[A-Za-z0-9]{8}",sid):continue
   content=file.read_bytes()
   if not content or len(content)>1_000_000:continue
   # A more direct official Pine source takes precedence over earlier mirror.
   if sid not in found or label=="TRADINGVIEW_PUBLIC":
    found[sid]={"path":file,"sha256":sha(content),"provenance":label}
 return found

class Collector:
 def __init__(self,urls,output,existing=None):
  self.urls=urls
  self.output=Path(output)
  self.cache={}       # import ref -> exact source payload or error
  self.metadata={}    # source page URL -> metadata
  self.network_calls=0
  if existing:
   for meta in Path(existing).rglob("library_corpus/*/*/*.json"):
    try:
     rec=json.loads(meta.read_text(encoding="utf-8"))
     if rec.get("status")!="EXACT_VERSION_PUBLIC_SOURCE":continue
     pine=meta.with_suffix(".pine")
     if not pine.is_file():continue
     blob=pine.read_bytes()
     if sha(blob)!=rec.get("sha256"):continue
     rec["source"]=blob.decode("utf-8")
     self.cache[rec["ref"]]=rec
    except (ValueError,KeyError,OSError):pass

 def author_candidates(self,username,name):
  """Public author feed fallback. Do not guess library IDs or substitute versions."""
  cachekey="authorfeed:"+username.lower()+"/"+name.lower()
  if cachekey in self.metadata:return self.metadata[cachekey]
  found=[];failures=[]
  # Publisher feed is a separate public script index from the page-name archive.
  for page in range(1,7):
   url="https://www.tradingview.com/api/v1/scripts/?"+urllib.parse.urlencode({
     "by":username,"q":name,"page":page,"per_page":24})
   try:
    reply=json.loads(safe_get(url,1_500_000))
    self.network_calls+=1
    if not isinstance(reply.get("results"),list):break
    for item in reply["results"]:
     author=(item.get("user") or {}).get("username","")
     if author.lower()!=username.lower():continue
     if str(item.get("script_type","")).lower() not in ("library","libraries"):continue
     if item.get("script_access")!=1:continue
     addr=item.get("chart_url","")
     if addr.startswith("https://www.tradingview.com/script/") and PUBLIC_SLUG.fullmatch(addr):
      found.append(addr)
    if page>=int(reply.get("page_count",1) or 1) or not reply.get("next"):break
   except Exception as e:
    failures.append(type(e).__name__+":"+str(e)[:100]);break
  self.metadata[cachekey]=list(dict.fromkeys(found))[:25]
  return self.metadata[cachekey]
 def candidates(self,ref):
  u,name,version=ref.split("/")
  key=u+"/"+name
  vals=([SEEDS[key]] if key in SEEDS else [])
  vals+=self.urls.get(normalize(name),[])
  vals+=self.author_candidates(u,name)
  return list(dict.fromkeys(vals))[:45]
 def inspect_page(self,url):
  if url in self.metadata:return self.metadata[url]
  try:
   b=safe_get(url,MAX_PAGE);self.network_calls+=1
   page=b.decode("utf-8","replace")
   ta=title_author(page)
   ids=list(dict.fromkeys(PUB_RE.findall(page)))
   out={"title_author":ta,"pub_id":"PUB;"+ids[0] if len(ids)==1 else None,
        "url":url,"pub_id_count":len(ids)}
  except Exception as e:
   out={"url":url,"error":type(e).__name__+":"+str(e)[:140]}
  self.metadata[url]=out
  return out
 def get(self,ref):
  if ref in self.cache:return self.cache[ref]
  bits=ref.split("/")
  if len(bits)!=3 or not bits[2].isdigit():
   obj={"ref":ref,"status":"INVALID_IMPORT_REFERENCE"};self.cache[ref]=obj;return obj
  username,name,version=bits
  # Check all *public* candidates, do not use a newer library version.
  reports=[]
  for candidate in self.candidates(ref):
   page=self.inspect_page(candidate)
   ta=page.get("title_author")
   curated=SEEDS.get(username+"/"+name)==candidate
   if not ta or not publisher_identity_matches(username,ta[1]) or (normalize(ta[0])!=normalize(name) and not curated):
    reports.append({"url":candidate,"reason":"AUTHOR_OR_TITLE_NOT_VERIFIED",
                    "published":ta})
    continue
   pid=page.get("pub_id")
   if not pid:
    reports.append({"url":candidate,"reason":"PUB_ID_NOT_VERIFIED"});continue
   u="https://pine-facade.tradingview.com/pine-facade/get/"+urllib.parse.quote(pid,safe="")+"/"+version
   try:
    raw=safe_get(u,MAX_SOURCE);self.network_calls+=1
    payload=json.loads(raw)
    source=payload.get("source")
    if not isinstance(source,str) or not source.strip():
     raise ValueError("VERSION_SOURCE_MISSING")
    declared=library_title(source)
    if declared!=name:
     raise ValueError("DECLARED_LIBRARY_TITLE_MISMATCH:"+declared)
    if not DECL_RE.search(source) or not source:
     raise ValueError("NO_LIBRARY_DECLARATION")
    pine=source.encode("utf-8")
    obj={
     "title_match_exception":"CURATED_URL_PUBLISHER_VERIFIED_AND_SOURCE_DECLARATION_MATCH" if curated and normalize(ta[0])!=normalize(name) else None,
     "ref":ref,"status":"EXACT_VERSION_PUBLIC_SOURCE",
     "sha256":sha(pine),"source":source,"source_bytes":len(pine),
     "publisher":username,"publisher_current":ta[1],"publisher_historic_alias_used":ta[1].lower()!=username.lower(),"library_name":name,"version":version,
     "page_url":candidate,"pub_id":pid,"source_url":u,
     "imports":refs(source),"rights":"PUBLISHED_OPEN_LIBRARY"}
    self.cache[ref]=obj
    return obj
   except Exception as e:
    reports.append({"url":candidate,"reason":type(e).__name__+":"+str(e)[:170]})
  obj={"ref":ref,"status":"EXACT_LIBRARY_SOURCE_NOT_FOUND",
       "candidate_urls_checked":len(reports),"checks":reports[:12]}
  self.cache[ref]=obj
  return obj
 def traverse(self,main):
  ordered=[];seen=set();errors=[];pending=deque(refs(main))
  while pending:
   ref=pending.popleft()
   if ref in seen:continue
   seen.add(ref)
   if len(seen)>120:
    errors.append("DEPENDENCY_GRAPH_EXCEEDS_LIMIT");break
   lib=self.get(ref)
   if lib["status"]!="EXACT_VERSION_PUBLIC_SOURCE":
    errors.append({"ref":ref,"reason":lib["status"]});continue
   ordered.append(ref)
   pending.extend(lib["imports"])
  return ordered,errors

def index_urls():
 raw=safe_get(INDEX_URL,1_500_000)
 arr=json.loads(raw)
 idx=defaultdict(list)
 for url in arr:
  if not isinstance(url,str):continue
  m=PUBLIC_SLUG.fullmatch(url)
  if m and m.group(1):
   idx[normalize(m.group(1))].append(url)
 return idx,len(arr)

def make_runner(path,main,libs):
 """Executable Python adapter; does NOT claim standalone native transpilation."""
 data=[{"namespace":x["publisher"],"name":x["library_name"],
        "version":int(x["version"]),"source":x["source"]} for x in libs]
 content=(
  "# Auto-generated Python PYNE adapter with exact-version Pine library sources\n"
  "# This executes Pine via Python; it is NOT a native Pine-to-Python translation.\n"
  "from pynescript.runtime import Runtime\n"
  "PINE_SOURCE="+repr(main)+"\n"
  "LIBRARIES="+repr(data)+"\n"
  "def execute(bars,symbol='TEST'):\n"
  "    return Runtime(symbol=symbol).run(PINE_SOURCE,bars,mode='auto',libraries=LIBRARIES)\n"
 )
 Path(path).write_text(content,encoding="utf-8")

def execute(args):
 sources=source_catalog(args.old,args.new)
 idx,sz=index_urls()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 c=Collector(idx,out,args.existing)
 rows=[]; dependency_refs=Counter()
 for sid,v in sorted(sources.items()):
  raw_original=v["path"].read_bytes()
  if sha(raw_original)!=v["sha256"]:raise ValueError("STRATEGY_SOURCE_SHA256_MISMATCH:"+sid)
  src=raw_original.decode("utf-8-sig",errors="strict")
  if not refs(src):continue
  root=out/"strategies"/sid
  root.mkdir(parents=True,exist_ok=True)
  sr=raw_original
  (root/"strategy.pine").write_bytes(sr)
  if sha((root/"strategy.pine").read_bytes())!=v["sha256"]:
   raise ValueError("PACKAGED_STRATEGY_BYTES_MISMATCH:"+sid)
  resolved,errors=c.traverse(src)
  libs=[c.cache[r] for r in resolved]
  for ref in resolved:
   dependency_refs[ref]+=1
   lib=c.cache[ref]
   user,name,version=ref.split("/")
   fn=root/"libraries"/user/name/(version+".pine")
   fn.parent.mkdir(parents=True,exist_ok=True)
   fn.write_text(lib["source"],encoding="utf-8")
  if not errors:
   make_runner(root/"runtime_adapter.py",src,libs)
  status="DEPENDENCY_COMPLETE_EXECUTION_NOT_VALIDATED" if not errors else "DEPENDENCY_INCOMPLETE"
  manifest={"strategy_id":sid,"status":status,"strategy_sha256":v["sha256"],
    "strategy_source_origin":v["provenance"],"direct_imports":refs(src),
    "transitive_imports":resolved,"missing_dependencies":errors,
    "libraries":[{k:x[k] for k in ("ref","sha256","source_bytes","page_url","source_url",
                                      "pub_id","imports","rights")} for x in libs],
    "native_python_transpiled":False,
    "runtime_adapter_created":not bool(errors),
    "runtime_behavior_verified":False,"tradingview_parity_verified":False,
    "collected_utc":datetime.now(timezone.utc).isoformat()}
  jdump(root/"manifest.json",manifest)
  rows.append({"id":sid,"status":status,"direct":len(refs(src)),
        "closure":len(resolved),"missing":len(errors),
        "missing_refs":" | ".join(str(x.get("ref",x)) if isinstance(x,dict) else str(x) for x in errors),
        "origin":v["provenance"]})
  print("LIBRARY_STRATEGY",json.dumps(rows[-1]),flush=True)
 for ref,lib in c.cache.items():
  user,name,version=ref.split("/")
  folder=out/"library_corpus"/user/name
  folder.mkdir(parents=True,exist_ok=True)
  if lib["status"]=="EXACT_VERSION_PUBLIC_SOURCE":
   (folder/(version+".pine")).write_text(lib["source"],encoding="utf-8")
  jdump(folder/(version+".json"),{k:v for k,v in lib.items() if k!="source"})
 jdump(out/"summary.json",{
  "input_strategy_pine_count":len(sources),
  "strategies_with_direct_library_imports":len(rows),
  "all_library_import_refs":len(c.cache),
  "verified_exact_library_sources":sum(x["status"]=="EXACT_VERSION_PUBLIC_SOURCE" for x in c.cache.values()),
  "complete_strategy_dependency_closure":sum(x["status"].startswith("DEPENDENCY_COMPLETE") for x in rows),
  "native_python_transpiled":0,
  "executability_smoke_tested":0,
  "library_source_references":dict(dependency_refs),
  "source_catalog_index_entries":sz,
  "public_network_calls":c.network_calls,
  "errors":dict(Counter(x["status"] for x in c.cache.values())),
  "result_notes":"Exact numeric /version source; no /last fallback. Library native Python conversion not yet supported.",
 })
 with (out/"strategy_library_status.csv").open("w",encoding="utf-8-sig",newline="") as f:
  import csv
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print("LIBRARY_FINAL",json.dumps(json.loads((out/"summary.json").read_text())),flush=True)
 if len(sources)!=3455:raise ValueError(f"EXPECTED_3455_PINE_SOURCES_GOT_{len(sources)}")
 if len(rows)<70:raise ValueError("EXPECTED_70_PLUS_STRATEGIES_WITH_IMPORTS")

def test():
 source='//@version=6\nstrategy("x")\nimport demo/Parent/3 as p\nplot(p.mult(close))'
 parent='//@version=6\nlibrary("Parent")\nimport demo/Child/2 as c\nexport mult(float x)=>c.add(x)*2'
 child='//@version=6\nlibrary("Child")\nexport add(float x)=>x+1'
 assert refs(source)==["demo/Parent/3"]
 assert library_title(parent)=="Parent"
 assert refs(parent)==["demo/Child/2"]
 assert library_title(child)=="Child"
 print("LOCAL_SYNTAX_AND_RECURSION_PARSE_TEST_PASS")
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--old",default="source_old");p.add_argument("--new",default="source_new")
 p.add_argument("--out",default="exact_library_result")
 p.add_argument("--existing",default="")
 p.add_argument("--selftest",action="store_true")
 a=p.parse_args()
 test()
 if not a.selftest:execute(a)
