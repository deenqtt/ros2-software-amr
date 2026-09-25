#!/bin/bash
set -e

# Source ROS environments in order.
source /opt/ros/jazzy/setup.bash
source /ros2_ws/install/setup.bash 2>/dev/null || true

export TURTLEBOT3_MODEL=${TURTLEBOT3_MODEL:-waffle_pi}
export GZ_SIM_RESOURCE_PATH=/ros2_ws/src/amr_simulation/models:/opt/ros/jazzy/share:/opt/ros/jazzy/share/turtlebot3_gazebo/models:${GZ_SIM_RESOURCE_PATH:-}
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}

# GUI is supplied by Compose in development; headless mode can leave it unset.
export DISPLAY=${DISPLAY:-:0}

exec "$@"
