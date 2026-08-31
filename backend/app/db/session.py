"""SQLite connection helper. One file database — no server to run, per the
brief's "how you store the analysis is your design decision" latitude."""
import sqlite3
import sys
import time
from pathlib import Path
from typing import Annotated, Iterator

from fastapi import Depends

from app.config import settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

#: Printed once, not once per request, if WAL has to be given up on.
_wal_warning_shown = False

#: A few short retries absorb a momentary external lock on the db file (a
#: sync client, an antivirus scan, a just-killed process still releasing its
#: handle) rather than surfacing it as a request failure.
_OPEN_RETRIES = 3
_OPEN_RETRY_DELAY_SECONDS = 0.3


def _open_and_configure() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row

    # WAL needs a shared-memory (-shm) sidecar file with working fcntl-style
    # locking. That's not guaranteed on every filesystem a bind mount can sit
    # on: verified live, `docker compose up` on this exact repo (Windows,
    # backend/data bind-mounted, both inside a OneDrive-synced folder) hit
    # "unable to open database file" on this PRAGMA a few minutes into a
    # session that had been serving requests successfully — every endpoint
    # started 500ing until the container was restarted. WAL is a concurrency
    # optimisation, not a correctness requirement for this app's access
    # pattern (one writer during ingest/batch, readers meanwhile already
    # covered by busy_timeout below) — so failing to enable it should degrade
    # to SQLite's default rollback journal, not take the whole API down.
    global _wal_warning_shown
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError as e:
        if not _wal_warning_shown:
            print(
                f"warning: could not enable WAL journal mode ({e}) — "
                "continuing with the default journal. Read/write still work; "
                "concurrent access is just less parallel.",
                file=sys.stderr,
            )
            _wal_warning_shown = True

    conn.execute("PRAGMA foreign_keys=ON;")
    # The batch writes while the API reads; without this, a concurrent reader
    # raises "database is locked" instead of waiting the moment out.
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def get_connection() -> sqlite3.Connection:
    """Open a configured connection, retrying through a momentary lock on the
    file itself rather than failing the request outright.

    The WAL fallback above handles WAL specifically being unavailable; this
    handles the broader case where the *main* db file was transiently
    unopenable (same underlying class of problem — a bind mount over a
    synced folder — but not limited to the WAL sidecar). Observed once live:
    every endpoint 500'd until the container was restarted by hand, which is
    exactly the outcome a 300ms retry should absorb instead.
    """
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(_OPEN_RETRIES):
        try:
            return _open_and_configure()
        except sqlite3.OperationalError as e:
            last_error = e
            if attempt < _OPEN_RETRIES - 1:
                time.sleep(_OPEN_RETRY_DELAY_SECONDS)
    raise last_error


def init_db() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    with conn:
        conn.executescript(SCHEMA_PATH.read_text())
    conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """Request-scoped connection. SQLite connections are not thread-safe and
    FastAPI may serve requests on different threads, so one per request."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


#: Use as `conn: DbConn` in a route signature.
DbConn = Annotated[sqlite3.Connection, Depends(get_db)]
