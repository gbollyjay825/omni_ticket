import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=channels', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Team Inbox' })).toBeVisible()
})

test('Omnichat workflow is API-backed and responsive', async ({ page }, testInfo) => {
  const viewport = page.viewportSize()
  expect(viewport).not.toBeNull()

  await expect(page.getByText('Date change for Lagos to London booking').first()).toBeVisible()

  if (viewport!.width <= 800) {
    await page.getByText('Date change for Lagos to London booking').first().click()
    await expect(page.getByRole('main', { name: 'Active conversation' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Back to queue' })).toBeVisible()
    await page.getByRole('button', { name: 'Customer context' }).click()
    await expect(page.getByRole('complementary', { name: 'Customer context' })).toBeVisible()
    await page.getByRole('button', { name: 'Back to conversation' }).click()
  } else {
    await expect(page.getByRole('main', { name: 'Active conversation' })).toBeVisible()
  }

  await page.screenshot({
    path: testInfo.outputPath(`omnichat-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    shellWidth: document.querySelector('.omnichat-shell')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.shellWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)

  if (viewport!.width > 1180) {
    const layout = await page.locator('.omnichat-shell').evaluate(() => {
      const names = ['.omnichat-rail', '.omnichat-queue', '.omnichat-thread', '.omnichat-context']
      return names.map((selector) => {
        const rect = document.querySelector(selector)!.getBoundingClientRect()
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }
      })
    })
    for (let index = 1; index < layout.length; index += 1) {
      expect(layout[index - 1].right).toBeLessThanOrEqual(layout[index].left + 1)
    }
    for (const rect of layout) {
      expect(rect.top).toBeGreaterThanOrEqual(0)
      expect(rect.bottom).toBeLessThanOrEqual(viewport!.height + 1)
    }
  }
})

test('Omnichat has no serious accessibility violations', async ({ page }) => {
  if (page.viewportSize()!.width <= 800) {
    await page.getByText('Date change for Lagos to London booking').first().click()
  }
  const results = await new AxeBuilder({ page })
    .include('.omnichat-shell')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
