/**
 * Map editing operations and history.
 *
 * The invariants that matter: nothing outside the three canonical values is ever
 * written, undo returns the grid bit-for-bit, and the changed-cell count stays
 * honest through any sequence of edits — it is what the operator reads before
 * committing a new version.
 */
import { describe, expect, it } from 'vitest'
import { CELL, type CellValue, type Grid } from '../map/pgm'
import {
  EditSession,
  floodFill,
  HISTORY_LIMIT,
  paintDisc,
  paintLine,
  paintRect,
} from '../map/edit'

function grid(width: number, height: number, fill: CellValue = CELL.free): Grid {
  return { width, height, cells: new Uint8Array(width * height).fill(fill) }
}

function at(g: Grid, column: number, row: number): number {
  return g.cells[row * g.width + column] as number
}

describe('paintDisc', () => {
  it('paints exactly one cell at diameter 1', () => {
    const g = grid(5, 5)
    const session = new EditSession(g)
    session.apply(paintDisc(g, 2, 2, 1, CELL.occupied))
    expect(session.changedCells).toBe(1)
    expect(at(g, 2, 2)).toBe(CELL.occupied)
  })

  it('is symmetric about the cell under the cursor', () => {
    const g = grid(7, 7)
    new EditSession(g).apply(paintDisc(g, 3, 3, 3, CELL.occupied))
    expect(at(g, 2, 3)).toBe(CELL.occupied)
    expect(at(g, 4, 3)).toBe(CELL.occupied)
    expect(at(g, 3, 2)).toBe(CELL.occupied)
    expect(at(g, 3, 4)).toBe(CELL.occupied)
  })

  it('is round rather than square, once a brush is big enough to tell', () => {
    // At diameter 3 a disc and a square are the same nine cells. Roundness only
    // becomes observable further out, so that is where it is asserted.
    const g = grid(11, 11)
    new EditSession(g).apply(paintDisc(g, 5, 5, 7, CELL.occupied))
    expect(at(g, 2, 5)).toBe(CELL.occupied)
    expect(at(g, 2, 2)).toBe(CELL.free)
  })

  it('covers more than one cell at diameter 2', () => {
    // The sizing bug this guards: a brush labelled 2 cells wide that paints one.
    const g = grid(5, 5)
    const session = new EditSession(g)
    session.apply(paintDisc(g, 2, 2, 2, CELL.occupied))
    expect(session.changedCells).toBeGreaterThan(1)
  })

  it('clips at the edge instead of wrapping to the next row', () => {
    const g = grid(5, 5)
    new EditSession(g).apply(paintDisc(g, 0, 0, 5, CELL.occupied))
    // Wrapping would paint the right-hand end of row 0 or 1.
    expect(at(g, 4, 0)).toBe(CELL.free)
    expect(at(g, 4, 1)).toBe(CELL.free)
  })

  it('produces no patch when the cells already hold the value', () => {
    const g = grid(5, 5, CELL.occupied)
    // Otherwise undo appears to do nothing, because it undoes a no-op.
    expect(paintDisc(g, 2, 2, 3, CELL.occupied)).toBeNull()
  })

  it('returns null entirely outside the grid', () => {
    const g = grid(5, 5)
    expect(paintDisc(g, 99, 99, 1, CELL.occupied)).toBeNull()
  })
})

describe('paintLine', () => {
  it('leaves no gaps along a diagonal', () => {
    const g = grid(9, 9)
    new EditSession(g).apply(
      paintLine(g, { column: 0, row: 0 }, { column: 8, row: 8 }, 1, CELL.occupied),
    )
    for (let i = 0; i <= 8; i += 1) expect(at(g, i, i)).toBe(CELL.occupied)
  })

  it('closes a doorway at the brush width asked for', () => {
    const g = grid(11, 11)
    new EditSession(g).apply(
      paintLine(g, { column: 5, row: 2 }, { column: 5, row: 8 }, 3, CELL.occupied),
    )
    expect(at(g, 4, 5)).toBe(CELL.occupied)
    expect(at(g, 6, 5)).toBe(CELL.occupied)
    // Two cells past the endpoint: a 3-wide brush reaches one, not two.
    expect(at(g, 5, 0)).toBe(CELL.free)
  })

  it('handles a line of zero length', () => {
    const g = grid(5, 5)
    const patch = paintLine(g, { column: 2, row: 2 }, { column: 2, row: 2 }, 1, CELL.occupied)
    expect(patch?.indices.length).toBe(1)
  })
})

describe('paintRect', () => {
  it('fills the block regardless of which corner was dragged from', () => {
    const a = grid(6, 6)
    const b = grid(6, 6)
    new EditSession(a).apply(paintRect(a, { column: 1, row: 1 }, { column: 3, row: 3 }, CELL.occupied))
    new EditSession(b).apply(paintRect(b, { column: 3, row: 3 }, { column: 1, row: 1 }, CELL.occupied))
    expect([...a.cells]).toEqual([...b.cells])
  })

  it('clamps a drag that ran off the canvas', () => {
    const g = grid(4, 4)
    const session = new EditSession(g)
    session.apply(paintRect(g, { column: -5, row: -5 }, { column: 99, row: 99 }, CELL.occupied))
    expect(session.changedCells).toBe(16)
  })

  it('returns null when the rectangle misses the grid completely', () => {
    const g = grid(4, 4)
    expect(paintRect(g, { column: 10, row: 10 }, { column: 20, row: 20 }, CELL.occupied)).toBeNull()
  })
})

describe('floodFill', () => {
  it('fills a region bounded by a wall and stops there', () => {
    const g = grid(7, 3)
    // Vertical wall down the middle.
    for (let row = 0; row < 3; row += 1) g.cells[row * 7 + 3] = CELL.occupied

    const session = new EditSession(g)
    session.apply(floodFill(g, 0, 0, CELL.unknown))

    expect(at(g, 0, 0)).toBe(CELL.unknown)
    expect(at(g, 2, 2)).toBe(CELL.unknown)
    expect(at(g, 3, 1)).toBe(CELL.occupied)
    // The far side is a separate region and must be untouched.
    expect(at(g, 4, 0)).toBe(CELL.free)
    expect(session.changedCells).toBe(9)
  })

  it('is four-connected, so a diagonal gap does not leak', () => {
    const g = grid(3, 3, CELL.occupied)
    g.cells[0] = CELL.free
    g.cells[4] = CELL.free // diagonal neighbour only
    new EditSession(g).apply(floodFill(g, 0, 0, CELL.unknown))
    expect(at(g, 0, 0)).toBe(CELL.unknown)
    expect(at(g, 1, 1)).toBe(CELL.free)
  })

  it('does nothing when the seed already holds the value', () => {
    const g = grid(4, 4)
    expect(floodFill(g, 1, 1, CELL.free)).toBeNull()
  })

  it('survives a whole-grid fill without overflowing the stack', () => {
    // Recursive flood dies well before this size; iterative must not.
    const g = grid(400, 400)
    const session = new EditSession(g)
    session.apply(floodFill(g, 0, 0, CELL.occupied))
    expect(session.changedCells).toBe(160_000)
  })
})

describe('EditSession history', () => {
  it('undo restores the grid bit for bit', () => {
    const g = grid(8, 8)
    const before = g.cells.slice()
    const session = new EditSession(g)

    session.apply(paintDisc(g, 4, 4, 5, CELL.occupied))
    session.apply(paintRect(g, { column: 0, row: 0 }, { column: 2, row: 2 }, CELL.unknown))
    session.undo()
    session.undo()

    expect([...g.cells]).toEqual([...before])
    expect(session.changedCells).toBe(0)
    expect(session.canUndo).toBe(false)
  })

  it('redo reapplies what undo took away', () => {
    const g = grid(8, 8)
    const session = new EditSession(g)
    session.apply(paintDisc(g, 4, 4, 3, CELL.occupied))
    const painted = g.cells.slice()

    session.undo()
    expect(session.canRedo).toBe(true)
    session.redo()

    expect([...g.cells]).toEqual([...painted])
    expect(session.canRedo).toBe(false)
  })

  it('a new edit discards the redo branch', () => {
    const g = grid(8, 8)
    const session = new EditSession(g)
    session.apply(paintDisc(g, 1, 1, 1, CELL.occupied))
    session.undo()
    session.apply(paintDisc(g, 5, 5, 1, CELL.unknown))
    expect(session.canRedo).toBe(false)
  })

  it('counts a cell painted and painted back as unchanged', () => {
    // The count is what the operator reads before committing a version, so a
    // cell returned to its original value must not still be counted.
    const g = grid(4, 4)
    const session = new EditSession(g)
    session.apply(paintDisc(g, 1, 1, 1, CELL.occupied))
    expect(session.changedCells).toBe(1)
    session.apply(paintDisc(g, 1, 1, 1, CELL.free))
    expect(session.changedCells).toBe(0)
    expect(session.isDirty).toBe(false)
  })

  it('does not double-count a cell painted twice', () => {
    const g = grid(4, 4)
    const session = new EditSession(g)
    session.apply(paintDisc(g, 1, 1, 1, CELL.occupied))
    session.apply(paintDisc(g, 1, 1, 1, CELL.unknown))
    expect(session.changedCells).toBe(1)
  })

  it('reset returns to the loaded map and clears history', () => {
    const g = grid(6, 6)
    const before = g.cells.slice()
    const session = new EditSession(g)
    session.apply(paintRect(g, { column: 0, row: 0 }, { column: 4, row: 4 }, CELL.occupied))

    session.reset()

    expect([...g.cells]).toEqual([...before])
    expect(session.changedCells).toBe(0)
    expect(session.canUndo).toBe(false)
    expect(session.canRedo).toBe(false)
  })

  it('bounds history, and the count stays right past the limit', () => {
    const g = grid(4, HISTORY_LIMIT + 10)
    const session = new EditSession(g)
    for (let row = 0; row < HISTORY_LIMIT + 5; row += 1) {
      session.apply(paintDisc(g, 0, row, 1, CELL.occupied))
    }
    expect(session.changedCells).toBe(HISTORY_LIMIT + 5)

    // Only the retained patches can be undone; the count follows what actually
    // reverts rather than what was ever applied.
    let undone = 0
    while (session.undo()) undone += 1
    expect(undone).toBe(HISTORY_LIMIT)
    expect(session.changedCells).toBe(5)
  })

  it('never writes a value outside the three canonical ones', () => {
    const g = grid(20, 20)
    const session = new EditSession(g)
    session.apply(paintDisc(g, 5, 5, 7, CELL.occupied))
    session.apply(paintLine(g, { column: 0, row: 0 }, { column: 19, row: 19 }, 3, CELL.unknown))
    session.apply(floodFill(g, 19, 0, CELL.occupied))
    session.undo()

    const allowed = new Set<number>([CELL.occupied, CELL.unknown, CELL.free])
    expect([...new Set(g.cells)].every((value) => allowed.has(value))).toBe(true)
  })

  it('ignores a null patch without disturbing history', () => {
    const g = grid(4, 4)
    const session = new EditSession(g)
    expect(session.apply(null)).toBe(false)
    expect(session.canUndo).toBe(false)
  })
})
