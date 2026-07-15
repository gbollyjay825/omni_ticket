import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=forums', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('region', { name: 'Forums workspace' })).toBeVisible()
})

test('Forums matches the Freshdesk activity and category hierarchy', async ({ page }, testInfo) => {
  const workspace = page.getByRole('region', { name: 'Forums workspace' })
  await expect(workspace.getByRole('complementary', { name: 'Forum views and categories' })).toBeVisible()
  await expect(workspace.getByRole('navigation', { name: 'Forum views' })).toBeVisible()
  await expect(workspace.getByRole('tab', { name: 'All Activity' })).toBeVisible()
  await expect(workspace.getByRole('button', { name: 'New topic' })).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`forums-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    workspaceWidth: document.querySelector('.forums-workspace')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.workspaceWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})

test('Forums topic, moderation, and reply controls call real APIs', async ({ page }, testInfo) => {
  const workspace = page.getByRole('region', { name: 'Forums workspace' })
  const title = `Parity forum topic ${testInfo.project.name} ${Date.now()}`
  await workspace.getByRole('button', { name: 'New topic' }).click()
  const form = page.getByRole('form', { name: 'New forum topic' })
  await form.getByLabel('Title').fill(title)
  await form.getByLabel('Category').fill('Parity checks')
  await form.getByLabel('Description').fill('A real forum topic created by the parity workflow test.')
  const created = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/forums/topics')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await form.getByRole('button', { name: 'Create topic' }).click()
  await created

  const topicRow = workspace.locator('.forum-activity-list article').filter({ hasText: title })
  const topicButton = topicRow.locator('button:not(.icon-button)')
  await expect(topicButton).toBeVisible()
  await topicButton.click()
  await expect(workspace.getByRole('heading', { name: title })).toBeVisible()

  const status = workspace.getByLabel('Status')
  const nextStatus = await status.inputValue() === 'pending' ? 'closed' : 'pending'
  const moderated = page.waitForResponse((response) =>
    response.url().includes('/api/v1/forums/topics/')
      && response.request().method() === 'PATCH'
      && response.ok(),
  )
  await status.selectOption(nextStatus)
  await moderated
  await expect(status).toHaveValue(nextStatus)

  const reply = `Forum reply ${testInfo.project.name} ${Date.now()}`
  await workspace.getByLabel('Reply to topic').fill(reply)
  const posted = page.waitForResponse((response) =>
    response.url().includes('/api/v1/forums/topics/')
      && response.url().endsWith('/comments')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await workspace.getByRole('button', { name: 'Post reply' }).click()
  await posted
  await expect(workspace.getByText(reply, { exact: true })).toBeVisible()
})

test('Forums has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.forums-workspace')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
