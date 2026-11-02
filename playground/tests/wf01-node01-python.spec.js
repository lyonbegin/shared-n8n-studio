import {test,expect} from '@playwright/test';

const BASE='https://investment-n8n-native-editor-production.up.railway.app';
for(const kind of ['strategy','library']){
  const path='operations/WF01-latest-'+kind+'-one.json';
  const nodeId='wf01-'+kind+'-01';
  const endpoint='/api/studio/node01/execute';

  test('WF01 '+kind+' N01 Python actual click, input/output, SQLite reload',async ({page})=>{
    await page.goto(BASE+'/?workflow='+encodeURIComponent(path));
    await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(16);
    await page.locator('[data-node-id="'+nodeId+'"]').click();
    const panel=page.getByTestId('wf01-node01-python');
    await expect(panel).toBeVisible();
    await expect(page.getByTestId('node01-python-binding')).toContainText('investment_node_adapter.execute_node01');
    const input={ui_selection:kind,requested_detail_limit:1};
    await page.getByTestId('node01-input').fill(JSON.stringify(input,null,2));
    await page.getByTestId('execute-node01').click();
    await expect(page.getByTestId('node01-result')).toContainText('SUCCESS');
    const actual=JSON.parse(await page.getByTestId('node01-actual-input').innerText());
    const output=JSON.parse(await page.getByTestId('node01-output').innerText());
    expect(actual).toEqual(input);
    expect(output).toMatchObject({kind,page:1,max_pages:3,max_detail_success:1,
      sort:'recent_extended',execution_mode:'ONE_NODE_ONLY',tradingview_requested:false,
      next_node_executed:false});
    await expect(page.getByTestId('node01-history-count')).toContainText('1건');
    const historyResponse=await page.context().request.get(BASE+'/api/studio/node01/executions?'+
      new URLSearchParams({workflow:path,node_id:nodeId}));
    expect(historyResponse.status()).toBe(200);
    const history=await historyResponse.json();
    expect(history.executions).toHaveLength(1);
    expect(history.executions[0].output_json).toEqual(output);
    expect(history.executions[0].python_function).toBe('execute_node01');
    expect(history.executions[0].code_sha256).toMatch(/^[a-f0-9]{64}$/);
    const savedRun=history.executions[0].run_id;
    await page.reload();
    await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(16);
    await page.locator('[data-node-id="'+nodeId+'"]').click();
    await expect(page.getByTestId('node01-latest-history')).toContainText(savedRun);
    await page.screenshot({path:'test-results/wf01-node01-'+kind+'-executed.png',fullPage:true});
  });

  test('WF01 '+kind+' N01 rejects bad input, persists error, blocks other nodes',async ({page})=>{
    await page.goto(BASE+'/?workflow='+encodeURIComponent(path));
    await page.locator('[data-node-id="'+nodeId+'"]').click();
    await page.getByTestId('node01-input').fill(JSON.stringify({ui_selection:kind,requested_detail_limit:10}));
    await page.getByTestId('execute-node01').click();
    await expect(page.getByTestId('node01-result')).toContainText('FAILED');
    await expect(page.getByTestId('node01-error')).toContainText('DETAIL_LIMIT_MUST_EQUAL_ONE');
    const badNode=await page.context().request.post(BASE+endpoint,{
      headers:{'X-Studio-Node-Run':'N01'},data:{workflow:path,node_id:'wf01-'+kind+'-03',
        input_json:{ui_selection:kind,requested_detail_limit:1}}});
    expect(badNode.status()).toBe(403);
    const noHeader=await page.context().request.post(BASE+endpoint,{
      data:{workflow:path,node_id:nodeId,input_json:{ui_selection:kind,requested_detail_limit:1}}});
    expect(noHeader.status()).toBe(403);
    await page.locator('[data-node-id="wf01-'+kind+'-03"]').click();
    await expect(page.getByTestId('execute-node01')).toHaveCount(0);
  });
}

test('N01 Python history isolated by browser cookie',async ({browser})=>{
  const a=await browser.newContext(), b=await browser.newContext();
  const path='operations/WF01-latest-strategy-one.json',id='wf01-strategy-01';
  // GET creates independent HttpOnly studio_sid cookies.
  await a.request.get(BASE+'/api/studio/workflows/'+path);
  await b.request.get(BASE+'/api/studio/workflows/'+path);
  const run=await a.request.post(BASE+'/api/studio/node01/execute',{
    headers:{'X-Studio-Node-Run':'N01'},
    data:{workflow:path,node_id:id,input_json:{ui_selection:'strategy',requested_detail_limit:1}}});
  expect(run.status()).toBe(200);
  const url=BASE+'/api/studio/node01/executions?'+new URLSearchParams({workflow:path,node_id:id});
  const ar=await (await a.request.get(url)).json(), br=await (await b.request.get(url)).json();
  expect(ar.executions.length).toBe(1);
  expect(br.executions.length).toBe(0);
  await a.close();await b.close();
});
