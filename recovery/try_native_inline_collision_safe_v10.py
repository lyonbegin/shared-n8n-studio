#!/usr/bin/env python3
"""Conservative v10 direct Pine library inliner for namespace/builtin collisions.

In particular, 'import TradingView/ta/7' makes a textual inliner confuse Pine's
built-in ta.ema/ta.sma with external library symbols. This emitter rewrites ONLY
verified exported library function calls; recognized built-ins are preserved.
Unknown symbols, source SHA mismatches, imports with required transitive
functions, UDT exports, and unsafe captures are rejected, not guessed.
All emitted Python is explicitly UNVALIDATED (not TradingView parity).
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re
from pathlib import Path
import try_native_inline_batch as base
from try_multiline_function_inline import parse_pure_functions

# Explicit allowlist: symbols in Pine's built-in ta namespace, not in the
# pinned TradingView/ta Library's exports. Deliberately fail for unknown names.
BUILTIN_TA = set("""
alma atr barssince bb bbw cci change cog correlation cross crossover crossunder
cum dev dmi ema falling highest highestbars hma kc kcw linreg lowest lowestbars
macd max median mfi min mom percentile_linear_interpolation
percentile_nearest_rank percentrank pivothigh pivotlow range rising rma roc rsi
sar sma stdev stoch supertrend swma tr tsi valuewhen variance vwap vwma wma
wpr willr fisher
""".split())
ALIASES = {"ta"}
LIB_DECL = re.compile(r'(?m)^\s*library\s*\(\s*(?:title\s*=\s*)?["\x27]([^"\x27]+)')
NAME_RE = re.compile(r'\b([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)')

def safe_references(script, alias, ref, exported):
    used = set(re.findall(r'\b'+re.escape(alias)+r'\s*\.\s*([A-Za-z_]\w*)',script))
    available=set(exported)
    library_calls=used & available
    unknown=used - available
    # Only ta builtin collisions are known and explicitly supported. If the
    # source uses a Library export and built-in with same name, it is ambiguous.
    if alias=="ta" and ref.split("/")[1]=="ta":
        if unknown - BUILTIN_TA:
            raise ValueError("UNKNOWN_TA_SYMBOLS:"+",".join(sorted(unknown-BUILTIN_TA)))
        if library_calls & BUILTIN_TA:
            raise ValueError("AMBIGUOUS_TA_SYMBOLS:"+",".join(sorted(library_calls&BUILTIN_TA)))
    elif unknown:
        raise ValueError("NON_LIBRARY_FUNCTION_SYMBOLS:"+",".join(sorted(unknown)))
    return library_calls

def flatten(root):
    root=Path(root)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if not str(manifest["status"]).startswith("DEPENDENCY_COMPLETE"):
        raise ValueError("LIBRARY_CLOSURE_INCOMPLETE")
    script=(root/"strategy.pine").read_text(encoding="utf-8-sig")
    imports=list(base.IMPORT.finditer(script))
    if not imports: raise ValueError("NO_DIRECT_IMPORTS")
    direct={m.group(1) for m in imports}
    if direct!=set(manifest["direct_imports"]):
        raise ValueError("DIRECT_IMPORT_MANIFEST_MISMATCH")
    metadata={obj["ref"]:obj for obj in manifest["libraries"]}
    if not direct.issubset(metadata):
        raise ValueError("LIBRARY_METADATA_MISSING")
    # Reject multi-alias shadowing. Each alias must identify only one ref.
    aliases=[(m.group(2) or m.group(1).split("/")[1]) for m in imports]
    if len(set(aliases))!=len(aliases):
        raise ValueError("IMPORT_ALIAS_COLLISION")
    transitive=set(manifest["transitive_imports"])-direct
    blocks=[];replaced=[];unused=[]
    derived=script
    for m,alias in zip(imports,aliases):
        ref=m.group(1)
        owner,name,version=ref.split("/")
        path=root/"libraries"/owner/name/(version+".pine")
        if not path.is_file() or base.psha(path)!=metadata[ref]["sha256"]:
            raise ValueError("EXACT_LIBRARY_SHA_MISMATCH:"+ref)
        library=path.read_text(encoding="utf-8-sig")
        dec=LIB_DECL.search(library)
        if not dec or dec.group(1)!=name:
            raise ValueError("LIBRARY_DECLARATION_MISMATCH:"+ref)
        # First, establish whether the imported namespace is ever used at all.
        allnames=set(re.findall(r'\b'+re.escape(alias)+r'\s*\.\s*([A-Za-z_]\w*)',derived))
        if not allnames:
            unused.append(ref);continue
        # Parse only safe exported functions. This deliberately refuses UDTs,
        # enums and methods whose semantics cannot be preserved by text inline.
        functions=parse_pure_functions(library)
        names={name for name,exp,body in functions}
        exported={name for name,exp,body in functions if exp}
        called=safe_references(derived,alias,ref,exported)
        if not called:
            unused.append(ref);continue
        if transitive or re.search(r"(?m)^\s*import\s+",library):
            raise ValueError("REQUIRED_TRANSITIVE_LIBRARY_NOT_SUPPORTED")
        needed=set(called)
        byname={n:(exp,body) for n,exp,body in functions}
        # Include helper functions required by an exported call, but not
        # unrelated exports (which frequently use other Pine type features).
        while True:
            before=len(needed)
            for name0 in list(needed):
                body=byname[name0][1]
                for candidate in names:
                    if re.search(r'(?<![\w.])'+re.escape(candidate)+r'\s*\(',body):
                        needed.add(candidate)
            if len(needed)==before:break
        for name0,exposed,block in functions:
            if name0 not in needed:continue
            block=re.sub(r"^export[ \t]+","",block,count=1)
            # Rename the function declaration and same-library helper calls.
            for helper in sorted(needed,key=len,reverse=True):
                block=re.sub(r'(?<![\w.])'+re.escape(helper)+r'(\s*\()',
                             lambda mm,x=helper:alias+"__"+x+mm.group(1),block)
            # Disallow unresolved exported namespace names in the function body.
            if re.search(r'\b'+re.escape(alias)+r'\s*\.\s*[A-Za-z_]',block):
                raise ValueError("UNRESOLVED_LIBRARY_NAMESPACE_CALL:"+ref)
            blocks.append(block)
        for func in sorted(called,key=len,reverse=True):
            derived=re.sub(r'\b'+re.escape(alias)+r'\s*\.\s*'+re.escape(func)+r'\b',
                           alias+"__"+func,derived)
        replaced.append({"ref":ref,"called":sorted(called),"included":sorted(needed)})
    # All exact original import declarations are removed only from the derived
    # copy; original files/versions and per-strategy lock remain unchanged.
    derived=base.IMPORT.sub("",derived)
    if base.IMPORT.search(derived):raise ValueError("UNREMOVED_IMPORT_LINE")
    if blocks:
        insertion=base.strategy_header_end(derived)
        derived=derived[:insertion]+"\n\n"+"\n\n".join(blocks)+"\n\n"+derived[insertion:]
    return derived,{"rewritten":replaced,"unused_imports":unused,
                    "transitive_count":len(transitive)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    p.add_argument("--shard",type=int,default=0);p.add_argument("--shards",type=int,default=2)
    args=p.parse_args()
    root=Path(args.root);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    manifests=sorted(root.glob("strategies/*/manifest.json"))
    selected=[x for x in manifests if json.loads(x.read_text()).get("status","").startswith("DEPENDENCY_COMPLETE")]
    rows=[]
    for i,m in enumerate(selected):
        if i%args.shards!=args.shard:continue
        sid=m.parent.name
        row={"id":sid,"status":"BLOCKED","error":"","python_sha256":"",
             "derived_sha256":"","parity_verified":False,"source_originals_modified":False}
        try:
            code,info=flatten(m.parent)
            dest=out/"strategies"/sid;dest.mkdir(parents=True,exist_ok=True)
            (dest/"derived_inline.pine").write_text(code,encoding="utf-8")
            row["derived_sha256"]=base.sha(code)
            row.update(info)
            try:
                py=base.compile_pine(code,expected_sha=base.sha(code),timeout=35)
                (dest/"generated.py").write_text(py,encoding="utf-8")
                row["python_sha256"]=base.sha(py)
                row["status"]="NATIVE_PYTHON_EMITTED_UNVALIDATED"
            except base.FreePineBlocked as ex:
                row["status"]="PYNE_COMPILE_BLOCKED";row["error"]=ex.code
        except Exception as ex:
            row["status"]="SAFE_INLINE_UNSUPPORTED";row["error"]=type(ex).__name__+":"+str(ex)[:200]
        rows.append(row)
        print("LIBRARY_V10_CASE",json.dumps(row,ensure_ascii=False),flush=True)
    (out/"result.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"processed":len(rows),"states":dict(collections.Counter(x["status"] for x in rows)),
             "python_generated":sum(x["status"]=="NATIVE_PYTHON_EMITTED_UNVALIDATED" for x in rows),
             "tradingview_parity_verified":0}
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("LIBRARY_V10_FINAL",json.dumps(summary),flush=True)

if __name__=="__main__":main()
