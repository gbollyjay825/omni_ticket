import { expect, test } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] } })

test('local development access signs in and persists the admin session', async ({ page }) => {
  await page.goto('/?screen=inbox', { waitUntil: 'domcontentloaded' })

  const access = page.getByRole('region', { name: 'Local development access' })
  await expect(access).toBeVisible()
  await expect(access).toContainText('gbolahan@omniticket.example.com')
  await expect(access).toContainText('omni-demo')

  await access.getByRole('button', { name: 'Sign in as local administrator' }).click()
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()

  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})
