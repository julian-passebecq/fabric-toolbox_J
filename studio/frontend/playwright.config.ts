import { defineConfig } from '@playwright/test';
import path from 'node:path';

const python = process.env.STUDIO_TEST_PYTHON || path.resolve('../backend/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const env = { STUDIO_CLIENT_TOKEN: 'synthetic-browser-credential', STUDIO_API_PORT: '18765', STUDIO_UI_PORT: '15173' };
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 45000,
  use: { baseURL: 'http://127.0.0.1:15173', screenshot: 'only-on-failure' },
  webServer: [
    { command: `"${python}" ../scripts/fixture_server.py`, url: 'http://127.0.0.1:18765/api/health', env, reuseExistingServer: false },
    { command: 'npm run dev', url: 'http://127.0.0.1:15173', env, reuseExistingServer: false },
  ],
});
