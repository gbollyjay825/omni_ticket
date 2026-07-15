import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('Dashboard renders source-backed metrics and applies server filters', async ({ page }, testInfo) => {
  const initialSummary = page.waitForResponse((response) =>
    response.url().includes('/api/v1/analytics/summary') && response.request().method() === 'GET',
  )
  await page.goto('/?screen=command', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Omnichannel Dashboard' })).toBeVisible()

  const response = await initialSummary
  expect(response.ok()).toBeTruthy()
  const summary = await response.json() as { ticket_trends: { open: number } }
  const ticketTrends = page.locator('.desk-widget').filter({ hasText: 'Ticket trends' })
  await expect(ticketTrends.getByRole('button', { name: new RegExp(`Open\\s+${summary.ticket_trends.open}$`) })).toBeVisible()

  const filteredSummary = page.waitForResponse((nextResponse) =>
    nextResponse.url().includes('/api/v1/analytics/summary') && nextResponse.url().includes('range=7d'),
  )
  await page.getByRole('combobox', { name: 'Dashboard period' }).selectOption('7d')
  expect((await filteredSummary).ok()).toBeTruthy()

  await page.screenshot({
    path: testInfo.outputPath(`dashboard-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  await ticketTrends.getByRole('button', { name: /^Open/ }).click()
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()
})

test('Dashboard has no serious accessibility or overflow violations', async ({ page }) => {
  await page.goto('/?screen=command', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Omnichannel Dashboard' })).toBeVisible()

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    mainWidth: document.querySelector('.main-shell')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.mainWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)

  const results = await new AxeBuilder({ page })
    .include('.app-shell')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()
  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
