import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const actor = {
  id: '00000000-0000-4000-8000-000000000200',
  handle: 'local-analyst',
  kind: 'human',
  is_active: true,
}
const empty = { items: [], total: 0, limit: 25, offset: 0 }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/session', (route) =>
    route.fulfill({
      json: {
        mode: 'local_single_user',
        actor,
        csrf_token: 'synthetic-browser-only-token',
      },
    }),
  )
  await page.route('**/api/v1/users', (route) =>
    route.fulfill({ json: [actor] }),
  )
})

test('case queue has a deliberate loading and empty state', async ({
  page,
}) => {
  let release = () => {}
  const ready = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/cases?*', async (route) => {
    await ready
    await route.fulfill({ json: empty })
  })
  await page.goto('/cases')
  await expect(page.getByText('Loading cases', { exact: true })).toBeVisible()
  release()
  await expect(
    page.getByText('A clear desk. A place to start.', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Cases', exact: true }),
  ).toHaveAttribute('aria-current', 'page')
  const accessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  expect(accessibility.violations).toEqual([])
})

test('storage outage is actionable and can recover without fabricated rows', async ({
  page,
}) => {
  let recovered = false
  await page.route('**/api/v1/cases?*', (route) =>
    recovered
      ? route.fulfill({ json: empty })
      : route.fulfill({
          status: 503,
          json: {
            type: 'urn:ate:problem:storage_unavailable',
            title: 'Service unavailable',
            status: 503,
            code: 'storage_unavailable',
            detail:
              'Case storage is unavailable. Try again when services recover.',
            correlation_id: 'synthetic-error-reference',
            errors: [],
          },
        }),
  )
  await page.goto('/cases')
  await expect(page.getByRole('alert')).toContainText(
    'Case storage is unavailable',
  )
  await expect(
    page.getByText('Reference synthetic-error-reference', { exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('row')).toHaveCount(0)
  recovered = true
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(
    page.getByText('A clear desk. A place to start.', { exact: true }),
  ).toBeVisible()
})

test('untrusted case titles are rendered as text in the queue', async ({
  page,
}) => {
  const title = '<img src=x onerror="untrusted()"> synthetic case'
  await page.route('**/api/v1/cases?*', (route) =>
    route.fulfill({
      json: {
        ...empty,
        total: 1,
        items: [
          {
            id: '00000000-0000-4000-8000-000000000001',
            display_id: 'SF-2026-009999',
            title,
            summary: 'Synthetic text',
            severity: 'high',
            status: 'new',
            disposition: null,
            assigned_to: null,
            owner_handle: null,
            created_by: actor.id,
            version: 1,
            created_at: '2026-10-28T12:00:00Z',
            updated_at: '2026-10-28T12:00:00Z',
            sources: ['synthetic'],
            allowed_transitions: ['triaging', 'investigating'],
          },
        ],
      },
    }),
  )
  await page.goto('/cases')
  await expect(page.getByText(title, { exact: true })).toBeVisible()
  await expect(page.locator('img')).toHaveCount(0)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})
