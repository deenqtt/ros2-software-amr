import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CollapsibleSection from '../CollapsibleSection.vue'

function screenWidth(width: number) {
  window.matchMedia = ((query: string) => ({
    matches: width <= Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

describe('CollapsibleSection', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => delete (window as { matchMedia?: unknown }).matchMedia)

  const mountIt = (props = {}) =>
    mount(CollapsibleSection, {
      props: { title: 'Configuration', summary: 'Warehouse A v1', ...props },
      slots: { default: '<p class="body">details</p>' },
    })

  it('starts open on a wide screen, folded on a phone', () => {
    screenWidth(1366)
    expect(mountIt().get('button').attributes('aria-expanded')).toBe('true')
    setActivePinia(createPinia())
    screenWidth(390)
    expect(mountIt().get('button').attributes('aria-expanded')).toBe('false')
  })

  it('keeps the summary in view while folded, and opens on a tap', async () => {
    screenWidth(390)
    const wrapper = mountIt()
    expect(wrapper.text()).toContain('Warehouse A v1')
    await wrapper.get('button').trigger('click')
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
  })

  it('honours an explicit default', () => {
    screenWidth(1366)
    expect(mountIt({ defaultOpen: false }).get('button').attributes('aria-expanded')).toBe('false')
  })
})
