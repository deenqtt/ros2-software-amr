/**
 * Gamepad input, via the browser's Gamepad API.
 *
 * A physical stick is the safer control, not merely the nicer one: it has a
 * mechanical centre. Let go and it returns to zero on its own. A screen
 * joystick does not — if the pointer is lost mid-drag, because the cursor left
 * the window or a click never came back, the last command simply stays.
 *
 * That advantage only holds with a deadman. A controller resting on a bench
 * with a stick pushed over is exactly the runaway a mechanical centre was
 * supposed to prevent, so driving requires a button to be held and stops the
 * moment the page loses focus.
 *
 * The API has no events for axis movement; it must be polled, and only from
 * inside a rAF loop while the page is visible.
 */

import { onBeforeUnmount, onMounted, readonly, ref, shallowRef } from 'vue'

/** Standard-mapping indices, which PS and Xbox pads both report. */
export const GAMEPAD_AXIS = {
  leftX: 0,
  leftY: 1,
  rightX: 2,
  rightY: 3,
} as const

export const GAMEPAD_BUTTON = {
  l1: 4,
  r1: 5,
  l2: 6,
  r2: 7,
} as const

export interface GamepadState {
  connected: boolean
  id: string
  /**
   * Whether the browser applied its standard layout.
   *
   * On Linux it often does not, and then the button indices are whatever the
   * driver happened to report — which is why the deadman accepts any shoulder
   * button rather than trusting index 4 to be L1.
   */
  standardMapping: boolean
  /** Forward-positive: the raw axis is inverted, because up is negative. */
  leftY: number
  /** Left-positive, matching ROS rather than the screen. */
  leftX: number
  deadmanHeld: boolean
  /** Indices currently pressed, for the diagnostic readout. */
  pressed: number[]
  /** Raw axis values, so a miscalibrated stick is visible rather than guessed at. */
  axes: number[]
}

/**
 * Any shoulder or trigger counts as the deadman.
 *
 * Naming one index assumes the browser applied standard mapping. When it does
 * not — common on Linux — L1 lands somewhere else and the control silently
 * does nothing, which reads to an operator as a broken robot rather than a
 * mismapped button.
 */
export const DEADMAN_BUTTONS = [4, 5, 6, 7] as const

export interface UseGamepadOptions {
  /** Buttons that may act as the deadman. Any shoulder or trigger by default. */
  deadmanButtons?: readonly number[]
  /** Called every frame while a pad is connected. */
  onSample?: (state: GamepadState) => void
}

const IDLE: GamepadState = {
  connected: false,
  id: '',
  standardMapping: false,
  leftY: 0,
  leftX: 0,
  deadmanHeld: false,
  pressed: [],
  axes: [],
}

export function useGamepad(options: UseGamepadOptions = {}) {
  const deadmanButtons = options.deadmanButtons ?? DEADMAN_BUTTONS

  const state = ref<GamepadState>({ ...IDLE })
  /** True once a pad has been seen, so its disappearance can be noticed. */
  const wasConnected = ref(false)
  const windowFocused = ref(typeof document === 'undefined' || document.hasFocus())
  const frame = shallowRef<number | null>(null)

  function firstConnectedPad(): Gamepad | null {
    if (typeof navigator === 'undefined' || !navigator.getGamepads) return null
    for (const pad of navigator.getGamepads()) {
      if (pad?.connected) return pad
    }
    return null
  }

  function sample() {
    const pad = firstConnectedPad()

    if (!pad) {
      if (state.value.connected) state.value = { ...IDLE }
      return
    }

    wasConnected.value = true
    const pressed: number[] = []
    pad.buttons.forEach((button, index) => {
      if (button.pressed) pressed.push(index)
    })

    state.value = {
      connected: true,
      id: pad.id,
      standardMapping: pad.mapping === 'standard',
      // The vertical axis reads negative when pushed up, and ROS linear.x is
      // positive forward. Flip here so nothing downstream has to remember.
      leftY: -(pad.axes[GAMEPAD_AXIS.leftY] ?? 0),
      // Likewise the horizontal axis reads positive to the right, while ROS
      // angular.z is positive counter-clockwise, which is left.
      leftX: -(pad.axes[GAMEPAD_AXIS.leftX] ?? 0),
      deadmanHeld: deadmanButtons.some((index) => pad.buttons[index]?.pressed),
      pressed,
      axes: [...pad.axes],
    }
    options.onSample?.(state.value)
  }

  function loop() {
    sample()
    frame.value = requestAnimationFrame(loop)
  }

  function onFocus() {
    windowFocused.value = true
  }

  function onBlur() {
    windowFocused.value = false
  }

  onMounted(() => {
    window.addEventListener('focus', onFocus)
    window.addEventListener('blur', onBlur)
    frame.value = requestAnimationFrame(loop)
  })

  onBeforeUnmount(() => {
    if (frame.value !== null) cancelAnimationFrame(frame.value)
    window.removeEventListener('focus', onFocus)
    window.removeEventListener('blur', onBlur)
  })

  return {
    state: readonly(state),
    windowFocused: readonly(windowFocused),
    /** A pad was in use and is no longer there. */
    wasConnected: readonly(wasConnected),
  }
}
