/**
 * When an alarm was raised, for a log that spans more than one day.
 *
 * A bare "01:09:44" on a list that keeps 200 entries does not say whether that
 * was last night or this morning. Today's entries show the time alone; older
 * ones say which day. 24-hour, because "what happened at 14:20" is how the
 * question gets asked on a shift.
 */
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function clock(date: Date): string {
  return [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((part) => String(part).padStart(2, '0'))
    .join(':')
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

export function alarmTime(at: number, now: number = Date.now()): string {
  const date = new Date(at)
  const days = Math.round((startOfDay(new Date(now)) - startOfDay(date)) / 86_400_000)
  if (days <= 0) return clock(date)
  if (days === 1) return `Yesterday ${clock(date)}`
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${clock(date)}`
}

/** "just now", "5m ago", "3h ago", "2d ago" — for the hover title. */
export function alarmAge(at: number, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - at) / 1000))
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}
