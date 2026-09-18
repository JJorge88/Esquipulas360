import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  testMatch: 'editor.spec.mjs',
  timeout: 60000,
  expect: { timeout: 15000 },
  workers: 1,
  outputDir: 'artifacts/editor-test-results',
  reporter: [['list'], ['html', { outputFolder: 'artifacts/editor-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8013', channel: 'chrome',
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
    viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure', trace: 'retain-on-failure'
  },
  webServer: {
    command: '.venv/bin/python tests/browser/editor_server.py',
    url: 'http://127.0.0.1:8013/admin/login/', reuseExistingServer: false, timeout: 30000,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 }
  }
});
