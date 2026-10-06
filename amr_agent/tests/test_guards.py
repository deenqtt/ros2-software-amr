"""Tests for guards.py: no ROS, no robot."""

import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guards import resolve_map_path, sanitize_twist  # noqa: E402

ML, MA = 0.5, 1.5


def tw(lx=0.0, ly=0.0, lz=0.0, ax=0.0, ay=0.0, az=0.0, ml=ML, ma=MA):
    return sanitize_twist(lx, ly, lz, ax, ay, az, ml, ma)


def test_zero_passes_as_zero():
    r = tw()
    assert tuple(r[:6]) == (0.0,) * 6
    assert not r.rejected and not r.clamped


def test_normal_values_unchanged():
    r = tw(lx=0.2, az=-0.7)
    assert (r.linear_x, r.angular_z) == (0.2, -0.7)
    assert not r.rejected and not r.clamped


def test_exactly_max_not_clamped():
    r = tw(lx=ML, az=-MA)
    assert (r.linear_x, r.angular_z) == (ML, -MA)
    assert not r.clamped


def test_above_max_clamped():
    r = tw(lx=5.0, az=99.0)
    assert (r.linear_x, r.angular_z) == (ML, MA)
    assert r.clamped and not r.rejected


def test_below_negative_max_clamped():
    r = tw(lx=-5.0, az=-99.0)
    assert (r.linear_x, r.angular_z) == (-ML, -MA)
    assert r.clamped


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("index", range(6))
def test_non_finite_anywhere_means_stop(bad, index):
    args = [0.3, 0.0, 0.0, 0.0, 0.0, 0.4]
    args[index] = bad
    r = sanitize_twist(*args, ML, MA)
    assert tuple(r[:6]) == (0.0,) * 6
    assert r.rejected


def test_other_axes_zeroed():
    r = tw(lx=0.1, ly=0.4, lz=0.4, ax=1.0, ay=1.0, az=0.2)
    assert (r.linear_y, r.linear_z, r.angular_x, r.angular_y) == (0.0, 0.0, 0.0, 0.0)
    assert (r.linear_x, r.angular_z) == (0.1, 0.2)


def test_negative_zero_normalised():
    r = tw(lx=-0.0)
    assert math.copysign(1.0, r.linear_x) == 1.0


@pytest.mark.parametrize("ml,ma", [(0, 1.5), (0.5, 0), (-1, 1.5), (0.5, -1),
                                   (math.nan, 1.5), (0.5, math.inf)])
def test_invalid_limits_raise(ml, ma):
    with pytest.raises(ValueError):
        sanitize_twist(0, 0, 0, 0, 0, 0, ml, ma)


# ── resolve_map_path ────────────────────────────────────────────────────────

@pytest.fixture
def dirs(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    evil = tmp_path / "cache-evil"
    evil.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    return tmp_path, cache, evil, outside


def test_valid_cache_yaml_accepted(dirs):
    _, cache, _, _ = dirs
    f = cache / "map.yaml"
    f.write_text("x")
    assert resolve_map_path(str(f), [str(cache)]) == os.path.realpath(f)


def test_dotdot_escape_rejected(dirs):
    _, cache, _, outside = dirs
    (outside / "secret.yaml").write_text("x")
    assert resolve_map_path(f"{cache}/../outside/secret.yaml", [str(cache)]) is None


def test_absolute_outside_rejected(dirs):
    _, cache, _, outside = dirs
    f = outside / "m.yaml"
    f.write_text("x")
    assert resolve_map_path(str(f), [str(cache)]) is None


def test_symlink_escape_rejected(dirs):
    _, cache, _, outside = dirs
    target = outside / "m.yaml"
    target.write_text("x")
    (cache / "link.yaml").symlink_to(target)
    assert resolve_map_path(str(cache / "link.yaml"), [str(cache)]) is None


def test_symlinked_dir_escape_rejected(dirs):
    _, cache, _, outside = dirs
    (outside / "m.yaml").write_text("x")
    (cache / "d").symlink_to(outside)
    assert resolve_map_path(str(cache / "d" / "m.yaml"), [str(cache)]) is None


def test_non_yaml_rejected(dirs):
    _, cache, _, _ = dirs
    f = cache / "passwd"
    f.write_text("x")
    assert resolve_map_path(str(f), [str(cache)]) is None


def test_missing_file_rejected(dirs):
    _, cache, _, _ = dirs
    assert resolve_map_path(str(cache / "nope.yaml"), [str(cache)]) is None


def test_prefix_trick_dir_rejected(dirs):
    _, cache, evil, _ = dirs
    f = evil / "m.yaml"
    f.write_text("x")
    assert resolve_map_path(str(f), [str(cache)]) is None


def test_empty_candidate_and_roots(dirs):
    _, cache, _, _ = dirs
    f = cache / "m.yaml"
    f.write_text("x")
    assert resolve_map_path("", [str(cache)]) is None
    assert resolve_map_path(str(f), []) is None
    assert resolve_map_path(str(f), [""]) is None


def test_second_root_accepted(dirs):
    _, cache, evil, _ = dirs
    f = evil / "m.yaml"
    f.write_text("x")
    assert resolve_map_path(str(f), [str(cache), str(evil)]) == os.path.realpath(f)
