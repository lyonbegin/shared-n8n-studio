<script setup>
import {ref,computed,watch} from 'vue';

const props=defineProps({
  open:Boolean, workflow:String, nodeId:String, nodeName:String,
  defaultInput:{type:Object,default:()=>({})},
  defaultDraft:{type:Object,default:()=>({kind:'none'})},
  canRun:Boolean, running:Boolean, runResult:{type:Object,default:null},
  runHistory:{type:Array,default:()=>[]}
});
const emit=defineEmits(['close','run']);
const loading=ref(false),saving=ref(false),revision=ref(0),error=ref('');
const inputText=ref('{}'),draft=ref({kind:'none'}),revisions=ref([]),oldVersion=ref('');
const status=ref(''),loadedKey=ref('');
const stringify=x=>JSON.stringify(x,null,2);
const recordKey=computed(()=>props.workflow+':'+props.nodeId);
const outputs=computed(()=>props.runHistory.filter(x=>x.status==='SUCCESS'&&x.output_json));
const changeSummary=computed(()=>{
  const latest=outputs.value[0]?.output_json||props.runResult?.output_json;
  const previous=outputs.value[1]?.output_json;
  if(!latest||!previous)return null;
  const keys=[...new Set([...Object.keys(latest),...Object.keys(previous)])].sort();
  return keys.filter(k=>JSON.stringify(latest[k])!==JSON.stringify(previous[k])).map(k=>({
    key:k,before:previous[k],after:latest[k]
  }));
});
function resetFromRecord(w){
  revision.value=w.revision||0;
  inputText.value=stringify(w.revision?w.input_json:props.defaultInput);
  draft.value={...props.defaultDraft,...(w.revision?w.execution_draft:{})};
}
async function load(){
  if(!props.open||!props.workflow||!props.nodeId)return;
  const key=recordKey.value;
  error.value='';loading.value=true;
  try{
    const query=new URLSearchParams({workflow:props.workflow,node_id:props.nodeId});
    const [r,h]=await Promise.all([
      fetch('/api/studio/nodes/workspace?'+query,{credentials:'same-origin',cache:'no-store'}),
      fetch('/api/studio/nodes/workspace/revisions?'+query,{credentials:'same-origin',cache:'no-store'})
    ]);
    if(!r.ok||!h.ok)throw Error('노드 설정 API '+(r.ok?h.status:r.status));
    const payload=await r.json(),hist=await h.json();
    if(!props.open||recordKey.value!==key)return;
    resetFromRecord(payload.workspace);
    revisions.value=hist.revisions||[];
    loadedKey.value=key;status.value=revision.value?'저장된 설정 v'+revision.value:'첫 실행 설정';
  }catch(e){error.value=e.message;}finally{loading.value=false;}
}
watch(()=>[props.open,props.workflow,props.nodeId],()=>{if(props.open)load();},{immediate:true});
async function save(){
  if(saving.value||loading.value)return false;
  error.value='';saving.value=true;
  try{
    const input=JSON.parse(inputText.value);
    if(!input||Array.isArray(input)||typeof input!=='object')throw Error('INPUT JSON 객체가 필요합니다');
    const response=await fetch('/api/studio/nodes/workspace',{
      method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({workflow:props.workflow,node_id:props.nodeId,expected_revision:revision.value,
        input_json:input,execution_draft:draft.value})
    });
    const data=await response.json();
    if(!response.ok)throw Error(data.error||'설정 저장 실패 '+response.status);
    revision.value=data.workspace.revision;
    revisions.value=[{revision:revision.value,input_json:input,execution_draft:{...draft.value},
      updated_at:data.workspace.updated_at},...revisions.value].slice(0,50);
    status.value='SQLite 설정 저장 완료 · v'+revision.value;
    return true;
  }catch(e){error.value=e.message;return false;}finally{saving.value=false;}
}
async function saveAndRun(){
  if(!props.canRun){error.value='이 노드에는 검증된 실행 어댑터가 없습니다. 수정된 URL/코드는 저장만 가능합니다.';return;}
  if(await save())emit('run',JSON.parse(inputText.value));
}
function restoreVersion(){
  const previous=revisions.value.find(r=>String(r.revision)===oldVersion.value);
  if(!previous)return;
  inputText.value=stringify(previous.input_json);draft.value={...previous.execution_draft};
  status.value='v'+previous.revision+'의 값을 불러왔습니다. 현재 버전으로 저장하면 새 이력이 생성됩니다.';
}
</script>

<template>
  <div v-if="open" class="shared-workspace-overlay" data-testid="shared-node-workspace" @click.self="$emit('close')">
    <section class="shared-workspace-panel" role="dialog" aria-modal="true" aria-label="노드 실행·설정 작업 공간">
      <header class="shared-workspace-head">
        <div><strong>{{nodeName}}</strong><small> 공통 노드 작업 공간 · {{nodeId}} · 설정 v{{revision}}</small></div>
        <button class="shared-workspace-close" aria-label="노드 작업 공간 닫기" @click="$emit('close')">×</button>
      </header>
      <div v-if="loading">저장된 설정을 불러오는 중입니다.</div>
      <template v-else>
        <p v-if="error" class="shared-workspace-error" data-testid="workspace-error">{{error}}</p>
        <p v-if="status" class="shared-workspace-status" data-testid="workspace-status">{{status}}</p>
        <div class="shared-workspace-columns">
          <div class="shared-workspace-section">
            <h4>① INPUT JSON · 직접 수정</h4>
            <textarea data-testid="workspace-input" v-model="inputText" aria-label="노드 실행 입력 JSON" spellcheck="false" rows="9"></textarea>
            <p>수정 후 저장하면 기존 값을 덮지 않고 새 이력으로 남습니다.</p>
            <div class="shared-workspace-actions">
              <button data-testid="workspace-save" :disabled="saving" @click="save">설정 버전 저장</button>
              <button data-testid="workspace-save-run" :disabled="saving||running||!canRun" @click="saveAndRun">저장 후 ▶ 다시 실행</button>
            </div>
            <h4>② 입력·실행 설정 수정 이력</h4>
            <div class="shared-workspace-actions">
              <select data-testid="workspace-revision" v-model="oldVersion" aria-label="이전 입력 버전 선택">
                <option value="">이전 버전 선택</option>
                <option v-for="r in revisions" :key="r.revision" :value="String(r.revision)">v{{r.revision}} · {{r.updated_at}}</option>
              </select>
              <button data-testid="workspace-restore" :disabled="!oldVersion" @click="restoreVersion">선택 버전 불러오기</button>
            </div>
            <p>이전 버전을 불러온 뒤 저장하면 새 버전이 생성됩니다.</p>
          </div>
          <div class="shared-workspace-section">
            <h4>③ API·Python 실행 설정 (초안)</h4>
            <label>실행 유형</label>
            <select v-model="draft.kind" data-testid="workspace-execution-kind">
              <option value="none">미설정</option><option value="http">HTTP API</option>
              <option value="python">Python</option><option value="n8n">n8n</option>
            </select>
            <template v-if="draft.kind==='http'">
              <label>HTTP 메서드</label><select v-model="draft.http_method" data-testid="workspace-http-method">
                <option>GET</option><option>POST</option><option>PUT</option><option>PATCH</option><option>DELETE</option>
              </select>
              <label>API URL</label><input v-model="draft.api_url" data-testid="workspace-api-url" placeholder="https://api.example.com/..." />
            </template>
            <template v-if="draft.kind==='python'">
              <label>Python 모듈·함수</label>
              <input v-model="draft.python_module" data-testid="workspace-python-module" placeholder="app.module"/>
              <input v-model="draft.python_function" data-testid="workspace-python-function" placeholder="function_name"/>
              <label>Python 실행 코드 초안</label>
              <textarea v-model="draft.python_code" data-testid="workspace-python-code" rows="7" spellcheck="false" placeholder="검토·배포 전까지 서버에서 실행하지 않습니다."/>
            </template>
            <label>변경 이유·설명</label>
            <textarea v-model="draft.notes" data-testid="workspace-notes" rows="2"/>
            <p><b>실행 코드/URL을 수정해도 즉시 실행되지 않습니다.</b> 공통 모듈은 수정 이력만 저장하고, 프로젝트 실행 어댑터에서 검증·승인된 코드를 배포한 후 실행합니다. 인증정보를 이곳에 붙여 넣지 마세요.</p>
            <h4>④ 실제 실행 결과</h4>
            <p v-if="!canRun">현재 노드에 연결된 실행 어댑터가 없습니다.</p>
            <template v-if="runResult">
              <p data-testid="workspace-run-status">상태 {{runResult.status}} · {{runResult.duration_ms}} ms · 코드 {{runResult.code_version}}</p>
              <pre data-testid="workspace-run-output">{{stringify(runResult.output_json)}}</pre>
              <p v-if="runResult.error">{{runResult.error}}</p>
            </template>
            <p v-else>이 노드에서 실행한 결과가 아직 없습니다.</p>
            <h4>⑤ 이전 실행과 출력 비교</h4>
            <p v-if="changeSummary===null">비교할 성공 실행 결과가 2건 이상 필요합니다.</p>
            <p v-else-if="changeSummary.length===0">직전 성공 실행과 출력 JSON이 같습니다.</p>
            <div v-else data-testid="workspace-output-diff">
              <div v-for="change in changeSummary" :key="change.key" class="shared-workspace-diff">
                <b>{{change.key}}</b>
                <pre>이전: {{stringify(change.before)}}</pre>
                <pre>이번: {{stringify(change.after)}}</pre>
              </div>
            </div>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.shared-workspace-overlay{position:fixed;inset:0;background:rgba(15,23,42,.48);z-index:2200;display:flex;align-items:center;justify-content:center;padding:20px}
.shared-workspace-panel{background:#fff;color:#18243b;border-radius:12px;width:min(1100px,98vw);max-height:94vh;overflow:auto;padding:20px;box-shadow:0 14px 60px #14203444}
.shared-workspace-head{display:flex;justify-content:space-between;gap:14px;border-bottom:1px solid #dde5ef;padding-bottom:12px;margin-bottom:14px}
.shared-workspace-head strong{font-size:17px}.shared-workspace-head small{display:block;color:#66728b;padding-top:5px}
.shared-workspace-close{font-size:24px;border:0;background:transparent;cursor:pointer}
.shared-workspace-columns{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.shared-workspace-section{min-width:0}
.shared-workspace-section h4{font-size:13px;margin:14px 0 7px}
.shared-workspace-section label{font-size:12px;font-weight:600;display:block;margin:9px 0 4px}
.shared-workspace-section textarea,.shared-workspace-section input,.shared-workspace-section select{background:white;color:#18243b;border:1px solid #c8d4e2;border-radius:5px;padding:8px;width:100%;max-width:100%;box-sizing:border-box;font:12px/1.5 ui-monospace,Consolas,monospace}
.shared-workspace-section p{font-size:11px;color:#657189}
.shared-workspace-actions{display:flex;gap:8px;margin:9px 0}
.shared-workspace-actions button{background:#eef3fa;color:#1b375e;border:1px solid #b7c8df;border-radius:6px;padding:8px;cursor:pointer;font-size:12px;white-space:nowrap}
.shared-workspace-actions button:disabled{opacity:.5;cursor:not-allowed}
.shared-workspace-section pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:230px;overflow:auto;background:#f1f5fb;padding:9px;border-radius:6px;font-size:11px}
.shared-workspace-status{font-size:12px;color:#176b42}.shared-workspace-error{color:#a12336}
.shared-workspace-diff{border-top:1px solid #dce3ed;margin-top:8px}
@media(max-width:740px){.shared-workspace-columns{grid-template-columns:1fr}.shared-workspace-overlay{padding:4px}}
</style>
