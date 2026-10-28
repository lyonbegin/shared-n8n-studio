import {test,expect} from '@playwright/test';

test.beforeEach(async({page})=>{
  await page.goto('/');
  await expect(page.getByText('Shared n8n Studio',{exact:true}).first()).toBeVisible();
  await expect(page.locator('.vue-flow__node')).toHaveCount(5);
});

test('switch templates without business API and create nodes',async({page})=>{
  await page.getByRole('button',{name:/주식 자동화/}).click();
  await expect(page.getByText('TradingView 이벤트')).toBeVisible();
  await page.getByRole('button',{name:/ProcureFlow/}).click();
  await expect(page.getByText('공고 조회 시작')).toBeVisible();
  await page.getByRole('button',{name:/Code/}).first().click();
  await expect(page.locator('.vue-flow__node')).toHaveCount(6);
  await expect(page.getByText(/Code 노드 추가/).first()).toBeVisible();
});
test('node inspector edit, JSON params, delete',async({page})=>{
  const node=page.locator('.vue-flow__node').first();
  await node.click();
  const title=page.getByRole('textbox',{name:'노드 이름'});
  await expect(title).toBeVisible();
  await title.fill('변경 테스트');
  await title.blur();
  const params=page.getByRole('textbox',{name:'노드 JSON 파라미터'});
  await params.fill('{"sample": true}');
  await page.getByRole('button',{name:'설정 적용'}).click();
  await expect(node.getByText('변경 테스트')).toBeVisible();
  await page.getByRole('button',{name:'선택 노드 삭제'}).click();
  await expect(page.locator('.vue-flow__node')).toHaveCount(4);
});
test('canvas left mouse drag pans viewport',async({page})=>{
  const pane=page.locator('.vue-flow__pane'),viewport=page.locator('.vue-flow__viewport');
  const rect=await pane.boundingBox();
  const before=await viewport.getAttribute('transform');
  const p={x:rect.x+rect.width*.55,y:rect.y+rect.height*.88};
  await page.mouse.move(p.x,p.y);await page.mouse.down();
  await page.mouse.move(p.x+150,p.y-65,{steps:10});await page.mouse.up();
  const after=await viewport.getAttribute('transform');
  expect(after).not.toBe(before);
});
test('node drag changes graph node position',async({page})=>{
  const node=page.locator('.vue-flow__node').first();
  const box=await node.boundingBox();
  await page.mouse.move(box.x+55,box.y+30);await page.mouse.down();
  await page.mouse.move(box.x+125,box.y+66,{steps:10});await page.mouse.up();
  const later=await node.boundingBox();
  expect(later.x-box.x).toBeGreaterThan(30);
});
test('zoom buttons and local browser save load',async({page})=>{
  const viewport=page.locator('.vue-flow__viewport');
  const before=await viewport.getAttribute('transform');
  await page.getByRole('button',{name:'확대',exact:true}).first().click();
  await expect.poll(()=>viewport.getAttribute('transform')).not.toBe(before);
  await page.getByRole('button',{name:'브라우저 저장'}).click();
  await expect(page.getByText(/이 브라우저에 저장했습니다/)).toBeVisible();
  await page.reload();
  await page.getByRole('button',{name:'브라우저 저장값 불러오기'}).click();
  await expect(page.locator('.vue-flow__node')).toHaveCount(5);
});
test('simulated execution is labeled and does not call business APIs',async({page})=>{
  const requests=[];
  page.on('request',r=>{if(/api\/v1|webhook|trading|procure/i.test(r.url()))requests.push(r.url());});
  await page.getByRole('button',{name:'모의 실행'}).click();
  await expect(page.getByText(/모의 실행 완료/).first()).toBeVisible({timeout:15000});
  expect(requests).toEqual([]);
});
