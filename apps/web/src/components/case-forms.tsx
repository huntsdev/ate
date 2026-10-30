import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { LoaderCircle, Plus, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Choice, ErrorPanel, TextField } from '@/components/workspace'
import {
  ApiError,
  field,
  label,
  localDateInput,
  request,
  severities,
  useData,
  useSession,
  write,
} from '@/lib/api'
import type {
  AlertRecord,
  CaseRecord,
  CaseStatus,
  Schema,
  Severity,
} from '@/lib/api'
import { useNotice } from '@/lib/notice'

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  trigger,
  children,
  restoreFocus,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  trigger?: ReactNode
  children: ReactNode
  restoreFocus?: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
      <DialogContent
        className="max-h-[90dvh] overflow-y-auto sm:max-w-[640px]"
        onCloseAutoFocus={
          restoreFocus
            ? (event) => {
                event.preventDefault()
                restoreFocus()
              }
            : undefined
        }
      >
        <DialogHeader>
          <p className="eyebrow mb-1">ANALYST ACTION</p>
          <DialogTitle className="pr-6 text-xl tracking-tight">
            {title}
          </DialogTitle>
          <DialogDescription className="leading-6">
            {description}
          </DialogDescription>
        </DialogHeader>
        {open && children}
      </DialogContent>
    </Dialog>
  )
}

export function useCommand<T>({
  record,
  onDone,
  message,
}: {
  record?: CaseRecord
  onDone: (result: T) => void
  message: string
}) {
  const [version, setVersion] = useState(record?.version)
  const [hint, setHint] = useState('')
  const [reloading, setReloading] = useState(false)
  const session = useSession()
  const queryClient = useQueryClient()
  const notify = useNotice()
  const mutation = useMutation({
    mutationFn: ({
      path,
      method = 'POST',
      body,
    }: {
      path: string
      method?: string
      body: object
    }) => {
      if (!session.data)
        throw new Error(
          'The local session is unavailable. Check system status and retry.',
        )
      return write<T>(
        path,
        method,
        { ...body, ...(record ? { expected_version: version } : {}) },
        session.data.csrf_token,
      )
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({
        predicate: (query) =>
          ['dashboard', 'cases', 'case', 'alerts', 'alert'].includes(
            String(query.queryKey[0]),
          ),
      })
      onDone(result)
      notify(message)
    },
  })
  const problem =
    mutation.error instanceof ApiError ? mutation.error.problem : null
  const conflict = problem?.code === 'version_conflict'
  async function reload() {
    setReloading(true)
    try {
      if (problem?.code === 'csrf_invalid') {
        const result = await session.refetch()
        if (!result.data || result.error)
          throw new Error('The local session could not be refreshed.')
      } else if (record) {
        const latest = await request<CaseRecord>(`/cases/${record.id}`)
        queryClient.setQueryData(['case', record.id], latest)
        setVersion(latest.version)
      }
      mutation.reset()
      setHint(
        'Latest data loaded. Your draft is preserved. Review it before saving.',
      )
    } catch (error) {
      setHint(error instanceof Error ? error.message : 'Reload failed.')
    } finally {
      setReloading(false)
    }
  }
  return {
    mutation,
    version,
    busy: mutation.isPending || session.isPending,
    feedback: (
      <>
        {(mutation.error || session.error) && (
          <ErrorPanel error={mutation.error ?? session.error} />
        )}
        {(conflict || problem?.code === 'csrf_invalid') && (
          <Button
            type="button"
            variant="outline"
            onClick={() => void reload()}
            disabled={reloading}
          >
            <RefreshCw className={reloading ? 'animate-spin' : ''} />
            {problem?.code === 'csrf_invalid'
              ? 'Reload local session'
              : 'Reload latest case'}
          </Button>
        )}
        {hint && (
          <p role="status" className="form-hint">
            {hint}
          </p>
        )}
      </>
    ),
    blocked: conflict || !session.data || mutation.isPending || reloading,
  }
}

export function SaveButton({
  busy,
  disabled,
  children,
}: {
  busy: boolean
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <div className="form-footer">
      <p>Saved with analyst attribution.</p>
      <Button type="submit" disabled={disabled || busy}>
        {busy && <LoaderCircle className="animate-spin" aria-hidden="true" />}
        {busy ? 'Saving…' : children}
      </Button>
    </div>
  )
}

export function TextAreaField({
  id,
  label: text,
  help,
  ...props
}: React.ComponentProps<typeof Textarea> & {
  id: string
  label: string
  help?: string
}) {
  return (
    <div className="field">
      <Label htmlFor={id}>{text}</Label>
      <Textarea
        id={id}
        aria-describedby={help ? `${id}-help` : undefined}
        {...props}
      />
      {help && (
        <p id={`${id}-help`} className="field-help">
          {help}
        </p>
      )}
    </div>
  )
}

export function NewCaseDialog({
  alert,
  trigger,
}: {
  alert?: AlertRecord
  trigger?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <Modal
      open={open}
      onOpenChange={setOpen}
      title="Create case"
      description={
        alert
          ? 'Open an investigation with this alert linked as its first signal.'
          : 'Start an analyst-owned investigation. Link alerts and preserve evidence as you review.'
      }
      trigger={
        trigger ?? (
          <Button>
            <Plus />
            New case
          </Button>
        )
      }
    >
      <CreateCaseForm alert={alert} close={() => setOpen(false)} />
    </Modal>
  )
}

function CreateCaseForm({
  alert,
  close,
}: {
  alert?: AlertRecord
  close: () => void
}) {
  const navigate = useNavigate()
  const command = useCommand<CaseRecord>({
    message: 'Case created. Ready for investigation.',
    onDone: (record) => {
      close()
      void navigate(`/cases/${record.id}`)
    },
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const body: Schema['CreateCase'] = {
      title: field(data, 'title'),
      summary: field(data, 'summary'),
      severity: field(data, 'severity') as Severity,
      ...(alert ? { alert_id: alert.id } : {}),
    }
    command.mutation.mutate({ path: '/cases', body })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <TextField
        id="new-case-title"
        name="title"
        label="Case title"
        required
        maxLength={256}
        defaultValue={alert?.title}
        placeholder="A concise description of the investigation"
      />
      <Choice
        id="new-case-severity"
        name="severity"
        label="Severity"
        defaultValue={alert?.severity ?? 'medium'}
        options={severities.map((value) => ({ value, label: label(value) }))}
      />
      <TextAreaField
        id="new-case-summary"
        name="summary"
        label="Investigation summary"
        defaultValue={alert?.summary}
        maxLength={8192}
        rows={4}
        placeholder="What triggered the review? What context should other analysts know?"
      />
      {alert && (
        <div className="subtle-callout">
          <span className="case-number">LINKED ON CREATION</span>
          <p className="mt-1 text-sm">{alert.title}</p>
        </div>
      )}
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked}>
        Create case
      </SaveButton>
    </form>
  )
}

export function ImportAlertDialog() {
  const [open, setOpen] = useState(false)
  return (
    <Modal
      open={open}
      onOpenChange={setOpen}
      title="Import synthetic alert"
      description="Add a synthetic signal for a local investigation. Reusing an alert ID opens the existing record."
      trigger={
        <Button variant="outline">
          <Plus />
          Import synthetic alert
        </Button>
      }
    >
      <ImportAlertForm close={() => setOpen(false)} />
    </Modal>
  )
}

function ImportAlertForm({ close }: { close: () => void }) {
  const navigate = useNavigate()
  const [externalId] = useState(() => `manual-${crypto.randomUUID()}`)
  const command = useCommand<Schema['AlertImport']>({
    message: 'Synthetic alert is available in the queue.',
    onDone: (result) => {
      close()
      void navigate(`/alerts/${result.alert.id}`)
    },
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const body: Schema['SyntheticAlert'] = {
      provider: 'synthetic',
      provider_scope: 'manual',
      source_ref: `synthetic://manual/${encodeURIComponent(field(data, 'external_alert_id'))}`,
      title: field(data, 'title'),
      severity: field(data, 'severity') as Severity,
      external_alert_id: field(data, 'external_alert_id'),
      observed_at: new Date(field(data, 'observed_at')).toISOString(),
      host: field(data, 'host') || null,
      summary: field(data, 'summary'),
    }
    command.mutation.mutate({ path: '/alerts', body })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <TextField
        id="alert-title"
        name="title"
        label="Alert title"
        required
        maxLength={256}
        placeholder="Synthetic suspicious process activity"
      />
      <div className="form-columns">
        <Choice
          id="alert-severity"
          name="severity"
          label="Severity"
          defaultValue="medium"
          options={severities.map((value) => ({ value, label: label(value) }))}
        />
        <TextField
          id="alert-observed"
          name="observed_at"
          label="Event time (local)"
          type="datetime-local"
          defaultValue={localDateInput()}
          required
        />
      </div>
      <TextField
        id="alert-host"
        name="host"
        label="Synthetic host"
        defaultValue="workstation.example.invalid"
        maxLength={256}
        help="Use a reserved .invalid hostname for synthetic data."
      />
      <TextAreaField
        id="alert-summary"
        name="summary"
        label="Alert context"
        maxLength={8192}
        rows={4}
        placeholder="Preserve the context you want an analyst to review."
      />
      <TextField
        id="alert-external-id"
        name="external_alert_id"
        label="Synthetic alert ID"
        defaultValue={externalId}
        required
        maxLength={256}
      />
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked}>
        Import alert
      </SaveButton>
    </form>
  )
}

export function EditCaseForm({
  record,
  close,
}: {
  record: CaseRecord
  close: () => void
}) {
  const command = useCommand<CaseRecord>({
    record,
    onDone: close,
    message: 'Case details updated.',
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    command.mutation.mutate({
      path: `/cases/${record.id}`,
      method: 'PATCH',
      body: {
        title: field(data, 'title'),
        severity: field(data, 'severity'),
        summary: field(data, 'summary'),
        reason: field(data, 'reason'),
      },
    })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <TextField
        id="edit-title"
        name="title"
        label="Case title"
        required
        maxLength={256}
        defaultValue={record.title}
      />
      <Choice
        id="edit-severity"
        name="severity"
        label="Severity"
        defaultValue={record.severity}
        options={severities.map((value) => ({ value, label: label(value) }))}
      />
      <TextAreaField
        id="edit-summary"
        name="summary"
        label="Investigation summary"
        maxLength={8192}
        rows={5}
        defaultValue={record.summary}
      />
      <TextField
        id="edit-reason"
        name="reason"
        label="Reason for change"
        required
        maxLength={1000}
      />
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked}>
        Save case details
      </SaveButton>
    </form>
  )
}

export function TransitionForm({
  record,
  close,
}: {
  record: CaseRecord
  close: () => void
}) {
  const [target, setTarget] = useState<CaseStatus>(
    record.allowed_transitions[0] ?? 'investigating',
  )
  const [disposition, setDisposition] = useState('')
  const command = useCommand<CaseRecord>({
    record,
    onDone: close,
    message: 'Case status updated. Analyst decision recorded.',
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    command.mutation.mutate({
      path: `/cases/${record.id}/transitions`,
      body: {
        status: target,
        reason: field(data, 'reason'),
        ...(target === 'resolved' ? { disposition } : {}),
      },
    })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <div className="subtle-callout text-sm">
        Current status: <strong>{label(record.status)}</strong>
        {['closed', 'resolved'].includes(record.status) && (
          <p className="mt-2 text-xs text-muted-foreground">
            Reopening clears the current disposition. The previous decision
            remains in history.
          </p>
        )}
      </div>
      <Choice
        id="transition-status"
        label="Next status"
        value={target}
        onValueChange={(value) => setTarget(value as CaseStatus)}
        options={record.allowed_transitions.map((value) => ({
          value,
          label:
            value === 'investigating' &&
            ['closed', 'resolved'].includes(record.status)
              ? 'Reopen investigation'
              : label(value),
        }))}
      />
      {target === 'resolved' && (
        <>
          <Choice
            id="transition-disposition"
            label="Analyst disposition"
            value={disposition}
            onValueChange={setDisposition}
            placeholder="Select an analyst disposition"
            options={[
              'true_positive',
              'benign_positive',
              'false_positive',
              'inconclusive',
            ].map((value) => ({ value, label: label(value) }))}
          />
          <p className="field-help">
            This is your reviewed decision. No AI recommendation is used.
          </p>
        </>
      )}
      <TextAreaField
        id="transition-reason"
        name="reason"
        label="Decision rationale"
        required
        maxLength={1000}
        rows={3}
        placeholder="Record the evidence and reasoning behind this change."
      />
      {command.feedback}
      <SaveButton
        busy={command.busy}
        disabled={command.blocked || (target === 'resolved' && !disposition)}
      >
        Confirm status change
      </SaveButton>
    </form>
  )
}

export function AssignmentForm({
  record,
  close,
}: {
  record: CaseRecord
  close: () => void
}) {
  const users = useData<Schema['UserOut'][]>(['users'], '/users')
  const command = useCommand<CaseRecord>({
    record,
    onDone: close,
    message: 'Case assignment updated.',
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    command.mutation.mutate({
      path: `/cases/${record.id}/assignment`,
      body: {
        assignee_id:
          field(data, 'assignee') === 'unassigned'
            ? null
            : field(data, 'assignee'),
        reason: field(data, 'reason'),
      },
    })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <Choice
        id="assignment-owner"
        name="assignee"
        label="Case owner"
        defaultValue={record.assigned_to ?? 'unassigned'}
        options={[
          { value: 'unassigned', label: 'Unassigned' },
          ...(users.data ?? []).map((user) => ({
            value: user.id,
            label: user.handle,
          })),
        ]}
      />
      <TextField
        id="assignment-reason"
        name="reason"
        label="Assignment reason"
        defaultValue="Assigned for analyst review"
        required
        maxLength={1000}
      />
      {users.error && (
        <ErrorPanel error={users.error} retry={() => void users.refetch()} />
      )}
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked || !users.data}>
        Save assignment
      </SaveButton>
    </form>
  )
}

export function NoteForm({
  record,
  note,
  close,
}: {
  record: CaseRecord
  note?: Schema['NoteOut']
  close: () => void
}) {
  const command = useCommand<Schema['CaseMutation']>({
    record,
    onDone: close,
    message: note
      ? 'Note revision saved. Previous text is retained in history.'
      : 'Analyst note added.',
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    command.mutation.mutate({
      path: `/cases/${record.id}/notes${note ? `/${note.id}` : ''}`,
      method: note ? 'PATCH' : 'POST',
      body: {
        body: field(data, 'body'),
        ...(note ? { reason: field(data, 'reason') } : {}),
      },
    })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <TextAreaField
        id="note-body"
        name="body"
        label="Analyst note"
        required
        maxLength={16384}
        defaultValue={note?.body}
        rows={7}
        placeholder="What did you observe? What did you validate?"
        help="Plain text. Notes retain their author and revision history."
      />
      {note && (
        <TextField
          id="note-reason"
          name="reason"
          label="Revision reason"
          required
          maxLength={1000}
        />
      )}
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked}>
        {note ? 'Save note revision' : 'Add note'}
      </SaveButton>
    </form>
  )
}

export function EvidenceForm({
  record,
  alert,
  close,
}: {
  record: CaseRecord
  alert?: AlertRecord
  close: () => void
}) {
  const command = useCommand<Schema['CaseMutation']>({
    record,
    onDone: close,
    message: 'Evidence preserved with source provenance.',
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    command.mutation.mutate({
      path: `/cases/${record.id}/evidence`,
      body: {
        provider: field(data, 'provider'),
        provider_scope: field(data, 'scope'),
        source_event_id: field(data, 'event_id'),
        source_ref: field(data, 'source_ref'),
        observed_at: new Date(field(data, 'observed_at')).toISOString(),
        sensitivity: field(data, 'sensitivity'),
        snapshot: field(data, 'snapshot') || null,
        reason: field(data, 'reason'),
      },
    })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <div className="form-columns">
        <TextField
          id="evidence-provider"
          name="provider"
          label="Source provider"
          defaultValue={alert?.provider ?? 'synthetic'}
          required
          maxLength={256}
        />
        <TextField
          id="evidence-scope"
          name="scope"
          label="Source scope"
          defaultValue={alert?.provider_scope ?? 'manual'}
          required
          maxLength={256}
        />
      </div>
      <TextField
        id="evidence-event"
        name="event_id"
        label="Source event ID"
        defaultValue={alert?.external_alert_id}
        required
        maxLength={256}
      />
      <TextField
        id="evidence-reference"
        name="source_ref"
        label="Source reference"
        defaultValue={alert?.source_ref ?? 'synthetic://manual/evidence'}
        required
        maxLength={2048}
      />
      <div className="form-columns">
        <TextField
          id="evidence-observed"
          name="observed_at"
          label="Event time (local)"
          type="datetime-local"
          defaultValue={localDateInput(alert?.observed_at)}
          required
        />
        <Choice
          id="evidence-sensitivity"
          name="sensitivity"
          label="Sensitivity"
          defaultValue={
            alert?.provider === 'synthetic' ? 'synthetic' : 'internal'
          }
          options={['synthetic', 'internal', 'restricted'].map((value) => ({
            value,
            label: label(value),
          }))}
        />
      </div>
      <TextAreaField
        id="evidence-snapshot"
        name="snapshot"
        label="Preserved excerpt"
        maxLength={16384}
        defaultValue={alert?.summary}
        rows={4}
        help="Optional bounded text snapshot. A source reference remains available without an excerpt."
      />
      <TextField
        id="evidence-reason"
        name="reason"
        label="Preservation reason"
        defaultValue="Preserve investigation evidence"
        required
        maxLength={1000}
      />
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked}>
        Preserve evidence
      </SaveButton>
    </form>
  )
}

export function UnlinkForm({
  record,
  path,
  noun,
  close,
}: {
  record: CaseRecord
  path: string
  noun: 'alert' | 'evidence'
  close: () => void
}) {
  const command = useCommand<Schema['CaseMutation']>({
    record,
    onDone: close,
    message: `${label(noun)} unlinked. Provenance is retained in history.`,
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    command.mutation.mutate({
      path,
      method: 'DELETE',
      body: { reason: field(data, 'reason') },
    })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <p className="text-sm leading-6 text-muted-foreground">
        This removes the {noun} from the active investigation.{' '}
        {noun === 'evidence'
          ? 'Its preserved content and source remain available.'
          : 'The original alert remains in the alert queue.'}{' '}
        The change is recorded in the case history.
      </p>
      <TextAreaField
        id="unlink-reason"
        name="reason"
        label="Unlink reason"
        required
        maxLength={1000}
        rows={3}
      />
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked}>
        Unlink {noun}
      </SaveButton>
    </form>
  )
}

export function LinkAlertForm({
  record,
  close,
}: {
  record: CaseRecord
  close: () => void
}) {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState('')
  const alerts = useData<Schema['AlertPage']>(
    ['alerts', 'picker', search],
    `/alerts?limit=50&q=${encodeURIComponent(search)}`,
  )
  const command = useCommand<Schema['CaseMutation']>({
    record,
    onDone: close,
    message: 'Alert linked to the investigation.',
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    command.mutation.mutate({
      path: `/cases/${record.id}/alerts`,
      body: { alert_id: selected, reason: field(data, 'reason') },
    })
  }
  return (
    <form onSubmit={submit} className="action-form">
      <TextField
        id="link-alert-search"
        label="Search alerts"
        value={search}
        onChange={(event) => {
          setSearch(event.target.value)
          setSelected('')
        }}
        maxLength={200}
      />
      <Choice
        id="link-alert-selection"
        label="Alert to link"
        value={selected}
        onValueChange={setSelected}
        placeholder="Select an alert"
        options={(alerts.data?.items ?? []).map((alert) => ({
          value: alert.id,
          label: alert.title,
        }))}
      />
      <TextField
        id="link-alert-reason"
        name="reason"
        label="Link reason"
        required
        maxLength={1000}
        defaultValue="Related to this investigation"
      />
      {alerts.error && (
        <ErrorPanel error={alerts.error} retry={() => void alerts.refetch()} />
      )}
      {command.feedback}
      <SaveButton busy={command.busy} disabled={command.blocked || !selected}>
        Link alert
      </SaveButton>
    </form>
  )
}
