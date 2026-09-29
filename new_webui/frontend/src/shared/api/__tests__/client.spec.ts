import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../client'

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
