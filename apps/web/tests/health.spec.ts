import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const healthy = {
  status: 'ready',
  dependencies: { postgres: 'healthy', redis: 'healthy' },
}
const live = {
  status: 'alive',
  service: 'ate',
  phase: 2,
  optional_dependencies: { elastic: 'not_enabled', ollama: 'not_enabled' },
}

test('healthy foundation displays API data and remains accessible on both layouts', async ({
  page,
}) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: live }))
  await page.route('**/api/v1/health/ready', (route) =>
    route.fulfill({ json: healthy }),
  )
  await page.goto('/system')
  await expect(page.getByText('Core services are ready')).toBeVisible()
  await expect(page.getByText('2 / 2', { exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Refresh status' }),
  ).toBeEnabled()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
  await page.keyboard.press('Tab')
  await expect(page.getByText('Skip to content')).toBeFocused()
  const accessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  expect(accessibility.violations).toEqual([])
})

test('dependency failure is visible and can recover with refresh', async ({
  page,
}) => {
  let recovered = false
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: live }))
  await page.route('**/api/v1/health/ready', (route) =>
    route.fulfill(
      recovered
        ? { json: healthy }
        : {
            status: 503,
            json: {
              status: 'not_ready',
              dependencies: { postgres: 'unavailable', redis: 'healthy' },
            },
          },
    ),
  )
  await page.goto('/system')
  await expect(page.getByText('Core services need attention')).toBeVisible()
  await expect(page.getByText('1 / 2', { exact: true })).toBeVisible()
  await expect(page.getByText('Unavailable', { exact: true })).toBeVisible()
  recovered = true
  await page.getByRole('button', { name: 'Refresh status' }).click()
  await expect(page.getByText('Core services are ready')).toBeVisible()
})

test('unreachable API shows an actionable state without invented dependency health', async ({
  page,
}) => {
  await page.route('**/api/**', (route) => route.abort())
  await page.goto('/system')
  await expect(page.getByText('API unreachable', { exact: true })).toBeVisible()
  await expect(page.getByText('— / 2', { exact: true })).toBeVisible()
  await expect(page.getByText('Unknown', { exact: true })).toHaveCount(2)
  await expect(
    page.getByRole('button', { name: 'Refresh status' }),
  ).toBeEnabled()
})

test('malformed readiness data is not presented as healthy', async ({
  page,
}) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: live }))
  await page.route('**/api/v1/health/ready', (route) =>
    route.fulfill({ json: { status: 'ready' } }),
  )
  await page.goto('/system')
  await expect(page.getByText('Core services need attention')).toBeVisible()
  await expect(page.getByText('— / 2', { exact: true })).toBeVisible()
})
