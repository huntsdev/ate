// Real browser/API check; no intercepted requests or mocked providers.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const artifactDirectory = new URL('../../../artifacts/', import.meta.url)
await mkdir(artifactDirectory, { recursive: true })
const browser = await chromium.launch()
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  })
  const healthResponse = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/v1/health',
  )
  const readyResponse = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/v1/health/ready',
  )
  await page.goto(process.env.ATE_WEB_URL ?? 'http://127.0.0.1:8080')
  const health = await healthResponse
  const readiness = await readyResponse
  assert.equal(health.status(), 200)
  assert.equal((await health.json()).service, 'ate')
  assert.ok([200, 503].includes(readiness.status()))
  await page.getByRole('button', { name: 'Refresh status' }).waitFor()
  assert.equal(
    await page.getByText('API unreachable', { exact: true }).count(),
    0,
  )
  assert.equal(
    await page.getByRole('heading', { name: 'System overview' }).count(),
    1,
  )
  await page.screenshot({
    path: fileURLToPath(new URL('foundation-desktop.png', artifactDirectory)),
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  )
  await page.screenshot({
    path: fileURLToPath(new URL('foundation-mobile.png', artifactDirectory)),
    fullPage: true,
  })
  console.log(
    JSON.stringify({
      status: 'passed',
      health: 200,
      readiness: readiness.status(),
      mocked: false,
    }),
  )
} finally {
  await browser.close()
}
