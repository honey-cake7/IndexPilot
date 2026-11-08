import uuid
from dataclasses import dataclass

from pglast import ast, parse_sql, parser
from pglast.stream import RawStream
from pydantic import ValidationError

from indexpilot.candidates.deduplication import compare_existing
from indexpilot.candidates.models import CandidateDefinition
from indexpilot.candidates.sql import candidate_key, definition, load_operator_classes
from indexpilot.errors import DomainError
from indexpilot.evaluation.models import EvaluationQueryView
from indexpilot.schema.context import refresh_analyses
from indexpilot.sql.models import SQLAnalysis
from indexpilot.sql.resolution import resolve_query
from indexpilot.sql.validation import nodes, sql_size
from indexpilot.workloads.models import QueryInput


@dataclass(frozen=True)
class SourceQuery:
    plan_id: uuid.UUID
    frequency: float
    analysis: SQLAnalysis


def replanning_query(source: SourceQuery) -> QueryInput:
    """Restore internally qualified operators, then use the normal admission/resolution policy."""
    try:
        sql_size(source.analysis.canonical_sql)
        root = parse_sql(source.analysis.canonical_sql)
        if len(root) != 1 or not isinstance(root[0].stmt, ast.SelectStmt):
            raise ValueError("Expected one SELECT")
        for node in nodes(root[0].stmt):
            if (
                isinstance(node, ast.A_Expr)
                and len(node.name) == 2
                and node.name[0].sval == "pg_catalog"
            ):
                node.name = (node.name[-1],)
        return QueryInput(sql=RawStream()(root[0].stmt), frequency=source.frequency)
    except (ValueError, parser.ParseError, ValidationError, RecursionError):
        raise DomainError(
            "invalid_source_plan", "Saved resolved query is invalid; analyze it again.", 409
        ) from None


def prepare_context(connection, sources, stored_candidates, *, allowed_schemas, check):
    tables = refresh_analyses(
        connection,
        [source.analysis for source in sources],
        allowed_schemas=allowed_schemas,
        check=check,
    )
    classes = load_operator_classes(connection)
    compiled = {}
    for identifier, stored in stored_candidates.items():
        check()
        try:
            candidate = CandidateDefinition.model_validate(stored)
            table = tables.get(candidate.table_oid)
            if (
                table is None
                or not 1 <= len(candidate.keys) <= 3
                or len({key.column for key in candidate.keys}) != len(candidate.keys)
            ):
                raise ValueError("Invalid candidate relation/keys")
            columns = {column.name: column for column in table.columns}
            keys = [
                candidate_key(
                    columns[key.column],
                    classes[columns[key.column].type_oid],
                    descending=key.descending,
                    nulls_first=key.nulls_first,
                )
                for key in candidate.keys
            ]
            rebuilt = definition(table, keys)
            if rebuilt != candidate:
                raise ValueError("Candidate definition changed")
        except (ValueError, KeyError, TypeError, ValidationError):
            raise DomainError(
                "invalid_candidate",
                "Saved definition differs from its verified structure; regenerate the batch.",
                409,
            ) from None
        if compare_existing(rebuilt, table.indexes)[0]:
            raise DomainError(
                "candidate_already_exists",
                "An equivalent usable index now exists; regenerate the batch.",
                409,
            )
        compiled[identifier] = rebuilt
    queries = []
    for source in sources:
        check()
        analysis = resolve_query(
            connection, replanning_query(source), allowed_schemas=allowed_schemas
        )
        old = {
            (row.relation_oid, row.schema_name, row.table, row.alias)
            for row in source.analysis.relations
        }
        fresh = {
            (row.relation_oid, row.schema_name, row.table, row.alias) for row in analysis.relations
        }
        if old != fresh:
            raise DomainError(
                "invalid_source_plan", "Saved query bindings differ; analyze the query again.", 409
            )
        queries.append(
            EvaluationQueryView(
                source_plan_id=source.plan_id, frequency=source.frequency, analysis=analysis
            )
        )
    return queries, compiled
