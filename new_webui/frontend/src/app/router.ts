/**
 * Route table — one flat level, seven destinations.
 *
 * Every screen has a URL, so deep links, browser back and refresh all work.
 * The old app kept the active screen in a local `ref` inside App.vue.
 *
 * `meta.title` feeds the header; `meta.subtitle` is optional one-line context.
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

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
    ],
  },

  // Outside the shell: a dead end gets a way home, not a sidebar.
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/features/not-found/NotFoundView.vue'),
    meta: { title: 'Not found' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : null
  document.title = title ? `${title} · AMR Control` : 'AMR Control'
})
