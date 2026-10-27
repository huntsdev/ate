import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  Box,
  Check,
  CircleDot,
  Database,
  Fingerprint,
  Layers3,
  LockKeyhole,
  Network,
  RefreshCw,
  Server,
  ShieldCheck,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import type { components } from '@/lib/api.generated'

type Health = components['schemas']['Health']
type Readiness = components['schemas']['Readiness']

async function getHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch('/api/v1/health', {
    signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
  })
  if (!response.ok) throw new Error('API unavailable')
  const data: Health = await response.json()
  if (data.status !== 'alive') throw new Error('Unexpected health response')
  return data
}

async function getReadiness(signal: AbortSignal): Promise<Readiness> {
  const response = await fetch('/api/v1/health/ready', {
    signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
  })
  if (!response.ok && response.status !== 503)
    throw new Error('Readiness unavailable')
  const data: Readiness = await response.json()
  if (
    !['ready', 'not_ready'].includes(data.status) ||
    !data.dependencies ||
    !['healthy', 'unavailable'].includes(data.dependencies.postgres) ||
    !['healthy', 'unavailable'].includes(data.dependencies.redis)
  ) {
    throw new Error('Unexpected readiness response')
  }
  if ((response.status === 200) !== (data.status === 'ready'))
    throw new Error('Inconsistent readiness response')
  return data
}

type Tone = 'good' | 'warning' | 'neutral'
function Status({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode
  tone?: Tone
}) {
  return (
    <Badge
      variant="outline"
      className={
        tone === 'good'
          ? 'border-primary/20 bg-primary/8 text-primary'
          : tone === 'warning'
            ? 'border-amber-300/20 bg-amber-300/8 text-amber-200'
            : 'text-muted-foreground'
      }
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {children}
    </Badge>
  )
}

function Stat({
  icon: Icon,
  title,
  value,
  detail,
}: {
  icon: LucideIcon
  title: string
  value: string
  detail: string
}) {
  return (
    <Card className="gap-4 py-5 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between px-5">
        <CardTitle className="text-sm font-normal text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
      </CardHeader>
      <CardContent className="px-5">
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
        <p className="mt-2 text-xs text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  )
}

export default function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: 30000,
    retry: false,
  })
  const readiness = useQuery({
    queryKey: ['readiness'],
    queryFn: ({ signal }) => getReadiness(signal),
    refetchInterval: 30000,
    retry: false,
  })
  const refreshing = health.isFetching || readiness.isFetching
  const apiOnline = health.isSuccess && !health.isError
  const readyData = readiness.isError ? undefined : readiness.data
  const healthyCount = readyData
    ? Object.values(readyData.dependencies).filter((v) => v === 'healthy')
        .length
    : null
  const ready = apiOnline && readyData?.status === 'ready'
  const timestamp = Math.max(health.dataUpdatedAt, readiness.dataUpdatedAt)
  const services = [
    {
      name: 'Application API',
      kind: 'FastAPI · modular monolith',
      icon: Server,
      status: health.isPending
        ? 'Checking'
        : apiOnline
          ? 'Healthy'
          : 'Unreachable',
      good: apiOnline,
    },
    {
      name: 'Case storage',
      kind: 'PostgreSQL · persistent volume',
      icon: Database,
      status: readyData
        ? readyData.dependencies.postgres === 'healthy'
          ? 'Healthy'
          : 'Unavailable'
        : readiness.isPending
          ? 'Checking'
          : 'Unknown',
      good: readyData?.dependencies.postgres === 'healthy',
    },
    {
      name: 'Task broker',
      kind: 'Redis · append-only persistence',
      icon: Layers3,
      status: readyData
        ? readyData.dependencies.redis === 'healthy'
          ? 'Healthy'
          : 'Unavailable'
        : readiness.isPending
          ? 'Checking'
          : 'Unknown',
      good: readyData?.dependencies.redis === 'healthy',
    },
  ]

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[224px_1fr]">
      <a
        href="#main"
        className="sr-only z-50 bg-card p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>
      <aside className="flex flex-col border-b bg-[#0c1118] lg:sticky lg:top-0 lg:h-screen lg:border-r lg:border-b-0">
        <div className="flex h-20 items-center gap-3 px-6">
          <div className="rounded-lg border border-primary/25 bg-primary/8 p-2">
            <ShieldCheck className="size-6 text-primary" aria-hidden="true" />
          </div>
          <span className="text-2xl font-semibold tracking-[0.12em]">
            ATÉ<span className="ml-1 text-primary">.</span>
          </span>
        </div>
        <div className="px-4 pb-5 lg:mt-5">
          <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.18em] text-muted-foreground">
            WORKSPACE
          </p>
          <nav aria-label="Workspace">
            <a
              href="#main"
              aria-current="page"
              className="flex items-center gap-3 rounded-lg border border-primary/15 bg-primary/8 px-3 py-2.5 text-sm text-primary"
            >
              <Activity className="size-4" aria-hidden="true" />
              System overview
              <span className="ml-auto size-1.5 rounded-full bg-primary" />
            </a>
          </nav>
          <div className="mt-7 hidden px-3 lg:block">
            <p className="text-[10px] font-semibold tracking-[0.18em] text-muted-foreground">
              NEXT MILESTONE
            </p>
            <p className="mt-3 text-sm text-slate-300">
              Investigation workspace
            </p>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              Cases, evidence, and analyst review arrive after the foundation.
            </p>
          </div>
        </div>
        <div className="mt-auto hidden p-4 lg:block">
          <div className="rounded-lg border bg-card p-3">
            <div className="flex items-center gap-2 text-xs font-medium">
              <LockKeyhole
                className="size-3.5 text-primary"
                aria-hidden="true"
              />
              Local workspace
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              Self-hosted. Human-directed.
              <br />
              Your environment, your control.
            </p>
          </div>
          <p className="mt-4 px-2 font-mono text-[10px] tracking-wider text-muted-foreground">
            FOUNDATION / PHASE 00
          </p>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="flex h-16 items-center justify-between border-b px-5 sm:px-8">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Box className="size-4" aria-hidden="true" />
            <span>Workspace</span>
            <span className="mx-1 text-border">/</span>
            <span className="text-foreground">System overview</span>
          </div>
          <Badge
            variant="outline"
            className="font-mono text-[10px] uppercase tracking-wider"
          >
            Development
          </Badge>
        </header>
        <main
          id="main"
          className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 lg:py-10"
        >
          <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="mb-2 flex items-center gap-2 text-xs font-medium text-primary">
                <span className="h-px w-5 bg-primary" />
                OPERATIONS FOUNDATION
              </p>
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                System overview
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
                A clear view of the services behind your security workspace.
              </p>
            </div>
            <Button
              variant="outline"
              disabled={refreshing}
              onClick={() => {
                void health.refetch()
                void readiness.refetch()
              }}
            >
              <RefreshCw
                className={refreshing ? 'animate-spin' : ''}
                aria-hidden="true"
              />
              {refreshing ? 'Checking services' : 'Refresh status'}
            </Button>
          </div>

          <div
            role="status"
            aria-live="polite"
            className={`mb-6 flex items-start gap-3 rounded-xl border px-4 py-4 ${ready ? 'border-primary/20 bg-primary/5' : 'border-border bg-card'}`}
          >
            <div className="mt-0.5 rounded-full border p-1.5">
              {ready ? (
                <Check className="size-4 text-primary" aria-hidden="true" />
              ) : (
                <CircleDot
                  className="size-4 text-amber-200"
                  aria-hidden="true"
                />
              )}
            </div>
            <div>
              <p className="text-sm font-medium">
                {health.isPending
                  ? 'Connecting to your workspace'
                  : !apiOnline
                    ? 'API unreachable'
                    : ready
                      ? 'Core services are ready'
                      : 'Core services need attention'}
              </p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                {!apiOnline && !health.isPending
                  ? 'Check that the application API is running, then refresh the status.'
                  : ready
                    ? 'The API, database, and task broker are responding. Optional integrations are not enabled.'
                    : 'The API can run independently. Database and broker availability determine readiness.'}
              </p>
            </div>
          </div>

          <section
            aria-label="Foundation summary"
            className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
          >
            <Stat
              icon={Activity}
              title="Application API"
              value={
                health.isPending
                  ? 'Checking'
                  : apiOnline
                    ? 'Online'
                    : 'Unreachable'
              }
              detail="Live process health"
            />
            <Stat
              icon={Database}
              title="Core dependencies"
              value={healthyCount === null ? '— / 2' : `${healthyCount} / 2`}
              detail="Database and task broker responding"
            />
            <Stat
              icon={Network}
              title="External integrations"
              value="Not enabled"
              detail="Elastic and Ollama are optional"
            />
            <Stat
              icon={Fingerprint}
              title="Workspace mode"
              value="Local development"
              detail="Loopback access · no sign-in configured"
            />
          </section>

          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.8fr)_minmax(280px,1fr)]">
            <div className="space-y-6">
              <Card className="gap-0 overflow-hidden shadow-none">
                <CardHeader className="flex flex-row items-center justify-between border-b py-5">
                  <CardTitle className="text-base">Core services</CardTitle>
                  <span className="font-mono text-[10px] tracking-wider text-muted-foreground">
                    LIVE CHECK
                  </span>
                </CardHeader>
                <CardContent className="p-0">
                  {services.map(({ name, kind, icon: Icon, status, good }) => (
                    <div
                      key={name}
                      className="flex items-center gap-3 border-b px-4 py-5 last:border-0 sm:px-6"
                    >
                      <div className="rounded-lg border bg-background/50 p-2.5">
                        <Icon
                          className="size-4 text-slate-300"
                          aria-hidden="true"
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">{name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {kind}
                        </p>
                      </div>
                      <Status
                        tone={
                          good
                            ? 'good'
                            : status === 'Checking'
                              ? 'neutral'
                              : 'warning'
                        }
                      >
                        {status}
                      </Status>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card className="gap-4 shadow-none">
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-base">
                    Optional integrations
                  </CardTitle>
                  <Badge variant="secondary">Decoupled</Badge>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2">
                  {[
                    {
                      name: 'Elastic Security',
                      label: 'Alerts & telemetry',
                      icon: ArrowDownLeft,
                    },
                    { name: 'Ollama', label: 'Local AI inference', icon: Box },
                  ].map(({ name, label, icon: Icon }) => (
                    <div
                      key={name}
                      className="rounded-lg border bg-background/30 p-4"
                    >
                      <div className="mb-4 flex items-center justify-between">
                        <Icon
                          className="size-5 text-muted-foreground"
                          aria-hidden="true"
                        />
                        <Status>Not enabled</Status>
                      </div>
                      <p className="text-sm font-medium">{name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {label}
                      </p>
                    </div>
                  ))}
                  <p className="text-xs leading-5 text-muted-foreground sm:col-span-2">
                    External integrations are added in later phases. Their
                    availability does not block core readiness.
                  </p>
                </CardContent>
              </Card>
            </div>

            <Card className="overflow-hidden shadow-none">
              <div className="workspace-grid flex h-32 items-center justify-center border-b">
                <div className="rounded-2xl border border-primary/25 bg-background p-4 shadow-[0_0_35px_#7ee6b512]">
                  <ShieldCheck
                    className="size-9 text-primary"
                    strokeWidth={1.4}
                    aria-hidden="true"
                  />
                </div>
              </div>
              <CardHeader>
                <p className="text-[10px] font-semibold tracking-[0.15em] text-primary">
                  BUILT FOR THE ANALYST
                </p>
                <CardTitle className="text-xl leading-7">
                  A deliberate foundation.
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-6 text-muted-foreground">
                  Durable infrastructure first. Evidence, investigations, and
                  AI-assisted analysis follow in focused stages.
                </p>
                <Separator className="my-5" />
                <ul className="space-y-4 text-xs text-slate-300">
                  {[
                    'Persistent storage across restarts',
                    'Optional local inference',
                    'Human review at the center',
                  ].map((item) => (
                    <li key={item} className="flex items-center gap-2">
                      <Check
                        className="size-3.5 text-primary"
                        aria-hidden="true"
                      />
                      {item}
                    </li>
                  ))}
                </ul>
                <Button asChild variant="outline" className="mt-6 w-full">
                  <a href="/docs" target="_blank" rel="noreferrer">
                    View API reference
                    <ArrowUpRight aria-hidden="true" />
                  </a>
                </Button>
              </CardContent>
            </Card>
          </div>
          <footer className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t pt-5 font-mono text-[10px] text-muted-foreground">
            <span>ATÉ / SECURITY OPERATIONS WORKSPACE</span>
            <span>
              {timestamp
                ? `Last response ${new Date(timestamp).toLocaleTimeString()}`
                : 'Waiting for first response'}{' '}
              · refreshes every 30s
            </span>
          </footer>
        </main>
      </div>
    </div>
  )
}
