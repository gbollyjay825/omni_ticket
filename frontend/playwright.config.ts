import { defineConfig, devices } from '@playwright/test'

const authState = 'playwright/.auth/user.json'

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'cd ../backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/, use: { ...devices['Desktop Chrome'] } },
    {
      name: 'desktop-1440',
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], storageState: authState, viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'desktop-1280',
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], storageState: authState, viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'tablet',
      dependencies: ['setup'],
      use: { ...devices['iPad (gen 7)'], browserName: 'chromium', storageState: authState },
    },
    {
      name: 'mobile',
      dependencies: ['setup'],
      use: { ...devices['iPhone 13'], browserName: 'chromium', storageState: authState },
    },
  ],
})
