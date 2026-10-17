"""DuckDB database connection management with thread-safe singleton connection pooling."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Dict
import threading
import duckdb

from backend.config.settings import get_settings

_connections: Dict[str, duckdb.DuckDBPyConnection] = {}
_lock = threading.Lock()


def get_db_path(custom_path: Optional[Path] = None) -> Path:
    """Resolve database path, defaulting to artifacts/copilot.duckdb."""
    if custom_path is not None:
        return custom_path.resolve()
    settings = get_settings()
    return (settings.artifacts_path / "copilot.duckdb").resolve()


def get_db_connection(
    db_path: Optional[Path] = None,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Create or retrieve a DuckDB cursor from a thread-safe connection pool."""
    path = get_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path_key = str(path)

    with _lock:
        if path_key not in _connections:
            _connections[path_key] = duckdb.connect(database=path_key, read_only=False)
        return _connections[path_key].cursor()


def close_all_connections() -> None:
    """Safely close all open DuckDB connections."""
    with _lock:
        for con in _connections.values():
            try:
                con.close()
            except Exception:
                pass
        _connections.clear()


@contextmanager
def db_session(
    db_path: Optional[Path] = None,
    read_only: bool = False,
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Context manager for managing DuckDB connections."""
    con = get_db_connection(db_path=db_path, read_only=read_only)
    try:
        yield con
    finally:
        try:
            con.close()
        except Exception:
            pass


def get_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """FastAPI request dependency that guarantees DuckDB connection cleanup."""
    with db_session() as con:
        yield con
