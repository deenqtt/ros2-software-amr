/**
 * A cancelled pointer is not a drop: the dragged station returns to where it
 * began and nothing new is proposed.
 */
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import StationMapCanvas from '../components/StationMapCanvas.vue'
import type { Station } from '@/domain/types'

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

const station: Station = {
  id: 's1',
  mapId: 'm1',
  name: 'Dock 1',
  type: 'pick',
  x: 0.5,
  y: 0.5,
  yaw: 0,
  note: null,
  taughtByRobotId: null,
  createdAt: '',
  updatedAt: '',
}

async function mountCanvas(placing = false) {
  const wrapper = mount(StationMapCanvas, {
    props: {
      grid: { width: 10, height: 10, cells: new Uint8Array(100) },
      placement: { resolution: 0.1, originX: 0, originY: 0 },
      stations: [station],
      selectedId: null,
      placing,
      movable: true,
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

// The 10x10 grid fills the 100px viewport at 10px a cell: world (0.5, 0.5) m is
// grid (5, 5), and the y axis is flipped, so it sits at screen (50, 50).
describe('dragging a station', () => {
  it('puts the station back when the pointer is cancelled', async () => {
    const wrapper = await mountCanvas()
    const el = wrapper.get('.touch-none').element
    fire(el, 'pointerdown', 50, 50)
    fire(el, 'pointermove', 80, 80)
    const moves = () => wrapper.emitted('move') as [{ id: string; x: number; y: number }][]
    expect(moves()).toHaveLength(1)
    expect(moves()[0]![0].x).not.toBeCloseTo(0.5)

    fire(el, 'pointercancel', 80, 80)
    const last = moves().at(-1)![0]
    expect(last.id).toBe('s1')
    expect(last.x).toBe(0.5)
    expect(last.y).toBe(0.5)

    // The gesture is over: a stray move no longer drags the station.
    const count = moves().length
    fire(el, 'pointermove', 10, 10)
    expect(moves()).toHaveLength(count)
  })

  it('emits nothing when cancelled before the station moved', async () => {
    const wrapper = await mountCanvas()
    const el = wrapper.get('.touch-none').element
    fire(el, 'pointerdown', 50, 50)
    fire(el, 'pointercancel', 50, 50)
    expect(wrapper.emitted('move')).toBeUndefined()
  })

  it('keeps the dropped position on a normal release', async () => {
    const wrapper = await mountCanvas()
    const el = wrapper.get('.touch-none').element
    fire(el, 'pointerdown', 50, 50)
    fire(el, 'pointermove', 80, 80)
    fire(el, 'pointerup', 80, 80)
    fire(el, 'lostpointercapture', 80, 80)
    expect(wrapper.emitted('move')).toHaveLength(1)
  })
})

describe('placing a station', () => {
  it('abandons the placement when the pointer is cancelled', async () => {
    const wrapper = await mountCanvas(true)
    const el = wrapper.get('.touch-none').element
    fire(el, 'pointerdown', 20, 20)
    fire(el, 'pointermove', 60, 40)
    fire(el, 'pointercancel', 60, 40)
    fire(el, 'pointerup', 60, 40)
    expect(wrapper.emitted('place')).toBeUndefined()
  })
})
