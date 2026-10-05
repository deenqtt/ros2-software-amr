/**
 * Sign-in, accounts and the audit trail.
 *
 * The session itself is an HttpOnly cookie the browser sends on its own; no
 * token passes through this code, so nothing here can leak one.
 */

import { api, ApiError } from './client'
import { config } from '@/app/config'
import type { CurrentUser, Role } from '@/domain/auth'

interface MeWire {
  id: string
  username: string
  display_name: string | null
  role: Role
  session_idle_minutes: number
  must_change_password: boolean
}

interface UserWire {
  id: string
  username: string
  display_name: string | null
  role: Role
  disabled: boolean
  must_change_password: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
}

interface AuditWire {
  id: number
  at: string
  user_id: string | null
  username: string | null
  role: Role | null
  action: string
  method: string | null
  path: string | null
  status: number | null
  detail: string | null
  ip: string | null
}

export interface UserAccount {
  id: string
  username: string
  displayName: string | null
  role: Role
  disabled: boolean
  /** Still on a password someone else set: a new account or a reset. */
  mustChangePassword: boolean
  createdAt: string
  lastLoginAt: string | null
}

export interface AuditEntry {
  id: number
  /** UTC, as the server stamps it: "2026-10-05 02:18:32". */
  at: string
  userId: string | null
  username: string | null
  role: Role | null
  action: string
  method: string | null
  path: string | null
  status: number | null
  detail: string | null
  ip: string | null
}

export interface UserDraft {
  username: string
  displayName: string | null
  role: Role
  password: string
}

export interface UserPatch {
  displayName?: string | null
  role?: Role
  disabled?: boolean
  password?: string
}

function meFromWire(wire: MeWire): CurrentUser {
  return {
    id: wire.id,
    username: wire.username,
    displayName: wire.display_name,
    role: wire.role,
    sessionIdleMinutes: wire.session_idle_minutes,
    mustChangePassword: wire.must_change_password ?? false,
  }
}

function userFromWire(wire: UserWire): UserAccount {
  return {
    id: wire.id,
    username: wire.username,
    displayName: wire.display_name,
    role: wire.role,
    disabled: wire.disabled,
    mustChangePassword: wire.must_change_password ?? false,
    createdAt: wire.created_at,
    lastLoginAt: wire.last_login_at,
  }
}

function auditFromWire(wire: AuditWire): AuditEntry {
  return {
    id: wire.id,
    at: wire.at,
    userId: wire.user_id,
    username: wire.username,
    role: wire.role,
    action: wire.action,
    method: wire.method,
    path: wire.path,
    status: wire.status,
    detail: wire.detail,
    ip: wire.ip,
  }
}

/** A refusal that belongs on one field of a form. */
export class FieldError extends Error {
  constructor(
    readonly field: string,
    message: string,
  ) {
    super(message)
    this.name = 'FieldError'
  }
}

/** Turn a 409/422 with {"detail": {"field", "message"}} into a FieldError. */
function fieldError(error: unknown): unknown {
  if (!(error instanceof ApiError) || (error.status !== 409 && error.status !== 422)) return error
  try {
    const detail = (JSON.parse(error.message) as { detail?: unknown }).detail
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const { field, message } = detail as { field?: string; message?: string }
      if (message) return field ? new FieldError(field, message) : new Error(message)
    }
    // Pydantic's list form: [{loc: ["body", "password"], msg: "..."}]
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { loc?: unknown[]; msg?: string }
      const field = String(first.loc?.[first.loc.length - 1] ?? '')
      return new FieldError(field, (first.msg ?? 'Invalid value').replace(/^Value error, /, ''))
    }
  } catch {
    // Not JSON; keep the original error.
  }
  return error
}

async function withFieldErrors<T>(call: Promise<T>): Promise<T> {
  try {
    return await call
  } catch (error) {
    throw fieldError(error)
  }
}

export const authApi = {
  async login(username: string, password: string): Promise<CurrentUser> {
    return meFromWire(await api.post<MeWire>('/auth/login', { username, password }))
  },

  logout(): Promise<void> {
    return api.post<void>('/auth/logout')
  },

  /** Who is signed in, or null when nobody is. */
  async me(): Promise<CurrentUser | null> {
    try {
      return meFromWire(await api.get<MeWire>('/auth/me'))
    } catch (error) {
      if (error instanceof ApiError && error.isUnauthorized) return null
      throw error
    }
  },

  changePassword(currentPassword: string, newPassword: string): Promise<void> {
    return withFieldErrors(
      api.put<void>('/auth/password', {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    )
  },
}

/**
 * Whether the server answers at all. /health is the one route that needs no
 * sign-in, so the sign-in page can say "server down" before anyone types.
 */
export async function serverReachable(): Promise<boolean> {
  try {
    const response = await fetch(`${config.apiStaticUrl}/health`, { cache: 'no-store' })
    return response.ok
  } catch {
    return false
  }
}

export const usersApi = {
  async list(): Promise<UserAccount[]> {
    return (await api.get<UserWire[]>('/users')).map(userFromWire)
  },

  async create(draft: UserDraft): Promise<UserAccount> {
    const wire = await withFieldErrors(
      api.post<UserWire>('/users', {
        username: draft.username,
        display_name: draft.displayName,
        role: draft.role,
        password: draft.password,
      }),
    )
    return userFromWire(wire)
  },

  async update(id: string, patch: UserPatch): Promise<UserAccount> {
    const body: Record<string, unknown> = {}
    if ('displayName' in patch) body.display_name = patch.displayName
    if (patch.role !== undefined) body.role = patch.role
    if (patch.disabled !== undefined) body.disabled = patch.disabled
    if (patch.password !== undefined) body.password = patch.password
    return userFromWire(await withFieldErrors(api.patch<UserWire>(`/users/${id}`, body)))
  },

  remove(id: string): Promise<void> {
    return withFieldErrors(api.del<void>(`/users/${id}`))
  },
}

export type AuditKind = 'all' | 'changes' | 'sign-ins' | 'refused'

export interface AuditQuery {
  kind?: AuditKind
  userId?: string | null
  /** ISO 8601. */
  since?: string | null
  until?: string | null
  search?: string | null
}

export interface AuditPage {
  items: AuditEntry[]
  total: number
  /** Send back with the next page so rows do not shift as records arrive. */
  uptoId: number
}

function auditParams(query: AuditQuery): URLSearchParams {
  const params = new URLSearchParams()
  if (query.kind && query.kind !== 'all') params.set('kind', query.kind)
  if (query.userId) params.set('user_id', query.userId)
  if (query.since) params.set('since', query.since)
  if (query.until) params.set('until', query.until)
  if (query.search?.trim()) params.set('q', query.search.trim())
  return params
}

export const auditApi = {
  async page(
    query: AuditQuery,
    options: { limit: number; offset: number; uptoId?: number | null },
  ): Promise<AuditPage> {
    const params = auditParams(query)
    params.set('limit', String(options.limit))
    params.set('offset', String(options.offset))
    if (options.uptoId) params.set('upto_id', String(options.uptoId))
    const wire = await api.get<{ items: AuditWire[]; total: number; upto_id: number }>(
      `/audit?${params}`,
    )
    return { items: wire.items.map(auditFromWire), total: wire.total, uptoId: wire.upto_id }
  },

  /** A link the browser downloads directly; the session cookie goes along. */
  exportUrl(query: AuditQuery): string {
    const params = auditParams(query)
    const suffix = params.toString() ? `?${params}` : ''
    return `${config.apiBaseUrl}/audit/export.csv${suffix}`
  },
}
