/**
 * Stop & park, for any page that shows one robot.
 *
 * Shared because the robot bar carries it on every robot page: a stop that is
 * only on the navigation page is not there when someone is reading the
 * diagnostics of a robot that starts moving.
 *
 * Three separate things, in this order and for a reason. Cancelling the goal
 * alone leaves the agent free to send the next step; cancelling the run alone
 * leaves the robot finishing the goal it already has. Parking last is what
 * stops it resuming: without it the registry still says `nav`, and the agent
 * reconciles back within its sync period.
 *
 * Each step is attempted even if an earlier one failed. A stop that gives up
 * halfway is worse than no stop at all, because it looks like it worked.
 *
 * This is not the physical E-STOP. It cuts what the software is asking for,
 * not power to the motors, and the button says so.
 */
import { ref, type Ref } from 'vue'
import { toast } from 'vue-sonner'
import { useRosPool } from '@/app/ros/pool'
import { useFleetStore } from '@/stores/fleet'
import { useMissionStore } from '@/stores/missions'
import { SERVICE_TYPES } from '@/domain/ros/topics'
import { cancelAllGoals } from './cancelGoal'

export function useRobotStop(robotId: Ref<string>) {
  const pool = useRosPool()
  const fleet = useFleetStore()
  const missions = useMissionStore()
  const stopPending = ref(false)

  async function stopAndPark() {
    const target = fleet.byId(robotId.value)
    if (!target) return
    const failures: string[] = []
    stopPending.value = true
    try {
      const client = pool.clientFor(target.id)
      if (client) {
        try {
          await client.callService('cancelNavGoal', SERVICE_TYPES.cancelGoal, cancelAllGoals())
        } catch (error) {
          failures.push(`goal: ${error instanceof Error ? error.message : String(error)}`)
        }
      } else {
        failures.push('goal: no connection to this robot')
      }

      const run = missions.runForRobot(target.id)
      if (run) {
        try {
          await missions.cancel(run.id)
        } catch (error) {
          failures.push(`mission: ${missions.describeError(error)}`)
        }
      }

      try {
        await fleet.setMode(target.id, 'idle')
      } catch (error) {
        failures.push(`park: ${error instanceof Error ? error.message : String(error)}`)
      }

      if (failures.length === 0) {
        toast.error('Stopped', {
          description:
            'Goal canceled, mission canceled, robot parked. Use the physical E-STOP to cut power.',
        })
      } else {
        toast.error('Stopped, but not completely', { description: failures.join(' · ') })
      }
    } finally {
      stopPending.value = false
    }
  }

  return { stopAndPark, stopPending }
}
