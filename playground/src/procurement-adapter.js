// ProcureFlow project manifest for the SAME shared-n8n-studio Vue Flow editor.
// Original PF00-PF15 / S01-S10 official n8n JSON is packaged by ProcureFlow.
// This adapter reuses the same stock canvas, with isolated approved Python mock-only node execution. No real G2B or bidding.
// No duplicated n8n runtime or alternate DAG executor.
export const PROCURE_WORKFLOWS=Object.freeze([
  ['operations/A01-public-win-strategy.json','A · 공공입찰 낙찰정보 → 수주전략 → 제안서'],
  ['operations/B01-private-software-proposal.json','B · 민간 SW 외주 기술·공수·견적 전략'],
  ['operations/C01-staffing-service-proposal.json','C · 인력·단순 용역 수급·원가·제안'],
  ['operations/PF00.json','PF00 · 전체 입찰 분석 오케스트레이터'],
  ['operations/PF01.json','PF01 · 공고 상시 수집'],
  ['operations/PF02.json','PF02 · 발주 등록·1차 심사'],
  ['operations/PF03.json','PF03 · 분석 작업 할당'],
  ['operations/PF04.json','PF04 · 공고·첨부자료 처리'],
  ['operations/PF05.json','PF05 · 10년 개찰·낙찰 분석'],
  ['operations/PF06.json','PF06 · 발주기관·경쟁업체 분석'],
  ['operations/PF07.json','PF07 · 입찰참가 자격 검증'],
  ['operations/PF08.json','PF08 · 공급업체·인력 조사'],
  ['operations/PF09.json','PF09 · 원가·가격전략'],
  ['operations/PF10.json','PF10 · 제안서·서류'],
  ['operations/PF11.json','PF11 · 근거·결과 독립 감사'],
  ['operations/PF12.json','PF12 · 입찰 참여 의사결정'],
  ['operations/PF13.json','PF13 · 정정·분석버전 갱신'],
  ['operations/PF14.json','PF14 · 전역 API·Worker 통제'],
  ['operations/PF15.json','PF15 · 장애 복구·상태 대조'],
  ['scenarios/S01.json','S01 · 정상 발주 (가상)'],
  ['scenarios/S02.json','S02 · 대상 외 공고 (가상)'],
  ['scenarios/S03.json','S03 · 세부종목 미확인 (가상)'],
  ['scenarios/S04.json','S04 · 정정공고 버전 관리 (가상)'],
  ['scenarios/S05.json','S05 · API 429·503 장애 (가상)'],
  ['scenarios/S06.json','S06 · 필수 자격 미충족 (가상)'],
  ['scenarios/S07.json','S07 · 견적 정족수 미달 (가상)'],
  ['scenarios/S08.json','S08 · Worker 장애 복구 (가상)'],
  ['scenarios/S09.json','S09 · 독립 감사 오류 (가상)'],
  ['scenarios/S10.json','S10 · 동시 발주 경합 (가상)']
]);
if(PROCURE_WORKFLOWS.length!==29 || new Set(PROCURE_WORKFLOWS.map(([path])=>path)).size!==26)
  throw Error('ProcureFlow studio workflow catalog must contain 29 unique n8n JSON files');
