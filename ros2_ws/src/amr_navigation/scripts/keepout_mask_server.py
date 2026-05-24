#!/usr/bin/env python3
"""
Keepout Mask Server untuk AMR Navigation.

Menerima keepout zone polygon dari web UI (JSON via std_msgs/String),
lalu mem-publish OccupancyGrid mask ke Nav2 KeepoutFilter plugin.

Topics:
  Subscribe:
    /map                 (nav_msgs/OccupancyGrid, transient_local) - map metadata
    /amr/keepout_zones   (std_msgs/String)  - JSON array of zone polygons

  Publish:
    /costmap_filter_info (nav2_msgs/CostmapFilterInfo, transient_local)
    /keepout_filter_mask (nav_msgs/OccupancyGrid, transient_local)
"""

import json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from nav_msgs.msg import OccupancyGrid, MapMetaData
from nav2_msgs.msg import CostmapFilterInfo


TRANSIENT_LOCAL_QOS = QoSProfile(
    depth=1,
    history=HistoryPolicy.KEEP_LAST,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
)


class KeepoutMaskServer(Node):

    def __init__(self):
        super().__init__('keepout_mask_server')

        self._map_info: MapMetaData = None
        self._zones = []  # list of {'polygon': [{'x': float, 'y': float}]}

        # Subscribe ke /map untuk dapat metadata (resolusi, origin, ukuran)
        self.create_subscription(
            OccupancyGrid, '/map',
            self._on_map,
            TRANSIENT_LOCAL_QOS,
        )

        # Subscribe ke zone updates dari web UI
        self.create_subscription(
            String, '/amr/keepout_zones',
            self._on_zones,
            10,
        )

        # Publish CostmapFilterInfo (latched) → KeepoutFilter plugin membaca ini
        self._pub_filter_info = self.create_publisher(
            CostmapFilterInfo,
            '/costmap_filter_info',
            TRANSIENT_LOCAL_QOS,
        )

        # Publish OccupancyGrid mask (latched) → isi keepout zones
        self._pub_mask = self.create_publisher(
            OccupancyGrid,
            '/keepout_filter_mask',
            TRANSIENT_LOCAL_QOS,
        )

        # Publish filter info segera saat node start
        self._publish_filter_info()
        self.get_logger().info('Keepout Mask Server started. Waiting for /map...')

    # ── Publishers ─────────────────────────────────────────────────────────────

    def _publish_filter_info(self):
        """Publish CostmapFilterInfo agar KeepoutFilter tahu mask topic-nya."""
        msg = CostmapFilterInfo()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.type = 1                                  # 1 = keepout filter
        msg.filter_mask_topic = '/keepout_filter_mask'
        msg.base = 0.0
        msg.multiplier = 1.0
        self._pub_filter_info.publish(msg)

    def _publish_mask(self):
        """Build OccupancyGrid dari zone polygons dan publish."""
        if self._map_info is None:
            return

        w = self._map_info.width
        h = self._map_info.height
        res = self._map_info.resolution
        ox = self._map_info.origin.position.x
        oy = self._map_info.origin.position.y

        # Semua cell = 0 (bebas)
        data = bytearray(w * h)

        for zone in self._zones:
            polygon = zone.get('polygon', [])
            if len(polygon) < 3:
                continue
            # Konversi map coords (meter) → grid cell indices
            cells = [
                (int((p['x'] - ox) / res), int((p['y'] - oy) / res))
                for p in polygon
            ]
            self._fill_polygon(data, cells, w, h)

        mask = OccupancyGrid()
        mask.header.stamp = self.get_clock().now().to_msg()
        mask.header.frame_id = 'map'
        mask.info = self._map_info
        mask.data = list(data)
        self._pub_mask.publish(mask)

        self.get_logger().info(
            f'Published keepout mask: {len(self._zones)} zone(s), '
            f'{sum(1 for v in data if v > 0)} occupied cells'
        )

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def _on_map(self, msg: OccupancyGrid):
        self._map_info = msg.info
        self.get_logger().info(
            f'Map received: {msg.info.width}x{msg.info.height} '
            f'@ {msg.info.resolution:.3f} m/cell, '
            f'origin=({msg.info.origin.position.x:.2f}, {msg.info.origin.position.y:.2f})'
        )
        self._publish_mask()

    def _on_zones(self, msg: String):
        try:
            self._zones = json.loads(msg.data)
        except (json.JSONDecodeError, ValueError) as e:
            self.get_logger().error(f'Failed to parse zones JSON: {e}')
            return
        self.get_logger().info(f'Keepout zones updated: {len(self._zones)} zone(s)')
        self._publish_mask()

    # ── Polygon fill ───────────────────────────────────────────────────────────

    def _fill_polygon(self, data: bytearray, vertices: list, width: int, height: int, value: int = 100):
        """
        Isi area polygon menggunakan scanline fill algorithm.
        vertices: list of (grid_x, grid_y)
        """
        if len(vertices) < 3:
            return

        n = len(vertices)
        min_y = max(0, min(v[1] for v in vertices))
        max_y = min(height - 1, max(v[1] for v in vertices))

        for y in range(min_y, max_y + 1):
            intersections = []
            for i in range(n):
                x1, y1 = vertices[i]
                x2, y2 = vertices[(i + 1) % n]
                if y1 == y2:
                    continue
                if min(y1, y2) <= y < max(y1, y2):
                    xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                    intersections.append(int(xi))
            intersections.sort()
            for i in range(0, len(intersections) - 1, 2):
                x_start = max(0, intersections[i])
                x_end = min(width - 1, intersections[i + 1])
                for x in range(x_start, x_end + 1):
                    idx = y * width + x
                    if 0 <= idx < len(data):
                        data[idx] = value


def main(args=None):
    rclpy.init(args=args)
    node = KeepoutMaskServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
