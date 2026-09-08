import { expect, test } from '@playwright/test';

test('real local proxy enforces origin and replaces a supplied credential', async ({ request }) => {
  expect((await request.get('http://127.0.0.1:18765/api/session')).status()).toBe(401);
  expect((await request.get('/api/session', { headers: { 'X-Studio-Client': 'attacker-override' } })).status()).toBe(200);
  expect((await request.get('/api/session', { headers: { Origin: 'https://foreign.example' } })).status()).toBe(403);
  expect((await request.get('/api/session', { headers: { Host: 'foreign.example' } })).status()).toBe(403);
});

test('keyboard connect, tenant draft, inventory, and failed reconnect clear context', async ({ page }) => {
  await page.goto('/');
  const tenant = page.getByLabel('Tenant', { exact: true });
  await tenant.fill('tenant-a');
  await tenant.press('Tab');
  await expect(page.getByRole('button', { name: 'Connect', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Connected to tenant tenant-a', { exact: true })).toBeVisible();
  await tenant.fill('draft-tenant');
  await expect(page.getByText('Connected to tenant tenant-a', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Workspaces', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.getByRole('button', { name: 'Use workspace', exact: true }).click();
  await expect(page.getByText('Workspace: Fixture workspace', { exact: true })).toBeVisible();
  await tenant.fill('fail');
  await page.getByRole('button', { name: 'Connect', exact: true }).click();
  await expect(page.getByText('Workspace: Fixture workspace', { exact: true })).toHaveCount(0);
  await expect(page.getByText('OFFLINE', { exact: true })).toBeVisible();
  const storage = await page.evaluate(() => JSON.stringify(localStorage));
  expect(storage).not.toContain('synthetic-browser-credential');
  expect(page.url()).not.toContain('credential');
});

test('offline catalog visibly blocks execution', async ({ page }) => {
  await page.route('**/api/capabilities', route => route.abort());
  await page.goto('/');
  await expect(page.getByText('Catalog: fallback')).toBeVisible();
  await page.getByRole('button', { name: 'PowerShell Library', exact: true }).click();
  expect(await page.getByRole('button', { name: 'Plan / apply', exact: true }).count()).toBe(0);
  expect(await page.getByRole('button', { name: 'Open / run', exact: true }).count()).toBe(0);
});

test('guarded workflow applies once and exports the displayed read data', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Tenant', { exact: true }).fill('tenant-a');
  await page.getByRole('button', { name: 'Connect', exact: true }).click();
  await expect(page.getByText('Connected to tenant tenant-a', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Workspaces', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.getByRole('button', { name: 'Use workspace', exact: true }).click();
  await page.getByRole('button', { name: 'Run read-only', exact: true }).click();
  const jsonDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download JSON', exact: true }).click();
  const json = await jsonDownload;
  const jsonStream = await json.createReadStream();
  let content = ''; for await (const chunk of jsonStream!) content += chunk.toString();
  expect(JSON.parse(content).data[0].description).toBe('=1+1,\n"quoted"');
  const csvDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download CSV', exact: true }).click();
  const csv = await csvDownload;
  const csvStream = await csv.createReadStream();
  content = ''; for await (const chunk of csvStream!) content += chunk.toString();
  expect(content).toContain('"\'=1+1,\n""quoted"""');
  expect(csv.suggestedFilename()).toMatch(/^[A-Za-z0-9._-]+\.csv$/);
  await page.getByLabel('WorkspaceName *', { exact: true }).fill('Fixture workspace');
  await page.getByRole('button', { name: 'Create guarded plan', exact: true }).click();
  await page.getByRole('button', { name: 'Validate with -WhatIf', exact: true }).click();
  const confirmation = page.getByLabel(/^Type APPLY .* to apply$/);
  const label = await page.locator('label').filter({ hasText: /^Type APPLY .* to apply$/ }).innerText();
  await confirmation.fill(label.replace(/^Type /, '').replace(/ to apply$/, ''));
  let applies = 0;
  page.on('request', req => { if (/\/api\/mutations\/[^/]+\/execute$/.test(req.url())) applies++; });
  await page.getByRole('button', { name: 'Apply guarded write', exact: true }).dblclick();
  await expect(page.getByText('Applied and verified against the requested workspace fields.', { exact: true })).toBeVisible();
  expect(applies).toBe(1);
  await expect(page.getByRole('button', { name: 'Apply guarded write', exact: true })).toBeDisabled();
  await page.screenshot({ path: 'test-results/guarded-workflow.png', fullPage: true });
});
