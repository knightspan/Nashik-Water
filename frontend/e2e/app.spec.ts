import { expect, test } from '@playwright/test';

test('map shows 7 sites, a site page shows charts', async ({ page }) => {
  await page.goto('/');

  // 7 coloured circle markers on the Leaflet map.
  await expect(page.locator('path.site-marker')).toHaveCount(7);
  // ...and 7 site cards with text verdicts below it.
  await expect(page.getByTestId('site-card')).toHaveCount(7);
  await expect(page.getByText('Simulated').first()).toBeVisible();

  // Open a simulated site (has back-filled history from the simulator).
  await page.getByTestId('site-card').filter({ hasText: 'Tapovan' }).click();
  await expect(page).toHaveURL(/\/site\/tapovan$/);
  await expect(page.getByTestId('status-card')).toBeVisible();
  await expect(page.getByTestId('chart-wqi')).toBeVisible();
  await expect(page.locator('[data-testid="chart-wqi"] .recharts-line-curve')).toHaveCount(1);
  await expect(page.locator('.recharts-line-curve')).toHaveCount(5);

  // 7-day view switches to 15-minute averages.
  await page.getByRole('button', { name: '7 days' }).click();
  await expect(page.getByText('15-minute averages')).toBeVisible();
});

test('works in Marathi and dark mode without horizontal scroll', async ({ page }) => {
  await page.goto('/about');
  await page.getByTestId('lang-switch').click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('माहितीविषयी');
  await expect(page.getByTestId('limitations')).toContainText('नदीचे पाणी थेट पिण्यासाठी नाही.');
  await page.getByTestId('theme-toggle').click();
  await expect(page.locator('html')).toHaveClass(/dark/);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
});
