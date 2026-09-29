/**
 * Map save classification.
 *
 * This exists because of a real loss: the agent returned
 * "SAVED locally at /maps/... (no backend configured)", the view tested
 * `startsWith('SAVED')`, and the operator was told the map was in the registry
 * while the map list stayed empty.
 */
import { describe, expect, it } from 'vitest'
import { classifyMapSave, mapSaveFailureMessage } from '../mapSave'

describe('classifyMapSave', () => {
  it('reads a published save as published, with its id', () => {
    expect(classifyMapSave('SAVED 0154fcb8-53fa-433c-9dea-c90ddc963a15 v1')).toEqual({
      kind: 'published',
      mapId: '0154fcb8-53fa-433c-9dea-c90ddc963a15',
    })
  })

  it('does NOT read a local-only save as published', () => {
    // The whole point: "SAVED_LOCAL" starts with "SAVED".
    const outcome = classifyMapSave('SAVED_LOCAL /maps/cache/.staging/map.yaml')
    expect(outcome.kind).toBe('local-only')
    expect(outcome).toEqual({ kind: 'local-only', path: '/maps/cache/.staging/map.yaml' })
  })

  it('tells the operator the map is still on the robot', () => {
    const message = mapSaveFailureMessage(classifyMapSave('SAVED_LOCAL /maps/x.yaml'))
    // Naming the fix matters more than naming the fault: the survey is
    // recoverable, but only if they know it was not thrown away.
    expect(message).toContain('AMR_BACKEND_URL')
    expect(message).toContain('still on the robot disk')
  })

  it('treats a refusal as a refusal and keeps its reason', () => {
    expect(classifyMapSave('REJECTED SLAM is not running')).toEqual({
      kind: 'refused',
      reason: 'REJECTED SLAM is not running',
    })
  })

  it('treats an empty or missing result as a refusal', () => {
    expect(classifyMapSave(undefined)).toEqual({ kind: 'refused', reason: 'Save refused' })
    expect(classifyMapSave('   ')).toEqual({ kind: 'refused', reason: 'Save refused' })
  })

  it('does not accept a bare SAVED with no id', () => {
    // An id-less publish cannot be assigned or downloaded, so it is not one.
    expect(classifyMapSave('SAVED').kind).toBe('refused')
  })
})
