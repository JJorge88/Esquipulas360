import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser', testMatch: 'panel.spec.mjs',
  timeout: 90000, expect: { timeout: 15000 }, workers: 1,
  outputDir: 'artifacts/panel-test-results',
  reporter: [['list'], ['html', { outputFolder: 'artifacts/panel-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8014', channel: 'chrome',
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
    viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure', trace: 'retain-on-failure'
  },
  webServer: {
    command: '.venv/bin/python tests/browser/panel_server.py',
    url: 'http://127.0.0.1:8014/panel/ingresar/', reuseExistingServer: false, timeout: 30000,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 }
  }
});
