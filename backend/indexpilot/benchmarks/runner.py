import os
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

from psycopg import sql
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from indexpilot.benchmarks import dataset
from indexpilot.benchmarks.guard import LOCK_KEY, isolation, namespace, verify
from indexpilot.benchmarks.measurements import compare, parse_log, parse_summary, statistics_ms
from indexpilot.benchmarks.models import BenchmarkRequest
from indexpilot.benchmarks.pgbench import ContainerClient, read_script, write_script
from indexpilot.candidates.models import CandidateDefinition
from indexpilot.errors import DomainError
from indexpilot.evaluation.engine import EvaluationBudget, WorkloadEvaluator
from indexpilot.evaluation.session import HypotheticalSession
from indexpilot.local import LocalConnectionError, connect_local
from indexpilot.metadata.models import (
    BenchmarkArmIndex,
    BenchmarkCandidate,
    BenchmarkJob,
    BenchmarkMeasurement,
    BenchmarkQuery,
    BenchmarkSample,
    MonitoredDatabase,
    RecommendationSet,
)
from indexpilot.sql.models import SQLAnalysis

ARMS = ("baseline", "per_query", "indexpilot")


def terminate_clients(connection, application):
    connection.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename=current_user "
        "AND application_name=%s AND pid<>pg_backend_pid()",
        (application,),
    ).fetchall()


def plans_and_simple(connection, queries, candidates, selected, budget_bytes, check):
    connection.autocommit = False
    try:
        connection.execute("SET TRANSACTION READ ONLY")
        with HypotheticalSession(connection) as hypo:
            budget = EvaluationBudget(connection, seconds=30, statement_timeout_ms=5000)
            planning_check = budget.check

            def combined_check():
                check()
                planning_check()

            budget.check = combined_check
            evaluator = WorkloadEvaluator(connection, hypo, queries, candidates, budget)
            baseline = evaluator.evaluate()
            singletons = {identifier: evaluator.evaluate({identifier}) for identifier in candidates}
            simple = set()
            assignments = []
            for number, query in enumerate(baseline.queries):
                choices = [
                    (
                        value.queries[number].plan.root.total_cost,
                        candidates[identifier].signature,
                        identifier,
                    )
                    for identifier, value in singletons.items()
                    if value.queries[number].plan.root.total_cost is not None
                    and value.queries[number].plan.root.total_cost < query.plan.root.total_cost
                ]
                best = min(choices)[2] if choices else None
                if best is not None:
                    simple.add(best)
                assignments.append(
                    dict(
                        source_plan_id=str(query.source_plan_id),
                        candidate_id=str(best) if best else None,
                    )
                )
            simple_result = evaluator.evaluate(simple)
            selected_result = evaluator.evaluate(selected)
            summary = dict(
                policy="per-query-singleton-on-benchmark-v1",
                hypopg_capability=hypo.capability.model_dump(),
                assignments=assignments,
                baseline_weighted_planner_cost=baseline.weighted_cost,
                per_query_weighted_planner_cost=simple_result.weighted_cost,
                indexpilot_weighted_planner_cost=selected_result.weighted_cost,
                per_query_estimated_bytes=simple_result.estimated_size_bytes,
                per_query_estimated_budget_fit=(simple_result.estimated_size_bytes <= budget_bytes)
                if simple_result.estimated_size_bytes is not None
                else None,
            )
        return simple, summary
    finally:
        connection.rollback()
        connection.autocommit = True


def record_measurement(
    engine, job_id, repetition, arm, phase, stdout, raw, request, scripts, conditions
):
    rows = parse_log(
        raw,
        clients=request.clients,
        transactions=request.transactions_per_client,
        scripts=len(scripts),
    )
    metrics = statistics_ms(rows)
    metrics.update(
        tps=parse_summary(stdout, len(rows)),
        latency_unit="ms",
        throughput_unit="transactions_per_second",
        percentile_method="nearest_rank_individual_transactions",
        transaction_definition=conditions["transaction_definition"],
        script_transaction_counts=[
            sum(row[3] == number for row in rows) for number in range(len(scripts))
        ],
    )
    with Session(engine) as db, db.begin():
        row = BenchmarkMeasurement(
            job_id=job_id,
            repetition=repetition,
            arm=arm,
            phase=phase,
            metrics=metrics,
            conditions=conditions,
        )
        db.add(row)
        db.flush()
        db.add_all(
            BenchmarkSample(
                measurement_id=row.id,
                client_id=client,
                sequence=sequence,
                latency_us=latency,
                script_id=script,
            )
            for client, sequence, latency, script in rows
        )
    return dict(repetition=repetition, arm=arm, phase=phase, metrics=metrics, conditions=conditions)


def run_job(engine, settings, job_id, connection, expected):
    with Session(engine) as db:
        row = db.get(BenchmarkJob, job_id)
        request = BenchmarkRequest.model_validate(row.request)
        query_inputs = [
            SimpleNamespace(
                source_plan_id=item.source_plan_id,
                frequency=item.frequency,
                analysis=SQLAnalysis.model_validate(item.analysis),
            )
            for item in db.scalars(
                select(BenchmarkQuery)
                .where(BenchmarkQuery.job_id == job_id)
                .order_by(BenchmarkQuery.source_plan_id)
            )
        ]
        candidate_rows = list(
            db.scalars(select(BenchmarkCandidate).where(BenchmarkCandidate.job_id == job_id))
        )
        originals = {
            item.candidate_id: CandidateDefinition.model_validate(item.definition)
            for item in candidate_rows
        }
        selected = {item.candidate_id for item in candidate_rows if item.selected}
        if (
            db.scalar(
                select(MonitoredDatabase.id).where(
                    MonitoredDatabase.database_name == "indexpilot_bench"
                )
            )
            is not None
        ):
            raise DomainError(
                "unsafe_benchmark_target",
                "A monitored database uses the benchmark database name.",
                409,
            )
        original_estimates = db.get(RecommendationSet, row.recommendation_id).summary
        budget_bytes = original_estimates["storage_budget_bytes"]
    deadline = time.monotonic() + request.timeout_seconds

    def check():
        if time.monotonic() >= deadline:
            raise DomainError(
                "benchmark_timeout", "Benchmark exceeded its configured time limit.", 504
            )
        with Session(engine) as db:
            active = db.get(BenchmarkJob, job_id)
            if active.cancel_requested:
                raise DomainError(
                    "benchmark_cancelled", "Benchmark cancellation was requested.", 409
                )

    client = ContainerClient(job_id, check, settings=settings)
    manifest = dict(
        policy="isolated-pgbench-v1",
        application_version=version("indexpilot"),
        identity=expected,
        dataset=dict(
            seed=request.seed,
            orders=request.orders,
            anchor="2026-01-01T00:00:00+00:00",
            generator_version=1,
        ),
        client_platform=platform.system(),
        python_version=platform.python_version(),
        host_cpu_count=os.cpu_count(),
        cache_policy="read warmup; no OS/PostgreSQL cache flush; restored write datasets",
        protocol="simple",
        threads=1,
        arm_order="cyclic rotation by repetition",
        sample_semantics="committed transaction latency including BEGIN/COMMIT and protocol",
        budget_bytes=budget_bytes,
        original_recommendation_estimates=original_estimates,
        source_table_row_estimates={
            f"{table.schema_name}.{table.name}": table.estimated_rows
            for query in query_inputs
            for table in query.analysis.tables
        },
        client_transport="container-local Unix socket",
        client_statement_timeout_ms=5000,
        client_lock_timeout_ms=1000,
        random_schedule="same seed/weights; concurrent scheduling may change finite script counts",
    )
    completed = False
    cleanup = False
    error = None
    measurements = []
    try:
        manifest["pgbench_version"] = client.setup()
        if not manifest["pgbench_version"].startswith("pgbench (PostgreSQL) 18."):
            raise DomainError(
                "unsupported_pgbench_version", "Pinned PostgreSQL 18 pgbench is required.", 503
            )
        manifest["server_version"] = connection.execute("SHOW server_version").fetchone()[0]
        manifest["planner_settings"] = dict(
            connection.execute(
                "SELECT name,setting FROM pg_settings WHERE name=ANY(%s)",
                (
                    [
                        "shared_buffers",
                        "work_mem",
                        "effective_cache_size",
                        "random_page_cost",
                        "seq_page_cost",
                        "max_parallel_workers_per_gather",
                        "TimeZone",
                    ],
                ),
            )
        )
        manifest["container_limits"] = client.call(
            [
                "sh",
                "-c",
                "printf 'cpu='; cat /sys/fs/cgroup/cpu.max; "
                "printf 'memory='; cat /sys/fs/cgroup/memory.max; "
                "printf 'cpus='; nproc; head -n 1 /proc/meminfo",
            ]
        )
        dataset.prepare(connection, job_id, expected, request)
        client.verify_nonce(namespace(job_id))
        queries, candidates = dataset.context(connection, job_id, query_inputs, originals)
        simple, estimates = plans_and_simple(
            connection, queries, candidates, selected, budget_bytes, check
        )
        manifest["benchmark_estimates"] = estimates
        max_frequency = max(query.frequency for query in queries)
        weights = [max(1, round(query.frequency / max_frequency * 10000)) for query in queries]
        manifest["read_weights"] = [
            dict(
                source_plan_id=str(query.source_plan_id),
                frequency=query.frequency,
                pgbench_weight=weight,
            )
            for query, weight in zip(queries, weights, strict=True)
        ]
        manifest["weight_policy"] = (
            "nearest integer after max-frequency scaling to 10000, minimum one; quantized"
        )
        with Session(engine) as db, db.begin():
            for arm, ids in [("per_query", simple), ("indexpilot", selected)]:
                db.add_all(
                    BenchmarkArmIndex(job_id=job_id, candidate_id=identifier, arm=arm)
                    for identifier in ids
                )
            db.get(BenchmarkJob, job_id).manifest = manifest
        dataset.clean(connection, job_id, expected)
        hashes = {}
        for repetition in range(request.repetitions):
            order = ARMS[repetition % 3 :] + ARMS[: repetition % 3]
            for arm in order:
                ids = set() if arm == "baseline" else simple if arm == "per_query" else selected
                for operation in ("read", "insert", "update", "delete"):
                    check()
                    verify(connection, expected=expected)
                    fingerprint = dataset.prepare(
                        connection,
                        job_id,
                        expected,
                        request,
                        delete_rows=request.clients * request.transactions_per_client
                        if operation == "delete"
                        else 0,
                    )
                    if operation in hashes and hashes[operation] != fingerprint:
                        raise DomainError("dataset_mismatch", "Restored arm datasets differ.", 409)
                    hashes[operation] = fingerprint
                    queries, candidates = dataset.context(
                        connection, job_id, query_inputs, originals
                    )
                    actual_bytes = dataset.build_indexes(connection, candidates, ids)
                    client.verify_nonce(namespace(job_id))
                    conditions = dict(
                        dataset=fingerprint,
                        additional_index_bytes=actual_bytes,
                        actual_budget_fit=actual_bytes <= budget_bytes,
                        clients=request.clients,
                        seed=request.seed + repetition,
                        protocol="simple",
                        threads=1,
                        total_index_bytes=connection.execute(
                            "SELECT coalesce(sum(pg_indexes_size(c.oid)),0)::bigint "
                            "FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname=%s AND c.relkind='r'",
                            (namespace(job_id),),
                        ).fetchone()[0],
                    )
                    if operation == "read":
                        mixed = [
                            (read_script(query.analysis.canonical_sql), weight)
                            for query, weight in zip(queries, weights, strict=True)
                        ]
                        if request.read_warmup_per_client:
                            warmup_stdout, warmup_log = client.execute(
                                mixed,
                                clients=request.clients,
                                transactions=request.read_warmup_per_client,
                                seed=request.seed + repetition,
                                label=f"w_{repetition}_{arm}",
                            )
                            parse_summary(
                                warmup_stdout, request.clients * request.read_warmup_per_client
                            )
                            parse_log(
                                warmup_log,
                                clients=request.clients,
                                transactions=request.read_warmup_per_client,
                                scripts=len(mixed),
                            )
                        phases = [("read_mix", mixed)] + [
                            (f"read_q{number}", [(read_script(query.analysis.canonical_sql), 1)])
                            for number, query in enumerate(queries)
                        ]
                        conditions["transaction_definition"] = (
                            "BEGIN READ ONLY; one representative SELECT; COMMIT"
                        )
                        conditions["read_warmup_per_client"] = request.read_warmup_per_client
                    else:
                        phases = [
                            (
                                operation,
                                [(write_script(namespace(job_id), operation, request.orders), 1)],
                            )
                        ]
                        conditions["transaction_definition"] = {
                            "insert": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
                            "update": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
                            "delete": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
                        }[operation]
                        conditions["write_warmup_per_client"] = 0
                    for phase, scripts in phases:
                        check()
                        output, raw = client.execute(
                            scripts,
                            clients=request.clients,
                            transactions=request.transactions_per_client,
                            seed=request.seed + repetition,
                            label=f"m_{repetition}_{arm}_{phase}",
                        )
                        artifact = Path("benchmark-results") / str(job_id)
                        artifact.mkdir(parents=True, exist_ok=True)
                        stem = f"{repetition}_{arm}_{phase}"
                        (artifact / (stem + ".stdout.txt")).write_text(output, encoding="utf-8")
                        (artifact / (stem + ".transactions.log")).write_text(raw, encoding="utf-8")
                        conditions["additional_index_bytes_after"] = dataset.index_bytes(
                            connection, candidates, ids
                        )
                        conditions["actual_budget_fit_after"] = (
                            conditions["additional_index_bytes_after"] <= budget_bytes
                        )
                        actual_orders = connection.execute(
                            sql.SQL("SELECT count(*) FROM {}.orders").format(
                                sql.Identifier(namespace(job_id))
                            )
                        ).fetchone()[0]
                        expected_orders = fingerprint["row_counts"]["orders"]
                        if operation == "insert":
                            expected_orders += request.clients * request.transactions_per_client
                        if operation == "delete":
                            expected_orders -= request.clients * request.transactions_per_client
                        if actual_orders != expected_orders:
                            raise DomainError(
                                "benchmark_write_mismatch",
                                "Controlled write row counts differ.",
                                409,
                            )
                        conditions["orders_after"] = actual_orders
                        conditions["returning_row_checked"] = operation != "read"
                        measurements.append(
                            record_measurement(
                                engine,
                                job_id,
                                repetition,
                                arm,
                                phase,
                                output,
                                raw,
                                request,
                                scripts,
                                conditions,
                            )
                        )
                    dataset.clean(connection, job_id, expected)
        completed = True
    except Exception as failure:
        error = (
            failure.code
            if isinstance(failure, (DomainError, LocalConnectionError))
            else "benchmark_failed"
        )
    finally:
        try:
            client.check = lambda: None
            verify(connection, expected=expected)
            terminate_clients(connection, client.application)
            dataset.clean(connection, job_id, expected)
            client.cleanup()
            cleanup = True
        except Exception:
            error = "benchmark_cleanup_failed"
    result = None
    if completed and cleanup:
        result = dict(
            comparisons=compare(measurements, request.regression_threshold_pct),
            measurement_count=len(measurements),
            regression_threshold_pct=request.regression_threshold_pct,
            benchmark_estimates=manifest["benchmark_estimates"],
            warnings=[
                "Warm-cache measurements are local; no universal speedup is claimed.",
                "TPS/latency describe transactions, not isolated server query execution.",
                "Write probes are controlled orders-table operations, not production write rates.",
                "No WAL or cold-cache measurement; no statistical significance claim.",
                "Per-query union ignores the budget; actual storage fit is reported per arm.",
            ],
        )
    with Session(engine) as db, db.begin():
        row = db.get(BenchmarkJob, job_id)
        row.status = (
            "completed"
            if result is not None
            else "cancelled"
            if error == "benchmark_cancelled"
            else "failed"
        )
        row.result = result
        row.error_code = error
        row.cleanup_confirmed = cleanup
        row.finished_at = datetime.now(UTC)
        row.manifest = manifest


def run_next(engine, settings):
    # A metadata session lock prevents overlapping workers/recovery; a target session lock
    # also excludes sample regeneration on the same dedicated benchmark database.
    with engine.connect() as coordinator:
        if not coordinator.execute(select(func.pg_try_advisory_lock(918273648))).scalar():
            raise DomainError(
                "benchmark_worker_busy", "Another benchmark worker owns this queue.", 409
            )
        try:
            with connect_local("bench", autocommit=True, settings=settings) as connection:
                expected = isolation(connection, settings)
                with Session(engine) as db:
                    if (
                        db.scalar(
                            select(MonitoredDatabase.id).where(
                                MonitoredDatabase.database_name == "indexpilot_bench"
                            )
                        )
                        is not None
                    ):
                        raise DomainError(
                            "unsafe_benchmark_target",
                            "A monitored database uses the benchmark identity.",
                            409,
                        )
                if not connection.execute(
                    "SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)
                ).fetchone()[0]:
                    raise DomainError(
                        "benchmark_target_busy", "The disposable benchmark target is busy.", 409
                    )
                try:
                    with Session(engine) as db:
                        stale = [
                            row.id
                            for row in db.scalars(
                                select(BenchmarkJob).where(
                                    or_(
                                        BenchmarkJob.status == "running",
                                        and_(
                                            BenchmarkJob.status.in_(["failed", "cancelled"]),
                                            BenchmarkJob.cleanup_confirmed.is_(False),
                                        ),
                                    )
                                )
                            )
                        ]
                    for identifier in stale:
                        cleaned = False
                        try:
                            terminate_clients(connection, "indexpilot-bench-" + identifier.hex)
                            dataset.clean(connection, identifier, expected)
                            ContainerClient(identifier, lambda: None, settings=settings).cleanup()
                            cleaned = True
                        finally:
                            with Session(engine) as db, db.begin():
                                row = db.get(BenchmarkJob, identifier)
                                was_running = row.status == "running"
                                row.status = "failed"
                                row.error_code = (
                                    "worker_interrupted" if was_running else row.error_code
                                )
                                row.cleanup_confirmed = cleaned
                                row.finished_at = datetime.now(UTC)
                    with Session(engine) as db, db.begin():
                        row = db.scalar(
                            select(BenchmarkJob)
                            .where(BenchmarkJob.status == "queued")
                            .order_by(BenchmarkJob.created_at)
                            .with_for_update()
                        )
                        if row is None:
                            return None
                        row.status = "running"
                        row.started_at = datetime.now(UTC)
                        identifier = row.id
                    try:
                        run_job(engine, settings, identifier, connection, expected)
                    except Exception:
                        with Session(engine) as db, db.begin():
                            row = db.get(BenchmarkJob, identifier)
                            row.status = "failed"
                            row.error_code = "worker_failed"
                            row.finished_at = datetime.now(UTC)
                        raise
                    return identifier
                finally:
                    connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
        finally:
            coordinator.execute(select(func.pg_advisory_unlock(918273648)))
