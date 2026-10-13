/**
 * The docking entry (staging pose) of a station, and whether the robot fits.
 *
 * The case that started it: a station 1.18 m from a wall whose heading put its
 * staging pose 0.37 m from that wall. The planner refused it and the mission
 * never moved, while driving to the station itself worked.
 */
import { describe, expect, it } from 'vitest'
import { CELL, type Grid } from '../map/pgm'
import { checkDocking, dockingProblemText, footprintCorners, stagingPose } from '../docking'

const placement = { resolution: 0.05, originX: 0, originY: 0 }

/** A 10 m × 6 m room, free inside, with a wall along x = 0.5 (columns 0-9 occupied). */
function room(): Grid {
  const width = 200
  const height = 120
  const cells = new Uint8Array(width * height).fill(CELL.free)
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < 10; column += 1) cells[row * width + column] = CELL.occupied
  }
  return { width, height, cells }
}

describe('stagingPose', () => {
  it('stands one metre behind the station, facing the same way', () => {
    const pose = stagingPose({ x: 5, y: 3, yaw: Math.PI / 2 })
    expect(pose.x).toBeCloseTo(5)
    expect(pose.y).toBeCloseTo(2)
    expect(pose.yaw).toBeCloseTo(Math.PI / 2)
  })
})

describe('footprintCorners', () => {
  it('is the robot rectangle turned to the heading', () => {
    const corners = footprintCorners({ x: 0, y: 0, yaw: 0 }, 2, 1)
    expect(corners).toEqual([
      { x: 1, y: 0.5 },
      { x: 1, y: -0.5 },
      { x: -1, y: -0.5 },
      { x: -1, y: 0.5 },
    ])
  })
})

describe('checkDocking', () => {
  it('passes a station with open floor behind it', () => {
    // Facing the wall from the middle of the room: the entry is further out.
    const check = checkDocking(room(), placement, { x: 3, y: 3, yaw: Math.PI })
    expect(check.problem).toBeNull()
    expect(dockingProblemText(check)).toBeNull()
  })

  it('refuses a station whose entry lands against the wall', () => {
    // Facing away from the wall 1.4 m out: the entry is 0.4 m from it.
    const check = checkDocking(room(), placement, { x: 1.9, y: 3, yaw: 0 })
    expect(check.problem).toBe('staging-blocked')
    expect(check.wallDistance).toBeCloseTo(0.4, 1)
    expect(dockingProblemText(check)).toContain('does not fit')
  })

  it('refuses an entry that falls off the map', () => {
    const check = checkDocking(room(), placement, { x: 9.5, y: 3, yaw: Math.PI })
    expect(check.problem).toBe('off-map')
  })

  it('warns about an entry on unmapped ground', () => {
    const grid = room()
    for (let row = 0; row < grid.height; row += 1) {
      for (let column = 100; column < 200; column += 1)
        grid.cells[row * grid.width + column] = CELL.unknown
    }
    // Station at x 6 facing -x: entry at x 7, inside the unknown half.
    const check = checkDocking(grid, placement, { x: 6, y: 3, yaw: Math.PI })
    expect(check.problem).toBe('staging-unknown')
  })

  it('refuses an approach that crosses a wall', () => {
    const grid = room()
    // A thin wall across the room at x 5.00-5.05.
    for (let row = 0; row < grid.height; row += 1)
      grid.cells[row * grid.width + 100] = CELL.occupied
    // Station at x 4.5 facing -x: the entry at x 5.5 is clear, the way in crosses the wall.
    const check = checkDocking(grid, placement, { x: 4.5, y: 3, yaw: Math.PI })
    expect(check.problem).toBe('approach-blocked')
  })
})
