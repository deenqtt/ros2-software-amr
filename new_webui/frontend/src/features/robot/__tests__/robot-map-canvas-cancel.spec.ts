/**
 * A cancelled pointer is not a release.
 *
 * The browser cancels a touch when it takes the gesture for a scroll or a
 * system swipe. Treating that as "finger lifted" sent the half-drawn pose to
 * the robot as an initial pose or a navigation goal.
 */
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import RobotMapCanvas from '../components/RobotMapCanvas.vue'
import type { OccupancyGrid } from '@/domain/types'

enableAutoUnmount(afterEach)

beforeAll(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  Element.prototype.getBoundingClientRect = () => new DOMRect(0, 0, 100, 100)
  HTMLCanvasElement.prototype.getContext = () => null
  Element.prototype.setPointerCapture = () => {}
  Element.prototype.releasePointerCapture = () => {}
  Element.prototype.hasPointerCapture = () => true
})

const grid: OccupancyGrid = {
  info: {
    width: 10,
    height: 10,
    resolution: 0.1,
    origin: { position: { x: 0, y: 0, z: 0 }, orientation: { x: 0, y: 0, z: 0, w: 1 } },
  },
  data: new Array(100).fill(0),
}

async function mountCanvas(tool: 'view' | 'initialPose' | 'goal') {
  const wrapper = mount(RobotMapCanvas, {
    props: {
      grid,
      costmap: null,
      plan: null,
      particles: null,
      scan: null,
      pose: null,
      sensorOffset: null,
      zones: [],
      footprint: null,
      layers: {},
      tool,
    },
  })
  // Vue ignores events stamped in the millisecond its listeners were attached.
  await new Promise((resolve) => setTimeout(resolve, 5))
  return wrapper
}

function fire(el: Element, type: string, x: number, y: number, pointerId = 1) {
  const event = new MouseEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true })
  Object.defineProperty(event, 'pointerId', { value: pointerId })
  el.dispatchEvent(event)
}

describe.each(['goal', 'initialPose'] as const)('%s tool', (tool) => {
  it('sends nothing when the pointer is cancelled mid-drag', async () => {
    const wrapper = await mountCanvas(tool)
    const el = wrapper.get('.touch-none').element
    fire(el, 'pointerdown', 20, 20)
    fire(el, 'pointermove', 60, 40)
    fire(el, 'pointercancel', 60, 40)
    fire(el, 'pointerup', 60, 40)
    expect(wrapper.emitted('pick')).toBeUndefined()
  })

  it('sends nothing when pointer capture is lost mid-drag', async () => {
    const wrapper = await mountCanvas(tool)
    const el = wrapper.get('.touch-none').element
    fire(el, 'pointerdown', 20, 20)
    fire(el, 'pointermove', 60, 40)
    fire(el, 'lostpointercapture', 60, 40)
    fire(el, 'pointerup', 60, 40)
    expect(wrapper.emitted('pick')).toBeUndefined()
  })

  it('still sends the pose on a normal release', async () => {
    const wrapper = await mountCanvas(tool)
    const el = wrapper.get('.touch-none').element
    fire(el, 'pointerdown', 20, 20)
    fire(el, 'pointermove', 60, 40)
    fire(el, 'pointerup', 60, 40)
    fire(el, 'lostpointercapture', 60, 40)
    expect(wrapper.emitted('pick')).toHaveLength(1)
  })
})

it('a cancelled pan ends, so the next gesture is not treated as a drag', async () => {
  const wrapper = await mountCanvas('view')
  const el = wrapper.get('.touch-none').element
  fire(el, 'pointerdown', 20, 20)
  fire(el, 'pointercancel', 20, 20)
  fire(el, 'pointermove', 80, 80)
  expect(wrapper.emitted('pick')).toBeUndefined()
})
