"""Connections for the explicitly provisioned local demonstration environment."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROLES = {
    "meta": ("indexpilot_meta", "indexpilot_meta", "meta_password"),
    "demo": ("indexpilot_demo", "indexpilot_demo_owner", "demo_password"),
    "analyzer": ("indexpilot_demo", "indexpilot_analyzer", "analyzer_password"),
    "bench": ("indexpilot_bench", "indexpilot_bench_owner", "bench_password"),
}


class LocalConnectionError(RuntimeError):
    """A sanitized failure that cannot render psycopg's credential-bearing frames."""


def connect_local(role: str, *, autocommit: bool = False) -> psycopg.Connection:
    """Keep credentials out of DSNs, CLI arguments, logs and returned data."""
    load_dotenv()
    database, user, secret_file = ROLES[role]
    secret_dir = Path(os.getenv("INDEXPILOT_SECRET_DIR", ".secrets"))
    password = (secret_dir / secret_file).read_text(encoding="utf-8").strip()
    try:
        return psycopg.connect(
            host=os.getenv("INDEXPILOT_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("INDEXPILOT_DB_PORT", "55432")),
            dbname=database,
            user=user,
            password=password,
            connect_timeout=5,
            application_name="indexpilot-local",
            options="-c statement_timeout=30000 -c lock_timeout=2000",
            autocommit=autocommit,
        )
    except psycopg.Error:
        raise LocalConnectionError(
            "Local PostgreSQL connection failed; verify service, credentials and port."
        ) from None
