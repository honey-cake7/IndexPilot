"""Exclusively held, session-local hypothetical state with verified cleanup."""

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from indexpilot.errors import DomainError
from indexpilot.evaluation.models import HypoPGCapability, IndexEstimate

SPECS = {
    "hypopg_reset": [],
    "hypopg_create_index": [25],
    "hypopg": [],
    "hypopg_unhide_all_indexes": [],
    "hypopg_hidden_indexes": [],
    "hypopg_relation_size": [26],
}
MANDATORY = set(SPECS) - {"hypopg_relation_size"}


class HypoPGUnavailable(DomainError):
    def __init__(self, capability):
        self.capability = capability
        super().__init__("hypopg_unavailable", capability.warning or "HypoPG is unavailable.", 503)


def inspect_hypopg(connection):
    row = connection.execute(
        "SELECT e.extversion,n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='hypopg'"
    ).fetchone()
    if row is None:
        return HypoPGCapability(
            available=False,
            warning="HypoPG is not installed; no hypothetical estimates were produced.",
        )
    version, schema = row
    functions = connection.execute("""
      SELECT p.proname,p.proargtypes::oid[],has_function_privilege(p.oid,'EXECUTE'),
       has_schema_privilege(n.oid,'USAGE') FROM pg_proc p
      JOIN pg_namespace n ON n.oid=p.pronamespace
      JOIN pg_depend d ON d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e'
      JOIN pg_extension e ON d.refclassid='pg_extension'::regclass AND e.oid=d.refobjid
      WHERE e.extname='hypopg' AND p.pronamespace=e.extnamespace
    """).fetchall()
    usable = {
        name
        for name, args, execute, usage in functions
        if name in SPECS and args == SPECS[name] and execute and usage
    }
    valid = MANDATORY <= usable and version.startswith("1.4.")
    return HypoPGCapability(
        available=valid,
        schema_name=schema,
        version=version,
        storage_available="hypopg_relation_size" in usable,
        warning=None
        if valid
        else "HypoPG 1.4 core functions are missing, unsupported or inaccessible.",
    )


class HypotheticalSession:
    """Caller owns the physical connection; this scope exclusively owns its hypothetical state."""

    def __init__(self, connection):
        if connection.autocommit:
            raise DomainError(
                "invalid_session", "Hypothetical evaluation requires a held transaction."
            )
        self.connection = connection
        self.capability = HypoPGCapability(available=False)
        self.cleanup_confirmed = False

    def call(self, name, args=(), columns="*"):
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in args)
        return self.connection.execute(
            sql.SQL("SELECT {} FROM {}({})").format(
                sql.SQL(columns), sql.Identifier(self.capability.schema_name, name), placeholders
            ),
            args,
        )

    def reset(self):
        if self.connection.closed:
            raise DomainError("hypopg_cleanup_failed", "The evaluation connection was lost.", 503)
        if self.connection.info.transaction_status == TransactionStatus.INERROR:
            self.connection.rollback()
            self.connection.execute("SET TRANSACTION READ ONLY")
        # Cleanup uses its own bounded timeout even when the evaluation deadline expired.
        self.connection.execute("SELECT set_config('statement_timeout','2000',true)")
        self.call("hypopg_reset")
        self.call("hypopg_unhide_all_indexes")
        if (
            self.call("hypopg", columns="count(*)").fetchone()[0]
            or self.call("hypopg_hidden_indexes", columns="count(*)").fetchone()[0]
        ):
            raise DomainError(
                "hypopg_cleanup_failed", "Hypothetical state could not be cleared.", 503
            )
        self.cleanup_confirmed = True

    def cleanup(self):
        try:
            self.reset()
        except Exception:
            self.connection.close()
            self.cleanup_confirmed = False
            raise DomainError(
                "hypopg_cleanup_failed",
                "Cleanup failed; the physical connection was discarded.",
                503,
            ) from None

    def __enter__(self):
        self.capability = inspect_hypopg(self.connection)
        if not self.capability.available:
            raise HypoPGUnavailable(self.capability)
        try:
            self.reset()
            self.connection.execute(
                "SELECT set_config('hypopg.enabled','on',true), "
                "set_config('hypopg.use_real_oids','off',true)"
            )
        except Exception:
            self.connection.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()
        return False

    def create(self, candidate_id, definition):
        self.cleanup_confirmed = False
        rows = self.call(
            "hypopg_create_index", (definition.ddl,), "indexrelid,indexname"
        ).fetchall()
        if len(rows) != 1 or rows[0][0] <= 0:
            raise DomainError(
                "invalid_hypothetical_index", "HypoPG did not create exactly one index.", 503
            )
        oid, name = rows[0]
        relation = self.call("hypopg", columns="indexrelid,indrelid").fetchall()
        if not any(row[0] == oid and row[1] == definition.table_oid for row in relation):
            raise DomainError(
                "invalid_hypothetical_index", "Hypothetical relation identity differs.", 503
            )
        size = None
        if self.capability.storage_available:
            try:
                with self.connection.transaction():
                    value = self.call("hypopg_relation_size", (oid,)).fetchone()[0]
                if isinstance(value, int) and 0 < value <= 2**63 - 1:
                    size = value
            except psycopg.Error as error:
                if error.sqlstate not in ("42501", "42883", "0A000"):
                    raise
        return IndexEstimate(
            candidate_id=candidate_id,
            hypothetical_oid=oid,
            hypothetical_name=name,
            estimated_size_bytes=size,
        )
