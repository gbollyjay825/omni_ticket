import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=automation', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('region', { name: 'Workflows workspace' })).toBeVisible()
})

test('Workflows matches the Freshdesk automation list hierarchy', async ({ page }, testInfo) => {
  const workspace = page.getByRole('region', { name: 'Workflows workspace' })
  await expect(workspace.getByRole('heading', { name: 'Automations' })).toBeVisible()
  await expect(workspace.getByRole('navigation', { name: 'Automation stages' })).toBeVisible()
  await expect(workspace.getByRole('button', { name: 'Ticket creation' })).toBeVisible()
  await expect(workspace.getByRole('button', { name: 'Ticket updates' })).toBeVisible()
  await expect(workspace.getByRole('button', { name: 'Hourly triggers' })).toBeVisible()
  await expect(workspace.getByRole('button', { name: 'New rule' })).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`workflows-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    workspaceWidth: document.querySelector('.workflows-workspace')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.workspaceWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})

test('Workflows create, edit, search, and activation controls call real APIs', async ({ page }, testInfo) => {
  const workspace = page.getByRole('region', { name: 'Workflows workspace' })
  const name = `Parity rule ${testInfo.project.name} ${Date.now()}`
  await workspace.getByRole('button', { name: 'New rule' }).click()
  const createForm = page.getByRole('form', { name: 'New automation rule' })
  await createForm.getByLabel('Rule name').fill(name)
  await createForm.getByLabel('When these conditions match').fill('Source is portal')
  await createForm.getByLabel('Perform these actions').fill('Assign to Customer Resolution')

  const created = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/automation-rules')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await createForm.getByRole('button', { name: 'Create rule' }).click()
  const rule = await (await created).json() as { id: string }
  await expect(workspace.getByRole('button', { name, exact: true })).toBeVisible()

  await workspace.getByRole('button', { name, exact: true }).click()
  const editForm = page.getByRole('form', { name: 'Edit automation rule' })
  const updatedName = `${name} updated`
  await editForm.getByLabel('Rule name').fill(updatedName)
  const updated = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/automation-rules/${rule.id}`)
      && response.request().method() === 'PATCH'
      && response.ok(),
  )
  await editForm.getByRole('button', { name: 'Save changes' }).click()
  await updated
  await expect(workspace.getByRole('button', { name: updatedName, exact: true })).toBeVisible()

  const toggle = workspace.getByRole('button', { name: `Pause ${updatedName}` })
  const toggled = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/automation-rules/${rule.id}`)
      && response.request().method() === 'PATCH'
      && response.ok(),
  )
  await toggle.click()
  await toggled
  await expect(workspace.getByRole('button', { name: `Activate ${updatedName}` })).toBeVisible()

  await workspace.getByLabel('Search automation rules').fill(updatedName)
  await expect(workspace.getByRole('button', { name: updatedName, exact: true })).toBeVisible()
})

test('Workflows has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.workflows-workspace')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
