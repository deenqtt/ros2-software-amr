/**
 * PGM codec.
 *
 * The values here are not arbitrary: 0/205/254 are what nav2's map_saver
 * writes, and every map already in this repository holds exactly those three.
 */
import { describe, expect, it } from 'vitest'
import {
  CELL,
  cellsForMetres,
  cellToWorld,
  decodePgm,
  encodePgm,
  isCanonical,
  metresForCells,
  gridToWorld,
  nonCanonicalValues,
  PgmFormatError,
  worldToGrid,
} from '../map/pgm'

function p5(width: number, height: number, cells: number[]): Uint8Array {
  const header = `P5\n${width} ${height}\n255\n`
  const out = new Uint8Array(header.length + cells.length)
  for (let i = 0; i < header.length; i += 1) out[i] = header.charCodeAt(i)
  out.set(cells, header.length)
  return out
}

describe('decodePgm', () => {
  it('reads a binary PGM', () => {
    const grid = decodePgm(p5(3, 2, [0, 205, 254, 254, 0, 205]))
    expect(grid.width).toBe(3)
    expect(grid.height).toBe(2)
    expect([...grid.cells]).toEqual([0, 205, 254, 254, 0, 205])
  })

  it('reads an ASCII PGM, because GIMP offers that on export', () => {
    const grid = decodePgm(new TextEncoder().encode('P2\n2 2\n255\n0 205\n254 0\n'))
    expect([...grid.cells]).toEqual([0, 205, 254, 0])
  })

  it('skips comment lines wherever they appear in the header', () => {
    const bytes = new TextEncoder().encode('P2\n# written by something else\n2 1\n255\n0 254')
    expect([...decodePgm(bytes).cells]).toEqual([0, 254])
  })

  it('copies the pixels rather than aliasing the caller buffer', () => {
    // The editor mutates cells in place; aliasing would corrupt the response.
    const bytes = p5(2, 1, [0, 254])
    const grid = decodePgm(bytes)
    grid.cells[0] = CELL.free
    expect(bytes[bytes.length - 2]).toBe(0)
  })

  it('refuses a truncated image rather than inventing cells', () => {
    expect(() => decodePgm(p5(4, 4, [0, 0, 0]))).toThrow(PgmFormatError)
  })

  it('refuses something that is not a PGM', () => {
    expect(() => decodePgm(new TextEncoder().encode('\x89PNG\r\n'))).toThrow(/Not a PGM/)
  })

  it('refuses a 16-bit PGM, which will not fit a cell', () => {
    const bytes = new TextEncoder().encode('P2\n1 1\n65535\n300')
    expect(() => decodePgm(bytes)).toThrow(/max value/)
  })

  it('refuses a zero-area image', () => {
    expect(() => decodePgm(new TextEncoder().encode('P2\n0 0\n255\n'))).toThrow(/no area/)
  })
})

describe('encodePgm', () => {
  it('round-trips a grid unchanged', () => {
    const cells = [0, 205, 254, 254, 205, 0]
    const grid = decodePgm(encodePgm({ width: 3, height: 2, cells: Uint8Array.from(cells) }))
    expect([...grid.cells]).toEqual(cells)
  })

  it('always writes binary P5, whatever came in', () => {
    const ascii = decodePgm(new TextEncoder().encode('P2\n2 1\n255\n0 254'))
    const encoded = encodePgm(ascii)
    expect(String.fromCharCode(encoded[0] as number, encoded[1] as number)).toBe('P5')
  })
})

describe('canonical values', () => {
  it('accepts only the three map_saver values', () => {
    expect([0, 205, 254].every(isCanonical)).toBe(true)
    expect([1, 100, 204, 206, 255].some(isCanonical)).toBe(false)
  })

  it('reports what a soft brush left behind', () => {
    const grid = { width: 4, height: 1, cells: Uint8Array.from([0, 60, 180, 254]) }
    expect(nonCanonicalValues(grid)).toEqual([60, 180])
  })
})

describe('cellToWorld', () => {
  const placement = { resolution: 0.05, originX: -5, originY: -5 }

  it('flips the row, because PGM row 0 is the top and ROS origin is the bottom', () => {
    const grid = { width: 10, height: 10, cells: new Uint8Array(100) }
    const top = cellToWorld(grid, 0, 0, placement)
    const bottom = cellToWorld(grid, 0, 9, placement)
    expect(top.y).toBeGreaterThan(bottom.y)
    // Bottom row sits half a cell above the origin.
    expect(bottom.y).toBeCloseTo(-5 + 0.025, 6)
  })

  it('places a column half a cell in from the origin', () => {
    const grid = { width: 10, height: 10, cells: new Uint8Array(100) }
    expect(cellToWorld(grid, 0, 9, placement).x).toBeCloseTo(-5 + 0.025, 6)
  })
})

describe('brush size in metres', () => {
  it('snaps a physical size to whole cells', () => {
    expect(cellsForMetres(0.15, 0.05)).toBe(3)
    // 12 cm cannot be expressed at 5 cm per cell; it rounds and says so.
    expect(cellsForMetres(0.12, 0.05)).toBe(2)
    expect(metresForCells(2, 0.05)).toBeCloseTo(0.1, 6)
  })

  it('never returns a brush of zero cells', () => {
    expect(cellsForMetres(0, 0.05)).toBe(1)
    expect(cellsForMetres(0.001, 0.05)).toBe(1)
  })

  it('survives a map with a nonsense resolution', () => {
    expect(cellsForMetres(0.15, 0)).toBe(1)
  })
})

describe('world and image coordinates', () => {
  const placement = { resolution: 0.05, originX: -5, originY: -5 }
  const grid = { width: 200, height: 100, cells: new Uint8Array(20_000) }

  it('round-trips a pose through image coordinates', () => {
    const { gx, gy } = worldToGrid(grid, 1.23, -2.34, placement)
    const back = gridToWorld(grid, gx, gy, placement)
    expect(back.x).toBeCloseTo(1.23, 9)
    expect(back.y).toBeCloseTo(-2.34, 9)
  })

  it('keeps fractional positions, because a dock pose is a measurement', () => {
    // Snapping would move a station by up to half a cell — 2.5 cm here, enough
    // to miss a charging contact.
    const { gx } = worldToGrid(grid, -5 + 0.5 * 0.05, 0, placement)
    expect(gx).toBeCloseTo(0.5, 9)
  })

  it('puts the map origin at the bottom-left of the image', () => {
    const { gx, gy } = worldToGrid(grid, -5, -5, placement)
    expect(gx).toBeCloseTo(0, 9)
    expect(gy).toBeCloseTo(grid.height, 9)
  })

  it('agrees with cellToWorld at a cell centre', () => {
    const centre = cellToWorld(grid, 3, 7, placement)
    const { gx, gy } = worldToGrid(grid, centre.x, centre.y, placement)
    expect(gx).toBeCloseTo(3.5, 9)
    expect(gy).toBeCloseTo(7.5, 9)
  })
})
