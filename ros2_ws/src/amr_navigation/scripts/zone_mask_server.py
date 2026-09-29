#!/usr/bin/env python3
"""
zone_mask_server — turns zone polygons into the costmap filter masks Nav2 reads.

Replaces keepout_mask_server. A zone is not only a keepout: Nav2 enforces zones
through *costmap filters*, of which there are exactly three, and this publishes
all three so a map can carry every kind at once.

  keepout  -> KeepoutFilter, mask value 100. Never enter.
  avoid    -> KeepoutFilter, mask value 1..99. Go around if you reasonably can.
              Same filter as keepout; only the value in the mask differs.
  speed    -> SpeedFilter, a maximum velocity in m/s.
  binary   -> BinaryFilter, toggles a topic on entry.

Each filter needs its own CostmapFilterInfo *and* its own mask, on separate
topics. They are told apart by the `type` field — which the previous version got
wrong: it published type 1 (a speed filter) while being used as a keepout
filter. KeepoutFilter happens not to check the type, so keepout kept working and
nothing reported the mistake; it would have started mattering the moment a
second filter appeared, which is now.

Topics:
  Subscribe:
    /map                        nav_msgs/OccupancyGrid (transient_local)
    /amr/zones                  std_msgs/String — JSON array from the agent

  Publish (all transient_local, so a filter that starts later still gets them):
    /zone_keepout_filter_info   nav2_msgs/CostmapFilterInfo  type 0
    /zone_keepout_mask          nav_msgs/OccupancyGrid
    /zone_speed_filter_info     nav2_msgs/CostmapFilterInfo  type 2
    /zone_speed_mask            nav_msgs/OccupancyGrid
    /zone_binary_filter_info    nav2_msgs/CostmapFilterInfo  type 3
    /zone_binary_mask           nav_msgs/OccupancyGrid
"""

import json

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from nav_msgs.msg import OccupancyGrid, MapMetaData
from nav2_msgs.msg import CostmapFilterInfo


TRANSIENT_LOCAL_QOS = QoSProfile(
    depth=1,
    history=HistoryPolicy.KEEP_LAST,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
)

# nav2_costmap_2d CostmapFilterInfo.type. Not a local invention — these are the
# numbers the filter plugins compare against.
FILTER_KEEPOUT = 0
FILTER_SPEED_PERCENT = 1
FILTER_SPEED_ABSOLUTE = 2
FILTER_BINARY = 3

# speed_limit = base + multiplier * mask_value, so a mask value of 1..100 with
# this multiplier spans 0.1 .. 10.0 m/s in 0.1 steps. Absolute m/s rather than a
# percentage because "0.3 m/s past the blind corner" is a number an operator can
# check with a tape measure; "30% of maximum" depends on a setting elsewhere.
SPEED_BASE = 0.0
SPEED_MULTIPLIER = 0.1

KEEPOUT_VALUE = 100
BINARY_VALUE = 100


class ZoneMaskServer(Node):

    def __init__(self):
        super().__init__('zone_mask_server')

        self._map_info: MapMetaData = None
        self._zones: list = []

        self.create_subscription(
            OccupancyGrid, '/map', self._on_map, TRANSIENT_LOCAL_QOS
        )
        self.create_subscription(String, '/amr/zones', self._on_zones, 10)

        # One info + one mask per filter. A single pair cannot serve three
        # filters: each reads the type from its own info topic to decide how to
        # interpret the values in the mask it points at.
        self._filters = {
            # KeepoutFilter checks that base and multiplier are at their
            # defaults and complains otherwise, so these two are not free.
            'keepout': self._make_filter(
                FILTER_KEEPOUT, '/zone_keepout_filter_info', '/zone_keepout_mask',
                0.0, 1.0,
            ),
            'speed': self._make_filter(
                FILTER_SPEED_ABSOLUTE, '/zone_speed_filter_info', '/zone_speed_mask',
                SPEED_BASE, SPEED_MULTIPLIER,
            ),
            'binary': self._make_filter(
                FILTER_BINARY, '/zone_binary_filter_info', '/zone_binary_mask',
                0.0, 1.0,
            ),
        }

        self._publish_filter_info()
        self.get_logger().info('Zone Mask Server started. Waiting for /map...')

    def _make_filter(self, kind: int, info_topic: str, mask_topic: str,
                     base: float, multiplier: float) -> dict:
        return {
            'type': kind,
            'base': base,
            'multiplier': multiplier,
            'mask_topic': mask_topic,
            'info_pub': self.create_publisher(
                CostmapFilterInfo, info_topic, TRANSIENT_LOCAL_QOS
            ),
            'mask_pub': self.create_publisher(
                OccupancyGrid, mask_topic, TRANSIENT_LOCAL_QOS
            ),
        }

    # ── Publishers ─────────────────────────────────────────────────────────────

    def _publish_filter_info(self):
        """Tell each filter plugin which mask is its own, and how to read it."""
        for name, spec in self._filters.items():
            msg = CostmapFilterInfo()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'map'
            msg.type = spec['type']
            msg.filter_mask_topic = spec['mask_topic']
            msg.base = spec['base']
            msg.multiplier = spec['multiplier']
            spec['info_pub'].publish(msg)
            self.get_logger().debug(f'filter info published for {name} (type {spec["type"]})')

    def _speed_value(self, limit: float) -> int:
        """
        A speed limit in m/s as a mask value.

        Clamped to 1 at the bottom: 0 in a speed mask means *no restriction*,
        so rounding a very low limit down to zero would turn the slowest zone on
        the map into the fastest.
        """
        value = int(round((limit - SPEED_BASE) / SPEED_MULTIPLIER))
        return max(1, min(100, value))

    def _publish_masks(self):
        if self._map_info is None:
            return

        w = self._map_info.width
        h = self._map_info.height
        res = self._map_info.resolution
        ox = self._map_info.origin.position.x
        oy = self._map_info.origin.position.y

        buffers = {name: bytearray(w * h) for name in self._filters}
        counts = {name: 0 for name in self._filters}

        for zone in self._zones:
            if not zone.get('enabled', True):
                continue
            polygon = zone.get('polygon') or []
            if len(polygon) < 3:
                continue

            kind = str(zone.get('kind', 'keepout'))
            if kind == 'keepout':
                target, value = 'keepout', KEEPOUT_VALUE
            elif kind == 'avoid':
                target, value = 'keepout', int(zone.get('avoid_cost') or 50)
            elif kind == 'speed':
                target, value = 'speed', self._speed_value(float(zone.get('speed_limit') or 0.1))
            elif kind == 'binary':
                target, value = 'binary', BINARY_VALUE
            else:
                self.get_logger().warning(f'unknown zone kind "{kind}", skipped')
                continue

            cells = [
                (int((point[0] - ox) / res), int((point[1] - oy) / res))
                for point in polygon
            ]
            self._fill_polygon(buffers[target], cells, w, h, value)
            counts[target] += 1

        for name, spec in self._filters.items():
            mask = OccupancyGrid()
            mask.header.stamp = self.get_clock().now().to_msg()
            mask.header.frame_id = 'map'
            mask.info = self._map_info
            mask.data = list(buffers[name])
            spec['mask_pub'].publish(mask)

        self.get_logger().info(
            'Published zone masks: '
            + ', '.join(f'{name} {counts[name]}' for name in self._filters)
        )

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def _on_map(self, msg: OccupancyGrid):
        self._map_info = msg.info
        self.get_logger().info(
            f'Map received: {msg.info.width}x{msg.info.height} '
            f'@ {msg.info.resolution:.3f} m/cell, '
            f'origin=({msg.info.origin.position.x:.2f}, {msg.info.origin.position.y:.2f})'
        )
        # Re-sent with the masks: a filter that only has the info is a filter
        # pointing at a topic with nothing on it.
        self._publish_filter_info()
        self._publish_masks()

    def _on_zones(self, msg: String):
        try:
            parsed = json.loads(msg.data)
        except (json.JSONDecodeError, ValueError) as exc:
            self.get_logger().error(f'Failed to parse zones JSON: {exc}')
            return
        if not isinstance(parsed, list):
            self.get_logger().error('Zones payload was not a list')
            return

        self._zones = parsed
        self.get_logger().info(f'Zones updated: {len(self._zones)} zone(s)')
        self._publish_masks()

    # ── Polygon fill ───────────────────────────────────────────────────────────

    def _fill_polygon(self, data: bytearray, vertices: list, width: int,
                      height: int, value: int = 100):
        """
        Scanline fill.

        Writes the larger value when zones overlap, so a keepout drawn across a
        speed zone stays a keepout — the stricter rule wins rather than whichever
        polygon happened to be drawn last.
        """
        if len(vertices) < 3:
            return

        ys = [y for _, y in vertices]
        y_start = max(0, min(ys))
        y_end = min(height - 1, max(ys))

        count = len(vertices)
        for y in range(y_start, y_end + 1):
            crossings = []
            for i in range(count):
                x1, y1 = vertices[i]
                x2, y2 = vertices[(i + 1) % count]
                if y1 == y2:
                    continue
                # Half-open test, so a vertex lying exactly on the scanline is
                # counted once rather than twice — otherwise the fill leaks.
                if (y1 <= y < y2) or (y2 <= y < y1):
                    crossings.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))

            crossings.sort()
            for i in range(0, len(crossings) - 1, 2):
                x_start = max(0, int(round(crossings[i])))
                x_end = min(width - 1, int(round(crossings[i + 1])))
                row = y * width
                for x in range(x_start, x_end + 1):
                    if value > data[row + x]:
                        data[row + x] = value


def main():
    rclpy.init()
    node = ZoneMaskServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
