/**
 * Zone geometry.
 *
 * `pointInPolygon` decides what the operator has selected; the robot's
 * rasteriser decides what actually gets filled in the mask. They use the same
 * rule on purpose — if they disagreed, a zone would select as one shape and
 * enforce as another, and nothing on screen would say so.
 */
import { describe, expect, it } from 'vitest'
import {
  distanceToPolygon,
  KEEPOUT_HALO_M,
  keepoutAt,
  keepoutCrowds,
  polygonArea,
  pointInPolygon,
  ROBOT_RADIUS_M,
  SPEED_MAX,
  speedLimitProblem,
  type Zone,
  type ZonePoint,
} from '@/domain/types'
import { avoidLevel, ZONE_KIND_STYLE, zoneSetting } from '../zoneKind'

const SQUARE: ZonePoint[] = [
  [0, 0],
  [4, 0],
  [4, 4],
  [0, 4],
]

/** An L, to catch a fill that leaks across a concave corner. */
const ELL: ZonePoint[] = [
  [0, 0],
  [6, 0],
  [6, 2],
  [2, 2],
  [2, 6],
  [0, 6],
]

describe('pointInPolygon', () => {
  it('accepts the middle and rejects the outside', () => {
    expect(pointInPolygon(SQUARE, 2, 2)).toBe(true)
    expect(pointInPolygon(SQUARE, 5, 2)).toBe(false)
    expect(pointInPolygon(SQUARE, -1, -1)).toBe(false)
  })

  it('does not treat the notch of a concave shape as inside', () => {
    expect(pointInPolygon(ELL, 1, 1)).toBe(true)
    expect(pointInPolygon(ELL, 4, 1)).toBe(true)
    // The corner cut out of the L.
    expect(pointInPolygon(ELL, 4, 4)).toBe(false)
  })

  it('is stable on a horizontal edge rather than flipping', () => {
    // A vertex exactly on the ray must count once. Counting it twice makes the
    // test alternate along an edge, and a click there selects at random.
    expect(pointInPolygon(SQUARE, 2, 0)).toBe(pointInPolygon(SQUARE, 2, 0))
    expect(pointInPolygon(SQUARE, 6, 0)).toBe(false)
  })

  it('handles a shape with negative coordinates', () => {
    // Map origins are usually negative, so most real polygons live here.
    const shifted: ZonePoint[] = SQUARE.map(([x, y]) => [x - 5, y - 5])
    expect(pointInPolygon(shifted, -3, -3)).toBe(true)
    expect(pointInPolygon(shifted, 1, 1)).toBe(false)
  })

  it('says nothing is inside a degenerate ring', () => {
    expect(pointInPolygon([[0, 0], [1, 1]] as ZonePoint[], 0.5, 0.5)).toBe(false)
  })
})

describe('polygonArea', () => {
  it('measures a square', () => {
    expect(polygonArea(SQUARE)).toBeCloseTo(16, 9)
  })

  it('does not care which way round the corners were drawn', () => {
    // An operator drawing clockwise must not get a negative area on screen.
    expect(polygonArea([...SQUARE].reverse())).toBeCloseTo(16, 9)
  })

  it('subtracts the notch of a concave shape', () => {
    // 6x2 plus 2x4 = 20, not the 36 of its bounding box.
    expect(polygonArea(ELL)).toBeCloseTo(20, 9)
  })

  it('is zero for a line', () => {
    expect(polygonArea([[0, 0], [3, 3]] as ZonePoint[])).toBeCloseTo(0, 9)
  })
})

describe('zone kinds', () => {
  it('says how hard an avoid zone pushes in words, with the number beside it', () => {
    expect(avoidLevel(10)).toBe('Low')
    expect(avoidLevel(50)).toBe('Medium')
    expect(avoidLevel(90)).toBe('High')
    expect(zoneSetting({ kind: 'avoid', avoidCost: 60, speedLimit: null } as Zone)).toBe(
      'Medium (60)',
    )
  })

  it('does not offer a trigger zone the robots would ignore', () => {
    expect(ZONE_KIND_STYLE.binary.unavailable).toBeTruthy()
    expect(ZONE_KIND_STYLE.keepout.unavailable).toBeUndefined()
  })
})

describe('speed limits', () => {
  it("stops at the robots' top speed, the same ceiling as the backend", () => {
    expect(SPEED_MAX).toBe(0.6)
    expect(speedLimitProblem(0.01)).toBeNull()
    expect(speedLimitProblem(0.3)).toBeNull()
    expect(speedLimitProblem(0.6)).toBeNull()
    expect(speedLimitProblem(0.61)).toMatch(/at most 0.6 m\/s/)
  })

  it('refuses zero, because Nav2 reads it as no limit rather than stop', () => {
    expect(speedLimitProblem(0)).toMatch(/Keep out/)
    expect(speedLimitProblem(-0.2)).not.toBeNull()
    expect(speedLimitProblem(Number.NaN)).not.toBeNull()
  })

  it('lists a limit to the centimetre per second the robot encodes', () => {
    expect(zoneSetting({ kind: 'speed', speedLimit: 0.25, avoidCost: null } as Zone)).toBe(
      '0.25 m/s',
    )
  })
})

describe('keepoutCrowds', () => {
  const station = (name: string, x: number, y: number) => ({ name, x, y })

  it('measures to the outline, and is zero inside', () => {
    expect(distanceToPolygon(SQUARE, 2, 2)).toBe(0)
    expect(distanceToPolygon(SQUARE, 5, 2)).toBeCloseTo(1, 9)
    // Off a corner, the distance is to the corner, not to the nearest box side.
    expect(distanceToPolygon(SQUARE, 7, 8)).toBeCloseTo(5, 9)
    // In the notch of the L: outside, 1 m from the inner corner's edges.
    expect(distanceToPolygon(ELL, 3, 3)).toBeCloseTo(1, 9)
  })

  it('flags a station within the halo plus the robot radius', () => {
    const clearance = KEEPOUT_HALO_M + ROBOT_RADIUS_M // 1.09 m
    const near = station('Dock', 4 + clearance - 0.01, 2)
    const clear = station('Bay', 4 + clearance + 0.01, 2)
    const inside = station('Inside', 1, 1)
    const corner = station('Corner', 4.7, 4.7) // 0.99 m off the corner
    const farCorner = station('Far corner', 4.8, 4.8) // 1.13 m off the corner
    expect(keepoutCrowds(SQUARE, [near, clear, inside, corner, farCorner])).toEqual([
      near,
      inside,
      corner,
    ])
  })

  it('flags nothing for a shape that is not yet a polygon', () => {
    expect(
      keepoutCrowds(
        [
          [0, 0],
          [1, 1],
        ],
        [station('A', 0.5, 0.5)],
      ),
    ).toEqual([])
  })
})

describe('keepoutAt', () => {
  const square: ZonePoint[] = [
    [0, 0],
    [2, 0],
    [2, 2],
    [0, 2],
  ]
  const zone = (kind: Zone['kind'], enabled = true, name = 'Panel') => ({
    kind,
    enabled,
    name,
    polygon: square,
  })

  it('names the active keep-out a point falls in', () => {
    expect(keepoutAt([zone('keepout')], 1, 1)?.name).toBe('Panel')
  })

  it('ignores points outside, switched-off keep-outs and other kinds', () => {
    expect(keepoutAt([zone('keepout')], 3, 1)).toBeUndefined()
    expect(keepoutAt([zone('keepout', false)], 1, 1)).toBeUndefined()
    expect(keepoutAt([zone('avoid'), zone('speed')], 1, 1)).toBeUndefined()
  })
})
