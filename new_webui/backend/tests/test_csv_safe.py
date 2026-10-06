from __future__ import annotations

import pytest

from app.api.users import _csv_safe


@pytest.mark.parametrize(
    "value", [" =1+1", "\t=cmd", "\r=x", "@SUM(A1)", "=1+1", "+1", "-1+1", "  \t@x", "-5"]
)
def test_formula_cells_are_neutralised(value):
    assert _csv_safe(value) == "'" + value


@pytest.mark.parametrize("value", ["hello", "", "a=b", " plain", "/api/x", 5, -5, None])
def test_ordinary_cells_are_untouched(value):
    assert _csv_safe(value) == value
