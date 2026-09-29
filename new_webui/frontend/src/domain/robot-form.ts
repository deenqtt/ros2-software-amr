/**
 * Validation for the robot registry form.
 *
 * Kept out of the component so it can be tested without mounting anything, and
 * so the same rules apply whether a robot is created in a dialog, imported, or
 * seeded on first run.
 */
import { ROS_DOMAIN_ID_MAX, ROS_DOMAIN_ID_SAFE_MAX, type RobotConfig } from './types'

export interface RobotFormValues {
  name: string
  bridgeUrl: string
  /** Raw field value — empty string means "not set". */
  rosDomainId: string
}

export interface RobotFormErrors {
  name?: string
  bridgeUrl?: string
  rosDomainId?: string
}

export interface RobotFormWarnings {
  rosDomainId?: string
}

const WEBSOCKET_PROTOCOLS = new Set(['ws:', 'wss:'])

function normalizeName(value: string): string {
  return value.trim().toLocaleLowerCase()
}

export function validateRobotForm(
  values: RobotFormValues,
  existing: RobotConfig[],
  /** Set when editing, so a robot does not collide with itself. */
  editingId: string | null = null,
): RobotFormErrors {
  const errors: RobotFormErrors = {}

  const name = values.name.trim()
  if (!name) {
    errors.name = 'Name is required.'
  } else if (
    existing.some((r) => r.id !== editingId && normalizeName(r.name) === normalizeName(name))
  ) {
    // Two robots sharing a name is how an operator ends up driving the wrong
    // one, so this is a hard error rather than a warning.
    errors.name = 'Another robot already uses this name.'
  }

  const bridgeUrl = values.bridgeUrl.trim()
  if (!bridgeUrl) {
    errors.bridgeUrl = 'Bridge URL is required.'
  } else {
    try {
      const parsed = new URL(bridgeUrl)
      if (!WEBSOCKET_PROTOCOLS.has(parsed.protocol)) {
        errors.bridgeUrl = 'Must start with ws:// or wss://'
      } else if (!parsed.hostname) {
        errors.bridgeUrl = 'Missing a host.'
      } else if (
        existing.some((r) => r.id !== editingId && r.bridgeUrl.trim() === bridgeUrl)
      ) {
        errors.bridgeUrl = 'Another robot already uses this bridge.'
      }
    } catch {
      errors.bridgeUrl = 'Not a valid WebSocket URL.'
    }
  }

  const domain = values.rosDomainId.trim()
  if (domain) {
    const parsed = Number(domain)
    if (!Number.isInteger(parsed)) {
      errors.rosDomainId = 'Must be a whole number.'
    } else if (parsed < 0 || parsed > ROS_DOMAIN_ID_MAX) {
      errors.rosDomainId = `Must be between 0 and ${ROS_DOMAIN_ID_MAX}.`
    }
  }

  return errors
}

/** Non-blocking advice, shown alongside a field that is technically valid. */
export function warnRobotForm(values: RobotFormValues): RobotFormWarnings {
  const warnings: RobotFormWarnings = {}
  const domain = values.rosDomainId.trim()
  if (domain) {
    const parsed = Number(domain)
    if (Number.isInteger(parsed) && parsed > ROS_DOMAIN_ID_SAFE_MAX && parsed <= ROS_DOMAIN_ID_MAX) {
      warnings.rosDomainId = `Above ${ROS_DOMAIN_ID_SAFE_MAX} can collide with ephemeral ports on some systems.`
    }
  }
  return warnings
}

export function hasErrors(errors: RobotFormErrors): boolean {
  return Object.keys(errors).length > 0
}

/** Form values -> the shape the store stores. */
export function toRobotPatch(values: RobotFormValues): Pick<
  RobotConfig,
  'name' | 'bridgeUrl' | 'rosDomainId'
> {
  const domain = values.rosDomainId.trim()
  return {
    name: values.name.trim(),
    bridgeUrl: values.bridgeUrl.trim(),
    rosDomainId: domain ? Number(domain) : null,
  }
}

export function fromRobot(robot: RobotConfig): RobotFormValues {
  return {
    name: robot.name,
    bridgeUrl: robot.bridgeUrl,
    rosDomainId: robot.rosDomainId === null ? '' : String(robot.rosDomainId),
  }
}
