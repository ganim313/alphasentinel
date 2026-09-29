"""
Thread-Safe DuckDB Write Coordinator.
All writes are now synchronous but protected by RLock in session.py.
"""

import logging
from typing import Optional, Any, Sequence
from contextlib import contextmanager
from src.db.session import get_write_connection

logger = logging.getLogger(__name__)

# Single-Writer DuckDB Concurrency & Queue Manager (Synchronous Thread-Safe Mode)
_daemon_process = None
_write_queue = None

def start_daemon():
    """Stub for backward compatibility. Thread safety now handled by RLock in session.py"""
    logger.info("DuckDB write coordinator active.")

def stop_daemon():
    """Stub for backward compatibility."""
    pass

def db_write(query: str, params: Optional[Sequence[Any]] = None, sync: bool = True) -> Any:
    """
    Executes a write query against DuckDB thread-safely.
    Note: 'sync' parameter is deprecated and ignored; all writes are synchronous and protected by RLock.
    """
    try:
        with get_write_connection() as conn:
            if params:
                cursor = conn.execute(query, params)
            else:
                cursor = conn.execute(query)
            
            if cursor and cursor.description is not None:
                try:
                    return cursor.fetchall()
                except Exception:
                    return None
            return None
    except Exception as e:
        logger.error(f"DuckDB Write Error: {e}\nQuery: {query}")
        raise

def db_write_many(query: str, param_list: list) -> None:
    """Executes a parameterized write query against DuckDB multiple times."""
    try:
        with get_write_connection() as conn:
            conn.executemany(query, param_list)
    except Exception as e:
        logger.error(f"DuckDB Write Many Error: {e}")
        raise

@contextmanager
def db_transaction():
    """
    Provides a transactional context block for grouping writes.
    """
    with get_write_connection() as conn:
        conn.execute("BEGIN TRANSACTION")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error(f"Transaction failed: {e}")
            raise
