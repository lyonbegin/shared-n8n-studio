/**
 * Shared n8n Studio — 50 UI node-kind contracts (version 1).
 * Reference types/recipes only: official n8n is the runtime, not this Vue Flow playground.
 * Business adapters and n8n custom extensions MUST be built by their owning projects.
 * Never store credentials, trade/bid submissions, or executable server calls here.
 */
const F=(key,label,type="text",extra={})=>({key,label,type,...extra});
const opts=(...pairs)=>pairs.map(([value,label])=>({value,label}));
const common={
  runName:[F("runName","실행 명칭")],
  schedule:[F("cron","Cron / 실행 일정","text",{placeholder:"*/15 * * * *"}),F("timezone","타임존","text",{default:"Asia/Seoul"})],
  webhook:[F("path","수신 경로"),F("method","HTTP 방식","select",{options:opts(["POST","POST"],["GET","GET"])})],
  http:[F("method","HTTP 방식","select",{options:opts(["GET","GET"],["POST","POST"],["PUT","PUT"],["PATCH","PATCH"],["DELETE","DELETE"])}),F("url","요청 URL","text",{placeholder:"https://service.example/api"}),F("credentialRef","서버 Credential 참조","text",{placeholder:"n8n credential ID; 비밀값 금지"}),F("headers","헤더 JSON","json",{default:{}}),F("body","요청 본문 JSON","json",{default:{}})],
  code:[F("code","JavaScript","code",{default:"return $input.all();"})],
  set:[F("mapping","필드 매핑 JSON","json",{default:{}})],
  if:[F("condition","조건 표현식","text",{default:"{{$json.ok === true}}"})],
  merge:[F("mode","합류 방식","select",{options:opts(["append","Append"],["combine","Combine"],["chooseBranch","Choose Branch"])})],
  wait:[F("seconds","대기 시간(초)","number",{default:5,min:0})],
  subWorkflow:[F("workflowId","하위 워크플로 ID"),F("waitForCompletion","완료까지 대기","boolean",{default:true}),F("input","입력 JSON","json",{default:{}})],
  subTrigger:[F("inputSchema","상위 워크플로 입력 스키마 JSON","json",{default:{}})],
  switch:[F("rules","분기 조건 JSON","json",{default:[{"field":"status","equals":"READY"}]})],
  loop:[F("batchSize","배치 크기","number",{default:10,min:1}),F("itemsPath","반복 대상 경로","text",{default:"$json.items"})],
  retry:[F("maxAttempts","최대 실행 횟수","number",{default:3,min:1}),F("delayMs","재시도 지연(ms)","number",{default:1000,min:0}),F("timeoutMs","제한 시간(ms)","number",{default:30000,min:1})],
  error:[F("policy","실패 대응","select",{options:opts(["stop","중단"],["continue","계속"],["fallback","대체 경로"])}),F("message","오류 메시지")],
  join:[F("mode","합류 정책","select",{options:opts(["ALL","ALL"],["ANY","ANY"],["QUORUM","QUORUM"],["ALL_SETTLED","ALL_SETTLED"])}),F("quorum","최소 성공 수","number",{default:2,min:1})],
  approval:[F("approverRole","승인자 역할","text",{default:"operator"}),F("timeoutHours","승인 기한(시간)","number",{default:24,min:1}),F("requestReason","승인 사유")],
  database:[F("operation","DB 작업","select",{options:opts(["select","SELECT"],["insert","INSERT"],["update","UPDATE"],["upsert","UPSERT"])}),F("credentialRef","DB Credential 참조"),F("query","SQL / 안전한 매개변수형 쿼리","code")],
  file:[F("action","문서 처리","select",{options:opts(["download","다운로드"],["extract","추출"],["write","쓰기"],["verify","검증"])}),F("fileRef","파일 참조/경로"),F("mimeType","MIME 유형")],
  schema:[F("jsonSchema","검증 JSON Schema","json",{default:{"type":"object"}}),F("onInvalid","실패 시","select",{options:opts(["fail","오류"],["branch","실패 분기"])})],
  evidence:[F("sourceUri","원본 출처 URI"),F("sha256","검증용 SHA-256"),F("provenance","출처 유형","select",{options:opts(["official","공식 원본"],["derived","파생/계산"],["mock","Mock"])})],
  worker:[F("queueName","작업 큐"),F("jobType","Worker 작업 유형"),F("idempotencyKey","멱등성 키 표현식")],
  lock:[F("lockKey","잠금 키 표현식"),F("ttlSeconds","잠금 유효시간(초)","number",{default:60,min:1}),F("maxConcurrency","최대 동시 실행","number",{default:1,min:1})],
  test:[F("mode","테스트 방식","select",{options:opts(["mock","Mock"],["assert","Assert"],["golden","Golden output"])}),F("mockResult","가상 결과 JSON","json",{default:{"ok":true}}),F("assertion","기대 조건")],
  parallel:[F("branchNames","병렬 경로 목록","json",{default:["branch_a","branch_b"]})],
  eventPub:[F("topic","발행 이벤트 유형"),F("payload","이벤트 JSON","json",{default:{}})],
  eventSub:[F("topic","수신 이벤트 유형"),F("correlationId","상관 ID"),F("timeoutMs","대기 제한(ms)","number",{default:60000,min:1})],
  state:[F("initialState","시작 상태","text",{default:"PENDING"}),F("transitions","상태 전이 규칙 JSON","json",{default:{}})],
  rollback:[F("compensationWorkflowId","보상 워크플로 ID"),F("onFailure","실패 조건")],
  checkpoint:[F("checkpointKey","체크포인트 키"),F("resumePolicy","복원 정책","select",{options:opts(["manual","수동"],["validated","검증 후 자동"])})],
  idem:[F("keyExpression","멱등성 키 표현식"),F("ttlSeconds","중복 판단 기간(초)","number",{default:3600,min:1})],
  dedupe:[F("keyFields","중복 판정 필드 JSON","json",{default:["id"]}),F("windowSeconds","판정 창(초)","number",{default:86400,min:1})],
  rate:[F("limit","최대 호출수","number",{default:10,min:1}),F("windowSeconds","시간 창(초)","number",{default:60,min:1})],
  breaker:[F("failureThreshold","연속 오류 기준","number",{default:5,min:1}),F("resetAfterMs","재시도 허용(ms)","number",{default:30000,min:1})],
  dead:[F("deadLetterQueue","오류 보관 큐"),F("retentionDays","보관일수","number",{default:7,min:1})],
  lease:[F("resourceKey","자원 식별 키"),F("leaseSeconds","임대 만료(초)","number",{default:30,min:1}),F("fencingToken","세대 토큰 매핑")],
  mapper:[F("mapping","출력→입력 매핑 JSON","json",{default:{"target":"$json.result"}})],
  split:[F("mode","처리 방식","select",{options:opts(["split","배열 분해"],["aggregate","결과 집계"])}),F("path","대상 JSON 경로","text",{default:"items"})],
  diff:[F("leftPath","기준값 경로"),F("rightPath","비교값 경로"),F("strategy","비교 전략","select",{options:opts(["deep","전체"],["keys","필드"])} )],
  complete:[F("requiredFields","필수 증빙 경로 JSON","json",{default:["source_id","verified_at"]}),F("threshold","최소 충족률(%)","number",{default:100,min:0,max:100})],
  hash:[F("algorithm","알고리즘","select",{options:opts(["sha256","SHA-256"],["sha512","SHA-512"])}),F("expectedHash","기대 해시")],
  provenance:[F("sourceSystem","원본 시스템"),F("recordId","공식 식별자"),F("collectedAt","수집시각 필드")],
  form:[F("formSchema","입력 양식 JSON","json",{default:{"fields":[]}}),F("submitPolicy","입력 승인 정책","select",{options:opts(["manual","사람 입력"],["session","인증 세션"])})],
  permission:[F("requiredRole","필요 역할"),F("action","허용할 동작"),F("approvalRequired","별도 승인 필요","boolean",{default:true})],
  alert:[F("channel","알림 채널","select",{options:opts(["email","이메일"],["webhook","Webhook"],["inapp","화면 알림"])}),F("message","메시지 템플릿")],
  metrics:[F("metricName","지표명"),F("valuePath","값 JSON 경로"),F("unit","단위")],
  probe:[F("watchPaths","관측 JSON 경로","json",{default:["$json"]}),F("captureInputs","입력 기록","boolean",{default:true})],
  replay:[F("savedRunId","재현할 실행 ID"),F("dryRun","드라이런 제한","boolean",{default:true})],
  fault:[F("fault","주입할 장애","select",{options:opts(["timeout","Timeout"],["http429","HTTP 429"],["http503","HTTP 503"],["exception","Exception"])}),F("probability","장애 확률(0-1)","number",{default:1,min:0,max:1})],
  business:[
    F("adapter","업무 어댑터","select",{options:opts(["investment","주식 자동화"],["procureflow","ProcureFlow"])}),
    F("executionMode","실행 방식","select",{options:opts(["api","API"],["javascript","Code"],["python","Python 함수"],["workflow","하위 Workflow"],["mock","Mock"])}),
    F("operationId","프로젝트 연산 ID / 업무 블록 ID","text",{placeholder:"주식: operation_id / 조달: H05"}),
    F("javascriptCode","Code 실행 내용","code",{default:"return $input.all();"}),
    F("apiUrl","API URL"),F("method","HTTP 방식","select",{options:opts(["POST","POST"],["GET","GET"])}),
    F("pythonFunction","Python 함수 식별자"),
    F("workflowId","호출할 하위 n8n 워크플로 ID"),
    F("credentialRef","서버 Credential 참조 (비밀값 금지)"),
    F("arguments","입력 인자 JSON","json",{default:{}}),
    F("mockResult","Mock 결과 JSON","json",{default:{"ok":true}}),
    F("timeoutMs","시간 제한(ms)","number",{default:30000,min:1})
  ]
};
const paletteRows=[
  ["trigger","Manual Trigger","트리거","▶","사용자가 직접 시작","native","n8n-nodes-base.manualTrigger","runName"],
  ["schedule","Schedule","트리거","◷","Cron / 일정 시작","native","n8n-nodes-base.scheduleTrigger","schedule"],
  ["webhook","Webhook","트리거","⌁","외부 이벤트 수신","native","n8n-nodes-base.webhook","webhook"],
  ["http","HTTP Request","처리","↗","HTTP API 호출","native","n8n-nodes-base.httpRequest","http"],
  ["code","Code","처리","{ }","JavaScript 코드 실행","native","n8n-nodes-base.code","code"],
  ["set","Edit Fields","처리","≡","데이터 필드 매핑","native","n8n-nodes-base.set","set"],
  ["if","IF","논리","◇","참/거짓 조건 분기","native","n8n-nodes-base.if","if"],
  ["merge","Merge","논리","⋈","여러 경로 병합","native","n8n-nodes-base.merge","merge"],
  ["wait","Wait","논리","◴","지연·이벤트 대기","native","n8n-nodes-base.wait","wait"],
  ["execute-workflow","Execute Sub-workflow","워크플로 제어","⤴","다른 워크플로 호출","native","n8n-nodes-base.executeWorkflow","subWorkflow"],
  ["subworkflow-trigger","Sub-workflow Trigger","워크플로 제어","⤵","상위 워크플로 호출 수신","native","n8n-nodes-base.executeWorkflowTrigger","subTrigger"],
  ["switch","Switch","논리","⑂","복수 조건 라우팅","native","n8n-nodes-base.switch","switch"],
  ["loop","Loop / Batch","워크플로 제어","↻","목록·구간 단위 반복","native","n8n-nodes-base.splitInBatches","loop"],
  ["retry","Retry / Timeout","오류·복구","⟳","제한된 재시도·시간 초과","composite",null,"retry"],
  ["error-halt","Error Handler / HALT","오류·복구","⏹","오류 분기·실행 중단","composite","n8n-nodes-base.stopAndError","error"],
  ["join-quorum","Join / Quorum","논리","⋈","ALL·ANY·QUORUM 합류","extension",null,"join"],
  ["approval","Human Approval","워크플로 제어","✓","승인·보류·재개","extension",null,"approval"],
  ["database","Database","연결·저장","▤","DB 조회·기록","native","n8n-nodes-base.postgres","database"],
  ["file-document","File / Document","연결·저장","▧","파일 다운로드·문서 처리","composite",null,"file"],
  ["schema-validator","Schema Validator","데이터·검증","☷","JSON 스키마 검증","extension",null,"schema"],
  ["evidence-audit","Evidence / Audit","데이터·검증","⚑","공식 원본·감사 증빙","extension",null,"evidence"],
  ["worker-queue","Worker / Queue","실행·자원","▦","비동기 Job 등록·결과","extension",null,"worker"],
  ["resource-lock","Resource / Lock","실행·자원","⊡","동시성·점유권 제어","extension",null,"lock"],
  ["test-mock-assert","Test / Mock / Assert","테스트·디버깅","◉","모의 입력과 검증","extension",null,"test"],
  ["parallel-fork","Parallel Fork","워크플로 제어","⑃","독립 분기 동시 실행","composite",null,"parallel"],
  ["event-publish","Event Publish","이벤트·상태","↥","이벤트 발행","extension",null,"eventPub"],
  ["event-subscribe","Event Subscribe / Wait","이벤트·상태","↧","이벤트 수신·대기","extension",null,"eventSub"],
  ["state-machine","State Machine","이벤트·상태","◈","상태 전이 검증","extension",null,"state"],
  ["compensation","Compensation / Rollback","오류·복구","↶","실패 작업 보상·무효화","extension",null,"rollback"],
  ["checkpoint","Checkpoint / Resume","오류·복구","▣","중단 지점 저장·복원","extension",null,"checkpoint"],
  ["idempotency","Idempotency","실행·자원","≍","요청 중복 실행 방지","extension",null,"idem"],
  ["deduplication","Deduplication","데이터·검증","≠","데이터 중복 제거","extension",null,"dedupe"],
  ["rate-limit","Rate Limit","실행·자원","◷","API 빈도 제한","extension",null,"rate"],
  ["circuit-breaker","Circuit Breaker","오류·복구","⚡","장애 확산 차단","extension",null,"breaker"],
  ["dead-letter-queue","Dead Letter Queue","오류·복구","▥","실패 작업 격리 보관","extension",null,"dead"],
  ["lease-fencing","Lease / Fencing","실행·자원","⌗","임대 소유권·세대 토큰","extension",null,"lease"],
  ["data-mapper","Data Mapper","데이터·검증","⇄","입력·출력 필드 매핑","composite",null,"mapper"],
  ["split-aggregate","Split / Aggregate","데이터·검증","⑆","배열 분해 및 집계","composite",null,"split"],
  ["json-diff","JSON Diff / Compare","데이터·검증","≡","원본·버전 비교","extension",null,"diff"],
  ["completeness","Completeness Gate","데이터·검증","▣","필수 근거 완전성 검증","extension",null,"complete"],
  ["hash-integrity","Hash / Integrity","데이터·검증","♯","원본 해시·무결성 검사","extension",null,"hash"],
  ["source-provenance","Source Provenance","데이터·검증","◎","공식·파생·가상 출처 추적","extension",null,"provenance"],
  ["human-form","Human Input / Form","워크플로 제어","▤","사용자 입력·선택","extension",null,"form"],
  ["permission-gate","Permission Gate","워크플로 제어","▩","역할·권한·실행 허가","extension",null,"permission"],
  ["notification-alert","Notification / Alert","이벤트·상태","♧","경고·승인 알림","composite",null,"alert"],
  ["metrics-counter","Metrics / Counter","테스트·디버깅","▥","실행 성과·건수 계측","extension",null,"metrics"],
  ["execution-probe","Execution Probe","테스트·디버깅","⌕","노드 입출력·중간 상태 관측","extension",null,"probe"],
  ["replay","Replay","테스트·디버깅","↺","이전 실행 입력 재현","extension",null,"replay"],
  ["fault-injection","Fault Injection","테스트·디버깅","⚠","시험용 장애 주입","extension",null,"fault"],
  ["business-operation","Business Operation","업무 실행","⚙","Code·API·Python·Workflow·Mock 통합","extension",null,"business"]
];
const groups=["트리거","처리","논리","워크플로 제어","연결·저장","데이터·검증","이벤트·상태","실행·자원","오류·복구","테스트·디버깅","업무 실행"];
const colors={"트리거":"#ec6384","처리":"#27aa99","논리":"#e6a640","워크플로 제어":"#778ce4","연결·저장":"#448ed3","데이터·검증":"#35a8b0","이벤트·상태":"#a28aea","실행·자원":"#b58842","오류·복구":"#e47559","테스트·디버깅":"#7979b8","업무 실행":"#0c927b"};
const outputs={"if":["true","false"],"switch":["path_1","path_2","fallback"],"loop":["loop","done"],"retry":["success","timeout","failed"],"error-halt":["recovered","halt"],"approval":["approved","rejected","timeout"],"join-quorum":["joined","insufficient"],"schema-validator":["valid","invalid"],"completeness":["complete","incomplete"],"permission-gate":["allow","deny"],"test-mock-assert":["pass","fail"],"circuit-breaker":["closed","open"],"state-machine":["accepted","rejected"],"fault-injection":["success","fault"],"business-operation":["success","error"]};
const configVisibility={
"business-operation":{javascriptCode:"javascript",apiUrl:"api",method:"api",pythonFunction:"python",workflowId:"workflow",mockResult:"mock"}
};
export const NODE_GROUPS=Object.freeze(groups);
export const NODE_CATALOG=Object.freeze(paletteRows.map(([kind,name,group,icon,description,implementation,nativeType,fieldGroup],index)=>Object.freeze({
  number:index+1,kind,name,group,icon,color:colors[group],description,
  implementation,nativeType,n8nEngine:"official",inputs:["main"],outputs:outputs[kind]||["main"],
  fields:common[fieldGroup]||[],fieldVisibility:configVisibility[kind]||{},
  release:"spec-v1",browserImplementation:"palette/config/graph-only"
})));
export const NODE_BY_KIND=Object.freeze(Object.fromEntries(NODE_CATALOG.map(item=>[item.kind,item])));
export const getNode=(kind)=>NODE_BY_KIND[kind];
export function defaultParameters(kind){
  const spec=getNode(kind);
  if(!spec)throw Error("Unknown node kind: "+kind);
  return Object.fromEntries(spec.fields.map(f=>[f.key,f.default!==undefined?JSON.parse(JSON.stringify(f.default)):f.type==="select"?(f.options?.[0]?.value||""):f.type==="boolean"?false:f.type==="number"?0:f.type==="json"?{}:""]));
}
export function visibleFields(spec,params){
  return spec.fields.filter(f=>!spec.fieldVisibility[f.key] || spec.fieldVisibility[f.key]===params?.executionMode);
}
export function validateParameters(kind,params){
  const node=getNode(kind);
  if(!node)return ["Unknown node kind: "+kind];
  if(!params||typeof params!=="object"||Array.isArray(params))return ["Parameters must be a JSON object"];
  const errs=[];
  for(const f of node.fields){
    if(!(f.key in params))continue;
    const v=params[f.key];
    if(f.type==="number"&&(typeof v!=="number"||!Number.isFinite(v)||f.min!==undefined&&v<f.min||f.max!==undefined&&v>f.max))errs.push(f.label+": invalid number");
    if(f.type==="boolean"&&typeof v!=="boolean")errs.push(f.label+": invalid boolean");
    if(f.type==="select"&&!f.options.some(o=>o.value===v))errs.push(f.label+": invalid option");
  }
  return errs;
}
export function validateCatalog(){
  if(NODE_CATALOG.length!==50)throw Error("Expected exactly 50 node types");
  const ids=NODE_CATALOG.map(n=>n.kind);
  if(new Set(ids).size!==ids.length)throw Error("Duplicate node kind");
  if(NODE_CATALOG.filter(n=>n.implementation==="native").length<9)throw Error("Native set missing");
  for(const n of NODE_CATALOG)if(!NODE_GROUPS.includes(n.group)||!n.outputs.length)throw Error("Invalid node group or output: "+n.kind);
  return true;
}
validateCatalog();
