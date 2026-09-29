/**
 * Typed REST client for the AMR backend.
 *
 * Errors carry the status code so callers can distinguish "backend is down"
 * from "that record is gone" — the old client threw a formatted string for
 * every failure, which made both look identical to the UI.
 */

import { config } from '@/app/config'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
    options?: { cause?: unknown },
  ) {
    super(message, options)
    this.name = 'ApiError'
  }

  get isNotFound(): boolean {
    return this.status === 404
  }

  /** status 0 means the request never reached the server. */
  get isOffline(): boolean {
    return this.status === 0
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(config.apiBaseUrl + path, init)
  } catch (cause) {
    // status 0 is the signal for "never reached the server"; keep the original
    // network error attached so it is still visible in the console.
    throw new ApiError(`Backend unreachable at ${config.apiBaseUrl}`, 0, path, { cause })
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new ApiError(detail || response.statusText, response.status, path)
  }

  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) return (await response.json()) as T
  return (await response.text()) as T
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path)
  },
  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body ?? {}) })
  },
  put<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(body) })
  },
  /**
   * Partial update. Preferred over PUT for anything with optional fields:
   * with PUT, a field the client forgets to resend is reset to its default.
   */
  patch<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify(body) })
  },
  del<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' })
  },
  /** Multipart upload. Do not set Content-Type — the browser adds the boundary. */
  upload<T>(path: string, form: FormData): Promise<T> {
    return request<T>(path, { method: 'POST', body: form })
  },
  /** Multipart replace. Same rule as upload: leave Content-Type to the browser. */
  uploadPut<T>(path: string, form: FormData): Promise<T> {
    return request<T>(path, { method: 'PUT', body: form })
  },

  /**
   * Raw bytes, for content the application parses itself.
   *
   * Map images go through this rather than an <img> because a browser cannot
   * decode PGM, and because a cell value must never make a round trip through
   * the rendering pipeline — see domain/map/pgm.ts.
   */
  async bytes(path: string): Promise<Uint8Array> {
    let response: Response
    try {
      // Map files can be replaced in place while keeping the same map id and
      // URL. Reusing a cached response would make the editor show the old
      // cells after a successful overwrite; the backend also marks these
      // responses as non-cacheable for other clients.
      response = await fetch(config.apiBaseUrl + path, { cache: 'no-store' })
    } catch (cause) {
      throw new ApiError(`Backend unreachable at ${config.apiBaseUrl}`, 0, path, { cause })
    }
    if (!response.ok) {
      const detail = await response.text().catch(() => response.statusText)
      throw new ApiError(detail || response.statusText, response.status, path)
    }
    return new Uint8Array(await response.arrayBuffer())
  },

  /** Absolute URL for a backend-served static file. */
  staticUrl(filename: string | null): string | null {
    return filename ? `${config.apiStaticUrl}/maps/${filename}` : null
  },
}
