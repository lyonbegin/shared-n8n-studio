import {test,expect} from '@playwright/test';

const ROOT='https://investment-n8n-native-editor-production.up.railway.app';
const FLOW='operations/WF02-pine-to-python.json';
const API='/api/studio/workflows/'+FLOW;
const allEdges=workflow=>Object.entries(workflow.connections||{}).flatMap(([source,types])=>
  Object.values(types).flatMap(outputs=>outputs.flatMap((targets,sourceIndex)=>
    targets.map(t=>({source,target:t.node,sourceIndex,targetIndex:t.index}))));

test('WF02-01 live VueFlow 48 nodes, 50 edges, rights gate and parallel semantic merges',async ({page})=>{
  const runtimeErrors=[];
  page.on('pageerror',e=>runtimeErrors.push(String(e)));
  await page.goto(ROOT+'/?workflow='+encodeURIComponent(FLOW));
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(48);
  await expect(page.locator('.vue-flow__edge')).toHaveCount(50);
  await expect(page.locator('[data-stock-flow="'+FLOW+'"]')).toBeVisible();
  await expect(page.locator('.canvas-stats')).toContainText('DB 연결됨');
  const res=await page.context().request.get(ROOT+API);
  expect(res.status()).toBe(200);
  const state=await res.json();
  expect(state.source).toBe('original');
  expect(state.version).toBe(0);
  const w=state.workflow;
  expect(w.active).toBe(false);
  expect(w.nodes).toHaveLength(48);
  const connections=allEdges(w);
  expect(connections).toHaveLength(50);
  const labels=new Set(w.nodes.map(n=>n.name));
  expect(new Set(w.nodes.map(n=>n.id)).size).toBe(48);
  for(const edge of connections) {
    expect(labels.has(edge.source)).toBe(true);
    expect(labels.has(edge.target)).toBe(true);
  }
  const n=id=>w.nodes.find(x=>x.id==='wf02-'+id);
  expect(n('01').parameters.authentication).toBe('headerAuth');
  expect(n('06').parameters.url).toContain('/conversion-input');
  expect(n('07').parameters.jsCode).toContain('pin_match');
  expect(n('15').parameters.url).toContain('/parse');
  expect(n('22').parameters.url).toContain('/ir');
  expect(n('34').parameters.url).toContain('/generate');
  expect(n('41').parameters.url).toContain('/sandbox-run');
  expect(n('42').parameters.url).toContain('/compare');
  expect(n('43').parameters.jsCode).toContain('parity_pass');
  expect(['29','30','40'].every(id=>n(id).type==='n8n-nodes-base.merge')).toBe(true);
  expect(n('48').parameters.jsCode).toContain('live_allowed:false');
  expect(w.meta.executionEnabled).toBe(false);
  expect(w.meta.converterEndpointsImplemented).toBe(false);
  expect(runtimeErrors).toEqual([]);
  await page.screenshot({path:'test-results/wf02-48-nodes.png',fullPage:true});
});

test('WF02-02 real inspector edit, SQLite server save, reload, revision history',async ({page})=>{
  await page.goto(ROOT+'/?workflow='+encodeURIComponent(FLOW));
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(48);
  const initial=await (await page.context().request.get(ROOT+API)).json();
  const n=initial.workflow.nodes.find(x=>x.id==='wf02-31');
  expect(n).toBeTruthy();
  await page.locator('[data-node-id="wf02-31"]').click();
  const field=page.getByRole('textbox',{name:'노드 JSON 파라미터'});
  await expect(field).toHaveValue(/semantics_ok/);
  const updated={...n.parameters,jsCode:n.parameters.jsCode+'\n// WF02-SQLITE-EDITOR-TEST'};
  await field.fill(JSON.stringify(updated,null,2));
  await page.getByRole('button',{name:'설정 적용'}).click();
  await page.locator('button.primary-btn').click();
  await expect(page.locator('.bottom-status')).toContainText('서버 DB 저장 성공');
  const stored=await (await page.context().request.get(ROOT+API)).json();
  expect(stored.source).toBe('server');
  expect(stored.version).toBe(1);
  expect(stored.workflow.active).toBe(false);
  expect(stored.workflow.nodes.find(x=>x.id==='wf02-31').parameters).toEqual(updated);
  expect(allEdges(stored.workflow)).toHaveLength(50);
  await page.reload();
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(48);
  await page.locator('[data-node-id="wf02-31"]').click();
  await expect(page.getByRole('textbox',{name:'노드 JSON 파라미터'})).toHaveValue(/WF02-SQLITE-EDITOR-TEST/);
  await expect(page.locator('.canvas-stats')).toContainText('DB 연결됨 · v1');
  const versions=await (await page.context().request.get(ROOT+API+'/versions')).json();
  expect(versions.versions[0].version).toBe(1);
  await page.screenshot({path:'test-results/wf02-sqlite-restored.png',fullPage:true});
});

test('WF02-03 version conflict protection on a distinct anonymous browser',async ({browser})=>{
  const ctx=await browser.newContext();
  const response=await ctx.request.get(ROOT+API);
  expect(response.status()).toBe(200);
  const state=await response.json();
  const w=state.workflow;
  w.name='WF02 E2E isolated draft check';
  const first=await ctx.request.put(ROOT+API,{data:{workflow:w,expectedVersion:state.version}});
  expect(first.status()).toBe(200);
  const stale=await ctx.request.put(ROOT+API,{data:{workflow:w,expectedVersion:state.version}});
  expect(stale.status()).toBe(409);
  const restored=await (await ctx.request.get(ROOT+API)).json();
  expect(restored.version).toBe(state.version+1);
  expect(restored.workflow.nodes).toHaveLength(48);
  await ctx.close();
});
