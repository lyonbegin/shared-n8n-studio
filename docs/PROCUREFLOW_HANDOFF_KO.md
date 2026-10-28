# ProcureFlow — 공통 n8n 편집기 도입 실행 지시서

> 수신: `lyonbegin/procureflow` 프로젝트 작업 에이전트/개발자  
> 기준 브랜치: `main`  
> 공통 저장소: https://github.com/lyonbegin/shared-n8n-studio  
> 반드시 먼저 읽기: [공통 통합 지침](./CONSUMER_INTEGRATION_GUIDE_KO.md)

## 임무

공식 n8n 2.44.6 Vue 캔버스에 공통 Pan 패치를 적용하고, 사용자가 실제 Chrome에서 드래그·확대·축소·노드 연결/이동/설정·저장하는 과정을 검증하십시오. 검증은 운영 n8n과 분리된 인스턴스에서만 수행합니다.

## 기존 구조 (소스 확인)

- 공식 소스 빌드: `n8n/source-build/Dockerfile` / `n8n@2.44.6` /`b58d9e89d60e9a3485bb511c5091d8be0d9511e4`.
- 빌더 작업 경로: `/src/n8n`. 빌드 산출물을 복사해 isolated-vm native module을 재빌드하고 런타임을 구성합니다.
- 운영 PF 워크플로 `n8n/operational/PF01.json`~`PF15.json`, 합성 S01~S10 JSON 및 `n8n/operational_manifest.json`은 보존합니다.
- `n8n/native-preview/src/main.js`는 Vue Flow로 실제 JSON을 표시하는 **조회 전용 시각화**입니다. 이 화면만 고쳐서 공식 n8n 편집기 수정 완료라고 보고하면 안 됩니다.
- `n8n/source-build/bootstrap-workflows.sh`, `compile-native-topology.mjs`, DB/Worker 구성, ProcureFlow API/G2B 증빙 검증은 변경하지 않습니다.

## 구체적인 작업 지시

1. `main` 기준으로 `feature/shared-n8n-pan-integration` 새 브랜치를 만드십시오. 별도 테스트 Dockerfile을 작성하여 운영용 Dockerfile과 실제 배포 구성을 보존합니다.
2. 기존 `n8n/source-build/Dockerfile`의 공식 n8n Git clone 및 고정 SHA 확인 뒤, `pnpm install` 전에 다음 패치를 추가하십시오.

```dockerfile
ARG SHARED_N8N_STUDIO_COMMIT=999062f1676bdffafa852a36e6c986ef5ce7589f
RUN git clone https://github.com/lyonbegin/shared-n8n-studio.git /tmp/shared-n8n-studio \
    && git -C /tmp/shared-n8n-studio checkout --detach "$SHARED_N8N_STUDIO_COMMIT" \
    && test "$(git -C /tmp/shared-n8n-studio rev-parse HEAD)" = "$SHARED_N8N_STUDIO_COMMIT" \
    && node /tmp/shared-n8n-studio/scripts/apply-pan-patch.mjs \
      /src/n8n/packages/frontend/editor-ui/src/features/workflows/canvas/components/Canvas.vue
```

3. 기존 `pnpm run build:deploy` 및 isolated-vm 빌드 절차를 유지하며, `PAN_PATCH_PATCHED`와 컴파일된 n8n 2.44.6 버전의 로그를 보관하십시오.
4. 운영 n8n과 분리된 별도의 테스트 DB 및 n8n 실행 인스턴스에서 공식 UI 접근·편집이 되는지 확인하십시오. 기존 운영 15 PF/10 S 워크플로와 실계정/토큰/암호화키/Redis/Worker를 테스트 인스턴스로 복사·연결하지 마십시오.
5. **합성된** n8n 노드 그래프를 통해 실제 Chrome 사용자 조작 테스트: 왼쪽·가운데 Pan, Shift 범위 선택, 노드 이동, 핸들 연결, 노드 추가·삭제·설정, Zoom/Fit을 수행하십시오.
6. 테스트 DB에 워크플로 저장→재접속→위치/연결/설정 보존을 확인하고, **수동 트리거·Code 등 외부 API를 호출하지 않는 테스트 노드만** 실행하십시오. n8n 서버의 실행 상태·노드별 로그와 UI 결과를 비교하십시오.
7. ProcureFlow의 운영/데모 워크플로 JSON 및 G2B Worker 코드 변경 여부를 점검하십시오. 운영 PF의 기본 `active:false`, PF05 증빙 검증, 자동 투찰 차단 등의 기존 정책을 그대로 보존하십시오.

## 완료 조건

- 수정된 공식 n8n Vue 에디터의 Chrome 실사용 Pan·편집 동작 증빙
- 합성 노드 설정/이동/연결의 서버 저장 및 재열기 검증
- 합성 워크플로 시험 실행 상태/로그와 화면 일치
- 운영 G2B API/Worker/15 PF/10 S, 실제 DB 및 기존 배포 미변경
- 기능 브랜치 PR, 커밋, Docker 빌드·실행 로그, Chrome 스크린샷/trace, PASS/FAIL 테이블 포함

**완료로 보고할 수 없는 상태:** `native-preview` 조회 화면만 정상인 경우, 공통 fixture Chromium 8/8만 통과한 경우, 공식 에디터가 아닌 자체 그래프에만 Pan을 구현한 경우.

현재 공통 프로젝트 검증: https://github.com/lyonbegin/shared-n8n-studio/actions
