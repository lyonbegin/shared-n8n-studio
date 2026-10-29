import {test,expect} from '@playwright/test';

const ROOT='https://investment-n8n-native-editor-production.up.railway.app';
const FLOW='operations/WF01-pine-source-intake.json';
const API='/api/studio/workflows/'+FLOW;

// This suite uses a fresh anonymous browser cookie per test, so the SQLite
// revisions belong to an isolated test session, not an operator's saved draft.
test('WF-01 step 1: real VueFlow canvas loads 13 nodes and 12 edges', async ({page})=>{
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(ROOT+'/?workflow='+FLOW);
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(13);
  await expect(page.locator('.vue-flow__edge')).toHaveCount(12);
  await expect(page.locator('[data-testid="stock-workflows"] [data-stock-flow="'+FLOW+'"]')).toBeVisible();
  await expect(page.locator('.canvas-stats')).toContainText('13 Nodes');
  await expect(page.locator('.canvas-stats')).toContainText('12 Connections');
  await expect(page.locator('.canvas-stats')).toContainText('DB 연결됨');
  expect(errors).toEqual([]);
  await page.screenshot({path:'test-results/wf01-original-canvas.png',fullPage:true});
});

test('WF-01 step 2: VueFlow edit, server SQLite save and reload', async ({page})=>{
  await page.goto(ROOT+'/?workflow='+FLOW);
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(13);
  const before=await (await page.context().request.get(ROOT+API)).json();
  expect(before.source).toBe('original');
  expect(before.version).toBe(0);
  // Actual browser click and Inspector edit.
  await page.locator('[data-node-id="wf01-trigger"]').click();
  const name=page.getByRole('textbox',{name:'노드 이름'});
  await name.fill('WF-01 수동 원본 입력 / E2E');
  await name.press('Tab');
  // Actual browser palette action adds one visible VueFlow node.
  await page.locator('[data-node-kind="code"]').click();
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(14);
  await page.locator('button.primary-btn').click();
  await expect(page.locator('.bottom-status')).toContainText('서버 DB 저장 성공');
  const saved=await (await page.context().request.get(ROOT+API)).json();
  expect(saved.version).toBe(1);
  expect(saved.source).toBe('server');
  expect(saved.workflow.nodes).toHaveLength(14);
  expect(saved.workflow.nodes.find(n=>n.id==='wf01-trigger').name).toBe('WF-01 수동 원본 입력 / E2E');
  expect(saved.workflow.active).toBe(false);
  const history=await (await page.context().request.get(ROOT+API+'/versions')).json();
  expect(history.versions[0].version).toBe(1);
  await page.reload();
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(14);
  await expect(page.locator('[data-node-id="wf01-trigger"]')).toContainText('WF-01 수동 원본 입력 / E2E');
  await expect(page.locator('.canvas-stats')).toContainText('DB 연결됨 · v1');
  await page.screenshot({path:'test-results/wf01-sqlite-restored.png',fullPage:true});
});

test('WF-01 step 3: SQLite optimistic lock rejects stale update',async ({browser})=>{
  const ctx=await browser.newContext();
  const req=ctx.request;
  const beforeResp=await req.get(ROOT+API);
  expect(beforeResp.status()).toBe(200);
  const before=await beforeResp.json();
  const workflow=before.workflow;
  workflow.name='E2E SQLite version conflict probe';
  const first=await req.put(ROOT+API,{data:{workflow,expectedVersion:before.version}});
  expect(first.status()).toBe(200);
  const next=await first.json();
  expect(next.version).toBe(before.version+1);
  const stale=await req.put(ROOT+API,{data:{workflow,expectedVersion:before.version}});
  expect(stale.status()).toBe(409);
  const read=await req.get(ROOT+API);
  expect((await read.json()).version).toBe(next.version);
  await ctx.close();
});
