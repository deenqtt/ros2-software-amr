/**
 * useSystemStats — polls backend /stats for CPU, MEM, and ROS latency.
 * Shows "—" gracefully if the endpoint is unavailable.
 */
import { ref } from 'vue'

const cpu     = ref('—')
const mem     = ref('—')
const latency = ref('—')

let _interval = null

export function useSystemStats() {
  async function startPolling(apiGet) {
    if (_interval) return
    const poll = async () => {
      try {
        const s = await apiGet('/stats')
        if (s.cpu_percent != null) cpu.value     = s.cpu_percent.toFixed(0) + '%'
        if (s.mem_mb      != null) mem.value     = s.mem_mb + 'MB'
        if (s.latency_ms  != null) latency.value = s.latency_ms + 'ms'
      } catch {
        // /stats endpoint not available — silently ignore
      }
    }
    await poll()
    _interval = setInterval(poll, 5000)
  }

  function stopPolling() {
    if (_interval) { clearInterval(_interval); _interval = null }
  }

  function setLatency(ms) {
    latency.value = ms != null ? ms + 'ms' : '—'
  }

  return { cpu, mem, latency, startPolling, stopPolling, setLatency }
}
