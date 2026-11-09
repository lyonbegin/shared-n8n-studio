#!/usr/bin/env python3
"""Multiline pure function export parser for safe original-source-preserving inline.

Refuses UDT/method/enum. Library and Strategy SHA constraints are enforced
by existing native inline modules; generated Python is NOT parity validated.
"""
from __future__ import annotations
import re,sys
def parse_pure_functions(source):
 if re.search(r'(?m)^export[ \t]+(?:method|type|enum)\b',source):
  raise ValueError('UDT_METHOD_OR_ENUM_EXPORT_UNSUPPORTED')
 lines=source.splitlines(keepends=True);starts=[]
 start_re=re.compile(r'^(export\s+)?([A-Za-z_]\w*)\s*\(')
 for i,line in enumerate(lines):
  if not line or line[0] in ' \t' or line.lstrip().startswith('//'):continue
  m=start_re.match(line)
  if m and m.group(2) not in ('library','strategy','indicator'):
   starts.append((i,m.group(2),bool(m.group(1))))
  elif line.startswith('export '):raise ValueError('OTHER_UNSUPPORTED_EXPORT')
 if not starts:raise ValueError('NO_FUNCTION_DECLARATIONS')
 out=[]
 for start,name,exported in starts:
  chunk='';end_signature=None;parens=0;quote=None;escape=False
  for i in range(start,min(start+40,len(lines))):
   s=lines[i];chunk+=s
   for ch in s:
    if quote:
     if escape:escape=False
     elif ch=='\\':escape=True
     elif ch==quote:quote=None
    elif ch in ('"',"'"):quote=ch
    elif ch=='(':parens+=1
    elif ch==')':parens-=1
   if parens<0:raise ValueError('FUNCTION_SIGNATURE_PARENTHESIS_UNBALANCED')
   if parens==0 and '=>' in chunk:end_signature=i+1;break
  if end_signature is None:raise ValueError('MULTILINE_SIGNATURE_MISSING_ARROW')
  end=end_signature
  while end<len(lines):
   s=lines[end]
   if not s.strip() or s.lstrip().startswith('//'):
    end+=1;continue
   if not s.startswith((' ','\t')):break
   end+=1
  out.append((name,exported,''.join(lines[start:end])))
 return out

def main():
 import try_native_inline_batch as direct
 import try_transitive_function_inline as trans
 direct.functions_only=parse_pure_functions
 trans.functions_only=parse_pure_functions
 if '--transitive' in sys.argv:
  sys.argv.remove('--transitive');trans.main()
 else:direct.main()
if __name__=='__main__':
 s='//@version=6\nlibrary("test")\nexport add(\n  float a,\n  float b\n) =>\n    a+b\nexport twice(float x) =>\n    add(x,x)\n'
 assert len(parse_pure_functions(s))==2
 print('MULTILINE_PARSER_SELFTEST_PASS',flush=True)
 main()
