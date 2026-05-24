/**
 * useAPI — thin fetch wrapper for the AMR backend (FastAPI on :3001).
 *
 * Base URL is always localhost:3001 — the backend runs on the same machine
 * as the browser (or via port-forward). Only the ROS WebSocket URL adjusts
 * to the remote hostname.
 *
 * Usage:
 *   const api = useAPI()
 *   const maps = await api.get('/maps')
 *   const m    = await api.post('/missions', { name, waypoints })
 *   await api.del('/missions/5')
 *   const result = await api.upload('/maps/upload', formData)
 */

export function useAPI() {
  const BASE = 'http://localhost:3001/api'
  const baseUrl = { value: BASE }

  async function _fetch(path, options = {}) {
    const url = BASE + path
    const res = await fetch(url, options)
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(`API ${options.method || 'GET'} ${path} → ${res.status}: ${text}`)
    }
    if (res.status === 204) return null
    const ct = res.headers.get('content-type') ?? ''
    if (ct.includes('application/json')) return res.json()
    return res.text()
  }

  function get(path) {
    return _fetch(path)
  }

  function post(path, body) {
    return _fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  function put(path, body) {
    return _fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  function del(path) {
    return _fetch(path, { method: 'DELETE' })
  }

  /** Upload multipart/form-data (do NOT set Content-Type — browser sets boundary) */
  function upload(path, formData) {
    return _fetch(path, { method: 'POST', body: formData })
  }

  /** Resolve a backend static file URL (e.g. preview image) */
  function staticUrl(filename) {
    if (!filename) return null
    return `http://localhost:3001/maps/${filename}`
  }

  return { get, post, put, del, upload, staticUrl, baseUrl }
}
