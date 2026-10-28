# ProcureFlow — 공통 50종 노드와 43개 업무 블록 실제 구현·연결 지침

> 대상 저장소: [lyonbegin/procureflow](https://github.com/lyonbegin/procureflow) (\`main\` 원본 보존).  
> 최종 업무 정본: \`docs/FINAL_PROJECT_MASTER_PLAN_2026-10-28.md\`; 104개 기능: \`g2b_feature_registry.py\`; 43개 블록: \`n8n/operational_manifest.json\`.  
> 공통 노드 계약: [SHARED_NODE_50_SPEC_KO.md](./SHARED_NODE_50_SPEC_KO.md).

## 1. 노드 50종과 업무 블록 43개의 관계

**43개의 업무 블록은 43개의 독립 노드 클래스를 뜻하지 않습니다.** 각각을 공통 \`Business Operation\` 인스턴스로 배치하되 \`adapter=procureflow\`, \`operationId=N01/H05/Q05/...\`와 업무 입력·출력 계약을 붙입니다.

| 업무 블록 | 수량 | 실제 업무 영역 |
|---|---:|---|
| \`N01~N10\` | 10 | 공고 수집·원본·첨부·정정 |
| \`H01~H11\` | 11 | 정확한 10자리 세부종목·10년 실제 개찰/투찰·확정 낙찰 |
| \`Q01~Q05\` | 5 | 참가자격·증빙·제한 조건 |
| \`S01~S04\` | 4 | 공급업체·견적·인력 |
| \`P01~P07\` | 7 | 원가·가격 규칙·투찰 전략 |
| \`R01~R02\` | 2 | 제안서·제출 패키지 |
| \`O01~O04\` | 4 | 작업 소유·Worker·감사·사람 승인 전 판정 |
| **총계** | **43** | **104개 업무 기능을 독립 증빙 기준으로 평가** |

PF00은 상위 워크플로이며 PF01~PF15를 \`Execute Sub-workflow\`와 병렬·합류·조건·승인으로 묶습니다. \`PF15\`는 해당 manifest에서 \`owned_blocks: []\`인 장애 회복 **제어 플로우**이므로, 새로운 업무 블록을 임의로 추가하지 않습니다.

## 2. 업무 코드 계약 추출 예시 (실제 manifest 근거)

| \`operationId\` | manifest 입력 명세 | 출력 명세 |
|---|---|---|
| \`N01\` | \`query.window\` | \`tender_candidates[]\` |
| \`N09\` | \`attachment_manifest[]\` | \`artifact_refs[]\` |
| \`H01\` | \`N06.verified_detail10\` | \`validated_detail10\` |
| \`H05\` | \`verified_historical_notices[]\` | \`opening_records[] + bidder_records[]\` |
| \`H06\` | \`verified_historical_notices[]\` | \`award_records[]\` |
| \`H07\` | \`opening_records[] + award_records[] + search_windows[]\` | \`coverage_verdict\` |
| \`Q05\` | \`eligibility_gaps + joint_and_bond_terms\` | \`eligibility_verdict\` |
| \`S04\` | \`verified_quotes[] + specification\` | \`cost_quotes + quote_quorum\` |
| \`P06\` | \`total_cost + historical_price_stats + applicable_price_rules\` | \`price_scenarios[]\` |
| \`R02\` | \`draft_package + eligibility_verdict + conflicts\` | \`package_validation\` |
| \`O04\` | \`eligibility_verdict + package_validation + approved_price_or_block + audit_findings\` | \`READY/HOLD/NO_BID/REVIEW\` |

**주의:** manifest의 \`input/output\`은 현재 문자열 명세입니다. 실제 JSON Schema·포트별 타입·실행 함수·공식 증빙 판정은 조달청 프로젝트에서 구현/검증해야 합니다.

## 3. Business Operation 실제 입력 예시

\`\`\`json
{
  "kind": "business-operation",
  "data": {
    "parameters": {
      "adapter": "procureflow",
      "executionMode": "api",
      "operationId": "H05",
      "apiUrl": "/api/n8n/operational/flows/PF05/inspect",
      "method": "GET",
      "arguments": {
        "verified_historical_notices": []
      },
      "credentialRef": "procureflow_n8n_api_credential",
      "timeoutMs": 30000
    }
  }
}
\`\`\`

이 예시의 \`inspect\`는 현재 프로젝트에서 **실제 DB 증빙 상태를 읽는 경로**입니다. 호출 결과가 \`H05\`의 원본 수집 실행 결과라는 뜻이 아닙니다. 실제 수집이 필요한 경우 프로젝트가 **H05 작업 핸들러의 구체적인 작업 요청과 공식 증빙 출력 스키마**를 연결해야 합니다. \`verified_historical_notices: []\`는 샘플 입력이며 전수 수집 증빙이 아닙니다.

### 코드에서 참조할 원본

- \`n8n/operational_manifest.json\` → 블록 \`id,label,input,output,to,features\` 및 PF 플로우 소유관계.
- \`n8n/operational/PF01.json~PF15.json\` → 현재 read-only 기본 실행과 실제 Worker Job dispatch 조건.
- \`n8n/source-build/compile-native-topology.mjs\` → 공식 n8n의 \`executeWorkflow\`, \`executeWorkflowTrigger\`, \`merge\`, \`if\`로 PF00·내부 병렬 구조 컴파일하는 기존 코드.
- \`g2b_feature_registry.py\` → 104개 업무 기능의 개별 입력·출처·완료 판정.
- \`g2b_node_lab.py\` 및 \`reports/workflow_81_160_implementation_20261025.md\` → 기존 테스트 입력·디버깅·Mock/Replay 구현 현황. 이 코드를 새 DAG 실행 엔진으로 사용하지 않습니다.

## 4. 현존 API와 실제 사업 기능 연결

| API | 용도 | 데이터 상태 |
|---|---|---|
| \`GET /api/n8n/operational/flows/{PF}/inspect\` | 공식 원본·증빙 현황 조회 | 읽기 전용 |
| \`GET /api/n8n/operational/flows/{PF}/progress\` | 실행·Worker·충족률 표시 | 읽기 전용 |
| \`GET /api/n8n/operational/flows/{PF}/next-action\` | 다음 수집 가능 작업·차단 사유 | 실행하지 않음 |
| \`POST /api/n8n/operational/flows/{PF}/dispatch\` | 관리자 인증·멱등 키 기반 실제 Worker 등록 | 운영 영향 가능, 승인된 격리 테스트만 |
| \`GET /api/n8n/operational/flows/{PF}/jobs/{job_id}\` | Worker 실제 상태·증빙 판정 | 읽기 전용, 인증 필요 |
| \`GET /api/n8n/operational/flows\` | 15개 PF/43블록/104기능 현황 | 읽기 전용 |

\`Business Operation\`을 \`mode=api\`로 놓고 인증된 서버에서 위 API를 호출하되, **임의 호스트 입력 허용·브라우저 비밀 노출·운영 DB 직접 수정은 금지**합니다. 복잡한 실행 게이트는 각 프로젝트 서버에서 강제합니다. HTTP 200 및 Worker 상태 success만으로 공식 원본 검증 완료가 되는 것은 아닙니다.

## 5. PF00 실제 그래프 구성 방식

\`\`\`text
Human Input (발주 1건 선택)
  -> Permission Gate / Resource Lock
  -> PF00 Execute Sub-workflow
  -> PF01 신규 공고 -> PF04 공식 첨부 -> PF02 심사 -> PF03 건별 작업
  -> Parallel Fork:
       PF05 실제 10년 개찰·낙찰
       PF07 참가 자격
       PF08 공급업체·견적
  -> Join/Quorum (필수 의존성과 정족수 엄격 확인)
  -> PF06 경쟁업체 -> PF09 가격 전략 -> PF10 제안서
  -> Completeness Gate + Evidence/Audit (PF11)
  -> Human Approval / Permission Gate (PF12)
  -> READY_FOR_MANUAL_PARTICIPATION / HOLD / NO_BID / REVIEW
 [전역 제어] PF13 정정 / PF14 호출 제한 / PF15 오류·복구
\`\`\`

위는 **기획상 연결 구조**입니다. 기존 \`compile-native-topology.mjs\`가 생성하는 PF00·하위 노드의 실제 연결과 차이를 대조해 소스 패치 여부를 결정해야 하며, 운영 환경의 기존 워크플로를 무단으로 덮어쓰지 않습니다.

**H05/H06/H07은 각각 별도 Business Operation 인스턴스**로 연결하고, H07은 공식 원본 10년 전 기간창과 실제 참가·투찰·순위·확정 낙찰의 누락을 평가해야 합니다. \`Code\`로 임의의 \`verified: true\`를 생성하지 않습니다.

## 6. 각 프로젝트 구현·검증 필수 작업

1. 독립 feature 브랜치와 격리 n8n 2.44.6 테스트 인스턴스를 사용합니다. 기존 Railway/API/Worker/DB를 보존합니다.
2. 공통 50종 노드의 \`kind/fields/outputs\`를 팔레트 UI와 맞춘 뒤 기본 노드는 n8n native, 조합 노드는 n8n workflow template, 확장 노드는 프로젝트 어댑터로 매핑합니다.
3. **manifest 43개 블록의 구체적 핸들러·입출력·공식 증빙 스키마**를 등록하고 \`operationId\`로 연결합니다. 기능 번호 104개 전체를 단일 플래그로 완료 처리하지 않습니다.
4. 실제 PF00→PF 하위 워크플로에 노드별 경로·포트·상태·Worker Job ID와 실행 로그를 연결합니다.
5. \`S01~S10\`을 실제 Chrome에서 각각 실행해 결과/실패 위치/상태·정정/429·503/QUORUM/인증/자원 경합을 검증합니다. 합성 테스트와 실수집 공식 증빙을 구분합니다.
6. 자동 투찰·전자서명·입찰참가 버튼 클릭을 구현하거나 수행하지 않습니다. 최종 사람 판단 직전 단계에서 종료합니다.

**완료 조건:** 사용자가 편집 → n8n 서버 저장 → 실제 안전한 Workflow 실행 → 개별 노드 진행/오류/재시도 → 공식 원본·근거 확인 → 사람 최종 결정까지 브라우저에서 검증해야 합니다.
