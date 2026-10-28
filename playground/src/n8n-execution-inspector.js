import {parse as parseFlatted} from 'flatted';
/**
 * Import REAL n8n execution-result JSON (exported by the official runtime).
 * Read-only; no fake execution, API calls, Python engines or brokerage actions.
 * Imported files are untrusted: never render raw HTML, keep them in memory only.
 */
const REDACT=/^(authorization|cookie|set-cookie|x-api-key|api[-_]?key|token|access[-_]?token|refresh[-_]?token|password|passwd|secret|client[-_]?secret|credential|private[-_]?key)$/i;
const MAX_FILE=2_000_000,MAX_ITEMS=20,MAX_DEPTH=6,MAX_STRING=900;
export function redactExecutionValue(v,depth=0,seen=new WeakSet()){
 if(depth>MAX_DEPTH)return '[truncated depth]';
 if(typeof v==='string'){
   return v.slice(0,MAX_STRING).replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi,'Bearer [REDACTED]');
 }
 if(v===null||typeof v==='boolean'||typeof v==='number')return v;
 if(typeof v!=='object')return String(v);
 if(seen.has(v))return '[circular]';
 seen.add(v);
 if(Array.isArray(v))return v.slice(0,MAX_ITEMS).map(x=>redactExecutionValue(x,depth+1,seen));
 const out={};
 for(const [k,val] of Object.entries(v).slice(0,MAX_ITEMS)){
  out[k]=REDACT.test(k)?'[REDACTED]':redactExecutionValue(val,depth+1,seen);
 }
 return out;
}
function executionData(source){
 let data=source?.data;
 if(!data) data=source?.executionData||source?.resultData||source;
 if(typeof data==='string'){
  // Exporters should unpack official n8n flatted serialized data into a JSON
  // object beforehand, rather than interpreting serialized strings as a run.
  try{data=parseFlatted(data)}catch{try{data=JSON.parse(data)}catch{throw Error('실행 data JSON 해석에 실패했습니다');}}
 }
 if(Array.isArray(data))throw Error('배열 형식 실행 data는 지원하지 않습니다');
 if(!data||typeof data!=='object')throw Error('실행 결과 데이터가 없습니다');
 return data?.data?.resultData?data.data:data;
}
export function normalizeN8nExecution(source,originalWorkflow){
 if(!source||typeof source!=='object'||Array.isArray(source))throw Error('실행 JSON 객체가 필요합니다');
 if(!originalWorkflow||!Array.isArray(originalWorkflow.nodes))throw Error('현재 워크플로가 없습니다');
 const data=executionData(source);
 const result=data.resultData||data;
 const runData=result.runData;
 if(!runData||typeof runData!=='object'||Array.isArray(runData))throw Error('공식 n8n resultData.runData가 없습니다');
 const workflow=source.workflowData||source.workflow||data.workflowData;
 const expectedName=new Set(originalWorkflow.nodes.map(n=>n.name));
 // A supplied execution may be from another workflow. Refuse incorrect matches.
 if(workflow?.nodes&&Array.isArray(workflow.nodes)){
  const names=new Set(workflow.nodes.map(n=>n.name));
  if(names.size!==expectedName.size||[...names].some(n=>!expectedName.has(n)))throw Error('현재 워크플로와 다른 실행 결과입니다');
 }
 const runNames=Object.keys(runData);
 if(runNames.length>350||runNames.some(n=>!expectedName.has(n)))throw Error('실행 노드가 현재 워크플로에 속하지 않습니다');
 let errorCount=0;
 const byName={};
 for(const node of originalWorkflow.nodes){
  const steps=runData[node.name]||[];
  if(!Array.isArray(steps))throw Error('노드 실행 기록 형식 오류: '+node.name);
  const latest=steps.at(-1);
  const error=latest?.error||(!latest&&result.error?.node?.name===node.name?result.error:null);
  const status=error?'error':latest?.executionStatus==='running'?'running':latest?'success':'idle';
  if(error)errorCount++;
  // n8n task input is often exposed in executionData.data.main and real
  // output in data.main; do not infer absent values as successful outputs.
  const value=latest?.data?.main ?? latest?.data ?? null;
  const bounded={status,iterations:steps.length,
    startTime:latest?.startTime||null,executionTime:typeof latest?.executionTime==='number'?latest.executionTime:null,
    output:redactExecutionValue(value),input:redactExecutionValue(latest?.inputData??latest?.input??null),
    error:error?redactExecutionValue(error):null};
  byName[node.name]=bounded;
 }
 const finished=source.finished===true||source.status==='success'||source.status==='error';
 const status=source.status==='error'||errorCount?'error':finished?'success':source.status==='running'?'running':'unknown';
 const startedAt=source.startedAt||data.startTime||null;
 const stoppedAt=source.stoppedAt||null;
 return {id:String(source.id||source.executionId||'imported'),workflowId:String(source.workflowId||''),status,
  startedAt,stoppedAt,importedAt:new Date().toISOString(),source:'local_file_unverified',
  nodeResults:byName,executedCount:runNames.length,errorCount};
}
export async function readN8nExecutionFile(file,workflow){
 if(!file||typeof file.size!=='number'||file.size>MAX_FILE)throw Error('실행 JSON은 2MB 이하만 가능합니다');
 const text=await file.text();
 return normalizeN8nExecution(JSON.parse(text),workflow);
}
