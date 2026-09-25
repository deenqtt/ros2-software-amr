#!/usr/bin/env python3
from phase4m_contacts import parse_contact_json_line


def test_contact_json_extracts_pair_force_and_depth():
    line = (
        '{"header":{"stamp":{"sec":"12","nsec":500000000}},'
        '"contact":[{"collision1":{"name":"wheel::collision"},'
        '"collision2":{"name":"ground::collision"},'
        '"depth":[0.001],"wrench":[{"body1Wrench":{"force":{"z":42.5}}}]}]}'
    )
    parsed = parse_contact_json_line(line)
    assert parsed["stamp_s"] == 12.5
    assert parsed["active"] is True
    assert parsed["contact_count"] == 1
    assert parsed["pairs"] == [("wheel::collision", "ground::collision")]
    assert parsed["normal_force_z_max_n"] == 42.5
    assert parsed["depth_max_m"] == 0.001


def test_empty_contact_json_is_inactive():
    parsed = parse_contact_json_line('{"header":{"stamp":{"sec":"1","nsec":0}},"contact":[]}')
    assert parsed["active"] is False
    assert parsed["contact_count"] == 0
    assert parsed["normal_force_z_max_n"] == 0.0


if __name__ == "__main__":
    test_contact_json_extracts_pair_force_and_depth()
    test_empty_contact_json_is_inactive()
    print("phase4m contact tests passed")
