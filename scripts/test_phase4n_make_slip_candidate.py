from pathlib import Path

import pytest

from phase4n_make_slip_candidate import generate_candidate


MODEL = """<sdf version=\"1.9\">\n  <model name=\"amr_robot\">\n    <link name=\"wheel_left_link\">\n      <collision name=\"collision\"><surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2><slip1>0.035</slip1><slip2>0.0</slip2></ode></friction></surface></collision>\n    </link>\n    <link name=\"wheel_right_link\">\n      <collision name=\"collision\"><surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2><slip1>0.035</slip1><slip2>0.0</slip2></ode></friction></surface></collision>\n    </link>\n    <link name=\"caster_front_link\">\n      <collision><surface><friction><ode><mu>0.01</mu><mu2>0.01</mu2><slip1>0.2</slip1><slip2>0.2</slip2></ode></friction></surface></collision>\n    </link>\n  </model>\n</sdf>\n"""


def test_candidate_changes_only_two_drive_wheel_slip1_values(tmp_path: Path):
    source = tmp_path / "source.sdf"
    output = tmp_path / "candidate.sdf"
    source.write_text(MODEL)

    manifest = generate_candidate(source, output, 0.0)

    assert output.read_text() == MODEL.replace("<slip1>0.035</slip1>", "<slip1>0.0</slip1>", 2)
    assert manifest["changes"] == [
        {"link": "wheel_left_link", "old": "0.035", "new": "0.0"},
        {"link": "wheel_right_link", "old": "0.035", "new": "0.0"},
    ]


def test_candidate_rejects_missing_drive_wheel(tmp_path: Path):
    source = tmp_path / "source.sdf"
    output = tmp_path / "candidate.sdf"
    source.write_text(MODEL.replace('name="wheel_right_link"', 'name="other_link"'))

    with pytest.raises(ValueError, match="exactly one block for each drive wheel"):
        generate_candidate(source, output, 0.0)


def test_candidate_rejects_multiple_slip1_fields_in_drive_wheel(tmp_path: Path):
    source = tmp_path / "source.sdf"
    output = tmp_path / "candidate.sdf"
    source.write_text(MODEL.replace("</link>\n    <link name=\"wheel_right_link\">", "<slip1>0.035</slip1></link>\n    <link name=\"wheel_right_link\">", 1))

    with pytest.raises(ValueError, match="expected exactly one slip1 field"):
        generate_candidate(source, output, 0.0)
