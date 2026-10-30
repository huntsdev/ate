import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ArrowUpRight,
  Check,
  Cpu,
  Database,
  HardDrive,
  Network,
  RefreshCw,
  Server,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PageHeading, Panel } from '@/components/workspace'
import type { Schema } from '@/lib/api'

async function health(signal: AbortSignal): Promise<Schema['Health']> {
  const response = await fetch('/api/v1/health', {
    signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
  })
  if (!response.ok) throw new Error('API unavailable')
  const data: Schema['Health'] = await response.json()
  if (data.status !== 'alive') throw new Error('Unexpected health response')
  return data
}

async function readiness(signal: AbortSignal): Promise<Schema['Readiness']> {
  const response = await fetch('/api/v1/health/ready', {
    signal: AbortSignal.any([signal, AbortSignal.timeout(5000)]),
  })
  if (!response.ok && response.status !== 503)
    throw new Error('Readiness unavailable')
  const data: Schema['Readiness'] = await response.json()
  if (
    !['ready', 'not_ready'].includes(data.status) ||
    !data.dependencies ||
    !['healthy', 'unavailable'].includes(data.dependencies.postgres) ||
    !['healthy', 'unavailable'].includes(data.dependencies.redis) ||
    (response.status === 200) !== (data.status === 'ready')
  )
    throw new Error('Unexpected readiness response')
  return data
}

export function SystemPage() {
  const live = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => health(signal),
    retry: false,
    refetchInterval: 30000,
  })
  const core = useQuery({
    queryKey: ['readiness'],
    queryFn: ({ signal }) => readiness(signal),
    retry: false,
    refetchInterval: 30000,
  })
  const readyData = core.isError ? undefined : core.data
  const online = live.isSuccess && !live.isError
  const ready = online && readyData?.status === 'ready'
  const count = readyData
    ? Object.values(readyData.dependencies).filter(
        (value) => value === 'healthy',
      ).length
    : null
  const refreshing = live.isFetching || core.isFetching
  const services = [
    {
      name: 'Application API',
      description: 'Workspace requests and case operations',
      icon: Server,
      state: live.isPending ? 'Checking' : online ? 'Healthy' : 'Unreachable',
    },
    {
      name: 'Case storage',
      description: 'Persistent cases, evidence, and audit history',
      icon: Database,
      state: readyData
        ? readyData.dependencies.postgres === 'healthy'
          ? 'Healthy'
          : 'Unavailable'
        : core.isPending
          ? 'Checking'
          : 'Unknown',
    },
    {
      name: 'Task broker',
      description: 'Background task infrastructure',
      icon: Network,
      state: readyData
        ? readyData.dependencies.redis === 'healthy'
          ? 'Healthy'
          : 'Unavailable'
        : core.isPending
          ? 'Checking'
          : 'Unknown',
    },
  ]
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE / SERVICE HEALTH"
        title="System overview"
        description="Live availability for the services supporting your analyst workspace."
        actions={
          <Button
            variant="outline"
            disabled={refreshing}
            onClick={() => {
              void live.refetch()
              void core.refetch()
            }}
          >
            <RefreshCw className={refreshing ? 'animate-spin' : ''} />
            Refresh status
          </Button>
        }
      />
      <div
        role="status"
        className={`mb-6 flex items-center gap-3 rounded-lg border p-4 ${ready ? 'border-primary/20 bg-primary/5 text-primary' : 'bg-card text-muted-foreground'}`}
      >
        <Activity className="size-5 shrink-0" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium">
            {live.isPending
              ? 'Connecting to your workspace'
              : !online
                ? 'API unreachable'
                : ready
                  ? 'Core services are ready'
                  : 'Core services need attention'}
          </p>
          <p className="mt-1 text-[11px] leading-6 text-muted-foreground">
            {ready
              ? 'The API, database, and broker are responding.'
              : 'Check service status below and refresh when the environment is available.'}
          </p>
        </div>
      </div>
      <div className="metric-grid">
        {[
          {
            title: 'Application API',
            value: live.isPending
              ? 'Checking'
              : online
                ? 'Online'
                : 'Unreachable',
            detail: 'Process health',
            icon: Activity,
          },
          {
            title: 'Core dependencies',
            value: count === null ? '— / 2' : `${count} / 2`,
            detail: 'Database and task broker',
            icon: HardDrive,
          },
          {
            title: 'External integrations',
            value: 'Not enabled',
            detail: 'Optional provider capabilities',
            icon: Cpu,
          },
          {
            title: 'Workspace mode',
            value: 'Local only',
            detail: 'Single analyst development access',
            icon: Check,
          },
        ].map(({ title, value, detail, icon: Icon }) => (
          <div className="metric-card" key={title}>
            <div className="metric-heading">
              <span>{title}</span>
              <Icon aria-hidden="true" />
            </div>
            <p className="mt-4 text-xl font-medium tracking-tight">{value}</p>
            <p className="metric-description">{detail}</p>
          </div>
        ))}
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,1fr)]">
        <Panel
          title="Core services"
          description="Live checks · refreshed every 30 seconds"
        >
          {services.map(({ name, description, icon: Icon, state }) => (
            <div className="system-service" key={name}>
              <div className="system-service-icon">
                <Icon className="size-4" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-[13px] font-medium">{name}</h3>
                <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                  {description}
                </p>
              </div>
              <span
                className={`service-status ${state === 'Healthy' ? 'service-good' : ['Unavailable', 'Unreachable'].includes(state) ? 'service-warning' : 'service-neutral'}`}
              >
                {state}
              </span>
            </div>
          ))}
        </Panel>
        <Panel
          title="Provider capabilities"
          description="Optional integrations remain independent"
        >
          {[
            {
              name: 'Elastic Security',
              description: 'Alert and telemetry ingestion',
              icon: Database,
            },
            {
              name: 'Ollama',
              description: 'Local AI investigation assistance',
              icon: Cpu,
            },
          ].map(({ name, description, icon: Icon }) => (
            <div className="border-b p-5 last:border-0" key={name}>
              <div className="flex items-center justify-between">
                <Icon
                  className="size-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <Badge
                  variant="outline"
                  className="text-[9px] text-muted-foreground"
                >
                  Not enabled
                </Badge>
              </div>
              <h3 className="mt-4 text-xs font-medium">{name}</h3>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {description}
              </p>
            </div>
          ))}
          <div className="border-t px-5 py-4">
            <p className="text-[11px] leading-6 text-muted-foreground">
              Saved investigations remain available independently of optional
              providers.
            </p>
            <Button asChild variant="link" className="mt-2 h-auto px-0 text-xs">
              <a href="/docs" target="_blank" rel="noreferrer">
                View API reference
                <ArrowUpRight />
              </a>
            </Button>
          </div>
        </Panel>
      </div>
    </>
  )
}
