import {test,expect} from '@playwright/test';

const BASE='https://investment-n8n-native-editor-production.up.railway.app';

for(const kind of ['strategy','library']){
  test('▶ '+kind+' executes in canvas without modal; ⚙ details opens saved history on demand',async ({page})=>{
    const workflow='operations/WF01-latest-'+kind+'-one.json', nodeId='wf01-'+kind+'-01';
    await page.goto(BASE+'/?workflow='+encodeURIComponent(workflow));
    const card=page.locator('[data-node-id="'+nodeId+'"]');
    await expect(card).toBeVisible();
    await card.hover();
    await expect(page.getByTestId('shared-node-workspace')).toHaveCount(0);
    await page.getByTestId('node-run-'+nodeId).click();
    await expect(page.getByTestId('shared-node-workspace')).toHaveCount(0);
    await expect(card.locator('.node-footer')).toContainText('Python 실행 성공');
    await expect(card).toHaveClass(/is-success/);
    await expect(page.getByTestId('shared-node-workspace')).toHaveCount(0);
    const resp=await page.context().request.get(BASE+'/api/studio/node01/executions?'+new URLSearchParams({workflow,node_id:nodeId}));
    expect(resp.ok()).toBe(true);
    const history=await resp.json();
    expect(history.executions).toHaveLength(1);
    expect(history.executions[0].output_json.kind).toBe(kind);
    const id=history.executions[0].run_id;
    // The second run also preserves the uninterrupted canvas.
    await page.getByTestId('node-run-'+nodeId).click();
    await expect(card.locator('.node-footer')).toContainText('Python 실행 성공');
    await expect(page.getByTestId('shared-node-workspace')).toHaveCount(0);
    await page.getByTestId('node-open-'+nodeId).click();
    await expect(page.getByTestId('shared-node-workspace')).toBeVisible();
    await expect(page.getByTestId('workspace-run-output')).toContainText('"kind": "'+kind+'"');
    await expect(page.getByTestId('workspace-run-status')).toContainText('SUCCESS');
    const history2=await (await page.context().request.get(BASE+'/api/studio/node01/executions?'+new URLSearchParams({workflow,node_id:nodeId}))).json();
    expect(history2.executions.length).toBe(2);
    expect(history2.executions[1].run_id).toBe(id);
    await page.getByRole('button',{name:'노드 작업 공간 닫기'}).click();
    await expect(page.getByTestId('shared-node-workspace')).toHaveCount(0);
    await page.screenshot({path:'test-results/'+kind+'-inline-node-run-no-modal.png',fullPage:true});
  });
}
