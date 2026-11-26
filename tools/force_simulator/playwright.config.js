const { defineConfig } = require('@playwright/test');
const path = require('path');

const simulatorDir = __dirname;
const assets = process.env.TROLLFX_FACTORY_PACKAGES_DIR || path.join(process.env.HOME, 'asr10-force-assets-v1');
const port = process.env.TROLLFX_SIM_PORT || '8765';

module.exports = defineConfig({
  testDir: path.join(simulatorDir, 'browser-tests'),
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: { baseURL: `http://127.0.0.1:${port}`, headless: true, viewport: { width: 1600, height: 1100 } },
  reporter: [['list'], ['json', { outputFile: path.join(simulatorDir, 'test-results', 'playwright-report.json') }]],
  outputDir: path.join(simulatorDir, 'test-results', 'artifacts'),
  webServer: {
    command: `python3 launch.py --host 127.0.0.1 --port ${port} --assets "${assets}"`,
    cwd: simulatorDir,
    url: `http://127.0.0.1:${port}/api/state`,
    reuseExistingServer: process.env.TROLLFX_SIM_REUSE_SERVER === '1',
    timeout: 120_000,
    env: { ...process.env, TROLLFX_FACTORY_PACKAGES_DIR: assets },
  },
});
