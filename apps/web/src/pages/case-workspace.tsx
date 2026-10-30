import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import {
  ArrowRight,
  ChevronRight,
  FileText,
  Fingerprint,
  Link2,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  AssignmentForm,
  EditCaseForm,
  EvidenceForm,
  LinkAlertForm,
  Modal,
  NoteForm,
  TransitionForm,
  UnlinkForm,
} from '@/components/case-forms'
import {
  EmptyPanel,
  ErrorPanel,
  LoadingPanel,
  Pager,
  Panel,
  SeverityBadge,
  SourceReference,
  StateBadge,
} from '@/components/workspace'
import { dateTime, label, useData, useSession } from '@/lib/api'
import type { AlertRecord, Schema } from '@/lib/api'

type Action =
  | { kind: 'details' | 'assignment' | 'status' | 'link-alert' }
  | { kind: 'note'; note?: Schema['NoteOut'] }
  | { kind: 'evidence'; alert?: AlertRecord }
  | { kind: 'unlink-alert'; alert: AlertRecord }
  | { kind: 'unlink-evidence'; evidence: Schema['EvidenceOut'] }

export function CasePage() {
  const { id } = useParams()
  return <CaseWorkspace key={id} id={id!} />
}

function CaseWorkspace({ id }: { id: string }) {
  const record = useData<Schema['CaseOut']>(['case', id], `/cases/${id}`)
  const session = useSession()
  const [tab, setTab] = useState('overview')
  const [action, updateAction] = useState<Action | null>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  function setAction(next: Action | null) {
    if (next)
      returnFocus.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null
    updateAction(next)
  }
  const [offsets, setOffsets] = useState({
    alerts: 0,
    notes: 0,
    evidence: 0,
    timeline: 0,
  })
  const alerts = useData<Schema['LinkedAlertPage']>(
    ['case', id, 'alerts', offsets.alerts],
    `/cases/${id}/alerts?offset=${offsets.alerts}`,
    !!record.data,
  )
  const notes = useData<Schema['NotePage']>(
    ['case', id, 'notes', offsets.notes],
    `/cases/${id}/notes?offset=${offsets.notes}`,
    !!record.data,
  )
  const evidence = useData<Schema['EvidencePage']>(
    ['case', id, 'evidence', offsets.evidence],
    `/cases/${id}/evidence?offset=${offsets.evidence}`,
    !!record.data,
  )
  const history = useData<Schema['EventPage']>(
    ['case', id, 'timeline', offsets.timeline],
    `/cases/${id}/timeline?offset=${offsets.timeline}`,
    !!record.data,
  )
  const close = () => setAction(null)
  if (record.isPending) return <LoadingPanel message="Opening investigation" />
  if (record.error)
    return (
      <>
        <Link to="/cases" className="text-xs text-primary">
          ← Back to cases
        </Link>
        <ErrorPanel error={record.error} retry={() => void record.refetch()} />
      </>
    )
  const item = record.data!
  const closed = item.status === 'closed'
  const title =
    action?.kind === 'note'
      ? action.note
        ? 'Edit analyst note'
        : 'Add analyst note'
      : {
          details: 'Edit case details',
          assignment: 'Manage assignment',
          status: 'Change case status',
          'link-alert': 'Link an alert',
          evidence: 'Preserve evidence',
          'unlink-alert': 'Unlink alert',
          'unlink-evidence': 'Unlink evidence',
        }[action?.kind ?? 'details']
  const changePage = (kind: keyof typeof offsets, offset: number) =>
    setOffsets({ ...offsets, [kind]: offset })
  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/cases"
          className="flex items-center gap-2 text-[11px] text-muted-foreground hover:text-primary"
        >
          Cases
          <ChevronRight className="size-3" aria-hidden="true" />
          <span className="font-mono">{item.display_id}</span>
        </Link>
        <span className="font-mono text-[9px] text-muted-foreground">
          CASE WORKSPACE / REVISION {item.version}
        </span>
      </div>
      <div className="detail-toolbar">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <span className="eyebrow mb-0 text-primary">{item.display_id}</span>
            <StateBadge status={item.status} />
          </div>
          <h1 className="record-title">{item.title}</h1>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <SeverityBadge severity={item.severity} />
            <span className="text-[11px] text-muted-foreground">
              {item.sources.length
                ? item.sources.join(' · ')
                : 'Manual investigation'}
            </span>
            <span className="text-[11px] text-muted-foreground">
              Updated {dateTime(item.updated_at)}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Refresh case"
            disabled={record.isFetching}
            onClick={() => void record.refetch()}
          >
            <RefreshCw className={record.isFetching ? 'animate-spin' : ''} />
          </Button>
          <Button
            variant="outline"
            disabled={closed}
            onClick={() => setAction({ kind: 'details' })}
          >
            <Pencil />
            Edit case
          </Button>
          <Button onClick={() => setAction({ kind: 'status' })}>
            {closed ? 'Reopen case' : 'Change status'}
            <ArrowRight />
          </Button>
        </div>
      </div>
      {closed && (
        <div className="mb-5 rounded-lg border bg-card px-4 py-3 text-xs text-muted-foreground">
          This case is closed. Reopen it to add notes, change links, or continue
          the investigation.
        </div>
      )}
      <div className="detail-grid">
        <div className="min-w-0">
          <Tabs value={tab} onValueChange={setTab} className="gap-5">
            <TabsList
              variant="line"
              className="h-auto w-full justify-start gap-1 overflow-x-auto border-b border-border pb-0"
            >
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="alerts">
                Alerts{' '}
                <span className="ml-1 hidden font-mono text-[9px] text-muted-foreground sm:inline">
                  {alerts.data?.total ?? '—'}
                </span>
              </TabsTrigger>
              <TabsTrigger value="evidence">
                Evidence{' '}
                <span className="ml-1 hidden font-mono text-[9px] text-muted-foreground sm:inline">
                  {evidence.data?.total ?? '—'}
                </span>
              </TabsTrigger>
              <TabsTrigger value="notes">
                Notes{' '}
                <span className="ml-1 hidden font-mono text-[9px] text-muted-foreground sm:inline">
                  {notes.data?.total ?? '—'}
                </span>
              </TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="space-y-5">
              <Panel
                title="Investigation summary"
                actions={
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={closed}
                    onClick={() => setAction({ kind: 'details' })}
                  >
                    <Pencil />
                    Edit summary
                  </Button>
                }
              >
                <div className="p-5">
                  <p className="record-text">
                    {item.summary ||
                      'No investigation summary yet. Add context as you validate this case.'}
                  </p>
                </div>
              </Panel>
              <div className="grid grid-cols-3 gap-3">
                {[
                  {
                    name: 'Linked alerts',
                    value: alerts.data?.total,
                    icon: Link2,
                    tab: 'alerts',
                  },
                  {
                    name: 'Evidence records',
                    value: evidence.data?.total,
                    icon: Fingerprint,
                    tab: 'evidence',
                  },
                  {
                    name: 'Analyst notes',
                    value: notes.data?.total,
                    icon: FileText,
                    tab: 'notes',
                  },
                ].map(({ name, value, icon: Icon, tab: target }) => (
                  <button
                    key={name}
                    className="rounded-xl border bg-card p-5 text-left hover:border-primary/30 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
                    onClick={() => setTab(target)}
                  >
                    <Icon
                      className="mb-4 size-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <p className="font-mono text-xl">{value ?? '—'}</p>
                    <p className="mt-1.5 text-[11px] text-muted-foreground">
                      {name}
                    </p>
                  </button>
                ))}
              </div>
              <Panel
                title="Recent activity"
                description="A record of who changed what, and why"
                actions={
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setTab('history')}
                  >
                    Full history
                    <ArrowRight />
                  </Button>
                }
              >
                {history.error ? (
                  <div className="p-5">
                    <ErrorPanel
                      error={history.error}
                      retry={() => void history.refetch()}
                    />
                  </div>
                ) : history.isPending ? (
                  <div className="p-5">
                    <LoadingPanel message="Loading case activity" />
                  </div>
                ) : (
                  <HistoryEvents
                    items={history.data?.items.slice(0, 3) ?? []}
                    compact
                  />
                )}
              </Panel>
            </TabsContent>
            <TabsContent value="alerts">
              <Panel
                title="Linked alerts"
                description="Signals attached to this investigation"
                actions={
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={closed}
                    onClick={() => setAction({ kind: 'link-alert' })}
                  >
                    <Link2 />
                    Link alert
                  </Button>
                }
              >
                {alerts.error ? (
                  <div className="p-5">
                    <ErrorPanel
                      error={alerts.error}
                      retry={() => void alerts.refetch()}
                    />
                  </div>
                ) : alerts.isPending ? (
                  <div className="p-5">
                    <LoadingPanel message="Loading linked alerts" />
                  </div>
                ) : (
                  alerts.data && (
                    <>
                      {alerts.data.items.length ? (
                        alerts.data.items.map((alert) => (
                          <div className="signal-card" key={alert.id}>
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0">
                                <Link
                                  to={`/alerts/${alert.id}`}
                                  className="text-[13px] font-medium hover:text-primary"
                                >
                                  {alert.title}
                                </Link>
                                <p className="mt-2 break-all font-mono text-[10px] text-muted-foreground">
                                  {alert.external_alert_id}
                                </p>
                              </div>
                              <SeverityBadge severity={alert.severity} />
                            </div>
                            <p className="mt-3 text-[11px] leading-6 text-muted-foreground">
                              {alert.host ?? 'Host not provided'} ·{' '}
                              {dateTime(alert.observed_at)}
                            </p>
                            <p className="mt-2 text-xs text-muted-foreground">
                              Relationship: {alert.reason}
                            </p>
                            <div className="mt-4 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={closed}
                                onClick={() =>
                                  setAction({ kind: 'evidence', alert })
                                }
                              >
                                <Fingerprint />
                                Preserve as evidence
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={closed}
                                onClick={() =>
                                  setAction({ kind: 'unlink-alert', alert })
                                }
                              >
                                Unlink alert
                              </Button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <EmptyPanel
                          title="No linked alerts"
                          description="Attach a signal to connect this case to its source context."
                        />
                      )}
                      <Pager
                        {...alerts.data}
                        label="linked alerts"
                        change={(offset) => changePage('alerts', offset)}
                      />
                    </>
                  )
                )}
              </Panel>
            </TabsContent>
            <TabsContent value="evidence">
              <Panel
                title="Preserved evidence"
                description="Source references, acquisition times, and immutable snapshots"
                actions={
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={closed}
                    onClick={() => setAction({ kind: 'evidence' })}
                  >
                    <Plus />
                    Add evidence
                  </Button>
                }
              >
                {evidence.error ? (
                  <div className="p-5">
                    <ErrorPanel
                      error={evidence.error}
                      retry={() => void evidence.refetch()}
                    />
                  </div>
                ) : evidence.isPending ? (
                  <div className="p-5">
                    <LoadingPanel message="Loading preserved evidence" />
                  </div>
                ) : (
                  evidence.data && (
                    <>
                      {evidence.data.items.length ? (
                        evidence.data.items.map((entry) => (
                          <div
                            key={entry.id}
                            className="evidence-card"
                            data-unlinked={!!entry.unlinked_at}
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="break-all text-[13px] font-medium">
                                  {entry.source_event_id}
                                </p>
                                <p className="mt-1 text-[11px] text-muted-foreground">
                                  {entry.provider} / {entry.provider_scope}
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <Badge
                                  variant="outline"
                                  className="text-[9px] text-muted-foreground"
                                >
                                  {label(entry.sensitivity)}
                                </Badge>
                                {entry.unlinked_at && (
                                  <Badge
                                    variant="outline"
                                    className="text-[9px] text-muted-foreground"
                                  >
                                    Unlinked · retained
                                  </Badge>
                                )}
                              </div>
                            </div>
                            <div className="mt-3">
                              <SourceReference value={entry.source_ref} />
                            </div>
                            <dl className="mt-4 grid gap-3 text-[10px] sm:grid-cols-2">
                              <div>
                                <dt className="text-muted-foreground">
                                  EVENT TIME
                                </dt>
                                <dd className="mt-1">
                                  {dateTime(entry.observed_at)}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-muted-foreground">
                                  ACQUIRED
                                </dt>
                                <dd className="mt-1">
                                  {dateTime(entry.acquired_at)}
                                  {entry.acquired_by_handle &&
                                    ` · ${entry.acquired_by_handle}`}
                                </dd>
                              </div>
                            </dl>
                            {entry.snapshot !== null ? (
                              <details className="mt-4">
                                <summary className="cursor-pointer text-xs text-primary">
                                  Inspect preserved snapshot
                                </summary>
                                <pre className="snapshot">
                                  {entry.snapshot || '(Empty excerpt)'}
                                </pre>
                                <div className="mt-3">
                                  <p className="text-[9px] tracking-wider text-muted-foreground">
                                    SHA-256 / PRESERVED CONTENT
                                  </p>
                                  <code className="mt-1 block break-all font-mono text-[10px] text-muted-foreground">
                                    {entry.snapshot_sha256}
                                  </code>
                                </div>
                              </details>
                            ) : (
                              <p className="mt-4 text-[11px] text-muted-foreground">
                                Reference-only evidence. No snapshot was stored.
                              </p>
                            )}
                            {!entry.unlinked_at && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="mt-4"
                                disabled={closed}
                                onClick={() =>
                                  setAction({
                                    kind: 'unlink-evidence',
                                    evidence: entry,
                                  })
                                }
                              >
                                Unlink evidence
                              </Button>
                            )}
                          </div>
                        ))
                      ) : (
                        <EmptyPanel
                          title="No evidence preserved yet"
                          description="Keep a bounded excerpt or source reference so the case retains its context."
                        />
                      )}
                      <Pager
                        {...evidence.data}
                        label="evidence records"
                        change={(offset) => changePage('evidence', offset)}
                      />
                    </>
                  )
                )}
              </Panel>
            </TabsContent>
            <TabsContent value="notes">
              <Panel
                title="Analyst notes"
                description="Observations, reasoning, and retained revisions"
                actions={
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={closed}
                    onClick={() => setAction({ kind: 'note' })}
                  >
                    <Plus />
                    Add note
                  </Button>
                }
              >
                {notes.error ? (
                  <div className="p-5">
                    <ErrorPanel
                      error={notes.error}
                      retry={() => void notes.refetch()}
                    />
                  </div>
                ) : notes.isPending ? (
                  <div className="p-5">
                    <LoadingPanel message="Loading analyst notes" />
                  </div>
                ) : (
                  notes.data && (
                    <>
                      {notes.data.items.length ? (
                        notes.data.items.map((note) => (
                          <article key={note.id} className="note-card">
                            <div className="mb-4 flex items-center gap-3">
                              <div className="profile-avatar">
                                {note.author_handle.slice(0, 2).toUpperCase()}
                              </div>
                              <div>
                                <h3 className="text-xs font-medium">
                                  {note.author_handle}
                                </h3>
                                <p className="mt-1 text-[10px] text-muted-foreground">
                                  {dateTime(note.edited_at ?? note.created_at)}{' '}
                                  · Revision {note.revision}
                                </p>
                              </div>
                              {note.author_id === session.data?.actor.id && (
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  className="ml-auto"
                                  disabled={closed}
                                  aria-label={`Edit note by ${note.author_handle}`}
                                  onClick={() =>
                                    setAction({ kind: 'note', note })
                                  }
                                >
                                  <Pencil />
                                </Button>
                              )}
                            </div>
                            <p className="record-text">{note.body}</p>
                          </article>
                        ))
                      ) : (
                        <EmptyPanel
                          title="Make your reasoning visible"
                          description="Add an analyst note to record observations, validation, and next steps."
                        />
                      )}
                      <Pager
                        {...notes.data}
                        label="notes"
                        change={(offset) => changePage('notes', offset)}
                      />
                    </>
                  )
                )}
              </Panel>
            </TabsContent>
            <TabsContent value="history">
              <Panel
                title="Audit history"
                description="Newest first · committed case versions with actor attribution"
              >
                {history.error ? (
                  <div className="p-5">
                    <ErrorPanel
                      error={history.error}
                      retry={() => void history.refetch()}
                    />
                  </div>
                ) : history.isPending ? (
                  <div className="p-5">
                    <LoadingPanel message="Loading audit history" />
                  </div>
                ) : (
                  history.data && (
                    <>
                      <HistoryEvents items={history.data.items} />
                      <Pager
                        {...history.data}
                        label="audit events"
                        change={(offset) => changePage('timeline', offset)}
                      />
                    </>
                  )
                )}
              </Panel>
            </TabsContent>
          </Tabs>
        </div>
        <aside className="space-y-5" aria-label="Case context">
          <Panel title="Case owner">
            <div className="p-5">
              <div className="flex items-center gap-3">
                <div className="profile-avatar">
                  <UserRound className="size-4" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-xs font-medium">
                    {item.owner_handle ?? 'Unassigned'}
                  </p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {item.owner_handle
                      ? 'Assigned analyst'
                      : 'Ready for analyst ownership'}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="mt-4 w-full"
                disabled={closed}
                onClick={() => setAction({ kind: 'assignment' })}
              >
                Manage assignment
              </Button>
            </div>
          </Panel>
          <Panel title="Analyst disposition">
            <div className="p-5">
              <ShieldCheck
                className="mb-3 size-5 text-primary"
                aria-hidden="true"
              />
              <p className="text-sm font-medium">
                {item.disposition
                  ? label(item.disposition)
                  : 'Review in progress'}
              </p>
              <p className="mt-2 text-[11px] leading-6 text-muted-foreground">
                {item.disposition
                  ? 'A human-reviewed case decision. Previous decisions remain in audit history.'
                  : 'A disposition is recorded when an analyst resolves this case.'}
              </p>
            </div>
          </Panel>
          <Panel title="Case record">
            <dl className="fact-list">
              <div>
                <dt>Created</dt>
                <dd>{dateTime(item.created_at)}</dd>
              </div>
              <div>
                <dt>Last activity</dt>
                <dd>{dateTime(item.updated_at)}</dd>
              </div>
              <div>
                <dt>Record version</dt>
                <dd className="font-mono">{item.version}</dd>
              </div>
              <div>
                <dt>Sources</dt>
                <dd>{item.sources.join(', ') || 'Manual'}</dd>
              </div>
            </dl>
          </Panel>
          <div className="rounded-lg border border-dashed px-4 py-4">
            <p className="text-[11px] font-medium">
              AI assistance is not enabled
            </p>
            <p className="mt-2 text-[10px] leading-6 text-muted-foreground">
              This investigation contains analyst decisions and preserved
              evidence. No AI assessment has been generated.
            </p>
          </div>
        </aside>
      </div>
      <Modal
        restoreFocus={() => {
          const target = returnFocus.current
          if (target?.isConnected && target !== document.body)
            target.focus({ preventScroll: true })
          else
            document
              .querySelector<HTMLElement>('[role="tab"][data-state="active"]')
              ?.focus({ preventScroll: true })
        }}
        open={!!action}
        onOpenChange={(open) => {
          if (!open) close()
        }}
        title={title}
        description={`Changes to ${item.display_id} are attributed to your local analyst identity.`}
      >
        {action?.kind === 'details' ? (
          <EditCaseForm record={item} close={close} />
        ) : action?.kind === 'assignment' ? (
          <AssignmentForm record={item} close={close} />
        ) : action?.kind === 'status' ? (
          <TransitionForm record={item} close={close} />
        ) : action?.kind === 'note' ? (
          <NoteForm record={item} note={action.note} close={close} />
        ) : action?.kind === 'evidence' ? (
          <EvidenceForm
            record={item}
            alert={action.alert}
            close={() => {
              setTab('evidence')
              close()
            }}
          />
        ) : action?.kind === 'link-alert' ? (
          <LinkAlertForm record={item} close={close} />
        ) : action?.kind === 'unlink-alert' ? (
          <UnlinkForm
            record={item}
            path={`/cases/${id}/alerts/${action.alert.id}`}
            noun="alert"
            close={close}
          />
        ) : action?.kind === 'unlink-evidence' ? (
          <UnlinkForm
            record={item}
            path={`/cases/${id}/evidence/${action.evidence.id}`}
            noun="evidence"
            close={close}
          />
        ) : null}
      </Modal>
    </>
  )
}

function HistoryEvents({
  items,
  compact = false,
}: {
  items: Schema['EventOut'][]
  compact?: boolean
}) {
  if (!items.length)
    return (
      <EmptyPanel
        title="No activity in this view"
        description="Committed changes appear here with their actor and reason."
      />
    )
  return (
    <>
      {items.map((event) => (
        <article className="timeline-item" key={event.id}>
          <div className="flex items-start gap-3">
            <span
              className="timeline-marker"
              aria-label={`Case version ${event.case_version}`}
            >
              {event.case_version}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap justify-between gap-2">
                <h3 className="text-xs font-medium">{label(event.action)}</h3>
                <time
                  className="font-mono text-[9px] text-muted-foreground"
                  dateTime={event.occurred_at}
                >
                  {dateTime(event.occurred_at)}
                </time>
              </div>
              <p className="mt-2 break-words text-xs leading-6 text-muted-foreground">
                {event.reason}
              </p>
              <p className="mt-2 text-[10px] text-muted-foreground">
                <span className="text-foreground">{event.actor_handle}</span> ·{' '}
                {event.actor_kind === 'human' ? 'Analyst' : 'Service'}
              </p>
              {!compact && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-[11px] text-primary">
                    View change details
                  </summary>
                  <div className="mt-3 grid min-w-0 gap-3 md:grid-cols-2">
                    <div className="min-w-0">
                      <p className="mb-2 text-[9px] text-muted-foreground">
                        BEFORE
                      </p>
                      <pre className="audit-json">
                        {event.before
                          ? JSON.stringify(event.before, null, 2)
                          : 'No previous state'}
                      </pre>
                    </div>
                    <div className="min-w-0">
                      <p className="mb-2 text-[9px] text-muted-foreground">
                        AFTER
                      </p>
                      <pre className="audit-json">
                        {event.after
                          ? JSON.stringify(event.after, null, 2)
                          : 'No new state'}
                      </pre>
                    </div>
                  </div>
                  <p className="mt-3 break-all font-mono text-[9px] text-muted-foreground">
                    REQUEST {event.correlation_id}
                  </p>
                </details>
              )}
            </div>
          </div>
        </article>
      ))}
    </>
  )
}
