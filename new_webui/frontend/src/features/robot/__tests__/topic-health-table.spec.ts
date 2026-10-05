import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TopicHealthTable from '../components/TopicHealthTable.vue'
import type { TopicHealth } from '@/domain/ros/health'

function topic(key: string, extra: Partial<TopicHealth> = {}): TopicHealth {
  return {
    key,
    label: `/${key}`,
    cadence: 'periodic',
    tier: 'vitals',
    subscribed: true,
    messages: 120,
    lastMessageAt: Date.now(),
    state: 'ok',
    rateHz: 10,
    needsStack: false,
    ...extra,
  }
}

describe('TopicHealthTable', () => {
  const wrapper = mount(TopicHealthTable, {
    props: { topics: [topic('odom'), topic('scan', { state: 'stale', rateHz: null })] },
  })

  it('lists topics on a phone with the state, rate and last seen, stale first', () => {
    const items = wrapper.get('ul.md\\:hidden').findAll('li')
    expect(items.map((item) => item.text().split(/\s+/)[0])).toEqual(['/scan', '/odom'])
    expect(items[0]!.text()).toContain('Stale')
    expect(items[1]!.text()).toContain('10 Hz')
    // Cadence and message count are table-only.
    expect(wrapper.get('ul.md\\:hidden').text()).not.toContain('periodic')
    expect(wrapper.get('ul.md\\:hidden').text()).not.toContain('120')
  })

  it('keeps the full table for wider screens, messages from lg', () => {
    const messages = wrapper.findAll('th').find((th) => th.text() === 'Messages')
    expect(messages?.classes()).toContain('lg:table-cell')
  })
})
