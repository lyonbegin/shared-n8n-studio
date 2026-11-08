#!/usr/bin/env python3
import argparse,csv,datetime,json,re,time,zipfile
from pathlib import Path
import requests
BASE="https://www.tradingview.com"
def writejl(path,rows):
 with open(path,"w",encoding="utf-8") as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False)+"\n")
def normalize(x):
 u=x.get("chart_url") or ""
 m=re.search(r"/script/([A-Za-z0-9]{8})-",u)
 user=x.get("user") or {}
 return {"id":m[1] if m else "","title":x.get("name"),"url":u,"type":x.get("script_type"),"author":user.get("username"),
         "description_preview":x.get("description"),"created_at":x.get("created_at"),"updated_at":x.get("updated_at"),"access":x.get("script_access")}
def gather(session,author,delay):
 page=1;data=[];responses=[];expected=None;countpages=None;error=None
 while True:
  time.sleep(delay)
  r=session.get(BASE+"/api/v1/scripts/",params={"page":page,"per_page":24,"by":author,"q":""},timeout=30)
  r.raise_for_status();j=r.json()
  if not isinstance(j,dict) or not isinstance(j.get("results"),list):raise ValueError("bad API response")
  expected=j.get("count");countpages=j.get("page_count")
  responses.extend(j["results"])
  data.append({"page":page,"received":len(j["results"]),"next":j.get("next")})
  print("PAGE",author,page,"received",len(j["results"]),"count",expected,"page_count",countpages,flush=True)
  if not j.get("next"):break
  page+=1
  if page>10000:raise RuntimeError("pagination cap reached")
 ids=[str(v.get("id")) for v in responses]
 complete=isinstance(expected,int) and len(responses)==expected and len(set(ids))==len(ids)
 return responses,{"author":author,"expected_count":expected,"collected_count":len(responses),"page_count":countpages,
                   "pages":data,"complete_for_published_profile":complete}
def main():
 p=argparse.ArgumentParser();p.add_argument("--authors",default="FuturesTeller");p.add_argument("--authors-file")
 p.add_argument("--output",default="tv_author_out");p.add_argument("--delay",type=float,default=1.3)
 a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 authors=[x.strip() for x in a.authors.split(",") if x.strip()]
 if a.authors_file:authors.extend(x.strip() for x in Path(a.authors_file).read_text(encoding="utf-8").splitlines() if x.strip())
 authors=list(dict.fromkeys(authors))
 s=requests.Session();s.headers.update({"User-Agent":"Mozilla/5.0","Referer":BASE+"/","Accept":"application/json"})
 raw=[];reports=[]
 for author in authors:
  try:
   found,report=gather(s,author,max(1,a.delay));raw+=found;reports.append(report)
  except Exception as e:
   print("ERROR",author,repr(e),flush=True)
   reports.append({"author":author,"complete_for_published_profile":False,"error":str(e)})
 rows={r["id"]:r for x in raw if (r:=normalize(x))["id"]}
 rows=list(rows.values())
 writejl(out/"raw_api.jsonl",raw);writejl(out/"all.jsonl",rows)
 for typ,filename in (("strategy","strategies"),("indicator","indicators"),("library","libraries_reference_only")):
  subset=[r for r in rows if r["type"]==typ]
  writejl(out/(filename+".jsonl"),subset)
  if typ!="library":
   with open(out/(filename+".csv"),"w",encoding="utf-8-sig",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=list(normalize({}).keys()));writer.writeheader();writer.writerows(subset)
 writejl(out/"authors_coverage.jsonl",reports)
 manifest={"date":datetime.datetime.now(datetime.timezone.utc).isoformat(),"authors":len(authors),
  "authors_covered":sum(bool(r.get("complete_for_published_profile")) for r in reports),
  "total_unique":len(rows),"strategies":sum(r["type"]=="strategy" for r in rows),
  "indicators":sum(r["type"]=="indicator" for r in rows),
  "libraries_for_reference":sum(r["type"]=="library" for r in rows),
  "full_details_fetched":False,"source":"live published-scripts API; list descriptions are truncated"}
 (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
 (out/"README.md").write_text("# 작성자 2차 수집\n\n제작자 프로필 #published-scripts 탭에서 브라우저가 호출한 공개 목록 API로 페이지를 순회합니다.\nStrategy / Indicator는 별도 파일에 보관합니다. Library는 참조 목록으로만 보관합니다.\n목록 설명은 요약문이며 전체 상세 설명은 별도 수집 대상입니다.\n",encoding="utf-8")
 with zipfile.ZipFile(out/"author_publications.zip","w",zipfile.ZIP_DEFLATED) as z:
  for f in out.iterdir():
   if f.is_file() and f.name!="author_publications.zip":z.write(f,f.name)
 print("MANIFEST",json.dumps(manifest,ensure_ascii=False),flush=True)
 if manifest["authors_covered"]!=len(authors):raise SystemExit("Some profiles incomplete")
if __name__=="__main__":main()
