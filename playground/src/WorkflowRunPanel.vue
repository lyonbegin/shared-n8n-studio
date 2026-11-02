<script setup>
import {ref,watch} from 'vue';
const props=defineProps({open:Boolean,config:{type:Object,default:()=>({})},
  running:Boolean,workflowName:String});
const emit=defineEmits(['close','execute']);
const values=ref({}),error=ref('');
watch(()=>props.open,open=>{
  if(open){values.value=Object.fromEntries((props.config.fields||[]).filter(f=>f.type!=='file_csv'&&f.type!=='file_image').map(f=>[f.key,f.default||'']));error.value='';}
},{immediate:true});
async function fileChange(field,event){
  const file=event.target.files?.[0];
  if(!file){values.value[field.key]='';return;}
  if(file.size>(field.max_bytes||1000000)){error.value=field.label+' 크기 제한 초과';return;}
  if(field.type==='file_csv'){
    values.value[field.key]=await file.text();return;
  }
  if(!['image/png','image/jpeg'].includes(file.type)){error.value='PNG/JPEG 이미지만 허용됩니다.';return;}
  values.value[field.key]=await new Promise((resolve,reject)=>{
    const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(new Error('파일 읽기 오류'));r.readAsDataURL(file);
  });
}
function execute(){
  error.value='';
  try{
    const data={...values.value};
    for(const f of props.config.fields||[]){
      if(f.type==='json'){
        data[f.key]=JSON.parse(data[f.key]||'{}');
        if(!data[f.key]||typeof data[f.key]!=='object'||Array.isArray(data[f.key]))throw Error(f.label+' JSON 객체가 필요합니다.');
      }
      if(f.required&&(!data[f.key]||String(data[f.key]).trim()===''))throw Error(f.label+' 입력이 필요합니다.');
    }
    emit('execute',data);
  }catch(e){error.value=e.message;}
}
</script>
<template>
  <div v-if="open" class="workflow-run-overlay" data-testid="workflow-run-panel" @click.self="$emit('close')">
    <section class="workflow-run-dialog" role="dialog" aria-label="워크플로 실행 입력">
      <header class="workflow-run-header">
        <div><h3>▶ {{workflowName}} · 실제 입력자료 실행</h3>
          <p>입력자료는 노드 실행 서비스로 전달됩니다. 차트는 마지막 검증 노드의 결과 버튼에서 별도로 엽니다.</p>
        </div><button aria-label="실행 입력 닫기" @click="$emit('close')">×</button>
      </header>
      <p v-if="error" role="alert" class="workflow-run-error">{{error}}</p>
      <div class="workflow-run-fields">
        <label v-for="field in config.fields||[]" :key="field.key">
          <span>{{field.label}} {{field.required?'*':''}}</span>
          <input v-if="field.type==='text'||field.type==='url'" :data-run-field="field.key"
            :type="field.type" v-model="values[field.key]" :placeholder="field.placeholder||''"/>
          <textarea v-else-if="field.type==='textarea'||field.type==='json'"
            :data-run-field="field.key" v-model="values[field.key]"
            :rows="field.rows||4" spellcheck="false"/>
          <input v-else-if="field.type==='file_csv'||field.type==='file_image'"
            :data-run-field="field.key" type="file" :accept="field.type==='file_csv'?'.csv,text/csv':'image/png,image/jpeg'"
            @change="fileChange(field,$event)"/>
          <small v-if="field.help">{{field.help}}</small>
        </label>
      </div>
      <p class="workflow-run-warning">실제 TradingView 원본 코드·CSV·원본 차트 이미지 없이 동등성 PASS로 처리하지 않습니다. 비공개 코드·계정 키 등 민감한 정보는 공개 테스트 서비스에 올리지 마세요.</p>
      <div class="workflow-run-actions">
        <button @click="$emit('close')">취소</button>
        <button data-testid="workflow-run-start" :disabled="running" @click="execute">{{running?'서버 실행 중…':'▶ 입력자료로 전체 검증 실행'}}</button>
      </div>
    </section>
  </div>
</template>
<style scoped>
.workflow-run-overlay{position:fixed;inset:0;background:rgba(13,26,46,.55);z-index:2500;display:flex;align-items:center;justify-content:center;padding:15px}
.workflow-run-dialog{width:min(720px,98vw);max-height:95vh;overflow:auto;background:#fff;border-radius:12px;padding:20px;color:#213146;box-shadow:0 15px 50px #14203455}
.workflow-run-header{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid #dce4ed;padding-bottom:10px}
.workflow-run-header h3{font-size:16px;margin:0}.workflow-run-header p{font-size:12px;color:#64748b}
.workflow-run-header button{border:0;background:transparent;font-size:24px;cursor:pointer}
.workflow-run-fields{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}
.workflow-run-fields label{display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:650;min-width:0}
.workflow-run-fields label:has(textarea),.workflow-run-fields label:has(input[type=file]){grid-column:span 2}
.workflow-run-fields input,.workflow-run-fields textarea{font:12px/1.5 ui-monospace,Consolas,monospace;padding:9px;border:1px solid #bdcadb;border-radius:6px;color:#1d3047;background:#fff;width:100%;box-sizing:border-box}
.workflow-run-fields small{font-size:11px;color:#71819a;font-weight:400}
.workflow-run-warning{font-size:12px;line-height:1.55;color:#96641c;background:#fff8e8;border-radius:6px;padding:10px}
.workflow-run-error{color:#b42339;font-size:12px}
.workflow-run-actions{display:flex;justify-content:flex-end;gap:8px}
.workflow-run-actions button{border-radius:6px;border:1px solid #8c9fb7;padding:10px 14px;background:#f2f6fc;cursor:pointer}
.workflow-run-actions button:last-child{background:#1769bd;border-color:#1769bd;color:#fff}
.workflow-run-actions button:disabled{opacity:.5}
@media(max-width:620px){.workflow-run-fields{grid-template-columns:1fr}.workflow-run-fields label:has(textarea),.workflow-run-fields label:has(input[type=file]){grid-column:auto}}
</style>