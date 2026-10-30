// Project-neutral regression for original n8n JSON -> shared Vue Flow -> n8n JSON.
// Runs offline on ORIGINAL ProcureFlow PF/S files; does not access production DB.
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {join} from 'node:path';
import {fromN8nWorkflow,toN8nWorkflow} from '../src/investment-adapter.js';

const operational=process.env.PF_OPERATIONS_DIR;
const scenarios=process.env.PF_SCENARIOS_DIR;
if(!operational||!scenarios)throw Error('Set PF_OPERATIONS_DIR and PF_SCENARIOS_DIR');
const fixtureIds=[...Array.from({length:16},(_,i)=>'PF'+String(i).padStart(2,'0')),
  ...Array.from({length:10},(_,i)=>'S'+String(i+1).padStart(2,'0'))];
const results=[];
let total=0;
for(const id of fixtureIds){
  const file=join(id.startsWith('PF')?operational:scenarios,id+'.json');
  const original=JSON.parse(await readFile(file,'utf8'));
  const graph=fromN8nWorkflow(original);
  const restored=toN8nWorkflow({...graph,nodes:graph.nodes,edges:graph.edges});
  const wanted=structuredClone(original);
  wanted.active=false; // deliberate safety policy of Studio export
  try { assert.deepStrictEqual(restored,wanted); }
  catch(err) {
    console.error('ROUNDTRIP_DIFF',id,err.message.slice(0,3500));
    throw err;
  }
  const custom=graph.nodes.filter(n=>n.data.n8n?.type==='CUSTOM.procureFlowBusinessOperation');
  for(const node of custom){
    const ports=original.connections?.[node.data.label]?.main||[];
    for(const idx of [0,1])if(ports[idx]?.length){
      assert(graph.edges.some(e=>e.source===node.id&&e.data?.n8nSourceIndex===idx),
        id+': missing native success/HOLD port '+idx);
    }
  }
  results.push({id,nodes:graph.nodes.length,edges:graph.edges.length,custom:custom.length});
  total+=custom.length;
}
// Mutation round-trip: change an existing business operation node, preserving
// its original n8n type, operation ID, success/HOLD output indices and neighbor edges.
const pf05=JSON.parse(await readFile(join(operational,'PF05.json'),'utf8'));
const editable=fromN8nWorkflow(pf05);
const op=editable.nodes.find(n=>n.data.n8n?.type==='CUSTOM.procureFlowBusinessOperation'
  &&editable.edges.some(e=>e.source===n.id&&e.data.n8nSourceIndex===1));
assert(op,'PF05 needs a real 2-output Business Operation gate');
const oldName=op.data.label;
const newName=oldName+' · 검사편집';
const revisedNodes=editable.nodes.map(n=>n.id!==op.id?n:{
  ...n,position:{...n.position,x:n.position.x+115,y:n.position.y+35},
  data:{...n.data,label:newName}
});
const changed=toN8nWorkflow({original:editable.original,nodes:revisedNodes,
  edges:editable.edges,workflowName:editable.workflowName});
const current=changed.nodes.find(n=>n.name===newName);
assert(current,'Renamed native business gate must survive export');
assert.equal(current.type,'CUSTOM.procureFlowBusinessOperation');
assert.equal(current.parameters.operationId,op.data.parameters.operationId);
assert.deepEqual(current.position,[op.position.x+115,op.position.y+35]);
assert(!Object.hasOwn(changed.connections,oldName),'Old name must not leave dangling source edges');
assert.deepEqual(changed.connections[newName]?.main,
  pf05.connections[oldName]?.main,'Both native success/HOLD ports must be preserved by rename');
assert.equal(changed.active,false);
assert.equal(pf05.nodes.find(n=>n.id===op.id).name,oldName,'Original must be immutable');
console.log('SHARED_N8N_STUDIO_NATIVE_EDIT_PORTS_RENAME_PASS',JSON.stringify({
  renamed:op.data.parameters.operationId,outputs:changed.connections[newName].main.length
}));

assert.equal(results.length,26);
assert.equal(total,43);
console.log('SHARED_N8N_STUDIO_EXACT_26_ROUNDTRIP_PASS',JSON.stringify({workflows:26,customGates:43,totalNodes:results.reduce((n,x)=>n+x.nodes,0)}));
