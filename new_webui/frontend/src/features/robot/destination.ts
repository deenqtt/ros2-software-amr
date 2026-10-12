/**
 * The Destination picker on the Navigation page: one station, driven to
 * directly, without a mission.
 *
 * A station inside an active keep-out is still listed — hiding it would make
 * the operator wonder where it went — but cannot be picked: it can never be
 * reached, and the robot would otherwise try for minutes.
 */
import { keepoutAt, type Zone } from '@/domain/types/zone'
import { STATION_TYPE_LABEL, type Station } from '@/domain/types/station'
import type { SelectOption } from '@/shared/ui/select/Select.vue'

export function destinationOptions(
  stations: Pick<Station, 'id' | 'name' | 'type' | 'x' | 'y'>[],
  zones: Pick<Zone, 'kind' | 'enabled' | 'polygon' | 'name'>[],
): SelectOption<string>[] {
  return [...stations]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((station) => {
      const keepout = keepoutAt(zones, station.x, station.y)
      return {
        value: station.id,
        label: station.name,
        hint: keepout ? `inside keep-out "${keepout.name}"` : STATION_TYPE_LABEL[station.type],
        disabled: Boolean(keepout),
      }
    })
}
