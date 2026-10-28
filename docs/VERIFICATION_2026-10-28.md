# Verification record · 2026-10-28 (Asia/Seoul)

## Source comparison

| Consumer | Source reference | Upstream n8n | Canvas source |
|---|---|---|---|
| Autonomous Investor | `feature/n8n-upstream-source-railway-20261027` | 2.44.5, `e993c789c83dba66030f3b0259b42e452b64c3b9` | `packages/frontend/editor-ui/src/features/workflows/canvas/components/Canvas.vue` |
| ProcureFlow | `main` | 2.44.6, `b58d9e89d60e9a3485bb511c5091d8be0d9511e4` | same |

The exact three pre-patch signatures occur once in both pinned upstream versions. The common patch changes only Pan and selection configuration and rejects unexpected upstream source.

## Public live browser baseline — BEFORE patch

- URL: https://investment-n8n-native-editor-production.up.railway.app/
- User-browser session: https://agent.tinyfish.ai/runs/4399e760-7b5d-4ac3-9fc4-1f6809cbe844
- The public page loaded, displayed 13 workflow options and showed 5 F01 nodes. Selecting a node worked.
- Blank-canvas left, middle and Space+left drags did not produce an observed viewport translation. Native node movement was not proved.
- No workflow execution, deletions, saving, trading or bid submissions were attempted.

This baseline suggests a Pan issue but does not establish that the default button mapping is its only cause.

## Isolated tests

- Local source-level: `npm test` — **4/4 passed**
- Local Chromium/Playwright on `tests/browser/pan_harness.html` — **8/8 passed** (Pan left/middle, Shift select, node move, connection, add, delete, zoom)
- Result JSON: `tests/browser/chrome-test-results.json`

**Limitation:** The Chromium fixture is not the compiled upstream n8n Vue component. A separate source-patched n8n instance and actual Chrome validation are still required.

## Preservation and next gates

- [x] Both original GitHub repositories inspected read-only
- [x] Shared repository and initial Pan implementation committed
- [x] Source and fixture regression test run
- [ ] Independently build official n8n with common patch
- [ ] Verify Pan and editing in a real browser on isolated deployed n8n
- [ ] Verify safe save/reload with synthetic workflow only
- [ ] Integrate validated commit into application adapters without touching production DB/credentials
