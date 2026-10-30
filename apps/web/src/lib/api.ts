import { useQuery } from '@tanstack/react-query'
import type { components } from './api.generated'

export type Schema = components['schemas']
export type CaseRecord = Schema['CaseOut']
export type AlertRecord = Schema['AlertOut']
export type Severity = Schema['Severity']
export type CaseStatus = Schema['CaseStatus']
export type LocalSession = Schema['LocalSession']

export class ApiError extends Error {
  constructor(public problem: Schema['Problem']) {
    super(problem.detail)
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const timeout = AbortSignal.timeout(15000)
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    headers: { Accept: 'application/json', ...options.headers },
  })
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (data && typeof data === 'object' && 'code' in data && 'detail' in data)
      throw new ApiError(data as Schema['Problem'])
    throw new Error(
      'The workspace could not complete this request. Check system status and try again.',
    )
  }
  if (!data || typeof data !== 'object')
    throw new Error('The workspace returned an unexpected response.')
  return data as T
}

export function write<T>(
  path: string,
  method: string,
  body: object,
  token: string,
): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-ATE-CSRF': token },
    body: JSON.stringify(body),
  })
}

export function useSession() {
  return useQuery({
    queryKey: ['session'],
    queryFn: ({ signal }) => request<LocalSession>('/session', {}, signal),
    retry: false,
    staleTime: 60000,
  })
}

export function useData<T>(
  key: readonly unknown[],
  path: string,
  enabled = true,
) {
  return useQuery({
    queryKey: key,
    queryFn: ({ signal }) => request<T>(path, {}, signal),
    enabled,
    retry: false,
    refetchInterval: 30000,
  })
}

export const severities: Severity[] = ['critical', 'high', 'medium', 'low']
export const statuses: CaseStatus[] = [
  'new',
  'triaging',
  'investigating',
  'resolved',
  'closed',
]
export const label = (value: string) =>
  value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
export const dateTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
export const shortDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
export const field = (data: FormData, name: string) =>
  String(data.get(name) ?? '')
export function localDateInput(value: string = new Date().toISOString()) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16)
}
