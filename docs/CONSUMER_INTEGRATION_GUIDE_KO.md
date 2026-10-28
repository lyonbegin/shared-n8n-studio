# 공통 n8n 편집기 도입 지침서 — 두 프로젝트 공통

> 작성일: 2026-10-28 · 공식 공통 저장소: https://github.com/lyonbegin/shared-n8n-studio  
> 적용 대상: `lyonbegin/autonomous-investor-backend`, `lyonbegin/procureflow`  
> 이 문서는 **각 프로젝트에서 실행할 작업 지시서**입니다. 문서 작성이나 CI 통과 자체는 배포·구현 완료를 의미하지 않습니다.

## 0. 반드시 지킬 구현 원칙

1. **기존 두 프로젝트의 소스, 배포 서비스, 운영 DB, 자격 증명, 데이터 및 업무 엔진을 보존**한다. 운영 변경·운영 배포·데이터 삭제·실거래·자동 투찰을 수행하지 않는다.
2. 공통 편집기는 반드시 **n8n 공식 Vue 편집기**를 사용한다. React Flow/별도 Vue Flow 미리보기, 자체 DAG 실행 엔진을 공통 편집기라고 주장하지 않는다.
3. 공통 코드는 `lyonbegin/shared-n8n-studio`에서만 유지한다. 각 소비 프로젝트에는 공통 코드 전체를 복제하지 않고 **정확한 Git 커밋을 핀한 소스 패치 적용/어댑터**만 작성한다.
4. **Pan 기능을 첫 번째 통합 항목**으로 한다. 다른 기능을 완성했다고 보고하기 전에 실제 Chromium 기반 Chrome 사용자 조작 테스트를 수행한다.
5. 실행·저장·상태 추적은 공통 에디터와 독립된 각 업무용 n8n 서버/어댑터를 통한다. 투자 Python 엔진과 ProcureFlow G2B API/Worker를 공통 저장소로 이관하지 않는다.
6. 테스트는 완전히 격리된 n8n, 테스트 전용 DB·워크플로·자격 증명 없는 합성 데이터로 실행한다. 기존 운영 화면에는 패치가 검증되기 전 적용하지 않는다.

## 1. 소스 및 버전 기준 (확인 완료)

| 요소 | 주식 자동화 | ProcureFlow |
|---|---|---|
| 원본 GitHub | [autonomous-investor-backend](https://github.com/lyonbegin/autonomous-investor-backend) | [procureflow](https://github.com/lyonbegin/procureflow) |
| 기준 브랜치 | `feature/n8n-upstream-source-railway-20261027` | `main` |
| 기존 upstream n8n | `n8n@2.44.5` / `e993c789c83dba66030f3b0259b42e452b64c3b9` | `n8n@2.44.6` / `b58d9e89d60e9a3485bb511c5091d8be0d9511e4` |
| 소스 빌드 | `n8n/Dockerfile.upstream-source.railway` | `n8n/source-build/Dockerfile` |
| 공식 UI | n8n Vue의 `/workflows/demo` 테스트 화면 | 운영/격리 n8n 공식 Vue UI |
| 기존 대체 화면 | `investment_studio/src/InvestmentStudio.tsx` React Flow | `n8n/native-preview/src/main.js` Vue Flow 조회 화면 |
| 업무 API | 투자 Python/TradingView | G2B 수집/분석 API와 Worker |

**첫 차수에서는 버전 강제 통일 금지.** 주식은 2.44.5에 패치만 도입하고 ProcureFlow는 2.44.6에 적용한다. 공식 2.44.6 업그레이드는 별도 호환성/롤백 검증 이후 진행한다.

## 2. 공통 코드 사용 방법 (복사 금지·핀 고정)

- 공통 구현 경로: [Pan patch](../scripts/apply-pan-patch.mjs), [Pan contract](../packages/pan/pan-contract.mjs)
- 검증 기준 커밋(고정): `999062f1676bdffafa852a36e6c986ef5ce7589f`
- 이 커밋에는 공통 패치, 테스트 및 최초 CI 정의가 포함되어 있다. 이후 업데이트가 생겨도 **main 최신본을 무조건 가져오지 않는다.**
- 공식 n8n 캔버스 경로(두 버전 동일): `packages/frontend/editor-ui/src/features/workflows/canvas/components/Canvas.vue`

**공식 n8n 소스를 Clone한 직후, `pnpm install` / `pnpm build:deploy`보다 먼저** 아래 단계를 추가한다.

```dockerfile
# 기존 공식 n8n 소스 git clone + HEAD SHA 확인이 끝난 직후 실행
ARG SHARED_N8N_STUDIO_COMMIT=999062f1676bdffafa852a36e6c986ef5ce7589f
RUN git clone https://github.com/lyonbegin/shared-n8n-studio.git /tmp/shared-n8n-studio \
    && git -C /tmp/shared-n8n-studio checkout --detach "$SHARED_N8N_STUDIO_COMMIT" \
    && test "$(git -C /tmp/shared-n8n-studio rev-parse HEAD)" = "$SHARED_N8N_STUDIO_COMMIT"
# 소비자별 아래 경로만 달라진다 (각 전용 지침서 참조)
```

- 투자 프로젝트: `RUN node /tmp/shared-n8n-studio/scripts/apply-pan-patch.mjs /src/packages/frontend/editor-ui/src/features/workflows/canvas/components/Canvas.vue`
- ProcureFlow: `RUN node /tmp/shared-n8n-studio/scripts/apply-pan-patch.mjs /src/n8n/packages/frontend/editor-ui/src/features/workflows/canvas/components/Canvas.vue`
- 이후 기존 공식 `pnpm` 빌드 및 기존 런타임 구성을 그대로 유지한다.
- **패치 실패 시 이미지 빌드를 중단한다.** 예상치 못한 upstream 소스 변경을 임의 텍스트 치환으로 무시하지 않는다.
- 원본 Dockerfile을 덮어쓰기 전 해당 프로젝트의 기능 브랜치를 새로 만들고, 가능하면 해당 브랜치에만 Dockerfile 별도 복사본을 만든다.

### 왜 이 방식인가?

공통 패치가 `shared-n8n-studio`에만 존재하고 소비자는 정해진 소스 커밋을 빌드 시 참조합니다. 각 서비스는 자신의 n8n 데이터베이스·API·Worker·인증을 그대로 사용하므로 공통 UI 유지보수와 업무 분리가 동시에 가능합니다.

## 3. Pan 사용자 동작 계약 (테스트 기준)

| 사용자 행동 | 기대 결과 |
|---|---|
| 빈 캔버스 왼쪽 버튼 드래그 | 카메라/Viewport 이동, 노드의 워크플로 좌표 불변 |
| 빈 캔버스 가운데 버튼 드래그 | 카메라/Viewport 이동 |
| Shift + 왼쪽 드래그 | 노드 범위 선택, Viewport 이동하지 않음 |
| 노드 본문 왼쪽 드래그 | **노드 좌표만** 이동 |
| 연결 핸들 드래그 | 엣지 연결, Viewport 이동하지 않음 |
| 마우스 휠/컨트롤 버튼 | 확대·축소 및 Fit 정상 |
| 노드 추가·삭제·설정 변경 | 테스트 워크플로에서 정상 |
| 저장 → 새로고침 → 재진입 | 테스트 n8n 서버에 변경이 영속 저장됨 |
| 시험 실행 → 결과/로그 | 테스트 전용 실행 기록이 실제 서버 로그와 일치 |

테스트 코드가 있는 `tests/browser/pan_harness.html`은 **독립 제스처 계약용 fixture**입니다. 해당 Chromium 테스트의 합격만으로 **수정된 공식 n8n의 통합 검증 완료**라고 보고하지 않습니다. 실제 n8n UI DOM에서 viewport transform 및 노드 위치 변화를 드래그 전후 수치로 확인해야 합니다.

## 4. 권장 실행 단계

1. 기능 브랜치 생성: `feature/shared-n8n-pan-integration` (원본 기준 브랜치는 유지).
2. 위 커밋을 고정해 소스 빌드 과정에 패치 적용. 업스트림 버전/커밋 SHA는 유지.
3. 해당 기능 브랜치에서 CI 소스 패치 검사와 Docker 빌드. 빌드 로그에 `PAN_PATCH_PATCHED` 표시 확인.
4. **별도** 테스트용 n8n 인스턴스 시작. 실 운영 DB/Redis/암호화키·실거래 인증·G2B 인증 연결 금지.
5. 합성 워크플로를 새로 만들어 실제 Chrome 사용자 조작: 빈 공간 Pan, Shift 선택, 노드 이동, 핸들 연결, 추가/삭제/되돌리기, 줌, 저장/재접속.
6. Chrome 스크린샷·동영상/trace, CI 링크, 테스트 데이터, 서버 저장 결과, 실행 로그, 실패 항목을 PR에 첨부.
7. Pan/편집 UX가 통과하면 이후 단계로 서버 저장·실제 테스트 실행·상태 추적·디버깅을 해당 사업 어댑터에 맞게 확장.
8. 운영 배포는 본 문서의 범위 밖. 사용자 승인과 별도 롤백 계획이 확보된 후에만 진행.

## 5. 공통/개별 소유권 분리

| 공유 저장소에서 관리 | 투자 프로젝트에서 관리 | 조달청 프로젝트에서 관리 |
|---|---|---|
| 공식 Vue UI 소스 적용 패치 | TradingView/Python 12엔진, 투자 API | G2B API, 증빙 검증, Worker |
| Pan·Zoom·노드 조작 공통 UX 계약 | 투자 워크플로 JSON·버전 저장 | PF01~PF15, S01~S10 JSON |
| 브라우저 회귀 테스트·소스 버전 핀 | 투자 실행 상태/로그 어댑터 | 조달 실행 상태/로그 어댑터 |
| 공통 편집기 배포 패키지 정책 | 거래 차단·연구 실행 정책 | 투찰 차단·수집 제한 정책 |

## 6. 각 프로젝트 작업의 최종 제출물

- 수정한 **기능 브랜치와 PR URL** (원본 기본 브랜치/운영 미수정)
- 공통 저장소의 핀 커밋 및 실제 패치 적용 로그
- n8n 소스 빌드의 성공/실패 원본 로그
- **실제 Chrome 조작** 테스트 보고서 (좌표/viewport의 before-after 증거 포함)
- 노드 추가/삭제/연결/이동, Zoom, 저장/재열기, 시험 실행/상태 확인 PASS/FAIL 표
- 기존 프로젝트의 독립 어댑터·보존 범위 비교와 잔여 장애 목록
- 운영 배포/실거래/입찰행위가 없었다는 변경 범위 보고

## 7. 프로젝트별 지시서

- [주식 자동화용 지시서](./AUTONOMOUS_INVESTOR_HANDOFF_KO.md)
- [조달청 ProcureFlow용 지시서](./PROCUREFLOW_HANDOFF_KO.md)

**중요:** 현재 통과한 공통 CI는 소스 패치 및 fixture Chrome 검증입니다. 공식 n8n 패치 버전의 독립 배포·실사용 Chrome 검증은 **미완료** 상태입니다. 각 담당 프로젝트가 이를 직접 확인하고 증빙해야 합니다.
