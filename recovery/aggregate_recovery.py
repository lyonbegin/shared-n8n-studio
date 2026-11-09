#!/usr/bin/env python3
"""Merge exactly 3537 missing Strategy recovery attempts and previous 891.

This report never equates "not found in a mirror" with "not public".
"""
import csv,json,hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone

orig=Path("source_4428/strategy_4428_result/strategy_4428_source_status.csv")
previous=list(csv.DictReader(orig.open(encoding="utf-8-sig",newline="")))
if len(previous)!=4428:raise SystemExit("PREVIOUS_CATALOG_LENGTH_NOT_4428")
files=sorted(Path("collected").glob("strategy4428-recovery-shard-*/status.csv"))
if len(files)!=4:raise SystemExit("MUST_HAVE_FOUR_RECOVERY_SHARDS "+str(files))
results=[]
for file in files:
    rows=list(csv.DictReader(file.open(encoding="utf-8-sig",newline="")))
    results.extend(rows)
if len(results)!=3537 or len({x["script_id"] for x in results})!=3537:
    raise SystemExit(f"RECOVERY_COVERAGE_INVALID {len(results)} {len({x['script_id'] for x in results})}")
new={x["script_id"]:x for x in results}
out=Path("final_recovery");out.mkdir(exist_ok=True)
combined=[];final_headers=["script_id","script_title","tradingview_url","original_access",
    "previous_state","current_source_status","source_provenance","source_sha256",
    "pine_version","direct_imports","source_path","facade_pub_id","error"]
for r in previous:
    sid=r["script_id"]
    if r["source_state"]=="PINE_RETRIEVED_FROM_PINNED_MIRROR":
        item={"script_id":sid,"script_title":r["script_title"],"tradingview_url":r["tradingview_url"],
          "original_access":r["original_access"],"previous_state":r["source_state"],
          "current_source_status":"PREVIOUS_PUBLIC_MIRROR_PINE_AVAILABLE",
          "source_provenance":r["source_provenance"],
          "source_sha256":r["pine_sha256"],"pine_version":r["pine_version"],
          "direct_imports":"NOT_ANALYZED_IN_THIS_RUN",
          "source_path":r["local_pine_path"],"facade_pub_id":"","error":r["error"]}
    else:
        itemnew=new[sid]
        item={"script_id":sid,"script_title":r["script_title"],"tradingview_url":r["tradingview_url"],
          "original_access":r["original_access"],"previous_state":r["source_state"],
          "current_source_status":itemnew["recovery_state"],
          "source_provenance":"TradingView public Pine source" if itemnew["pine_sha256"] else "NONE",
          "source_sha256":itemnew["pine_sha256"],"pine_version":itemnew["pine_version"],
          "direct_imports":itemnew["direct_imports"],
          "source_path":itemnew["source_path"],"facade_pub_id":itemnew["pub_id"],
          "error":itemnew["error"]}
    combined.append(item)
assert len(combined)==4428 and len({x["script_id"] for x in combined})==4428
with (out/"all_4428_recovery_status.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=final_headers);w.writeheader();w.writerows(combined)
with (out/"missing_3537_recovery_results.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(sorted(results,key=lambda x:x["script_id"]))
states=Counter(x["current_source_status"] for x in combined)
summary={"processed_4428_unique_ids":4428,
    "prior_missing_3537_checked":len(results),
    "prior_mirror_source_891":891,
    "new_official_pine_retrieved":states["OFFICIAL_OPEN_SOURCE_RETRIEVED"]+states["OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW"],
    "new_pine_needs_version_review":states["OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW"],
    "combined_source_candidates":891+states["OFFICIAL_OPEN_SOURCE_RETRIEVED"]+states["OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW"],
    "closed_not_public":states["CLOSED_SOURCE_NO_PUBLIC_ACCESS"],
    "source_status_counts":dict(states),
    "actual_compile_verified_count_for_new_sources":0,
    "actual_tradingview_parity_verified_count":0,
    "completed_at_utc":datetime.now(timezone.utc).isoformat(),
    "warnings":["Old GitHub mirror Pine may differ from TradingView latest revision.",
      "Even official Pine source may require source licenses or Library dependencies to convert.",
      "Protected and invite-only source never requested or fabricated."]}
(out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("RECOVERY_AGGREGATE_PASS",json.dumps(summary,ensure_ascii=False),flush=True)
