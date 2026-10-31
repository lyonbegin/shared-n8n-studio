# 공통 n8n Studio · 노드별 실행/입출력/코드 설정/버전 비교 모듈

## 노드 실행 버튼 UX (공통 v3)

- **노드 위 `▶ 실행`: 모달을 열지 않고 저장된 최신 INPUT으로 허용된 어댑터를 실행합니다. 캔버스가 보이는 상태로 노드가 실행 중/성공/실패 색상과 상태를 표시합니다.** 실행 기록은 서버 SQLite에 남습니다.
- **노드 위 `⚙ 설정·이력`: 사용자가 이 버튼을 명시적으로 눌렀을 때만 노드 작업 공간 모달을 엽니다.** 이때 저장된 실제 실행 OUTPUT과 수정 이력을 조회합니다.
- 모달의 `저장 후 ▶ 다시 실행`은 입력 편집 상황에서 명시적으로 실행 요청하는 별도 동작입니다. 새 모달을 열지 않습니다.
- 이 정책은 공통 UI 동작이며 ProcureFlow 등 실제 어댑터 미연결 노드의 ▶ 실행은 비활성화됩니다.
- 실제 Chromium 검증: https://github.com/lyonbegin/shared-n8n-studio/actions/runs/41229102100 (25/25 통과, Strategy/Library 모두 ▶ 클릭 후 모달 0개 확인).


## 단일 코드 소유자

공통 모듈 원본: `lyonbegin/shared-n8n-studio` 브랜치 `feature/wf01-canvas-20261029`

- `playground/src/SharedNodeWorkspace.vue`: 모든 호스팅 프로젝트에서 사용하는 입력 JSON·수정 이력·실행 설정·결과 비교 창.
- `playground/src/App.vue`: 노드 상단 도구모음(설정/실행), 현재 선택 노드 및 실행 상태 연동. 현재 주식 워크플로 목록은 `investment-adapter.js`가 제공합니다.
- `playground/src/style.css`: 노드 상단 도구모음 디자인·드래그 충돌 방지.
- `server/node_workspace_store.py`: 프로젝트 중립적인 SQLite 이력 테이블, 버전 충돌 방지, JSON/URL 초안 검증.
- `server/studio_server.py`: `/api/studio/nodes/workspace` 및 `/revisions` HTTP 컨트롤러.
- `server/node_run_store.py`: 모든 프로젝트에 공통인 노드 INPUT/OUTPUT 및 실제 연결선 전달 이력.
- `server/project_adapter_runtime.py`: 소비 프로젝트의 명시적 승인 실행 어댑터를 로드하는 제한된 인터페이스.
- **실제 주식 업무 Python 코드는 공통 저장소에 없습니다.** `autonomous-investor-backend/n8n/editor-adapter/investment_node_adapter.py`로 이전했습니다.

## HTTP 계약

GET `/api/studio/nodes/workspace?workflow=operations/F01.json&node_id=id`
GET `/api/studio/nodes/workspace/revisions?workflow=operations/F01.json&node_id=id`

PUT `/api/studio/nodes/workspace`:

```json
{
  "workflow": "operations/F01.json",
  "node_id": "node-01",
  "expected_revision": 0,
  "input_json": {"page": 1, "max_pages": 3},
  "execution_draft": {
    "kind": "http",
    "http_method": "GET",
    "api_url": "https://example.org/api",
    "notes": "URL 실험안 1"
  }
}
```

- 서버가 `node_workspaces` 현재 상태와 `node_workspace_revisions` 불변 버전을 같은 트랜잭션에 보존.
- 잘못된 버전이면 409와 `current_revision` 반환.
- 저장한 새 코드나 API URL은 **실행 권한을 얻지 못함**: `code_execution_approved:false`. 공개 편집기에 저장된 스크립트는 **어떤 경우에도 eval/exec, 임의 HTTP 실행의 근거가 될 수 없음**.
- 모든 API는 현재 브라우저 세션의 `studio_sid` 격리 범위에 저장. 계정 기반 공동 편집/프로덕션 권한 부여가 아님.
- 입력 JSON의 비밀번호, 토큰, 계정 시크릿 저장 금지.

## 실행 어댑터 경계

공통 편집기는 어떤 프로젝트의 임의 Python 코드를 실행할지 결정하면 안 됩니다.

프로젝트별 서버는 반드시 검증된 바인딩을 등록합니다:
- node_id, node_type, accepted input/output schemas
- immutable source SHA, approved code version and runtime identity
- explicit permissions for HTTP/python/write calls
- execution id, input revision, output artifact, success/error, duration
- abort support, replay protection, output sanitization

주식 자동화는 `STUDIO_PROJECT_ADAPTER=investment_node_adapter`를 지정하고, 프로젝트가 승인한 WF01 N01 `execute_node01`, N02 `execute_node02`를 사용합니다. N01→N02 연결선에는 N01의 전체 OUTPUT·실행 ID·동일 브라우저 세션이 보존되고, N02가 성공하면 N03 INPUT이 READY가 됩니다. N03은 아직 실행 어댑터가 없으므로 비활성입니다. DB 저장 초안으로 임의 코드를 실행할 수 없습니다.

## 동일 모듈을 다른 프로젝트에 적용하는 순서

1. 이 저장소의 검증된 커밋/릴리스를 프로젝트 Dockerfile 또는 package tag에 고정.
2. `SharedNodeWorkspace.vue`, `node_workspace_store.py`, `studio_server.py`를 동일 버전으로 배포.
3. 프로젝트의 노드 카탈로그·워크플로 목록·실제 Python/HTTP 실행 어댑터만 별도로 주입.
4. `GET/PUT/GET revisions` API를 대상 프로젝트의 테스트용 워크플로에서 검사.
5. 실제 실행은 서버에 허용된 어댑터에서만 수행. UI에 입력한 Python/URL 초안은 검토/CI/승인 과정을 거쳐 배포.
6. Playwright로 노드 위 버튼, 입력 수정, v1→v2·복원 v3, 재실행 후 OUTPUT diff, 장애 복구, 프로젝트 간 격리 확인.

## 현재 확인된 미완료

- 공식 n8n 2.x 전체 실행 엔진과 자동 연결된 것은 아님.
- 과거 N01 호환 REST 엔드포인트 이름과 주식 워크플로 선택 화면의 일부 코드는 여전히 존재합니다. 타 프로젝트 재사용 시 공식 엔진/어댑터 목록의 완전한 분리와 인증·권한 설계가 추가로 필요합니다.
- 임의 Python/HTTP 코드 핫스왑 실행이나 실제 TradingView 수집 기능은 없음.
- 실제 브라우저 E2E 결과와 Railway 배포 상태는 별도 검증 필요.

이 경계를 지키면 공통 노드 UI와 이력 저장을 재사용하면서도 각 프로젝트의 인증과 실행 엔진을 분리할 수 있습니다.

## 노드 간 실제 OUTPUT 전달 (공통 runtime v1)

- `node_runs`: `sid + workflow_path + run_id` 단위 실제 실행의 입력·출력·성공/실패·코드 SHA·input_revision 기록.
- `edge_transfers`: 원본 워크플로 `connections`에 존재하는 연결에만 `source_run_id`, 전체 `output_json`, 대상 노드/포트, `READY/CONSUMED` 기록.
- `GET /api/studio/nodes/transfers?workflow=...&node_id=...`: 다음 노드의 대기 입력 조회.
- `POST /api/studio/nodes/execute`: 프로젝트가 승인한 연결 노드만 실행. `X-Studio-Node-Run: APPROVED` 및 `source_run_id` 필수. 같은 sid, 같은 workflow, 원본 연결선 및 성공 실행 조건 검증.
- `GET /api/studio/nodes/graph-state?workflow=...`: 노드·선의 DB 상태 복원.
- `GET /api/studio/nodes/history?workflow=...&node_id=...`: 실제 노드 입력/출력 이력.
- *원본 N01 OUTPUT은 불변*: 다음 노드에서 수동 편집한 `input_json`은 새 input revision으로 별도 저장하며, 다음 노드 실행 때만 결합합니다.
- 노드 위 ▶ 실행은 모달 없이 단독 실행, 이전 결과·앞 노드 변수는 ⚙ 설정·이력에서 확인합니다.
- 공통 런타임은 Pine/주식/조달 업무를 몰라도 됩니다. 종목/종류/정렬·page_size 검증과 실제 Python 코드는 소비 프로젝트에 둡니다.

현재 구현은 **하나의 앞 노드→다음 노드(직렬 경로)의 입력·출력 전달**을 검증하기 위한 것입니다. 복수 입력 Merge, 병렬 실행 정책, 일반 n8n 실행기 연동, 실제 TradingView 수집은 별도 구현 범위입니다.
