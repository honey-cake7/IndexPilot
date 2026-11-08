from indexpilot.errors import DomainError
from indexpilot.sql.safety import require_safe_table


def refresh_analyses(connection, analyses, *, allowed_schemas, check=None):
    """Refresh context and reject stale bindings, including sources sharing an OID."""
    tables = {}
    for analysis in analyses:
        for observed in analysis.tables:
            if check:
                check()
            if observed.oid not in tables:
                try:
                    current = require_safe_table(
                        connection,
                        observed.schema_name,
                        observed.name,
                        allowed_schemas=allowed_schemas,
                    )
                except DomainError as error:
                    if error.code == "relation_not_found":
                        raise DomainError(
                            "stale_plan", "Source relation is absent; analyze the query again.", 409
                        ) from None
                    raise
                if current.oid != observed.oid:
                    raise DomainError(
                        "stale_plan", "Table identity changed; analyze the query again.", 409
                    )
                tables[current.oid] = current
            current = tables[observed.oid]
            if (current.schema_name, current.name) != (observed.schema_name, observed.name):
                raise DomainError(
                    "stale_plan", "Source relation was renamed; analyze the query again.", 409
                )
            old_columns = {column.name: column for column in observed.columns}
            current_columns = {column.name: column for column in current.columns}
            for usage in analysis.columns:
                if usage.column.relation_oid != observed.oid:
                    continue
                old, new = (
                    old_columns.get(usage.column.name),
                    current_columns.get(usage.column.name),
                )
                if (
                    old is None
                    or new is None
                    or (old.number, old.type_oid, old.collation_oid)
                    != (new.number, new.type_oid, new.collation_oid)
                ):
                    raise DomainError(
                        "stale_plan", "Referenced columns changed; analyze the query again.", 409
                    )
    return tables
