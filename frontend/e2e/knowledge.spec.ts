import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=knowledge', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Knowledge base (Wakanow)' })).toBeVisible()
})

test('Solutions uses the extracted API-backed catalog at every viewport', async ({ page }, testInfo) => {
  await expect(page.getByRole('region', { name: 'Knowledge categories' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'New article' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Manage' })).toBeEnabled()
  await expect(page.getByRole('link', { name: 'View support portal' })).toHaveAttribute('href', /screen=portal/)

  await page.screenshot({
    path: testInfo.outputPath(`knowledge-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    shellWidth: document.querySelector('.knowledge-shell')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.shellWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})

test('Solutions has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.knowledge-shell')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
