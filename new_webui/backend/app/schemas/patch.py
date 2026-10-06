"""
The one rule every partial update shares: omitted is not null.

A key left out of a PATCH keeps the stored value. A key sent as ``null`` clears
it — but only where the column can actually be empty. For a column that cannot,
``null`` used to mean something else depending on where it landed: a zone's
``enabled: null`` was written as 0 and silently switched a keep-out zone off,
and ``name: null`` hit the NOT NULL constraint and came back as a misleading
"name already taken". Refusing it up front, as a 422 naming the field, is the
only reading that cannot surprise anybody.
"""

from __future__ import annotations

from collections.abc import Collection

from pydantic import BaseModel


def reject_nulls(model: BaseModel, nullable: Collection[str]) -> None:
    """
    Raise if a field outside `nullable` was sent explicitly as null.

    Call from a ``model_validator(mode="after")``: ``model_fields_set`` is what
    tells "sent as null" apart from "left out".
    """
    for name in sorted(model.model_fields_set - set(nullable)):
        if getattr(model, name) is None:
            raise ValueError(f"{name} cannot be null; leave it out to keep the stored value")
