# Benchmark protocol

Implemented in M9 for the provisioned local PostgreSQL 18/Compose environment. The engine runs real pgbench experiments, retains individual transaction samples and saves measured latency/TPS/storage comparisons. It supports the five public sample tables and up to ten saved representative SELECTs. It is not a general production benchmark/deployment service.

## Run a confirmed job

Keep PostgreSQL/WSL running, apply migration 0009 and restart the API. In a separate foreground terminal run:

```powershell
uv run python scripts/run_benchmarks.py --serve
```

Alternatively `--once` handles one queued job and exits, which is how verification was executed. No worker starts invisibly with the API. Follow the [recommendation example](RECOMMENDATIONS.md), then explicitly request disposable index creation:

```powershell
$body = @{
  recommendation_id = $recommendation.id
  confirm_disposable_benchmark = $true
  orders = 10000
  seed = 42
  repetitions = 3
  clients = 1
  transactions_per_client = 200
  read_warmup_per_client = 20
  timeout_seconds = 300
  regression_threshold_pct = 10
} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/benchmarks `
  -ContentType application/json -Body $body
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/benchmarks/$($job.id)"
$measurements = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/benchmarks/$($job.id)/measurements"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/benchmarks/measurements/$($measurements[0].id)/samples?limit=100"
```

POST returns 202 queued, not a measured result. Poll until terminal status; without a worker it stays queued. GET `/api/v1/benchmarks?recommendation_id=<UUID>&limit=20&offset=0` lists associated jobs. POST `/{job_id}/cancel` cancels queued jobs immediately or requests cooperative cancellation of a running job. Running cancellation is visible through cancel_requested until cleanup finishes. Measurements completed before a failure/cancel remain identifiable, but the whole job has no successful aggregate result.

Only a saved recommendation ID and bounded experiment settings are accepted. Confirmation must be the boolean true, not 1 or a string. Bounds: 1,000–100,000 orders; seed 0–2^31−1; 1–5 repetitions; 1–4 clients; 5–10,000 measured transactions per client/phase; 0–1,000 read-warmup transactions; 10–600 seconds; nonnegative regression threshold up to 1,000%. At most eight queued/running jobs and 200,000 measured transactions are permitted. The bound is `3 * repetitions * clients * transactions * (queries + 4)`.

## Isolation

Only indexpilot_bench as indexpilot_bench_owner with its exact disposable marker is permitted. Live server/database identities are compared with metadata/demo connections; a monitored record naming the benchmark database is conservatively refused even through a hostname alias. A row nonce verifies the fixed Compose pgbench transport reaches the same database as the guarded psycopg connection. That check precedes workload execution. No request accepts arbitrary hosts, DSNs, roles, SELECTs or DDL.

Every operation/repetition/arm uses a generated UUID-owned schema, not the existing public sample tables. Ownership/marker/identity are checked before cleanup. Baseline schemas contain only the template's constraint indexes. Additional indexes are rebuilt from validated saved keys and current generated-table catalogs. Existing public indexes, including user-created indexes and constraints, are preserved. Cleanup drops only the known job tables/sequence/schema without CASCADE; unknown external dependencies block cleanup rather than being destroyed.

A metadata advisory lock serializes workers, and a benchmark-session lock also excludes concurrent sample regeneration. Interrupted running jobs become failed on the next worker start; owned resources are verified/cleaned before another claim. Failed/cancelled jobs with unconfirmed cleanup are retried for safe cleanup. Unsafe markers/dependencies stop further work and require operator resolution; no destructive fallback is attempted. Target refusal before claim leaves confirmed jobs queued for correction or cancellation.

The worker uses the pinned local Compose project `indexpilot`, pgbench 18, container-local Unix sockets and the provisioned secret mount. Passwords are neither CLI arguments nor returned errors. Each pgbench statement has a five-second timeout, one-second lock timeout and ten-second idle-transaction timeout. An outer container timeout is 60 seconds per invocation. Job deadlines/cancel requests are checked cooperatively between work and during subprocess waits. Cleanup has separate bounded calls, so the requested job timeout is not an exact wall-clock deadline. Cancellation terminates only the job's own benchmark-role application-name sessions.

## Comparable experiments

The shared backend generator creates users, products, orders, order items and payments with recorded scale/seed and fixed 2026-01-01 UTC anchor. Squared hash-derived user uniforms concentrate orders among fewer users; dates span the prior year and status cycles over four values. The original generation CLI delegates to this module. The benchmark creates new namespaces and records ordered row hashes/counts; mismatch across comparable arms aborts the job. ANALYZE is run after generation, but sampled statistics/physical layout are not guaranteed bit-identical.

Compare:

1. Baseline: only indexes required by schema constraints.
2. Per-query baseline: independently useful singleton recommendations, deduplicated; disclose storage and any budget mismatch.
3. IndexPilot: the saved recommendation's selected set, originally chosen within its estimated-byte budget. Physical fit is measured and disclosed separately.

The per-query baseline evaluates all approved singleton candidates using HypoPG on an initial restored benchmark dataset, chooses each query's lowest estimated cost when it improves on baseline, then deduplicates that union. It ignores the storage budget; its larger storage is disclosed. It does not reuse a partial historical singleton search. IndexPilot's set is kept fixed from the recommendation rather than being retuned after seeing benchmark results. No budget-matched per-query variant or exhaustive solver is implemented. Source columns, collations/nullability and constraints must match the fixed template; the worker refuses silent reinterpretation of incompatible source schemas.

Jobs retain versions, OS/CPU/container resource limits, selected planner settings, source/benchmark estimates, dataset hashes/counts, representative queries/frequencies, weights, budget, clients, transaction count, repetitions and warmup policy. Arm order rotates cyclically with repetition. Fixed representative values are preserved through AST/schema rebinding and normal SQL admission; no parameter-sampling feature is implied. Mixture weights scale the largest frequency to 10,000 and round others to positive integers; quantization and actual script counts are recorded. The same seed/weights are used across arms per repetition. Concurrent scheduling may change finite sample mixes. No cache flushing or cold-cache claim is made.

Read measurements include a weighted mixture plus a separate probe for each representative query. Each read transaction is BEGIN READ ONLY, one SELECT and COMMIT. Their latency includes protocol/transaction overhead, not isolated server query execution time. pgbench TPS excludes initial connection time. Mean/median/nearest-rank p95 come from complete individual microsecond transaction logs, never aggregate statement means. Incomplete/failed/duplicate samples and failed transaction summaries fail the experiment. Read warmup is separate and checked for successful completion. Requests containing multiline/backslash SQL literals are refused because pgbench meta commands are a separate language.

Every write operation starts from a separately restored dataset. Inserts create negative-ID orders with a sequence, a known parent user and committed rows. Updates change one randomly chosen original order's indexed user_id to 1/2. Deletes remove separately preloaded negative-ID orders without child references, using a sequence-allocation SELECT. RETURNING/gset requires exactly one affected row per DML, and final row counts are checked. These are committed controlled orders-table transactions, not a production write-rate model. Writes have no warmup; prior mutation/dead-tuple state is not carried between arms/operations. WAL/write amplification is not measured.

Additional index bytes before/after each phase use pg_relation_size's main fork; total_index_bytes uses pg_indexes_size including constraint indexes. Budget-fit flags compare those measured additional main-fork bytes with the configured estimated budget; they are not filesystem-capacity guarantees. Mutation growth is visible. Failed/time-limited runs stay failed with no completed aggregate; no unfavorable observation is silently removed. Per-repetition variation and regression flags are retained without a statistical-significance claim.

## Estimates versus actuals

HypoPG reports relative planner costs and estimated sizes. Physical experiments report measured milliseconds, TPS and actual bytes. Show both, with separate labels; there is no general conversion from a planner cost unit to milliseconds. Flag per-query regressions using a declared threshold, even if total throughput improves. Do not promise IndexPilot always wins.

## Measured local evidence

The checked-in [sanitized result summary](../sample/benchmarks/local-results.json) records job `38ced867-7cfc-429f-9a3a-bc4ee90e51d6`: 10,000 orders, seed 42, two queries with frequencies 100/25, three rotated repetitions, one client and 200 measured transactions per phase. All **54 measurements / 10,800 individual transactions** completed with cleanup confirmed. [The example notes](../sample/benchmarks/README.md) describe query mapping and limitations.

Mean committed transaction latency across the three equal-size repetitions, in milliseconds:

| Phase | Baseline | Per-query | IndexPilot |
| --- | ---: | ---: | ---: |
| Mixed reads | 0.3604 | 0.1209 | 0.2117 |
| Latest paid orders | 0.5275 | 0.1425 | 0.5415 |
| Orders by user | 0.3086 | 0.1128 | 0.1133 |
| Insert | 2.3684 | 2.2840 | 2.3189 |
| Update | 2.2787 | 2.3154 | 5.3443 |
| Delete | 2.3827 | 5.0028 | 2.3481 |

The estimated budget was 300,000 bytes. IndexPilot used one user_id index measuring **114,688 main-fork bytes**; the per-query union used two indexes totaling **475,136 bytes**, exceeding that budget. IndexPilot's mixed-read mean improved 41.26% here, while the larger per-query arm improved 66.45%. IndexPilot did not win every comparison. Its update mean and the per-query delete mean triggered the declared 10% regression threshold. Each was dominated by one slower repetition; the JSON retains all repetitions and dispersion. No cause is attributed to indexing alone, and no universal benefit or significance is claimed.

Raw local stdout/logs remain in ignored `benchmark-results/<job-id>/`. Individual samples and measured conditions are also normalized in metadata and survive restart. Failed prototype records remain failed. The recommendation snapshot's benchmark_outcome stays null at its capture time; subsequent measured jobs are retrieved through the benchmark recommendation_id filter rather than rewriting historical estimates.

The workload integration tests now request a bounded 5,000-entry capture on the pinned server when local history has accumulated; the application's default remains 1,000, with truncation/reset/eviction checks unchanged. No global statement-statistics reset was used to make tests pass. Final test/commit records are in [PROGRESS.md](PROGRESS.md).

PostgreSQL documents [pgbench script weights, transaction logs and transaction-rate semantics](https://www.postgresql.org/docs/18/pgbench.html). The implementation's isolation, reset and result behavior was also exercised against the actual pinned local database/container.
