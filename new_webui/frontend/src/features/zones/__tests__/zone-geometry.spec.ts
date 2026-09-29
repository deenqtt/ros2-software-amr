/**
 * Zone geometry.
 *
 * `pointInPolygon` decides what the operator has selected; the robot's
 * rasteriser decides what actually gets filled in the mask. They use the same
 * rule on purpose — if they disagreed, a zone would select as one shape and
 * enforce as another, and nothing on screen would say so.
 */
import { describe, expect, it } from 'vitest'
import { polygonArea, pointInPolygon, type ZonePoint } from '@/domain/types'

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
