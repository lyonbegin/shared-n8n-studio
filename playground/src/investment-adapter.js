// Stock-project data adapter for the one shared Vue Flow editor.
// This module has NO workflow execution privileges. Original n8n node types,
// parameters, options and connection ordering are preserved for JSON export.
import {NODE_CATALOG} from './node-catalog.js';
const map=new Map(NODE_CATALOG.filter(x=>x.nativeType).map(x=>[x.nativeType,x.kind]));
map.set('n8n-nodes-base.respondToWebhook','webhook');
map.set('n8n-nodes-base.noOp','code');
export const STOCK_WORKFLOWS=Object.freeze([
 ['operations/WF02-pine-to-python.json','WF-02 상세 48노드 · Pine→Python 변환·동등성'],
 ['operations/WF01-pine-source-intake-v2.json','WF-01 상세 31노드 · 원본 등록·권리 재확인'],
 ['operations/WF01-pine-source-intake.json','WF-01 Pine 원본 등록·라이선스 검토'],
 ['operations/F01-strategy-sync.json','F01 전략 증분 수집'],
 ['operations/F03-agent-allocation.json','F03 에이전트 할당'],
 ['operations/F05-independent-audit.json','F05 독립 감사'],
 ['scenarios/01-new-strategy.json','01 신규 전략 수집'],
 ['scenarios/02-version-update.json','02 전략 버전 변경'],
 ['scenarios/03-capital-race.json','03 자본 배분 경쟁'],
 ['scenarios/04-partial-fill.json','04 부분 체결'],
 ['scenarios/05-long-backtest.json','05 장기 백테스트'],
 ['scenarios/06-strategy-drift.json','06 전략 드리프트'],
 ['scenarios/07-broker-timeout.json','07 브로커 타임아웃'],
 ['scenarios/08-agent-crash.json','08 에이전트 중단'],
 ['scenarios/09-unsupported-pine.json','09 지원 불가 Pine'],
 ['scenarios/10-strategy-retire.json','10 전략 폐기'],
]);
const deep=v=>JSON.parse(JSON.stringify(v));
export function fromN8nWorkflow(workflow){
 if(!workflow||!Array.isArray(workflow.nodes)||typeof workflow.connections!=='object'||!workflow.connections)throw Error('n8n 워크플로 형식이 올바르지 않습니다');
 const nodes=workflow.nodes.map((node,i)=>({
  id:String(node.id||'n8n-import-'+i),
  type:'studio',position:{x:Number(node.position?.[0])||0,y:Number(node.position?.[1])||0},
  data:{kind:map.get(node.type)||'business-operation',label:String(node.name||node.type),description:'원본 n8n 노드: '+node.type,
   state:'idle',parameters:deep(node.parameters||{}),disabled:!!node.disabled,
   n8n:deep(node)}
 }));
 const byName=new Map(nodes.map(n=>[n.data.label,n]));
 const edges=[];let seq=0;
 for(const [sourceName,outputTypes] of Object.entries(workflow.connections)){
  const source=byName.get(sourceName);if(!source)continue;
  for(const [connectionType,outputPorts] of Object.entries(outputTypes||{})){
   for(let sourceIndex=0;sourceIndex<(outputPorts||[]).length;sourceIndex++){
    for(const target of outputPorts[sourceIndex]||[]){
     const destination=byName.get(target.node);if(!destination)continue;
     edges.push({id:'stock-edge-'+(++seq),source:source.id,target:destination.id,
      type:'smoothstep',
      sourceHandle:source.data.kind==='if'?(sourceIndex===0?'true':'false'):'main',
      targetHandle:'main',
      data:{n8nConnectionType:connectionType,n8nSourceIndex:sourceIndex,n8nTargetIndex:target.index||0}});
    }
   }
  }
 }
 return {nodes,edges,workflowName:String(workflow.name||'Stock workflow'),original:deep(workflow)};
}
export function toN8nWorkflow({original,nodes,edges,workflowName}){
 if(!Array.isArray(nodes)||!Array.isArray(edges))throw Error('그래프 누락');
 const out=deep(original||{});
 const names=new Map();
 out.name=workflowName||out.name||'Investment workflow';
 out.active=false;
 out.nodes=nodes.map((n,i)=>{
  const previous=n.data?.n8n;
  const known=NODE_CATALOG.find(x=>x.kind===n.data?.kind);
  // Existing native node type is authoritative. Never silently replace an
  // unsupported existing node with Code/noOp or drop its original settings.
  const type=previous?.type||known?.nativeType;
  if(!type)throw Error('실행 어댑터 없는 '+n.data?.kind+' 노드는 n8n JSON으로 내보낼 수 없습니다');
  const value=previous?deep(previous):{id:n.id,type,typeVersion:1,parameters:{}};
  value.id=n.id;value.name=String(n.data?.label||value.name||'Node');
  value.position=[Math.round(n.position.x),Math.round(n.position.y)];
  value.parameters=deep(n.data?.parameters||{});
  value.disabled=!!n.data?.disabled;
  names.set(n.id,value.name);
  return value;
 });
 if(new Set(names.values()).size!==names.size)throw Error('노드 이름이 중복되어 n8n 연결을 복원할 수 없습니다');
 out.connections={};
 for(const e of edges){
  const source=names.get(e.source),target=names.get(e.target);
  if(!source||!target)throw Error('존재하지 않는 노드를 연결했습니다');
  const kind=nodes.find(n=>n.id===e.source)?.data?.kind;
  const index=Number.isInteger(e.data?.n8nSourceIndex)?e.data.n8nSourceIndex:kind==='if'&&e.sourceHandle==='false'?1:0;
  const type=e.data?.n8nConnectionType||'main';
  const targetIndex=e.data?.n8nTargetIndex||0;
  out.connections[source]??={};
  out.connections[source][type]??=[];
  while(out.connections[source][type].length<=index)out.connections[source][type].push([]);
  out.connections[source][type][index].push({node:target,type,index:targetIndex});
 }
 return out;
}
