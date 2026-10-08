#!/usr/bin/env python3
"""
zone_mask_server — turns zone polygons into the costmap filter masks Nav2 reads.

Replaces keepout_mask_server. A zone is not only a keepout: Nav2 enforces zones
through *costmap filters*, and this publishes one filter's worth for each kind
of zone so a map can carry every kind at once.

  keepout  -> KeepoutFilter, mask value 100. Never enter. Each keepout also gets
              a non-lethal halo round it (95 at the edge falling to 60, 0.6 m
              wide by default): filters are not inflated, and without the halo
              the robot's body clips into the keepout and MPPI deadlocks there.
  avoid    -> a second KeepoutFilter on its own mask. The UI's avoid_cost 1..99
              becomes 8..80: go around if you reasonably can, never lethal.
  speed    -> SpeedFilter, absolute: mask value = m/s * 100 (1..100).
  binary   -> BinaryFilter, toggles a topic on entry.

The arithmetic — polygon fill, halo, value mapping — lives in zone_raster.py,
which has no ROS imports and is unit-tested; this node only moves messages.

Each filter needs its own CostmapFilterInfo *and* its own mask, on separate
topics. They are told apart by the `type` field — which the previous version got
wrong: it published type 1 (a speed filter) while being used as a keepout
filter. KeepoutFilter happens not to check the type, so keepout kept working and
nothing reported the mistake; it would have started mattering the moment a
second filter appeared, which is now.

The topic names are a contract with the robot's Nav2 parameters: each filter
plugin there names one of the info topics below. Rename nothing here without
changing those too.

Parameters:
    keepout_halo_width   m, default 0.6. 0 turns the halo off.
    keepout_halo_inner   mask value at the keepout's edge, default 95.
    keepout_halo_outer   mask value at the halo's outer rim, default 60.

Topics:
  Subscribe:
    /map                        nav_msgs/OccupancyGrid (transient_local)
    /amr/zones                  std_msgs/String — JSON array from the agent

  Publish (all transient_local + reliable, depth 1, so a filter that starts
  later still gets them):
    /zone_keepout_filter_info   nav2_msgs/CostmapFilterInfo  type 0, base 0, multiplier 1
    /zone_keepout_mask          nav_msgs/OccupancyGrid       keepouts 100 + halo 60..95
    /zone_avoid_filter_info     nav2_msgs/CostmapFilterInfo  type 0, base 0, multiplier 1
    /zone_avoid_mask            nav_msgs/OccupancyGrid       avoid zones 8..80
    /zone_speed_filter_info     nav2_msgs/CostmapFilterInfo  type 2, base 0, multiplier 0.01
    /zone_speed_mask            nav_msgs/OccupancyGrid       round(m/s * 100), 0 = no limit
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

from zone_raster import (
    HALO_INNER,
    HALO_OUTER,
    HALO_WIDTH_M,
    SPEED_BASE,
    SPEED_MULTIPLIER,
    Grid,
    rasterise,
    validate_halo,
)


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

# The speed filter's encoding (base 0, multiplier 0.01: a mask value is cm/s)
# is defined in zone_raster, next to the code that writes the values.


class ZoneMaskServer(Node):

    def __init__(self):
        super().__init__('zone_mask_server')

        self.declare_parameter('keepout_halo_width', HALO_WIDTH_M)
        self.declare_parameter('keepout_halo_inner', HALO_INNER)
        self.declare_parameter('keepout_halo_outer', HALO_OUTER)
        # Refused at startup: a halo of 100 would quietly grow every keepout,
        # and a negative width is a typo rather than a setting.
        self._halo = validate_halo(
            self.get_parameter('keepout_halo_width').value,
            self.get_parameter('keepout_halo_inner').value,
            self.get_parameter('keepout_halo_outer').value,
        )

        self._map_info: MapMetaData = None
        self._zones: list = []

        self.create_subscription(
            OccupancyGrid, '/map', self._on_map, TRANSIENT_LOCAL_QOS
        )
        # Latched, like the agent's publisher. The agent only republishes when
        # the zone set changes, so a server started later — every time Nav2 is
        # restarted — would otherwise never hear the zones and run with none.
        self.create_subscription(String, '/amr/zones', self._on_zones, TRANSIENT_LOCAL_QOS)

        # One info + one mask per filter. A single pair cannot serve four
        # filters: each reads the type from its own info topic to decide how to
        # interpret the values in the mask it points at.
        self._filters = {
            # KeepoutFilter checks that base and multiplier are at their
            # defaults and complains otherwise, so these two are not free.
            'keepout': self._make_filter(
                FILTER_KEEPOUT, '/zone_keepout_filter_info', '/zone_keepout_mask',
                0.0, 1.0,
            ),
            # A second KeepoutFilter instance, so avoid costs no longer share a
            # mask with the keepout halo and cannot outrank it.
            'avoid': self._make_filter(
                FILTER_KEEPOUT, '/zone_avoid_filter_info', '/zone_avoid_mask',
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
        self.get_logger().info(
            f'Zone Mask Server started (keepout halo {self._halo.width:.2f} m, '
            f'{self._halo.inner}..{self._halo.outer}). Waiting for /map...'
        )

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

    def _publish_masks(self):
        if self._map_info is None:
            return

        grid = Grid(
            width=self._map_info.width,
            height=self._map_info.height,
            resolution=self._map_info.resolution,
            origin_x=self._map_info.origin.position.x,
            origin_y=self._map_info.origin.position.y,
        )
        result = rasterise(self._zones, grid, self._halo)
        for reason in result.skipped:
            self.get_logger().warning(f'{reason}, skipped')
        buffers, counts = result.masks, result.counts

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
