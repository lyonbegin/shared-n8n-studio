import {stringify as stringifyFlatted} from 'flatted';
import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeN8nExecution,redactExecutionValue,readN8nExecutionFile} from '../src/n8n-execution-inspector.js';
const workflow={nodes:[{id:'x',name:'Safe Manual Trigger',type:'n8n-nodes-base.manualTrigger'},{id:'y',name:'Safe NoOp',type:'n8n-nodes-base.noOp'}]};
const record={
 id:'e2e-safe-123',workflowId:'test-only',status:'success',finished:true,
 startedAt:'2026-10-29T00:00:00Z',
 data:{resultData:{runData:{
  'Safe Manual Trigger':[{startTime:1000,executionTime:2,data:{main:[[{json:{hello:'test',password:'very_secret'}}]]}}],
  'Safe NoOp':[{startTime:1003,executionTime:5,data:{main:[[{json:{ok:true,authorization:'Bearer xyz_token_data'}}]]}}],
 }}}
};
test('n8n success with node output and masked secrets',()=>{
 const v=normalizeN8nExecution(record,workflow);
 assert.equal(v.status,'success');
 assert.equal(v.executedCount,2);
 assert.equal(v.errorCount,0);
 assert.equal(v.nodeResults['Safe Manual Trigger'].status,'success');
 assert.equal(v.nodeResults['Safe Manual Trigger'].output[0][0].json.password,'[REDACTED]');
 assert.equal(v.nodeResults['Safe NoOp'].output[0][0].json.authorization,'[REDACTED]');
 assert.equal(v.source,'local_file_unverified');
});
test('partial / failed execution retains per-node errors and does not fake unrun nodes',()=>{
 const raw=structuredClone(record);
 delete raw.data.resultData.runData['Safe NoOp'];
 raw.status='error';raw.finished=false;
 raw.data.resultData.runData['Safe Manual Trigger'][0].error={message:'credential error',headers:{cookie:'sensitive'}};
 const v=normalizeN8nExecution(raw,workflow);
 assert.equal(v.status,'error');
 assert.equal(v.nodeResults['Safe Manual Trigger'].status,'error');
 assert.equal(v.nodeResults['Safe Manual Trigger'].error.headers.cookie,'[REDACTED]');
 assert.equal(v.nodeResults['Safe NoOp'].status,'idle');
});
test('reject execution from a different workflow, foreign nodes, and missing runData',()=>{
 const other=structuredClone(record);other.data.resultData.runData.Injected=[{data:{main:[]}}];
 assert.throws(()=>normalizeN8nExecution(other,workflow),/속하지 않습니다/);
 assert.throws(()=>normalizeN8nExecution({data:{resultData:{}}},workflow),/runData/);
 const wrong=structuredClone(record);wrong.workflowData={nodes:[{name:'Safe Manual Trigger'}]};
 assert.throws(()=>normalizeN8nExecution(wrong,workflow),/다른 실행 결과/);
});
test('bounded nested value masks key, bearer and circular data',()=>{
 const r={Authorization:'x',safe:'Bearer aaa.bbb.ccc',nested:{apiKey:'secret'}};
 r.self=r;
 const v=redactExecutionValue(r);
 assert.equal(v.Authorization,'[REDACTED]');
 assert.equal(v.nested.apiKey,'[REDACTED]');
 assert.equal(v.self,'[circular]');
 assert.equal(v.safe,'Bearer [REDACTED]');
});
test('execution file must be <= 2MB',async()=>{
 await assert.rejects(readN8nExecutionFile({size:2_000_001,text:async()=>''},workflow),/2MB/);
 const file={size:300,text:async()=>JSON.stringify(record)};
 const imported=await readN8nExecutionFile(file,workflow);
 assert.equal(imported.nodeResults['Safe NoOp'].status,'success');
});

test('official n8n flatted execution data can be decoded',()=>{
 const source={...record,data:stringifyFlatted(record.data)};
 const imported=normalizeN8nExecution(source,workflow);
 assert.equal(imported.nodeResults['Safe Manual Trigger'].status,'success');
 assert.equal(imported.nodeResults['Safe NoOp'].output[0][0].json.authorization,'[REDACTED]');
});
