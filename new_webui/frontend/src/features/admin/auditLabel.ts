/**
 * An audit record in words.
 *
 * The server records what was asked for (method + path) rather than a sentence,
 * so a new endpoint is audited without anyone writing copy for it. The words
 * live here: a route that is not listed still reads as "PATCH /api/…", which is
 * accurate if not pretty.
 */
import type { AuditEntry } from '@/shared/api/auth'

export type AuditOutcome = 'ok' | 'refused' | 'failed'

interface Rule {
  method: string
  pattern: RegExp
  label: string
}

const ID = '[^/]+'

const RULES: Rule[] = [
  { method: 'POST', pattern: /^\/api\/runs$/, label: 'Started a mission' },
  { method: 'PATCH', pattern: new RegExp(`^/api/runs/${ID}$`), label: 'Stopped or updated a mission run' },
  { method: 'PUT', pattern: new RegExp(`^/api/robots/${ID}/mode$`), label: 'Changed a robot’s mode' },
  { method: 'PUT', pattern: new RegExp(`^/api/robots/${ID}/map$`), label: 'Assigned a map to a robot' },
  { method: 'POST', pattern: /^\/api\/robots$/, label: 'Added a robot' },
  { method: 'PATCH', pattern: new RegExp(`^/api/robots/${ID}$`), label: 'Edited a robot' },
  { method: 'DELETE', pattern: new RegExp(`^/api/robots/${ID}$`), label: 'Removed a robot' },
  { method: 'POST', pattern: /^\/api\/maps$/, label: 'Uploaded a map' },
  { method: 'PATCH', pattern: new RegExp(`^/api/maps/${ID}$`), label: 'Renamed a map' },
  { method: 'PUT', pattern: new RegExp(`^/api/maps/${ID}/image$`), label: 'Edited a map' },
  { method: 'DELETE', pattern: new RegExp(`^/api/maps/${ID}$`), label: 'Deleted a map' },
  { method: 'POST', pattern: /^\/api\/missions$/, label: 'Created a mission' },
  { method: 'PATCH', pattern: new RegExp(`^/api/missions/${ID}$`), label: 'Edited a mission' },
  { method: 'DELETE', pattern: new RegExp(`^/api/missions/${ID}$`), label: 'Deleted a mission' },
  { method: 'POST', pattern: /^\/api\/stations$/, label: 'Added a station' },
  { method: 'PATCH', pattern: new RegExp(`^/api/stations/${ID}$`), label: 'Edited a station' },
  { method: 'DELETE', pattern: new RegExp(`^/api/stations/${ID}$`), label: 'Deleted a station' },
  { method: 'POST', pattern: /^\/api\/zones$/, label: 'Drew a zone' },
  { method: 'PATCH', pattern: new RegExp(`^/api/zones/${ID}$`), label: 'Edited a zone' },
  { method: 'DELETE', pattern: new RegExp(`^/api/zones/${ID}$`), label: 'Deleted a zone' },
  { method: 'POST', pattern: /^\/api\/users$/, label: 'Created an account' },
  { method: 'PATCH', pattern: new RegExp(`^/api/users/${ID}$`), label: 'Changed an account' },
  { method: 'DELETE', pattern: new RegExp(`^/api/users/${ID}$`), label: 'Deleted an account' },
  { method: 'PUT', pattern: /^\/api\/auth\/password$/, label: 'Changed their password' },
]

const LOGIN_DETAIL: Record<string, string> = {
  'bad password': 'wrong password',
  'unknown user': 'no such account',
  disabled: 'account disabled',
  throttled: 'paused after repeated failures',
}

export function auditLabel(entry: Pick<AuditEntry, 'action' | 'method' | 'path' | 'status' | 'detail'>): string {
  if (entry.action === 'login') {
    if (entry.status === 200) return 'Signed in'
    const why = entry.detail ? LOGIN_DETAIL[entry.detail] ?? entry.detail : null
    return why ? `Sign-in refused (${why})` : 'Sign-in refused'
  }
  if (entry.action === 'logout') return 'Signed out'

  const rule = RULES.find((r) => r.method === entry.method && r.pattern.test(entry.path ?? ''))
  return rule ? rule.label : `${entry.method ?? ''} ${entry.path ?? entry.action}`.trim()
}

export function auditOutcome(status: number | null): AuditOutcome {
  if (status == null || status < 400) return 'ok'
  if (status === 401 || status === 403 || status === 429) return 'refused'
  return 'failed'
}

/** The server stamps UTC as "YYYY-MM-DD HH:MM:SS", without a zone. */
export function auditDate(at: string): Date {
  return new Date(`${at.replace(' ', 'T')}Z`)
}
