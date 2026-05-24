/**
 * useMapMode — shared singleton for map interaction mode.
 * Allows sidebar panels (e.g. KeepoutEditor) to trigger map modes
 * without direct component coupling.
 */
import { ref } from 'vue'

// view | navigate | waypoint | keepout | initial_pose | destination | dock_placement
const _mode = ref('view')

export function useMapMode() {
  function setMode(mode) {
    _mode.value = mode
  }
  return { mapMode: _mode, setMode }
}
