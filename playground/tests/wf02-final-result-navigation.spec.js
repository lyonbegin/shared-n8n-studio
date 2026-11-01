import {test,expect} from '@playwright/test';
const FLOW='operations/WF02-chart-parity-first-stage.json';
const EDITOR='https://investment-n8n-native-editor-production.up.railway.app';
const PARITY='https://investment-pine-parity-review-production.up.railway.app';
const PINE=[
'//@version=6','strategy("SYNTHETIC CI cross", overlay=true)',
'fastN = input.int(3, "Fast")','slowN = input.int(5, "Slow")',
'fastMA = ta.sma(close, fastN)','slowMA = ta.ema(close, slowN)',
'longCondition = ta.crossover(fastMA, slowMA)',
'shortCondition = ta.crossunder(fastMA, slowMA)',
'if (longCondition)','    strategy.entry("L", strategy.long)',
'if (shortCondition)','    strategy.entry("S", strategy.short)',
'plot(fastMA)','plot(slowMA)'
].join('\n');
function makeCsv(){
 let a=['time,open,high,low,close,volume'];
 for(let i=0;i<48;i++){
  const price=100+10*Math.sin(i*.26)+i*.04;
  const open=price-.5,close=price+.5;
  a.push(['SYNTHETIC-'+i,open,close+1,open-1,close,100].join(','));
 }
 return a.join('\n')+'\n';
}
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+rllUAAAAASUVORK5CYII=','base64');
test('WF02 editor submits real backend steps, then final node alone opens independent chart page',async({page})=>{
 await page.goto(EDITOR+'/?workflow='+encodeURIComponent(FLOW));
 await expect(page.locator('[data-testid="studio-node"]')).toHaveCount(8);
 await expect(page.getByTestId('node-result-wf02-parity-08')).toHaveCount(0);
 await page.getByTestId('workflow-open-run').click();
 await expect(page.getByTestId('workflow-run-panel')).toBeVisible();
 await page.locator('[data-run-field="symbol"]').fill('SYNTHETIC:CI');
 await page.locator('[data-run-field="timeframe"]').fill('1D');
 await page.locator('[data-run-field="pine_code"]').fill(PINE);
 await page.locator('[data-run-field="columns"]').fill('{}');
 await page.locator('[data-run-field="csv_text"]').setInputFiles({
   name:'synthetic-ci.csv',mimeType:'text/csv',buffer:Buffer.from(makeCsv())
 });
 await page.locator('[data-run-field="screenshot_data_url"]').setInputFiles({
   name:'synthetic-not-tradingview.png',mimeType:'image/png',buffer:png
 });
 await page.getByTestId('workflow-run-start').click();
 await expect(page.getByTestId('workflow-run-panel')).toHaveCount(0);
 await expect(page.getByTestId('node-result-wf02-parity-08')).toBeVisible({timeout:40000});
 await expect(page.locator('[data-node-id="wf02-parity-08"] .node-footer')).toContainText('비교 결과 확인 가능');
 const runBtn=page.getByTestId('node-result-wf02-parity-08');
 const popupPromise=page.waitForEvent('popup');
 await runBtn.click();
 const popup=await popupPromise;
 await popup.waitForLoadState('domcontentloaded');
 expect(popup.url().startsWith(PARITY+'/?run=')).toBe(true);
 await expect(popup.locator('#leftChart img')).toBeVisible();
 await expect(popup.locator('#rightChart img')).toBeVisible();
 await expect(popup.locator('#status')).not.toHaveText(/PASS|완료/);
 const runId=new URL(popup.url()).searchParams.get('run');
 expect(runId).toMatch(/^[0-9a-f]{24}$/);
 const record=await(await page.context().request.get(PARITY+'/api/runs/'+runId)).json();
 expect(record.status).toBe('REFERENCE_COLUMNS_REQUIRED');
 expect(record.numeric_match).toBe(false);
 const trace=await(await page.context().request.get(PARITY+'/api/runs/'+runId+'/trace')).json();
 expect(trace.events).toHaveLength(7);
 await popup.close();
 await page.reload();
 await expect(page.getByTestId('node-result-wf02-parity-08')).toBeVisible({timeout:25000});
 await page.screenshot({path:'test-results/wf02-final-result-node-and-flow.png',fullPage:true});
});
