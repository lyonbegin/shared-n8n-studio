#!/usr/bin/env python3
"""Reprocess ONLY newly recovered Strategy originals absent from the prior PYNE audit.

Runs the existing isolated legacy compiler with immutable originals, never
patches an original or calls production services. Legacy version migration is
an EXPERIMENTAL syntax probe and is NEVER counted as semantic or TV parity.
"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys
from collections import Counter
from pathlib import Path

STATES = {"OFFICIAL_OPEN_SOURCE_RETRIEVED", "OFFICIAL_OPEN_SOURCE_NEEDS_VERSION_REVIEW"}

def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)

def prepare(prior, latest, output):
    fields, old = read(prior)
    _, current = read(latest)
    if len(old) != 4428 or len({r["script_id"] for r in old}) != 4428:
        raise ValueError("PRIOR_AUDIT_NOT_EXACT_4428")
    if len(current) != 4428 or len({r["script_id"] for r in current}) != 4428:
        raise ValueError("LATEST_AUDIT_NOT_EXACT_4428")
    new = {r["script_id"]: r for r in current}
    selected = []
    for row in old:
        sid = row["script_id"]
        fin = new[sid]
        if (row["python_conversion_status"] == "SOURCE_NOT_RECOVERED"
            and fin["current_source_status"] in STATES
            and not fin["direct_imports"].strip()):
            if not fin["source_sha256"] or len(fin["source_sha256"]) != 64:
                raise ValueError("LATEST_SOURCE_SHA_MISSING:" + sid)
            row["source_status"] = fin["current_source_status"]
            row["original_sha256"] = fin["source_sha256"]
            row["import_refs"] = ""
            selected.append(sid)
        else:
            row["source_status"] = "EXCLUDED_ALREADY_AUDITED_OR_NOT_PUBLIC"
    target = Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(old)
    return selected

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prior-audit", required=True)
    p.add_argument("--latest-audit", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--shards", type=int, default=4)
    p.add_argument("--shard", type=int, default=0)
    p.add_argument("--timeout", type=int, default=30)
    args=p.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    selected=prepare(args.prior_audit,args.latest_audit,out/"late_recovery_input.csv")
    if not selected: raise ValueError("NO_LATE_RECOVERY_IDS_FOUND")
    print("LATE_RECOVERY_IDS",len(selected),flush=True)
    (out/"late_recovery_selected_ids.json").write_text(json.dumps(selected,indent=2),encoding="utf-8")
    sub=out/"compiled"
    cmd=[sys.executable,str(Path(__file__).with_name("legacy_version_repair_v1.py")),
         "--sources",args.sources,"--audit",str(out/"late_recovery_input.csv"),
         "--output",str(sub),"--shard",str(args.shard),"--shards",str(args.shards),
         "--timeout",str(args.timeout)]
    subprocess.run(cmd,check=True)
    rows=json.loads((sub/"results.json").read_text(encoding="utf-8"))
    expected=len(selected[args.shard::args.shards])
    if len(rows)!=expected: raise ValueError(f"TARGET_SHARD_INCOMPLETE {len(rows)}/{expected}")
    print("LATE_RECOVERY_FINAL",json.dumps({"selected_total":len(selected),
           "shard":args.shard,"processed":len(rows),
           "states":dict(Counter(x["status"] for x in rows)),
           "parity_verified":0},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
