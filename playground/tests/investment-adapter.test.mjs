import test from 'node:test';
import assert from 'node:assert/strict';
import {STOCK_WORKFLOWS,fromN8nWorkflow,toN8nWorkflow} from '../src/investment-adapter.js';
const original={
 name:'F01 전략 수집',nodes:[
  {id:'a',name:'관리자 수동 실행',type:'n8n-nodes-base.manualTrigger',typeVersion:1,position:[240,320],parameters:{}},
  {id:'b',name:'운영 서비스 실행',type:'n8n-nodes-base.httpRequest',typeVersion:4.2,position:[550,320],parameters:{url:'http://invest-backend:8000/api/v1/ops/strategies/sync',authentication:'genericCredentialType',genericAuthType:'httpHeaderAuth'},credentials:{httpHeaderAuth:{id:'credential_ref_only',name:'ref'}},disabled:false}
 ],connections:{'관리자 수동 실행':{main:[[{node:'운영 서비스 실행',type:'main',index:0}]]}},
 settings:{executionOrder:'v1'},meta:{version:'preserved'},active:false
};
test('stock project must load all 13 original workflow entries',()=>{
 assert.equal(STOCK_WORKFLOWS.length,13);
 assert.equal(STOCK_WORKFLOWS.filter(x=>x[0].startsWith('operations/')).length,3);
});
test('real n8n node type/params/credentials remain unchanged on shared editor round-trip',()=>{
 const converted=fromN8nWorkflow(original);
 assert.equal(converted.nodes.length,2);
 assert.equal(converted.edges.length,1);
 assert.equal(converted.nodes[1].data.kind,'http');
 const exported=toN8nWorkflow(converted);
 assert.deepEqual(exported.nodes[1].parameters,original.nodes[1].parameters);
 assert.deepEqual(exported.nodes[1].credentials,original.nodes[1].credentials);
 assert.deepEqual(exported.connections,original.connections);
 assert.deepEqual(exported.settings,original.settings);
 assert.equal(exported.active,false);
});
test('canvas node movement and rename survive n8n JSON export',()=>{
 const converted=fromN8nWorkflow(original);
 converted.nodes[1].position={x:888,y:222};
 converted.nodes[1].data.label='운영 서비스 실행 (변경)';
 const exported=toN8nWorkflow(converted);
 assert.deepEqual(exported.nodes[1].position,[888,222]);
 assert.equal(exported.connections['관리자 수동 실행'].main[0][0].node,'운영 서비스 실행 (변경)');
});
test('unimplemented 50-kind extension is never misrepresented as executable node',()=>{
 const converted=fromN8nWorkflow(original);
 converted.nodes.push({id:'extra',type:'studio',position:{x:8,y:9},data:{kind:'join-quorum',label:'QUORUM',parameters:{}}});
 assert.throws(()=>toN8nWorkflow(converted),/실행 어댑터 없는/);
});
test('unsupported existing original n8n type is retained exactly',()=>{
 const src=structuredClone(original);src.nodes[1].type='n8n-nodes-base.respondToWebhook';
 const result=toN8nWorkflow(fromN8nWorkflow(src));
 assert.equal(result.nodes[1].type,'n8n-nodes-base.respondToWebhook');
});
