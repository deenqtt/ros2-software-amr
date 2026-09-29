/**
 * Parse a robot footprint out of a URDF string.
 *
 * Ported from web-ui useROS.js:498-534. Used to size the map marker to the
 * real robot rather than a fixed icon.
 */

export interface Footprint {
  /** Along the robot's x axis (forward), in metres. */
  length: number
  /** Along the robot's y axis (lateral), in metres. */
  width: number
}

const BASE_LINK_NAMES = ['base_footprint', 'base_link', 'chassis', 'body'] as const

function parseBox(box: Element): Footprint | null {
  const size = box.getAttribute('size')
  if (!size) return null
  // URDF box size is "x y z" — length, width, height.
  const parts = size.trim().split(/\s+/).map(Number)
  const [length, width] = parts
  if (length === undefined || width === undefined) return null
  if (!Number.isFinite(length) || !Number.isFinite(width)) return null
  if (length <= 0 || width <= 0) return null
  return { length, width }
}

function parseCylinder(cylinder: Element): Footprint | null {
  const radius = Number(cylinder.getAttribute('radius'))
  if (!Number.isFinite(radius) || radius <= 0) return null
  return { length: radius * 2, width: radius * 2 }
}

export function parseUrdfFootprint(urdf: string, parser: DOMParser = new DOMParser()): Footprint | null {
  if (!urdf) return null
  try {
    const doc = parser.parseFromString(urdf, 'text/xml')
    if (doc.querySelector('parsererror')) return null

    for (const name of BASE_LINK_NAMES) {
      const link = doc.querySelector(`link[name="${name}"]`)
      if (!link) continue

      // Collision geometry is the honest footprint; visual is a fallback.
      const box =
        link.querySelector('collision geometry box') ?? link.querySelector('visual geometry box')
      if (box) {
        const fromBox = parseBox(box)
        if (fromBox) return fromBox
      }

      const cylinder =
        link.querySelector('collision geometry cylinder') ??
        link.querySelector('visual geometry cylinder')
      if (cylinder) {
        const fromCylinder = parseCylinder(cylinder)
        if (fromCylinder) return fromCylinder
      }
    }
    return null
  } catch {
    return null
  }
}
