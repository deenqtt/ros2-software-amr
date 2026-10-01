/**
 * Runtime configuration, read once from the Vite environment.
 *
 * The old project made the ROS URL configurable but hardcoded the backend to
 * http://localhost:3001/api in two places, so any deployment where the backend
 * was not on the operator's own machine silently failed (audit section 4,
 * item 11). Both are environment-driven here.
 */

function required(value: string | undefined, name: string, fallback: string): string {
  if (value && value.trim()) return value.trim()
  console.warn(`[config] ${name} is not set; falling back to ${fallback}`)
  return fallback
}

/**
 * Unset means the production layout: the backend behind the same origin as
 * this page, under /backend/ (see new_webui/deploy/nginx.conf.example).
 *
 * The prefix is not decoration. The backend serves map images at /maps/…,
 * which is also a page of this app; mounted at the root, one of the two
 * would shadow the other. Relative, so one build works on any host name.
 */
const SAME_ORIGIN_BACKEND = '/backend'

export const config = {
  apiBaseUrl: required(
    import.meta.env.VITE_API_BASE_URL,
    'VITE_API_BASE_URL',
    `${SAME_ORIGIN_BACKEND}/api`,
  ),
  apiStaticUrl: required(
    import.meta.env.VITE_API_STATIC_URL,
    'VITE_API_STATIC_URL',
    SAME_ORIGIN_BACKEND,
  ),
  defaultRosUrl: required(import.meta.env.VITE_DEFAULT_ROS_URL, 'VITE_DEFAULT_ROS_URL', 'ws://localhost:8765'),
  defaultCameraPort: Number(import.meta.env.VITE_DEFAULT_CAMERA_PORT ?? 8080),
  /**
   * Development aid: artificial delay on registry loads, so the skeleton and
   * empty states can be exercised while the data still comes from
   * localStorage. Ships as 0 — see .env.example.
   */
  devLatencyMs: Number(import.meta.env.VITE_DEV_LATENCY_MS ?? 0),
} as const

const WEBSOCKET_PROTOCOLS = new Set(['ws:', 'wss:'])

export interface UrlValidation {
  valid: boolean
  error: string
}

export function validateBridgeUrl(value: string): UrlValidation {
  const url = value.trim()
  if (!url) return { valid: false, error: 'Bridge URL is required.' }
  try {
    const parsed = new URL(url)
    if (!WEBSOCKET_PROTOCOLS.has(parsed.protocol) || !parsed.hostname) {
      return { valid: false, error: 'Bridge URL must be a ws:// or wss:// address.' }
    }
  } catch {
    return { valid: false, error: 'Bridge URL must be a valid WebSocket URL.' }
  }
  return { valid: true, error: '' }
}

/** Derive a camera stream URL from a bridge URL, for pre-filling the registry. */
export function deriveCameraUrl(bridgeUrl: string, port = config.defaultCameraPort): string | null {
  try {
    const host = new URL(bridgeUrl).hostname
    if (!host) return null
    return `http://${host}:${port}`
  } catch {
    return null
  }
}
