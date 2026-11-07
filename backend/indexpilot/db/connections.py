from contextlib import contextmanager

from psycopg import Connection

from indexpilot.config import Settings
from indexpilot.local import connect_local


@contextmanager
def target_connection(settings: Settings):
    # A new physical connection per analysis avoids pooled hypothetical-session leakage.
    with connect_local("analyzer", settings=settings) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (str(settings.statement_timeout_ms),),
        )
        connection.execute(
            "SELECT set_config('lock_timeout', %s, true)", (str(settings.lock_timeout_ms),)
        )
        connection.execute("SET LOCAL search_path = pg_catalog, public")
        yield connection


def require_demo_identity(connection: Connection) -> None:
    name, marker = connection.execute(
        "SELECT current_database(), shobj_description(oid, 'pg_database') "
        "FROM pg_database WHERE datname=current_database()"
    ).fetchone()
    if (name, marker) != ("indexpilot_demo", "indexpilot:demo:v1"):
        raise ValueError("Only the configured IndexPilot demo database is supported initially.")
