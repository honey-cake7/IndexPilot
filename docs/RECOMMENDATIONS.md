# Saved recommendation explanations

Implemented in M8. IndexPilot freezes a completed M7 optimization into a recommendation with selected index definitions, proposal evidence, before/after plans, weighted query contributions, selection-step marginal gains, provenance and uncertainty. These are **planner estimates**, not measured runtime or write-performance results. No physical index is created.

## Use the API

Apply migration 0008 and restart the backend:

```powershell
uv sync --locked
uv run alembic upgrade head
uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. Follow the [optimization example](OPTIMIZATION_ALGORITHM.md) to obtain `$optimization`, then:

```powershell
$body = @{ optimization_id = $optimization.id } | ConvertTo-Json
$recommendation = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/recommendations `
  -ContentType application/json -Body $body
$recommendation.summary
$recommendation.indexes | Select-Object candidate_id, selection_order, definition, estimated_size_bytes, explanation
$recommendation.queries | Select-Object source_plan_id, frequency, explanation
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/recommendations/$($recommendation.id)"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/recommendations?optimization_id=$($optimization.id)&limit=20&offset=0"
```

Only an existing optimization UUID is accepted; arbitrary SQL, target settings and replacement selection members are rejected. POST creates a snapshot (201), or returns its unchanged existing snapshot (200) on a repeat. One recommendation is allowed per optimization. Concurrent creations serialize on that optimization's metadata row; ordinary configured statement/lock timeouts still apply. There are no recommendation update/delete endpoints. To change budget, frequencies or settings, create a new optimization and recommendation.

Creation reads only saved metadata. It does not reconnect to the target, refresh current catalogs or replan queries. This permits documenting a historical analysis after target permissions/schema have changed, while explicitly warning that current deployment validity is unverified. GET reads only the recommendation's frozen rows; it does not consult mutable optimizer/candidate source content. Source references remain protected by foreign keys. These are immutable through the API, not a sandbox against a privileged metadata administrator changing database rows directly.

## Understand the explanation

`summary` freezes original baseline/final objective components, budget, total estimated bytes, stop reason, evaluation count and search-limit status. `options` preserves the heuristic write/regression settings and declared frequency basis. `provenance` preserves generation/selection versions, original observation times, database/OID/version, selected planner settings, HypoPG capabilities and source IDs. Those timestamps describe observations, not a fully frozen physical database or a freshness guarantee.

Each selected `index` has its table/schema, B-Tree keys, opclasses/collations/ordering, estimated bytes, source selection trial and order. `relevant_queries` distinguishes saved proposal evidence from actual final-plan use. A query may motivate a candidate without using it in the final plan; another query may use it without having proposed it. Neither relationship independently proves a latency gain.

An index's `selection_step_read_cost_reduction` compares the preceding selected set to the whole trial set when that index was added. `selection_step_net_gain` also incorporates the optional heuristic write penalty. These are **marginal selection-step observations**, not independent attribution of the final total gain to each index. The explanation explicitly warns about this distinction and flags a selected index absent from every final plan. Qualitative write-overhead text states that inserts, deletes and indexed-column updates may require maintenance; no write latency, WAL or maintenance cost was measured.

Every `query` retains its original input, representative bound SQL, frequency, raw/parsed baseline and hypothetical plans. The snapshot stores query/catalog context and raw plans plus versioned explanation metrics; plan parsing/display observations use the current compatible reader. Estimated query cost reduction is baseline minus final root cost. Weighted reduction is frequency times that change; its contribution is `100 * weighted_reduction / baseline_workload_cost`. Contributions are relative to the complete workload baseline and can be negative for regressions. They sum to the workload's read-improvement percentage, not a penalized objective percentage. A zero workload/query baseline makes the relevant percentage null rather than inventing a gain.

Plan comparisons list actual node types, baseline index names and final used candidate IDs. They describe observed estimated-plan changes, without assuming that any sequential scan is a defect or assigning an unproved cause. Missing visible column statistics, unavailable ANALYZE timestamps and query regressions produce warnings. `evidence_level=planner_estimate`, `execution_measured=false` and `benchmark_outcome=null` avoid an invented confidence score or benchmark result. Greedy-search and estimated-storage limitations remain visible.

## Export reviewable SQL

Deployment SQL is a separate read-only artifact:

```powershell
$sql = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/recommendations/$($recommendation.id)/deployment-sql"
$sql.statements | Select-Object candidate_id, sql
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/recommendations/$($recommendation.id)/deployment.sql" `
  -OutFile recommendation.sql
```

The JSON artifact has `requires_human_review=true` and `executed=false`. The download is a plain SQL attachment with fixed review warnings. Both include only the selected indexes; an empty selection produces no commands. Index SQL is structurally rebuilt from saved catalog/key context with identifier quoting, checked against its saved definition/signature and frozen at snapshot creation. It is never accepted as an arbitrary request string or executed by these routes.

Review current schema, existing index/name conflicts, physical space and locking before any deliberate use. Historical estimated bytes do not guarantee final disk size. There is no automatic production deployment endpoint or general SQL executor. M9 now provides a separately guarded [disposable benchmark runner](BENCHMARKING.md) with explicit confirmation. GET `/api/v1/benchmarks?recommendation_id=<UUID>` retrieves subsequent measured outcomes; benchmark_outcome remains null in the historical recommendation snapshot rather than rewriting what was known at its capture time.

## Storage, privacy and verification

Migration 0008 adds recommendation_set, recommendation_set_index, recommendation_query and recommendation_index_query. Selected membership/order, source trial/query references and relevant-query links are normalized. Composite foreign keys prevent a link from referring to another recommendation's query/index. Variable definitions, context, raw plans and explanations use structured JSON. One metadata transaction saves the header and all children; validation/constraint failures roll everything back. SQL/schema/parameter literals may contain private business data, so retain the local-only deployment and avoid sharing snapshots/artifacts indiscriminately. Credential files/DSNs are not copied, and request logs omit submitted bodies/SQL.

New unit tests use explicitly synthetic arithmetic to verify contributions, regression/zero-baseline handling, marginal penalties, statistics warnings and quoted SQL structure. Real PostgreSQL/API tests cover saved/reloaded history across app instances, target SELECT revocation, source mutation independence, concurrent duplicate creation, one-connection retrieval, atomic rollback, composite scope/byte/order constraints, empty selections, safe errors and SQL export without physical index creation. Test-owned fixtures and grants are restored. Full-suite counts and commit verification are recorded in [PROGRESS.md](PROGRESS.md).
