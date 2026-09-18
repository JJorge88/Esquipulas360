import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  timeout: 45000,
  expect: { timeout: 15000 },
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.TEST_BASE_URL || 'http://127.0.0.1:8000',
    channel: 'chrome',
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure'
  },
  webServer: {
    command: '.venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload',
    url: 'http://127.0.0.1:8000',
    reuseExistingServer: true,
    timeout: 15000
  }
});
