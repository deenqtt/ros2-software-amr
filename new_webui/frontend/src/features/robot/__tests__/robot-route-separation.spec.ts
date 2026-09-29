import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { router } from '@/app/router'

const navigationSource = readFileSync(
  resolve(process.cwd(), 'src/features/robot/views/RobotNavigationView.vue'),
  'utf8',
)
const detailSource = readFileSync(
  resolve(process.cwd(), 'src/features/robot/views/RobotDetailView.vue'),
  'utf8',
)

describe('robot page routes', () => {
  it('keeps navigation and technical detail as separate destinations', () => {
    const routes = router.getRoutes()
    const navigation = routes.find((route) => route.name === 'robot-nav')
    const detail = routes.find((route) => route.name === 'robot-detail')

    expect(navigation?.path).toBe('/robot/:robotId/nav')
    expect(String(navigation?.components?.default)).toContain('RobotNavigationView.vue')
    expect(detail?.path).toBe('/robot/:robotId/detail')
    expect(String(detail?.components?.default)).toContain('RobotDetailView.vue')
  })

  it('keeps the old robot URL pointing to the operational navigation page', () => {
    const legacy = router.getRoutes().find((route) => route.name === 'robot-legacy')

    expect(legacy?.path).toBe('/robot/:robotId')
    if (!legacy || typeof legacy.redirect !== 'function') throw new Error('legacy route has no redirect')
    expect(legacy.redirect({ params: { robotId: 'r1' } } as never, {} as never)).toEqual({
      name: 'robot-nav',
      params: { robotId: 'r1' },
    })
  })

  it('keeps diagnostic topic details out of the operational navigation page', () => {
    expect(navigationSource).not.toContain('TopicHealthTable')
    expect(navigationSource).not.toContain('Technical details')
    expect(detailSource).not.toContain('RobotMapCanvas')
  })

  it('keeps robot-scoped mission execution on the navigation page', () => {
    expect(navigationSource).toContain('missions.dispatch')
    expect(navigationSource).toContain('Start mission')
    expect(navigationSource).toContain('Stop after lap')
  })
})
