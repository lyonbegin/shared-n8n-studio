#!/usr/bin/env python3
"""Audit all 960 closed-source TradingView Strategy IDs against INDEXED,
PUBLIC GitHub source archives only. Never request protected code from TV.

A filename-path match means a PUBLIC_CANDIDATE, never proof of the
closed-source publication's original Pine. No content is redistributed.
"""
import csv,json,os,re,time,urllib.request,urllib.parse,urllib.error
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone

REPOSITORIES=[
"venkatalokeshanne/trading_strategies_indicators",
"Alorse/pinescript-strategies",
"thecapmarkets/pinescript-strategies-tmc",
"casoon/pine-scripts",
"kevanoullio/tradingview-pine-scripts",
"surajmateti/algorithmic-trading-pinescript",
"Salikha003/PineScripts",
"OdynBrouwer/Tradingview-Pine-Script-Downloader",
"pankajminda/TradingView-Pine-Script-Downloader",
"PyneSys/pyne-in-the-wild",
]
STATUS="final_source/all_4428_recovery_status.csv"
out=Path("restricted960_audit");out.mkdir(exist_ok=True)
rows=list(csv.DictReader(Path(STATUS).open(encoding="utf-8-sig",newline="")))
target=[r for r in rows if r["current_source_status"]=="CLOSED_SOURCE_NO_PUBLIC_ACCESS"]
if len(rows)!=4428 or len(target)!=960 or len({x["script_id"] for x in target})!=960:
 raise SystemExit("EXPECTED_EXACTLY_960_GATED_IDS_IN_4428_SOURCE_AUDIT")
access=Counter(x["original_access"] for x in target)
if access!={"2":452,"3":508}: raise SystemExit("EXPECTED_452_PROTECTED_AND_508_INVITE_ONLY")
ids={x["script_id"] for x in target}
headers={"Accept":"application/vnd.github+json",
         "User-Agent":"strategy-960-authenticated-public-archive-index/1",
         "X-GitHub-Api-Version":"2022-11-28"}
if os.getenv("GH_TOKEN"):headers["Authorization"]="Bearer "+os.environ["GH_TOKEN"]
def api(url):
 request=urllib.request.Request(url,headers=headers)
 try:
  with urllib.request.urlopen(request,timeout=22) as response:
   return json.load(response)
 except urllib.error.HTTPError as e:
  raise RuntimeError(f"HTTP_{e.code}")
public_index_report=[]
candidates=defaultdict(list)
for name in REPOSITORIES:
 entry={"repository":name,"accessible":False,"files":0,"truncated":False,"matched_ids":0,"error":""}
 try:
  data=api("https://api.github.com/repos/"+name)
  default=data["default_branch"]
  commit=api("https://api.github.com/repos/"+name+"/commits/"+urllib.parse.quote(default))
  commit_sha=commit["sha"]
  tree=api("https://api.github.com/repos/"+name+"/git/trees/"+commit_sha+"?recursive=1")
  entry["accessible"]=True;entry["files"]=len(tree.get("tree",[]))
  entry["truncated"]=bool(tree.get("truncated"))
  entry["commit_sha"]=commit_sha
  matched=set()
  for node in tree.get("tree",[]):
   path=node.get("path","")
   if node.get("type")!="blob":continue
   if not re.search(r"\.(pine|pinescript|txt|md)$",path,re.I):continue
   for cand in re.findall(r"(?<![A-Za-z0-9])([A-Za-z0-9]{8})(?![A-Za-z0-9])",path):
    if cand not in ids:continue
    matched.add(cand)
    url="https://github.com/"+name+"/blob/"+commit_sha+"/"+urllib.parse.quote(path)
    candidates[cand].append({
       "source_archive_repo":name,"commit_sha":commit_sha,
       "path":path,"public_browser_url":url,
       "evidence":"EXACT_TRADINGVIEW_SCRIPT_ID_IN_PUBLIC_FILE_PATH",
       "exact_source_identity_verified":False,
       "publisher_permission_verified":False})
  entry["matched_ids"]=len(matched)
 except Exception as e:
  entry["error"]=str(e)[:250]
 public_index_report.append(entry)
 print("ARCHIVE_INDEX",json.dumps(entry),flush=True)
 time.sleep(0.25)
report=[]
for x in target:
 sid=x["script_id"];cand=candidates.get(sid,[])
 report.append({
   "script_id":sid,"strategy_title":x["script_title"],
   "tradingview_url":x["tradingview_url"],
   "visibility_code":x["original_access"],
   "visibility_class":"PROTECTED" if x["original_access"]=="2" else "INVITE_ONLY",
   "tradingview_source_access":"AUTHOR_ONLY_AS_PUBLISHED",
   "status":"PUBLIC_FILENAME_CANDIDATE_UNVERIFIED" if cand else "NO_EXACT_FILENAME_CANDIDATE_IN_SEARCHED_REPOS",
   "public_archive_candidate_count":len(cand),
   "candidate_urls":" | ".join(c["public_browser_url"] for c in cand),
   "original_pine_obtained":False,
   "tradeview_version_equivalent_proven":False,
   "requires_author_source_or_permission":True,
 })
with (out/"restricted_960_audit.csv").open("w",encoding="utf-8-sig",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(report[0]));w.writeheader();w.writerows(report)
with (out/"public_archive_index_audit.csv").open("w",encoding="utf-8-sig",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(public_index_report[0]));w.writeheader();w.writerows(public_index_report)
(out/"candidate_paths.json").write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding="utf-8")
summary={
 "strategy_ids_audited":960,"protected":452,"invite_only":508,
 "archives_checked":len(public_index_report),
 "archives_accessible":sum(x["accessible"] for x in public_index_report),
 "truncated_archive_indexes":sum(x["truncated"] for x in public_index_report),
 "matched_exact_id_filename_candidates":sum(bool(candidates.get(x["script_id"])) for x in target),
 "verified_original_pine_retrieved":0,
 "compliance":"Only publicly listed GitHub repo file indexes. No TradingView protected source access or authentication bypass.",
 "limits":"A public repo filename match cannot verify source identity or reuse rights. Only author-provided exact source or independently verifiable licensed publication can be accepted as original.",
 "completed_at":datetime.now(timezone.utc).isoformat(),
}
(out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print("RESTRICTED960_COMPLETE",json.dumps(summary,ensure_ascii=False),flush=True)
