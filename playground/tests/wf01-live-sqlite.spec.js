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

test('WF-01 step 4: drag node, connect output handle, save edge and coordinates to SQLite',async ({page})=>{
  await page.goto(ROOT+'/?workflow='+FLOW);
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(13);
  const initial=await (await page.context().request.get(ROOT+API)).json();
  const initialPoint=initial.workflow.nodes.find(n=>n.id==='wf01-trigger').position;
  const originalEdges=12;
  const sourceNode=page.locator('[data-node-id="wf01-trigger"]');
  await page.locator('button[title="화면 맞춤"]').click();
  const box=await sourceNode.boundingBox();
  expect(box).not.toBeNull();
  const x=box.x+box.width/2,y=box.y+box.height/2;
  await page.mouse.move(x,y);
  await page.mouse.down();
  await page.mouse.move(x+42,y+24,{steps:12});
  await page.mouse.up();
  await expect(page.locator('.bottom-status')).toContainText('노드 위치 변경');
  await page.locator('[data-node-kind="code"]').click();
  await page.locator('button[title="화면 맞춤"]').click();
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(14);
  const last=page.locator('[data-node-id^="node_"]').last();
  const source=sourceNode.locator('.vue-flow__handle.source').last();
  const target=last.locator('.vue-flow__handle.target').first();
  const a=await source.boundingBox(), b=await target.boundingBox();
  expect(a).not.toBeNull();
  expect(b).not.toBeNull();
  await page.mouse.move(a.x+a.width/2,a.y+a.height/2);
  await page.mouse.down();
  await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:18});
  await page.mouse.up();
  // VueFlow also supports click-to-connect; exercise it if mouse drag did not complete.
  if(await page.locator('.vue-flow__edge').count()===originalEdges){
    await source.click({force:true});
    await target.click({force:true});
  }
  await expect(page.locator('.vue-flow__edge')).toHaveCount(originalEdges+1);
  await page.locator('button.primary-btn').click();
  await expect(page.locator('.bottom-status')).toContainText('서버 DB 저장 성공');
  const saved=await (await page.context().request.get(ROOT+API)).json();
  expect(saved.workflow.nodes.find(n=>n.id==='wf01-trigger').position).not.toEqual(initialPoint);
  const edges=Object.values(saved.workflow.connections)
    .flatMap(v=>Object.values(v).flatMap(port=>port.flat()));
  expect(edges.length).toBe(originalEdges+1);
  await page.reload();
  await expect(page.locator('.vue-flow__edge')).toHaveCount(originalEdges+1);
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(14);
  await page.screenshot({path:'test-results/wf01-drag-connect-restored.png',fullPage:true});
});

test('WF-01 step 5: edit real n8n jsCode JSON and restore exactly from SQLite',async ({page})=>{
  await page.goto(ROOT+'/?workflow='+FLOW);
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(13);
  const original=await (await page.context().request.get(ROOT+API)).json();
  const codeNode=original.workflow.nodes.find(n=>n.id==='입력 정규화');
  expect(codeNode).toBeTruthy();
  await page.locator('[data-node-id="입력 정규화"]').click();
  const field=page.getByRole('textbox',{name:'노드 JSON 파라미터'});
  const patched={...codeNode.parameters,jsCode:codeNode.parameters.jsCode+'\\n// WF01-SQLITE-E2E-CHECK'};
  await field.fill(JSON.stringify(patched,null,2));
  await page.getByRole('button',{name:'설정 적용'}).click();
  await page.locator('button.primary-btn').click();
  await expect(page.locator('.bottom-status')).toContainText('서버 DB 저장 성공');
  let stored=await (await page.context().request.get(ROOT+API)).json();
  expect(stored.workflow.nodes.find(n=>n.id==='입력 정규화').parameters).toEqual(patched);
  await page.reload();
  await page.locator('[data-node-id="입력 정규화"]').click();
  await expect(page.getByRole('textbox',{name:'노드 JSON 파라미터'})).toContainText('WF01-SQLITE-E2E-CHECK');
});
