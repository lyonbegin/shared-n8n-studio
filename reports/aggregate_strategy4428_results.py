#!/usr/bin/env python3
"""Aggregate 4 already-completed Strategy4428 shard artifacts, no WF02 imports."""
from __future__ import annotations
import csv
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone

root=Path("collected")
files=sorted(root.rglob("status.csv"))
print("AGGREGATE_SHARD_FILES",[str(x) for x in files],flush=True)
if len(files)!=4:raise SystemExit("AGGREGATE_REQUIRES_EXACTLY_4_SHARD_STATUS_FILES")
allrows=[]
for f in files:
    with f.open(encoding="utf-8-sig",newline="") as h:
        rows=list(csv.DictReader(h))
    if len(rows)!=1107:raise SystemExit(f"SHARD_ROW_COUNT_INVALID {f} {len(rows)}")
    allrows.extend(rows)
n=len(allrows)
ids=[x["script_id"] for x in allrows]
if n!=4428 or len(set(ids))!=4428:
    raise SystemExit(f"AGGREGATE_MISSING_OR_DUPLICATE_STRATEGIES n={n} unique={len(set(ids))}")

out=Path("final_4428_result");out.mkdir(parents=True,exist_ok=True)
keys=list(allrows[0])
with (out/"strategy_4428_full_status.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(sorted(allrows,key=lambda x:x["script_id"]))
pattern=re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[0-9]+$")
usages=defaultdict(set)
for row in allrows:
    imported=set()
    for col in ["missing_libraries","resolved_libraries"]:
        for raw in (row.get(col) or "").split(" | "):
            ref=raw.strip().split(" [")[0]
            if pattern.fullmatch(ref):imported.add(ref)
    for ref in imported:usages[ref].add(row["script_id"])
with (out/"library_shared_metadata.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.writer(f)
    w.writerow(["exact_import_ref","observed_strategy_count","strategy_ids","reference_metadata","consolidation_performed"])
    for ref,sids in sorted(usages.items()):
        w.writerow([ref,len(sids)," | ".join(sorted(sids)),
          "REFERENCED_BY_MORE_THAN_ONE_STRATEGY" if len(sids)>1 else "REFERENCED_BY_ONE_STRATEGY",
          "NO"])
states={key:dict(Counter(x[key] for x in allrows)) for key in
    ["strategy_source_status","library_resolution_status","conversion_status"]}
summary={
    "timestamp_utc":datetime.now(timezone.utc).isoformat(),
    "scope":"TradingView Strategy 4428, independent per-Strategy Pine/Library bundles",
    "run_origin":"GitHub Actions 42575393731 four completed shards",
    "input_unique_strategy_ids":len(ids),
    "retrieved_pine_strategy_count":sum(x["strategy_source_status"]=="PINE_RETRIEVED_FROM_PINNED_MIRROR" for x in allrows),
    "native_python_generated_count":sum(x["conversion_status"]=="PYTHON_GENERATED_UNVALIDATED" for x in allrows),
    "library_missing_strategy_count":sum(x["conversion_status"]=="BLOCKED_INCOMPLETE_LIBRARY_DEPENDENCIES" for x in allrows),
    "unique_library_references":len(usages),
    "repeat_library_references":sum(len(x)>1 for x in usages.values()),
    "direct_library_import_occurrences":sum(int(x["direct_import_count"] or 0) for x in allrows),
    "states":states,
    "parity_validated_count":0,
    "note":"Pine mirror source unverified against original TradingView revision; exact libraries not provided in source registry and cannot be fabricated",
    "scope_disclaimer":"Native conversion for library-free scripts; import-bearing scripts require exact library sources and dedicated linker or interpreted runtime; no claim of native translation",
}
(out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("AGGREGATE_PASS",json.dumps(summary,ensure_ascii=False),flush=True)
