#!/usr/bin/env python3
"""Create a disposable Phase 4N drive-wheel slip candidate.

The source text is copied byte-for-byte except for exactly one ``slip1`` value
inside each of the two named drive-wheel links. This keeps structural diffs
auditable and prevents accidental changes to physics or ROS configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


DRIVE_LINKS = ("wheel_left_link", "wheel_right_link")
LINK_RE = re.compile(
    r'(?P<block><link\s+name=["\'](?P<name>wheel_left_link|wheel_right_link)["\'][^>]*>.*?</link>)',
    re.DOTALL,
)
SLIP_RE = re.compile(r"<slip1>(?P<value>[^<]+)</slip1>")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_candidate(source: Path, output: Path, slip1: float) -> dict:
    source_text = source.read_text(encoding="utf-8")
    matches = list(LINK_RE.finditer(source_text))
    found = {match.group("name") for match in matches}
    if found != set(DRIVE_LINKS) or len(matches) != len(DRIVE_LINKS):
        raise ValueError("source must contain exactly one block for each drive wheel")

    changes = []
    replacements = []
    replacement_text = str(slip1)
    for match in matches:
        link_name = match.group("name")
        block = match.group("block")
        slip_matches = list(SLIP_RE.finditer(block))
        if len(slip_matches) != 1:
            raise ValueError(f"{link_name}: expected exactly one slip1 field")
        slip_match = slip_matches[0]
        old_value = slip_match.group("value")
        changes.append({"link": link_name, "old": old_value, "new": replacement_text})
        start = match.start("block") + slip_match.start("value")
        end = match.start("block") + slip_match.end("value")
        replacements.append((start, end, replacement_text))

    candidate_text = source_text
    for start, end, value in reversed(replacements):
        candidate_text = candidate_text[:start] + value + candidate_text[end:]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(candidate_text, encoding="utf-8")
    manifest = {
        "source": str(source),
        "output": str(output),
        "source_sha256": _sha256(source),
        "output_sha256": _sha256(output),
        "candidate_slip1": replacement_text,
        "changed_fields": 2,
        "changes": changes,
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--slip1", type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(generate_candidate(args.source, args.output, args.slip1), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
