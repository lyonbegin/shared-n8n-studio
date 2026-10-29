<script setup>
import {ref, computed, watch, onMounted, onBeforeUnmount, defineComponent, h, nextTick} from 'vue';
import {VueFlow, Handle, Position, MarkerType, useVueFlow} from '@vue-flow/core';
import {Background} from '@vue-flow/background';
import {Controls} from '@vue-flow/controls';
import {MiniMap} from '@vue-flow/minimap';
import {NODE_CATALOG,NODE_GROUPS,NODE_BY_KIND,defaultParameters,visibleFields,validateParameters} from './node-catalog.js';
import {STOCK_WORKFLOWS,fromN8nWorkflow,toN8nWorkflow} from './investment-adapter.js';
import {PROCURE_WORKFLOWS} from './procurement-adapter.js';
import {readN8nExecutionFile} from './n8n-execution-inspector.js';

const STUDIO_PROJECT=import.meta.env.VITE_EDITOR_PROJECT;
const IS_PROCUREMENT=STUDIO_PROJECT==='procurement';
const STOCK_MODE=STUDIO_PROJECT==='investment'||IS_PROCUREMENT;
const projectLabel=IS_PROCUREMENT?'조달청 자동화':'투자 자동화';
const projectEnglish=IS_PROCUREMENT?'ProcureFlow':'Investment';
const projectNoun=IS_PROCUREMENT?'조달청':'주식';
const STORAGE_KEY='shared-n8n-studio:playground:v1';
const stockMode=STOCK_MODE;
const stockWorkflows=IS_PROCUREMENT?PROCURE_WORKFLOWS:STOCK_WORKFLOWS;
const stockFlow=ref(stockWorkflows[0][0]);
const stockOriginal=ref(null);
const stockServerVersion=ref(0);
const stockServerState=ref('');
const stockServerAvailable=ref(false);
const stockVersionRows=ref([]);
const importedExecution=ref(null);
const fixtureRun=ref(null);
const fixtureError=ref('');
const fixtureSuite=ref(null);
function paintFixture(){
 if(!fixtureRun.value)return;
 const history=fixtureRun.value.events;
 nodes.value=nodes.value.map(n=>{
  const found=history.find(x=>n.data.label.includes(x.event)||n.data.label.includes(x.flow+' '));
  return {...n,data:{...n.data,state:found?'success':'idle',stateSource:found?'fixture':''}};
 });
}
async function beginFixture(){
 if(!IS_PROCUREMENT)return;
 fixtureError.value='';
 if(!/^scenarios\/S(?:0[1-9]|10)\.json$/.test(stockFlow.value)){
  fixtureError.value='S01~S10 시나리오에서만 모의 실행할 수 있습니다';return;
 }
 try{
  if(!fixtureSuite.value){
   const response=await fetch('/procure-workflows/fixture-scenarios.json',{cache:'no-store'});
   if(!response.ok)throw Error('모의 시나리오 파일 없음');
   fixtureSuite.value=await response.json();
  }
  if(fixtureSuite.value.origin!=='fictional_test_fixtures'||fixtureSuite.value.never_calls_official_api!==true)throw Error('안전한 테스트 원본 아님');
  const id=stockFlow.value.split('/').pop().replace('.json','');
  const spec=fixtureSuite.value.scenarios.find(x=>x.id===id);
  if(!spec)throw Error('시나리오를 찾을 수 없음');
  fixtureRun.value={id,executionId:'MOCK-'+Date.now().toString(36),status:'paused',cursor:0,events:[],
   state:JSON.parse(JSON.stringify(fixtureSuite.value.base_state)),steps:spec.steps,expected:spec.expected};
  paintFixture();announce(id+' 가상 단계 실행 준비');
 }catch(e){fixtureError.value=String(e.message||e);}
}
function nextFixture(){
 const r=fixtureRun.value;if(!r||r.status==='stopped'||r.cursor>=r.steps.length)return;
 const s=r.steps[r.cursor],before=JSON.parse(JSON.stringify(r.state));
 r.state={...r.state,...s.patch};
 r.events=[...r.events,{sequence:r.cursor+1,flow:s.flow,event:s.event,input:before,output:JSON.parse(JSON.stringify(r.state)),simulationOnly:true}];
 r.cursor++;r.status=r.cursor===r.steps.length?'completed':'paused';
 fixtureRun.value={...r};paintFixture();announce('MOCK '+s.flow+' / '+s.event);
}
function runFixture(){if(!fixtureRun.value)return;while(fixtureRun.value.cursor<fixtureRun.value.steps.length&&fixtureRun.value.status!=='stopped')nextFixture();}
function stopFixture(){if(fixtureRun.value)fixtureRun.value={...fixtureRun.value,status:'stopped'};}

const runFileInput=ref(null);
const storageKey=()=>stockMode?'shared-n8n-studio:'+STUDIO_PROJECT+':v1:'+stockFlow.value:STORAGE_KEY;
const palette=NODE_CATALOG;
const paletteGroups=NODE_GROUPS;
const paletteMap=NODE_BY_KIND;
let counter=10, edgeCounter=10;
const newId=()=> 'node_'+(++counter);
const edgeId=()=> 'edge_'+(++edgeCounter);
const makeNode=(id,kind,label,x,y,extra={})=>({
  id,type:'studio',position:{x,y},data:{
    kind,label,description:paletteMap[kind]?.description||'',state:'idle',
    parameters:{...defaultParameters(kind),...extra},disabled:false
  }
});
const makeEdge=(source,target)=>({id:edgeId(),source,target,type:'smoothstep',markerEnd:MarkerType.ArrowClosed,style:{stroke:'#97a9bd',strokeWidth:2}});
function makeTemplate(type){
  const texts={
    common:[['trigger','워크플로 시작'],['http','데이터 요청'],['if','조건 확인'],['code','결과 처리'],['wait','재시도 대기']],
    investment:[['webhook','TradingView 이벤트'],['business-operation','투자 Python 엔진 실행'],['join-quorum','분석 결과 합류'],['approval','운용 승인 대기'],['evidence-audit','독립 감사 기록']],
    procurement:[['schedule','공고 조회 시작'],['business-operation','G2B 개찰 수집'],['completeness','10년 수집 완전성'],['approval','참가 승인 대기'],['evidence-audit','공식 증빙 기록']]
  };
  const rows=texts[type]||texts.common;
  const positions=[[110,170],[400,170],[690,170],[1000,170],[705,390]];
  const ns=rows.map(([kind,label],i)=>makeNode('demo_'+type+'_'+i,kind,label,positions[i][0],positions[i][1]));
  const es=[[0,1],[1,2],[2,3],[2,4]].map(([a,b])=>makeEdge(ns[a].id,ns[b].id));
  return {nodes:ns,edges:es};
}
const NodeCard=defineComponent({
  props:{id:{type:String,required:true},data:{type:Object,required:true},selected:Boolean},
  setup(props){
    return ()=> {
      const meta=paletteMap[props.data.kind]||paletteMap.code;
      return h('div',{
        class:['studio-node',props.selected?'is-selected':'',props.data.state==='success'?'is-success':'',props.data.state==='running'?'is-running':'',props.data.state==='error'?'is-error':''],
        'data-testid':'studio-node','data-node-id':props.id,
        style:{'--node-accent':meta.color}
      },[
        ...((meta.inputs||['main']).map((port,i)=>h(Handle,{type:'target',position:Position.Left,id:port,class:'port port-in',title:'입력: '+port,style:{top:((i+1)/(meta.inputs.length+1)*100)+'%'}}))),
        h('div',{class:'node-header'},[
          h('span',{class:'node-icon'},meta.icon),
          h('span',{class:'node-meta'},[
            h('span',{class:'node-name'},props.data.label),
            h('span',{class:'node-type'},meta.name)
          ]),
          h('span',{class:'node-more'},'⋯')
        ]),
        h('div',{class:'node-footer'},[
          h('span',{class:['node-status-dot',props.data.state||'idle']}),
          h('span',props.data.stateSource==='execution_file'?(props.data.state==='error'?'실행 기록: 오류':props.data.state==='success'?'실행 기록: 성공':props.data.state==='running'?'실행 기록: 실행 중':'기록 없음'):props.data.state==='running'?'실행 중':props.data.state==='success'?'모의 성공':'준비됨'),
          h('span',{class:'node-id'},props.id.replace(/^demo_.+?_/, '#'))
        ]),
        ...((meta.outputs||['main']).map((port,i)=>h(Handle,{type:'source',position:Position.Right,id:port,class:'port port-out',title:'출력: '+port,style:{top:((i+1)/(meta.outputs.length+1)*100)+'%'}})))
      ]);
    };
  }
});
const nodeTypes={studio:NodeCard};
const {fitView,zoomIn,zoomOut,screenToFlowCoordinate, getViewport}=useVueFlow({id:'shared-studio-playground'});
const initial=stockMode?{nodes:[],edges:[]}:makeTemplate('common');
const nodes=ref(initial.nodes);
const edges=ref(initial.edges);
const selectedNodeId=ref(null);
const selectedEdgeId=ref(null);
const activeTab=ref('nodes');
const search=ref('');
const groupFilter=ref('all');
const template=ref('common');
const workflowName=ref('Untitled workflow');
const status=ref('편집기를 준비했습니다');
const localSavedAt=ref(null);
const running=ref(false);
const inspectorJson=ref('{}');
const events=ref([{time:new Date().toLocaleTimeString('ko-KR'),text:'독립 편집기 시작 · 서버 연결 없음'}]);
const showHelp=ref(false);
const fileInput=ref(null);
const nodeCount=computed(()=>nodes.value.length);
const edgeCount=computed(()=>edges.value.length);
const selectedNode=computed(()=>nodes.value.find(n=>n.id===selectedNodeId.value)||null);
const selectedEdge=computed(()=>edges.value.find(e=>e.id===selectedEdgeId.value)||null);
const selectedSpec=computed(()=>selectedNode.value?paletteMap[selectedNode.value.data.kind]:null);
const selectedExecutionResult=computed(()=>selectedNode.value&&importedExecution.value?importedExecution.value.nodeResults[selectedNode.value.data.label]||null:null);
const selectedFields=computed(()=>selectedSpec.value?visibleFields(selectedSpec.value,selectedNode.value?.data.parameters||{}):[]);
const catalogStats=computed(()=>({
 native:palette.filter(p=>p.implementation==='native').length,
 composite:palette.filter(p=>p.implementation==='composite').length,
 extension:palette.filter(p=>p.implementation==='extension').length
}));
const filteredPalette=computed(()=>palette.filter(x=>(groupFilter.value==='all'||x.group===groupFilter.value)&&(x.name+' '+x.kind+' '+x.description+' '+x.group+' '+(x.nativeType||'')).toLowerCase().includes(search.value.toLowerCase())));
const canUndo=ref(false),canRedo=ref(false);
let history=[],historyIndex=-1,suspendHistory=false;
function snapshot(){return JSON.stringify({nodes:nodes.value,edges:edges.value,name:workflowName.value,template:template.value});}
function recordHistory(){
  if(suspendHistory)return;
  const state=snapshot();
  if(history[historyIndex]===state)return;
  history=history.slice(0,historyIndex+1);
  history.push(state);
  if(history.length>60)history.shift();
  historyIndex=history.length-1;
  canUndo.value=historyIndex>0;canRedo.value=false;
}
function restoreSnapshot(state){
  suspendHistory=true;
  const data=JSON.parse(state);
  nodes.value=data.nodes;edges.value=data.edges;workflowName.value=data.name;template.value=data.template;
  selectedNodeId.value=null;selectedEdgeId.value=null;
  suspendHistory=false;canUndo.value=historyIndex>0;canRedo.value=historyIndex<history.length-1;
}
function undo(){if(historyIndex<=0)return;historyIndex--;restoreSnapshot(history[historyIndex]);announce('마지막 변경 되돌림');}
function redo(){if(historyIndex>=history.length-1)return;historyIndex++;restoreSnapshot(history[historyIndex]);announce('변경 다시 적용');}
function announce(message){
  status.value=message;
  events.value.unshift({time:new Date().toLocaleTimeString('ko-KR'),text:message});
  if(events.value.length>20)events.value.pop();
}
function onNodeClick({node}){selectedNodeId.value=node.id;selectedEdgeId.value=null;inspectorJson.value=JSON.stringify(node.data.parameters||{},null,2);}
function onEdgeClick({edge}){selectedEdgeId.value=edge.id;selectedNodeId.value=null;}
function onPaneClick(){selectedNodeId.value=null;selectedEdgeId.value=null;}
function onConnect(connection){
  if(!connection.source||!connection.target||connection.source===connection.target)return;
  if(edges.value.some(e=>e.source===connection.source&&e.target===connection.target&&e.sourceHandle===connection.sourceHandle&&e.targetHandle===connection.targetHandle))return;
  edges.value=[...edges.value,{...makeEdge(connection.source,connection.target),sourceHandle:connection.sourceHandle,targetHandle:connection.targetHandle}];
  recordHistory();announce('연결선을 만들었습니다 · '+(connection.sourceHandle||'main')+' → '+(connection.targetHandle||'main'));
}
function onNodeDragStop(){recordHistory();announce('노드 위치 변경');}
function addNode(kind,position){
  const label=paletteMap[kind]?.name||'New node';
  const p=position||{x:180+(nodes.value.length%3)*245,y:185+Math.floor(nodes.value.length/3)*165};
  const n=makeNode(newId(),kind,label,Math.round(p.x),Math.round(p.y));
  nodes.value=[...nodes.value,n];selectedNodeId.value=n.id;selectedEdgeId.value=null;
  inspectorJson.value=JSON.stringify(n.data.parameters,null,2);
  recordHistory();announce(label+' 노드 추가');
}
function onPaletteDragStart(event,kind){event.dataTransfer.setData('application/x-shared-studio-node',kind);event.dataTransfer.effectAllowed='copy';}
function onDragOver(event){if(event.dataTransfer.types.includes('application/x-shared-studio-node'))event.preventDefault();}
function onDrop(event){
  const kind=event.dataTransfer.getData('application/x-shared-studio-node');
  if(!paletteMap[kind])return;
  event.preventDefault();
  addNode(kind,screenToFlowCoordinate({x:event.clientX,y:event.clientY}));
}
function deleteSelected(){
  if(selectedNodeId.value){
    const id=selectedNodeId.value;
    nodes.value=nodes.value.filter(n=>n.id!==id);
    edges.value=edges.value.filter(e=>e.source!==id&&e.target!==id);
    selectedNodeId.value=null;
    recordHistory();announce('노드 삭제');
  }else if(selectedEdgeId.value){
    edges.value=edges.value.filter(e=>e.id!==selectedEdgeId.value);
    selectedEdgeId.value=null;
    recordHistory();announce('연결선 삭제');
  }else announce('삭제할 노드나 연결선을 선택하세요');
}
function onKeyDown(event){
  if(['INPUT','TEXTAREA','SELECT'].includes(event.target?.tagName))return;
  if(event.key==='Delete'||event.key==='Backspace'){event.preventDefault();deleteSelected();}
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();if(event.shiftKey)redo();else undo();}
}
function displayParameter(field){
  const value=selectedNode.value?.data.parameters?.[field.key];
  if(value===null||value===undefined)return '';
  return field.type==='json'?JSON.stringify(value,null,2):String(value);
}
function updateParameter(field,raw){
  if(!selectedNode.value)return;
  try{
    const value=field.type==='json'?JSON.parse(raw):field.type==='number'?Number(raw):field.type==='boolean'?Boolean(raw):raw;
    const next={...selectedNode.value.data.parameters,[field.key]:value};
    const errors=validateParameters(selectedNode.value.data.kind,next);
    if(errors.length)throw Error(errors.join('; '));
    selectedNode.value.data.parameters=next;
    inspectorJson.value=JSON.stringify(next,null,2);
    recordHistory();announce(field.label+' 설정 변경');
  }catch(e){announce('설정 오류: '+e.message);}
}
function applyNodeSettings(){
  const n=selectedNode.value;
  if(!n)return;
  if(!n.data.label.trim()){announce('노드 이름을 입력해 주세요');return;}
  try{
    const parsed=JSON.parse(inspectorJson.value);
    if(!parsed||Array.isArray(parsed)||typeof parsed!=='object')throw Error('JSON 객체가 필요합니다');
    const errors=validateParameters(n.data.kind,parsed);
    if(errors.length)throw Error(errors.join('; '));
    n.data.parameters={...defaultParameters(n.data.kind),...parsed};
    recordHistory();announce('노드 설정을 적용했습니다');
  }catch(e){announce('설정 JSON 오류: '+e.message);}
}
function applyEdgeSettings(){recordHistory();announce('연결선 설정을 변경했습니다');}
async function refreshStockVersions(file=stockFlow.value){
 if(!stockMode||!stockServerAvailable.value)return;
 try{
  const response=await fetch('/api/studio/workflows/'+file+'/versions',{cache:'no-store',credentials:'same-origin'});
  if(!response.ok)throw Error('버전 목록 HTTP '+response.status);
  const payload=await response.json();
  if(stockFlow.value===file)stockVersionRows.value=Array.isArray(payload.versions)?payload.versions:[];
 }catch(err){stockVersionRows.value=[];announce('변경 이력 조회 실패: '+err.message);}
}
async function restoreStockVersion(version){
 if(!stockMode||!stockServerAvailable.value||!Number.isInteger(version))return;
 if(!confirm('서버 버전 v'+version+'을 새 버전으로 복원합니까? 현재 미저장 수정은 유지되지 않습니다.'))return;
 const file=stockFlow.value;
 try{
   const response=await fetch('/api/studio/workflows/'+file+'/versions/'+version,{cache:'no-store',credentials:'same-origin'});
   if(!response.ok)throw Error('이전 버전을 읽지 못했습니다');
   const previous=await response.json();
   const saved=await fetch('/api/studio/workflows/'+file,{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({workflow:previous.workflow,expectedVersion:stockServerVersion.value})});
   const result=await saved.json();
   if(!saved.ok)throw Error(saved.status===409?'다른 탭에서 먼저 저장했습니다':result.error||'복원 실패');
   localStorage.removeItem(storageKey());
   await openStockFlow(file);
   announce('이전 버전 v'+version+'을 서버 v'+result.version+'으로 복원했습니다');
 }catch(err){announce('버전 복원 실패: '+err.message);}
}
function clearImportedExecution(silent=false){
 importedExecution.value=null;
 nodes.value=nodes.value.map(n=>({...n,data:{...n.data,state:'idle',stateSource:null}}));
 if(!silent)announce('외부 실행 결과 표시를 초기화했습니다 · 실제 워크플로는 변경되지 않습니다');
}
async function importN8nExecution(event){
 const file=event.target.files?.[0];event.target.value='';
 if(!file||!stockMode)return;
 try{
  const workflow=toN8nWorkflow({original:stockOriginal.value,nodes:nodes.value,edges:edges.value,workflowName:workflowName.value});
  const result=await readN8nExecutionFile(file,workflow);
  importedExecution.value=result;
  nodes.value=nodes.value.map(n=>{
   const state=result.nodeResults[n.data.label]?.status||'idle';
   return {...n,data:{...n.data,state,stateSource:'execution_file'}};
  });
  announce('공식 n8n 실행 JSON 조회 · '+result.executedCount+'개 기록 · 오류 '+result.errorCount+'개 · 실제 엔진 실행 아님');
 }catch(err){announce('실행 결과 불러오기 실패: '+err.message);}
}
async function openStockFlow(file){
 if(!stockMode||!stockWorkflows.some(([id])=>id===file))return;
 stockFlow.value=file;
 clearImportedExecution(true);
 // Persist route synchronously, not only after network fetch, to avoid
 // restoring a stale F01 when the user reloads immediately after an edit.
 localStorage.setItem('shared-n8n-studio:'+STUDIO_PROJECT+':selected',file);
 const route=new URL(window.location.href);
 route.searchParams.set('workflow',file);
 window.history.replaceState(null,'',route.pathname+route.search+route.hash);
 const stored=localStorage.getItem(storageKey());
 try{
   let data;
   let serverSource=false;
   try{
     const response=await fetch('/api/studio/workflows/'+file,{cache:'no-store',credentials:'same-origin'});
     if(!response.ok)throw Error('서버 HTTP '+response.status);
     const remote=await response.json();
     if(!remote.workflow||!Number.isInteger(remote.version))throw Error('서버 응답 형식 오류');
     stockServerVersion.value=remote.version;
     stockServerAvailable.value=true;
     serverSource=remote.source==='server';
     stockServerState.value=serverSource?'서버 저장본':'원본';
     data=fromN8nWorkflow(remote.workflow);
   }catch(apiError){
     stockServerAvailable.value=false;
     stockVersionRows.value=[];
     stockServerVersion.value=0;
     stockServerState.value='서버 연결 없음';
     const response=await fetch('/'+(IS_PROCUREMENT?'procure-workflows':'stock-workflows')+'/'+file,{cache:'no-store'});
     if(!response.ok)throw Error('원본 워크플로 HTTP '+response.status);
     data=fromN8nWorkflow(await response.json());
   }
   // An old browser-only draft is recoverable until the first server save.
   if(!serverSource && stored){
     const local=JSON.parse(stored);
     if(Array.isArray(local.nodes)&&Array.isArray(local.edges)&&local.original)data=local;
   }
   // VueFlow's initial internal nodes may still be synchronizing on mount.
   // Wait for its first actual paint before restoring a same-tab local draft;
   // otherwise the initial 5-node synthetic template can overwrite 6 real nodes.
   await nextTick();
   await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
   if(stockFlow.value!==file)return;
   stockOriginal.value=data.original;
   nodes.value=data.nodes.map(n=>({...n,data:{...n.data,state:'idle',stateSource:null}}));edges.value=data.edges;
   workflowName.value=data.workflowName||stockWorkflows.find(x=>x[0]===file)?.[1]||projectLabel+' 워크플로';
   selectedNodeId.value=null;selectedEdgeId.value=null;
   history=[];historyIndex=-1;recordHistory();
   localStorage.setItem('shared-n8n-studio:'+STUDIO_PROJECT+':selected',file);
   announce((serverSource?'서버 저장본':stored?'브라우저 복구본':'실제 원본 n8n JSON')+' 로드 · '+nodes.value.length+'개 노드 · 연결 '+edges.value.length+'개 · '+stockServerState.value);
   if(stockServerAvailable.value)await refreshStockVersions(file);
   nextTick(()=>fitView({padding:.25,duration:150}));
 }catch(err){announce('워크플로 불러오기 실패: '+err.message);}
}
function changeTemplate(next){
  if(running.value)return;
  const t=makeTemplate(next);
  nodes.value=t.nodes;edges.value=t.edges;template.value=next;
  selectedNodeId.value=null;selectedEdgeId.value=null;
  workflowName.value=next==='investment'?'Research Strategy (Sample)':next==='procurement'?'ProcureFlow Process (Sample)':'Untitled workflow';
  recordHistory();announce('예제 워크플로를 불러왔습니다 · 합성 데이터');
  nextTick(()=>fitView({padding:0.24,duration:250}));
}
function clearCanvas(){
  nodes.value=[];edges.value=[];selectedNodeId.value=null;selectedEdgeId.value=null;
  recordHistory();announce('캔버스를 비웠습니다');
}
async function saveLocal(){
  const payload={format:'shared-n8n-studio-playground/v1',workflowName:workflowName.value,template:template.value,nodes:nodes.value,edges:edges.value};
  if(stockMode){
    // Convert back to real official n8n workflow data. Reject unsupported
    // extension nodes rather than recording a misleading "successful save".
    let workflow;
    try{workflow=toN8nWorkflow({original:stockOriginal.value,nodes:nodes.value,edges:edges.value,workflowName:workflowName.value});}
    catch(e){announce('서버 저장 불가: '+e.message);return;}
    if(stockServerAvailable.value){
      try{
        const res=await fetch('/api/studio/workflows/'+stockFlow.value,{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({workflow,expectedVersion:stockServerVersion.value})});
        const data=await res.json();
        if(!res.ok){announce(res.status===409?'저장 충돌: 다른 탭에서 변경됨. 다시 불러와 주세요.':'서버 저장 실패: '+(data.error||res.status));return;}
        stockServerVersion.value=data.version;
        stockServerState.value='서버 v'+data.version;
        payload.original=stockOriginal.value;payload.format='shared-n8n-studio:'+STUDIO_PROJECT+'/v1';
        localStorage.setItem(storageKey(),JSON.stringify(payload));
        localSavedAt.value=new Date().toLocaleTimeString('ko-KR');
        clearImportedExecution(true);
        announce('서버 DB 저장 성공 · v'+data.version+' · 브라우저 백업 완료');
        await refreshStockVersions();
        return;
      }catch(e){announce('서버 연결 오류: '+e.message+' · 서버에는 저장되지 않았습니다');return;}
    }
    payload.original=stockOriginal.value;payload.format='shared-n8n-studio:'+STUDIO_PROJECT+'/v1';
  }
  try{localStorage.setItem(storageKey(),JSON.stringify(payload));localSavedAt.value=new Date().toLocaleTimeString('ko-KR');announce(stockMode?'서버 미연결 · 브라우저에만 백업했습니다':'이 브라우저에 저장했습니다 (서버 저장 아님)');}
  catch(e){announce('브라우저 저장 실패: '+e.message);}
}
function importGraph(raw){
  if(!raw||!Array.isArray(raw.nodes)||!Array.isArray(raw.edges)||raw.nodes.length>150||raw.edges.length>350)throw Error('지원하지 않는 그래프 형식');
  const ids=new Set();
  const nn=raw.nodes.map(n=>{
    if(typeof n.id!=='string'||!n.id||ids.has(n.id)||!Number.isFinite(n.position?.x)||!Number.isFinite(n.position?.y))throw Error('잘못된 노드 식별자/좌표');
    ids.add(n.id);
    const kind=paletteMap[n.data?.kind]?n.data.kind:'code';
    return makeNode(n.id,kind,String(n.data?.label||paletteMap[kind].name).slice(0,80),n.position.x,n.position.y,n.data?.parameters&&typeof n.data.parameters==='object'&&!Array.isArray(n.data.parameters)?n.data.parameters:{});
  });
  const ee=raw.edges.map(e=>{if(!ids.has(e.source)||!ids.has(e.target))throw Error('잘못된 연결선');return {...makeEdge(e.source,e.target),id:String(e.id||edgeId()),sourceHandle:e.sourceHandle||null,targetHandle:e.targetHandle||null};});
  nodes.value=nn;edges.value=ee;workflowName.value=String(raw.workflowName||raw.name||'Imported workflow').slice(0,100);
  selectedNodeId.value=null;selectedEdgeId.value=null;recordHistory();nextTick(()=>fitView({padding:.2,duration:250}));
}
function loadLocal(){
  try{const raw=localStorage.getItem(storageKey());if(!raw){announce('저장된 워크플로가 없습니다');return;}if(stockMode){const d=JSON.parse(raw);if(!d.original)throw Error('원본 JSON 누락');stockOriginal.value=d.original;nodes.value=d.nodes;edges.value=d.edges;workflowName.value=d.workflowName;recordHistory();nextTick(()=>fitView({padding:.2,duration:250}));}else importGraph(JSON.parse(raw));announce('브라우저 저장 데이터를 다시 불러왔습니다');}
  catch(e){announce('불러오기 실패: '+e.message);}
}
function exportJson(){
  let data;
  try{data=stockMode?toN8nWorkflow({original:stockOriginal.value,nodes:nodes.value,edges:edges.value,workflowName:workflowName.value}):{format:'shared-n8n-studio-playground/v1',workflowName:workflowName.value,nodes:nodes.value,edges:edges.value};}
  catch(e){announce('n8n JSON 내보내기 실패: '+e.message);return;}
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=stockMode?stockFlow.value.split('/').pop():'shared-n8n-workflow-demo.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
  announce('JSON 파일을 내려받았습니다');
}
async function onImport(event){
  const f=event.target.files?.[0];if(!f)return;
  try{
    const raw=JSON.parse(await f.text());
    if(stockMode){
      const converted=fromN8nWorkflow(raw);
      stockOriginal.value=converted.original;nodes.value=converted.nodes;edges.value=converted.edges;
      workflowName.value=converted.workflowName;recordHistory();
      nextTick(()=>fitView({padding:.24,duration:200}));
      announce('원본 n8n JSON 가져오기 완료 · '+nodes.value.length+'개 노드');
    }else{
      importGraph(raw);announce('JSON 워크플로를 가져왔습니다 (모의 데이터)');
    }
  }
  catch(e){announce('가져오기 실패: '+e.message);}
  event.target.value='';
}
let taskTimer=null;
async function runSimulation(){
  if(running.value||nodes.value.length===0)return;
  running.value=true;
  nodes.value=nodes.value.map(n=>({...n,data:{...n.data,state:'idle'}}));
  announce('모의 실행 시작 · 실제 API 호출 없음');
  for(const n of [...nodes.value]){
    if(!running.value)break;
    nodes.value=nodes.value.map(x=>x.id===n.id?{...x,data:{...x.data,state:'running'}}:x);
    await new Promise(resolve=>{taskTimer=setTimeout(resolve,330);});
    if(!running.value)break;
    nodes.value=nodes.value.map(x=>x.id===n.id?{...x,data:{...x.data,state:'success'}}:x);
  }
  running.value=false;taskTimer=null;
  announce('모의 실행 완료 · 서버/워크플로 실행 없음');
}
function resetRun(){
  running.value=false;
  nodes.value=nodes.value.map(n=>({...n,data:{...n.data,state:'idle'}}));
  announce('모의 실행 표시 초기화');
}
function fit(){fitView({padding:0.23,duration:250});announce('전체 화면 맞춤');}
onMounted(()=>{
  document.addEventListener('keydown',onKeyDown);
  recordHistory();
  if(stockMode){
    const path=new URLSearchParams(window.location.search).get('workflow');
    const last=localStorage.getItem('shared-n8n-studio:'+STUDIO_PROJECT+':selected');
    const chosen=stockWorkflows.some(x=>x[0]===path)?path:stockWorkflows.some(x=>x[0]===last)?last:stockWorkflows[0][0];
    openStockFlow(chosen);
  }
  else nextTick(()=>fitView({padding:.23,duration:0}));
});
onBeforeUnmount(()=>{document.removeEventListener('keydown',onKeyDown);if(taskTimer)clearTimeout(taskTimer);});
watch(()=>selectedNodeId.value,()=>{
  if(selectedNode.value)inspectorJson.value=JSON.stringify(selectedNode.value.data.parameters||{},null,2);
});
</script>

<template>
  <div class="studio-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark"><span></span><span></span><span></span><span></span></div>
        <div class="brand-text"><strong>n8n <em>Studio</em></strong><small>SHARED EDITOR LAB</small></div>
        <span class="brand-divider"></span><span class="brand-trailing">{{stockMode?projectLabel+' · 공통 편집기':'Playground'}}</span>
      </div>
      <div class="environment"><span class="pulse-dot"></span> {{stockMode?projectNoun+' 자동화 · 공통 n8n 모듈':'독립 테스트 환경'}} <span class="env-separator">/</span> <b>{{stockMode?'편집·데이터 어댑터':'LOCAL ONLY'}}</b></div>
      <div class="top-actions">
        <button class="icon-btn outline" title="도움말" aria-label="도움말" @click="showHelp=!showHelp">?</button>
        <a class="github-link" href="https://github.com/lyonbegin/shared-n8n-studio" target="_blank" rel="noopener">GitHub <span>↗</span></a>
      </div>
    </header>
    <div class="workspace">
      <aside class="left-panel">
        <div class="section-overline">WORKSPACE</div>
        <div class="project-tile">
          <span class="project-monogram">S</span><div><b>Shared n8n Studio</b><small>{{stockMode?projectEnglish+' · 실제 '+stockWorkflows.length+'개 워크플로':'Canvas interaction test'}}</small></div><span class="project-menu">•••</span>
        </div>
        <div class="sidebar-separator"></div>
        <div class="section-heading"><b>{{stockMode?projectLabel+' 워크플로':'샘플 워크플로'}}</b><small>{{stockMode?stockWorkflows.length:3}}</small></div>
        <div v-if="stockMode" class="sample-list" data-testid="stock-workflows">
          <button v-for="[file,label] in stockWorkflows" :key="file" class="sample-item" :class="{active:stockFlow===file}" :data-stock-flow="file" @click="openStockFlow(file)">
            <span class="sample-icon">↗</span><span><b>{{label}}</b><small>{{file.startsWith('operations')?'운영 워크플로':'시나리오 테스트'}}</small></span><span class="sample-chevron">›</span>
          </button>
        </div>
        <div v-else class="sample-list">
          <button class="sample-item" :class="{active:template==='common'}" @click="changeTemplate('common')"><span class="sample-icon">◈</span><span><b>공통 기능 테스트</b><small>Basic canvas</small></span><span class="sample-chevron">›</span></button>
          <button class="sample-item" :class="{active:template==='investment'}" @click="changeTemplate('investment')"><span class="sample-icon">↗</span><span><b>주식 자동화</b><small>Investment sample</small></span><span class="sample-chevron">›</span></button>
          <button class="sample-item" :class="{active:template==='procurement'}" @click="changeTemplate('procurement')"><span class="sample-icon">▤</span><span><b>ProcureFlow</b><small>Procurement sample</small></span><span class="sample-chevron">›</span></button>
        </div>
        <div class="sidebar-separator"></div>
        <div class="section-heading"><b>노드 라이브러리</b><small data-testid="catalog-count">{{palette.length}} TYPES</small></div>
        <div class="catalog-legend"><span>공식 {{catalogStats.native}}</span><span>조합 {{catalogStats.composite}}</span><span>확장 {{catalogStats.extension}}</span></div>
        <div class="search-wrap"><span>⌕</span><input v-model="search" aria-label="노드 검색" placeholder="노드 이름·기능·분류 검색..." /></div>
        <select class="category-filter" v-model="groupFilter" aria-label="노드 분류 선택">
          <option value="all">전체 분류 · {{palette.length}}종</option>
          <option v-for="group in paletteGroups" :key="group" :value="group">{{group}} · {{palette.filter(p=>p.group===group).length}}종</option>
        </select>
        <div class="palette-scroll">
          <template v-for="group in paletteGroups" :key="group">
            <div v-if="filteredPalette.some(p=>p.group===group)" class="palette-category">{{group}}</div>
            <button v-for="item in filteredPalette.filter(p=>p.group===group)" :key="item.kind" class="palette-item" :data-node-kind="item.kind" draggable="true" @dragstart="onPaletteDragStart($event,item.kind)" @click="addNode(item.kind)" :title="item.name+' · 클릭하거나 캔버스로 드래그'">
              <span class="palette-icon" :style="{'--kind-color':item.color}">{{item.icon}}</span>
              <span><b>{{item.name}}</b><small>{{item.description}}</small></span><span class="palette-add">＋</span>
            </button>
          </template>
          <p v-if="!filteredPalette.length" class="empty-search">해당하는 노드가 없습니다.</p>
        </div>
        <div class="sidebar-foot"><span class="keycaps">좌측 드래그</span> Pan <span class="keycaps">SHIFT</span> Select</div>
      </aside>

      <section class="main-column">
        <div class="editor-toolbar">
          <div class="workflow-identity"><span class="workflow-dot"></span><input aria-label="워크플로 이름" v-model="workflowName" @change="recordHistory" /><span class="draft-pill">DRAFT</span></div>
          <div class="editor-buttons">
            <button class="toolbar-btn" title="되돌리기" :disabled="!canUndo" @click="undo">↶ <span>실행 취소</span></button>
            <button class="toolbar-btn" title="다시 실행" :disabled="!canRedo" @click="redo">↷</button>
            <span class="toolbar-separator"></span>
            <button class="toolbar-btn" @click="zoomOut()" title="축소" aria-label="축소">−</button>
            <button class="toolbar-btn" @click="fit()" title="화면 맞춤">⊡ <span>Fit</span></button>
            <button class="toolbar-btn" @click="zoomIn()" title="확대" aria-label="확대">＋</button>
            <span class="toolbar-separator"></span>
            <button class="toolbar-btn" @click="exportJson" title="JSON 내보내기">⇩ <span>JSON</span></button>
            <button class="toolbar-btn" @click="fileInput?.click()" title="JSON 가져오기">⇧</button>
            <input ref="fileInput" type="file" accept=".json,application/json" class="visually-hidden" @change="onImport"/>
            <button class="toolbar-btn" @click="loadLocal" title="브라우저 저장값 불러오기">↺</button>
            <button v-if="stockMode" class="toolbar-btn" title="공식 n8n 실행 결과 JSON 가져오기" @click="runFileInput?.click()">↳ <span>실행 결과</span></button>
             <input v-if="stockMode" ref="runFileInput" type="file" accept=".json,application/json" class="visually-hidden" aria-label="n8n 실행 JSON 파일" @change="importN8nExecution"/>
             <button class="primary-btn" @click="saveLocal">▣ <span>{{stockMode?'서버 저장':'브라우저 저장'}}</span></button>
          </div>
        </div>
        <div class="canvas-info">
          <div class="crumbs"><span>WORKFLOWS</span><span class="crumb-arrow">/</span><b>{{stockMode?projectEnglish+' · '+stockWorkflows.length+'개 실제 워크플로':'Editor playground'}}</b></div>
          <div class="canvas-stats"><span class="stat"><span class="stat-dot purple"></span> {{nodeCount}} Nodes</span><span class="stat"><span class="stat-dot blue"></span> {{edgeCount}} Connections</span><span class="stat-divider"></span><span class="safe-label">● {{stockMode?('DB '+(stockServerAvailable?'연결됨 · v'+stockServerVersion:'미연결')+' · 실행 비활성'):'모의 데이터 전용'}}</span></div>
        </div>
        <div class="canvas-holder" data-testid="canvas-holder" @dragover="onDragOver" @drop="onDrop">
          <VueFlow id="shared-studio-playground" v-model:nodes="nodes" v-model:edges="edges" :node-types="nodeTypes" :fit-view-on-init="true"
             :fit-view-on-init-options="{padding:0.23}" :pan-on-drag="[0,1]" :selection-key-code="'Shift'" :selection-on-drag="true"
             :nodes-draggable="true" :nodes-connectable="true" :elements-selectable="true"
             :min-zoom="0.2" :max-zoom="2.5" :delete-key-code="null"
             @node-click="onNodeClick" @edge-click="onEdgeClick" @pane-click="onPaneClick"
             @node-drag-stop="onNodeDragStop" @connect="onConnect">
            <Background pattern-color="#d9e1ea" :gap="22" :size="1.15"/>
            <Controls position="bottom-left" :show-interactive="false"/>
            <MiniMap position="bottom-right" :node-color="n=>paletteMap[n.data.kind]?.color||'#8c9fb2'" :mask-color="'rgba(238,244,250,.72)'"/>
          </VueFlow>
          <div class="canvas-watermark"><span>◈</span> SHARED N8N STUDIO <i>·</i> {{stockMode?(IS_PROCUREMENT?'PROCUREFLOW':'INVESTMENT'):'PLAYGROUND'}}</div>
          <div class="canvas-controls-hint">좌클릭 드래그: 화면 이동 <span>·</span> Shift + 드래그: 다중 선택 <span>·</span> 노드 핸들: 연결</div>
        </div>
        <div class="bottom-bar">
          <span class="bottom-status"><span class="green-dot"></span>{{status}}</span>
          <span class="bottom-right"><span>공통 Vue Flow 모듈</span><span class="bottom-divider"></span> {{stockMode?(stockServerAvailable?'SQLite 초안 서버 저장 · 업무 실행 차단':'서버 미연결 · 브라우저 저장만 가능'):'No API connected'}}</span>
        </div>
      </section>

      <aside class="right-panel">
        <div class="inspector-top"><span class="inspector-icon">⚙</span><div><strong>Inspector</strong><small>NODE & WORKFLOW SETTINGS</small></div></div>
        <div class="right-tabs"><button :class="{active:activeTab==='nodes'}" @click="activeTab='nodes'">설정</button><button :class="{active:activeTab==='activity'}" @click="activeTab='activity'">활동 기록</button></div>
        <div v-if="activeTab==='nodes'" class="inspector-body">
          <template v-if="selectedNode">
            <div class="selection-kind"><span class="selection-icon" :style="{'--kind-color':paletteMap[selectedNode.data.kind]?.color}">{{paletteMap[selectedNode.data.kind]?.icon}}</span><div><strong>{{paletteMap[selectedNode.data.kind]?.name}}</strong><small>NODE PROPERTIES</small></div></div>
            <label class="field-label">노드 이름</label>
            <input class="field-control" v-model="selectedNode.data.label" aria-label="노드 이름" @change="recordHistory"/>
            <label class="field-label">노드 유형</label>
            <select class="field-control" v-model="selectedNode.data.kind" aria-label="노드 유형" @change="selectedNode.data.parameters=defaultParameters(selectedNode.data.kind);inspectorJson=JSON.stringify(selectedNode.data.parameters,null,2);recordHistory()">
              <option v-for="p in palette" :key="p.kind" :value="p.kind">{{p.name}}</option>
            </select>
            <div class="contract-summary" v-if="selectedSpec" data-testid="node-contract">
              <b>{{selectedSpec.implementation==='native'?'공식 n8n 기본 노드':selectedSpec.implementation==='composite'?'공식 노드 조합 설계':'프로젝트 확장 구현 필요'}}</b>
              <span>노드 유형: {{selectedSpec.kind}}</span>
              <span>입력: {{selectedSpec.inputs.join(', ')}} · 출력: {{selectedSpec.outputs.join(', ')}}</span>
              <span v-if="selectedSpec.nativeType">n8n 매핑: {{selectedSpec.nativeType}}</span>
              <span v-else>실제 실행 어댑터 미연결 (설계 계약)</span>
            </div>
            <label class="field-label">설명</label>
            <textarea class="field-control" rows="2" v-model="selectedNode.data.description" @change="recordHistory"></textarea>
            <div class="inspector-section-head"><b>노드별 실행 설정</b><span>TYPE-CONTRACT</span></div>
            <div class="settings-fields" data-testid="settings-fields">
              <div v-for="field in selectedFields" :key="selectedNode.id+':'+field.key" class="settings-field">
                <label class="field-label" :for="'setting-'+field.key">{{field.label}}</label>
                <select v-if="field.type==='select'" class="field-control" :id="'setting-'+field.key" :data-setting="field.key" :value="selectedNode.data.parameters[field.key]" @change="updateParameter(field,$event.target.value)">
                  <option v-for="option in field.options" :key="option.value" :value="option.value">{{option.label}}</option>
                </select>
                <label v-else-if="field.type==='boolean'" class="toggle-setting">
                  <input type="checkbox" :data-setting="field.key" :checked="Boolean(selectedNode.data.parameters[field.key])" @change="updateParameter(field,$event.target.checked)"/>
                  <span>{{selectedNode.data.parameters[field.key]?'사용':'사용 안 함'}}</span>
                </label>
                <textarea v-else-if="field.type==='code'||field.type==='json'" :id="'setting-'+field.key" :data-setting="field.key" :rows="field.type==='code'?6:4" spellcheck="false" class="field-control code-editor" :value="displayParameter(field)" @change="updateParameter(field,$event.target.value)"></textarea>
                <input v-else :id="'setting-'+field.key" :data-setting="field.key" :type="field.type==='number'?'number':'text'" :min="field.min" :max="field.max" class="field-control" :placeholder="field.placeholder||''" :value="displayParameter(field)" @change="updateParameter(field,$event.target.value)"/>
              </div>
            </div>
            <div class="inspector-section-head"><b>전체 파라미터</b><span>JSON</span></div>
            <textarea class="field-control code-editor" v-model="inspectorJson" aria-label="노드 JSON 파라미터" spellcheck="false" rows="9"></textarea>
            <button class="secondary-btn full" @click="applyNodeSettings">설정 적용</button>
            <div class="position-panel"><span>X: {{Math.round(selectedNode.position.x)}}</span><span>Y: {{Math.round(selectedNode.position.y)}}</span></div>
            <div v-if="stockMode&&importedExecution" data-testid="n8n-node-execution-inspector" style="margin:12px 0;border-top:1px solid #d5dde8;padding-top:12px;">
              <div class="inspector-section-head"><b>n8n 노드 실행 기록</b><span>외부 JSON · 조회 전용</span></div>
              <p v-if="!selectedExecutionResult">선택한 노드의 실행 기록이 없습니다.</p>
              <template v-else>
                <p><b>상태:</b> {{selectedExecutionResult.status}} · {{selectedExecutionResult.iterations}}회</p>
                <p><b>실행시간:</b> {{selectedExecutionResult.executionTime??'확인 안 됨'}} ms</p>
                <label class="field-label">노드 입력 (기록에 포함된 경우)</label>
                <pre style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:150px;overflow:auto;font-size:11px;">{{JSON.stringify(selectedExecutionResult.input,null,2)}}</pre>
                <label class="field-label">노드 출력</label>
                <pre style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:190px;overflow:auto;font-size:11px;">{{JSON.stringify(selectedExecutionResult.output,null,2)}}</pre>
                <template v-if="selectedExecutionResult.error">
                  <label class="field-label">오류 정보</label>
                  <pre style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:150px;overflow:auto;color:#b11c38;font-size:11px;">{{JSON.stringify(selectedExecutionResult.error,null,2)}}</pre>
                </template>
              </template>
            </div>
            <button class="danger-outline" @click="deleteSelected">⌫ 선택 노드 삭제</button>
          </template>
          <template v-else-if="selectedEdge">
            <div class="selection-kind"><span class="selection-icon link-icon">↗</span><div><strong>연결선 선택</strong><small>CONNECTION PROPERTIES</small></div></div>
            <label class="field-label">출발 노드</label><input class="field-control" :value="selectedEdge.source" readonly/>
            <label class="field-label">도착 노드</label><input class="field-control" :value="selectedEdge.target" readonly/>
            <label class="field-label">연결선 유형</label>
            <select class="field-control" v-model="selectedEdge.type" @change="applyEdgeSettings"><option value="smoothstep">Smooth step</option><option value="bezier">Bezier</option><option value="straight">Straight</option></select>
            <button class="danger-outline" @click="deleteSelected">⌫ 연결선 삭제</button>
          </template>
          <template v-else>
            <div class="empty-selection"><div class="empty-illustration"><span>↖</span><span>◇</span><span>◎</span></div><h3>노드를 선택하세요</h3><p>캔버스의 노드나 연결선을 클릭하면 설정을 변경할 수 있습니다.</p></div>
            <div class="inspector-section-head"><b>Quick actions</b></div>
            <button class="quick-action" @click="addNode('code')"><span>＋</span><div><strong>새 Code 노드 추가</strong><small>캔버스에 노드 배치</small></div></button>
            <button class="quick-action" @click="fit"><span>⊡</span><div><strong>전체 화면 맞춤</strong><small>모든 노드를 한 화면에</small></div></button>
            <button class="quick-action" @click="clearCanvas"><span>⌫</span><div><strong>캔버스 비우기</strong><small>독립 테스트 데이터만 삭제</small></div></button>
          </template>
        </div>
        <div v-else class="inspector-body activity-list">
          <div class="activity-caption">최신 사용자 조작</div>
          <div v-for="(ev,i) in events" :key="i" class="activity-item"><span class="activity-marker"></span><div><b>{{ev.text}}</b><small>{{ev.time}}</small></div></div>
        </div>
        <div class="right-bottom">
          <div v-if="stockMode" data-testid="n8n-execution-file-panel" style="padding:10px 4px;border-bottom:1px solid #d5dde8;margin-bottom:10px;">
            <div style="font-weight:700;">n8n 실행 기록 보기 <small>조회 전용</small></div>
            <p v-if="!importedExecution" style="font-size:12px;">공식 n8n에서 내보낸 실행 JSON을 상단 ‘실행 결과’로 불러오세요. 연결된 실행 서버는 없습니다.</p>
            <template v-else>
              <p style="font-size:12px;" data-testid="imported-run-status">실행 #{{importedExecution.id}} · {{importedExecution.status}} · 처리 {{importedExecution.executedCount}}개 · 오류 {{importedExecution.errorCount}}개</p>
              <p style="font-size:11px;">외부 파일 (출처 미검증) · 실시간 실행 아님 · 브라우저 메모리에서만 조회</p>
              <button class="toolbar-btn" @click="clearImportedExecution()">결과 표시 초기화</button>
            </template>
          </div>
          <div v-if="stockMode" data-testid="stock-version-history" style="padding:9px 4px 14px;border-bottom:1px solid #d8dfe8;margin-bottom:10px;">
            <div style="font-weight:700;margin-bottom:8px;">서버 변경 이력 <small>최근 {{stockVersionRows.length}}개 · 현재 v{{stockServerVersion}}</small></div>
            <p v-if="!stockServerAvailable" style="font-size:12px;">서버 연결이 없어 이력을 볼 수 없습니다.</p>
            <p v-else-if="!stockVersionRows.length" style="font-size:12px;">저장된 서버 버전이 없습니다.</p>
            <div v-for="entry in stockVersionRows.slice(0,5)" :key="entry.version" style="display:flex;justify-content:space-between;align-items:center;gap:6px;margin:5px 0;">
              <span>v{{entry.version}} <small>{{entry.created_at?.slice(0,16)}}</small></span>
              <button class="toolbar-btn" :data-restore-version="entry.version" @click="restoreStockVersion(entry.version)">복원</button>
            </div>
          </div>
          <section v-if="IS_PROCUREMENT" data-testid="procurement-fixture-panel" style="padding:12px;border:1px solid #a1aec0;border-radius:8px;margin:10px 0;">
            <strong>격리 시나리오 실행 · MOCK ONLY</strong>
            <p style="font-size:12px;">S01~S10 가상 입력만 사용 · 실제 n8n 엔진/G2B/투찰 호출 없음</p>
            <button class="toolbar-btn" data-testid="mock-prepare" @click="beginFixture">모의 실행 준비</button>
            <button class="toolbar-btn" data-testid="mock-next" :disabled="!fixtureRun||fixtureRun.status==='stopped'||fixtureRun.status==='completed'" @click="nextFixture">다음 단계</button>
            <button class="toolbar-btn" data-testid="mock-run-all" :disabled="!fixtureRun||fixtureRun.status==='stopped'||fixtureRun.status==='completed'" @click="runFixture">끝까지 모의 실행</button>
            <button class="toolbar-btn" data-testid="mock-stop" :disabled="!fixtureRun" @click="stopFixture">중지</button>
            <p v-if="fixtureError" role="alert">{{fixtureError}}</p>
            <template v-if="fixtureRun">
              <p data-testid="mock-progress">{{fixtureRun.executionId}} · {{fixtureRun.status}} · {{fixtureRun.cursor}}/{{fixtureRun.steps.length}} · 예상 {{fixtureRun.expected}}</p>
              <div style="max-height:230px;overflow:auto;font-size:11px;">
                <div v-for="ev in fixtureRun.events" :key="ev.sequence">
                  {{ev.sequence}}. {{ev.flow}} / {{ev.event}} · 모의 실행
                  <details><summary>입출력 확인</summary><pre style="white-space:pre-wrap;">{{JSON.stringify({input:ev.input,output:ev.output},null,2)}}</pre></details>
                </div>
              </div>
            </template>
          </section>
          <div class="run-title"><div><strong>{{stockMode?'실행 엔진 연결 상태':'Test execution'}}</strong><small>{{stockMode?'실제 실행 서버 미연결 · 안전하게 기록 파일 조회만 지원':'외부 API·실거래 없이 화면만 시뮬레이션'}}</small></div><span class="run-icon">◉</span></div>
          <button v-if="!stockMode" class="run-btn" :disabled="running||!nodeCount" @click="runSimulation">{{running?'◉ 실행 중…':'▶ 모의 실행'}}</button>
          <button v-if="!stockMode" class="run-reset" @click="resetRun">실행 표시 초기화</button>
        </div>
      </aside>
    </div>
    <div v-if="showHelp" class="help-overlay" @click.self="showHelp=false"><div class="help-dialog">
      <button class="help-close" @click="showHelp=false">×</button><span class="help-kicker">INTERACTION GUIDE</span><h2>{{stockMode?projectLabel+' · 공통 Studio 편집기':'50종 노드 계약 플레이그라운드'}}</h2>
      <p>{{stockMode?(IS_PROCUREMENT?'ProcureFlow PF00~PF15와 S01~S10의 원본 n8n JSON을 공용 Studio에서 편집하고 별도 초안 DB에 저장할 수 있습니다. 실제 공고 수집·입찰·투찰은 실행되지 않습니다.':'주식 프로젝트의 실제 13개 n8n JSON을 공통 UI에서 편집하고 서버 DB에 저장할 수 있습니다. 실제 투자 주문 실행은 연결하지 않았습니다.'):'공통 50종 노드의 팔레트·설정·포트 연결을 시험하는 별도 Vue Flow 프론트입니다. 공식 n8n 엔진과 실제 투자·조달 API에는 연결되지 않았습니다.'}}</p>
      <div class="help-grid"><div><b>01 / Pan</b><span>빈 캔버스 왼쪽/가운데 드래그</span></div><div><b>02 / Select</b><span>Shift + 드래그 / 노드 클릭</span></div><div><b>03 / Edit</b><span>노드 추가·이동·삭제·연결</span></div><div><b>04 / Save</b><span>브라우저 저장 / JSON 내보내기</span></div></div>
      <div class="help-caution">{{stockMode?'서버 SQLite 저장은 브라우저별 익명 초안입니다. 다른 기기에서 동일 초안에 접근하려면 로그인 연동이 필요합니다. 실제 n8n 실행 엔진은 연결 전입니다.':'모의 실행, 브라우저 저장 및 예제 데이터만 포함됩니다. n8n 서버 저장·실제 노드 실행 검증은 별도 단계입니다.'}}</div>
      <button class="primary-btn" @click="showHelp=false">테스트 시작</button>
    </div></div>
  </div>
</template>
