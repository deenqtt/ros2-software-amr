/**
 * Roles, and what each may do.
 *
 * Mirrors app/auth.py on the backend: four ordered roles, each including the
 * one before. The server is the authority — this copy exists so a button can
 * say "needs operator" before it is pressed, instead of failing after.
 */

export type Role = 'viewer' | 'operator' | 'admin' | 'super_admin'

export const ROLES: readonly Role[] = ['viewer', 'operator', 'admin', 'super_admin']

const RANK: Record<Role, number> = { viewer: 0, operator: 1, admin: 2, super_admin: 3 }

export const ROLE_LABEL: Record<Role, string> = {
  viewer: 'Viewer',
  operator: 'Operator',
  admin: 'Admin',
  super_admin: 'Super admin',
}

export const ROLE_SUMMARY: Record<Role, string> = {
  viewer: 'Sees the fleet, maps and history. Changes nothing.',
  operator: 'Runs and stops missions, sends goals, drives and parks robots.',
  admin: 'Also edits maps, stations, zones, missions and robots.',
  super_admin: 'Also manages people and reads the activity log.',
}

export interface CurrentUser {
  id: string
  username: string
  displayName: string | null
  role: Role
  sessionIdleMinutes: number
  /** Signed in with a password someone else chose; must replace it first. */
  mustChangePassword: boolean
}

export function atLeast(role: Role | null | undefined, needed: Role): boolean {
  return role != null && RANK[role] >= RANK[needed]
}

/** The tooltip on a control the current role may not use, or '' when it may. */
export function roleBlocker(role: Role | null | undefined, needed: Role): string {
  return atLeast(role, needed) ? '' : `Needs the ${ROLE_LABEL[needed].toLowerCase()} role`
}

/** Two letters for the avatar: "Budi Santoso" → "BS", "rifai" → "RI". */
export function initials(user: Pick<CurrentUser, 'username' | 'displayName'>): string {
  const name = (user.displayName ?? '').trim()
  const words = name.split(/\s+/).filter(Boolean)
  const first = words[0]
  const last = words.at(-1)
  if (words.length >= 2 && first && last) return (first.charAt(0) + last.charAt(0)).toUpperCase()
  return (name || user.username).slice(0, 2).toUpperCase()
}

export function displayName(user: Pick<CurrentUser, 'username' | 'displayName'>): string {
  return user.displayName?.trim() || user.username
}
