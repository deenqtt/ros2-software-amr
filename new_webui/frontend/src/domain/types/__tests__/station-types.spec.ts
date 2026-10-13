/**
 * Station types and the numbers the robot receives for them.
 *
 * The numbers are master_control's Station_t on StationConfig.type; the backend
 * (TYPE_TO_WIRE) and the agent (STATION_TYPE_WIRE) use the same.
 */
import { describe, expect, it } from 'vitest'
import { STATION_TYPE_LABEL, STATION_TYPE_WIRE, STATION_TYPES } from '../station'

describe('station types', () => {
  it('match the robot numbering', () => {
    // 0 is master_control's HOME_STATION, not offered; the others keep its numbers.
    expect(STATION_TYPE_WIRE).toEqual({ pick_drop: 1, charging: 2 })
  })

  it('all have a label for the editor', () => {
    for (const type of STATION_TYPES) expect(STATION_TYPE_LABEL[type]).toBeTruthy()
  })
})
