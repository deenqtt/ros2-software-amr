/**
 * The confirmation has to reach the caller before the dialog closes.
 *
 * Every caller reads what to act on out of a ref that its own close handler
 * clears. reka-ui closed first, so the work was handed nothing and returned
 * without a word: the dialog shut, the row stayed, and no error was shown.
 * Two bug reports — a map that would not delete and a station that would not
 * delete — turned out to be this one ordering.
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ConfirmDialog from '../ConfirmDialog.vue'

async function clickAction(label: string, extra: Record<string, unknown> = {}) {
  const order: string[] = []
  const wrapper = mount(ConfirmDialog, {
    props: {
      open: true,
      title: 'Remove Dock 1?',
      description: 'This cannot be undone.',
      confirmLabel: label,
      'onUpdate:open': (value: boolean) => order.push(`update:open(${value})`),
      onConfirm: () => order.push('confirm'),
      onCancel: () => order.push('cancel'),
      ...extra,
    },
    attachTo: document.body,
  })
  await nextTick()
  const button = [...document.querySelectorAll('button')].find(
    (candidate) => candidate.textContent?.trim() === label,
  )
  expect(button, `no button labelled ${label}`).toBeTruthy()
  button!.click()
  await nextTick()
  wrapper.unmount()
  return order
}

describe('ConfirmDialog', () => {
  it('emits confirm before it reports itself closed', async () => {
    const order = await clickAction('Remove')
    expect(order[0]).toBe('confirm')
    expect(order).toContain('update:open(false)')
    expect(order.indexOf('confirm')).toBeLessThan(order.indexOf('update:open(false)'))
  })

  it('does not confirm while the action is already running', async () => {
    // `pending` disables the button, so a second click cannot start the work
    // twice — a double-click used to send two deletes.
    const order = await clickAction('Working…', { pending: true })
    expect(order).not.toContain('confirm')
  })

  it('does not confirm when the caller has said the action is blocked', async () => {
    const order = await clickAction('Remove', { blocked: true })
    expect(order).not.toContain('confirm')
  })
})
