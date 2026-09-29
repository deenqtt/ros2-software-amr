"""
ASGI entry point.

    uvicorn app.asgi:app --reload

Kept apart from main.py so importing the factory has no side effects.
"""

from __future__ import annotations

from app.main import create_app

app = create_app()
