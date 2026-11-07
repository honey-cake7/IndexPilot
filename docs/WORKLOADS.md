# Workload input and collection

Implemented in M3. These endpoints parse, validate and persist SQL/statistics; they do not execute submitted queries or generate execution plans. Catalog resolution, type checking against PostgreSQL and plan analysis belong to M4. Every saved scenario is labeled `syntax_only`; a representative SQL string is not a claim that it can run successfully.

## Manual input

Start the migrated backend using the commands in [DEVELOPMENT.md](DEVELOPMENT.md), then use `/docs` or PowerShell:

```powershell
$workload = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/workloads/manual `
  -ContentType application/json `
  -Body (Get-Content sample/workload.json -Raw)
$workload.id
```

The JSON file is a working example with representative parameters and frequencies. Each query has a positive finite frequency ≤1 billion. Treat frequency as the number of executions in a common observation period, or as a relative weight consistently across the workload. Each representative scenario carries its own frequency; several examples must share/split the intended query weight rather than each inheriting the full frequency.

`POST /api/v1/workloads/sql` accepts `{name, sql, frequency}`. The SQL string may contain 1–100 statements; the supplied frequency applies to each. `POST /api/v1/workloads/upload` accepts multipart fields `file`, optional `name`, and optional `frequency`. Upload a UTF-8 `.sql` file; an initial UTF-8 BOM is accepted. Files are read as content, never saved or executed as scripts. Semicolons within literals/comments are handled by the PostgreSQL parser.

The request-body limit is 1 MiB, including multipart overhead. SQL files and individual queries are limited to 65,536 UTF-8 bytes; manual batches contain at most 100 queries. AST traversal has nesting/node limits. Unsupported SQL returns a safe error; batch errors identify the query number. No partially valid batch is saved.

## Supported SQL and limits

The admission policy permits a conservative SELECT subset over unqualified/public-schema relations, explicit JOIN ON, equality/range/arithmetic operators, Boolean/null tests, ordering, grouping, basic built-in scalar casts and simple count/sum/avg/min/max aggregates. It rejects DDL/DML, multiple statements per query, CTEs, SELECT INTO, row locks, subqueries, set operations, function-based FROM items, window functions, custom qualified operators/types and arbitrary function calls.

This is **syntactic admission**, not a database sandbox. A table name may resolve to a view, or an expression to a custom implementation. M3 never sends the submitted SQL to the target. M4 must resolve inspected ordinary relations/types/operators and reject unsafe semantics before EXPLAIN. Databases remain administrator-controlled local targets.

Patterns use pglast structural fingerprints; original SQL and frequency are preserved in separate scenarios. Display normalization replaces literal AST nodes with placeholders. Structural grouping is not proof that every scenario has equal selectivity or identical plans.

## Representative parameters

Use PostgreSQL `$1` … `$100` positions. Each supplied value has an explicit type: `int8`, `numeric`, `text`, `date`, `timestamp`, `timestamptz` or `bool`. Missing values are preserved as unresolved positions, with `representative_sql: null`. Unused values are rejected.

Values are inserted as quoted literal AST nodes with explicit `pg_catalog` casts, never by replacing `$1` substrings. Quotes, semicolons and placeholder-looking text remain data. This does not check whether a string is a valid integer/date; later catalog/planning validation must do that. Values and query literals are sensitive local metadata and are not request-log fields.

Add scenarios to a normalized pattern with `POST /api/v1/query-patterns/{id}/scenarios`, passing `{parameters, frequency}`. Supply every required position. Collected statement text often contains placeholders without actual values; the collector does not invent or recover those values.

## Collected workloads and periodic snapshots

```powershell
uv run python scripts/collect_workload.py --samples 2 --interval-seconds 30
```

This creates a collected workload, prints its UUID, and saves two real observations 30 seconds apart. To append later, pass `--workload-id <UUID>`. Collection is explicitly invoked and bounded, not an always-running scheduler. The CLI allows 1–1,000 samples and intervals from 0.1–3,600 seconds. A two-sample 0.1-second run was executed during M3 verification; its counts came from PostgreSQL and are not latency benchmark results.

The equivalent API flow:

1. POST `/api/v1/workloads/collected` with `{name}`.
2. POST `/api/v1/workloads/{id}/snapshots` at each observation point.
3. GET `/api/v1/snapshots/{id}` to retrieve raw cumulative statistics.
4. GET `/api/v1/snapshots/{id}/delta` to compare with the preceding saved observation. Optionally pass `previous_id` explicitly.

The collector currently supports pg_stat_statements **1.12 on PostgreSQL 18**. It reads only the connected demo database, retains the `(dbid, userid, queryid, toplevel)` identity, and skips statements outside the supported syntax policy. Each entry stores cumulative calls, total/mean execution milliseconds, rows, ten buffer counters and `stats_since`. Snapshots retain extension version, database OID, server start, reset/deallocation metadata, collection start/end, skipped count and warnings. Start/end timestamps come from PostgreSQL's clock.

The database is not asked to run a workload to populate statistics. Collection reads statistics that already exist. It can legitimately return no supported entries. The capture has a bounded 1,000-entry scan; truncation is explicit and disables interval inference. Statistics are sampled over a window, not an atomic MVCC snapshot.

## Correct interval interpretation

For comparable entries:

```
interval_calls = current.calls - previous.calls
interval_total_ms = current.total_exec_ms - previous.total_exec_ms
interval_mean_ms = interval_total_ms / interval_calls
```

If interval calls are zero, mean is null. The server's cumulative mean remains available in raw snapshots but is never substituted for an interval mean. No percentiles are derived from aggregate counters.

The first observation needs a baseline. New entries do not get an assumed zero history; missing entries retain a missing reason. Global resets, server/database/version changes, any observed eviction, per-entry `stats_since` changes, decreasing/inconsistent counters, overlapping/unordered windows and truncated/unstable collections produce unusable deltas with reasons and null metrics. Eviction handling is deliberately conservative even if a particular surviving entry might be unaffected. A min/max-only reset does not invalidate unchanged cumulative counters; this was tested with PostgreSQL's actual reset function.

## Retrieval and persistence

GET `/api/v1/workloads` lists workloads. GET `/api/v1/workloads/{id}` returns patterns/scenarios. GET `/api/v1/workloads/{id}/snapshots` lists captures. Lists accept `limit` (1–100) and `offset`; workload responses include `pattern_total` and `pattern_offset` so pagination is explicit. Detailed snapshots contain at most the bounded capture's entries.

Signed 64-bit query IDs are decimal **strings in JSON**, preserving their exact value in JavaScript; database storage and Python arithmetic use integers. UUIDs identify IndexPilot's own resources. Query text/counters are saved with each observation; later collection does not overwrite historical observations. Keep metadata and secret files local and excluded from public artifacts.

Sources: PostgreSQL documents [cumulative counters, statement identity and reset functions](https://www.postgresql.org/docs/18/pgstatstatements.html); pglast documents [PostgreSQL AST parsing and transformation](https://pglast.readthedocs.io/en/latest/usage.html). These capabilities underpin ingestion; they do not demonstrate index effectiveness.
