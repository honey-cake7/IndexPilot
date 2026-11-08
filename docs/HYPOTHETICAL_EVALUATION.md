# Hypothetical index-set evaluation

Implemented in M6 using PostgreSQL 18 and HypoPG 1.4. The evaluator asks the real planner about individual and combined B-Tree candidate sets without creating physical indexes or executing submitted SELECTs. All costs are **planner units, not milliseconds**; sizes are HypoPG estimates, not measured disk consumption. Storage-budget selection and write penalties belong to M7.

## Run the API

Keep the local PostgreSQL container running, apply migration 0006 and restart the backend:

```powershell
uv sync --locked
uv run alembic upgrade head
uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. The root `/` and `/favicon.ico` do not have routes, so a 404 there is expected. Follow the [candidate example](CANDIDATES.md) to obtain `$batch`, then in that same PowerShell session:

```powershell
$request = @{ batch_id = $batch.id } | ConvertTo-Json
$evaluation = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/evaluations `
  -ContentType application/json -Body $request
$evaluation | Select-Object id, status, cleanup_confirmed
$evaluation.baseline | Select-Object weighted_cost, cost_unit
$evaluation.trials | Select-Object candidate_ids, weighted_cost, estimated_improvement_pct, estimated_size_bytes, storage_complete
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/evaluations/$($evaluation.id)"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/evaluations?batch_id=$($batch.id)&limit=20&offset=0"
```

The default request evaluates a fresh empty-set baseline, every proposed singleton, and the complete proposed set when it has more than one member. It does not search all subsets or recommend a winner. An empty candidate batch yields baseline only. Each evaluation replans **every source query**, preserving its representative values and frequency even if a candidate originated from another query.

To choose explicit trials, send UUID arrays in `candidate_sets`:

```json
{
  "batch_id": "<saved-batch-UUID>",
  "candidate_sets": [
    ["<candidate-A-UUID>"],
    ["<candidate-A-UUID>", "<candidate-B-UUID>"]
  ]
}
```

Every ID must identify a proposed candidate in that batch. Up to 64 distinct nonempty sets, each with 1–32 distinct IDs, are accepted. Set order is irrelevant to duplicate detection. The baseline is always included separately. Candidate batches keep their generation-time `not_evaluated`/null fields; separate immutable evaluation runs contain the later estimates.

## Reading the evidence

`baseline` and `trials` contain per-query raw EXPLAIN JSON, parsed plan trees, root costs, frequency, actual hypothetical-index usage, regression flags, weighted totals and estimated storage. `cost_unit` is `planner_cost`; `execution_measured` is always false. Improvement is `100 * (baseline - trial) / baseline`. A zero/unknown baseline yields a null percentage. Negative improvement is retained; one query can regress while the workload total improves.

The workload cost is `sum(frequency * root_total_cost)` across all source queries. Do not sum child costs: root totals already include them. Nonfinite, missing or overflowed totals remain unknown. A combined set is planned directly, because overlapping or complementary indexes do not have additive singleton benefits.

Each member's estimated bytes must be positive and known for `storage_complete=true`. An unavailable size function or unsupported estimate yields null, never a free index. Any unknown member makes the whole set's size null; the empty baseline alone legitimately has zero hypothetical bytes. These flags give M7 the information needed to reject unknown storage for automatic hard-budget selection; M6 does not implement that selection.

`context` records the database/OID, server version, backend PID, catalog observation time, selected planner settings and policy/budget. `queries` preserves fresh resolved table/statistics context. These are historical observations, not a promise that a transaction freezes all physical storage, ANALYZE results or concurrent server activity.

Missing/inaccessible required HypoPG functions produce a saved `status=unavailable` resource (HTTP 201) with capability warnings and no baseline/trials. It is a recorded outcome, not a successful comparison. Other evaluation failures return a safe error with the saved evaluation UUID; GET can retrieve that failed record. No partial successful comparisons are published. Invalid batch membership is rejected before an evaluation record is started. Runs are synchronous and saved atomically only after work finishes, so process crashes can leave no run record. There is no background job resource yet.

## Session lifecycle and safety

`service.py` loads a saved batch, verifies target identity and opens one fresh, exclusively held repeatable-read/read-only analyzer connection. `context.py` refreshes/locks referenced tables, verifies relation/column identity, reruns normal SQL admission/resolution, and structurally recompiles candidate DDL from current catalogs. Stored DDL is never passed through unchecked. Equivalent indexes created since generation require regenerating the batch.

M4 stored representative bindings in canonical SQL rather than separate plan parameters. Replanning parses that SQL as an AST, removes only internal pg_catalog operator qualification, and reruns normal validation/resolution. Bound strings/casts stay literal nodes, including embedded quotes, semicolons and `$1` text; this is not text substitution.

`session.py` discovers extension-member functions and verifies schema/function privileges. The held connection clears both HypoPG indexes and hidden-existing-index state before the baseline and each set, creates all members together, EXPLAINs every query without ANALYZE or prepared-plan reuse, then explicitly resets and verifies zero remaining state. Function names/identifiers are qualified and CREATE INDEX text is passed as a bound function argument.

**Rollback alone does not remove HypoPG session memory.** Timeout/error recovery rolls back an aborted transaction only to regain the ability to call reset. Cleanup has a separate bounded statement timeout; any failed reset/verification closes/discards the physical connection. Another connection cannot see these hypothetical indexes. There is no general deployment/physical DDL endpoint. Existing trusted-server and narrow SQL/catalog restrictions still apply; this is not a sandbox for malicious database administrators or concurrent hostile DDL.

`engine.py` owns a copied, fixed query/candidate context and a private cache of at most 65 sets (baseline plus 64 trials). Cache reads/writes are deep copies, and hits still clear hypothetical state and check selected planner settings. Any failure invalidates the evaluator; no cache survives connection/run exit. There is no shared or persistent estimate cache. `persistence.py` saves normalized run/query/set/member/plan evidence independently of the target connection.

`INDEXPILOT_EVALUATION_TIMEOUT_SECONDS` defaults to 30 seconds (allowed 1–120). The monotonic planning budget is checked between table/query/index operations, with each planning statement limited by remaining time and the configured statement timeout. Cleanup statements use their own 2-second timeout. This is a cooperative planning budget, not an exact HTTP deadline: connection setup, multiple catalog statements, cleanup and metadata persistence can extend request duration.

## Executed verification

`uv run pytest --integration -q`: **240 passed** (153 unit and 87 real PostgreSQL/API cases). M6 adds 22 unit cases and 14 integration cases. The live tests cover a fresh baseline despite tampered historical costs, weighted multi-query plans, singleton/combined interactions, optional/missing permissions, missing extension, timeout recovery, rollback-persistent state, concurrent session isolation, cache isolation/settings changes, unknown sizes, unsafe saved DDL rejection, newly existing indexes, an empty candidate batch and persisted reload equality. Physical index counts remain unchanged by evaluation.

The suite uses unique fixture schemas. Permission probes briefly revoke/restore public function grants on the dedicated local development cluster, and one cleanup test terminates only its own backend PID. Run it serially. A deliberately issued internal sleep tests timeout handling; ordinary API SQL remains unexecuted. Initial test assumptions about permission caching and a supposedly zero-cost PostgreSQL plan were corrected using observed behavior. Zero-baseline arithmetic is tested with explicit unit inputs, not invented database results.

A separate manual local evaluation of five public.orders candidates recorded baseline **320.12** and combined **28.05** planner units, with **1,662,976 estimated bytes**. The default API run was saved as `233f6e78-d78d-431d-a3ea-7cb06ecff993`, with six trials and exact reload equality. These are observations from that local state, not expected reproducible constants or latency gains. Ruff and Alembic schema checks passed; migration 0006 was reversed/reapplied only on the separate disposable metadata database.

## Sources

[HypoPG usage and session-local estimates](https://hypopg.readthedocs.io/en/rel1_stable/usage.html), [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/18/sql-explain.html), and [psycopg transactions/savepoints](https://www.psycopg.org/psycopg3/docs/basic/transactions.html) describe the underlying APIs. The rollback/cleanup behavior above was also exercised against the actual pinned local extension.
