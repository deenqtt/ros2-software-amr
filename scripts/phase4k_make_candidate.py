#!/usr/bin/env python3
"""Create disposable Phase 4K caster A/B SDF candidates.

The input production SDF is never modified.  Only the requested passive
caster collision radius is changed in the output copy; visuals and all other
model parameters remain unchanged.
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def make_candidate(source: Path, output: Path, mode: str) -> None:
    tree = ET.parse(source)
    root = tree.getroot()
    model = root.find("model")
    if model is None:
        raise ValueError("SDF has no model")
    if mode not in {
        "front-only",
        "rear-only",
        "mirror",
        "front-slip",
        "front-zero-friction",
        "front-low-friction",
    }:
        raise ValueError(f"unsupported candidate mode: {mode}")

    # A 0.015 m collision radius at the existing z=0.055 m centre is lifted
    # 0.040 m above the ground, so that caster is mechanically inactive.
    inactive = "0.015"
    if mode == "front-only":
        disabled = "caster_rear_link"
    elif mode == "rear-only":
        disabled = "caster_front_link"
    else:
        disabled = None

    if mode == "front-slip":
        link = model.find("./link[@name='caster_front_link']")
        if link is None:
            raise ValueError("missing caster_front_link")
        ode = link.find("./collision/surface/friction/ode")
        if ode is None:
            raise ValueError("missing front caster ODE friction")
        for field in ("slip1", "slip2"):
            element = ode.find(field)
            if element is None:
                raise ValueError(f"missing front caster {field}")
            element.text = "1.0"

    if mode == "front-zero-friction":
        link = model.find("./link[@name='caster_front_link']")
        if link is None:
            raise ValueError("missing caster_front_link")
        ode = link.find("./collision/surface/friction/ode")
        if ode is None:
            raise ValueError("missing front caster ODE friction")
        for field in ("mu", "mu2"):
            element = ode.find(field)
            if element is None:
                raise ValueError(f"missing front caster {field}")
            element.text = "0.0"

    if mode == "front-low-friction":
        link = model.find("./link[@name='caster_front_link']")
        if link is None:
            raise ValueError("missing caster_front_link")
        ode = link.find("./collision/surface/friction/ode")
        if ode is None:
            raise ValueError("missing front caster ODE friction")
        for field in ("mu", "mu2"):
            element = ode.find(field)
            if element is None:
                raise ValueError(f"missing front caster {field}")
            element.text = "0.001"

    for link in model.findall("link"):
        if link.get("name") != disabled:
            continue
        radius = link.find("./collision/geometry/sphere/radius")
        if radius is None:
            raise ValueError(f"missing caster collision radius in {disabled}")
        radius.text = inactive

    # Mirror is a disposable geometric control: swap front/rear caster
    # positions while preserving their contact size and all dynamics.
    if mode == "mirror":
        for link_name in ("caster_front_link", "caster_rear_link"):
            link = model.find(f"./link[@name='{link_name}']")
            if link is None:
                raise ValueError(f"missing {link_name}")
            pose = link.find("pose")
            if pose is None:
                raise ValueError(f"missing pose in {link_name}")
            values = pose.text.split()
            values[0] = str(-float(values[0]))
            pose.text = " ".join(values)

    tree.write(output, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=(
            "front-only",
            "rear-only",
            "mirror",
            "front-slip",
            "front-zero-friction",
            "front-low-friction",
        ),
        required=True,
    )
    args = parser.parse_args()
    make_candidate(args.source, args.output, args.mode)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
