/**
 * How a station type looks, in one place.
 *
 * The colour was written out as a hex literal in both the canvas and the list,
 * which is two copies of a decision that has to stay identical: a marker drawn
 * in one colour and listed in another is not a legend, it is a puzzle.
 */
import { BatteryCharging, PackageOpen, PackagePlus, Repeat } from 'lucide-vue-next'
import type { Component } from 'vue'
import { STATION_TYPES, type StationType } from '@/domain/types'

export interface StationTypeStyle {
  label: string
  /** Drawn on a canvas, so a CSS variable is no use — this has to be a value. */
  colour: string
  icon: Component
  hint: string
}

export const STATION_TYPE_STYLE: Record<StationType, StationTypeStyle> = {
  pick: {
    label: 'Pick',
    colour: '#1a6ef5',
    icon: PackagePlus,
    hint: 'Where a load is collected',
  },
  drop: {
    label: 'Drop',
    colour: '#7a3df5',
    icon: PackageOpen,
    hint: 'Where a load is left',
  },
  pick_drop: {
    label: 'Pick & drop',
    colour: '#0f9d58',
    icon: Repeat,
    hint: 'Both, at the same pose',
  },
  charging: {
    label: 'Charging',
    colour: '#f0a020',
    icon: BatteryCharging,
    hint: 'A dock the robot returns to',
  },
}

/** In the order they are offered, which is the order of the ROS enum. */
export const STATION_TYPE_LIST = STATION_TYPES.map((value) => ({
  value,
  ...STATION_TYPE_STYLE[value],
}))
