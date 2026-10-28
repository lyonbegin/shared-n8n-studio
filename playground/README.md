# Independent Canvas Playground

Fully isolated front-end for exercising **Pan / Zoom / node add-delete-move / edge connect / settings / local save / import-export / undo-redo** in the shared editor project.

- Built with Vue 3 and Vue Flow. This is an **interaction playground**, not the compiled official n8n Vue editor.
- No API calls to investor/ProcureFlow, no worker, n8n back-end, database, credentials or trade/bid execution.
- Save loads browser localStorage only. Simulate button creates explicitly marked *synthetic* visual run states.
- Workflow samples: Generic, Investment, ProcureFlow — all fictional.
- Official n8n Pan source patch remains in `scripts/apply-pan-patch.mjs`; the playground validates behavior before separately integrating that patch upstream.

```sh
cd playground
npm install
npm run dev
# To build:
npm run build
# Tests:
npx playwright install chromium
npm test
```

Hosted independently using root `Dockerfile` and `node playground/server.mjs`. No production service is replaced.
