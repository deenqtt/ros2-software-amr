/**
 * A refused station delete.
 *
 * The 409 body used to reach the operator verbatim, JSON and all. It carries
 * the missions that still name the station, and those are what has to show.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../client'
import { stationsApi, StationInUseError } from '../stations'

afterEach(() => vi.restoreAllMocks())

function refuse(body: string) {
  vi.spyOn(api, 'del').mockRejectedValue(new ApiError(body, 409, '/stations/s1'))
}

describe('stationsApi.remove', () => {
  it('turns a 409 into the missions that still use the station', async () => {
    refuse(JSON.stringify({ detail: { message: 'in use', missions: ['Shuttle', 'Loop'] } }))
    const error = await stationsApi.remove('s1').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(StationInUseError)
    expect((error as StationInUseError).missions).toEqual(['Shuttle', 'Loop'])
  })

  it('still says "in use" when the body is not JSON', async () => {
    refuse('Conflict')
    const error = await stationsApi.remove('s1').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(StationInUseError)
    expect((error as StationInUseError).missions).toEqual([])
  })

  it('passes other failures through untouched', async () => {
    vi.spyOn(api, 'del').mockRejectedValue(new ApiError('gone', 404, '/stations/s1'))
    await expect(stationsApi.remove('s1')).rejects.toMatchObject({ status: 404 })
  })
})
