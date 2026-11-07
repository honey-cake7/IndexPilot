from dataclasses import dataclass

from pglast import fingerprint

from indexpilot.sql.validation import normalized_sql, validate_sql
from indexpilot.workloads.models import QueryInput
from indexpilot.workloads.parameters import bind_parameters


@dataclass(frozen=True)
class PreparedQuery:
    original: QueryInput
    fingerprint: str
    normalized: str
    representative: str | None
    missing_parameters: list[int]


def prepare_query(query: QueryInput) -> PreparedQuery:
    root = validate_sql(query.sql)
    representative, missing = bind_parameters(root, query.parameters)
    return PreparedQuery(
        original=query,
        fingerprint=fingerprint(query.sql),
        normalized=normalized_sql(root),
        representative=representative,
        missing_parameters=missing,
    )
