/**
 * Classifying what the robot agent says about a map save.
 *
 * The agent writes the map to its own disk first and publishes to the registry
 * second, so "the file exists" and "the fleet can see it" are separate
 * outcomes. Collapsing them is how a survey gets lost: the operator reads a
 * success toast, navigates to the map list, and the map is not there.
 *
 * Contract, from robot_agent_node.py:
 *   "SAVED <map id> v<n>"   published to the registry
 *   "SAVED_LOCAL <path>"    written to the robot only, no backend configured
 *   "REJECTED ..."          not saved
 */

export type MapSaveOutcome =
  | { kind: 'published'; mapId: string }
  | { kind: 'local-only'; path: string }
  | { kind: 'refused'; reason: string }

const UNPUBLISHED_MESSAGE =
  'Written to the robot but not published — this robot has no backend configured. ' +
  'Restart it with AMR_BACKEND_URL and AMR_ROBOT_ID set, then save again; ' +
  'the survey is still on the robot disk.'

export function classifyMapSave(result: string | undefined | null): MapSaveOutcome {
  const text = (result ?? '').trim()

  // Checked before the published prefix, because "SAVED_LOCAL" starts with
  // "SAVED" and a prefix test in the wrong order reports a loss as a success.
  if (text.startsWith('SAVED_LOCAL')) {
    return { kind: 'local-only', path: text.slice('SAVED_LOCAL'.length).trim() }
  }
  if (text.startsWith('SAVED ')) {
    return { kind: 'published', mapId: text.split(/\s+/)[1] ?? '' }
  }
  return { kind: 'refused', reason: text || 'Save refused' }
}

/** Operator-facing text for an outcome that is not a publish. */
export function mapSaveFailureMessage(outcome: MapSaveOutcome): string {
  if (outcome.kind === 'local-only') return UNPUBLISHED_MESSAGE
  if (outcome.kind === 'refused') return outcome.reason
  return ''
}
