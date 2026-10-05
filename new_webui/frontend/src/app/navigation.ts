/**
 * The navigation model.
 *
 * Flat, one level, seven destinations. Not the fleet -> robot -> workspace
 * hierarchy proposed in the audit: that structure assumed operational actions
 * would always be scoped to a selected robot, and this one treats Robot as a
 * destination alongside the map data it works on.
 *
 * Alarm sits in its own group at the foot of the rail. It is the only item
 * that carries a count, and it is the only one an operator navigates to
 * because something went wrong rather than because they chose to.
 */
import {
  Bell,
  Bot,
  History,
  LayoutDashboard,
  Map as MapIcon,
  MapPin,
  Route,
  Shapes,
  Users,
  type LucideIcon,
} from 'lucide-vue-next'
import type { Role } from '@/domain/auth'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Rendered as a count pill on the rail and in the bell. */
  badgeKey?: 'alarms'
  /** Hidden from anyone below this role, rather than shown and refused. */
  role?: Role
}

export interface NavGroup {
  id: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'main',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/robot', label: 'Robot', icon: Bot },
      { to: '/maps', label: 'Maps', icon: MapIcon },
      { to: '/mission', label: 'Mission', icon: Route },
      { to: '/station', label: 'Station', icon: MapPin },
      { to: '/zone', label: 'Zone', icon: Shapes },
    ],
  },
  {
    id: 'alerts',
    items: [{ to: '/alarm', label: 'Alarm', icon: Bell, badgeKey: 'alarms' }],
  },
  {
    // Super admin only. Hidden, not disabled: these are not part of anyone
    // else's job, and a rail of greyed-out entries is noise on every screen.
    id: 'admin',
    items: [
      { to: '/users', label: 'Users', icon: Users, role: 'super_admin' },
      { to: '/activity', label: 'Activity', icon: History, role: 'super_admin' },
    ],
  },
]

/** The groups this role sees, with empty groups dropped. */
export function navGroupsFor(can: (role: Role) => boolean): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.role || can(item.role)),
  })).filter((group) => group.items.length > 0)
}
