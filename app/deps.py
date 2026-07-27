from __future__ import annotations

from app.db import DatabaseClient


def get_db_dependency() -> DatabaseClient | None:
    """Get the current database client from the global app instance.

    This dependency is injected by FastAPI into all route handlers.
    Returns None if database hasn't been initialized (shouldn't happen in normal flow).
    """
    from app.main import get_db
    return get_db()
