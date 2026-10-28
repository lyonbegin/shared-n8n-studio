# Shared editor integration boundaries

## Upstream compatibility

| Consumer | Application source | Current native n8n | Shared target |
|---|---|---|---|
| Stock automation | `lyonbegin/autonomous-investor-backend` branch `feature/n8n-upstream-source-railway-20261027` | 2.44.5 | 2.44.6, after compatibility check |
| ProcureFlow | `lyonbegin/procureflow` branch `main` | 2.44.6 | 2.44.6 |

Both use the **official n8n upstream Vue canvas**. Stock's React Flow and ProcureFlow's Vue Flow preview are separate UI paths, not the canonical shared editor.

## Isolation guarantees

- Do not move investment Python services, procurement G2B APIs, workflow JSON, or worker into this repository.
- Do not connect to live PostgreSQL, Redis, n8n credentials, brokerage or bid submission systems from browser tests.
- Keep both original repositories and Railway production services unchanged until isolated verification passes.
- Use a pinned upstream source SHA and fail-closed patch application rather than duplicating n8n's UI source.
- n8n third-party source license and version compatibility require review when upgrading.

## Acceptance (in an isolated instance of compiled upstream n8n)

1. Visually load real Vue n8n nodes and select a workflow.
2. Empty pane left-drag and middle-drag pan the graph.
3. Shift+left pane drag selects nodes without moving viewport.
4. Node drag moves node; connecting handles creates edge without moving viewport.
5. Wheel zoom and fit to view still work.
6. Add, edit, delete and undo affect only test workflow.
7. Save, reload and execution status tracking use sandbox persistence only.
8. Actual Chrome user-interaction evidence is retained before acceptance.
