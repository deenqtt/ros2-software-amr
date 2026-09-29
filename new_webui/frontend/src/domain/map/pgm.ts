/**
 * PGM reading and writing.
 *
 * Browsers cannot decode PGM, so this does it by hand. It is deliberately not
 * routed through a canvas: `getImageData` returns premultiplied, colour-managed
 * bytes, and a value that survives the round trip on one machine may not on
 * another. A map cell is data, not a picture, so it is never handed to the
 * rendering pipeline and read back.
 *
 * A ROS occupancy map holds three states, not a greyscale range. See CELL.
 */

/**
 * The only three values a cell may hold — what nav2's map_saver writes.
 *
 * Anything between is interpreted through the yaml's thresholds and lands on
 * "unknown", which a global costmap will not plan through. The margin is
 * thinner than it looks: at the project's default thresholds, 205 classifies as
 * unknown by 0.000078, two percent of one greyscale step. Values picked by eye
 * do not survive that.
 */
export const CELL = {
  occupied: 0,
  unknown: 205,
  free: 254,
} as const

export type Material = keyof typeof CELL
export type CellValue = (typeof CELL)[Material]

export const MATERIALS: readonly Material[] = ['occupied', 'free', 'unknown']

const CANONICAL: ReadonlySet<number> = new Set<number>(Object.values(CELL))

export function isCanonical(value: number): value is CellValue {
  return CANONICAL.has(value)
}

/**
 * A decoded map.
 *
 * `cells` is row-major with row 0 at the *top*, matching the image. ROS puts its
 * origin at the bottom-left, so anything converting a cell to world coordinates
 * has to flip the row — see cellToWorld.
 */
export interface Grid {
  width: number
  height: number
  cells: Uint8Array
}

export class PgmFormatError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PgmFormatError'
  }
}

const WHITESPACE = new Set([0x20, 0x09, 0x0a, 0x0d, 0x0b, 0x0c])
const HASH = 0x23

interface Header {
  magic: 'P5' | 'P2'
  width: number
  height: number
  maxValue: number
  offset: number
}

function readHeader(bytes: Uint8Array): Header {
  const magic = bytes[0] === 0x50 && bytes[1] === 0x35 ? 'P5' : bytes[1] === 0x32 ? 'P2' : null
  if (bytes[0] !== 0x50 || magic === null) {
    throw new PgmFormatError('Not a PGM: expected a P5 or P2 magic number')
  }

  const tokens: number[] = []
  let index = 2
  while (tokens.length < 3 && index < bytes.length) {
    const byte = bytes[index] as number
    // A comment may sit between any two header tokens; editors write them.
    if (byte === HASH) {
      while (index < bytes.length && bytes[index] !== 0x0a) index += 1
      index += 1
      continue
    }
    if (WHITESPACE.has(byte)) {
      index += 1
      continue
    }
    let end = index
    while (end < bytes.length && !WHITESPACE.has(bytes[end] as number)) end += 1
    const text = String.fromCharCode(...bytes.subarray(index, end))
    const value = Number.parseInt(text, 10)
    if (!Number.isInteger(value)) {
      throw new PgmFormatError(`PGM header holds a non-numeric token: "${text}"`)
    }
    tokens.push(value)
    index = end
  }

  const [width, height, maxValue] = tokens
  if (width === undefined || height === undefined || maxValue === undefined) {
    throw new PgmFormatError('PGM header is incomplete')
  }
  if (width <= 0 || height <= 0) {
    throw new PgmFormatError(`PGM has no area: ${width}x${height}`)
  }
  if (maxValue <= 0 || maxValue > 255) {
    throw new PgmFormatError(`PGM max value must be 1..255, got ${maxValue}`)
  }

  // Exactly one whitespace byte separates a P5 header from its binary data.
  return { magic, width, height, maxValue, offset: index + 1 }
}

export function decodePgm(bytes: Uint8Array): Grid {
  const header = readHeader(bytes)
  const expected = header.width * header.height

  if (header.magic === 'P5') {
    const body = bytes.subarray(header.offset)
    if (body.length < expected) {
      throw new PgmFormatError(
        `PGM is truncated: ${header.width}x${header.height} needs ${expected} cells, found ${body.length}`,
      )
    }
    // Copied, not referenced: the editor mutates these bytes, and the caller's
    // buffer may be a view onto a response it still holds.
    return { width: header.width, height: header.height, cells: body.slice(0, expected) }
  }

  const text = String.fromCharCode(...bytes.subarray(header.offset))
  const parts = text.split(/\s+/).filter(Boolean)
  if (parts.length < expected) {
    throw new PgmFormatError(
      `ASCII PGM is truncated: needs ${expected} cells, found ${parts.length}`,
    )
  }
  const cells = new Uint8Array(expected)
  for (let i = 0; i < expected; i += 1) {
    const value = Number.parseInt(parts[i] as string, 10)
    if (!Number.isInteger(value) || value < 0 || value > 255) {
      throw new PgmFormatError(`ASCII PGM holds a bad cell at ${i}: "${parts[i]}"`)
    }
    cells[i] = value
  }
  return { width: header.width, height: header.height, cells }
}

/** Always P5. One output encoding keeps the save path single. */
export function encodePgm(grid: Grid): Uint8Array {
  const header = `P5\n${grid.width} ${grid.height}\n255\n`
  const out = new Uint8Array(header.length + grid.cells.length)
  for (let i = 0; i < header.length; i += 1) out[i] = header.charCodeAt(i)
  out.set(grid.cells, header.length)
  return out
}

/** Every non-canonical value present, for reporting what an upload contains. */
export function nonCanonicalValues(grid: Grid): number[] {
  const seen = new Set<number>()
  for (const value of grid.cells) if (!isCanonical(value)) seen.add(value)
  return [...seen].sort((a, b) => a - b)
}

export interface MapPlacement {
  resolution: number
  originX: number
  originY: number
}

/**
 * The world coordinate at the centre of a cell.
 *
 * The row is flipped: PGM row 0 is the top of the image, while a ROS map's
 * origin is its bottom-left corner. Getting this wrong mirrors the map
 * vertically, which looks plausible on a symmetrical site.
 */
export function cellToWorld(
  grid: Grid,
  column: number,
  row: number,
  placement: MapPlacement,
): { x: number; y: number } {
  return {
    x: placement.originX + (column + 0.5) * placement.resolution,
    y: placement.originY + (grid.height - 1 - row + 0.5) * placement.resolution,
  }
}

/**
 * Continuous image coordinates for a world point.
 *
 * Returned in fractional cell units on the image's own axes, so a station can
 * sit between cells: a dock pose is a measurement, not a grid square, and
 * snapping it to the nearest cell would move it by up to half a cell — 2.5 cm
 * at the usual resolution, which is enough to miss a charging contact.
 *
 * The vertical axis is flipped, because a ROS map's origin is its bottom-left
 * corner while an image starts at the top.
 */
export function worldToGrid(
  grid: Grid,
  x: number,
  y: number,
  placement: MapPlacement,
): { gx: number; gy: number } {
  return {
    gx: (x - placement.originX) / placement.resolution,
    gy: grid.height - (y - placement.originY) / placement.resolution,
  }
}

/** The inverse of worldToGrid. */
export function gridToWorld(
  grid: Grid,
  gx: number,
  gy: number,
  placement: MapPlacement,
): { x: number; y: number } {
  return {
    x: placement.originX + gx * placement.resolution,
    y: placement.originY + (grid.height - gy) * placement.resolution,
  }
}

/** Whole cells covering a physical size, at least one. */
export function cellsForMetres(metres: number, resolution: number): number {
  if (!Number.isFinite(resolution) || resolution <= 0) return 1
  return Math.max(1, Math.round(metres / resolution))
}

/** What a whole number of cells actually covers, which is what the label shows. */
export function metresForCells(cells: number, resolution: number): number {
  return cells * resolution
}
