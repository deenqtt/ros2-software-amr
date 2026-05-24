#!/bin/bash
set -e

# Source ROS environments in order
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash 2>/dev/null || true

export TURTLEBOT3_MODEL=${TURTLEBOT3_MODEL:-waffle_pi}
export GAZEBO_MODEL_PATH=/opt/ros/humble/share/turtlebot3_gazebo/models:${GAZEBO_MODEL_PATH:-}
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}

# Gazebo needs display
export DISPLAY=${DISPLAY:-:0}

exec "$@"
