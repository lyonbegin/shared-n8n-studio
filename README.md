## Shared 50-kind node library and implementation contracts

- **[50 node kind specification (Korean)](docs/SHARED_NODE_50_SPEC_KO.md)** — 9 existing + 15 execution/control + 25 advanced control/verification/recovery + 1 Business Operation = 50.
- [Stock investment adapter implementation guide](docs/INVESTMENT_NODE_ADAPTER_GUIDE_KO.md) — reuse actual `operation_id` catalog and 12 engine bridges.
- [ProcureFlow adapter implementation guide](docs/PROCUREFLOW_NODE_ADAPTER_GUIDE_KO.md) — connect manifest `N/H/Q/S/P/R/O` 43 business blocks, PF00~PF15.
- [Standalone 50-kind playground](https://shared-n8n-playground-production.up.railway.app/) — UI/port/parameter/sandbox simulation only.

The 50-type UI catalog is `playground/src/node-catalog.js`; there are **14 native mappings, 7 composition recipes, and 29 proposed extensions**. Native execution/DB/API is not implemented by this fixture. The official n8n engine and project-specific adapters must run independently in approved test environments.


# Shared n8n Studio · 공통 n8n 편집기

**Source-based official n8n Vue canvas** shared by:
- [Autonomous Investor](https://github.com/lyonbegin/autonomous-investor-backend) — `feature/n8n-upstream-source-railway-20261027`, n8n `2.44.5`
- [ProcureFlow](https://github.com/lyonbegin/procureflow) — `main`, n8n `2.44.6`

The common upstream target is n8n `2.44.6` pinned to source SHA `b58d9e89d60e9a3485bb511c5091d8be0d9511e4`. **No original application repository or production environment has been modified.** Trading and procurement APIs, workflow data, DBs, credentials, and runtimes remain separate application adapters.

## Independent front-end playground (live)

**[Open Shared n8n Studio Playground](https://shared-n8n-playground-production.up.railway.app/)**

- Standalone Vue 3 + Vue Flow interface under [`playground/`](playground/).
- Test blank-canvas left/middle Pan, Shift selection, zoom/Fit, node add/delete/drag, handle connections, settings, undo/redo, JSON import/export, and browser-local save/reload.
- Switch between **common**, **investment**, and **ProcureFlow** synthetic examples. Simulated run only updates visual node statuses.
- Separate Railway project: `SHARED-N8N-STUDIO-PLAYGROUND`. Does not access production Railway services, n8n server credentials or business APIs.
- Automated Playwright Chromium checks: [Playground UI workflow](https://github.com/lyonbegin/shared-n8n-studio/actions/workflows/playground-ui.yml).
- **Acceptance distinction**: this independently testable UI is a Vue Flow interaction playground; the canonical official n8n Vue editor integration and backend persistence are separately gated.

## Phase 1 · Blank-canvas Pan behavior

The two official upstream versions both use default `panningMouseButton=[1]` and `selectionKeyCode=true`; blank-area left mouse drag performs marquee selection rather than Pan. The fail-closed shared patch switches to:

- Blank pane **left or middle drag → Pan**
- **Shift + left drag → marquee selection**
- Node drag and connection-handle drag retain upstream interactions
- Existing Space/Ctrl Pan, zoom and normal UI behavior remain upstream

Only three exact statements in official `packages/frontend/editor-ui/src/features/workflows/canvas/components/Canvas.vue` are changed. There is **no replacement React Flow/Vue Flow editor** and no second execution engine.

## Reproduce locally

```bash
npm test
node scripts/apply-pan-patch.mjs tests/fixtures/Canvas.vue --check
python tests/browser/test_pan_chrome.py
docker build -f docker/Dockerfile.n8n-patched -t shared-n8n-studio:pan-v1 .
```

The Chrome script tests a standalone pointer-interaction regression fixture. It does **not** prove the real compiled n8n editor is fixed.

## Completion gates

1. [x] Compare original GitHub code
2. [x] Create shared GitHub repository and commit common Pan source patch
3. [x] Source-level 4/4 tests and isolated Chromium fixture 8/8
4. [ ] Build and deploy a *separate*, source-patched official n8n sandbox
5. [ ] Actual Chrome browser test of official n8n Pan, node move/add/delete, connect, zoom, save and reload
6. [ ] Link both existing projects to a validated shared release without changing production behavior

See [migration boundaries](docs/MIGRATION.md) and [verification record](docs/VERIFICATION_2026-10-28.md). Do not declare complete until actual patched upstream Chrome verification passes.
