import hashlib
import json

from psycopg import sql

from indexpilot.candidates.models import CandidateDefinition, CandidateKey, OperatorClass
from indexpilot.schema.models import ColumnInfo, TableInfo


def load_operator_classes(connection) -> dict[int, OperatorClass]:
    rows = connection.execute("""
      SELECT o.opcintype::bigint,o.oid::bigint,n.nspname,o.opcname FROM pg_opclass o
      JOIN pg_am a ON a.oid=o.opcmethod JOIN pg_namespace n ON n.oid=o.opcnamespace
      WHERE a.amname='btree' AND o.opcdefault AND n.nspname='pg_catalog' AND o.oid<16384
    """).fetchall()
    classes = {
        type_oid: OperatorClass(oid=oid, schema_name=schema, name=name)
        for type_oid, oid, schema, name in rows
    }
    # PostgreSQL chooses text_ops for varchar through a built-in binary implicit cast.
    binary = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM pg_cast WHERE castsource=1043 "
        "AND casttarget=25 AND castmethod='b' AND castcontext='i')"
    ).fetchone()[0]
    if binary and 25 in classes:
        classes[1043] = classes[25]
    return classes


def candidate_key(
    column: ColumnInfo, operator_class: OperatorClass, *, descending=False, nulls_first=False
):
    return CandidateKey(
        column=column.name,
        attribute_number=column.number,
        type_oid=column.type_oid,
        operator_class=operator_class,
        collation_oid=column.collation_oid,
        collation_schema=column.collation_schema,
        collation_name=column.collation_name,
        descending=descending,
        nulls_first=nulls_first,
    )


def definition(table: TableInfo, keys: list[CandidateKey]) -> CandidateDefinition:
    payload = {
        "schema": table.schema_name,
        "table": table.name,
        "oid": table.oid,
        "method": "btree",
        "keys": [key.model_dump() for key in keys],
        "unique": False,
        "predicate": None,
        "expressions": None,
        "include": [],
    }
    signature = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    slug = "".join(
        char.lower() if char.isascii() and char.isalnum() else "_" for char in table.name
    )
    name = f"ip_{slug[:20]}_{signature[:16]}"
    parts = []
    for key in keys:
        part = sql.Identifier(key.column)
        if key.collation_oid:
            part += sql.SQL(" COLLATE {} ").format(
                sql.Identifier(key.collation_schema, key.collation_name)
            )
        else:
            part += sql.SQL(" ")
        part += sql.Identifier(key.operator_class.schema_name, key.operator_class.name)
        part += sql.SQL(" DESC" if key.descending else " ASC")
        part += sql.SQL(" NULLS FIRST" if key.nulls_first else " NULLS LAST")
        parts.append(part)
    ddl = (
        sql.SQL("CREATE INDEX {} ON {} USING btree ({})")
        .format(
            sql.Identifier(name),
            sql.Identifier(table.schema_name, table.name),
            sql.SQL(", ").join(parts),
        )
        .as_string()
    )
    return CandidateDefinition(
        signature=signature,
        schema_name=table.schema_name,
        table_name=table.name,
        table_oid=table.oid,
        index_name=name,
        keys=keys,
        ddl=ddl,
    )
