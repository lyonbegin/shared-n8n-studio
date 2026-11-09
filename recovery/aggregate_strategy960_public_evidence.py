#!/usr/bin/env python3
"""Merge public status audit for exactly 960 restricted Strategy IDs."""
import csv,json
from collections import Counter
from pathlib import Path

root=Path("collected")
csvs=sorted(root.glob("strategy960-audit-shard-*/public_visibility_audit.csv"))
if len(csvs)!=4:raise RuntimeError("EXPECTED_FOUR_SHARDS:"+str(csvs))
rows=[]
for path in csvs:
    with path.open(encoding="utf-8-sig",newline="") as f:
        part=list(csv.DictReader(f))
        assert len(part)==240,(path,len(part))
        rows.extend(part)
ids=[r["script_id"] for r in rows]
assert len(rows)==960 and len(set(ids))==960
counts=Counter(x["catalog_visibility"] for x in rows)
assert counts=={"PROTECTED":452,"INVITE_ONLY":508},counts
assert not any(x["source_code_retrieved"]!="False" for x in rows)
out=Path("strategy960_final");out.mkdir(exist_ok=True)
with (out/"strategy960_all_public_evidence.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(sorted(rows,key=lambda x:x["script_id"]))
with (out/"strategy960_author_source_request_queue.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.writer(f)
    w.writerow(["script_id","strategy_title","catalog_visibility","original_url",
                "required_author_material","exact_source_acquired",
                "public_github_links_unverified","next_action"])
    for r in sorted(rows,key=lambda x:x["script_id"]):
        w.writerow([r["script_id"],r["title"],r["catalog_visibility"],
           r["tradingview_url"],
           "author-provided original Pine source + license/permission + version and all recursive libraries",
           "NO",r["author_public_github_links_unverified"],
           "Obtain author's independently authorized source or explicit author publication; do not bypass TradingView"])
summary={
  "total_audited":960,"protected":452,"invite_only":508,
  "public_http_statuses":dict(Counter(r["public_page_http"] for r in rows)),
  "public_page_script_id_present":sum(r["script_id_present"]=="True" for r in rows),
  "github_link_items_unverified":sum(bool(r["author_public_github_links_unverified"]) for r in rows),
  "original_pine_from_restricted_publications_retrieved":0,
  "author_approved_original_source_confirmed":0,
  "source_rights_review":"REQUIRED",
  "source_recovery_conditions":"Public independently licensed original source or author-provided original with explicit permission and exact version; all libraries then recursively packaged",
  "classification_origin":"Original TradingView access code, not reconfirmed source-code permissions",
}
(out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print("STRATEGY960_AUDIT_COMPLETE",json.dumps(summary,ensure_ascii=False),flush=True)
