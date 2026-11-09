#!/usr/bin/env python3
"""Pine v1/v2 semantic-aware, bounded syntax-migration experiment.

Pine v1/v2 security() default lookahead=ON (v3+ default OFF).
v2 self references can require an explicitly initialized mutable series.
TradingView migration docs: https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-3/
This script changes only copies after original SHA checks. It deliberately
labels all output EXPERIMENTAL and does NOT establish TradingView or order parity.
"""
from __future__ import annotations
import argparse,ast,collections,csv,hashlib,json,os,re,sys
from pathlib import Path

sys.path.insert(0,os.environ.get("WF02_ADAPTER_DIR",""))
from investment_free_pyne import compile_pine, FreePineBlocked
from legacy_version_repair_v1 import VERSION,IMPORT,DECL,HASH

FUNC=re.compile(r"(?<![\w.])security\s*\(")
SELF_LINE=re.compile(r"^([ \t]*)([A-Za-z_]\w*)[ \t]*=[ \t]*(?!=)(.*)$")
# A limited proof obligation: use only numeric nz(var[n]) recurrence and
# top-level declarations; reject all other self-reference patterns.
def split_args(text):
    parts=[];start=0;depth=0;quote=None;esc=False
    for i,c in enumerate(text):
        if quote:
            if esc:esc=False
            elif c=="\\":esc=True
            elif c==quote:quote=None
            continue
        if c in ("'",'"'):quote=c;continue
        if c in "([{":depth+=1
        elif c in ")]}":depth-=1
        elif c=="," and depth==0:
            parts.append(text[start:i].strip());start=i+1
        if depth<0:raise ValueError("FUNCTION_ARGUMENT_NESTING_INVALID")
    if depth!=0 or quote:raise ValueError("UNBALANCED_FUNCTION_ARGUMENTS")
    parts.append(text[start:].strip())
    return parts

def repair_security(source):
    """Preserve documented Pine <=2 lookahead default as an explicit argument."""
    replacements=[]
    for match in FUNC.finditer(source):
        open_idx=match.end()-1;depth=0;quote=None;escape=False;end=None
        for j in range(open_idx,len(source)):
            c=source[j]
            if quote:
                if escape:escape=False
                elif c=="\\":escape=True
                elif c==quote:quote=None
                continue
            if c in ("'",'"'):quote=c;continue
            if c=="(":depth+=1
            elif c==")":
                depth-=1
                if depth==0:end=j;break
        if end is None:raise ValueError("SECURITY_PAREN_NOT_CLOSED")
        current=source[open_idx+1:end]
        args=split_args(current)
        if any(re.match(r"(?i)^lookahead\s*=",arg) for arg in args):
            continue
        if len(args) not in (3,4):
            raise ValueError("SECURITY_ARGUMENT_COUNT_MIGRATION_AMBIGUOUS")
        replacements.append((open_idx+1,end,current+", lookahead=barmerge.lookahead_on"))
    for begin,end,value in reversed(replacements):
        source=source[:begin]+value+source[end:]
    return source,len(replacements)

def repair_self_reference(source):
    lines=source.splitlines(keepends=True)
    changed=0;out=[]
    for line in lines:
        raw=line.rstrip("\r\n")
        newline=line[len(raw):]
        m=SELF_LINE.match(raw)
        if not m:
            out.append(line);continue
        indent,name,rhs=m.groups()
        refs=re.findall(r"(?<![\w.])"+re.escape(name)+r"\s*\[\s*\d+\s*\]",rhs)
        if not refs:
            out.append(line);continue
        if indent:
            raise ValueError("SELF_REF_NON_TOP_LEVEL_REQUIRES_SCOPE_ANALYSIS:"+name)
        if not re.search(r"\bnz\s*\(\s*"+re.escape(name)+r"\s*\[\s*\d+\s*\]",rhs):
            raise ValueError("SELF_REF_WITHOUT_NUMERIC_NZ_GUARD:"+name)
        # This is only an attempt. In particular, the exact Pine v2 runtime
        # behavior must still be compared against official TradingView bars.
        if re.search(r"\b(?:true|false|bool|color|label|line)\b",rhs):
            raise ValueError("NONNUMERIC_SELF_REFERENCE_REQUIRES_TYPE_ANALYSIS:"+name)
        out.append(indent+name+" = 0.0"+newline)
        out.append(indent+name+" := "+rhs+newline)
        changed+=1
    return "".join(out),changed

def derive_v3(raw):
    m=VERSION.search(raw)
    version=int(m.group(1)) if m else 1
    if version>=7:raise ValueError("PINE_FUTURE_UNSUPPORTED")
    out=raw;changes=[]
    if version in (1,2):
        out,count=repair_security(out)
        if count:changes.append("SECURITY_LOOKAHEAD_ON_EXPLICIT:"+str(count))
        out,count=repair_self_reference(out)
        if count:changes.append("NUMERIC_SELF_REFERENCE_INITIALIZATION:"+str(count))
    if version in (1,2,3):
        out=VERSION.sub("//@version=4",out,count=1) if m else "//@version=4\n"+out
        changes.append("HISTORICAL_VERSION_TO_4_EXPERIMENTAL:"+str(version))
    elif not re.search(r"(?m)^\s*//@version\s*=\s*[456]\s*$",out):
        out=VERSION.sub("//@version="+str(version),out,count=1)
        changes.append("VERSION_COMMENT_FORMAT_ONLY")
    return out,version,changes

def scan_blocked(paths):
    result={}
    for folder in paths:
        for f in Path(folder).rglob("results.json"):
            rows=json.loads(f.read_text(encoding="utf-8"))
            for row in rows:
                if row["script_id"] in result:
                    raise ValueError("DUPLICATE_PREVIOUS_RESULT:"+row["script_id"])
                if "UNVALIDATED" not in row["status"]:
                    result[row["script_id"]]=row
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--old-results",required=True)
    p.add_argument("--late-results",required=True)
    p.add_argument("--sources",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--shard",type=int,default=0)
    p.add_argument("--shards",type=int,default=4)
    p.add_argument("--timeout",type=int,default=30)
    args=p.parse_args()
    assert 0<=args.shard<args.shards
    blocked=scan_blocked([args.old_results,args.late_results])
    if len(blocked)!=100:raise ValueError("PREVIOUSLY_BLOCKED_COUNT_NOT_100:"+str(len(blocked)))
    sources={}
    for f in Path(args.sources).rglob("recovered/*/strategy.pine"):
        sid=f.parent.name
        if sid in sources:raise ValueError("DUPLICATE_ORIGINAL:"+sid)
        sources[sid]=f
    output=Path(args.out);output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,sid in enumerate(sorted(blocked)):
        if i%args.shards!=args.shard:continue
        old=blocked[sid]
        record={"script_id":sid,"status":"NOT_STARTED","source_sha256":old["source_sha256"],
                "derived_sha256":"","python_sha256":"","changes":[],"pine_version":"",
                "reason":"","tradingview_parity_verified":False,"order_parity_verified":False}
        try:
            file=sources.get(sid)
            if not file:raise ValueError("LATEST_ORIGINAL_NOT_FOUND")
            data=file.read_bytes()
            if HASH(data)!=old["source_sha256"]:
                raise ValueError("LATEST_ORIGINAL_SHA_MISMATCH")
            source=data.decode("utf-8-sig")
            if IMPORT.search(source):raise ValueError("EXTERNAL_LIBRARY_PRESENT")
            if not DECL.search(source):raise ValueError("STRATEGY_DECLARATION_NOT_FOUND")
            changed,version,events=derive_v3(source)
            target=output/"strategies"/sid;target.mkdir(parents=True,exist_ok=True)
            (target/"original.pine").write_bytes(data)
            (target/"derived_v3.pine").write_text(changed,encoding="utf-8")
            record["derived_sha256"]=HASH(changed.encode())
            record["changes"]=events
            record["pine_version"]=version
            generated=compile_pine(changed,expected_sha=record["derived_sha256"],timeout=args.timeout)
            ast.parse(generated)
            (target/"generated.py").write_text(generated,encoding="utf-8")
            record["python_sha256"]=HASH(generated.encode())
            record["status"]="EXPERIMENTAL_LEGACY_MIGRATION_PYTHON_GENERATED_UNVALIDATED"
        except FreePineBlocked as exc:
            record["status"]="COMPILER_BLOCKED";record["reason"]=exc.code
        except Exception as exc:
            record["status"]="SEMANTIC_REVIEW_REQUIRED";record["reason"]=str(exc)[:300]
        rows.append(record)
        print("LEGACY_V3_CASE",json.dumps(record,ensure_ascii=False),flush=True)
    (output/"results.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"input_blocked":len(blocked),"processed":len(rows),
             "states":dict(collections.Counter(x["status"] for x in rows)),
             "source_preserved":True,"tradingview_parity_verified":0}
    (output/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LEGACY_V3_FINAL",json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
