import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=inbox', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()
})

test('Tickets queue and detail use the extracted workspace at every viewport', async ({ page }, testInfo) => {
  await expect(page.locator('.ticket-row').first()).toBeVisible()
  if (page.viewportSize()!.width <= 900) {
    await expect(page.getByRole('complementary', { name: 'Ticket filters' })).toBeHidden()
    await page.getByRole('button', { name: /^Filters/ }).click()
    await expect(page.getByRole('complementary', { name: 'Ticket filters' })).toBeVisible()
    await page.getByRole('button', { name: 'Close filters' }).click()
  } else {
    await expect(page.getByRole('complementary', { name: 'Ticket filters' })).toBeVisible()
  }

  await page.screenshot({
    path: testInfo.outputPath(`ticket-queue-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const firstTicket = page.locator('.ticket-row-main').first()
  await firstTicket.click()

  await expect(page.getByRole('main', { name: 'Ticket detail' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Ticket commands' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Ticket conversation' })).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`tickets-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    shellWidth: document.querySelector('.ticket-workspace-shell')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.shellWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)

  await page.getByRole('button', { name: 'Back to tickets' }).click()
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()
})

test('Tickets workspace has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.ticket-workspace-shell')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})

test('Ticket filters can be persisted and reapplied as a saved view', async ({ page }, testInfo) => {
  if (page.viewportSize()!.width <= 900) {
    await page.getByRole('button', { name: /^Filters/ }).click()
  }

  const filters = page.getByRole('complementary', { name: 'Ticket filters' })
  await filters.getByLabel('Priority').selectOption('high')
  await filters.getByLabel('Created').selectOption('7d')
  if (page.viewportSize()!.width <= 900) {
    await filters.getByRole('button', { name: 'Close filters' }).click()
  }

  const name = `High priority ${testInfo.project.name} ${Date.now()}`
  await page.getByRole('button', { name: 'Save current view' }).click()
  await page.getByLabel('View name').fill(name)

  const saved = page.waitForResponse((response) =>
    response.url().includes('/api/v1/ticket-views')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await page.getByRole('button', { name: 'Save view' }).click()
  const response = await saved
  const view = await response.json() as { id: string }

  await expect(page.getByRole('status')).toContainText(`Saved view “${name}” created.`)
  await expect(page.getByRole('combobox', { name: 'Saved ticket view' })).toHaveValue(view.id)

  await expect.poll(async () => {
    const requests = await page.evaluate(() => performance.getEntriesByType('resource').map((entry) => entry.name))
    return requests.some((url) => url.includes('/api/v1/tickets?') && url.includes(`view_id=${view.id}`))
  }).toBe(true)
})
