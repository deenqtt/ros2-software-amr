import { describe, expect, it } from 'vitest'
import { defineComponent, ref } from 'vue'
import { mount } from '@vue/test-utils'
import MapListToggle from '../MapListToggle.vue'

describe('MapListToggle', () => {
  it('shows both views with the count and marks the active one', () => {
    const wrapper = mount(MapListToggle, { props: { modelValue: 'map', count: 3 } })
    const [map, list] = wrapper.findAll('[role="radio"]')
    expect(map!.text()).toBe('Map')
    expect(list!.text()).toBe('List (3)')
    expect(map!.attributes('aria-checked')).toBe('true')
    expect(list!.attributes('aria-checked')).toBe('false')
  })

  it('leaves the count out when none is given and honours a custom label', () => {
    const wrapper = mount(MapListToggle, { props: { modelValue: 'list', listLabel: 'Zones' } })
    const list = wrapper.findAll('[role="radio"]')[1]!
    expect(list.text()).toBe('Zones')
    expect(list.attributes('aria-checked')).toBe('true')
  })

  it('emits the chosen view', async () => {
    const wrapper = mount(MapListToggle, { props: { modelValue: 'map', count: 3 } })
    await wrapper.findAll('[role="radio"]')[1]!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['list']])
  })

  it('works with v-model', async () => {
    const Host = defineComponent({
      components: { MapListToggle },
      setup: () => ({ view: ref<'map' | 'list'>('map') }),
      template: '<MapListToggle v-model="view" :count="2" /><span class="view">{{ view }}</span>',
    })
    const wrapper = mount(Host)
    await wrapper.findAll('[role="radio"]')[1]!.trigger('click')
    expect(wrapper.get('.view').text()).toBe('list')
    expect(wrapper.findAll('[role="radio"]')[1]!.attributes('aria-checked')).toBe('true')
    await wrapper.findAll('[role="radio"]')[0]!.trigger('click')
    expect(wrapper.get('.view').text()).toBe('map')
  })
})
