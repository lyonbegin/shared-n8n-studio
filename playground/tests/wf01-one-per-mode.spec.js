import {test,expect} from '@playwright/test';

const BASE='https://investment-n8n-native-editor-production.up.railway.app';
const modes=['strategy','library'];
const path=kind=>'operations/WF01-latest-'+kind+'-one.json';
const graphURL=kind=>BASE+'/?workflow='+encodeURIComponent(path(kind));
const apiURL=kind=>BASE+'/api/studio/workflows/'+path(kind);
const id=(kind,n)=>'wf01-'+kind+'-'+String(n).padStart(2,'0');
const linkCount=w=>Object.values(w.connections).reduce((sum,ports)=>
  sum+Object.values(ports).reduce((a,outputs)=>a+outputs.reduce((b,t)=>b+t.length,0),0),0);

for (const kind of modes) {
 test('WF01 '+kind+' ONLY: actual 16-node VueFlow, 16 edges, source-first, no cross-type',async ({page})=>{
   await page.goto(graphURL(kind));
   await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(16);
   await expect(page.locator('.vue-flow__edge')).toHaveCount(16);
   await expect(page.locator('[data-stock-flow="'+path(kind)+'"]')).toBeVisible();
   const response=await page.context().request.get(apiURL(kind));
   expect(response.status()).toBe(200);
   const state=await response.json();
   expect(state.source).toBe('original');
   expect(state.version).toBe(0);
   const w=state.workflow;
   expect(w.active).toBe(false);
   expect(w.meta.kind).toBe(kind);
   expect(w.meta.limit_per_execution).toBe(1);
   expect(w.meta.always_start_at_latest).toBe(true);
   expect(w.meta.source_execution_wired).toBe(false);
   expect(w.nodes).toHaveLength(16);
   expect(linkCount(w)).toBe(16);
   const byId=n=>w.nodes.find(x=>x.id===id(kind,n));
   expect(byId(2).parameters.jsCode).toContain('page:1');
   expect(byId(3).parameters.url).toContain('kind='+kind);
   expect(byId(3).parameters.url).toContain('sort=updated_desc');
   expect(byId(5).parameters.url).toContain('check-batch');
   expect(byId(6).parameters.jsCode).toContain('imported===false');
   expect(byId(9).parameters.jsCode).toContain('next_page');
   expect(byId(11).parameters.url).toContain('kind='+kind);
   expect(byId(15).parameters.url).toContain('source-registry/import');
   expect(byId(15).parameters.jsonBody).toContain('idempotency_key');
   expect(byId(16).parameters.jsCode).toContain("p.status==='IMPORTED'?1:0");
   expect(w.nodes.filter(n=>n.type==='n8n-nodes-base.httpRequest').every(n=>n.parameters.authentication==='genericCredentialType')).toBe(true);
   const labels=new Set(w.nodes.map(n=>n.name));
   for(const [source,ports] of Object.entries(w.connections)){
     expect(labels.has(source)).toBe(true);
     for(const outputs of Object.values(ports))for(const targets of outputs)for(const t of targets)expect(labels.has(t.node)).toBe(true);
   }
   await page.screenshot({path:'test-results/wf01-'+kind+'-only-canvas.png',fullPage:true});
 });

 test('WF01 '+kind+' ONLY: actual source selection code skips newest imported and chooses next unseen',async ({request})=>{
   const response=await request.get(apiURL(kind));
   expect(response.status()).toBe(200);
   const w=(await response.json()).workflow;
   const selected=w.nodes.find(x=>x.id===id(kind,6)).parameters.jsCode;
   const fn=new Function('$input',selected);
   const select=items=>fn({all:()=>[{json:{kind,items,page:1,next_page:2,max_pages:20}}]})[0].json;
   const latest={kind,source_id:'top',version_key:'v12',updated_at:'2026-10-30',imported:true};
   const fresh={kind,source_id:'next',version_key:'v8',updated_at:'2026-10-29',imported:false};
   const different={kind:kind==='strategy'?'library':'strategy',source_id:'wrong',version_key:'v4',imported:false};
   const hit=select([latest,different,fresh]);
   expect(hit.candidate.source_id).toBe('next');
   expect(hit.has_candidate).toBe(true);
   expect(hit.selected_count).toBe(0);
   const missing=select([latest]);
   expect(missing.candidate).toBe(null);
   expect(missing.can_continue).toBe(true);
   const done=fn({all:()=>[{json:{kind,page:20,next_page:21,max_pages:20,items:[latest]}}]})[0].json;
   expect(done.has_candidate).toBe(false);
   expect(done.can_continue).toBe(false);
   const initial=new Function('$input',w.nodes.find(x=>x.id===id(kind,2)).parameters.jsCode)({});
   expect(initial[0].json.page).toBe(1);
   expect(initial[0].json.kind).toBe(kind);
 });

 test('WF01 '+kind+' ONLY: edit one real Code node; SQLite save and reload',async ({page})=>{
   await page.goto(graphURL(kind));
   await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(16);
   const before=await (await page.context().request.get(apiURL(kind))).json();
   const target=before.workflow.nodes.find(n=>n.id===id(kind,6));
   await page.locator('[data-node-id="'+id(kind,6)+'"]').click();
   const code=page.getByRole('textbox',{name:'노드 JSON 파라미터'});
   const updated={...target.parameters,jsCode:target.parameters.jsCode+'\n// TEST_MODE_ONLY_NOT_LIVE'};
   await code.fill(JSON.stringify(updated,null,2));
   await page.getByRole('button',{name:'설정 적용'}).click();
   await page.locator('button.primary-btn').click();
   await expect(page.locator('.bottom-status')).toContainText('서버 DB 저장 성공');
   const saved=await (await page.context().request.get(apiURL(kind))).json();
   expect(saved.version).toBe(1);
   expect(saved.workflow.nodes.find(n=>n.id===id(kind,6)).parameters).toEqual(updated);
   expect(saved.workflow.active).toBe(false);
   expect(linkCount(saved.workflow)).toBe(16);
   await page.reload();
   await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(16);
   await page.locator('[data-node-id="'+id(kind,6)+'"]').click();
   await expect(page.getByRole('textbox',{name:'노드 JSON 파라미터'})).toHaveValue(/TEST_MODE_ONLY_NOT_LIVE/);
   await expect(page.locator('.canvas-stats')).toContainText('DB 연결됨 · v1');
 });
}
