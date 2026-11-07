import uuid

import psycopg
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from indexpilot.config import Settings
from indexpilot.db.connections import require_demo_identity, target_connection
from indexpilot.errors import DomainError
from indexpilot.metadata.models import PlanAnalysis, QueryScenario
from indexpilot.metadata.targets import ensure_demo_target
from indexpilot.plans.explanations import explain_plan
from indexpilot.plans.models import PlanRecord, PlanSummary
from indexpilot.plans.parser import parse_explain
from indexpilot.sql.models import SQLAnalysis
from indexpilot.sql.resolution import resolve_query
from indexpilot.workloads.models import QueryInput

PLANNER_SETTINGS = (
    "seq_page_cost",
    "random_page_cost",
    "cpu_tuple_cost",
    "cpu_index_tuple_cost",
    "cpu_operator_cost",
    "effective_cache_size",
    "work_mem",
    "enable_seqscan",
    "enable_indexscan",
    "enable_indexonlyscan",
    "enable_bitmapscan",
    "enable_hashjoin",
    "enable_mergejoin",
    "enable_nestloop",
    "max_parallel_workers_per_gather",
    "jit",
)


def estimate_query(connection, query: QueryInput, *, allowed_schemas=("public",)):
    analysis = resolve_query(connection, query, allowed_schemas=allowed_schemas)
    try:
        # Only internally deparsed, qualified, catalog-validated SQL reaches EXPLAIN.
        raw = connection.execute(
            "EXPLAIN (FORMAT JSON, VERBOSE TRUE, COSTS TRUE, SETTINGS TRUE) "
            + analysis.canonical_sql,
            prepare=False,
        ).fetchone()[0]
    except psycopg.Error as error:
        if error.sqlstate and error.sqlstate.startswith(("22", "42")) and error.sqlstate != "42501":
            raise DomainError(
                "invalid_query", "PostgreSQL rejected query types, grouping, values or references."
            ) from None
        raise
    document = explain_plan(parse_explain(raw), analysis.tables)
    return analysis, document, raw


def _record(row: PlanAnalysis) -> PlanRecord:
    analysis = SQLAnalysis.model_validate(row.analysis)
    document = explain_plan(parse_explain(row.raw_explain), analysis.tables)
    return PlanRecord(
        id=row.id,
        scenario_id=row.scenario_id,
        captured_at=row.captured_at,
        database=row.database_name,
        server_version=row.server_version,
        original_sql=row.original_sql,
        frequency=row.frequency,
        analysis=analysis,
        plan=document,
        raw_explain=row.raw_explain,
        planner_settings=row.planner_settings,
    )


def analyze_query(
    engine: Engine, settings: Settings, query: QueryInput, *, scenario_id=None
) -> PlanRecord:
    with target_connection(settings) as connection:
        require_demo_identity(connection)
        version = int(connection.execute("SHOW server_version_num").fetchone()[0])
        if not 180000 <= version < 190000:
            raise DomainError(
                "unsupported_version", "Plan analysis currently requires PostgreSQL 18.", 503
            )
        analysis, document, raw = estimate_query(
            connection, query, allowed_schemas=settings.analysis_schemas
        )
        database, server_version, captured = connection.execute(
            "SELECT current_database(),current_setting('server_version'),clock_timestamp()"
        ).fetchone()
        planner_settings = dict(
            connection.execute(
                "SELECT name,setting FROM pg_settings WHERE name=ANY(%s)",
                (list(PLANNER_SETTINGS),),
            )
        )
    with Session(engine) as session, session.begin():
        row = PlanAnalysis(
            database_id=ensure_demo_target(session, settings),
            scenario_id=scenario_id,
            captured_at=captured,
            database_name=database,
            server_version=server_version,
            original_sql=query.sql,
            frequency=query.frequency,
            analysis=analysis.model_dump(mode="json"),
            raw_explain=raw,
            planner_settings=planner_settings,
            root_node_type=document.root.node_type,
            total_cost=document.root.total_cost,
        )
        session.add(row)
        session.flush()
        return _record(row)


def analyze_scenario(engine: Engine, settings: Settings, scenario_id: uuid.UUID):
    with Session(engine) as session:
        row = session.get(QueryScenario, scenario_id)
        if row is None:
            raise DomainError("not_found", "Saved query scenario was not found.", 404)
        query = QueryInput(sql=row.sql, frequency=row.frequency, parameters=row.parameters)
    return analyze_query(engine, settings, query, scenario_id=scenario_id)


def get_plan(engine: Engine, identifier: uuid.UUID):
    with Session(engine) as session:
        row = session.get(PlanAnalysis, identifier)
        if row is None:
            raise DomainError("not_found", "Saved plan analysis was not found.", 404)
        return _record(row)


def list_plans(engine: Engine, *, limit=50, offset=0):
    with Session(engine) as session:
        rows = session.scalars(
            select(PlanAnalysis)
            .order_by(PlanAnalysis.captured_at.desc(), PlanAnalysis.id)
            .offset(offset)
            .limit(limit)
        )
        return [PlanSummary.model_validate(row, from_attributes=True) for row in rows]
