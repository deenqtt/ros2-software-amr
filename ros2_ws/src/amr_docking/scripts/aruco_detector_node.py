#!/usr/bin/env python3
"""
aruco_detector_node — detect ArUco ID=0 (DICT_4X4_50) from rear camera.

Subscribes:
  /camera/image_raw       (sensor_msgs/Image)

Publishes:
  /aruco/detected         (std_msgs/Bool)    — marker visible this frame
  /aruco/marker_pose      (geometry_msgs/PoseStamped) — pose in camera_rgb_optical_frame
  /aruco/distance         (std_msgs/Float32) — Z-depth to marker (metres)
  /aruco/lateral_offset   (std_msgs/Float32) — X-offset in camera frame (metres, + = right)
  /aruco/debug_image      (sensor_msgs/Image) — optional annotated image

Camera intrinsics are taken from CameraInfo if available (/camera/camera_info),
otherwise a fallback for the simulated 1920×1080 FOV=80° camera is used.
"""

import math

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Bool, Float32


# ── ArUco config ───────────────────────────────────────────────────────────────
ARUCO_DICT_ID = cv2.aruco.DICT_4X4_50
MARKER_ID     = 0
MARKER_SIZE   = 0.10   # metres — physical size of printed ArUco marker


class ArucoDetectorNode(Node):
    def __init__(self):
        super().__init__('aruco_detector_node')

        self._bridge   = CvBridge()
        self._aruco_dict   = cv2.aruco.Dictionary_get(ARUCO_DICT_ID)
        self._aruco_params = cv2.aruco.DetectorParameters_create()
        # Relax detection for simulation (lower quality texture render)
        self._aruco_params.adaptiveThreshWinSizeMin  = 3
        self._aruco_params.adaptiveThreshWinSizeMax  = 23
        self._aruco_params.adaptiveThreshWinSizeStep = 10
        self._aruco_params.minMarkerPerimeterRate     = 0.02

        # Camera intrinsics — overwritten when /camera/camera_info arrives
        # Fallback: 1920×1080, horizontal FOV ≈ 80° (1.3962634 rad)
        fx = 960.0 / math.tan(1.3962634 / 2.0)  # ≈ 952
        self._camera_matrix = np.array([
            [fx,  0.0, 960.0],
            [0.0, fx,  540.0],
            [0.0, 0.0,   1.0],
        ], dtype=np.float64)
        self._dist_coeffs = np.zeros((5, 1), dtype=np.float64)
        self._got_camera_info = False

        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(Image,      '/camera/image_raw',    self._on_image,       1)
        self.create_subscription(CameraInfo, '/camera/camera_info',  self._on_camera_info, 1)

        # ── Publishers ────────────────────────────────────────────────────────
        self._pub_detected  = self.create_publisher(Bool,        '/aruco/detected',       10)
        self._pub_pose      = self.create_publisher(PoseStamped, '/aruco/marker_pose',    10)
        self._pub_dist      = self.create_publisher(Float32,     '/aruco/distance',       10)
        self._pub_lateral   = self.create_publisher(Float32,     '/aruco/lateral_offset', 10)
        self._pub_debug     = self.create_publisher(Image,       '/aruco/debug_image',    1)

        self.get_logger().info(
            '[aruco_detector] node started — watching for ArUco ID=0 on /camera/image_raw')

    # ── Camera info ───────────────────────────────────────────────────────────

    def _on_camera_info(self, msg: CameraInfo):
        if self._got_camera_info:
            return
        self._camera_matrix = np.array(msg.k, dtype=np.float64).reshape(3, 3)
        self._dist_coeffs   = np.array(msg.d, dtype=np.float64).reshape(-1, 1)
        self._got_camera_info = True
        self.get_logger().info('[aruco_detector] camera_info received, intrinsics updated')

    # ── Image callback ────────────────────────────────────────────────────────

    def _on_image(self, msg: Image):
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self._aruco_dict, parameters=self._aruco_params)

        detected = Bool()
        detected.data = False

        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id != MARKER_ID:
                    continue

                # Estimate pose (rvec, tvec in camera frame)
                rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                    [corners[i]], MARKER_SIZE,
                    self._camera_matrix, self._dist_coeffs)

                tx, ty, tz = tvec[0][0]   # camera optical frame: Z = depth

                # Publish distance & lateral offset
                dist_msg = Float32()
                dist_msg.data = float(tz)
                self._pub_dist.publish(dist_msg)

                lat_msg = Float32()
                lat_msg.data = float(tx)
                self._pub_lateral.publish(lat_msg)

                # Publish PoseStamped
                ps = PoseStamped()
                ps.header.stamp    = msg.header.stamp
                ps.header.frame_id = 'camera_rgb_optical_frame'
                ps.pose.position.x = float(tx)
                ps.pose.position.y = float(ty)
                ps.pose.position.z = float(tz)
                # Convert rvec → quaternion
                rot, _ = cv2.Rodrigues(rvec[0])
                q = _rot_to_quat(rot)
                ps.pose.orientation.x = q[0]
                ps.pose.orientation.y = q[1]
                ps.pose.orientation.z = q[2]
                ps.pose.orientation.w = q[3]
                self._pub_pose.publish(ps)

                detected.data = True

                # Debug image
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                # OpenCV 4.6 in the Jazzy/Noble image exposes frame-axis
                # drawing as cv2.drawFrameAxes, not cv2.aruco.drawAxis.
                cv2.drawFrameAxes(
                    frame, self._camera_matrix, self._dist_coeffs,
                    rvec[0], tvec[0], MARKER_SIZE * 0.5)
                cv2.putText(
                    frame,
                    f'ID:{marker_id}  Z={tz:.2f}m  X={tx:.3f}m',
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                break

        self._pub_detected.publish(detected)
        debug_msg = self._bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        debug_msg.header = msg.header
        self._pub_debug.publish(debug_msg)


# ── Helper: rotation matrix → quaternion ─────────────────────────────────────

def _rot_to_quat(R):
    """Convert 3×3 rotation matrix to (x, y, z, w) quaternion."""
    trace = R[0, 0] + R[1, 1] + R[2, 2]
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    return (x, y, z, w)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = ArucoDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
