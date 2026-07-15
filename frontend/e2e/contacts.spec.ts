import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=customers', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('contact-list-workspace')).toBeVisible()
})

test('Contacts matches the directory and record workflow at every viewport', async ({ page }, testInfo) => {
  const directory = page.getByTestId('contact-list-workspace')
  await expect(directory.getByText('All contacts', { exact: true })).toBeVisible()
  await expect(directory.getByPlaceholder('Search all contacts')).toBeVisible()
  await expect(directory.getByRole('columnheader', { name: 'Contact' })).toBeVisible()
  await expect(directory.getByRole('columnheader', { name: 'Company' })).toBeVisible()
  await expect(directory.getByRole('columnheader', { name: 'Email address' })).toBeVisible()
  await expect(directory.locator('.contact-filter-panel')).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`contact-directory-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const workspaceResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/customers/cust-sofia') && response.ok(),
  )
  await directory.getByRole('link', { name: 'Sofia Grant' }).click()
  await workspaceResponse

  const record = page.getByTestId('contact-detail-workspace')
  await expect(record).toBeVisible()
  await expect(record.getByRole('heading', { name: 'Sofia Grant' })).toBeVisible()
  await expect(record.getByRole('button', { name: 'Edit' })).toBeVisible()
  await expect(record.getByRole('button', { name: 'Merge' })).toBeVisible()
  await expect(record.getByRole('tab', { name: 'Timeline' })).toHaveAttribute('aria-selected', 'true')
  await expect(record.getByText('Contact info', { exact: true })).toBeVisible()

  await record.getByRole('tab', { name: 'Tickets' }).click()
  await expect(record.getByText('Booking confirmation not received by email')).toBeVisible()
  await record.getByRole('tab', { name: 'Notes' }).click()
  await expect(record.getByRole('tabpanel')).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`contact-record-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    workspaceWidth: document.querySelector('.contact-detail-shell')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.workspaceWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})

test('Contacts exposes real filters and action dialogs', async ({ page }) => {
  const directory = page.getByTestId('contact-list-workspace')
  await directory.getByLabel('Tags').fill('delivery-risk')
  const filtered = page.waitForResponse((response) =>
    response.url().includes('/api/v1/customers?')
      && response.url().includes('tag=delivery-risk')
      && response.ok(),
  )
  await directory.getByRole('button', { name: 'Apply' }).click()
  await filtered
  await expect(directory.getByRole('link', { name: 'Sofia Grant' })).toBeVisible()
  await expect(directory.getByRole('link', { name: 'Leo Ahmed' })).toBeHidden()

  await directory.getByRole('link', { name: 'Sofia Grant' }).click()
  const record = page.getByTestId('contact-detail-workspace')
  await record.getByRole('button', { name: 'Edit' }).click()
  await expect(page.getByRole('form', { name: 'Edit contact' })).toBeVisible()
  await page.getByRole('button', { name: 'Close edit contact' }).click()
  await record.getByRole('button', { name: 'Merge' }).click()
  await expect(page.getByRole('form', { name: 'Merge contact' })).toBeVisible()
  await page.getByRole('button', { name: 'Close merge contact' }).click()
})

test('Contacts has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.contact-list-shell')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
