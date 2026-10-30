import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import {
  ArrowRight,
  CircleCheck,
  ClipboardList,
  FolderKanban,
  Link2,
  Plus,
  Radio,
  Search,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  ImportAlertDialog,
  Modal,
  NewCaseDialog,
  SaveButton,
  useCommand,
} from '@/components/case-forms'
import {
  CaseTable,
  Choice,
  EmptyPanel,
  ErrorPanel,
  LoadingPanel,
  PageHeading,
  Pager,
  Panel,
  SeverityBadge,
  SourceReference,
  TextField,
} from '@/components/workspace'
import {
  dateTime,
  field,
  label,
  severities,
  shortDate,
  statuses,
  useData,
} from '@/lib/api'
import type { AlertRecord, CaseRecord, Schema } from '@/lib/api'

export function DashboardPage() {
  const data = useData<Schema['Dashboard']>(['dashboard'], '/dashboard')
  return (
    <>
      <PageHeading
        eyebrow="OPERATIONS / OVERVIEW"
        title="Your investigation desk."
        description="Keep the signal in focus. Move each investigation forward with evidence and a clear decision."
        actions={
          <>
            <ImportAlertDialog />
            <NewCaseDialog />
          </>
        }
      />
      {data.isPending ? (
        <LoadingPanel message="Loading operational overview" />
      ) : data.error ? (
        <ErrorPanel error={data.error} retry={() => void data.refetch()} />
      ) : (
        data.data && (
          <>
            <div className="metric-grid">
              {[
                {
                  label: 'Open cases',
                  value: data.data.open_cases,
                  description: 'New, triaging, and investigating',
                  icon: FolderKanban,
                },
                {
                  label: 'Awaiting an owner',
                  value: data.data.unassigned_open_cases,
                  description: 'Open cases without an assignment',
                  icon: UserRound,
                },
                {
                  label: 'Unlinked alerts',
                  value: data.data.unlinked_alerts,
                  description: 'Signals not yet attached to a case',
                  icon: Radio,
                },
                {
                  label: 'Total cases',
                  value: data.data.total_cases,
                  description: 'All retained investigations',
                  icon: ClipboardList,
                },
              ].map(({ label: title, value, description, icon: Icon }) => (
                <div className="metric-card" key={title}>
                  <div className="metric-heading">
                    <span>{title}</span>
                    <Icon aria-hidden="true" />
                  </div>
                  <p className="metric-value">{value.toLocaleString()}</p>
                  <p className="metric-description">{description}</p>
                </div>
              ))}
            </div>
            <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,2.2fr)_minmax(250px,1fr)]">
              <Panel
                title="Recently active cases"
                description="The latest changes across your workspace"
                actions={
                  <Button asChild variant="ghost" size="sm">
                    <Link to="/cases">
                      View all cases
                      <ArrowRight />
                    </Link>
                  </Button>
                }
              >
                {data.data.recent_cases.length ? (
                  <CaseTable cases={data.data.recent_cases} compact />
                ) : (
                  <EmptyPanel
                    title="No investigations yet"
                    description="Create your first case, or begin with a synthetic alert."
                  >
                    <NewCaseDialog />
                  </EmptyPanel>
                )}
                <div className="flex items-center justify-between gap-2 border-t px-5 py-3 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-2">
                    <span className="size-1 rounded-full bg-primary" />
                    Saved case activity
                  </span>
                  <span className="font-mono">REFRESHES EVERY 30s</span>
                </div>
              </Panel>
              <div className="space-y-5">
                <Panel
                  title="Active severity"
                  description="Open cases by current analyst severity"
                >
                  <div className="space-y-5 p-5">
                    {severities.map((severity) => (
                      <div key={severity}>
                        <div className="mb-2 flex justify-between gap-3">
                          <SeverityBadge severity={severity} />
                          <span className="font-mono text-xs">
                            {data.data.severity_counts[severity]}
                          </span>
                        </div>
                        <div className="severity-track">
                          <div
                            className="severity-fill"
                            style={{
                              width: `${(100 * data.data.severity_counts[severity]) / Math.max(1, data.data.open_cases)}%`,
                              background: {
                                critical: '#ffa8b5',
                                high: '#edc68a',
                                medium: '#9dbff0',
                                low: '#adbbcc',
                              }[severity],
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </Panel>
                <div className="rounded-xl border border-primary/15 bg-primary/[.035] p-5">
                  <ShieldCheck
                    className="mb-4 size-5 text-primary"
                    aria-hidden="true"
                  />
                  <h2 className="text-[13px] font-medium">
                    Human review is the authority.
                  </h2>
                  <p className="mt-2 text-xs leading-6 text-muted-foreground">
                    Your evidence, notes, and decisions stay connected to a
                    durable case history.
                  </p>
                  <div className="mt-4 flex items-center gap-2 border-t border-primary/10 pt-4 text-[10px] text-primary">
                    <CircleCheck className="size-3.5" aria-hidden="true" />
                    Analyst-owned dispositions
                  </div>
                </div>
              </div>
            </div>
          </>
        )
      )}
    </>
  )
}

function queryFromParams(params: URLSearchParams) {
  const output = new URLSearchParams(params)
  output.set(
    'limit',
    String(Math.min(100, Math.max(1, Number(params.get('limit')) || 25))),
  )
  output.set(
    'offset',
    String(Math.min(100000, Math.max(0, Number(params.get('offset')) || 0))),
  )
  return output
}

export function CaseListPage() {
  const [params, setParams] = useSearchParams()
  const query = queryFromParams(params)
  const data = useData<Schema['CasePage']>(
    ['cases', query.toString()],
    `/cases?${query}`,
  )
  const users = useData<Schema['UserOut'][]>(['users'], '/users')
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const next = new URLSearchParams()
    for (const key of ['q', 'status', 'severity', 'provider']) {
      const value = field(form, key)
      if (value && value !== 'all') next.set(key, value)
    }
    const owner = field(form, 'owner')
    if (owner === 'unassigned') next.set('unassigned', 'true')
    else if (owner !== 'all' && owner) next.set('owner', owner)
    const sort = field(form, 'sort_by')
    next.set('sort', sort === 'severity' ? 'severity' : 'updated_at')
    next.set('order', sort === 'oldest' ? 'asc' : 'desc')
    setParams(next)
  }
  const changePage = (offset: number) => {
    const next = new URLSearchParams(query)
    next.set('offset', String(offset))
    setParams(next)
  }
  return (
    <>
      <PageHeading
        eyebrow="OPERATIONS / CASE MANAGEMENT"
        title="Cases"
        description="A single record for the evidence, decisions, and people behind every investigation."
        actions={<NewCaseDialog />}
      />
      <Panel
        title="Investigation queue"
        description="Filter and prioritize retained cases"
      >
        <form
          className="filter-bar"
          onSubmit={filter}
          key={params.toString()}
          role="search"
        >
          <TextField
            id="case-search"
            name="q"
            label="Search cases"
            defaultValue={params.get('q') ?? ''}
            maxLength={200}
            placeholder="Title, case ID, or context"
          />
          <Choice
            id="case-filter-status"
            name="status"
            label="Status"
            defaultValue={params.get('status') ?? 'all'}
            options={[
              { value: 'all', label: 'All statuses' },
              ...statuses.map((value) => ({ value, label: label(value) })),
            ]}
          />
          <Choice
            id="case-filter-severity"
            name="severity"
            label="Severity"
            defaultValue={params.get('severity') ?? 'all'}
            options={[
              { value: 'all', label: 'All severities' },
              ...severities.map((value) => ({ value, label: label(value) })),
            ]}
          />
          <Choice
            id="case-filter-owner"
            name="owner"
            label="Owner"
            defaultValue={
              params.has('unassigned')
                ? 'unassigned'
                : (params.get('owner') ?? 'all')
            }
            options={[
              { value: 'all', label: 'All owners' },
              { value: 'unassigned', label: 'Unassigned' },
              ...(users.data ?? []).map((user) => ({
                value: user.id,
                label: user.handle,
              })),
            ]}
          />
          <Choice
            id="case-filter-source"
            name="provider"
            label="Source"
            defaultValue={params.get('provider') ?? 'all'}
            options={[
              { value: 'all', label: 'All sources' },
              { value: 'synthetic', label: 'Synthetic' },
            ]}
          />
          <Choice
            id="case-sort"
            name="sort_by"
            label="Sort order"
            defaultValue={
              params.get('sort') === 'severity'
                ? 'severity'
                : params.get('order') === 'asc'
                  ? 'oldest'
                  : 'recent'
            }
            options={[
              { value: 'recent', label: 'Recently active' },
              { value: 'oldest', label: 'Oldest activity' },
              { value: 'severity', label: 'Highest severity' },
            ]}
          />
          <Button type="submit" variant="secondary">
            <Search />
            Apply filters
          </Button>
          {params.size > 0 && (
            <Button type="button" variant="ghost" onClick={() => setParams({})}>
              Clear
            </Button>
          )}
        </form>
        {data.isPending ? (
          <div className="p-5">
            <LoadingPanel message="Loading cases" />
          </div>
        ) : data.error ? (
          <div className="p-5">
            <ErrorPanel error={data.error} retry={() => void data.refetch()} />
          </div>
        ) : (
          data.data && (
            <>
              {data.data.items.length ? (
                <CaseTable cases={data.data.items} />
              ) : (
                <EmptyPanel
                  title={
                    params.size
                      ? 'No cases match these filters'
                      : 'A clear desk. A place to start.'
                  }
                  description={
                    params.size
                      ? 'Try another status, severity, source, or search term.'
                      : 'Create a case to start tracking an investigation.'
                  }
                >
                  {params.size ? (
                    <Button variant="outline" onClick={() => setParams({})}>
                      Clear filters
                    </Button>
                  ) : (
                    <NewCaseDialog />
                  )}
                </EmptyPanel>
              )}
              <Pager {...data.data} change={changePage} label="cases" />
            </>
          )
        )}
      </Panel>
    </>
  )
}

export function AlertListPage() {
  const [params, setParams] = useSearchParams()
  const query = queryFromParams(params)
  const data = useData<Schema['AlertPage']>(
    ['alerts', query.toString()],
    `/alerts?${query}`,
  )
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const next = new URLSearchParams()
    for (const key of ['q', 'severity', 'linked', 'provider']) {
      const value = field(form, key)
      if (value && value !== 'all') next.set(key, value)
    }
    const sort = field(form, 'sort')
    if (sort) next.set('sort', sort)
    setParams(next)
  }
  return (
    <>
      <PageHeading
        eyebrow="OPERATIONS / SIGNAL INBOX"
        title="Alerts"
        description="Review incoming signals, preserve their context, and attach them to the right investigation."
        actions={<ImportAlertDialog />}
      />
      <Panel
        title="Alert queue"
        description="Synthetic development signals · source records remain unchanged"
      >
        <form
          role="search"
          className="filter-bar"
          onSubmit={filter}
          key={params.toString()}
        >
          <TextField
            id="alert-search"
            name="q"
            label="Search alerts"
            defaultValue={params.get('q') ?? ''}
            maxLength={200}
            placeholder="Title, host, user, or alert ID"
          />
          <Choice
            id="alert-filter-severity"
            name="severity"
            label="Severity"
            defaultValue={params.get('severity') ?? 'all'}
            options={[
              { value: 'all', label: 'All severities' },
              ...severities.map((value) => ({ value, label: label(value) })),
            ]}
          />
          <Choice
            id="alert-filter-linked"
            name="linked"
            label="Case relationship"
            defaultValue={params.get('linked') ?? 'all'}
            options={[
              { value: 'all', label: 'All alerts' },
              { value: 'false', label: 'Unlinked alerts' },
              { value: 'true', label: 'Linked alerts' },
            ]}
          />
          <Choice
            id="alert-filter-provider"
            name="provider"
            label="Source"
            defaultValue={params.get('provider') ?? 'all'}
            options={[
              { value: 'all', label: 'All sources' },
              { value: 'synthetic', label: 'Synthetic' },
            ]}
          />
          <Choice
            id="alert-sort"
            name="sort"
            label="Sort order"
            defaultValue={params.get('sort') ?? 'observed_at'}
            options={[
              { value: 'observed_at', label: 'Recent events' },
              { value: 'imported_at', label: 'Recent imports' },
              { value: 'severity', label: 'Highest severity' },
            ]}
          />
          <Button type="submit" variant="secondary">
            <Search />
            Apply filters
          </Button>
          {params.size > 0 && (
            <Button type="button" variant="ghost" onClick={() => setParams({})}>
              Clear
            </Button>
          )}
        </form>
        {data.isPending ? (
          <div className="p-5">
            <LoadingPanel message="Loading alerts" />
          </div>
        ) : data.error ? (
          <div className="p-5">
            <ErrorPanel error={data.error} retry={() => void data.refetch()} />
          </div>
        ) : (
          data.data && (
            <>
              {data.data.items.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Signal</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Case links</TableHead>
                      <TableHead className="text-right">Event time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.data.items.map((alert) => (
                      <TableRow key={alert.id}>
                        <TableCell className="max-w-[440px]">
                          <Link
                            to={`/alerts/${alert.id}`}
                            className="case-link"
                          >
                            <span className="case-number">
                              {alert.external_alert_id}
                            </span>
                            <span className="break-words whitespace-normal font-medium text-foreground">
                              {alert.title}
                            </span>
                          </Link>
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            {alert.host ?? 'Host not provided'}
                          </p>
                        </TableCell>
                        <TableCell>
                          <SeverityBadge severity={alert.severity} />
                        </TableCell>
                        <TableCell className="text-[11px] text-muted-foreground">
                          {alert.provider}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              alert.linked_case_count
                                ? 'text-primary'
                                : 'text-muted-foreground'
                            }
                          >
                            {alert.linked_case_count
                              ? `${alert.linked_case_count} linked`
                              : 'Unlinked'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono text-[10px] whitespace-nowrap text-muted-foreground">
                          {shortDate(alert.observed_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyPanel
                  title="No alerts in this view"
                  description="Import a synthetic alert, or adjust the current filters."
                >
                  <ImportAlertDialog />
                </EmptyPanel>
              )}
              <Pager
                {...data.data}
                label="alerts"
                change={(offset) => {
                  const next = new URLSearchParams(query)
                  next.set('offset', String(offset))
                  setParams(next)
                }}
              />
            </>
          )
        )}
      </Panel>
    </>
  )
}

export function AlertDetailPage() {
  const { id } = useParams()
  return <AlertDetail key={id} id={id!} />
}

function AlertDetail({ id }: { id: string }) {
  const data = useData<Schema['AlertDetail']>(['alert', id], `/alerts/${id}`)
  if (data.isPending) return <LoadingPanel message="Loading alert context" />
  if (data.error)
    return <ErrorPanel error={data.error} retry={() => void data.refetch()} />
  const alert = data.data!
  return (
    <>
      <div className="mb-5">
        <Link
          to="/alerts"
          className="text-xs text-muted-foreground hover:text-primary"
        >
          ← Alert queue
        </Link>
      </div>
      <div className="detail-toolbar">
        <div className="min-w-0">
          <p className="eyebrow">
            <span />
            ALERT CONTEXT
          </p>
          <h1 className="record-title">{alert.title}</h1>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <SeverityBadge severity={alert.severity} />
            <Badge
              variant="outline"
              className="text-[10px] text-muted-foreground"
            >
              {alert.provider}
            </Badge>
            <span className="text-[11px] text-muted-foreground">
              {alert.linked_case_count
                ? `${alert.linked_case_count} case relationships`
                : 'Not linked to a case'}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <LinkExistingCaseDialog alert={alert} />
          <NewCaseDialog
            alert={alert}
            trigger={
              <Button>
                <Plus />
                Create case from alert
              </Button>
            }
          />
        </div>
      </div>
      <div className="detail-grid">
        <div className="space-y-5">
          <Panel
            title="Signal context"
            description="Preserved alert metadata for analyst review"
          >
            <div className="p-5">
              <p className="record-text">
                {alert.summary ||
                  'No additional context was supplied for this alert.'}
              </p>
            </div>
          </Panel>
          <Panel
            title="Related investigations"
            description="Cases linked to this source alert"
          >
            {alert.cases.length ? (
              <CaseTable cases={alert.cases} compact />
            ) : (
              <EmptyPanel
                title="This signal needs an investigation"
                description="Create a case or attach this alert to an existing investigation."
              />
            )}
          </Panel>
        </div>
        <div className="space-y-5">
          <Panel title="Source provenance">
            <dl className="fact-list">
              <div>
                <dt>Provider</dt>
                <dd>{alert.provider}</dd>
              </div>
              <div>
                <dt>Scope</dt>
                <dd>{alert.provider_scope}</dd>
              </div>
              <div>
                <dt>Host</dt>
                <dd>{alert.host ?? 'Not provided'}</dd>
              </div>
              <div>
                <dt>User</dt>
                <dd>{alert.user_name ?? 'Not provided'}</dd>
              </div>
              <div>
                <dt>Rule</dt>
                <dd>{alert.rule_id ?? 'Not provided'}</dd>
              </div>
              <div>
                <dt>Event time</dt>
                <dd>{dateTime(alert.observed_at)}</dd>
              </div>
              <div>
                <dt>Imported</dt>
                <dd>{dateTime(alert.imported_at)}</dd>
              </div>
            </dl>
            <div className="border-t p-5">
              <p className="mb-2 text-[10px] text-muted-foreground">
                SOURCE REFERENCE
              </p>
              <SourceReference value={alert.source_ref} />
              <p className="mt-4 text-[10px] text-muted-foreground">
                EXTERNAL ALERT ID
              </p>
              <code className="mt-2 block break-all text-[11px] text-foreground">
                {alert.external_alert_id}
              </code>
            </div>
          </Panel>
          <div className="subtle-callout">
            <p className="text-xs font-medium">Review before disposition</p>
            <p className="mt-2 text-[11px] leading-6 text-muted-foreground">
              An alert is a signal. Record your conclusion in the case after
              reviewing its evidence.
            </p>
          </div>
        </div>
      </div>
    </>
  )
}

function LinkExistingCaseDialog({ alert }: { alert: AlertRecord }) {
  const [open, setOpen] = useState(false)
  return (
    <Modal
      open={open}
      onOpenChange={setOpen}
      title="Link to an existing case"
      description="Choose the investigation this alert supports and record the relationship."
      trigger={
        <Button variant="outline">
          <Link2 />
          Link to existing case
        </Button>
      }
    >
      <CasePicker alert={alert} close={() => setOpen(false)} />
    </Modal>
  )
}

function CasePicker({
  alert,
  close,
}: {
  alert: AlertRecord
  close: () => void
}) {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState('')
  const cases = useData<Schema['CasePage']>(
    ['cases', 'picker', search],
    `/cases?limit=50&q=${encodeURIComponent(search)}`,
  )
  const record = cases.data?.items.find((item) => item.id === selected)
  return (
    <div className="action-form">
      <TextField
        id="existing-case-search"
        label="Search existing cases"
        value={search}
        onChange={(event) => {
          setSearch(event.target.value)
          setSelected('')
        }}
        maxLength={200}
      />
      <Choice
        id="existing-case"
        label="Case to link"
        value={selected}
        onValueChange={setSelected}
        placeholder="Select a case"
        options={(cases.data?.items ?? []).map((item) => ({
          value: item.id,
          label: `${item.display_id} · ${item.title}`,
          disabled: item.status === 'closed',
        }))}
      />
      {cases.error && (
        <ErrorPanel error={cases.error} retry={() => void cases.refetch()} />
      )}
      {record && (
        <ExistingLinkForm
          key={record.id}
          record={record}
          alert={alert}
          close={close}
        />
      )}
      {cases.data?.total === 0 && (
        <p className="field-help">
          No cases match. Create a new case from this alert instead.
        </p>
      )}
    </div>
  )
}

function ExistingLinkForm({
  record,
  alert,
  close,
}: {
  record: CaseRecord
  alert: AlertRecord
  close: () => void
}) {
  const command = useCommand<Schema['CaseMutation']>({
    record,
    onDone: close,
    message: 'Alert linked to the selected case.',
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    command.mutation.mutate({
      path: `/cases/${record.id}/alerts`,
      body: { alert_id: alert.id, reason: field(form, 'reason') },
    })
  }
  return (
    <form onSubmit={submit} className="space-y-5">
      <TextField
        id="existing-link-reason"
        name="reason"
        label="Link reason"
        required
        maxLength={1000}
        defaultValue="Related to this investigation"
      />
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked}>
        Link alert to case
      </SaveButton>
    </form>
  )
}
