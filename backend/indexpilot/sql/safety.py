"""Conservative planning boundary for administrator-controlled demo databases."""

from psycopg import Connection, sql

from indexpilot.errors import DomainError
from indexpilot.schema.catalogs import inspect_table
from indexpilot.schema.models import TableInfo
from indexpilot.sql.types import BUILTIN_TYPE_OIDS


def require_safe_table(connection: Connection, schema: str, name: str, *, allowed_schemas):
    table = inspect_table(connection, schema, name, allowed_schemas=allowed_schemas)
    if (
        table.kind != "r"
        or table.persistence != "p"
        or table.access_method != "heap"
        or table.row_security
        or table.has_rules
        or table.inheritance
    ):
        raise DomainError(
            "unsupported_relation",
            "Planning requires an ordinary heap table without RLS, rules or inheritance.",
        )
    if not table.can_select or not table.can_use_schema:
        raise DomainError(
            "insufficient_privilege", "The analyzer needs table-level SELECT permission.", 403
        )
    # ONLY prevents implicit traversal of inheritance even if a child is attached concurrently.
    connection.execute(
        sql.SQL("LOCK TABLE ONLY {} IN ACCESS SHARE MODE").format(
            sql.Identifier(schema, name),
        )
    )
    current = connection.execute(
        "SELECT c.oid::bigint FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=%s AND c.relname=%s",
        (schema, name),
    ).fetchone()
    if current is None or current[0] != table.oid:
        raise DomainError(
            "schema_changed", "Relation identity changed during inspection; retry.", 409
        )
    validate_table_types(table)
    for index in table.indexes:
        if index.method != "btree" or any(
            key.operator_class_schema != "pg_catalog"
            or key.operator_class_oid >= 16384
            or key.collation_schema not in (None, "pg_catalog")
            for key in index.keys
        ):
            raise DomainError(
                "unsupported_index_dependency",
                "Planning requires B-Tree indexes with built-in operator classes and collations.",
            )
    unsafe = connection.execute(
        """
      SELECT EXISTS(
       SELECT 1 FROM pg_depend d
       LEFT JOIN pg_proc p ON d.refclassid='pg_proc'::regclass AND p.oid=d.refobjid
       LEFT JOIN pg_operator o ON d.refclassid='pg_operator'::regclass AND o.oid=d.refobjid
       LEFT JOIN pg_proc op ON op.oid=o.oprcode
       WHERE ((d.classid='pg_class'::regclass AND d.objid=ANY(%s::oid[]))
        OR (d.classid='pg_constraint'::regclass AND d.objid IN
            (SELECT oid FROM pg_constraint WHERE conrelid=%s)))
       AND ((p.oid IS NOT NULL AND (p.oid>=16384 OR p.pronamespace<>'pg_catalog'::regnamespace))
         OR (op.oid IS NOT NULL AND (op.oid>=16384 OR op.pronamespace<>'pg_catalog'::regnamespace)))
      )
    """,
        ([index.oid for index in table.indexes], table.oid),
    ).fetchone()[0]
    if unsafe:
        raise DomainError(
            "unsafe_planner_dependency",
            "A referenced constraint/index depends on unapproved functions or operators.",
        )
    return table


def validate_table_types(table: TableInfo):
    for column in table.columns:
        if (
            column.type_schema != "pg_catalog"
            or column.type_kind != "b"
            or BUILTIN_TYPE_OIDS.get(column.type_name) != column.type_oid
            or column.generated
            or column.collation_schema not in (None, "pg_catalog")
        ):
            raise DomainError(
                "unsupported_column_type",
                "Table contains unsupported types, generated columns or collations.",
            )


def require_safe_casts(connection: Connection):
    oids = list(BUILTIN_TYPE_OIDS.values())
    unsafe = connection.execute(
        """
      SELECT EXISTS(SELECT 1 FROM pg_cast c JOIN pg_proc p ON p.oid=c.castfunc
       WHERE c.castsource=ANY(%s::oid[]) AND c.casttarget=ANY(%s::oid[])
        AND (p.oid>=16384 OR p.pronamespace<>'pg_catalog'::regnamespace))
    """,
        (oids, oids),
    ).fetchone()[0]
    if unsafe:
        raise DomainError(
            "unsafe_cast", "Supported built-in types have an unapproved cast implementation."
        )
