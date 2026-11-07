import psycopg
from psycopg.rows import dict_row

from indexpilot.errors import DomainError
from indexpilot.sql.validation import validate_sql
from indexpilot.workloads.models import SnapshotData, StatementStats

BUFFER_COLUMNS = (
    "shared_blks_hit",
    "shared_blks_read",
    "shared_blks_dirtied",
    "shared_blks_written",
    "local_blks_hit",
    "local_blks_read",
    "local_blks_dirtied",
    "local_blks_written",
    "temp_blks_read",
    "temp_blks_written",
)


def _metadata(connection):
    return connection.execute(
        "SELECT pg_postmaster_start_time(), i.stats_reset, i.dealloc, d.oid::bigint, e.extversion "
        "FROM public.pg_stat_statements_info i CROSS JOIN pg_database d "
        "CROSS JOIN pg_extension e WHERE d.datname=current_database() "
        "AND e.extname='pg_stat_statements'"
    ).fetchone()


def collect_snapshot(connection: psycopg.Connection, *, limit: int = 1000) -> SnapshotData:
    if not 1 <= limit <= 1000:
        raise ValueError("Collection limit must be between 1 and 1000")
    try:
        with connection.transaction():
            # Use the source server's clock; Windows client clocks can share coarse ticks.
            started = connection.execute("SELECT clock_timestamp()").fetchone()[0]
            before = _metadata(connection)
            if before is None:
                raise DomainError(
                    "statistics_unavailable", "pg_stat_statements is not installed.", 503
                )
            if before[4] != "1.12":
                raise DomainError(
                    "unsupported_statistics_version",
                    "This collector requires pg_stat_statements 1.12.",
                    503,
                )
            # Column identifiers are internal constants; all values remain bound parameters.
            columns = ", ".join(BUFFER_COLUMNS)
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT userid::bigint, dbid::bigint, queryid, toplevel, query, calls, "
                    "total_exec_time, mean_exec_time, rows, stats_since, "
                    + columns
                    + " FROM public.pg_stat_statements WHERE dbid=%s AND queryid IS NOT NULL "
                    "ORDER BY userid, queryid, toplevel LIMIT %s",
                    (before[3], limit + 1),
                )
                records = cursor.fetchall()
            after = _metadata(connection)
            observed = connection.execute("SELECT clock_timestamp()").fetchone()[0]
    except psycopg.Error as error:
        status = 403 if error.sqlstate == "42501" else 503
        raise DomainError(
            "statistics_unavailable",
            "Statement statistics are unavailable or inaccessible.",
            status,
        ) from None
    entries, skipped = [], 0
    for record in records[:limit]:
        try:
            validate_sql(record["query"] or "")
        except DomainError:
            skipped += 1
            continue
        entries.append(
            StatementStats(
                identity=f"{record['dbid']}:{record['userid']}:{record['queryid']}:{int(record['toplevel'])}",
                query=record["query"],
                queryid=record["queryid"],
                userid=record["userid"],
                dbid=record["dbid"],
                toplevel=record["toplevel"],
                calls=record["calls"],
                total_exec_ms=record["total_exec_time"],
                mean_exec_ms=record["mean_exec_time"],
                rows=record["rows"],
                buffers={name: record[name] for name in BUFFER_COLUMNS},
                stats_since=record["stats_since"],
            )
        )
    warnings = [
        "Counters are cumulative and sampled over a collection window; the snapshot is not atomic."
    ]
    if skipped:
        warnings.append(f"Skipped {skipped} unsupported, unavailable or oversized statement texts.")
    if before != after:
        warnings.append(
            "Reset/eviction metadata changed during collection; interval deltas are unusable."
        )
    if len(records) > limit:
        warnings.append("Collection was truncated; interval deltas are unusable.")
    return SnapshotData(
        started_at=started,
        observed_at=observed,
        server_started_at=before[0],
        stats_reset=before[1],
        dealloc=before[2],
        dbid=before[3],
        extension_version=before[4],
        consistent=before == after,
        truncated=len(records) > limit,
        skipped_statements=skipped,
        entries=entries,
        warnings=warnings,
    )
