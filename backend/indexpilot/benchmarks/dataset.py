from pglast import ast, parse_sql
from pglast.stream import RawStream
from psycopg import sql

from indexpilot.benchmarks.guard import TABLES, namespace, require_namespace, verify
from indexpilot.candidates.sql import candidate_key, definition, load_operator_classes
from indexpilot.demo import generate
from indexpilot.errors import DomainError
from indexpilot.evaluation.context import SourceQuery, replanning_query
from indexpilot.evaluation.models import EvaluationQueryView
from indexpilot.sql.resolution import resolve_query
from indexpilot.sql.validation import nodes
from indexpilot.workloads.models import QueryInput


def clean(connection, job_id, expected):
    verify(connection, expected=expected)
    name = namespace(job_id)
    require_namespace(name)
    found = connection.execute(
        "SELECT pg_get_userbyid(nspowner),obj_description(oid,'pg_namespace') "
        "FROM pg_namespace WHERE nspname=%s",
        (name,),
    ).fetchone()
    if found is None:
        return
    if found != ("indexpilot_bench_owner", "indexpilot:benchmark:" + str(job_id)):
        raise DomainError("unsafe_benchmark_namespace", "Namespace ownership/marker differs.", 409)
    with connection.transaction():
        names = sql.SQL(",").join(sql.Identifier(name, table) for table in (*TABLES, "ip_guard"))
        connection.execute(sql.SQL("DROP TABLE IF EXISTS {} ").format(names))
        connection.execute(
            sql.SQL("DROP SEQUENCE IF EXISTS {}.write_ids").format(sql.Identifier(name))
        )
        # No CASCADE: unknown objects/dependencies must block cleanup rather than be destroyed.
        connection.execute(sql.SQL("DROP SCHEMA {}").format(sql.Identifier(name)))


def prepare(connection, job_id, expected, request, *, delete_rows=0):
    verify(connection, expected=expected)
    name = namespace(job_id)
    with connection.transaction():
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        connection.execute(
            sql.SQL("COMMENT ON SCHEMA {} IS {}").format(
                sql.Identifier(name), sql.Literal("indexpilot:benchmark:" + str(job_id))
            )
        )
        connection.execute(
            sql.SQL("CREATE TABLE {}.ip_guard(token uuid NOT NULL)").format(sql.Identifier(name))
        )
        connection.execute(
            sql.SQL("INSERT INTO {}.ip_guard VALUES (%s)").format(sql.Identifier(name)), (job_id,)
        )
    generate(connection, target="bench", orders=request.orders, seed=request.seed, schema_name=name)
    if delete_rows:
        connection.execute(
            sql.SQL(
                "INSERT INTO {}.orders SELECT -n,1,TIMESTAMPTZ '2026-01-01 UTC','paid',100 "
                "FROM generate_series(1,%s) n"
            ).format(sql.Identifier(name)),
            (delete_rows,),
        )
        connection.execute(sql.SQL("ANALYZE {}.orders").format(sql.Identifier(name)))
    connection.execute(sql.SQL("CREATE SEQUENCE {}.write_ids").format(sql.Identifier(name)))
    return fingerprint(connection, name)


def fingerprint(connection, name):
    hashes, counts = {}, {}
    for table in TABLES:
        order = (
            sql.SQL("order_id,line_number")
            if table == "order_items"
            else sql.SQL("singleton")
            if table == "indexpilot_dataset"
            else sql.SQL("id")
        )
        counts[table], hashes[table] = connection.execute(
            sql.SQL(
                "SELECT count(*),md5(string_agg(row_to_json(t)::text,',' ORDER BY {})) FROM {} t"
            ).format(order, sql.Identifier(name, table))
        ).fetchone()
    return dict(row_counts=counts, row_hashes=hashes)


def rebind_sql(analysis, name):
    source = SourceQuery(None, 1, analysis)
    tree = parse_sql(replanning_query(source).sql)[0].stmt
    for node in nodes(tree):
        if isinstance(node, ast.RangeVar):
            if node.schemaname != "public" or node.relname not in TABLES[:-1]:
                raise DomainError(
                    "unsupported_benchmark_query",
                    "Benchmarks support only the five public sample tables.",
                    422,
                )
            node.schemaname = name
    value = RawStream()(tree)
    # pgbench meta commands are a different language: never admit multiline/backslash input.
    if any(char in value for char in ("\n", "\r", "\\")):
        raise DomainError(
            "unsupported_benchmark_query",
            "Benchmark literals cannot contain line breaks or backslashes.",
            422,
        )
    return value


def context(connection, job_id, query_inputs, candidate_inputs):
    name = namespace(job_id)
    with connection.transaction():
        queries = [
            EvaluationQueryView(
                source_plan_id=row.source_plan_id,
                frequency=row.frequency,
                analysis=resolve_query(
                    connection,
                    QueryInput(sql=rebind_sql(row.analysis, name), frequency=row.frequency),
                    allowed_schemas=(name,),
                ),
            )
            for row in query_inputs
        ]
        tables = {table.name: table for query in queries for table in query.analysis.tables}
        for source in query_inputs:
            for original in source.analysis.tables:
                fresh = tables[original.name]

                def columns(table):
                    return {
                        column.name: (
                            column.type_oid,
                            column.collation_schema,
                            column.collation_name,
                            column.not_null,
                        )
                        for column in table.columns
                    }

                def constraints(table):
                    return {
                        (
                            item.kind,
                            tuple(item.columns),
                            item.validated,
                            item.referenced_table,
                            "sample"
                            if item.referenced_schema in ("public", name)
                            else item.referenced_schema,
                            tuple(item.referenced_columns or []),
                            item.definition if item.kind == "c" else None,
                        )
                        for item in table.constraints
                    }

                if columns(original) != columns(fresh) or constraints(original) != constraints(
                    fresh
                ):
                    raise DomainError(
                        "benchmark_schema_mismatch",
                        "Source columns/collations/constraints differ from the sample template.",
                        409,
                    )
        classes = load_operator_classes(connection)
        candidates = {}
        for identifier, original in candidate_inputs.items():
            if original.schema_name != "public" or original.table_name not in tables:
                raise DomainError(
                    "unsupported_benchmark_candidate",
                    "Candidate table is outside the benchmark workload.",
                )
            table = tables[original.table_name]
            columns = {column.name: column for column in table.columns}
            keys = []
            for key in original.keys:
                column = columns[key.column]
                if column.type_oid != key.type_oid:
                    raise DomainError(
                        "benchmark_schema_mismatch", "Benchmark column types differ.", 409
                    )
                keys.append(
                    candidate_key(
                        column,
                        classes[column.type_oid],
                        descending=key.descending,
                        nulls_first=key.nulls_first,
                    )
                )
            candidates[identifier] = definition(table, keys)
    return queries, candidates


def build_indexes(connection, definitions, selected):
    for identifier in sorted(selected, key=str):
        connection.execute(definitions[identifier].ddl, prepare=False)
    return index_bytes(connection, definitions, selected)


def index_bytes(connection, definitions, selected):
    return sum(
        connection.execute(
            "SELECT pg_relation_size(%s::regclass)",
            (
                sql.Identifier(
                    definitions[identifier].schema_name, definitions[identifier].index_name
                ).as_string(),
            ),
        ).fetchone()[0]
        for identifier in selected
    )
