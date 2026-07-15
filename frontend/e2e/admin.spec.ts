import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=admin', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Admin', exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Setup tools' })).toBeVisible()
})

test('Admin tools open focused API-backed settings rather than stacked panels', async ({ page }, testInfo) => {
  await expect(page.getByRole('button', { name: 'Agents', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Email', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Provider credentials' })).toBeEnabled()

  await page.getByRole('button', { name: 'Agents', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Agents' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'All tools' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Users, roles, and markets' })).toBeVisible()

  await page.getByRole('button', { name: 'All tools' }).click()
  await page.getByRole('button', { name: 'Email', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Email' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Mailbox intake and replies' })).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`admin-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    mainWidth: document.querySelector('.main-shell')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.mainWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})

test('Admin has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.app-shell')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
