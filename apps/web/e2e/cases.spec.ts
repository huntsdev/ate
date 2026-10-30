import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { execFile } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'

const artifacts = new URL('../../../artifacts/', import.meta.url)
const restartScript = fileURLToPath(
  new URL('../../../scripts/stack.ps1', import.meta.url),
)

async function choose(page: Page, label: string, option: string) {
  await page.getByRole('combobox', { name: label, exact: true }).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}

async function accessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  expect(result.violations).toEqual([])
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
}

async function status(
  page: Page,
  next: string,
  reason: string,
  disposition?: string,
) {
  await page.getByRole('button', { name: 'Change status', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Change case status' })
  await choose(page, 'Next status', next)
  if (disposition) await choose(page, 'Analyst disposition', disposition)
  await dialog.getByLabel('Decision rationale').fill(reason)
  await dialog.getByRole('button', { name: 'Confirm status change' }).click()
  await expect(dialog).toBeHidden()
}

test('analyst workflow survives a real stack restart', async ({
  page,
  baseURL,
}, testInfo) => {
  test.skip(
    process.env.ATE_LIVE_ALLOW_RESTART !== '1',
    'Set ATE_LIVE_ALLOW_RESTART=1 only for the disposable/synthetic local Compose deployment.',
  )
  expect(['127.0.0.1', 'localhost']).toContain(new URL(baseURL!).hostname)
  const token = crypto.randomUUID().slice(0, 8)
  const alertTitle = `Synthetic validation signal ${token}`
  const caseTitle = `Synthetic browser investigation ${token}`
  const note = `Synthetic analyst review ${token}. <script>untrusted()</script> remains plain text.`
  await page.goto('/')
  await expect(
    page.getByText('Recently active cases', { exact: true }),
  ).toBeVisible()
  await accessible(page)
  await page.getByRole('link', { name: 'Alerts', exact: true }).click()
  await page
    .getByRole('button', { name: 'Import synthetic alert', exact: true })
    .first()
    .click()
  const importDialog = page.getByRole('dialog', {
    name: 'Import synthetic alert',
  })
  await importDialog.getByLabel('Alert title').fill(alertTitle)
  await importDialog
    .getByLabel('Alert context')
    .fill(`Synthetic preserved source context ${token}`)
  await choose(page, 'Severity', 'High')
  await accessible(page)
  await importDialog
    .getByRole('button', { name: 'Import alert', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: alertTitle, exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Create case from alert' }).click()
  const createDialog = page.getByRole('dialog', {
    name: 'Create case',
    exact: true,
  })
  await createDialog.getByLabel('Case title').fill(caseTitle)
  await createDialog
    .getByLabel('Investigation summary')
    .fill(`Synthetic investigation context ${token}`)
  await createDialog
    .getByRole('button', { name: 'Create case', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: caseTitle, exact: true }),
  ).toBeVisible()
  const caseUrl = page.url()
  const editTrigger = page.getByRole('button', {
    name: 'Edit case',
    exact: true,
  })
  await editTrigger.focus()
  await page.keyboard.press('Enter')
  await expect(
    page.getByRole('dialog', { name: 'Edit case details' }),
  ).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(editTrigger).toBeFocused()
  await page.getByRole('tab', { name: /^Alerts/ }).click()
  await expect(
    page.getByRole('link', { name: alertTitle, exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Preserve as evidence' }).click()
  const evidenceDialog = page.getByRole('dialog', { name: 'Preserve evidence' })
  await expect(evidenceDialog.getByLabel('Preserved excerpt')).toHaveValue(
    `Synthetic preserved source context ${token}`,
  )
  await evidenceDialog
    .getByRole('button', { name: 'Preserve evidence', exact: true })
    .click()
  await expect(evidenceDialog).toBeHidden()
  await page.getByText('Inspect preserved snapshot', { exact: true }).click()
  await expect(
    page.getByText(`Synthetic preserved source context ${token}`, {
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    page.getByText('SHA-256 / PRESERVED CONTENT', { exact: true }),
  ).toBeVisible()
  await page.getByRole('tab', { name: /^Notes/ }).click()
  await page.getByRole('button', { name: 'Add note', exact: true }).click()
  const noteDialog = page.getByRole('dialog', { name: 'Add analyst note' })
  await noteDialog.getByLabel('Analyst note', { exact: true }).fill(note)
  await noteDialog
    .getByRole('button', { name: 'Add note', exact: true })
    .click()
  await expect(page.getByText(note, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Edit note by local-analyst' }).click()
  const revision = page.getByRole('dialog', { name: 'Edit analyst note' })
  await revision
    .getByLabel('Analyst note', { exact: true })
    .fill(`${note} Reviewed and corroborated.`)
  await revision
    .getByLabel('Revision reason')
    .fill('Clarify synthetic evidence review')
  await revision.getByRole('button', { name: 'Save note revision' }).click()
  await expect(revision).toBeHidden()
  await page
    .getByRole('button', { name: 'Manage assignment', exact: true })
    .click()
  const assignment = page.getByRole('dialog', { name: 'Manage assignment' })
  await choose(page, 'Case owner', 'local-analyst')
  await assignment.getByRole('button', { name: 'Save assignment' }).click()
  await expect(assignment).toBeHidden()
  await status(page, 'Triaging', 'Synthetic triage begins')
  await status(page, 'Investigating', 'Synthetic evidence is under review')
  await status(
    page,
    'Resolved',
    'Synthetic analyst verified evidence',
    'True positive',
  )
  await expect(page.getByRole('heading', { name: caseTitle })).toBeVisible()
  await status(page, 'Closed', 'Synthetic investigation complete')
  await expect(
    page.getByRole('button', { name: 'Reopen case', exact: true }),
  ).toBeVisible()
  await page.getByRole('tab', { name: 'History', exact: true }).click()
  await expect(
    page.getByText('10 audit events', { exact: false }),
  ).toBeVisible()
  await accessible(page)
  await mkdir(artifacts, { recursive: true })
  await page.screenshot({
    path: fileURLToPath(
      new URL(`phase2-history-${testInfo.project.name}.png`, artifacts),
    ),
    fullPage: true,
  })
  const shell = process.platform === 'win32' ? 'powershell.exe' : 'pwsh'
  const args = [
    '-NoProfile',
    '-File',
    restartScript,
    'Restart',
    ...(process.env.ATE_LIVE_DEV === '1' ? ['-Dev'] : []),
  ]
  const restarted = await promisify(execFile)(shell, args, {
    timeout: 120000,
    maxBuffer: 1024 * 1024,
  })
  expect(restarted.stderr).not.toContain('failed')
  await page.goto(caseUrl)
  await expect(
    page.getByRole('heading', { name: caseTitle, exact: true }),
  ).toBeVisible()
  await page.getByRole('tab', { name: /^Notes/ }).click()
  await expect(
    page.getByText(`${note} Reviewed and corroborated.`, { exact: true }),
  ).toBeVisible()
  await page.getByRole('tab', { name: /^Evidence/ }).click()
  await page.getByText('Inspect preserved snapshot', { exact: true }).click()
  await expect(
    page.getByText(`Synthetic preserved source context ${token}`, {
      exact: true,
    }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Reopen case', exact: true }).click()
  const reopen = page.getByRole('dialog', { name: 'Change case status' })
  await reopen
    .getByLabel('Decision rationale')
    .fill('Synthetic follow-up after restart')
  await reopen.getByRole('button', { name: 'Confirm status change' }).click()
  await expect(reopen).toBeHidden()
  await expect(
    page.getByText('Review in progress', { exact: true }),
  ).toBeVisible()
  await page.getByRole('tab', { name: 'History', exact: true }).click()
  await expect(
    page.getByText('11 audit events', { exact: false }),
  ).toBeVisible()
  await accessible(page)
  await page.screenshot({
    path: fileURLToPath(
      new URL(`phase2-case-${testInfo.project.name}.png`, artifacts),
    ),
    fullPage: true,
  })
})

test('a conflicting edit retains the draft until the analyst reloads and reviews', async ({
  page,
  context,
}) => {
  const title = `Synthetic concurrent review ${crypto.randomUUID().slice(0, 8)}`
  await page.goto('/cases')
  await page
    .getByRole('button', { name: 'New case', exact: true })
    .first()
    .click()
  const create = page.getByRole('dialog', { name: 'Create case', exact: true })
  await create.getByLabel('Case title').fill(title)
  await create.getByRole('button', { name: 'Create case', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: title, exact: true }),
  ).toBeVisible()
  const second = await context.newPage()
  await second.goto(page.url())
  await expect(
    second.getByRole('heading', { name: title, exact: true }),
  ).toBeVisible()
  await second.getByRole('button', { name: 'Edit case', exact: true }).click()
  const draft = second.getByRole('dialog', { name: 'Edit case details' })
  await draft.getByLabel('Case title').fill(`${title} — retained draft`)
  await draft.getByLabel('Reason for change').fill('Second analyst draft')
  await page.getByRole('button', { name: 'Edit case', exact: true }).click()
  const first = page.getByRole('dialog', { name: 'Edit case details' })
  await first.getByLabel('Case title').fill(`${title} — first saved`)
  await first.getByLabel('Reason for change').fill('First analyst save')
  await first.getByRole('button', { name: 'Save case details' }).click()
  await expect(first).toBeHidden()
  await draft.getByRole('button', { name: 'Save case details' }).click()
  await expect(
    draft.getByText('Case changed; reload before retrying', { exact: true }),
  ).toBeVisible()
  await expect(draft.getByLabel('Case title')).toHaveValue(
    `${title} — retained draft`,
  )
  await expect(
    draft.getByRole('button', { name: 'Save case details' }),
  ).toBeDisabled()
  await draft.getByRole('button', { name: 'Reload latest case' }).click()
  await expect(
    draft.getByText(
      'Latest data loaded. Your draft is preserved. Review it before saving.',
      { exact: true },
    ),
  ).toBeVisible()
  await expect(draft.getByLabel('Case title')).toHaveValue(
    `${title} — retained draft`,
  )
  await draft.getByRole('button', { name: 'Save case details' }).click()
  await expect(draft).toBeHidden()
  await expect(
    second.getByRole('heading', {
      name: `${title} — retained draft`,
      exact: true,
    }),
  ).toBeVisible()
  await second.close()
})
