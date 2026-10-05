/**
 * Words for a map's row in the phone list, where each map gets one line under
 * its name instead of a column per fact.
 */

/**
 * Which robots run a map, as a phrase: "AMR-01, AMR-02 +1".
 *
 * Names rather than a count: which robot runs which map is the question the
 * row exists to answer. The rest collapse into "+N" so the line stays one line.
 */
export function robotsSummary(names: readonly string[], shown = 2): string {
  if (!names.length) return 'Not on any robot'
  const listed = names.slice(0, shown).join(', ')
  const rest = names.length - shown
  return rest > 0 ? `${listed} +${rest}` : listed
}
