# 주식 자동화 — 공통 50종 노드 실제 구현·연결 지침

> 대상 저장소: [lyonbegin/autonomous-investor-backend](https://github.com/lyonbegin/autonomous-investor-backend)  
> 원본 유지: 기존 주식 백엔드, TradingView, 투자 엔진 12종, F01/F03/F05 운영 JSON 및 10개 합성 시나리오 변경 금지(격리 브랜치에서 복사해 실험).  
> 공통 계약: [SHARED_NODE_50_SPEC_KO.md](./SHARED_NODE_50_SPEC_KO.md). UI 소스: [node-catalog.js](../playground/src/node-catalog.js).

## 1. 무엇을 구현하는가

- 주식 프로젝트에 **업무 함수 140개를 별도 노드 클래스 140개로 복제하지 않습니다.** \`Business Operation\`의 \`adapter=investment\`, \`operationId\`에 실제 Python 함수/서비스 API를 매핑합니다.
- 함수 명세의 실제 원천은 \`app/alpha_nodes/inventory.py\`의 \`OPERATIONS\`과 \`app/alpha_nodes/investment_flow.py\`의 \`CONTROL\`입니다. \`GET /api/v1/alpha/investment/node-types\`를 관리자 인증 프록시를 거쳐 읽어 각 함수 입력, 출력, 실행 허용 상태를 채웁니다.
- 기본 n8n 실행/관측은 공식 n8n 엔진으로만 구성합니다. 화면의 \`kind\`는 카탈로그 식별자일 뿐 n8n 실행 노드의 \`type\`이 아닙니다.

## 2. 구현 파일·출처

| 실제 소스 | 활용할 데이터/계약 |
|---|---|
| \`app/alpha_nodes/inventory.py\` | 12개 엔진, 래퍼 함수 명칭·시그니처·\`operation_id\`·기본 차단 유형 |
| \`app/alpha_nodes/palette.py\` | 함수별 입력/출력 포트, read-only/blocked 정보 |
| \`app/alpha_nodes/investment_flow.py\` | 제어 노드 \`identity/join/approval\`, 버전·승인·실행/이벤트·멱등성 |
| \`app/alpha_nodes/investment_api.py\` | \`/api/v1/alpha/investment/node-types\`, \`workflows\`, \`runs\`, \`events\` |
| \`app/alpha_nodes/api.py\` | 직접 엔진 함수 호출 \`/api/v1/alpha/modules/{engine}/{source}/{module}/{function}/execute\` |
| \`n8n/workflows/operations/F01-strategy-sync.json\` | 15분 주기 전략 풀 증분 수집 |
| \`n8n/workflows/operations/F03-agent-allocation.json\` | 1분 주기 PAPER 에이전트 할당 |
| \`n8n/workflows/operations/F05-independent-audit.json\` | 1분 주기 독립 감사 |
| \`n8n/workflows/scenarios/*.json\` | 10개 합성 실패/복구 시나리오 (운영 실거래 증빙 아님) |

## 3. 50종 중 실제 업무에 필요한 조합

| 업무 단계 | 공통 노드 종류 | n8n 실행 매핑 |
|---|---|---|
| 시장 탐색·증분 수집 | Schedule + Business Operation | Schedule Trigger + 프로젝트 전략 수집 API |
| TradingView 실시간 이벤트 | Webhook + Schema Validator | Webhook + 검증 노드(별도 수신 계약) |
| Pine 수집·해시·버전 | Business Operation + Hash/Integrity + Deduplication | Python/API + 무결성·중복 검증 |
| 12개 Python 엔진 연구 | Parallel Fork + Business Operation + Join/Quorum | 12개 서버측 함수 호출 후 합류; 결과 정책 검증 |
| 전략·에이전트 배정 | Resource/Lock + Lease/Fencing + Business Operation | DB 원자 배정·세대 검증 API |
| 모델 학습·장시간 백테스트 | Worker/Queue + Checkpoint + Retry/Timeout | 백그라운드 Job API + 영속적 상태 조회 |
| 전략 승인/위험 | Schema Validator + Permission Gate + Human Approval | 인증된 승인 기록·위험 게이트 |
| Nautilus PAPER | Business Operation + Idempotency + Error/HALT | PAPER 허용 작업만, LIVE 주문 호출 차단 |
| 오류·원장 대조 | Event Subscribe + JSON Diff + Evidence/Audit | 이벤트/실행 상태/입출력 비교 |
| 디버깅 | Execution Probe + Test/Mock/Assert + Replay | 격리된 실행 기록/복원, 네이티브 실제 로그 |

## 4. Business Operation 사용 예시

\`\`\`json
{
  "kind": "business-operation",
  "data": {
    "parameters": {
      "adapter": "investment",
      "executionMode": "python",
      "operationId": "qlib.app.bridge.predict",
      "pythonFunction": "qlib.app.bridge.predict",
      "arguments": {"example": "test-only"},
      "timeoutMs": 30000,
      "credentialRef": "investment_server_credential"
    }
  }
}
\`\`\`

이 JSON은 **공통 팔레트/화면 설정 예시**입니다. Python 함수의 구체적인 매개변수는 \`/node-types\`가 반환하는 실제 \`inputs\`를 읽어 UI 양식을 구성하고, 실행 직전 서버에서 재검증합니다. 위 \`example\` 값은 실제 \`qlib.predict\` 매개변수라고 주장하지 않습니다.

**실행 경로 (권장)**

\`\`\`text
Browser (node kind + operation_id + args only)
  -> 사용자 인증된 n8n 서버
  -> 공식 n8n Execute / HTTP Request 노드
  -> 같은 프로젝트 투자 API gateway
  -> operation_id allowlist + 주식 프로젝트 정책/승인/멱등성 검사
  -> Python 12엔진 래퍼 / Worker (실행 허용 작업에 한함)
  -> run_id / node_id / 출력 JSON / 실제 오류 / 이벤트
  -> n8n Executions 및 공통 Inspector
\`\`\`

\`operation_id\`는 기존 \`OPERATIONS\`에서 조회해야 합니다. 백엔드에서 해당 \`operation_id\`의 \`endpoint\`를 찾아 서버측으로 요청하며 외부 사용자의 임의 함수 경로를 그대로 \`import\`/ \`eval\`하지 않습니다. 호출 전 \`_operation_status\`와 \`_validate_gate\`의 제한을 재검증합니다. API Key는 n8n Credential/서버 게이트웨이에 두고 프론트에서는 받지 않습니다.

### F01/F03/F05 기존 API 활용

실제로 소스에서 발견되는 업무 URL은 다음입니다. 아래는 **API 계약 참조이며 자동으로 실행하지 않습니다.**

- F01: \`POST /api/v1/ops/strategies/sync\`, \`GET /api/v1/ops/strategies\`
- F03: \`POST /api/v1/ops/assignments/allocate-one\`, \`GET /api/v1/ops/agents\`
- F05: \`POST /api/v1/ops/audit/reconcile\`, \`GET /api/v1/ops/audit/findings\`

예: **F01** \`Schedule Trigger → Business Operation(mode=api, 투자 API 전략 증분 수집) → Schema Validator → Evidence/Audit\`. F03에는 Resource/Lock·Lease, F05에는 Compare·HALT 계약을 추가해 각 기능을 캔버스에서 구분합니다. **이 설계도가 실제 F01/F03/F05에 이미 반영됐다고 표시하지 않습니다.**

## 5. 연결선/합류/권한 구현

투자 프로젝트의 기존 \`FlowEdge\`는 \`target_input\`, \`output_path\`, \`on_status\`, \`optional\`, \`when\`, \`transform\`을 정의합니다. 공통 캔버스 연결선 속성은 **실제 Python 함수 인자 포트**와 연결되도록 이 모델로 매핑합니다.

- \`Join/Quorum\`의 \`ALL/ANY/QUORUM/ALL_SETTLED\`는 서버측 실제 결과 수로 평가하며 단순 Merge append로 바꿔서는 안 됩니다.
- \`control.approval\` 승인 후 재개는 기록된 승인자·권한·실행 버전 기반이어야 합니다.
- \`Risk/HALT\` 실패는 PAPER 실행을 차단하며 승인 없는 LIVE 주문 호출을 허용하지 않습니다.
- 백테스트/연구 job의 완료, 모델 준비, 브로커 주문/체결 결과는 서로 다른 사실로 표시합니다.

## 6. 구현 순서와 실제 Chrome 검증

1. 운영 보존 → 별도 feature 브랜치/격리 n8n 인스턴스 생성.
2. 50종 공통 카탈로그의 \`kind,fields,outputs\` 참조; 기본/조합 노드를 실제 n8n 타입과 매핑. **미구현 확장 노드는 '설정 가능/실행 불가'**로 표시.
3. \`Business Operation\`부터 주식 프로젝트의 인증된 \`/node-types\`/함수 API와 연결. 137+3 타입을 동적 목록으로 노출(코드에 가짜 140개 목록 생성 금지).
4. 서버 저장·게시·재접속·실행·승인·출력/오류/로그/Worker ID 검증.
5. F01/F03/F05와 10개 합성 시나리오의 실패·복구·PAPER 차단 시나리오를 실제 Chrome UI에서 조작.
6. 원본 소스·운영 DB·실계좌·실거래 불변 보존. 검증 로그/Chrome trace/PR 증빙 확보.

**완료 판정:** 공식 n8n 캔버스에서 실제 데이터 계약과 저장·실행·관측이 이어지고, 12개 엔진의 실데이터 실험은 별도 승인된 시험 환경에서 단계적으로 검증할 때만 완료 표시합니다.
