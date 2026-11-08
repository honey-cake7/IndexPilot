# Verified development progress

## M0 — Repository inspection and technical roadmap

**What was built:** inspected and cloned the official empty repository; established local author identity and secret exclusions; documented dependency-ordered milestones, architecture, metadata relationships, optimizer specification, benchmark protocol and learning notes. Application code has not started.

**Why it matters / DBMS concepts:** separates planning estimates from measured execution and metadata from the analyzed/benchmark databases. Defines what evidence is required for indexes, workload optimization and actual performance claims.

**How it works:** `ROADMAP.md` specifies objectives, concepts, files, dependencies, functionality, checks, acceptance and GitHub deliverables for every milestone. `ARCHITECTURE.md` defines package and trust boundaries. Other design documents supply the data and experimental contracts.

**Technical decisions:** Python modular monolith, PostgreSQL 18 reference, pglast AST validation, psycopg target access, SQLAlchemy/Alembic metadata, session-isolated HypoPG and marginal-benefit-per-byte optimization. All are planned and require implementation evidence.

**Executed inspection:** `git ls-remote --symref ... HEAD` found no refs; `git clone ... .` confirmed an empty repository; `git status --short --branch`, remote inspection and symbolic HEAD confirmed unborn main. Git Credential Manager credentials were checked against GitHub's authenticated user/repository APIs without printing secrets. Owner honey-cake7 (Aniket Patil) has push/admin access; active rulesets list is empty. The connected GitHub app has no push access; local Git is used. An initial dry-run before a first commit correctly failed because main had no commit yet; that is not an authentication failure.

**Environment:** Windows PowerShell; Git, Python 3.10.11 and uv 0.11.6 available. Windows Docker, psql, pgbench, Node/npm and gh unavailable. WSL Ubuntu 26.04.1 is available as root; its package index lists PostgreSQL 18 and HypoPG 1.4.2, but neither is installed. No database tests, container build or benchmarks have run at M0.

**Verification:** documentation reviewed for milestone coverage, links, explicit planned/implemented separation, security boundaries and secret exclusions; Git whitespace check and final diff review required before commit. No application test suite exists at this milestone.

**Run/review:** `git status`, `git diff --check` and open `docs/ROADMAP.md`. The README intentionally supplies no fictional application startup command.

**GitHub record:** `Document IndexPilot architecture and development roadmap`, branch `main`, [`f83f6addf4070c3c1004e1f391cb569ebbee9754`](https://github.com/honey-cake7/IndexPilot/commit/f83f6addf4070c3c1004e1f391cb569ebbee9754). Push succeeded; `git ls-remote origin refs/heads/main` matched local HEAD exactly.

**Status / next:** M0 completed and published before application implementation. M1 began afterward.

## M1 — PostgreSQL environment and reproducible sample database

**What was built:** digest-pinned PostgreSQL 18.6/HypoPG 1.4.3 Docker image, Compose healthcheck/volume/loopback port, pg_stat_statements preload, three databases with separate roles, generated ignored credentials, Python 3.12 dependency lock, guarded deterministic data generation, environment inspection and real integration tests.

**Why / DBMS concepts:** keys enforce relationships; table statistics support planning; separate privileges enforce read-only analysis even if a session disables its default read-only setting. HypoPG state is session-local; tests proved that property on actual connections.

**Implementation:** `infra/postgres/init.sh` provisions roles/databases/extensions; `sample/schema.sql` defines constraints; `scripts/generate_demo.py` hashes a seed into repeatable distributions and derives order/payment totals from item rows; `backend/indexpilot/local.py` resolves credentials and sanitizes connection failures. Metadata remains free of sample business tables.

**Decisions:** fixed timestamp anchor; no random wall-clock inputs; no automatic reset of populated databases; reset requires the marked database and matching owner; no CASCADE; container build tools stay in a separate stage; HypoPG source checksum verified. Windows Docker runs through WSL, whose foreground lifetime must be maintained.

**Executed setup:** installed WSL Docker/Compose/client packages, installed managed Python 3.12.13, ran uv sync, local secret initialization, image build, clean startup, both default generators, environment inspection, 100,000-order benchmark generation and restoration. Exact commands and prerequisites are in [DEVELOPMENT.md](DEVELOPMENT.md).

**Verification:** Ruff lint/format, Compose config and Bash syntax checks; default tests distinguish skipped integration tests; **15 tests passed with `uv run pytest --integration -q`**, including a second run on a separate newly initialized Docker volume. Checks cover versions/extensions, deterministic fingerprints, seed/scale changes, row counts/totals, guarded reset, metadata separation, denied writes/schema/temp creation, real EXPLAIN/statistics, HypoPG storage/session isolation/cleanup and credential-free connection diagnostics. An initial missing HypoPG view grant was fixed and retested. A WSL idle shutdown interrupted one run; later complete runs passed with WSL held active. No benchmark timings are claimed.

**GitHub record:** `Set up PostgreSQL development environment`, branch `main`, [`a40b8d689ed84485d92203f901018c987b976067`](https://github.com/honey-cake7/IndexPilot/commit/a40b8d689ed84485d92203f901018c987b976067). Push verified against remote main.

**Status / next:** M1 verified; API, workload ingestion, SQL safety engine, candidate generator, optimizer, benchmarking UI and reports are not implemented. M2 adds typed backend configuration, capability reporting, initial metadata migration, structured logging and safe API errors.

## M2 — Backend foundation and database connectivity

**Built / purpose:** typed FastAPI health and configured-demo capability endpoints; bounded Pydantic settings; fresh read-only target connections; independent SQLAlchemy metadata engine; Alembic migration 0001; structured JSON request events, server-generated request IDs and sanitized errors. The first metadata table stores only credential references.

**Concepts / flow:** API → validated settings → dedicated target session → catalog/capability probes → typed response. Metadata migrations use a different database and owner. Savepoints keep an inaccessible extension probe from invalidating all capability checks; timeouts bound database work.

**Decisions:** no arbitrary-host connection endpoint; local-only deployment; no automatic migration at application startup; liveness independent of credentials/database; pg_stat_statements runtime probe avoids granting pg_read_all_settings. Unknown configuration is nullable. Authentication startup errors lacking SQLSTATE remain generic connection errors. SQLAlchemy URLs hide passwords; raw exceptions and validation inputs are not logged/returned.

**Run:** `uv run alembic upgrade head`; `uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000`; open `/docs`, `/health/ready`, `/api/v1/connections/demo`. Full instructions in DEVELOPMENT.md.

**Executed checks:** Ruff; **25 tests passed** with `uv run pytest --integration -q`; real API readiness/capability requests, missing HypoPG reporting on metadata, bad credentials/unreachable port, statement timeout, read-only DDL rejection, metadata constraints, sanitized responses/logs and configuration bounds. On a separate disposable metadata database ran Alembic upgrade/downgrade/upgrade and `alembic check` (no schema drift). No benchmarks or frontend tests exist yet.

**GitHub:** `Add backend configuration and database capability checks`, branch main, [`512121af18efbc0a6d7aa54a1e704d6fae036fd2`](https://github.com/honey-cake7/IndexPilot/commit/512121af18efbc0a6d7aa54a1e704d6fae036fd2). Push verified against remote main.

**Status / next:** M0–M2 verified. Next is safe manual workload ingestion and reset-aware cumulative statement-statistics snapshots. Optimization remains unimplemented.

## M3 — SQL workload input and collection

**1. What was built:** manual JSON/pasted SQL/multipart file input; finite positive frequencies; pglast PostgreSQL 18 AST admission and normalization; typed representative parameter binding; saved workloads/patterns/scenarios; actual pg_stat_statements snapshots; pure interval-delta calculation; bounded periodic CLI and paginated retrieval. API request bodies, SQL bytes and AST complexity are limited.

**2. Why it matters:** the later optimizer needs a workload, representative inputs and trustworthy query frequencies. Capturing cumulative statistics without proper interval subtraction would optimize the wrong workload. All M3 operations preserve a clear boundary: submitted SQL is parsed/saved, never executed or explained.

**3. DBMS concepts:** normalized query patterns versus value-dependent selectivity; full `(database, role, queryid, top-level)` statement identity; cumulative counters versus interval metrics; resets/evictions; transactions, foreign keys and normalized observation tables. No percentiles or index-effectiveness claims are inferred from aggregate counters.

**4. How it works:** `sql/validation.py` admits a constrained AST subset. `workloads/manual.py` fingerprints patterns; `parameters.py` inserts quoted typed literal nodes. `collector.py` reads real demo-database statistics and provenance around a bounded scan. `deltas.py` compares compatible snapshots. `service.py` persists/retrieves normalized records, and `api/workloads.py` exposes the typed routes. Migration 0002 introduces five related tables. `scripts/collect_workload.py` records explicit periodic observations without a daemon.

**5. Technical decisions:** ingestion is labeled syntax_only until M4 resolves catalogs/types and validates planning safety. Unresolved placeholders remain explicit; user-provided scenarios have separate weights. Unknown/new/reset/evicted intervals produce unusable deltas with null metrics. A repeated real test exposed coarse Windows timestamp ticks, so collection boundaries now use PostgreSQL's clock. Query IDs serialize as decimal strings to preserve JavaScript precision. A loose test matcher was corrected after an additional probe introduced another matching query; no PostgreSQL history was cleared to hide the failure.

**6. Run:** `uv sync --locked`; `uv run alembic upgrade head`; start the backend using DEVELOPMENT.md. Submit `sample/workload.json` through POST `/api/v1/workloads/manual`, use `/workloads/sql` for pasted SQL or `/workloads/upload` for a UTF-8 .sql file. Run `uv run python scripts/collect_workload.py --samples 2 --interval-seconds 30` for explicit periodic capture. The CLI's two-sample 0.1-second variant was actually executed, with saved records. Full endpoint contracts, limits and examples are in [WORKLOADS.md](WORKLOADS.md).

**7. Executed verification:** **103 tests passed** with `uv run pytest --integration -q`: 70 unit tests plus 33 real PostgreSQL/API integration tests. Default `pytest -q` reported 70 passed/33 intentionally skipped; these are not counted as database passes. Coverage includes unsafe/malformed SQL, Unicode/comments/semicolons, parameter literal injection resistance, missing/unused parameters, frequency/bounds validation, persistence across app instances, atomic batch rejection, real multipart upload, query/snapshot pagination, a controlled three-call delta, real targeted reset and min/max-only reset, actual missing/inaccessible statistics, truncation and safe API errors. Global reset/restart/eviction arithmetic is tested with explicit unit fixtures; the live cluster was not globally reset or restarted for those tests. Ruff lint/format, documentation links, Git whitespace and Alembic drift checks passed. Migration 0002 upgrade → downgrade to 0001 → upgrade passed on the separate disposable metadata database. No frontend/E2E/index benchmark exists yet.

**8. GitHub update:** `Add workload collection using pg_stat_statements`, branch `main`, [`5235164d8f9db1c01474a2d3f06d4fb87859d054`](https://github.com/honey-cake7/IndexPilot/commit/5235164d8f9db1c01474a2d3f06d4fb87859d054). Push succeeded; `git ls-remote origin refs/heads/main` exactly matched local HEAD. This subsequent documentation update records the now-known implementation SHA.

**9. Current status:** M0–M3 completed, verified and published. Workload ingestion and collection are usable; no catalog-based query resolution, execution-plan engine, candidate generator, optimizer, index benchmark, dashboard or report feature is implemented. Saved SQL/parameter values are sensitive local metadata. The initial target is the configured PostgreSQL 18 demo with pg_stat_statements 1.12; unsupported queries are skipped/rejected explicitly.

**10. Next:** stop for user review. M4 will add schema/catalog resolution and recursive EXPLAIN JSON analysis only after the user explicitly continues. No M4 application work has begun.

## M4 — SQL, schema and execution-plan intelligence

**1. What was built:** real schema/table/column/type/key/index/statistics inspection; catalog-based alias and column resolution; filtering/join/order features; conservative planning safety checks; EXPLAIN JSON capture, recursive parsing, deterministic explanations and saved plan history. Explicit plan requests can analyze a new query or a saved M3 scenario. Migration 0003 introduces plan_analysis.

**2. Why it matters:** candidate generation needs physical column identity and actual plan/statistics evidence. A parser alone cannot know whether id is ambiguous, a name is a view, or an expression invokes custom database code. M4 supplies that semantic boundary before any recommendation algorithm is introduced.

**3. DBMS concepts:** schemas and relation OIDs; alias/name resolution; sampled selectivity and negative n_distinct; B-Tree key ordering, opclasses, collations, INCLUDE, predicates and expressions; table/index sizes and cumulative usage; recursive scan/join/sort plans; root planner cost versus double-counted child costs. Sequential scans are not automatically defects, and cost units are never presented as milliseconds.

**4. How it works:** schema/catalogs.py reads actual catalogs into typed models. sql/resolution.py resolves references and extracts supported features; safety.py rejects unsupported objects/dependencies and qualifies internal SQL. plans/service.py requests EXPLAIN without ANALYZE on a held read-only target connection. parser.py preserves nested children/conditions; explanations.py interprets observed operations conservatively. The API saves raw JSON, schema/query context, frequency, capture/version/settings and optional scenario identity, then supports retrieval independent of current catalogs.

**5. Decisions:** only the configured trusted PostgreSQL 18 demo is supported. Planning requires permanent heap tables, table SELECT/schema USAGE, supported built-in types and existing B-Tree dependencies. Views, RLS, inheritance/partitions, generated/custom types and unapproved functions/operators are refused. Additional application schemas are explicitly allowlisted. A real pglast check revealed schema names are ignored by structural fingerprints, so M4 adds relation scope to manual identity. Histogram/common values are opt-in and formatted only for supported built-in types. This is not a sandbox for hostile administrators/extensions or concurrent malicious DDL.

**6. Run:** execute `uv run alembic upgrade head`, then start the backend as documented. Use GET /api/v1/schema and /schema/table?table_name=orders; POST /api/v1/plans accepts SQL/frequency/parameters; POST /api/v1/query-scenarios/{id}/plan analyzes saved examples; GET /api/v1/plans/{id} reloads evidence. [PLAN_ANALYSIS.md](PLAN_ANALYSIS.md) contains the exact PowerShell request and supported subset. The initial public-table API example and all sample workload statements were actually planned here.

**7. Executed checks:** **166 tests passed with `uv run pytest --integration -q`**, comprising 104 unit tests and 62 real PostgreSQL/API integration tests. M4 adds 29 database/API cases covering catalog/index/statistics details, quoted/multiple schemas, aliases and ambiguity, scope-aware grouping, representative values, saved/reloaded plans, unsafe dependency rejection, RLS/views/custom types, permission/type errors, sample workloads and actual index/index-only/bitmap/nested-loop/hash/merge plans. Session-local planner switches exercise node types only; they are not performance evidence. Pure tests cover recursive/optional/zero/invalid/measured-plan shapes, depth bounds, schema configuration and invalid parameter text. Fixture schemas/indexes are isolated and removed afterward. Ruff lint/format, whitespace, locked dependency synchronization, schema checks and documentation links passed. Migration 0003 upgrade → downgrade to 0002 → upgrade and Alembic no-drift verification passed on the separate disposable metadata database. No benchmarks/frontend tests apply yet.

**8. GitHub update:** `Parse execution plans and inspect PostgreSQL schema`, branch main, [`2e7b76d30b946ecd5f873cb6af3f0cffb2319013`](https://github.com/honey-cake7/IndexPilot/commit/2e7b76d30b946ecd5f873cb6af3f0cffb2319013). Push succeeded; remote main exactly matched local HEAD. This subsequent documentation update records the verified implementation SHA.

**9. Current status:** M0–M4 completed, verified and published. Workloads can reach real catalog-resolved estimated plans and saved explanations. No candidate generation, HypoPG evaluation engine, workload optimizer, physical benchmark runner, dashboard or reports are implemented. Ingestion remains syntax_only until an explicit plan request succeeds. Unsupported semantics produce explicit errors rather than speculative plans.

**10. Next:** pause for user review after publication. M5 will generate bounded schema-aware B-Tree candidates and deduplicate existing indexes. No M5 application work has begun.

## M5 — Automatic B-Tree candidate generation

**1. What was built:** a pure bounded generator over M4's resolved query features; singleton/composite equality, range, inner-join and compatible ordering candidates; verified catalog opclasses and safely quoted deterministic DDL; exact duplicate rejection and explicit overlap/unique-coverage decisions; saved candidate batches, source-plan membership and normalized evidence; typed POST/GET APIs.

**2. Why it matters:** HypoPG evaluation needs a manageable set of meaningful alternatives rather than every possible column permutation. M5 now supplies valid, explainable definitions and retains why each was proposed or rejected, without pretending its benefits have been measured.

**3. DBMS concepts:** equality prefixes and range keys; mixed sort direction/NULL placement; B-Tree opclasses/collations; unique versus ordinary index semantics; partial/expression/covering/prefix overlap; schema identity and stale catalog data; normalized many-to-many candidate/query evidence. Equality-first is a heuristic, including on PostgreSQL 18 where skip scans may help other orders.

**4. Implementation:** candidates/generator.py consumes typed resolved plans independently of HTTP; sql.py verifies default opclasses and quotes identifiers; deduplication.py compares usable signatures. The service refreshes table/index metadata, checks relation/column identity, generates bounded decisions and persists them. Migrations 0004–0005 introduce candidate batches/decisions/source links and convert prototype evidence into foreign-keyed rows while preserving existing records. No generation endpoint invokes HypoPG or physical CREATE INDEX.

**5. Decisions:** hard width/proposed limits of 3/32, working pool 512, attempt cap 4096; stable round-robin sources and structural priority, with explicit truncation. Do not confuse this priority with workload-cost optimization. Prefix/backward/covering overlap is retained for later evaluation; exact ordinary duplicates and matching unique coverage have separate rejection reasons. New size/benefit fields remain null. Pytest importlib mode fixes duplicate unit/integration basenames exposed by full-suite collection. Unknown opclasses and unsupported feature patterns are skipped explicitly.

**6. Run:** `uv sync --locked`; `uv run alembic upgrade head`; restart the backend. POST /api/v1/candidates with saved plan_ids and optional max_columns/max_candidates. GET /api/v1/candidates/{id} reloads decisions; GET /api/v1/candidates lists batches. [CANDIDATES.md](CANDIDATES.md) includes the complete executable PowerShell flow and limits. A live public.orders example was actually generated and its five proposed definitions accepted through session-local HypoPG syntax checks.

**7. Executed verification:** **204 tests passed** with `uv run pytest --integration -q`: 131 unit tests and 73 real PostgreSQL/API integration tests. M5 adds 27 unit cases and 11 database/API cases. Coverage includes ordering, bounded composite alternatives, joins, OR/NOT exclusions, exact/unique/partial/expression/covering/opclass distinctions, prefix/backward warnings, source merging, quoted/Unicode identifiers, width/count/pool/attempt limits, new indexes after source capture, changed column/table identities, saved history and empty sets. Generated SQL was validated using real session-local HypoPG with reset/finally cleanup and unchanged physical index counts; no benefit or latency measurement is claimed. A data-bearing 0005 downgrade/re-upgrade preserved the full prototype batch; 0004–0005 were reversed/reapplied on the separate disposable metadata database with no drift. Ruff lint/format, Git whitespace, locked dependencies, documentation links and staged-credential checks passed.

**8. GitHub update:** `Generate schema-aware B-Tree index candidates`, branch main, [`13a5b4c95855451563f073f5d892caaa2e957646`](https://github.com/honey-cake7/IndexPilot/commit/13a5b4c95855451563f073f5d892caaa2e957646). Push succeeded; remote main exactly matched local HEAD. This subsequent documentation update records the verified implementation SHA.

**9. Current status:** M0–M5 completed, verified and published. Workloads can reach saved catalog-resolved plans and bounded candidate batches with explanations. Hypothetical cost/size evaluation, storage-budget selection, write penalties, benchmark execution, dashboard and reports remain unimplemented. Candidate output is explicitly not_evaluated and does not claim performance improvement.

**10. Next:** pause after publishing M5. M6 will evaluate individual and combined hypothetical index sets using actual PostgreSQL planner estimates with controlled session cleanup. No M6 application work has begun.

## M6 — HypoPG evaluation engine

**1. What was built:** a dedicated-session evaluator for fresh baseline, individual and combined B-Tree sets; every source query is replanned with representative values and frequencies. Outputs include raw/parsed plans, actual hypothetical-index usage, weighted planner costs, relative changes/regression flags, estimated bytes and cleanup confirmation. Typed POST/GET/list routes and migration 0006 persist normalized run/query/set/member/plan evidence.

**2. Why it matters:** candidate definitions alone cannot show which alternatives PostgreSQL would choose. M6 obtains actual planner evidence for complete sets, supplying M7's future storage-budget selector without assuming individual benefits add together or claiming measured speedups.

**3. DBMS concepts:** session-local extension memory versus transaction rollback; EXPLAIN estimates versus ANALYZE measurements; root plan cost, frequency weighting and representative selectivity; fresh baselines, index interactions and optional storage estimates; repeatable-read scope and normalized many-to-many set/query evidence. A lower estimated cost is not proof of lower latency.

**4. Implementation:** evaluation/context.py refreshes catalog bindings, reconstructs representative SQL through its AST, reruns normal resolution and structurally recompiles candidate DDL. session.py discovers granted extension functions and owns reset/create/size/verified cleanup. engine.py evaluates whole sets independently of HTTP, captures selected planner settings and holds a bounded private cache. costs.py handles finite weighted arithmetic and zero/unknown baselines. service.py orchestrates one held connection; persistence.py saves/reloads immutable evidence; api/evaluations.py exposes it. Shared schema/context.py preserves M5's stale-binding checks.

**5. Technical decisions:** fresh empty-set baseline instead of historical M4 costs; default singleton plus full-set trials instead of combinatorial search; all source queries in every trial; at most 64 requested sets plus baseline; private deep-copy cache, no cross-run estimates. Rollback alone was proven to leave HypoPG memory, so explicit reset/unhide/verification is mandatory and cleanup failure closes the connection. Optional unknown sizes remain null; no free-index assumption. The 30-second cooperative planning budget has separate bounded cleanup, not an exact HTTP deadline. Failed/unavailable runs save no partial comparisons; synchronous results are persisted only after work finishes. Generation snapshots remain unchanged.

**6. Run:** `uv sync --locked`; `uv run alembic upgrade head`; restart `uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000`. Open `/docs` (root 404 is expected). POST /api/v1/evaluations with a saved batch_id; optionally specify candidate_sets. GET /api/v1/evaluations/{id} reloads evidence; list supports batch_id/limit/offset. [HYPOTHETICAL_EVALUATION.md](HYPOTHETICAL_EVALUATION.md) provides executable PowerShell and precise response semantics. A manual five-candidate public.orders run observed 320.12 baseline versus 28.05 combined planner units, with 1,662,976 estimated bytes; saved default API run 233f6e78-d78d-431d-a3ea-7cb06ecff993 has six trials and exact reload equality. Those values describe local observations, not latency or guaranteed constants.

**7. Executed verification:** **240 tests passed** with `uv run pytest --integration -q`: 153 unit and 87 real PostgreSQL/API integration tests. M6 adds 22 unit and 14 integration cases. Real checks cover fresh baselines despite altered historical costs, multiple-query weighting, actual singleton/combined interactions, missing/inaccessible extension functions, null storage, session isolation/concurrency, rollback-persistent state, real timeout cleanup, cache copies/settings changes, expired budget invalidation, test-backend termination/discard, saved-DDL tampering rejection, new existing indexes, empty candidates, reload equality and unchanged physical index counts. Zero/nonfinite/overflow arithmetic uses labeled unit inputs. Initial test assumptions about in-transaction permission caching and a supposedly zero-cost PostgreSQL plan were corrected from real observations. Permission probes restore grants; schemas/metadata are fixture-owned and removed. Migration 0006 upgrade → downgrade to 0005 → upgrade and no-drift checks passed on the separate disposable metadata database. Main retained metadata was only upgraded. No runtime benchmark/frontend/E2E tests apply yet. Publication checks are recorded below after execution.

**Publication checks:** locked dependency synchronization, Ruff lint/format, documentation file links, Git whitespace and Alembic schema comparison passed. Default pytest reported 153 passed/87 intentionally skipped; the separate full run above passed all 240. The saved manual evaluation was reloaded and its recorded status, six trials, cleanup and numerical estimates reconfirmed. Inspection of 31 staged files found no local credential bytes, token/private-key patterns or generated secret files.

**8. GitHub update:** implementation and verification complete locally; commit/push/remote-SHA verification pending. Intended message: `Evaluate candidate indexes with HypoPG`, branch main. The exact implementation SHA will be recorded after successful publication.

**9. Current status:** M0–M5 published; M6 implemented and verified, pending publication. Workloads now reach real estimated plans, bounded candidates and saved hypothetical comparisons. Cost/storage estimates are explicitly unmeasured; unknown sizes and per-query regressions remain visible. Storage-budget selection, heuristic write penalties, benchmark runner, dashboard and reports remain pending. Trusted local PostgreSQL 18/HypoPG 1.4 and the narrow SQL/catalog policy remain required. Physical/statistics changes are not completely frozen by repeatable read.

**10. Next:** finish M6 publication, then pause for user review. Only after the user continues will M7 implement frequency-weighted marginal-benefit selection under a storage budget. No M7 application work has begun.
