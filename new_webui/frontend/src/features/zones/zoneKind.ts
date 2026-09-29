/**
 * How a zone kind looks and reads, in one place.
 *
 * The colour is written into a canvas, so it has to be a value rather than a
 * CSS variable — and it is defined once here because a polygon drawn in one
 * colour and listed in another is not a legend, it is a puzzle.
 */
import { Ban, Gauge, ToggleRight, TrendingDown } from 'lucide-vue-next'
import type { Component } from 'vue'
import { ZONE_KINDS, type Zone, type ZoneKind } from '@/domain/types'

export interface ZoneKindStyle {
  label: string
  colour: string
  icon: Component
  /** What it does, in the words an operator would use. */
  hint: string
  /** The Nav2 filter behind it, for anyone wondering why the kinds group oddly. */
  filter: string
}

export const ZONE_KIND_STYLE: Record<ZoneKind, ZoneKindStyle> = {
  keepout: {
    label: 'Keep out',
    colour: '#e5484d',
    icon: Ban,
    hint: 'Never enter. Treated like a wall.',
    filter: 'KeepoutFilter',
  },
  avoid: {
    label: 'Avoid',
    colour: '#f0a020',
    icon: TrendingDown,
    hint: 'Go around if there is a reasonable way round.',
    filter: 'KeepoutFilter',
  },
  speed: {
    label: 'Speed limit',
    colour: '#1a6ef5',
    icon: Gauge,
    hint: 'Slow down while inside.',
    filter: 'SpeedFilter',
  },
  binary: {
    label: 'Trigger',
    colour: '#7a3df5',
    icon: ToggleRight,
    hint: 'Switches a signal on while inside — a beacon, a buzzer.',
    filter: 'BinaryFilter',
  },
}

export const ZONE_KIND_LIST = ZONE_KINDS.map((value) => ({
  value,
  ...ZONE_KIND_STYLE[value],
}))

/** The kind-specific setting, spelled out for a list row. */
export function zoneSetting(zone: Zone): string {
  if (zone.kind === 'speed') return `${zone.speedLimit?.toFixed(1)} m/s`
  if (zone.kind === 'avoid') return `reluctance ${zone.avoidCost}`
  return ''
}
