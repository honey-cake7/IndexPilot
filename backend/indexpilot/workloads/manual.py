import hashlib
import json
from dataclasses import dataclass

from pglast import ast, fingerprint

from indexpilot.sql.validation import nodes, normalized_sql, validate_sql
from indexpilot.workloads.models import QueryInput
from indexpilot.workloads.parameters import bind_parameters


@dataclass(frozen=True)
class PreparedQuery:
    original: QueryInput
    fingerprint: str
    normalized: str
    representative: str | None
    missing_parameters: list[int]


def prepare_query(query: QueryInput, *, allowed_schemas=("public",)) -> PreparedQuery:
    root = validate_sql(query.sql, allowed_schemas=allowed_schemas)
    representative, missing = bind_parameters(
        root, query.parameters, allowed_schemas=allowed_schemas
    )
    # pglast's structural fingerprint ignores schema names; scope them explicitly.
    relations = sorted(
        (node.schemaname or "public", node.relname)
        for node in nodes(root)
        if isinstance(node, ast.RangeVar)
    )
    scoped = hashlib.sha256(json.dumps([fingerprint(query.sql), relations]).encode()).hexdigest()[
        :32
    ]
    return PreparedQuery(
        original=query,
        fingerprint=scoped,
        normalized=normalized_sql(root),
        representative=representative,
        missing_parameters=missing,
    )
