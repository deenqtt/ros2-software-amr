/**
 * Map editing as data.
 *
 * No canvas, no Vue. A stroke is a function from a grid and a gesture to a
 * patch; a patch is a reversible record of which cells moved and what they held
 * before. Everything the view does is drive this and draw the result.
 *
 * Undo is diff-based rather than snapshot-based, and that is not premature. A
 * 100 m x 100 m site at 0.05 m/cell is 2000x2000 = 4 MB per snapshot, so fifty
 * undo steps would be 200 MB of history. A patch costs five bytes per cell it
 * actually touched.
 */

import { CELL, type CellValue, type Grid } from './pgm'

/** A reversible change. One stroke paints one value, so `value` is scalar. */
export interface Patch {
  indices: Int32Array
  /** What each of those cells held before, index-aligned with `indices`. */
  previous: Uint8Array
  value: CellValue
}

/**
 * How many patches to keep.
 *
 * Bounded so a long session cannot grow without limit. Fifty is well past what
 * an operator reaches back through, and a flood fill's patch is the only large
 * one — a full-map fill on the site above is 16 MB, so even the worst case stays
 * inside a browser tab.
 */
export const HISTORY_LIMIT = 50

function patchFrom(grid: Grid, touched: number[], value: CellValue): Patch | null {
  // Cells already holding the target value are dropped here rather than at each
  // call site, so a stroke over unchanged ground produces no history entry and
  // undo does not appear to do nothing.
  const changed: number[] = []
  for (const index of touched) {
    if (grid.cells[index] !== value) changed.push(index)
  }
  if (changed.length === 0) return null

  const indices = Int32Array.from(changed)
  const previous = new Uint8Array(indices.length)
  for (let i = 0; i < indices.length; i += 1) {
    previous[i] = grid.cells[indices[i] as number] as number
  }
  return { indices, previous, value }
}

function inside(grid: Grid, column: number, row: number): boolean {
  return column >= 0 && row >= 0 && column < grid.width && row < grid.height
}

/**
 * Cells under a round brush of `diameter` cells centred on one cell.
 *
 * Diameter rather than radius, because that is the number the operator sets and
 * an odd diameter is what makes a brush symmetric about the cell under the
 * cursor. Diameter 1 is exactly that cell.
 */
function discCells(grid: Grid, column: number, row: number, diameter: number): number[] {
  const size = Math.max(1, Math.round(diameter))
  const out: number[] = []
  if (size === 1) {
    if (inside(grid, column, row)) out.push(row * grid.width + column)
    return out
  }

  const radius = size / 2
  const reach = Math.ceil(radius)
  for (let dy = -reach; dy <= reach; dy += 1) {
    for (let dx = -reach; dx <= reach; dx += 1) {
      // Inclusive at the radius. Excluding it undersizes every brush — a
      // diameter of 2 would cover a single cell, which is not what the label
      // says. Distances are between cell centres, so the disc stays centred.
      if (Math.hypot(dx, dy) > radius) continue
      const x = column + dx
      const y = row + dy
      if (inside(grid, x, y)) out.push(y * grid.width + x)
    }
  }
  return out
}

export function paintDisc(
  grid: Grid,
  column: number,
  row: number,
  diameter: number,
  value: CellValue,
): Patch | null {
  return patchFrom(grid, discCells(grid, column, row, diameter), value)
}

/**
 * A straight run of brush stamps, for closing a doorway or drawing a wall.
 *
 * Bresenham, then a disc at every step. Stamping only the endpoints would leave
 * a dotted line at any brush smaller than the gap between samples.
 */
export function paintLine(
  grid: Grid,
  from: { column: number; row: number },
  to: { column: number; row: number },
  diameter: number,
  value: CellValue,
): Patch | null {
  const touched: number[] = []
  let x = Math.round(from.column)
  let y = Math.round(from.row)
  const x1 = Math.round(to.column)
  const y1 = Math.round(to.row)
  const dx = Math.abs(x1 - x)
  const dy = Math.abs(y1 - y)
  const stepX = x < x1 ? 1 : -1
  const stepY = y < y1 ? 1 : -1
  let error = dx - dy

  for (;;) {
    touched.push(...discCells(grid, x, y, diameter))
    if (x === x1 && y === y1) break
    const doubled = error * 2
    if (doubled > -dy) {
      error -= dy
      x += stepX
    }
    if (doubled < dx) {
      error += dx
      y += stepY
    }
  }
  return patchFrom(grid, touched, value)
}

/** An axis-aligned block, filled. Corners may be given in any order. */
export function paintRect(
  grid: Grid,
  from: { column: number; row: number },
  to: { column: number; row: number },
  value: CellValue,
): Patch | null {
  const left = Math.max(0, Math.min(from.column, to.column))
  const right = Math.min(grid.width - 1, Math.max(from.column, to.column))
  const top = Math.max(0, Math.min(from.row, to.row))
  const bottom = Math.min(grid.height - 1, Math.max(from.row, to.row))
  if (left > right || top > bottom) return null

  const touched: number[] = []
  for (let y = top; y <= bottom; y += 1) {
    for (let x = left; x <= right; x += 1) touched.push(y * grid.width + x)
  }
  return patchFrom(grid, touched, value)
}

/**
 * Replace a contiguous region of one value with another.
 *
 * Four-connected, and iterative: a recursive flood on a warehouse-sized free
 * area overflows the call stack long before it finishes.
 *
 * This is the highest-leverage tool — one click clears a room speckled with
 * unknown — and the most dangerous, because one click can also repaint half the
 * map. Undo is what makes it safe to offer.
 */
export function floodFill(
  grid: Grid,
  column: number,
  row: number,
  value: CellValue,
): Patch | null {
  if (!inside(grid, column, row)) return null
  const target = grid.cells[row * grid.width + column] as number
  if (target === value) return null

  const visited = new Uint8Array(grid.cells.length)
  const stack = [row * grid.width + column]
  const touched: number[] = []

  while (stack.length > 0) {
    const index = stack.pop() as number
    if (visited[index]) continue
    visited[index] = 1
    if (grid.cells[index] !== target) continue
    touched.push(index)

    const x = index % grid.width
    const y = (index - x) / grid.width
    if (x > 0) stack.push(index - 1)
    if (x < grid.width - 1) stack.push(index + 1)
    if (y > 0) stack.push(index - grid.width)
    if (y < grid.height - 1) stack.push(index + grid.width)
  }
  return patchFrom(grid, touched, value)
}

/**
 * One editing session: the live grid, its history, and how far it has drifted
 * from what was loaded.
 *
 * The grid is mutated in place. Copying 4 MB per stroke would make a freehand
 * drag allocate faster than the browser can collect.
 */
export class EditSession {
  readonly grid: Grid
  private readonly original: Uint8Array
  private readonly done: Patch[] = []
  private readonly undone: Patch[] = []
  private drift = 0

  constructor(grid: Grid) {
    this.grid = grid
    this.original = grid.cells.slice()
  }

  /**
   * The map as it was loaded, for a before/after comparison.
   *
   * Returned by reference and must not be written to: it is the baseline the
   * changed-cell count and `reset` are measured against.
   */
  get originalCells(): Uint8Array {
    return this.original
  }

  get canUndo(): boolean {
    return this.done.length > 0
  }

  get canRedo(): boolean {
    return this.undone.length > 0
  }

  /**
   * Cells differing from the loaded map.
   *
   * Tracked incrementally, not by scanning: this is shown beside the save
   * button, and re-counting four million cells on every stroke would stall the
   * drag it is meant to describe.
   */
  get changedCells(): number {
    return this.drift
  }

  get isDirty(): boolean {
    return this.drift > 0
  }

  /** Apply a patch, or do nothing when the operation touched nothing. */
  apply(patch: Patch | null): boolean {
    if (patch === null) return false
    this.write(patch.indices, () => patch.value)
    this.done.push(patch)
    if (this.done.length > HISTORY_LIMIT) this.done.shift()
    // A new edit invalidates the redo branch, as in every other editor.
    this.undone.length = 0
    return true
  }

  undo(): boolean {
    const patch = this.done.pop()
    if (patch === undefined) return false
    this.write(patch.indices, (slot) => patch.previous[slot] as number)
    this.undone.push(patch)
    return true
  }

  redo(): boolean {
    const patch = this.undone.pop()
    if (patch === undefined) return false
    this.write(patch.indices, () => patch.value)
    this.done.push(patch)
    return true
  }

  /** Discard every edit and return to the loaded map. */
  reset(): void {
    this.grid.cells.set(this.original)
    this.done.length = 0
    this.undone.length = 0
    this.drift = 0
  }

  private write(indices: Int32Array, valueAt: (slot: number) => number): void {
    for (let slot = 0; slot < indices.length; slot += 1) {
      const index = indices[slot] as number
      const before = this.grid.cells[index] as number
      const after = valueAt(slot)
      if (before === after) continue
      const origin = this.original[index] as number
      if (before === origin) this.drift += 1
      else if (after === origin) this.drift -= 1
      this.grid.cells[index] = after
    }
  }
}

/** The value a material paints. */
export function valueOf(material: keyof typeof CELL): CellValue {
  return CELL[material]
}
