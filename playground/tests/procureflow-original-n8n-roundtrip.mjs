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
assert.equal(results.length,26);
assert.equal(total,43);
console.log('SHARED_N8N_STUDIO_EXACT_26_ROUNDTRIP_PASS',JSON.stringify({workflows:26,customGates:43,totalNodes:results.reduce((n,x)=>n+x.nodes,0)}));
