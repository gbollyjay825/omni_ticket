import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/?screen=workforce', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('region', { name: 'Scheduling workspace' })).toBeVisible()
})

test('Scheduling matches the service-task and technician timeline workflow', async ({ page }, testInfo) => {
  const workspace = page.getByRole('region', { name: 'Scheduling workspace' })
  await expect(workspace.getByRole('complementary', { name: 'Service tasks' })).toBeVisible()
  await expect(workspace.getByText('Field Technicians', { exact: true })).toBeVisible()
  await expect(workspace.getByRole('button', { name: 'Today' })).toBeVisible()
  await expect(workspace.getByRole('button', { name: 'New service task' })).toBeVisible()
  await expect(workspace.locator('.technician-row').first()).toBeVisible()

  await page.screenshot({
    path: testInfo.outputPath(`scheduling-${testInfo.project.name}.png`),
    animations: 'disabled',
  })

  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
    workspaceWidth: document.querySelector('.scheduling-workspace')!.scrollWidth,
  }))
  expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  expect(overflow.workspaceWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1)
})

test('Scheduling create and edit controls call real APIs', async ({ page }, testInfo) => {
  const workspace = page.getByRole('region', { name: 'Scheduling workspace' })
  const title = `Parity service task ${testInfo.project.name} ${Date.now()}`
  await workspace.getByRole('button', { name: 'New service task' }).click()
  const createForm = page.getByRole('form', { name: 'New service task' })
  await createForm.getByLabel('Task title').fill(title)
  await createForm.getByLabel('Customer').selectOption('cust-sofia')
  await createForm.getByLabel('Technician').selectOption('agent-amara')
  await createForm.getByLabel('Location').fill('Lagos service desk')

  const created = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/service-appointments')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await createForm.getByRole('button', { name: 'Create service task' }).click()
  const createdAppointment = await (await created).json() as { id: string }
  await expect(workspace.getByRole('heading', { name: new RegExp(title) })).toBeVisible()

  await workspace.getByRole('button', { name: `Edit ${title}` }).click()
  const editForm = page.getByRole('form', { name: 'Edit service task' })
  await editForm.getByLabel('Status').selectOption('in_progress')
  const updated = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/service-appointments/${createdAppointment.id}`)
      && response.request().method() === 'PATCH'
      && response.ok(),
  )
  await editForm.getByRole('button', { name: 'Save changes' }).click()
  await updated
  const taskCard = workspace.getByRole('article').filter({ hasText: title })
  await expect(taskCard.getByText('In Progress', { exact: true })).toBeVisible()
})

test('Scheduling has no serious accessibility violations', async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include('.scheduling-workspace')
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  const serious = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious',
  )
  expect(serious).toEqual([])
})
