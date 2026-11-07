import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end test against the real stack: the API (E2E_API_URL, default :8000) must be
 * running with the seeded sites. The front end is built and served by `vite preview`.
 */
const API = process.env.E2E_API_URL ?? 'http://localhost:8000';
const PORT = 4173;

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'phone-380',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 380, height: 800 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: {
    command: `npm run build && npx vite preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { VITE_API_URL: API },
  },
});
