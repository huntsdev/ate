import type { ReactNode } from 'react'
import { Link } from 'react-router'
import {
  AlertCircle,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  LoaderCircle,
  RotateCcw,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ApiError, label, shortDate } from '@/lib/api'
import type { CaseRecord, CaseStatus, Severity } from '@/lib/api'

export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string
  title: string
  description: string
  actions?: ReactNode
}) {
  return (
    <div className="page-heading">
      <div className="min-w-0">
        <p className="eyebrow">
          <span />
          {eyebrow}
        </p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  )
}

export function StateBadge({ status }: { status: CaseStatus }) {
  return (
    <Badge variant="outline" className={`state-badge status-${status}`}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {label(status)}
    </Badge>
  )
}
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`severity severity-${severity}`}>
      <span className="severity-bars" aria-hidden="true">
        {[1, 2, 3, 4].map((number) => (
          <i
            key={number}
            style={{
              height: `${4 + number * 2}px`,
              opacity:
                number <= { low: 1, medium: 2, high: 3, critical: 4 }[severity]
                  ? 1
                  : 0.2,
            }}
          />
        ))}
      </span>
      {label(severity)}
    </span>
  )
}

export function ErrorPanel({
  error,
  retry,
}: {
  error: unknown
  retry?: () => void
}) {
  const problem = error instanceof ApiError ? error.problem : null
  return (
    <div role="alert" className="issue-panel">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">
          {error instanceof Error
            ? error.message
            : 'The workspace is unavailable.'}
        </p>
        {problem?.errors?.length ? (
          <p className="mt-2 text-xs">
            {problem.errors
              .map((item) => item.field.replace('body.', ''))
              .join(', ')}
          </p>
        ) : null}
        {problem?.correlation_id && (
          <p className="mt-2 break-all font-mono text-[10px] opacity-80">
            Reference {problem.correlation_id}
          </p>
        )}
        {retry && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={retry}
          >
            <RotateCcw />
            Try again
          </Button>
        )}
      </div>
    </div>
  )
}

export function LoadingPanel({
  message = 'Loading workspace',
}: {
  message?: string
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="space-y-4"
    >
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        {message}
      </span>
      <Skeleton className="h-24 rounded-xl" />
      <Skeleton className="h-48 rounded-xl" />
    </div>
  )
}

export function EmptyPanel({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <div className="empty-panel">
      <div className="empty-icon">
        <FolderOpen className="size-6" aria-hidden="true" />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {children && <div className="mt-5">{children}</div>}
    </div>
  )
}

export function Choice({
  id,
  name,
  label: text,
  options,
  defaultValue,
  value,
  onValueChange,
  placeholder = 'Choose an option',
  disabled = false,
}: {
  id: string
  name?: string
  label: string
  options: { value: string; label: string; disabled?: boolean }[]
  defaultValue?: string
  value?: string
  onValueChange?: (value: string) => void
  placeholder?: string
  disabled?: boolean
}) {
  return (
    <div className="field">
      <Label htmlFor={id}>{text}</Label>
      <Select
        name={name}
        defaultValue={defaultValue}
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
      >
        <SelectTrigger id={id} className="w-full">
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent position="popper">
          {options.map((option) => (
            <SelectItem
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export function TextField({
  id,
  label: text,
  help,
  ...props
}: React.ComponentProps<typeof Input> & {
  id: string
  label: string
  help?: string
}) {
  return (
    <div className="field">
      <Label htmlFor={id}>{text}</Label>
      <Input
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

export function Pager({
  total,
  limit,
  offset,
  change,
  label: noun = 'records',
}: {
  total: number
  limit: number
  offset: number
  change: (offset: number) => void
  label?: string
}) {
  return (
    <div className="pager">
      <p>
        {total
          ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}`
          : '0'}{' '}
        {noun}
      </p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={`Previous ${noun}`}
          disabled={offset === 0}
          onClick={() => change(Math.max(0, offset - limit))}
        >
          <ChevronLeft />
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={`Next ${noun}`}
          disabled={offset + limit >= total}
          onClick={() => change(offset + limit)}
        >
          Next
          <ChevronRight />
        </Button>
      </div>
    </div>
  )
}

export function CaseTable({
  cases,
  compact = false,
}: {
  cases: CaseRecord[]
  compact?: boolean
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Investigation</TableHead>
          <TableHead>Severity</TableHead>
          <TableHead>Status</TableHead>
          {!compact && <TableHead>Owner</TableHead>}
          <TableHead className="text-right">
            Last activity{' '}
            <ArrowDown className="ml-1 inline size-3" aria-hidden="true" />
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cases.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="max-w-[420px]">
              <Link to={`/cases/${item.id}`} className="case-link">
                <span className="case-number">{item.display_id}</span>
                <span className="break-words whitespace-normal font-medium text-foreground">
                  {item.title}
                </span>
              </Link>
              {!compact && (
                <span className="mt-1 block text-[11px] text-muted-foreground">
                  {item.sources.length
                    ? item.sources.join(' · ')
                    : 'Manual investigation'}
                </span>
              )}
            </TableCell>
            <TableCell>
              <SeverityBadge severity={item.severity} />
            </TableCell>
            <TableCell>
              <StateBadge status={item.status} />
            </TableCell>
            {!compact && (
              <TableCell>
                <span className="text-xs text-muted-foreground">
                  {item.owner_handle ?? 'Unassigned'}
                </span>
              </TableCell>
            )}
            <TableCell className="text-right font-mono text-[11px] whitespace-nowrap text-muted-foreground">
              {shortDate(item.updated_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function Panel({
  title,
  description,
  actions,
  children,
  className = '',
}: {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={`panel ${className}`}>
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </Card>
  )
}

export function SourceReference({ value }: { value: string }) {
  let safe = false
  try {
    safe = ['http:', 'https:'].includes(new URL(value).protocol)
  } catch {
    /* Render non-URL references as text. */
  }
  return safe ? (
    <a
      className="source-reference underline underline-offset-4"
      href={value}
      target="_blank"
      rel="noreferrer noopener"
    >
      {value}
    </a>
  ) : (
    <code className="source-reference">{value}</code>
  )
}
