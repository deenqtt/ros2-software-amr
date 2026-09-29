/**
 * Editing state for one map: tool, material, brush, history.
 *
 * Stroke assembly lives here rather than in the canvas. A pointer at 60 Hz
 * across a zoomed-out map skips whole cells between samples, so a freehand drag
 * has to be joined with lines — and that is a decision about the map, not about
 * the pointer.
 */
import { computed, ref, shallowRef } from 'vue'
import {
  cellsForMetres,
  metresForCells,
  type CellValue,
  type Grid,
  type Material,
} from '@/domain/map/pgm'
import {
  EditSession,
  floodFill,
  paintDisc,
  paintLine,
  paintRect,
  valueOf,
  type Patch,
} from '@/domain/map/edit'

export type Tool = 'brush' | 'line' | 'rect' | 'fill' | 'pan'

export interface Cell {
  column: number
  row: number
}

/** Brush sizes offered, in metres. Snapped to whole cells when applied. */
export const BRUSH_METRES = [0.05, 0.1, 0.2, 0.5, 1] as const

export function useMapEditor() {
  const session = shallowRef<EditSession | null>(null)
  const placement = ref({ resolution: 0.05, originX: 0, originY: 0 })

  const tool = ref<Tool>('brush')
  const material = ref<Material>('occupied')
  const brushMetres = ref<number>(0.1)

  /** Bumped on every change, so views can watch one thing to redraw. */
  const revision = ref(0)

  /**
   * While held, the canvas shows the map as it was loaded.
   *
   * The only way to judge "is my correction right" without undoing and redoing
   * it, which loses the place on screen.
   */
  const previewOriginal = ref(false)

  /** Set while a shape tool is mid-drag, for the preview outline. */
  const dragFrom = ref<Cell | null>(null)
  const dragTo = ref<Cell | null>(null)

  let lastCell: Cell | null = null

  const grid = computed<Grid | null>(() => session.value?.grid ?? null)
  /** Cells the canvas should draw: the baseline while previewing, else the live grid. */
  const displayCells = computed<Uint8Array | null>(() =>
    previewOriginal.value ? (session.value?.originalCells ?? null) : null,
  )
  const brushCells = computed(() => cellsForMetres(brushMetres.value, placement.value.resolution))
  /** What the brush actually covers, which is what the label must show. */
  const brushActualMetres = computed(() =>
    metresForCells(brushCells.value, placement.value.resolution),
  )
  const changedCells = computed(() => {
    void revision.value
    return session.value?.changedCells ?? 0
  })
  const totalCells = computed(() => {
    const value = grid.value
    return value ? value.width * value.height : 0
  })
  const changedFraction = computed(() =>
    totalCells.value === 0 ? 0 : changedCells.value / totalCells.value,
  )
  const canUndo = computed(() => {
    void revision.value
    return session.value?.canUndo ?? false
  })
  const canRedo = computed(() => {
    void revision.value
    return session.value?.canRedo ?? false
  })
  const isDirty = computed(() => changedCells.value > 0)

  /**
   * Which options the active tool actually uses.
   *
   * Irrelevant controls are hidden rather than disabled: a greyed brush stepper
   * beside the Pan tool is a question the operator has to read and answer, and
   * the answer is always "not with this tool".
   */
  const usesMaterial = computed(() => tool.value !== 'pan')
  const usesBrushSize = computed(() => tool.value !== 'pan' && tool.value !== 'fill')

  function load(loaded: Grid, where: { resolution: number; originX: number; originY: number }) {
    session.value = new EditSession(loaded)
    placement.value = where
    revision.value += 1
  }

  function value(): CellValue {
    return valueOf(material.value)
  }

  /** Apply a patch and report which cells moved, so a view can repaint just those. */
  function commit(patch: Patch | null): Int32Array | null {
    const active = session.value
    if (!active || !active.apply(patch) || patch === null) return null
    revision.value += 1
    return patch.indices
  }

  // ── Gestures ───────────────────────────────────────────────────────────────

  function begin(cell: Cell): Int32Array | null {
    const active = session.value
    if (!active) return null
    // Guarded here, not only in the canvas. The canvas currently routes a pan
    // gesture away before it ever reaches this, but a tool that paints when
    // asked to pan is a defect waiting for the next change to that routing.
    if (tool.value === 'pan') return null

    if (tool.value === 'fill') {
      return commit(floodFill(active.grid, cell.column, cell.row, value()))
    }
    if (tool.value === 'line' || tool.value === 'rect') {
      // Shapes commit on release: the operator has to be able to see the extent
      // before it lands, and a rectangle dragged the wrong way is common.
      dragFrom.value = cell
      dragTo.value = cell
      return null
    }
    lastCell = cell
    return commit(paintDisc(active.grid, cell.column, cell.row, brushCells.value, value()))
  }

  function extend(cell: Cell): Int32Array | null {
    const active = session.value
    if (!active || tool.value === 'pan') return null

    if (tool.value === 'line' || tool.value === 'rect') {
      dragTo.value = cell
      return null
    }
    if (tool.value !== 'brush') return null

    const previous = lastCell
    lastCell = cell
    if (!previous) return commit(paintDisc(active.grid, cell.column, cell.row, brushCells.value, value()))
    if (previous.column === cell.column && previous.row === cell.row) return null
    // Joined, not stamped: at low zoom consecutive samples are cells apart and
    // a stamped stroke comes out dotted.
    return commit(paintLine(active.grid, previous, cell, brushCells.value, value()))
  }

  function end(): Int32Array | null {
    const active = session.value
    const from = dragFrom.value
    const to = dragTo.value
    lastCell = null
    dragFrom.value = null
    dragTo.value = null
    if (!active || !from || !to) return null

    if (tool.value === 'line') {
      return commit(paintLine(active.grid, from, to, brushCells.value, value()))
    }
    if (tool.value === 'rect') {
      return commit(paintRect(active.grid, from, to, value()))
    }
    return null
  }

  function cancelDrag(): void {
    lastCell = null
    dragFrom.value = null
    dragTo.value = null
  }

  function undo(): boolean {
    if (!session.value?.undo()) return false
    revision.value += 1
    return true
  }

  function redo(): boolean {
    if (!session.value?.redo()) return false
    revision.value += 1
    return true
  }

  function reset(): void {
    session.value?.reset()
    cancelDrag()
    revision.value += 1
  }

  return {
    grid,
    displayCells,
    previewOriginal,
    placement,
    tool,
    material,
    brushMetres,
    brushCells,
    brushActualMetres,
    revision,
    dragFrom,
    dragTo,
    changedCells,
    totalCells,
    changedFraction,
    canUndo,
    canRedo,
    isDirty,
    usesMaterial,
    usesBrushSize,
    load,
    begin,
    extend,
    end,
    cancelDrag,
    undo,
    redo,
    reset,
  }
}
