/**
 * Route table — one flat level, seven destinations.
 *
 * Every screen has a URL, so deep links, browser back and refresh all work.
 * The old app kept the active screen in a local `ref` inside App.vue.
 *
 * `meta.title` feeds the header; `meta.subtitle` is optional one-line context.
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { toast } from 'vue-sonner'
import { useAuthStore } from '@/stores/auth'
import { ROLE_LABEL, type Role } from '@/domain/auth'

const AppShell = () => import('./layouts/AppShell.vue')
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: AppShell,
    children: [
      { path: '', redirect: '/dashboard' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/features/dashboard/views/DashboardView.vue'),
        meta: { title: 'Dashboard', subtitle: 'Fleet status at a glance' },
      },
      {
        path: 'robot',
        name: 'robot',
        component: () => import('@/features/robot/views/RobotView.vue'),
        meta: { title: 'Robot', subtitle: 'Registered robots and live state' },
      },
      {
        // The navigation view is the operational destination from the fleet
        // table. Keeping the robot id in the URL makes the focused robot,
        // reload, and back button agree.
        path: 'robot/:robotId/nav',
        name: 'robot-nav',
        component: () => import('@/features/robot/views/RobotNavigationView.vue'),
        meta: { title: 'Robot navigation', subtitle: 'Live map, localization and goals' },
      },
      {
        path: 'robot/:robotId/detail',
        name: 'robot-detail',
        component: () => import('@/features/robot/views/RobotDetailView.vue'),
        meta: { title: 'Robot details', subtitle: 'Telemetry, diagnostics and connection health' },
      },
      {
        // Keep the old URL working while the navigation view becomes the
        // operator-facing destination.
        path: 'robot/:robotId',
        name: 'robot-legacy',
        redirect: (to) => ({ name: 'robot-nav', params: { robotId: to.params.robotId } }),
      },
      {
        path: 'maps',
        name: 'maps',
        component: () => import('@/features/maps/views/MapsView.vue'),
        meta: { title: 'Maps', subtitle: 'Registry, versions and robot assignment' },
      },
      {
        path: 'maps/edit/:mapId',
        name: 'map-edit',
        component: () => import('@/features/maps/views/MapEditorView.vue'),
        meta: { title: 'Edit map', subtitle: 'Correct cells and publish a new version' },
      },
      {
        // A survey belongs to a robot but is reached from Maps, and the URL
        // says both — so the page can be reopened, shared, or rejoined after
        // the tab is closed mid-session.
        path: 'maps/survey/:robotId',
        name: 'map-survey',
        component: () => import('@/features/mapping/views/SurveyView.vue'),
        meta: { title: 'Survey', subtitle: 'Drive the robot to build a map' },
      },
      {
        path: 'mission',
        name: 'mission',
        component: () => import('@/features/missions/views/MissionView.vue'),
        meta: { title: 'Mission', subtitle: 'Routes, and what is running now' },
      },
      {
        path: 'mission/edit/:missionId',
        name: 'mission-edit',
        component: () => import('@/features/missions/views/MissionEditorView.vue'),
        meta: { title: 'Edit mission', subtitle: 'The steps of one route, in order' },
      },
      {
        path: 'station',
        name: 'station',
        component: () => import('@/features/stations/views/StationView.vue'),
        meta: { title: 'Station', subtitle: 'Named poses, per map' },
      },
      {
        path: 'zone',
        name: 'zone',
        component: () => import('@/features/zones/views/ZoneView.vue'),
        meta: { title: 'Zone', subtitle: 'Keep-out, speed and trigger areas' },
      },
      {
        path: 'alarm',
        name: 'alarm',
        component: () => import('@/features/alarm/views/AlarmView.vue'),
        meta: { title: 'Alarm', subtitle: 'What needs you now, and what happened' },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/features/admin/views/UsersView.vue'),
        meta: {
          title: 'Users',
          subtitle: 'Who can sign in, and what they may do',
          role: 'super_admin',
        },
      },
      {
        path: 'activity',
        name: 'activity',
        component: () => import('@/features/admin/views/ActivityView.vue'),
        meta: { title: 'Activity', subtitle: 'Who changed what, and when', role: 'super_admin' },
      },
    ],
  },

  // Outside the shell, and the only page open to someone not signed in.
  {
    path: '/login',
    name: 'login',
    component: () => import('@/features/auth/views/LoginView.vue'),
    meta: { title: 'Sign in', public: true },
  },
  {
    // Signed in, but on a password someone else chose. Nothing else opens
    // until it is replaced; see the guard below.
    path: '/set-password',
    name: 'set-password',
    component: () => import('@/features/auth/views/SetPasswordView.vue'),
    meta: { title: 'Set a new password' },
  },

  // Outside the shell: a dead end gets a way home, not a sidebar.
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/features/not-found/NotFoundView.vue'),
    meta: { title: 'Not found', public: true },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

/**
 * Where to go after signing in. Only a path inside this app: a `next` of
 * "//evil.example" or "https://…" would turn the sign-in page into a
 * redirector that sends a freshly signed-in operator anywhere.
 */
export function safeNext(next: unknown): string {
  if (typeof next !== 'string' || !next.startsWith('/') || next.startsWith('//')) {
    return '/dashboard'
  }
  return next.startsWith('/login') ? '/dashboard' : next
}

router.beforeEach(async (to, from) => {
  const auth = useAuthStore()
  await auth.restore()

  if (to.meta.public) {
    if (to.name === 'login' && auth.status === 'signed-in') return safeNext(to.query.next)
    return true
  }

  if (auth.status !== 'signed-in') {
    const keep = to.fullPath !== '/' && to.fullPath !== '/dashboard'
    return { name: 'login', query: keep ? { next: to.fullPath } : {} }
  }

  const mustChange = auth.user?.mustChangePassword === true
  if (mustChange && to.name !== 'set-password') {
    return { name: 'set-password', query: { next: to.fullPath } }
  }
  if (!mustChange && to.name === 'set-password') return safeNext(to.query.next)

  const needed = to.meta.role as Role | undefined
  if (needed && !auth.can(needed)) {
    toast.error(`${String(to.meta.title ?? 'That page')} needs the ${ROLE_LABEL[needed]} role`)
    // Stay put when there is somewhere to stay; a deep link lands on the dashboard.
    return from.matched.length ? false : '/dashboard'
  }
  return true
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : null
  document.title = title ? `${title} · AMR Control` : 'AMR Control'
})
