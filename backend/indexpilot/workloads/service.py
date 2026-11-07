import uuid

from pglast import fingerprint
from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from indexpilot.config import Settings
from indexpilot.db.connections import require_demo_identity, target_connection
from indexpilot.errors import DomainError
from indexpilot.metadata.models import (
    MonitoredDatabase,
    QueryPattern,
    QueryScenario,
    QueryStatistic,
    Workload,
    WorkloadSnapshot,
)
from indexpilot.workloads.collector import collect_snapshot
from indexpilot.workloads.deltas import snapshot_delta
from indexpilot.workloads.manual import prepare_query
from indexpilot.workloads.models import (
    ManualWorkloadInput,
    PatternView,
    QueryInput,
    ScenarioInput,
    ScenarioView,
    SnapshotData,
    SnapshotSummary,
    SnapshotView,
    StatementStats,
    WorkloadSummary,
    WorkloadView,
)


def _require(session: Session, model, identifier):
    row = session.get(model, identifier)
    if row is None:
        raise DomainError("not_found", "Requested workload resource was not found.", 404)
    return row


def _target(session: Session, settings: Settings) -> uuid.UUID:
    values = dict(
        target_key="demo",
        host=settings.db_host,
        port=settings.db_port,
        database_name="indexpilot_demo",
        role_name="indexpilot_analyzer",
        credential_reference="analyzer_password",
    )
    session.execute(
        insert(MonitoredDatabase)
        .values(id=uuid.uuid4(), **values)
        .on_conflict_do_nothing(index_elements=["target_key"])
    )
    target = session.scalar(select(MonitoredDatabase).where(MonitoredDatabase.target_key == "demo"))
    if any(getattr(target, key) != value for key, value in values.items()):
        raise DomainError(
            "target_changed", "Configured target differs from its saved identity.", 409
        )
    return target.id


def _scenario(pattern_id: uuid.UUID, prepared) -> QueryScenario:
    return QueryScenario(
        pattern_id=pattern_id,
        sql=prepared.original.sql,
        parameters={
            str(key): value.model_dump() for key, value in prepared.original.parameters.items()
        },
        representative_sql=prepared.representative,
        missing_parameters=prepared.missing_parameters,
        frequency=prepared.original.frequency,
    )


def create_manual(engine: Engine, settings: Settings, body: ManualWorkloadInput) -> WorkloadView:
    # Validate the entire upload before writing any metadata; input SQL never reaches the target.
    prepared = []
    for position, query in enumerate(body.queries, start=1):
        try:
            prepared.append(prepare_query(query))
        except DomainError as error:
            raise DomainError(
                error.code, f"Query {position}: {error.message}", error.status
            ) from None
    with Session(engine) as session, session.begin():
        workload = Workload(database_id=_target(session, settings), name=body.name, source="manual")
        session.add(workload)
        session.flush()
        patterns = {}
        for query in prepared:
            if query.fingerprint not in patterns:
                pattern = QueryPattern(
                    workload_id=workload.id,
                    identity=query.fingerprint,
                    fingerprint=query.fingerprint,
                    normalized_sql=query.normalized,
                )
                session.add(pattern)
                session.flush()
                patterns[query.fingerprint] = pattern
            session.add(_scenario(patterns[query.fingerprint].id, query))
        identifier = workload.id
    return get_workload(engine, identifier)


def create_collected(engine: Engine, settings: Settings, name: str) -> WorkloadView:
    with Session(engine) as session, session.begin():
        row = Workload(
            database_id=_target(session, settings), name=name, source="pg_stat_statements"
        )
        session.add(row)
        session.flush()
        identifier = row.id
    return get_workload(engine, identifier)


def list_workloads(engine: Engine, *, limit: int, offset: int) -> list[WorkloadSummary]:
    with Session(engine) as session:
        rows = session.scalars(
            select(Workload)
            .order_by(Workload.created_at.desc(), Workload.id)
            .offset(offset)
            .limit(limit)
        )
        return [WorkloadSummary.model_validate(row, from_attributes=True) for row in rows]


def get_workload(engine: Engine, identifier: uuid.UUID, *, limit=100, offset=0) -> WorkloadView:
    with Session(engine) as session:
        row = _require(session, Workload, identifier)
        statement = select(QueryPattern).where(QueryPattern.workload_id == identifier)
        total = session.scalar(
            select(func.count())
            .select_from(QueryPattern)
            .where(QueryPattern.workload_id == identifier)
        )
        patterns = list(
            session.scalars(statement.order_by(QueryPattern.id).offset(offset).limit(limit))
        )
        scenarios = (
            list(
                session.scalars(
                    select(QueryScenario)
                    .where(
                        QueryScenario.pattern_id.in_([pattern.id for pattern in patterns]),
                    )
                    .order_by(QueryScenario.id)
                )
            )
            if patterns
            else []
        )
        views = [
            PatternView(
                id=pattern.id,
                identity=pattern.identity,
                fingerprint=pattern.fingerprint,
                normalized_sql=pattern.normalized_sql,
                server_queryid=pattern.server_queryid,
                server_userid=pattern.server_userid,
                server_dbid=pattern.server_dbid,
                server_toplevel=pattern.server_toplevel,
                scenarios=[
                    ScenarioView.model_validate(item, from_attributes=True)
                    for item in scenarios
                    if item.pattern_id == pattern.id
                ],
            )
            for pattern in patterns
        ]
        warnings = [
            "SQL admission is syntactic only; catalog resolution and planning are not implemented."
        ]
        if row.source == "pg_stat_statements":
            warnings.append(
                "Collected counters are cumulative. Use snapshot deltas for interval frequencies."
            )
        if any(item.missing_parameters for item in scenarios):
            warnings.append(
                "Some queries need representative parameters before later plan analysis."
            )
        if total > offset + len(patterns):
            warnings.append("Patterns are paginated; request the next offset page.")
        return WorkloadView(
            id=row.id,
            name=row.name,
            source=row.source,
            created_at=row.created_at,
            patterns=views,
            pattern_total=total,
            pattern_offset=offset,
            warnings=warnings,
        )


def add_scenario(engine: Engine, pattern_id: uuid.UUID, body: ScenarioInput) -> ScenarioView:
    with Session(engine) as session, session.begin():
        pattern = _require(session, QueryPattern, pattern_id)
        prepared = prepare_query(QueryInput(sql=pattern.normalized_sql, **body.model_dump()))
        if prepared.missing_parameters:
            raise DomainError(
                "missing_parameters", "Supply all representative parameter positions."
            )
        row = _scenario(pattern_id, prepared)
        session.add(row)
        session.flush()
        return ScenarioView.model_validate(row, from_attributes=True)


def take_snapshot(engine: Engine, settings: Settings, workload_id: uuid.UUID) -> SnapshotView:
    with Session(engine) as session:
        row = _require(session, Workload, workload_id)
        if row.source != "pg_stat_statements":
            raise DomainError(
                "wrong_workload_source", "Only collected workloads support snapshots."
            )
        _target(session, settings)
    with target_connection(settings) as connection:
        require_demo_identity(connection)
        snapshot = collect_snapshot(connection)
    return save_snapshot(engine, workload_id, snapshot)


def save_snapshot(engine: Engine, workload_id: uuid.UUID, data: SnapshotData) -> SnapshotView:
    with Session(engine) as session, session.begin():
        _require(session, Workload, workload_id)
        snapshot = WorkloadSnapshot(workload_id=workload_id, **data.model_dump(exclude={"entries"}))
        session.add(snapshot)
        session.flush()
        for entry in data.entries:
            pattern_id = session.scalar(
                insert(QueryPattern)
                .values(
                    id=uuid.uuid4(),
                    workload_id=workload_id,
                    identity=entry.identity,
                    fingerprint=fingerprint(entry.query),
                    normalized_sql=entry.query,
                    server_queryid=entry.queryid,
                    server_userid=entry.userid,
                    server_dbid=entry.dbid,
                    server_toplevel=entry.toplevel,
                )
                .on_conflict_do_update(
                    constraint="pattern_identity", set_={"identity": entry.identity}
                )
                .returning(QueryPattern.id)
            )
            session.add(
                QueryStatistic(
                    snapshot_id=snapshot.id,
                    pattern_id=pattern_id,
                    **entry.model_dump(
                        exclude={
                            "identity",
                            "queryid",
                            "userid",
                            "dbid",
                            "toplevel",
                        }
                    ),
                )
            )
        identifier = snapshot.id
    return get_snapshot(engine, identifier)


def get_snapshot(engine: Engine, identifier: uuid.UUID) -> SnapshotView:
    with Session(engine) as session:
        snapshot = _require(session, WorkloadSnapshot, identifier)
        rows = session.execute(
            select(QueryStatistic, QueryPattern)
            .join(
                QueryPattern,
                QueryStatistic.pattern_id == QueryPattern.id,
            )
            .where(QueryStatistic.snapshot_id == identifier)
            .order_by(QueryPattern.identity)
        )
        entries = [
            StatementStats(
                identity=pattern.identity,
                query=stat.query,
                queryid=pattern.server_queryid,
                userid=pattern.server_userid,
                dbid=pattern.server_dbid,
                toplevel=pattern.server_toplevel,
                calls=stat.calls,
                total_exec_ms=stat.total_exec_ms,
                mean_exec_ms=stat.mean_exec_ms,
                rows=stat.rows,
                buffers=stat.buffers,
                stats_since=stat.stats_since,
            )
            for stat, pattern in rows
        ]
        fields = SnapshotData.model_fields.keys() - {"entries"}
        return SnapshotView(
            id=snapshot.id,
            workload_id=snapshot.workload_id,
            entries=entries,
            **{name: getattr(snapshot, name) for name in fields},
        )


def list_snapshots(engine: Engine, workload_id: uuid.UUID, *, limit: int, offset: int):
    with Session(engine) as session:
        _require(session, Workload, workload_id)
        rows = session.scalars(
            select(WorkloadSnapshot)
            .where(
                WorkloadSnapshot.workload_id == workload_id,
            )
            .order_by(WorkloadSnapshot.observed_at.desc(), WorkloadSnapshot.id)
            .offset(offset)
            .limit(limit)
        )
        return [SnapshotSummary.model_validate(row, from_attributes=True) for row in rows]


def get_delta(engine: Engine, identifier: uuid.UUID, previous_id: uuid.UUID | None):
    current = get_snapshot(engine, identifier)
    if previous_id is None:
        with Session(engine) as session:
            previous_id = session.scalar(
                select(WorkloadSnapshot.id)
                .where(
                    WorkloadSnapshot.workload_id == current.workload_id,
                    WorkloadSnapshot.observed_at < current.observed_at,
                )
                .order_by(WorkloadSnapshot.observed_at.desc(), WorkloadSnapshot.id)
                .limit(1)
            )
    previous = get_snapshot(engine, previous_id) if previous_id else None
    if previous and previous.workload_id != current.workload_id:
        raise DomainError("different_workloads", "Snapshots must belong to the same workload.")
    return snapshot_delta(previous, current)
