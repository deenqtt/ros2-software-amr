# ═══════════════════════════════════════════════════════════════════════════════
# AMR Simulation — ROS2 Humble + Gazebo Classic + Nav2
# Base: Ubuntu 22.04 (Jammy) — official Humble target
# ═══════════════════════════════════════════════════════════════════════════════

FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV TURTLEBOT3_MODEL=waffle_pi
ENV ROS_DOMAIN_ID=0
ENV GAZEBO_MODEL_PATH=/opt/ros/humble/share/turtlebot3_gazebo/models

SHELL ["/bin/bash", "-c"]

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    # ROS2 core tools
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    ros-humble-desktop \
    # Simulation
    ros-humble-gazebo-ros-pkgs \
    ros-humble-gazebo-ros2-control \
    ros-humble-turtlebot3 \
    ros-humble-turtlebot3-gazebo \
    ros-humble-turtlebot3-simulations \
    # SLAM
    ros-humble-slam-toolbox \
    # Navigation
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    # Web bridges
    ros-humble-rosbridge-suite \
    ros-humble-web-video-server \
    # Utilities
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# NOTE: opennav_docking main branch tidak kompatibel dengan Humble
# (butuh behaviortree-cpp v4 & nav2_ros_common yang belum ada di Humble apt).
# Docking di simulasi diimplementasi via navigate_to_pose ke koordinat dock.
# Akan diaktifkan saat robot fisik siap dengan versi yang kompatibel.

# ── AMR workspace ─────────────────────────────────────────────────────────────
WORKDIR /ros2_ws
COPY ros2_ws/src ./src

RUN apt-get update \
    && source /opt/ros/humble/setup.bash \
    && rosdep install --from-paths src -i -y --rosdistro humble \
    && colcon build --symlink-install \
    && rm -rf build/*/CMakeFiles \
    && rm -rf /var/lib/apt/lists/*

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

ENTRYPOINT ["bash", "/entrypoint.sh"]
CMD ["ros2", "launch", "amr_bringup", "bringup.launch.py"]
