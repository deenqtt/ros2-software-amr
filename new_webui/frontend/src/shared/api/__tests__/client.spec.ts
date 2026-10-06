import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from '../client'

describe('api.bytes', () => {
  afterEach(() => vi.restoreAllMocks())

  it('does not reuse a cached map file after an in-place replace', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(new Uint8Array([1, 2, 3])))

    await api.bytes('/api/maps/map-1/files/image')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/maps/map-1/files/image'),
      expect.objectContaining({ cache: 'no-store' }),
    )
  })
})

describe('ApiError.readable', () => {
  it('pulls the sentence out of a structured 409', () => {
    const body = JSON.stringify({
      detail: { message: "'Loop A' is running (running). Stop the run first.", run_id: 'r1' },
    })
    const error = new ApiError(body, 409, '/missions/m1')
    expect(error.readable).toBe("'Loop A' is running (running). Stop the run first.")
    // The raw body stays available for callers that parse the conflict.
    expect(JSON.parse(error.message).detail.run_id).toBe('r1')
  })

  it('reads a string detail and the first validation error', () => {
    expect(new ApiError('{"detail":"Not allowed"}', 400, '/x').readable).toBe('Not allowed')
    const invalid = JSON.stringify({ detail: [{ msg: 'Value error, enabled cannot be null' }] })
    expect(new ApiError(invalid, 422, '/x').readable).toBe('Value error, enabled cannot be null')
  })

  it('returns plain text unchanged', () => {
    expect(new ApiError('Bad Gateway', 502, '/x').readable).toBe('Bad Gateway')
  })
})
