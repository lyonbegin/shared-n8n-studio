# 공통 n8n Studio — 50종 노드 카탈로그 및 실제 코딩 계약

> 기준: 주식 자동화 최종 통합 기획(2026-10-28), ProcureFlow 최종 기획(2026-10-28).  
> 공통 저장소: `lyonbegin/shared-n8n-studio` · 계약 파일: [`playground/src/node-catalog.js`](../playground/src/node-catalog.js)  
> **중요:** 이 파일은 **50개 노드의 화면 편집·설정·포트 계약과 구현 책임을 정의한 기술 명세**입니다. 현재 독립 Playground에 50종 UI가 추가되었습니다. 50종의 실제 실행 엔진이 통합·검증되었다는 뜻이 아닙니다.

## 1. 왜 이런 노드가 필요한가

두 프로젝트의 업무 함수는 `Business Operation` 노드 하나에 `adapter`와 `operationId`를 지정해 실행합니다. 나머지 노드는 순서·분기·병렬·합류·승인·오류·증빙·중단·디버깅 등 **작업의 제어 의미**를 표현합니다. 이 제어 기능을 전부 Code/HTTP Request 한 개로 감싸면 사용자가 실행 그래프와 중단 지점을 확인하기 어려워집니다.

- 주식: TradingView/Pine → 12개 Python 엔진 및 AlphaForge 137개 기존 연산 + 제어 3개 → 에이전트 배정 → Nautilus PAPER 위험 게이트 → 독립 감사.
- 조달: PF00 → PF01~PF15, 104개 업무 기능을 43개 블록(`N01~N10`, `H01~H11`, `Q01~Q05`, `S01~S04`, `P01~P07`, `R01~R02`, `O01~O04`)으로 연결.
- 자체 DAG 엔진을 별도로 만들지 않고 **공식 n8n 원본 편집기·실행 엔진**에 통합하는 것이 최종 목표입니다.

## 2. 50종 전체 표

`implementation`은 다음 중 하나입니다.

- `native` (14종): 공식 n8n 노드가 존재하며 해당 n8n 버전에서 사용 가능한 타입/파라미터를 확인한 후 그대로 사용합니다.
- `composite` (7종): 기존 n8n 노드들의 템플릿/설정 묶음으로 실현하는 **UX 논리 유형**입니다. 독립된 실행 타입이라고 가정하지 않습니다.
- `extension` (29종): 공통 인터페이스와 각 프로젝트의 실행/저장 계약을 정의하고, 기존 n8n 기능으로 충분하지 않을 경우 커스텀 노드 또는 어댑터를 구현해야 합니다.

| # | 안정적인 노드 kind | UI 명칭 | 분류 | 구현 방식 | n8n 기본 타입 예시 |
|---:|---|---|---|---|---|
| 1 | `trigger` | Manual Trigger | 트리거 | native | `n8n-nodes-base.manualTrigger` |
| 2 | `schedule` | Schedule | 트리거 | native | `n8n-nodes-base.scheduleTrigger` |
| 3 | `webhook` | Webhook | 트리거 | native | `n8n-nodes-base.webhook` |
| 4 | `http` | HTTP Request | 처리 | native | `n8n-nodes-base.httpRequest` |
| 5 | `code` | Code | 처리 | native | `n8n-nodes-base.code` |
| 6 | `set` | Edit Fields | 처리 | native | `n8n-nodes-base.set` |
| 7 | `if` | IF | 논리 | native | `n8n-nodes-base.if` |
| 8 | `merge` | Merge | 논리 | native | `n8n-nodes-base.merge` |
| 9 | `wait` | Wait | 논리 | native | `n8n-nodes-base.wait` |
| 10 | `execute-workflow` | Execute Sub-workflow | 워크플로 제어 | native | `n8n-nodes-base.executeWorkflow` |
| 11 | `subworkflow-trigger` | Sub-workflow Trigger | 워크플로 제어 | native | `n8n-nodes-base.executeWorkflowTrigger` |
| 12 | `switch` | Switch | 논리 | native | `n8n-nodes-base.switch` |
| 13 | `loop` | Loop / Batch | 워크플로 제어 | native | `n8n-nodes-base.splitInBatches` |
| 14 | `retry` | Retry / Timeout | 오류·복구 | composite | 별도 실행 계약 |
| 15 | `error-halt` | Error Handler / HALT | 오류·복구 | composite | `n8n-nodes-base.stopAndError` |
| 16 | `join-quorum` | Join / Quorum | 논리 | extension | 별도 실행 계약 |
| 17 | `approval` | Human Approval | 워크플로 제어 | extension | 별도 실행 계약 |
| 18 | `database` | Database | 연결·저장 | native | `n8n-nodes-base.postgres` |
| 19 | `file-document` | File / Document | 연결·저장 | composite | 별도 실행 계약 |
| 20 | `schema-validator` | Schema Validator | 데이터·검증 | extension | 별도 실행 계약 |
| 21 | `evidence-audit` | Evidence / Audit | 데이터·검증 | extension | 별도 실행 계약 |
| 22 | `worker-queue` | Worker / Queue | 실행·자원 | extension | 별도 실행 계약 |
| 23 | `resource-lock` | Resource / Lock | 실행·자원 | extension | 별도 실행 계약 |
| 24 | `test-mock-assert` | Test / Mock / Assert | 테스트·디버깅 | extension | 별도 실행 계약 |
| 25 | `parallel-fork` | Parallel Fork | 워크플로 제어 | composite | 별도 실행 계약 |
| 26 | `event-publish` | Event Publish | 이벤트·상태 | extension | 별도 실행 계약 |
| 27 | `event-subscribe` | Event Subscribe / Wait | 이벤트·상태 | extension | 별도 실행 계약 |
| 28 | `state-machine` | State Machine | 이벤트·상태 | extension | 별도 실행 계약 |
| 29 | `compensation` | Compensation / Rollback | 오류·복구 | extension | 별도 실행 계약 |
| 30 | `checkpoint` | Checkpoint / Resume | 오류·복구 | extension | 별도 실행 계약 |
| 31 | `idempotency` | Idempotency | 실행·자원 | extension | 별도 실행 계약 |
| 32 | `deduplication` | Deduplication | 데이터·검증 | extension | 별도 실행 계약 |
| 33 | `rate-limit` | Rate Limit | 실행·자원 | extension | 별도 실행 계약 |
| 34 | `circuit-breaker` | Circuit Breaker | 오류·복구 | extension | 별도 실행 계약 |
| 35 | `dead-letter-queue` | Dead Letter Queue | 오류·복구 | extension | 별도 실행 계약 |
| 36 | `lease-fencing` | Lease / Fencing | 실행·자원 | extension | 별도 실행 계약 |
| 37 | `data-mapper` | Data Mapper | 데이터·검증 | composite | 별도 실행 계약 |
| 38 | `split-aggregate` | Split / Aggregate | 데이터·검증 | composite | 별도 실행 계약 |
| 39 | `json-diff` | JSON Diff / Compare | 데이터·검증 | extension | 별도 실행 계약 |
| 40 | `completeness` | Completeness Gate | 데이터·검증 | extension | 별도 실행 계약 |
| 41 | `hash-integrity` | Hash / Integrity | 데이터·검증 | extension | 별도 실행 계약 |
| 42 | `source-provenance` | Source Provenance | 데이터·검증 | extension | 별도 실행 계약 |
| 43 | `human-form` | Human Input / Form | 워크플로 제어 | extension | 별도 실행 계약 |
| 44 | `permission-gate` | Permission Gate | 워크플로 제어 | extension | 별도 실행 계약 |
| 45 | `notification-alert` | Notification / Alert | 이벤트·상태 | composite | 별도 실행 계약 |
| 46 | `metrics-counter` | Metrics / Counter | 테스트·디버깅 | extension | 별도 실행 계약 |
| 47 | `execution-probe` | Execution Probe | 테스트·디버깅 | extension | 별도 실행 계약 |
| 48 | `replay` | Replay | 테스트·디버깅 | extension | 별도 실행 계약 |
| 49 | `fault-injection` | Fault Injection | 테스트·디버깅 | extension | 별도 실행 계약 |
| 50 | `business-operation` | Business Operation | 업무 실행 | extension | 별도 실행 계약 |

**주의:** 위 `nativeType`은 후보 매핑입니다. 공식 n8n 버전의 타입 이름·설정·포트 지원 여부를 프로젝트별 실제 빌드에서 검증해야 합니다. UI 논리 유형을 그대로 n8n의 노드 타입 문자열로 저장하면 실행되지 않습니다.

## 3. 공통 데이터 계약

### 3.1 팔레트/편집기 모델 (UI)

```json
{
  "kind": "business-operation",
  "name": "Business Operation",
  "group": "업무 실행",
  "implementation": "extension",
  "inputs": ["main"],
  "outputs": ["success", "error"],
  "fields": [
    {"key":"adapter", "type":"select"},
    {"key":"executionMode", "type":"select"},
    {"key":"operationId", "type":"text"},
    {"key":"arguments", "type":"json"}
  ]
}
```

각 노드 인스턴스의 `id`와 유형 `kind`는 다릅니다. 인스턴스는 동일한 kind를 수십 개 배치할 수 있습니다. `operationId`는 프로젝트의 검증된 함수/업무 블록 ID를 사용하며 임의의 URL·코드가 함수를 자동으로 실행할 수 있게 만드는 규칙이 아닙니다.

### 3.2 표준 실행 입출력

프로젝트 어댑터는 최소한 다음 구조로 결과를 노출하도록 권장합니다. **아래는 제안된 공통 계약이며 기존 두 프로젝트 API가 이미 이 형식이라는 주장은 아닙니다.**

```json
{
  "schema_version": "shared-operation.v1",
  "run_id": "runtime-generated-id",
  "node_id": "business-node-3",
  "adapter": "investment",
  "operation_id": "qlib.app.bridge.predict",
  "status": "success",
  "input": {"symbol": "TEST"},
  "output": {"result": "example-only"},
  "error": null,
  "evidence": {"source": "mock", "verified": false},
  "duration_ms": 12,
  "worker_job_id": null
}
```

상태는 시스템 공통 집합 `queued/running/success/failed/skipped/waiting_approval/halted`에서 실제 n8n 실행 이벤트를 기초로 변환합니다. 공식 n8n 내부 실행 데이터 구조와 동일한 객체라고 가정하지 않고, **표시 어댑터에서 매핑**합니다.

### 3.3 연결선은 실행 의미를 갖는다

```json
{
  "source": "riskCheck",
  "sourceHandle": "approved",
  "target": "paperExecutor",
  "targetHandle": "main",
  "mapping": {"risk_result": "$json.result"},
  "on_status": "success",
  "optional": false
}
```

`approved/rejected/timeout`, `true/false`, `complete/incomplete`, `joined/insufficient` 등의 이름 붙은 포트를 플레이그라운드에서 선택·연결할 수 있습니다. **실제 n8n 출력 인덱스/파라미터로 변환하는 단계는 각 타입 어댑터 개발 대상**입니다. 플레이그라운드의 JSON은 **n8n 워크플로 실행 파일과 동일하지 않습니다.**

## 4. Business Operation 5개 실행 방식

| executionMode | UI 설정 | 공식 n8n으로 구현하는 방식 | 프로젝트가 해야 할 일 |
|---|---|---|---|
| `javascript` | `javascriptCode`, `arguments` | 공식 **Code** 노드의 서버측 JavaScript 실행 | 코드 검증, 입력/출력 스키마, 권한 제한 |
| `api` | `apiUrl`, `method`, `credentialRef` | 공식 **HTTP Request** 노드 | 허용 도메인/경로·자격증명·재시도·상태 코드 계약 |
| `python` | `operationId`, `pythonFunction`, `arguments` | 공식 HTTP Request → **프로젝트 Python API/Worker** | 함수 allowlist, Python 환경, 큐·결과·오류 |
| `workflow` | `workflowId`, `arguments` | 공식 **Execute Sub-workflow** | ID 매핑·인자 스키마·실행 기록 링크 |
| `mock` | `mockResult`, `arguments` | 격리 테스트 n8n Code / 시험 핸들러 | 모의 결과에 `mock/test_only` 출처 필수 |

**브라우저에서 JavaScript/Python을 실행하지 않습니다.** 서버 자격증명을 클라이언트·GitHub·워크플로 JSON에 저장하지 않습니다. `code`와 `javascript`는 승인된 n8n Code 실행 환경에서만 돌아가며 Python은 프로젝트 백엔드 실행 경로를 통합니다. 웹에서 외부 API를 무단 호출하거나 사용자 작성 코드를 서버에서 임의 `eval`하지 않습니다.

## 5. 제어 노드의 구현 규칙

| 유형 | 코딩 시 핵심 조건 |
|---|---|
| Execute Sub-workflow/Trigger | 상위→하위 inputSchema, 호출자 실행 ID, 완료/오류 전달 |
| Parallel Fork / Join | 실제 n8n 분기 실행과 합류 조건. `QUORUM`을 단순 Merge append로 오인하지 않음 |
| Retry / Timeout | 비멱등 호출의 자동 재시도 금지. 실제 HTTP timeout와 node-level retry 경계 구분 |
| Error / HALT | 정책상 중단을 오류와 구별하고 후속 노드 차단 |
| Human Approval / Permission Gate | 검증된 사용자·역할·명시적 기록, 서버측 재개 |
| Worker / Queue / Resource Lock / Lease | Worker Job ID, 멱등 키, 분산 DB 잠금·Fencing 토큰 확인 |
| State Machine / Compensation / Checkpoint | 서버측 불변 전이, 보상 로그, 재실행 시 중복 부작용 차단 |
| Schema / Completeness / Evidence / Integrity | 원본 출처·시간·해시 검증, 누락이면 성공 표시 금지 |
| Test / Replay / Fault Injection | 테스트 분리, 모의 응답의 실제 공식 원본 승격 금지 |

## 6. 실행 가능 수준별 합격 기준

1. **UI 계약 검사:** 카탈로그 정확히 50종, 중복 kind 없음, 검색·필터·노드 추가·이동·삭제, 분기별 포트, 설정 검증, JSON 저장/복원.
2. **n8n 소스 통합 검사:** 개별 UI 논리 유형이 실제 n8n 기본 노드나 설치된 확장 패키지에 정확히 대응하는지 확인. 플러그인이 없다면 읽기 전용 또는 비활성 상태로 표시.
3. **API/Worker 검사:** 비운영 테스트용 DB/API를 통해 입력→실제 실행 ID→노드 상태→출력/오류/로그 연결. 사용자 승인 이전의 실거래·입찰 제출 금지.
4. **실제 Chrome 테스트:** 노드 선택·배치·이동·분기 연결·설정·서버 저장·새로고침·재오픈·실행·다음 노드 제어·노드별 로그 확인.
5. **운영 증거 구분:** 로컬 UI / CI / 격리 n8n / 실제 업무 API / 운영 공식 증빙을 별도로 기록.

### 자료

- [투자 프로젝트 구현 안내](./INVESTMENT_NODE_ADAPTER_GUIDE_KO.md)
- [조달 프로젝트 구현 안내](./PROCUREFLOW_NODE_ADAPTER_GUIDE_KO.md)
- [두 프로젝트 공통 편집기 도입 안내](./CONSUMER_INTEGRATION_GUIDE_KO.md)
- [공식 n8n 노드 제작 문서](https://docs.n8n.io/integrations/creating-nodes/)
- [공식 n8n Node Code/Item linking 안내](https://docs.n8n.io/data/data-mapping/data-item-linking/item-linking-node-building/)
