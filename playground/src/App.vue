<script setup>
import {ref, computed, watch, onMounted, onBeforeUnmount, defineComponent, h, nextTick} from 'vue';
import {VueFlow, Handle, Position, MarkerType, useVueFlow} from '@vue-flow/core';
import {Background} from '@vue-flow/background';
import {Controls} from '@vue-flow/controls';
import {MiniMap} from '@vue-flow/minimap';

const STORAGE_KEY='shared-n8n-studio:playground:v1';
const palette=[
  {kind:'trigger',name:'Manual Trigger',group:'트리거',icon:'▶',color:'#ec6384',description:'수동 시작'},
  {kind:'schedule',name:'Schedule',group:'트리거',icon:'◷',color:'#ec6384',description:'일정 기반 실행'},
  {kind:'webhook',name:'Webhook',group:'트리거',icon:'⌁',color:'#ec6384',description:'이벤트 수신 (모의)'},
  {kind:'http',name:'HTTP Request',group:'처리',icon:'↗',color:'#4d8ee7',description:'외부 요청 설정 (모의)'},
  {kind:'code',name:'Code',group:'처리',icon:'{ }',color:'#27aa99',description:'데이터 변환 (모의)'},
  {kind:'set',name:'Edit Fields',group:'처리',icon:'≡',color:'#27aa99',description:'필드 편집'},
  {kind:'if',name:'IF',group:'논리',icon:'◇',color:'#e6a640',description:'조건에 따른 분기'},
  {kind:'merge',name:'Merge',group:'논리',icon:'⋈',color:'#a28aea',description:'분기 합류'},
  {kind:'wait',name:'Wait',group:'논리',icon:'◴',color:'#a28aea',description:'지연 단계'},
];
const paletteGroups=['트리거','처리','논리'];
const paletteMap=Object.fromEntries(palette.map(item=>[item.kind,item]));
let counter=10, edgeCounter=10;
const newId=()=> 'node_'+(++counter);
const edgeId=()=> 'edge_'+(++edgeCounter);
const makeNode=(id,kind,label,x,y,extra={})=>({
  id,type:'studio',position:{x,y},data:{
    kind,label,description:paletteMap[kind]?.description||'',state:'idle',
    parameters:{...extra},disabled:false
  }
});
const makeEdge=(source,target)=>({id:edgeId(),source,target,type:'smoothstep',markerEnd:MarkerType.ArrowClosed,style:{stroke:'#97a9bd',strokeWidth:2}});
function makeTemplate(type){
  const texts={
    common:[['trigger','워크플로 시작'],['http','데이터 요청'],['if','조건 확인'],['code','결과 처리'],['wait','재시도 대기']],
    investment:[['webhook','TradingView 이벤트'],['code','전략 신호 분석'],['if','위험 기준 검사'],['set','연구 결과 기록'],['wait','시장 데이터 대기']],
    procurement:[['schedule','공고 조회 시작'],['http','공고 자료 수집'],['if','증빙 조건 확인'],['set','심사 결과 정리'],['wait','응답 대기']]
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
        class:['studio-node',props.selected?'is-selected':'',props.data.state==='success'?'is-success':'',props.data.state==='running'?'is-running':''],
        'data-testid':'studio-node','data-node-id':props.id,
        style:{'--node-accent':meta.color}
      },[
        h(Handle,{type:'target',position:Position.Left,class:'port port-in'}),
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
          h('span',props.data.state==='running'?'실행 중':props.data.state==='success'?'모의 성공': '준비됨'),
          h('span',{class:'node-id'},props.id.replace(/^demo_.+?_/, '#'))
        ]),
        h(Handle,{type:'source',position:Position.Right,class:'port port-out'})
      ]);
    };
  }
});
const nodeTypes={studio:NodeCard};
const {fitView,zoomIn,zoomOut,screenToFlowCoordinate, getViewport}=useVueFlow({id:'shared-studio-playground'});
const initial=makeTemplate('common');
const nodes=ref(initial.nodes);
const edges=ref(initial.edges);
const selectedNodeId=ref(null);
const selectedEdgeId=ref(null);
const activeTab=ref('nodes');
const search=ref('');
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
const filteredPalette=computed(()=>palette.filter(x=>(x.name+' '+x.kind+' '+x.description).toLowerCase().includes(search.value.toLowerCase())));
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
  recordHistory();announce('연결선을 만들었습니다');
}
function onNodeDragStop(){recordHistory();announce('노드 위치 변경');}
function addNode(kind,position){
  const label=paletteMap[kind]?.name||'New node';
  const p=position||{x:180+(nodes.value.length%3)*245,y:185+Math.floor(nodes.value.length/3)*165};
  const n=makeNode(newId(),kind,label,Math.round(p.x),Math.round(p.y));
  nodes.value=[...nodes.value,n];selectedNodeId.value=n.id;selectedEdgeId.value=null;
  inspectorJson.value='{}';
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
function applyNodeSettings(){
  const n=selectedNode.value;
  if(!n)return;
  if(!n.data.label.trim()){announce('노드 이름을 입력해 주세요');return;}
  try{
    const parsed=JSON.parse(inspectorJson.value);
    if(!parsed||Array.isArray(parsed)||typeof parsed!=='object')throw Error('JSON 객체가 필요합니다');
    n.data.parameters=parsed;
    recordHistory();announce('노드 설정을 적용했습니다');
  }catch(e){announce('설정 JSON 오류: '+e.message);}
}
function applyEdgeSettings(){recordHistory();announce('연결선 설정을 변경했습니다');}
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
function saveLocal(){
  const payload={format:'shared-n8n-studio-playground/v1',workflowName:workflowName.value,template:template.value,nodes:nodes.value,edges:edges.value};
  try{localStorage.setItem(STORAGE_KEY,JSON.stringify(payload));localSavedAt.value=new Date().toLocaleTimeString('ko-KR');announce('이 브라우저에 저장했습니다 (서버 저장 아님)');}
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
  try{const raw=localStorage.getItem(STORAGE_KEY);if(!raw){announce('저장된 워크플로가 없습니다');return;}importGraph(JSON.parse(raw));announce('브라우저 저장 데이터를 다시 불러왔습니다');}
  catch(e){announce('불러오기 실패: '+e.message);}
}
function exportJson(){
  const data={format:'shared-n8n-studio-playground/v1',workflowName:workflowName.value,nodes:nodes.value,edges:edges.value};
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='shared-n8n-workflow-demo.json';document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);
  announce('JSON 파일을 내려받았습니다');
}
async function onImport(event){
  const f=event.target.files?.[0];if(!f)return;
  try{importGraph(JSON.parse(await f.text()));announce('JSON 워크플로를 가져왔습니다 (모의 데이터)');}
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
  nextTick(()=>fitView({padding:.23,duration:0}));
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
        <span class="brand-divider"></span><span class="brand-trailing">Playground</span>
      </div>
      <div class="environment"><span class="pulse-dot"></span> 독립 테스트 환경 <span class="env-separator">/</span> <b>LOCAL ONLY</b></div>
      <div class="top-actions">
        <button class="icon-btn outline" title="도움말" aria-label="도움말" @click="showHelp=!showHelp">?</button>
        <a class="github-link" href="https://github.com/lyonbegin/shared-n8n-studio" target="_blank" rel="noopener">GitHub <span>↗</span></a>
      </div>
    </header>
    <div class="workspace">
      <aside class="left-panel">
        <div class="section-overline">WORKSPACE</div>
        <div class="project-tile">
          <span class="project-monogram">S</span><div><b>Shared n8n Studio</b><small>Canvas interaction test</small></div><span class="project-menu">•••</span>
        </div>
        <div class="sidebar-separator"></div>
        <div class="section-heading"><b>샘플 워크플로</b><small>03</small></div>
        <div class="sample-list">
          <button class="sample-item" :class="{active:template==='common'}" @click="changeTemplate('common')"><span class="sample-icon">◈</span><span><b>공통 기능 테스트</b><small>Basic canvas</small></span><span class="sample-chevron">›</span></button>
          <button class="sample-item" :class="{active:template==='investment'}" @click="changeTemplate('investment')"><span class="sample-icon">↗</span><span><b>주식 자동화</b><small>Investment sample</small></span><span class="sample-chevron">›</span></button>
          <button class="sample-item" :class="{active:template==='procurement'}" @click="changeTemplate('procurement')"><span class="sample-icon">▤</span><span><b>ProcureFlow</b><small>Procurement sample</small></span><span class="sample-chevron">›</span></button>
        </div>
        <div class="sidebar-separator"></div>
        <div class="section-heading"><b>노드 라이브러리</b><small>{{palette.length}} TYPES</small></div>
        <div class="search-wrap"><span>⌕</span><input v-model="search" aria-label="노드 검색" placeholder="노드 검색..." /></div>
        <div class="palette-scroll">
          <template v-for="group in paletteGroups" :key="group">
            <div v-if="filteredPalette.some(p=>p.group===group)" class="palette-category">{{group}}</div>
            <button v-for="item in filteredPalette.filter(p=>p.group===group)" :key="item.kind" class="palette-item" draggable="true" @dragstart="onPaletteDragStart($event,item.kind)" @click="addNode(item.kind)" :title="item.name+' · 클릭하거나 캔버스로 드래그'">
              <span class="palette-icon" :style="{'--kind-color':item.color}">{{item.icon}}</span>
              <span><b>{{item.name}}</b><small>{{item.description}}</small></span><span class="palette-add">＋</span>
            </button>
          </template>
          <p v-if="!filteredPalette.length" class="empty-search">해당하는 노드가 없습니다.</p>
        </div>
        <div class="sidebar-foot"><span class="keycaps">SPACE</span> Pan <span class="keycaps">SHIFT</span> Select</div>
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
            <button class="primary-btn" @click="saveLocal">▣ <span>브라우저 저장</span></button>
          </div>
        </div>
        <div class="canvas-info">
          <div class="crumbs"><span>WORKFLOWS</span><span class="crumb-arrow">/</span><b>Editor playground</b></div>
          <div class="canvas-stats"><span class="stat"><span class="stat-dot purple"></span> {{nodeCount}} Nodes</span><span class="stat"><span class="stat-dot blue"></span> {{edgeCount}} Connections</span><span class="stat-divider"></span><span class="safe-label">● 모의 데이터 전용</span></div>
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
          <div class="canvas-watermark"><span>◈</span> SHARED N8N STUDIO <i>·</i> PLAYGROUND</div>
          <div class="canvas-controls-hint">좌클릭 드래그: 화면 이동 <span>·</span> Shift + 드래그: 다중 선택 <span>·</span> 노드 핸들: 연결</div>
        </div>
        <div class="bottom-bar">
          <span class="bottom-status"><span class="green-dot"></span>{{status}}</span>
          <span class="bottom-right"><span>Vue Flow · Standalone</span><span class="bottom-divider"></span> No API connected</span>
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
            <select class="field-control" v-model="selectedNode.data.kind" aria-label="노드 유형" @change="recordHistory">
              <option v-for="p in palette" :key="p.kind" :value="p.kind">{{p.name}}</option>
            </select>
            <label class="field-label">설명</label>
            <textarea class="field-control" rows="2" v-model="selectedNode.data.description" @change="recordHistory"></textarea>
            <div class="inspector-section-head"><b>파라미터</b><span>JSON</span></div>
            <textarea class="field-control code-editor" v-model="inspectorJson" aria-label="노드 JSON 파라미터" spellcheck="false" rows="9"></textarea>
            <button class="secondary-btn full" @click="applyNodeSettings">설정 적용</button>
            <div class="position-panel"><span>X: {{Math.round(selectedNode.position.x)}}</span><span>Y: {{Math.round(selectedNode.position.y)}}</span></div>
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
          <div class="run-title"><div><strong>Test execution</strong><small>외부 API·실거래 없이 화면만 시뮬레이션</small></div><span class="run-icon">◉</span></div>
          <button class="run-btn" :disabled="running||!nodeCount" @click="runSimulation">{{running?'◉ 실행 중…':'▶ 모의 실행'}}</button>
          <button class="run-reset" @click="resetRun">실행 표시 초기화</button>
        </div>
      </aside>
    </div>
    <div v-if="showHelp" class="help-overlay" @click.self="showHelp=false"><div class="help-dialog">
      <button class="help-close" @click="showHelp=false">×</button><span class="help-kicker">INTERACTION GUIDE</span><h2>독립 캔버스 플레이그라운드</h2>
      <p>공통 편집기 조작 UX를 시험하는 별도 Vue Flow 프론트입니다. 실제 공식 n8n 엔진에 연결되지 않았습니다.</p>
      <div class="help-grid"><div><b>01 / Pan</b><span>빈 캔버스 왼쪽/가운데 드래그</span></div><div><b>02 / Select</b><span>Shift + 드래그 / 노드 클릭</span></div><div><b>03 / Edit</b><span>노드 추가·이동·삭제·연결</span></div><div><b>04 / Save</b><span>브라우저 저장 / JSON 내보내기</span></div></div>
      <div class="help-caution">모의 실행, 브라우저 저장 및 예제 데이터만 포함됩니다. n8n 서버 저장·실제 노드 실행 검증은 별도 단계입니다.</div>
      <button class="primary-btn" @click="showHelp=false">테스트 시작</button>
    </div></div>
  </div>
</template>
