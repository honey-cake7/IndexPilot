"""Inspect the real local database environment without exposing credentials."""

import json

import psycopg
from indexpilot.local import LocalConnectionError, connect_local


def inspect() -> dict:
    result = {}
    for role in ("meta", "demo", "analyzer", "bench"):
        with connect_local(role) as connection:
            database, user, version = connection.execute(
                "SELECT current_database(), current_user, current_setting('server_version')"
            ).fetchone()
            extensions = dict(
                connection.execute(
                    "SELECT extname, extversion FROM pg_extension "
                    "WHERE extname IN ('hypopg','pg_stat_statements')"
                ).fetchall()
            )
            result[role] = {"database": database, "role": user, "version": version, **extensions}
            if role == "analyzer":
                result[role]["statement_statistics_visible"] = connection.execute(
                    "SELECT count(*) FROM pg_stat_statements WHERE dbid = "
                    "(SELECT oid FROM pg_database WHERE datname=current_database())"
                ).fetchone()[0]
                result[role]["plan_node"] = connection.execute(
                    "EXPLAIN (FORMAT JSON) SELECT id FROM public.orders WHERE user_id=101"
                ).fetchone()[0][0]["Plan"]["Node Type"]
                result[role]["read_only_default"] = connection.execute(
                    "SHOW default_transaction_read_only"
                ).fetchone()[0]
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(), indent=2))
    except (psycopg.Error, LocalConnectionError, OSError) as error:
        raise SystemExit(
            f"Environment check failed ({type(error).__name__}); no secrets displayed."
        ) from None
