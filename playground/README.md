## 50-type catalog and implementation

The live playground displays **50 node-kind UI contracts** (14 official n8n node mappings, 7 existing-node compositions and 29 adapters/extensions awaiting actual project implementation). Use the category filter/search, choose a node, and edit its type-specific parameters. Business Operation supports Code/API/Python/Workflow/Mock settings and named success/error ports. Branches such as IF/Human Approval have named outputs. This visual editor **does not execute** Code/Python/API against business backends.

- [Full 50 node specifications](../docs/SHARED_NODE_50_SPEC_KO.md)
- [Investment adapter guide](../docs/INVESTMENT_NODE_ADAPTER_GUIDE_KO.md)
- [ProcureFlow adapter guide](../docs/PROCUREFLOW_NODE_ADAPTER_GUIDE_KO.md)


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
