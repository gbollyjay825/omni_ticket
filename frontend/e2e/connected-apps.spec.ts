import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const routes = [
  ['ai-agents', 'AI Agents and Chatbots workspace'],
  ['campaigns', 'Proactive campaigns workspace'],
  ['custom-objects', 'Custom Objects workspace'],
] as const

test('tenant-connected apps match the Freshdesk route hierarchy without overflow', async ({ page }, testInfo) => {
  for (const [screen, regionName] of routes) {
    await page.goto(`/?screen=${screen}`, { waitUntil: 'domcontentloaded' })
    const workspace = page.getByRole('region', { name: regionName })
    await expect(workspace).toBeVisible()
    const overflow = await page.evaluate(() => ({
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
    }))
    expect(overflow.documentWidth, `${screen} document width`).toBeLessThanOrEqual(overflow.viewportWidth + 1)
    await page.screenshot({
      path: testInfo.outputPath(`${screen}-${testInfo.project.name}.png`),
      animations: 'disabled',
    })
  }
})

test('AI agent lifecycle uses the production API contract', async ({ page }, testInfo) => {
  await page.goto('/?screen=ai-agents', { waitUntil: 'domcontentloaded' })
  const workspace = page.getByRole('region', { name: 'AI Agents and Chatbots workspace' })
  const name = `Parity agent ${testInfo.project.name} ${Date.now()}`
  await workspace.getByRole('button', { name: 'New AI agent' }).click()
  await workspace.getByLabel('Name').fill(name)
  await workspace.getByLabel('Instructions').fill('Answer booking questions and hand complex work to an operator for review.')
  const created = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/ai/agents')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await workspace.getByRole('button', { name: 'Save draft' }).click()
  await created
  await expect(workspace.getByText(name, { exact: true })).toBeVisible()

  const decisions = page.waitForResponse((response) =>
    response.url().includes('/api/v1/ai/decisions')
      && response.request().method() === 'GET'
      && response.ok(),
  )
  await workspace.getByRole('tab', { name: 'Decision log' }).click()
  await decisions
})

test('campaign drafts use the consent-aware campaign API', async ({ page }, testInfo) => {
  await page.goto('/?screen=campaigns', { waitUntil: 'domcontentloaded' })
  const workspace = page.getByRole('region', { name: 'Proactive campaigns workspace' })
  const name = `Parity campaign ${testInfo.project.name} ${Date.now()}`
  await workspace.getByRole('button', { name: 'New campaign' }).click()
  await workspace.getByLabel('Name').fill(name)
  await workspace.getByLabel('Include all addressable contacts').check()
  await workspace.getByRole('textbox', { name: 'Message', exact: true }).fill('Your booking update is available in your Wakanow account.')
  const created = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/campaigns')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await workspace.getByRole('button', { name: 'Save draft' }).click()
  await created
  await expect(workspace.getByText(name, { exact: true })).toBeVisible()
})

test('custom-object creation and schema updates use real APIs', async ({ page }, testInfo) => {
  await page.goto('/?screen=custom-objects', { waitUntil: 'domcontentloaded' })
  const workspace = page.getByRole('region', { name: 'Custom Objects workspace' })
  const suffix = `${testInfo.project.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${Date.now()}`
  const name = `Parity orders ${testInfo.project.name} ${Date.now()}`
  await workspace.getByRole('button', { name: 'New object' }).click()
  const form = page.getByRole('form', { name: 'New custom object' })
  await form.getByLabel('Name').fill(name)
  await form.getByLabel('Key').fill(`parity_${suffix}`.slice(0, 63))
  await form.getByLabel('Description').fill('Order details used by parity workflow tests.')
  const created = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/custom-objects')
      && response.request().method() === 'POST'
      && response.ok(),
  )
  await form.getByRole('button', { name: 'Create object' }).click()
  await created
  await workspace.getByRole('combobox', { name: 'Custom object' }).selectOption({ label: name })
  await workspace.getByRole('button', { name: 'Text', exact: true }).click()
  const updated = page.waitForResponse((response) =>
    response.url().includes('/api/v1/custom-objects/')
      && response.request().method() === 'PATCH'
      && response.ok(),
  )
  await workspace.getByRole('button', { name: 'Save schema' }).click()
  await updated
  await expect(workspace.getByText('Custom object schema saved.')).toBeVisible()
})

test('tenant-connected app workspaces have no serious accessibility violations', async ({ page }) => {
  for (const [screen] of routes) {
    await page.goto(`/?screen=${screen}`, { waitUntil: 'domcontentloaded' })
    const selector = screen === 'ai-agents'
      ? '.connected-workspace'
      : screen === 'campaigns'
        ? '.connected-workspace'
        : '.custom-objects-workspace'
    await expect(page.locator(selector)).toBeVisible()
    const results = await new AxeBuilder({ page })
      .include(selector)
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    const serious = results.violations.filter(
      (violation) => violation.impact === 'critical' || violation.impact === 'serious',
    )
    expect(serious, `${screen} accessibility`).toEqual([])
  }
})
