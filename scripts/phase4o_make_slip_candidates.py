#!/usr/bin/env python3
"""Generate the controlled Phase 4O drive-wheel slip1 response series."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase4n_make_slip_candidate import generate_candidate


def _label(value: float) -> str:
    return f"slip-{round(value * 1000):03d}"


def _filename(value: float) -> str:
    return f"amr_robot_harmonic_slip1_{value:.3f}.sdf"


def generate_series(source: Path, output_root: Path, values: list[float]) -> list[dict]:
    normalized = [float(value) for value in values]
    if any(value < 0.0 or value > 1.0 for value in normalized):
        raise ValueError("slip1 must be between 0.0 and 1.0")
    if len(set(normalized)) != len(normalized):
        raise ValueError("slip1 values must be unique")

    manifests = []
    for value in normalized:
        candidate_dir = output_root / _label(value)
        manifest = generate_candidate(
            source,
            candidate_dir / _filename(value),
            value,
        )
        (candidate_dir / "candidate-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        manifests.append(manifest)
    return manifests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--slip1", type=float, nargs="+", required=True)
    args = parser.parse_args()
    print(json.dumps(generate_series(args.source, args.output_root, args.slip1), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
