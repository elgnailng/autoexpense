import threading
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from staging.database import get_connection, initialize_db

# DuckDB is single-writer — serialize pipeline operations
pipeline_lock = threading.Lock()

# Rate limiter — shared across all routes
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


def get_db():
    """Yield a DuckDB connection, closing after use."""
    initialize_db()
    con = get_connection()
    try:
        yield con
    finally:
        con.close()


def require_pipeline_idle():
    """Dependency that rejects requests when a pipeline step is running."""
    if pipeline_lock.locked():
        raise HTTPException(409, "Configuration changes are disabled while a pipeline step is running.")
