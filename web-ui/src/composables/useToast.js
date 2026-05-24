/**
 * useToast — global toast notification composable.
 *
 * Usage:
 *   const toast = useToast()
 *   toast.success('Map saved!')
 *   toast.error('Connection failed: ' + err.message)
 *   toast.info('Navigating to dock...')
 */

import { ref } from 'vue'

// Singleton state shared across all consumers
const toasts = ref([])
let _nextId = 0

function addToast(type, message, duration = 3000) {
  const id = ++_nextId
  toasts.value.push({ id, type, message })
  setTimeout(() => removeToast(id), duration)
}

function removeToast(id) {
  const idx = toasts.value.findIndex((t) => t.id === id)
  if (idx !== -1) toasts.value.splice(idx, 1)
}

export function useToast() {
  return {
    toasts,
    success: (msg) => addToast('success', msg),
    error: (msg) => addToast('error', msg),
    info: (msg) => addToast('info', msg),
    warning: (msg) => addToast('warning', msg, 5000), // Longer duration for warnings
    remove: removeToast,
  }
}
