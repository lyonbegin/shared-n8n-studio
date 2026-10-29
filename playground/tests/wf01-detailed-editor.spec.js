import {test,expect} from '@playwright/test';

const ROOT='https://investment-n8n-native-editor-production.up.railway.app';
const FLOW='operations/WF01-pine-source-intake-v2.json';
const API='/api/studio/workflows/'+FLOW;

function links(workflow) {
  return Object.entries(workflow.connections).flatMap(([source,ports])=>
    Object.entries(ports).flatMap(([type,outputs])=>outputs.flatMap((targets,sourceIndex)=>
      targets.map(t=>({source,target:t.node,type,sourceIndex,targetIndex:t.index})))));
}
test('WF-01 detailed: 31-node/29-edge contract, independent review webhook, no auto-approval',async ({page})=>{
  const jsErrors=[];page.on('pageerror',e=>jsErrors.push(String(e)));
  await page.goto(ROOT+'/?workflow='+encodeURIComponent(FLOW));
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(31);
  await expect(page.locator('.vue-flow__edge')).toHaveCount(29);
  await expect(page.locator('[data-stock-flow="'+FLOW+'"]')).toBeVisible();
  await expect(page.locator('.canvas-stats')).toContainText('DB 연결됨');
  const res=await page.context().request.get(ROOT+API);
  expect(res.status()).toBe(200);
  const {workflow,version,source}=await res.json();
  expect(source).toBe('original');
  expect(version).toBe(0);
  expect(workflow.active).toBe(false);
  expect(workflow.nodes).toHaveLength(31);
  const edges=links(workflow);
  expect(edges).toHaveLength(29);
  const labels=new Set(workflow.nodes.map(x=>x.name));
  for(const e of edges) {expect(labels.has(e.source)).toBe(true);expect(labels.has(e.target)).toBe(true);}
  const hooks=workflow.nodes.filter(x=>x.type==='n8n-nodes-base.webhook');
  expect(hooks).toHaveLength(2);
  expect(hooks.every(x=>x.parameters.authentication==='headerAuth')).toBe(true);
  const input=workflow.nodes.find(x=>x.id==='wf01-02').parameters.jsCode;
  expect(input).not.toContain('DEMO_STRATEGY');
  const approver=workflow.nodes.find(x=>x.id==='wf01-26');
  expect(approver.parameters.conditions.conditions[0].rightValue).toBe('APPROVED');
  const registrationNodes=new Set(['wf01-01','wf01-02','wf01-03','wf01-04','wf01-06','wf01-07','wf01-09','wf01-10','wf01-12','wf01-13','wf01-14','wf01-16','wf01-17','wf01-18','wf01-20']);
  const idByName=Object.fromEntries(workflow.nodes.map(n=>[n.name,n.id]));
  expect(edges.every(e=>idByName[e.source]!=='wf01-20')).toBe(true);
  expect(registrationNodes.has('wf01-20')).toBe(true);
  expect(jsErrors).toEqual([]);
  await page.screenshot({path:'test-results/wf01-detailed-31nodes.png',fullPage:true});
});

test('WF-01 detailed: edit VueFlow node and persist original n8n code in SQLite',async ({page})=>{
  await page.goto(ROOT+'/?workflow='+encodeURIComponent(FLOW));
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(31);
  const before=await (await page.context().request.get(ROOT+API)).json();
  const n=before.workflow.nodes.find(x=>x.id==='wf01-22');
  expect(n).toBeTruthy();
  await page.locator('[data-node-id="wf01-22"]').click();
  const textarea=page.getByRole('textbox',{name:'노드 JSON 파라미터'});
  await expect(textarea).toHaveValue(/lookup_ok/);
  const revised={...n.parameters,jsCode:n.parameters.jsCode+'\n// WF01-DETAIL-EDIT-VERIFIED'};
  await textarea.fill(JSON.stringify(revised,null,2));
  await page.getByRole('button',{name:'설정 적용'}).click();
  await page.locator('button.primary-btn').click();
  await expect(page.locator('.bottom-status')).toContainText('서버 DB 저장 성공');
  const after=await (await page.context().request.get(ROOT+API)).json();
  expect(after.version).toBe(1);
  expect(after.workflow.active).toBe(false);
  expect(after.workflow.nodes.find(x=>x.id==='wf01-22').parameters).toEqual(revised);
  expect(links(after.workflow)).toHaveLength(29);
  await page.reload();
  await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(31);
  await page.locator('[data-node-id="wf01-22"]').click();
  await expect(page.getByRole('textbox',{name:'노드 JSON 파라미터'})).toHaveValue(/WF01-DETAIL-EDIT-VERIFIED/);
  await expect(page.locator('.canvas-stats')).toContainText('DB 연결됨 · v1');
  const rev=await (await page.context().request.get(ROOT+API+'/versions')).json();
  expect(rev.versions.some(x=>x.version===1)).toBe(true);
  await page.screenshot({path:'test-results/wf01-detailed-sqlite-restored.png',fullPage:true});
});
