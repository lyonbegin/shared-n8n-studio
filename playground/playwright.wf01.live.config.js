import {defineConfig,devices} from '@playwright/test';
export default defineConfig({
  testDir:'./tests',
  testMatch:['wf01-live-sqlite.spec.js','wf01-detailed-editor.spec.js'],
  timeout:60000,
  expect:{timeout:15000},
  retries:1,
  use:{...devices['Desktop Chrome'],trace:'retain-on-failure',screenshot:'only-on-failure'},
  reporter:[['list'],['html',{open:'never',outputFolder:'playwright-report/wf01'}]],
});
