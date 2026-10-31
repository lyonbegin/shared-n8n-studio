import {test,expect} from '@playwright/test';
const BASE='https://investment-n8n-native-editor-production.up.railway.app';

for(const kind of ['strategy','library']){
 test('full N01 output → SQLite edge → N02 input → N02 real execution → N03 ready '+kind,async({page})=>{
   const workflow='operations/WF01-latest-'+kind+'-one.json';
   const n1='wf01-'+kind+'-01',n2='wf01-'+kind+'-02',n3='wf01-'+kind+'-03';
   const url=BASE+'/?workflow='+encodeURIComponent(workflow);
   await page.goto(url);
   await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(16);
   const first=page.locator('[data-node-id="'+n1+'"]');
   const second=page.locator('[data-node-id="'+n2+'"]');
   await first.hover();
   await page.getByTestId('node-run-'+n1).click();
   await expect(first.locator('.node-footer')).toContainText('Python 실행 성공');
   await expect(page.getByTestId('shared-node-workspace')).toHaveCount(0);
   await expect(second.locator('.node-footer')).toContainText('입력 준비');
   const transfers=await(await page.context().request.get(BASE+'/api/studio/nodes/transfers?'+new URLSearchParams({workflow,node_id:n2}))).json();
   expect(transfers.transfers.length).toBe(1);
   const transfer=transfers.transfers[0];
   expect(transfer.status).toBe('READY');
   expect(transfer.output_json).toMatchObject({kind,page:1,max_pages:3,max_detail_success:1,
     sort:'recent_extended',tradingview_requested:false,next_node_executed:false});
   const oldRun=transfer.source_run_id;
   await second.hover();
   await page.getByTestId('node-open-'+n2).click();
   await expect(page.getByTestId('workspace-upstream')).toBeVisible();
   await expect(page.getByTestId('workspace-upstream-output')).toContainText('"sort": "recent_extended"');
   await expect(page.getByTestId('workspace-upstream-output')).toContainText('"execution_mode": "ONE_NODE_ONLY"');
   await page.getByRole('button',{name:'노드 작업 공간 닫기'}).click();
   await page.getByTestId('node-run-'+n2).click();
   await expect(second.locator('.node-footer')).toContainText('Python 실행 성공');
   await expect(page.getByTestId('shared-node-workspace')).toHaveCount(0);
   await expect(page.locator('[data-node-id="'+n3+'"] .node-footer')).toContainText('입력 준비');
   const h=await(await page.context().request.get(BASE+'/api/studio/nodes/history?'+new URLSearchParams({workflow,node_id:n2}))).json();
   expect(h.executions.length).toBe(1);
   const exec=h.executions[0];
   expect(exec.upstream_run_id).toBe(oldRun);
   for(const [key,value] of Object.entries(transfer.output_json))expect(exec.input_json[key]).toEqual(value);
   expect(exec.output_json).toMatchObject({...transfer.output_json,page_size:50,selected_count:0});
   const graph=await(await page.context().request.get(BASE+'/api/studio/nodes/graph-state?'+new URLSearchParams({workflow}))).json();
   expect(graph.edges.some(e=>e.source_node_id===n1&&e.target_node_id===n2&&e.status==='CONSUMED')).toBe(true);
   expect(graph.edges.some(e=>e.source_node_id===n2&&e.target_node_id===n3&&e.status==='READY')).toBe(true);
   await page.reload();
   await expect(page.locator('[data-node-id="'+n2+'"] .node-footer')).toContainText('Python 실행 성공');
   await expect(page.locator('[data-node-id="'+n3+'"] .node-footer')).toContainText('입력 준비');
   await page.screenshot({path:'test-results/'+kind+'-N01-N02-N03-data-lineage.png',fullPage:true});
 });
}
