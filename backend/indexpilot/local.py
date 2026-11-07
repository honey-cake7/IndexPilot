"""Connections for the explicitly provisioned local demonstration environment."""

import psycopg

from indexpilot.config import Settings

ROLES = {
    "meta": ("indexpilot_meta", "indexpilot_meta", "meta_password"),
    "demo": ("indexpilot_demo", "indexpilot_demo_owner", "demo_password"),
    "analyzer": ("indexpilot_demo", "indexpilot_analyzer", "analyzer_password"),
    "bench": ("indexpilot_bench", "indexpilot_bench_owner", "bench_password"),
}


class LocalConnectionError(RuntimeError):
    """A sanitized failure that cannot render psycopg's credential-bearing frames."""

    def __init__(self, code="connection_failed"):
        self.code = code
        super().__init__(
            "Local PostgreSQL connection failed; verify service, credentials and port."
        )


def connect_local(
    role: str, *, autocommit: bool = False, settings: Settings | None = None
) -> psycopg.Connection:
    """Keep credentials out of DSNs, CLI arguments, logs and returned data."""
    settings = settings or Settings()
    database, user, secret_file = ROLES[role]
    try:
        password = (settings.secret_dir / secret_file).read_text(encoding="utf-8").strip()
    except OSError:
        raise LocalConnectionError("credential_file_unavailable") from None
    try:
        return psycopg.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=database,
            user=user,
            password=password,
            connect_timeout=settings.connect_timeout,
            application_name="indexpilot-local",
            options="-c statement_timeout=30000 -c lock_timeout=2000",
            autocommit=autocommit,
        )
    except psycopg.Error as error:
        code = "authentication_failed" if error.sqlstate == "28P01" else "connection_failed"
        raise LocalConnectionError(code) from None
