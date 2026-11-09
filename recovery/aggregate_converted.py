#!/usr/bin/env python3
"""Unify old 891 and recovered 3537 sources with actual free-PYNE outcomes."""
from collections import Counter
from pathlib import Path
import csv,json
from datetime import datetime,timezone

def load(path):
 with Path(path).open(encoding="utf-8-sig",newline="") as f:
  return list(csv.DictReader(f))
source=load("prior_4428/strategy_4428_full_status.csv")
recovery=load("recovered_final/all_4428_recovery_status.csv")
files=sorted(Path("converted_collected").glob("strategy4428-recovered-python-shard-*/conversion_status.csv"))
if len(files)!=4:raise SystemExit("CONVERSION_SHARD_ARTIFACTS_INCOMPLETE:"+str(files))
news=[]
for p in files:news+=load(p)
if len(source)!=4428 or len(recovery)!=4428 or len(news)!=3537:
 raise SystemExit(f"INPUT_COUNT_INVALID old={len(source)} new={len(news)} recovery={len(recovery)}")
byold={x["script_id"]:x for x in source}
byrec={x["script_id"]:x for x in recovery}
bynew={x["script_id"]:x for x in news}
if len(byold)!=4428 or len(byrec)!=4428 or len(bynew)!=3537:
 raise SystemExit("DUPLICATE_IDS")
out=Path("verified_4428_pipeline");out.mkdir(parents=True,exist_ok=True)
rows=[]
for sid in sorted(byold):
 old=byold[sid];rec=byrec[sid]
 if sid in bynew:
  fresh=bynew[sid]
  status=fresh["conversion_status"]
  strategy_source=rec["current_source_status"]
  pyhash=fresh["python_sha256"]
  reason=fresh["reason"]
  import_str=fresh["imports"]
 else:
  status=old["conversion_status"]
  strategy_source=rec["current_source_status"]
  pyhash=old["python_sha256"]
  reason=old["error"]
  import_str=old["resolved_libraries"] or old["missing_libraries"]
 rows.append({"script_id":sid,"title":rec["script_title"],
              "tradingview_url":rec["tradingview_url"],
              "source_status":strategy_source,
              "source_provenance":rec["source_provenance"],
              "original_access":rec["original_access"],
              "original_sha256":rec["source_sha256"],
              "import_refs":import_str,
              "python_conversion_status":status,
              "generated_python_sha256":pyhash,
              "source_notes":rec["error"],"conversion_notes":reason})
fields=list(rows[0])
with (out/"strategy4428_all_pipeline_status.csv").open("w",newline="",encoding="utf-8-sig") as f:
 w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
counts={"source":dict(Counter(x["source_status"] for x in rows)),
        "python":dict(Counter(x["python_conversion_status"] for x in rows))}
summary={
 "unique_strategy_ids":4428,
 "previous_pine_mirror_sources":891,
 "official_recovered":sum(x["source_status"] in ("OFFICIAL_OPEN_SOURCE_RETRIEVED","OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW") for x in rows),
 "total_source_candidates":sum(x["source_status"] in ("PREVIOUS_PUBLIC_MIRROR_PINE_AVAILABLE","OFFICIAL_OPEN_SOURCE_RETRIEVED","OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW") for x in rows),
 "python_generated":sum(x["python_conversion_status"] in ("PYTHON_GENERATED_UNVALIDATED","PYTHON_GENERATED_FROM_DERIVED_PINE_UNVALIDATED") for x in rows),
 "external_library_pending":sum("LIBRARY" in x["python_conversion_status"] and x["python_conversion_status"] not in ("PYTHON_GENERATED_UNVALIDATED",) for x in rows),
 "access_limited":sum(x["source_status"]=="CLOSED_SOURCE_NO_PUBLIC_ACCESS" for x in rows),
 "source_counts":counts["source"],"conversion_counts":counts["python"],
 "tv_parity_verified":0,
 "no_production_edits":True,
 "generated_at_utc":datetime.now(timezone.utc).isoformat()}
(out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("COMPLETE_4428_PIPELINE_AUDIT",json.dumps(summary,ensure_ascii=False),flush=True)
