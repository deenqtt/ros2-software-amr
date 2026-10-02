import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { RouterView } from 'vue-router'
import { router } from '@/app/router'

describe('not found', () => {
  it('names the address, offers the dashboard, and has no sidebar', async () => {
    setActivePinia(createPinia())
    await router.push('/does/not/exist')
    await router.isReady()
    const wrapper = mount(RouterView, { global: { plugins: [router] } })
    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(router.currentRoute.value.name).toBe('not-found')
    expect(wrapper.text()).toContain('/does/not/exist')
    expect(wrapper.find('a[href="/dashboard"]').exists()).toBe(true)
    expect(wrapper.find('aside').exists()).toBe(false)
  })
})
