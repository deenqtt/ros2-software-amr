# ═══════════════════════════════════════════════════════════════════════════════
# AMR Simulation foundation — ROS 2 Jazzy + Ubuntu Noble + Gazebo Harmonic
# Gazebo Classic assets remain only as rollback/reference material.
# ═══════════════════════════════════════════════════════════════════════════════

FROM ros:jazzy-ros-base-noble

ENV DEBIAN_FRONTEND=noninteractive
ENV TURTLEBOT3_MODEL=waffle_pi
ENV ROS_DOMAIN_ID=0
ENV GZ_SIM_RESOURCE_PATH=/ros2_ws/src/amr_simulation/models:/opt/ros/jazzy/share:/opt/ros/jazzy/share/turtlebot3_gazebo/models

SHELL ["/bin/bash", "-c"]

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    # ROS 2 core tools
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    ros-jazzy-desktop \
    # Modern Gazebo foundation for the later simulation migration phase
    ros-jazzy-ros-gz-sim \
    ros-jazzy-ros-gz-bridge \
    ros-jazzy-ros-gz-image \
    ros-jazzy-turtlebot3 \
    ros-jazzy-turtlebot3-gazebo \
    ros-jazzy-turtlebot3-simulations \
    # SLAM
    ros-jazzy-slam-toolbox \
    # Navigation
    ros-jazzy-navigation2 \
    ros-jazzy-nav2-bringup \
    # Web bridges
    ros-jazzy-rosbridge-suite \
    ros-jazzy-web-video-server \
    # Robot description and custom-node runtime dependencies
    ros-jazzy-robot-state-publisher \
    ros-jazzy-xacro \
    ros-jazzy-cv-bridge \
    ros-jazzy-tf2-ros \
    ros-jazzy-teleop-twist-keyboard \
    python3-opencv \
    python3-numpy \
    # Utilities
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# NOTE: OpenNav docking is deliberately not activated in Phase 0/1.
# The current simulator runtime uses custom Python docking logic. Its package
# dependency remains subject to the separate docking validation phase.

# ── AMR workspace ─────────────────────────────────────────────────────────────
WORKDIR /ros2_ws
COPY ros2_ws/src ./src

# Phase 3 has removed the active Classic dependency, so the image build is a
# real full-workspace gate rather than a discovery-only foundation check.
ARG BUILD_WORKSPACE=true
RUN source /opt/ros/jazzy/setup.bash \
    && colcon list \
    && if [[ "${BUILD_WORKSPACE}" == "true" ]]; then \
         rosdep update --rosdistro jazzy; \
         rosdep install --from-paths src --ignore-src -y --rosdistro jazzy; \
         colcon build --symlink-install; \
       fi

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

ENTRYPOINT ["bash", "/entrypoint.sh"]
CMD ["ros2", "launch", "amr_bringup", "bringup.launch.py"]
