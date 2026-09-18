import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/browser', testMatch: 'stand.spec.mjs',
  timeout: 120000, expect: { timeout: 20000 }, workers: 1,
  outputDir: 'artifacts/stand-test-results',
  reporter: [['list'], ['html', { outputFolder: 'artifacts/stand-report', open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:8016', channel: 'chrome',
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
    viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: '.venv/bin/python tests/browser/stand_server.py', url: 'http://127.0.0.1:8016/stand/',
    reuseExistingServer: false, timeout: 30000, gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 } }
});
