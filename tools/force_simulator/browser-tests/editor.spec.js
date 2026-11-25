const { test, expect } = require('@playwright/test');

test('navigates the three generated pages', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('READY');
  for (const name of ['BROWSE', 'EDIT', 'MIX']) {
    const tab = page.getByRole('button', { name });
    await tab.click();
    await expect(tab).toHaveClass(/active/);
  }
});

test('selects Hall and Room and refreshes the shared EDIT Q-Link values', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('READY');
  await page.locator('#effect').selectOption('1');
  await expect(page.locator('#effectName')).toContainText('HALL REVERB');
  await page.getByRole('button', { name: 'EDIT' }).click();
  await expect(page.locator('.qlink[data-q="3"] .qvalue')).toContainText('DECAY TIME');

  await page.locator('#effect').selectOption('3');
  await expect(page.locator('#effectName')).toContainText('ROOM REVERB');
  await expect(page.locator('.qlink[data-q="1"] .qvalue')).toContainText('DECAY TIME');
  await expect(page.locator('.qlink[data-q="2"] .qvalue')).toContainText('DIFFUSION');
});

async function dragDial(page, q) {
  const dial = page.locator(`.qlink[data-q="${q}"] .dial`);
  await expect(dial).toBeVisible();
  await dial.scrollIntoViewIfNeeded();
  const box = await dial.boundingBox();
  if (!box) throw new Error(`Q${q} dial is not visible`);
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y - 58, { steps: 6 });
  await page.mouse.up();
}

test('mouse Q-Link drag edits Hall Q3 through the VST trace', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('READY');
  await page.locator('#effect').selectOption('1');
  await page.getByRole('button', { name: 'EDIT' }).click();
  await expect(page.locator('.qlink[data-q="3"] .qvalue')).toContainText('DECAY TIME');
  await dragDial(page, 3);
  await expect(page.locator('.event').first()).toContainText('EDIT / Q3');
  await expect(page.locator('.event').first()).toContainText('decay_time');
  await expect(page.locator('.event').first()).toContainText('DSP GROUP');
});

test('mouse Q-Link drag edits Room Q1 through the VST trace', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('READY');
  await page.locator('#effect').selectOption('3');
  await page.getByRole('button', { name: 'EDIT' }).click();
  await expect(page.locator('.qlink[data-q="1"] .qvalue')).toContainText('DECAY TIME');
  await dragDial(page, 1);
  await expect(page.locator('.event').first()).toContainText('EDIT / Q1');
  await expect(page.locator('.event').first()).toContainText('decay_time');
  await expect(page.locator('.event').first()).toContainText('DSP GROUP');
});
