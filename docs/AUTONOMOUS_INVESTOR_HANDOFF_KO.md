# AUTONOMOUS-INVESTOR — 공통 n8n 편집기 도입 실행 지시서

> 수신: `lyonbegin/autonomous-investor-backend` 프로젝트 작업 에이전트/개발자  
> 기준 브랜치: `feature/n8n-upstream-source-railway-20261027`  
> 공통 저장소: https://github.com/lyonbegin/shared-n8n-studio  
> 반드시 먼저 읽기: [공통 통합 지침](./CONSUMER_INTEGRATION_GUIDE_KO.md)

## 임무

공식 n8n Vue 캔버스에 공통 Pan 패치를 적용하고, **실제 Chrome 사용자가 빈 공간 드래그·노드 추가/삭제/이동/연결·확대·축소·설정·저장하는 행위**로 검증합니다. 계획서 작성만으로 마무리하지 말고, 기능 브랜치에서 실제 코드를 적용·빌드·테스트하고 근거를 PR에 첨부하십시오.

## 기존 구조 (소스 확인)

- 소스 빌드: `n8n/Dockerfile.upstream-source.railway`의 upstream `n8n@2.44.5`/`e993c789c83dba66030f3b0259b42e452b64c3b9`.
- 공식 Vue 편집기 테스트 포털: `n8n/preview/native-portal.html`, 경로 `/workflows/demo`. 3개 F01/F03/F05 및 10개 합성 JSON을 `openWorkflow` 메시지로 표시합니다.
- 별도 React Flow 구현: `investment_studio/src/InvestmentStudio.tsx`. 이것을 공식 공통 에디터로 대체하거나 주식 API·Python 엔진을 공유 저장소에 복사하지 않습니다.
- 기존 연구/투자 워크플로, TradingView, 운영관리 UI, Railway 배포를 그대로 보존합니다. 기존 공개 미리보기는 서버 DB 저장/실제 임의 노드 실행 기능이 없습니다.

## 구체적인 작업 지시

1. 기준 브랜치에서 `feature/shared-n8n-pan-integration` 기능 브랜치를 새로 만드십시오. 원본 브랜치에 직접 커밋하지 마십시오.
2. 기존 `n8n/Dockerfile.upstream-source.railway`를 참고해 테스트 전용 Dockerfile을 만들고, **공식 n8n 소스를 clone한 다음, `pnpm install` 전** 아래 명령을 추가하십시오. 원래 n8n 2.44.5 버전 및 commit 검증, native isolated-vm 빌드와 런타임 설정은 보존하십시오.

```dockerfile
ARG SHARED_N8N_STUDIO_COMMIT=999062f1676bdffafa852a36e6c986ef5ce7589f
RUN git clone https://github.com/lyonbegin/shared-n8n-studio.git /tmp/shared-n8n-studio \
    && git -C /tmp/shared-n8n-studio checkout --detach "$SHARED_N8N_STUDIO_COMMIT" \
    && test "$(git -C /tmp/shared-n8n-studio rev-parse HEAD)" = "$SHARED_N8N_STUDIO_COMMIT" \
    && node /tmp/shared-n8n-studio/scripts/apply-pan-patch.mjs \
      /src/packages/frontend/editor-ui/src/features/workflows/canvas/components/Canvas.vue
```

3. 소스 패치 로그와 `pnpm build:deploy` 통과를 기록하십시오. 예외가 나면 upstream `Canvas.vue` 소스와 공통 패치의 호환성을 먼저 조사하고 shared 저장소에 수정 PR을 제출하십시오. 소비자 프로젝트에 로컬 복제 패치를 만들지 마십시오.
4. **독립 실행 n8n 테스트 인스턴스**를 구동하십시오. 운영 투자 DB/Redis, 실제 브로커 계정, 운영 API 키를 연결하지 마십시오. 기존 공개 미리보기에서 Pan이 움직이는지만 확인하는 테스트와 **편집·영속 저장이 가능한 격리 인스턴스** 테스트를 구분하십시오.
5. Chrome에서 F01 합성 노드 로드, 빈 공간 왼쪽/가운데 Pan, Shift 선택, 노드 이동, 연결선 생성/삭제, 노드 추가/설정/삭제, Zoom/Fit을 직접 테스트하십시오. 각 동작의 viewport/노드 좌표를 비교하고 스크린샷/trace를 저장하십시오.
6. DB 저장 테스트는 n8n 테스트 계정의 별도 시험 워크플로에 한하여 **저장 → 새로고침 → 다시 열기**까지 검증하십시오. 이후 `dry_run` 또는 안전한 합성 webhook 실행과 작업 로그 상태를 대조하십시오. 실제 주문·거래 실행은 금지합니다.
7. 기존 React 운영 화면의 공식 n8n 링크·라우팅이 유지되는지 확인하고, 공통 편집기와 투자 어댑터/API 경계 및 잔존 이슈를 정리하십시오.

## 완료 조건

- 패치된 **공식** n8n Vue 화면에서 Pan·Zoom·노드 조작 모두 Chrome 사용자 테스트 통과
- 합성 워크플로의 저장/새로고침/재진입 결과 일치
- 시험 실행·상태·디버깅 자료는 실제 테스트 서버 로그와 일치
- 기존 프로젝트 원본 기능·Railway 프로덕션·실거래 주문 미변경
- PR 링크, 커밋, 빌드 로그, Chrome 증거, PASS/FAIL 및 실패 원인 보고

**완료로 보고할 수 없는 상태:** 소스/fixture 8/8 통과만 있는 경우, `/workflows/demo` 렌더링만 검증한 경우, 운영 인스턴스 재배포 전 승인 없이 진행한 경우.

현재 공통 프로젝트 검증: https://github.com/lyonbegin/shared-n8n-studio/actions
