import { expect, test } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] }, serviceWorkers: 'block' })

test('administrator access signs in and persists the session', async ({ page }) => {
  await page.goto('/?screen=inbox', { waitUntil: 'domcontentloaded' })

  const access = page.getByRole('region', { name: 'Local development access' })
  if (await access.isVisible()) {
    await expect(access).toContainText('gbolahan@omniticket.example.com')
    await expect(access).toContainText('omni-demo')
    await access.getByRole('button', { name: 'Sign in as local administrator' }).click()
  } else {
    await page.getByLabel('Email').fill('gbolahan@omniticket.example.com')
    await page.getByLabel('Password').fill('omni-demo')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  }
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()

  await page.route('**/api/v1/auth/browser/session', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500))
    await route.continue()
  })
  await page.reload({ waitUntil: 'commit' })
  await expect(page.getByRole('heading', { name: 'Restoring secure session' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Sign in to your market workspace' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})
