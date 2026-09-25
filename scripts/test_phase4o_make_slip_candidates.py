import json
from pathlib import Path

import pytest

from phase4o_make_slip_candidates import generate_series


SOURCE = Path("ros2_ws/src/amr_simulation/models/amr_robot_harmonic/model.sdf")


def test_generate_series_creates_auditable_candidate_for_each_value(tmp_path):
    manifests = generate_series(SOURCE, tmp_path, [0.0, 0.01, 0.02, 0.035])

    assert [item["candidate_slip1"] for item in manifests] == ["0.0", "0.01", "0.02", "0.035"]
    assert all(item["source_sha256"] for item in manifests)
    assert all(item["changed_fields"] == 2 for item in manifests)
    assert all({change["link"] for change in item["changes"]} == {"wheel_left_link", "wheel_right_link"} for item in manifests)
    assert all(Path(item["output"]).is_file() for item in manifests)

    manifest_files = sorted(tmp_path.glob("slip-*/candidate-manifest.json"))
    assert len(manifest_files) == 4
    assert json.loads(manifest_files[0].read_text())["changed_fields"] == 2


def test_generate_series_rejects_out_of_range_value_without_partial_output(tmp_path):
    with pytest.raises(ValueError, match="slip1 must be between 0.0 and 1.0"):
        generate_series(SOURCE, tmp_path, [0.01, 1.01])
    assert list(tmp_path.iterdir()) == []
