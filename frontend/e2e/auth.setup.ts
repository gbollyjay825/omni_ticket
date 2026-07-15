import { expect, test as setup } from '@playwright/test'
import { mkdir } from 'node:fs/promises'

const authState = 'playwright/.auth/user.json'

setup('authenticate the local test operator once', async ({ page }) => {
  await mkdir('playwright/.auth', { recursive: true })
  await page.goto('/?screen=inbox', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('region', { name: 'Local development access' })).toBeVisible()
  await page.getByRole('button', { name: 'Sign in as local administrator' }).click()
  await expect(page.getByRole('heading', { name: 'All tickets' })).toBeVisible()
  await page.context().storageState({ path: authState })
})
