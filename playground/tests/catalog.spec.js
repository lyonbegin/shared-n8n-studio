import {test,expect} from '@playwright/test';
import {NODE_CATALOG,NODE_GROUPS,NODE_BY_KIND,defaultParameters,validateCatalog,validateParameters} from '../src/node-catalog.js';

test('canonical fifty node kinds have unique IDs and usable typed defaults',()=>{
  expect(validateCatalog()).toBe(true);
  expect(NODE_CATALOG).toHaveLength(50);
  expect(new Set(NODE_CATALOG.map(n=>n.kind)).size).toBe(50);
  expect(NODE_CATALOG.filter(n=>n.implementation==='native').length).toBeGreaterThanOrEqual(9);
  expect(NODE_CATALOG.find(n=>n.kind==='business-operation')?.fields.map(f=>f.key)).toContain('executionMode');
  expect(NODE_BY_KIND['approval'].outputs).toEqual(['approved','rejected','timeout']);
  for(const spec of NODE_CATALOG){
    const defaults=defaultParameters(spec.kind);
    expect(validateParameters(spec.kind,defaults),spec.kind).toEqual([]);
    for(const field of spec.fields)expect(defaults).toHaveProperty(field.key);
  }
  expect(NODE_GROUPS).toContain('오류·복구');
});

test.beforeEach(async({page})=>{
  await page.goto('/');
  await expect(page.locator('[data-testid="catalog-count"]')).toHaveText('50 TYPES');
});

test('all categories filter and search actual node kind names',async({page})=>{
  const filter=page.getByRole('combobox',{name:'노드 분류 선택'});
  await filter.selectOption('오류·복구');
  await expect(page.locator('.palette-item').first()).toBeVisible();
  await expect(page.locator('.palette-item[data-node-kind="circuit-breaker"]')).toHaveCount(1);
  await expect(page.locator('.palette-item[data-node-kind="business-operation"]')).toHaveCount(0);
  await filter.selectOption('all');
  const search=page.getByRole('textbox',{name:'노드 검색'});
  await search.fill('Quorum');
  await expect(page.locator('.palette-item[data-node-kind="join-quorum"]')).toHaveCount(1);
  await expect(page.locator('.palette-item')).toHaveCount(1);
});

test('Business Operation has real configurable API, Python, Code, Workflow and Mock forms',async({page})=>{
  await page.getByRole('textbox',{name:'노드 검색'}).fill('Business Operation');
  await page.locator('[data-node-kind="business-operation"]').click();
  await expect(page.locator('.vue-flow__node')).toHaveCount(6);
  await expect(page.locator('[data-testid="node-contract"]')).toContainText('프로젝트 확장 구현 필요');
  await expect(page.locator('[data-setting="apiUrl"]')).toBeVisible();
  const mode=page.locator('[data-setting="executionMode"]');
  await mode.selectOption('python');
  await expect(page.locator('[data-setting="pythonFunction"]')).toBeVisible();
  await expect(page.locator('[data-setting="apiUrl"]')).toHaveCount(0);
  await page.locator('[data-setting="pythonFunction"]').fill('qlib.app.bridge.predict');
  await page.locator('[data-setting="pythonFunction"]').blur();
  await mode.selectOption('javascript');
  await expect(page.locator('[data-setting="javascriptCode"]')).toBeVisible();
  await mode.selectOption('workflow');
  await expect(page.locator('[data-setting="workflowId"]')).toBeVisible();
  await mode.selectOption('mock');
  await expect(page.locator('[data-setting="mockResult"]')).toBeVisible();
  await page.locator('[data-setting="adapter"]').selectOption('procureflow');
  await page.locator('[data-setting="operationId"]').fill('H05');
  await page.locator('[data-setting="operationId"]').blur();
  await expect(page.getByRole('textbox',{name:'노드 JSON 파라미터'})).toHaveValue(/H05/);
  await page.getByRole('button',{name:'브라우저 저장'}).click();
  await page.reload();
  await page.locator('button[title="브라우저 저장값 불러오기"]').click();
  await expect(page.locator('.vue-flow__node')).toHaveCount(6);
  await page.getByRole('textbox',{name:'노드 검색'}).fill('');
  await page.locator('.vue-flow__node').last().click();
  await expect(page.locator('[data-setting="adapter"]')).toHaveValue('procureflow');
  await expect(page.locator('[data-setting="executionMode"]')).toHaveValue('mock');
});

test('IF, approvals and quorum use distinct named source port handles',async({page})=>{
  const ifNode=page.locator('.vue-flow__node').filter({hasText:'조건 확인'});
  await expect(ifNode.locator('.port-out')).toHaveCount(2);
  await expect(ifNode.locator('.port-out[data-handleid="true"]')).toHaveCount(1);
  await expect(ifNode.locator('.port-out[data-handleid="false"]')).toHaveCount(1);
  await page.getByRole('textbox',{name:'노드 검색'}).fill('Human Approval');
  await page.locator('[data-node-kind="approval"]').click();
  await expect(page.locator('.vue-flow__node').last().locator('.port-out')).toHaveCount(3);
  await expect(page.locator('.vue-flow__node').last().locator('.port-out[data-handleid="approved"]')).toHaveCount(1);
});

test('new node kind settings are validated and rejected when malformed',async({page})=>{
  await page.getByRole('textbox',{name:'노드 검색'}).fill('Rate Limit');
  await page.locator('[data-node-kind="rate-limit"]').click();
  const input=page.locator('[data-setting="limit"]');
  await expect(input).toHaveValue('10');
  await input.fill('-1');await input.blur();
  await expect(page.locator('.bottom-status')).toContainText('invalid number');
  await expect(page.getByRole('textbox',{name:'노드 JSON 파라미터'})).toHaveValue(/"limit": 10/);
  await input.fill('24');await input.blur();
  await expect(page.getByRole('textbox',{name:'노드 JSON 파라미터'})).toHaveValue(/"limit": 24/);
});

test('investment and procurement sample workflows now include business operation and control gates',async({page})=>{
  await page.getByRole('button',{name:/주식 자동화/}).click();
  await expect(page.getByText('투자 Python 엔진 실행')).toBeVisible();
  await expect(page.getByText('운용 승인 대기')).toBeVisible();
  await page.getByRole('button',{name:/ProcureFlow/}).click();
  await expect(page.getByText('G2B 개찰 수집')).toBeVisible();
  await expect(page.getByText('10년 수집 완전성')).toBeVisible();
});


test('browser save and reload preserves every original plus added node and every edge',async({page})=>{
  const initialIds=await page.locator('.studio-node').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-node-id')));
  expect(initialIds).toHaveLength(5);
  const before=await page.locator('.vue-flow__edge').count();
  for(const kind of ['business-operation','approval','circuit-breaker']){
    await page.getByRole('textbox',{name:'노드 검색'}).fill(kind==='business-operation'?'Business Operation':kind==='approval'?'Human Approval':'Circuit Breaker');
    await page.locator('[data-node-kind="'+kind+'"]').click();
  }
  await expect(page.locator('.vue-flow__node')).toHaveCount(8);
  const savedIds=await page.locator('.studio-node').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-node-id')).sort());
  await page.getByRole('button',{name:'브라우저 저장'}).click();
  await page.reload();
  await page.locator('button[title="브라우저 저장값 불러오기"]').click();
  await expect(page.locator('.vue-flow__node')).toHaveCount(8);
  await expect(page.locator('.vue-flow__edge')).toHaveCount(before);
  const restoredIds=await page.locator('.studio-node').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-node-id')).sort());
  expect(restoredIds).toEqual(savedIds);
  for(const id of initialIds)expect(restoredIds).toContain(id);
  await expect(page.locator('.studio-node').filter({hasText:'재시도 대기'})).toHaveCount(1);
});
