import {defineConfig,devices} from '@playwright/test';
export default defineConfig({
  testDir:'./tests',
  timeout:30000,
  retries:process.env.CI?1:0,
  use:{baseURL:'http://127.0.0.1:5173',trace:'retain-on-failure',screenshot:'only-on-failure',...devices['Desktop Chrome']},
  webServer:{command:'npm run dev -- --host 127.0.0.1 --port 5173',url:'http://127.0.0.1:5173',reuseExistingServer:!process.env.CI,timeout:60000},
  reporter:process.env.CI?[['list'],['html',{open:'never'}]]:'list'
});
