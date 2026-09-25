# custom_interfaces

ROS 2 custom interface definitions for the AMR (Autonomous Mobile Robot) system. This package provides services, actions, and messages used to communicate between the web interface and the robot's navigation and docking subsystems.

---

## Package Information

| Field      | Value                                             |
| ---------- | ------------------------------------------------- |
| Package    | `custom_interfaces`                               |
| Version    | 0.0.0                                             |
| License    | Apache-2.0                                        |
| Maintainer | Alfonsus Giovanni (alfonsusgiovanni360@gmail.com) |

---

## Interfaces

### Services (`srv/`)

#### `StationConfig.srv`

Manages station (dock) entries in the station data file. Used to add or delete station configurations.

**Request**

| Field        | Type      | Description                              |
| ------------ | --------- | ---------------------------------------- |
| `station_id` | `string`  | Unique station name/identifier           |
| `type`       | `uint8`   | Station type (e.g. pick, drop, charging) |
| `x_pose`     | `float32` | Station X position in map frame          |
| `y_pose`     | `float32` | Station Y position in map frame          |
| `yaw_pose`   | `float32` | Station yaw orientation in map frame     |
| `action`     | `uint8`   | `1` = add/update, `0` = delete           |

**Response**

| Field    | Type     | Description           |
| -------- | -------- | --------------------- |
| `result` | `string` | Result message string |

---

#### `DockCommand.srv`

Sends a docking or undocking command to the robot for a specified station.

**Request**

| Field        | Type     | Description                                       |
| ------------ | -------- | ------------------------------------------------- |
| `action`     | `string` | Command type: `"dock"`, `"undock"`, or `"cancel"` |
| `station_id` | `string` | Target station name/identifier                    |

**Response**

| Field    | Type     | Description           |
| -------- | -------- | --------------------- |
| `result` | `string` | Result message string |

---

### Actions (`action/`)

#### `MissionPlan.action`

Sends a full mission goal to the robot, including navigation to a station and execution of a task at that station.

**Goal**

| Field           | Type     | Description                                             |
| --------------- | -------- | ------------------------------------------------------- |
| `station_id`    | `string` | Target station name/identifier                          |
| `dest_tasks`    | `int8`   | Task to perform at destination (e.g. pick, drop, both)  |
| `continue_mode` | `bool`   | Whether to continue after task completion automatically |

**Result**

| Field    | Type     | Description                       |
| -------- | -------- | --------------------------------- |
| `result` | `string` | Mission completion result message |

**Feedback**

| Field         | Type     | Description                                                                                   |
| ------------- | -------- | --------------------------------------------------------------------------------------------- |
| `mission_sts` | `string` | Current mission status (e.g. `"NAVIGATING"`, `"DOCKING"`, `"WAITING PAYLOAD"`, `"COMPLETED"`) |

---

### Messages (`msg/`)

#### `RobotStatus.msg`

Publishes the current status of the robot, including docking state and operational status code.

| Field               | Type    | Description                           |
| ------------------- | ------- | ------------------------------------- |
| `robot_docked`      | `bool`  | `true` if robot is currently docked   |
| `robot_undocked`    | `bool`  | `true` if robot is currently undocked |
| `charging_state`    | `bool`  | `true` if robot is charging           |
| `robot_current_sts` | `uint8` | Current robot operational status code |

---

## Dependencies

- `geometry_msgs`
- `rosidl_default_generators` (build)
- `rosidl_default_runtime` (exec)
