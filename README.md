# Shared n8n Studio · 공통 n8n 편집기

**Source-based official n8n Vue canvas** shared by:
- [Autonomous Investor](https://github.com/lyonbegin/autonomous-investor-backend) — `feature/n8n-upstream-source-railway-20261027`, n8n `2.44.5`
- [ProcureFlow](https://github.com/lyonbegin/procureflow) — `main`, n8n `2.44.6`

The common upstream target is n8n `2.44.6` pinned to source SHA `b58d9e89d60e9a3485bb511c5091d8be0d9511e4`. **No original application repository or production environment has been modified.** Trading and procurement APIs, workflow data, DBs, credentials, and runtimes remain separate application adapters.

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
