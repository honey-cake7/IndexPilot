from psycopg import Connection
from psycopg.rows import dict_row

from indexpilot.errors import DomainError
from indexpilot.schema.models import (
    ColumnInfo,
    ColumnStatistics,
    ConstraintInfo,
    IndexInfo,
    IndexKey,
    SchemaSnapshot,
    TableInfo,
    TableSummary,
)
from indexpilot.sql.types import BUILTIN_TYPE_OIDS

TABLES = """
SELECT c.oid::bigint, n.nspname AS schema_name, c.relname AS name, c.relkind::text AS kind,
 c.relpersistence::text AS persistence, am.amname AS access_method,
 CASE WHEN c.reltuples < 0 THEN NULL ELSE c.reltuples END AS estimated_rows,
 c.relpages AS estimated_pages, pg_table_size(c.oid) AS table_bytes,
 pg_indexes_size(c.oid) AS indexes_bytes, pg_total_relation_size(c.oid) AS total_bytes,
 c.relrowsecurity AS row_security, c.relhasrules AS has_rules,
 EXISTS(SELECT 1 FROM pg_inherits h WHERE h.inhrelid=c.oid OR h.inhparent=c.oid) AS inheritance,
 has_table_privilege(c.oid,'SELECT') AS can_select,
 has_schema_privilege(n.oid,'USAGE') AS can_use_schema,s.last_analyze,s.last_autoanalyze
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
LEFT JOIN pg_am am ON am.oid=c.relam LEFT JOIN pg_stat_all_tables s ON s.relid=c.oid
"""


def _rows(connection, query, params=()):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def require_schema(schema: str, allowed_schemas):
    if schema not in allowed_schemas:
        raise DomainError(
            "schema_not_allowed", "Schema is outside the configured analysis allowlist."
        )


def inspect_schema(
    connection: Connection, *, allowed_schemas=("public",), schema=None, limit=50, offset=0
):
    names = [schema] if schema else list(allowed_schemas)
    for name in names:
        require_schema(name, allowed_schemas)
    where = " WHERE n.nspname=ANY(%s) AND c.relkind IN ('r','p','v','m','f')"
    rows = _rows(
        connection,
        TABLES + where + " ORDER BY n.nspname,c.relname LIMIT %s OFFSET %s",
        (names, limit, offset),
    )
    total = connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace" + where,
        (names,),
    ).fetchone()[0]
    database, dbid, version, observed = connection.execute(
        "SELECT current_database(), oid::bigint, "
        "current_setting('server_version'),clock_timestamp() "
        "FROM pg_database WHERE datname=current_database()"
    ).fetchone()
    return SchemaSnapshot(
        database=database,
        database_oid=dbid,
        server_version=version,
        observed_at=observed,
        schema_names=names,
        tables=[TableSummary(**row) for row in rows],
        total_tables=total,
        offset=offset,
        warnings=[
            "Row counts and column selectivity are estimates from sampled statistics.",
            "Low index usage alone does not justify dropping an index; workloads vary.",
        ],
    )


def inspect_table(
    connection: Connection,
    schema: str,
    table: str,
    *,
    allowed_schemas=("public",),
    include_values=False,
):
    require_schema(schema, allowed_schemas)
    rows = _rows(
        connection,
        TABLES + " WHERE n.nspname=%s AND c.relname=%s AND c.relkind IN ('r','p','v','m','f')",
        (schema, table),
    )
    if not rows:
        raise DomainError(
            "relation_not_found", "Relation was not found in the configured schema.", 404
        )
    summary = TableSummary(**rows[0])
    oid = summary.oid
    column_rows = _rows(
        connection,
        """
      SELECT a.attnum AS number,a.attname AS name,a.atttypid::bigint AS type_oid,
       tn.nspname AS type_schema,t.typname AS type_name,
       format_type(a.atttypid,a.atttypmod) AS formatted_type,
       t.typtype::text AS type_kind,a.attnotnull AS not_null,a.attgenerated::text AS generated,
       a.attidentity::text AS identity,pg_get_expr(d.adbin,d.adrelid) AS default_expression,
       a.attcollation::bigint AS collation_oid,
       cn.nspname AS collation_schema,co.collname AS collation_name
      FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
      JOIN pg_namespace tn ON tn.oid=t.typnamespace LEFT JOIN pg_attrdef d
       ON d.adrelid=a.attrelid AND d.adnum=a.attnum
      LEFT JOIN pg_collation co ON co.oid=a.attcollation
      LEFT JOIN pg_namespace cn ON cn.oid=co.collnamespace
      WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum
    """,
        (oid,),
    )
    safe_value_columns = [
        row["name"]
        for row in column_rows
        if row["type_schema"] == "pg_catalog"
        and BUILTIN_TYPE_OIDS.get(row["type_name"]) == row["type_oid"]
    ]
    include_values = include_values and summary.can_select and summary.can_use_schema
    statistics = {
        row["attname"]: row
        for row in _rows(
            connection,
            """
      SELECT attname,null_frac,avg_width,n_distinct,correlation,most_common_freqs,
       CASE WHEN %s AND attname=ANY(%s) THEN most_common_vals::text END AS common_values,
       CASE WHEN %s AND attname=ANY(%s) THEN histogram_bounds::text END AS histogram
      FROM pg_stats WHERE schemaname=%s AND tablename=%s AND NOT inherited
    """,
            (include_values, safe_value_columns, include_values, safe_value_columns, schema, table),
        )
    }
    columns = []
    for row in column_rows:
        stats = statistics.get(row["name"])
        model = None
        if stats:
            distinct = (
                stats["n_distinct"]
                if stats["n_distinct"] >= 0
                else (
                    -stats["n_distinct"] * summary.estimated_rows
                    if summary.estimated_rows is not None
                    else None
                )
            )
            model = ColumnStatistics(
                null_fraction=stats["null_frac"],
                average_width=stats["avg_width"],
                n_distinct=stats["n_distinct"],
                estimated_distinct_values=distinct,
                uniform_equality_selectivity=(1 - stats["null_frac"]) / distinct
                if distinct and distinct > 0
                else None,
                correlation=stats["correlation"],
                most_common_frequencies=stats["most_common_freqs"],
                most_common_values=stats["common_values"],
                histogram_bounds=stats["histogram"],
            )
        columns.append(ColumnInfo(**row, statistics=model))
    indexes = []
    index_rows = _rows(
        connection,
        """
      SELECT i.indexrelid::bigint AS oid,ci.relname AS name,ni.nspname AS schema_name,
       am.amname AS method,pg_get_indexdef(i.indexrelid) AS definition,
       i.indisprimary AS primary,i.indisunique AS unique,i.indisvalid AS valid,
       i.indisready AS ready,i.indislive AS live,i.indnullsnotdistinct AS nulls_not_distinct,
       pg_get_expr(i.indpred,i.indrelid) AS predicate,
       pg_get_expr(i.indexprs,i.indrelid) AS expressions,
       pg_relation_size(i.indexrelid) AS size_bytes,s.idx_scan AS scans,
       s.idx_tup_read AS tuples_read,s.idx_tup_fetch AS tuples_fetched,i.indnkeyatts,
       i.indkey::smallint[] AS attribute_numbers
      FROM pg_index i JOIN pg_class ci ON ci.oid=i.indexrelid
      JOIN pg_namespace ni ON ni.oid=ci.relnamespace JOIN pg_am am ON am.oid=ci.relam
      LEFT JOIN pg_stat_all_indexes s ON s.indexrelid=i.indexrelid
      WHERE i.indrelid=%s ORDER BY ci.relname
    """,
        (oid,),
    )
    by_number = {column.number: column.name for column in columns}
    for row in index_rows:
        key_rows = _rows(
            connection,
            """
          SELECT k.pos AS position,i.indkey[k.pos-1] AS attribute_number,a.attname AS column,
           pg_get_indexdef(i.indexrelid,k.pos,true) AS expression,
           op.oid::bigint AS operator_class_oid,onsp.nspname AS operator_class_schema,
           op.opcname AS operator_class_name,op.opcdefault AS operator_class_default,
           i.indcollation[k.pos-1]::bigint AS collation_oid,cn.nspname AS collation_schema,
           co.collname AS collation_name,(i.indoption[k.pos-1]&1)=1 AS descending,
           (i.indoption[k.pos-1]&2)=2 AS nulls_first
          FROM pg_index i CROSS JOIN LATERAL generate_series(1,i.indnkeyatts) k(pos)
          LEFT JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=i.indkey[k.pos-1]
          JOIN pg_opclass op ON op.oid=i.indclass[k.pos-1]
          JOIN pg_namespace onsp ON onsp.oid=op.opcnamespace
          LEFT JOIN pg_collation co ON co.oid=i.indcollation[k.pos-1]
          LEFT JOIN pg_namespace cn ON cn.oid=co.collnamespace
          WHERE i.indexrelid=%s ORDER BY k.pos
        """,
            (row["oid"],),
        )
        included = [
            by_number[number] for number in row.pop("attribute_numbers")[row.pop("indnkeyatts") :]
        ]
        indexes.append(
            IndexInfo(**row, keys=[IndexKey(**key) for key in key_rows], included_columns=included)
        )
    constraints = []
    for row in _rows(
        connection,
        """
      SELECT con.conname AS name,con.contype::text AS kind,con.conkey,
       pg_get_constraintdef(con.oid) AS definition,con.convalidated AS validated,
       rn.nspname AS referenced_schema,rc.relname AS referenced_table,
       ARRAY(SELECT a.attname::text FROM unnest(con.confkey) WITH ORDINALITY k(num,pos)
        JOIN pg_attribute a ON a.attrelid=con.confrelid AND a.attnum=k.num
        ORDER BY k.pos) AS referenced_columns
      FROM pg_constraint con LEFT JOIN pg_class rc ON rc.oid=con.confrelid
      LEFT JOIN pg_namespace rn ON rn.oid=rc.relnamespace WHERE con.conrelid=%s ORDER BY con.conname
    """,
        (oid,),
    ):
        numbers = row.pop("conkey") or []
        constraints.append(
            ConstraintInfo(
                **row, columns=[by_number[number] for number in numbers if number in by_number]
            )
        )
    warnings = []
    if not statistics:
        warnings.append(
            "Column statistics are unavailable; run ANALYZE as the owner if appropriate."
        )
    if summary.kind != "r" or summary.row_security or summary.inheritance:
        warnings.append("Relation is inspectable but unsupported for initial safe plan analysis.")
    warnings.append("Index usage is cumulative and is insufficient evidence for dropping an index.")
    return TableInfo(
        **summary.model_dump(),
        columns=columns,
        indexes=indexes,
        constraints=constraints,
        warnings=warnings,
    )
