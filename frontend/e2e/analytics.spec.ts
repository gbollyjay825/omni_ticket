import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=analytics', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('region', { name: 'Analytics report library' })).toBeVisible()
})

test('Analytics matches the Freshdesk report library hierarchy', async ({ page }, testInfo) => {
  const library = page.getByRole('region', { name: 'Analytics report library' })
  await expect(library.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible()
  await expect(library.getByRole('complementary', { name: 'Report views' })).toBeVisible()
  await expect(library.getByRole('button', { name: 'All reports' })).toBeVisible()
  await expect(library.getByLabel('All analytics reports')).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`analytics-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    libraryWidth: document.querySelector('.analytics-library-shell')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.libraryWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})

test('Analytics report search, sort, export, and saved views are functional', async ({ page }) => {
  const library = page.getByRole('region', { name: 'Analytics report library' })
  await library.getByLabel('Search reports').fill('Customer satisfaction')
  await expect(library.getByRole('link', { name: 'Customer satisfaction' })).toBeVisible()
  await expect(library.getByRole('link', { name: 'Ticket operations' })).toHaveCount(0)

  await library.getByLabel('Search reports').fill('')
  await library.getByLabel('Sort reports').selectOption('name')
  const reportNames = await library.locator('.analytics-report-list article a').allTextContents()
  expect(reportNames).toEqual([...reportNames].sort((left, right) => left.localeCompare(right)))

  const download = page.waitForEvent('download')
  await library.getByRole('button', { name: 'Export Ticket operations' }).click()
  const artifact = await download
  expect(artifact.suggestedFilename()).toContain('ticket')

  await library.getByRole('button', { name: 'My reports' }).click()
  await expect(library.getByRole('heading', { name: 'My reports' })).toBeVisible()
  await library.getByRole('button', { name: 'Scheduled reports' }).click()
  await expect(library.getByRole('heading', { name: 'Scheduled reports' })).toBeVisible()
})

test('Analytics has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.analytics-library-panel')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
