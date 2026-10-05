import { describe, expect, it } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import LargerScreenNotice from '../LargerScreenNotice.vue'

const mountIt = (props = {}) =>
  mount(LargerScreenNotice, {
    props: {
      description: 'Painting cells needs a precise pointer.',
      backTo: '/maps',
      backLabel: 'Back to maps',
      ...props,
    },
    global: { stubs: { RouterLink: RouterLinkStub } },
  })

describe('LargerScreenNotice', () => {
  it('shows the default title and the description', () => {
    const wrapper = mountIt()
    expect(wrapper.text()).toContain('Best on a tablet or laptop')
    expect(wrapper.text()).toContain('Painting cells needs a precise pointer.')
  })

  it('takes a custom title', () => {
    expect(mountIt({ title: 'Editing is easier on a bigger screen' }).text()).toContain(
      'Editing is easier on a bigger screen',
    )
  })

  it('links back to where the user came from', () => {
    const link = mountIt().getComponent(RouterLinkStub)
    expect(link.props('to')).toBe('/maps')
    expect(link.text()).toBe('Back to maps')
  })

  it('lets the user open the task anyway', async () => {
    const wrapper = mountIt()
    const open = wrapper.findAll('button').find((b) => b.text() === 'Open anyway')!
    await open.trigger('click')
    expect(wrapper.emitted('continue')).toHaveLength(1)
  })
})
