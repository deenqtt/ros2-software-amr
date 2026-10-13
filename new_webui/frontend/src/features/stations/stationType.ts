/**
 * How a station type looks, in one place.
 *
 * The colour was written out as a hex literal in both the canvas and the list,
 * which is two copies of a decision that has to stay identical: a marker drawn
 * in one colour and listed in another is not a legend, it is a puzzle.
 */
import { BatteryCharging, House, Repeat } from 'lucide-vue-next'
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
  home: {
    label: 'Home',
    colour: '#1a6ef5',
    icon: House,
    hint: 'Where the robot rests and starts from',
  },
  pick_drop: {
    label: 'Pick & drop',
    colour: '#0f9d58',
    icon: Repeat,
    hint: 'Where loads are collected or left; the mission step says which',
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
