#!/usr/bin/env python3
"""Create a disposable SDF contact-instrumentation clone.

The clone adds only contact sensors and the Gazebo Contact system. It does not
change collision geometry, pose, friction, inertia, mass, controller, or ROS
application topics.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path


CONTACT_LINKS = {
    "wheel_left_link": "wheel_left",
    "wheel_right_link": "wheel_right",
    "caster_front_link": "caster_front",
    "caster_rear_link": "caster_rear",
    "stability_front_left_link": "anti_tip_front_left",
    "stability_front_right_link": "anti_tip_front_right",
    "stability_rear_left_link": "anti_tip_rear_left",
    "stability_rear_right_link": "anti_tip_rear_right",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_clone(model_source: Path, world_source: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_tree = ET.parse(model_source)
    model_root = model_tree.getroot()
    model = model_root.find("model")
    if model is None:
        raise ValueError("model SDF has no model element")
    added = []
    for link_name, topic_suffix in CONTACT_LINKS.items():
        link = next((item for item in model.findall("link") if item.get("name") == link_name), None)
        if link is None:
            raise ValueError(f"missing diagnostic link {link_name}")
        sensor = ET.Element("sensor", {"name": f"phase4m_{topic_suffix}_contact", "type": "contact"})
        ET.SubElement(sensor, "always_on").text = "true"
        ET.SubElement(sensor, "update_rate").text = "100"
        ET.SubElement(sensor, "visualize").text = "false"
        ET.SubElement(sensor, "topic").text = f"/phase4m/contact/{topic_suffix}"
        contact = ET.SubElement(sensor, "contact")
        ET.SubElement(contact, "collision").text = "collision"
        link.append(sensor)
        added.append(f"{link_name}:/phase4m/contact/{topic_suffix}")
    ET.indent(model_tree, space="  ")
    model_output = output_dir / "amr_robot_harmonic_contact.sdf"
    model_tree.write(model_output, encoding="utf-8", xml_declaration=True)

    world_tree = ET.parse(world_source)
    world = world_tree.getroot().find("world")
    if world is None:
        raise ValueError("world SDF has no world element")
    contact_plugin = ET.Element(
        "plugin",
        {"filename": "gz-sim-contact-system", "name": "gz::sim::systems::Contact"},
    )
    # UserCommands is already present in the production world; append Contact
    # after all existing systems so runtime-spawned model sensors are seen by
    # the contact system while preserving the existing system order.
    world.append(contact_plugin)
    ET.indent(world_tree, space="  ")
    world_output = output_dir / "amr_world_contact.sdf"
    world_tree.write(world_output, encoding="utf-8", xml_declaration=True)

    manifest = {
        "source_model_sha256": _sha256(model_source),
        "source_world_sha256": _sha256(world_source),
        "clone_model": str(model_output),
        "clone_world": str(world_output),
        "contact_plugin": "gz::sim::systems::Contact",
        "contact_topics": added,
        "physics_or_controller_changes": [],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(make_clone(args.model, args.world, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
