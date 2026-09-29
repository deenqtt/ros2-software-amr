/**
 * Editor state: tools, brush sizing, stroke assembly.
 *
 * Stroke assembly is the part that fails silently. A pointer sampled at 60 Hz
 * across a zoomed-out map skips whole cells between samples, so a freehand drag
 * that stamps rather than joins comes out dotted — which looks like a rendering
 * glitch rather than a data defect.
 */
import { describe, expect, it } from 'vitest'
import { CELL } from '@/domain/map/pgm'
import { useMapEditor } from '../composables/useMapEditor'

function editorWith(width = 20, height = 20, resolution = 0.05) {
  const editor = useMapEditor()
  editor.load(
    { width, height, cells: new Uint8Array(width * height).fill(CELL.free) },
    { resolution, originX: -0.5, originY: -0.5 },
  )
  return editor
}

function at(editor: ReturnType<typeof useMapEditor>, column: number, row: number) {
  const grid = editor.grid.value
  return grid?.cells[row * grid.width + column]
}

describe('brush sizing', () => {
  it('reports what whole cells actually cover, not what was asked for', () => {
    const editor = editorWith()
    editor.brushMetres.value = 0.2
    expect(editor.brushCells.value).toBe(4)
    expect(editor.brushActualMetres.value).toBeCloseTo(0.2, 6)
  })

  it('rescales with the map, because cells are not a physical unit', () => {
    const coarse = editorWith(20, 20, 0.1)
    coarse.brushMetres.value = 0.2
    // The same 20 cm is half as many cells on a coarser map.
    expect(coarse.brushCells.value).toBe(2)
  })
})

describe('freehand strokes', () => {
  it('joins samples instead of stamping them, so a fast drag has no gaps', () => {
    const editor = editorWith()
    editor.material.value = 'occupied'
    editor.brushMetres.value = 0.05

    editor.begin({ column: 2, row: 2 })
    // A jump of six cells, which is what one 60 Hz sample looks like zoomed out.
    editor.extend({ column: 8, row: 2 })

    for (let column = 2; column <= 8; column += 1) {
      expect(at(editor, column, 2)).toBe(CELL.occupied)
    }
  })

  it('ignores a sample that has not left the current cell', () => {
    const editor = editorWith()
    editor.material.value = 'occupied'
    editor.begin({ column: 5, row: 5 })
    expect(editor.extend({ column: 5, row: 5 })).toBeNull()
  })

  it('counts a repainted cell once', () => {
    const editor = editorWith()
    editor.material.value = 'occupied'
    editor.brushMetres.value = 0.05
    editor.begin({ column: 3, row: 3 })
    editor.extend({ column: 3, row: 4 })
    editor.extend({ column: 3, row: 3 })
    editor.end()
    expect(editor.changedCells.value).toBe(2)
  })
})

describe('shape tools', () => {
  it('commits a rectangle on release, not while dragging', () => {
    const editor = editorWith()
    editor.tool.value = 'rect'
    editor.material.value = 'occupied'

    editor.begin({ column: 2, row: 2 })
    editor.extend({ column: 5, row: 5 })
    // Nothing has landed yet: the operator must be able to see the extent first.
    expect(editor.changedCells.value).toBe(0)
    expect(editor.dragFrom.value).toEqual({ column: 2, row: 2 })

    editor.end()
    expect(editor.changedCells.value).toBe(16)
    expect(editor.dragFrom.value).toBeNull()
  })

  it('commits a line on release at the brush width', () => {
    const editor = editorWith()
    editor.tool.value = 'line'
    editor.material.value = 'occupied'
    editor.brushMetres.value = 0.05

    editor.begin({ column: 1, row: 10 })
    editor.extend({ column: 6, row: 10 })
    editor.end()

    for (let column = 1; column <= 6; column += 1) {
      expect(at(editor, column, 10)).toBe(CELL.occupied)
    }
  })

  it('cancelDrag abandons a shape without painting it', () => {
    const editor = editorWith()
    editor.tool.value = 'rect'
    editor.begin({ column: 1, row: 1 })
    editor.extend({ column: 9, row: 9 })
    editor.cancelDrag()
    editor.end()
    expect(editor.changedCells.value).toBe(0)
  })

  it('fill lands immediately, because there is nothing to preview', () => {
    const editor = editorWith(6, 6)
    editor.tool.value = 'fill'
    editor.material.value = 'unknown'
    editor.begin({ column: 0, row: 0 })
    expect(editor.changedCells.value).toBe(36)
  })
})

describe('history and reporting', () => {
  it('reports the changed fraction of the map', () => {
    const editor = editorWith(10, 10)
    editor.tool.value = 'rect'
    editor.material.value = 'occupied'
    editor.begin({ column: 0, row: 0 })
    editor.extend({ column: 4, row: 4 })
    editor.end()

    expect(editor.changedCells.value).toBe(25)
    expect(editor.changedFraction.value).toBeCloseTo(0.25, 6)
  })

  it('undo and redo track what is actually available', () => {
    const editor = editorWith()
    expect(editor.canUndo.value).toBe(false)

    editor.material.value = 'occupied'
    editor.begin({ column: 4, row: 4 })
    editor.end()

    expect(editor.canUndo.value).toBe(true)
    expect(editor.undo()).toBe(true)
    expect(editor.isDirty.value).toBe(false)
    expect(editor.canRedo.value).toBe(true)
    expect(editor.redo()).toBe(true)
    expect(editor.isDirty.value).toBe(true)
  })

  it('reset clears the edits and the history together', () => {
    const editor = editorWith()
    editor.material.value = 'occupied'
    editor.begin({ column: 4, row: 4 })
    editor.end()

    editor.reset()

    expect(editor.changedCells.value).toBe(0)
    expect(editor.canUndo.value).toBe(false)
  })

  it('does nothing before a map is loaded', () => {
    const editor = useMapEditor()
    expect(editor.begin({ column: 0, row: 0 })).toBeNull()
    expect(editor.undo()).toBe(false)
    expect(editor.changedCells.value).toBe(0)
  })
})

describe('the pan tool', () => {
  it('paints nothing, whatever gesture it receives', () => {
    // It was previously reachable only by keyboard, so this pins that it exists
    // as a tool and that selecting it makes the canvas inert.
    const editor = editorWith()
    editor.tool.value = 'pan'
    editor.material.value = 'occupied'

    editor.begin({ column: 5, row: 5 })
    editor.extend({ column: 9, row: 9 })
    editor.end()

    expect(editor.changedCells.value).toBe(0)
  })
})

describe('which options a tool uses', () => {
  // Hidden, not disabled. A greyed control is a question the operator has to
  // read every time, and the answer never changes.
  it.each([
    ['brush', true, true],
    ['line', true, true],
    ['rect', true, true],
    ['fill', true, false],
    ['pan', false, false],
  ] as const)('%s: material %s, brush size %s', (tool, material, brushSize) => {
    const editor = editorWith()
    editor.tool.value = tool
    expect(editor.usesMaterial.value).toBe(material)
    expect(editor.usesBrushSize.value).toBe(brushSize)
  })
})
