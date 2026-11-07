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

**8. GitHub update:** implementation subject `Add workload collection using pg_stat_statements`, branch `main`. Publication pending at preparation of this record; actual SHA/link and remote verification will be added after pushing. No completed publication is claimed before the push succeeds.

**9. Current status:** M0–M3 implemented and verified locally. Workload ingestion and collection are usable; no catalog-based query resolution, execution-plan engine, candidate generator, optimizer, index benchmark, dashboard or report feature is implemented. Saved SQL/parameter values are sensitive local metadata. The initial target is the configured PostgreSQL 18 demo with pg_stat_statements 1.12; unsupported queries are skipped/rejected explicitly.

**10. Next:** stop for user review. M4 will add schema/catalog resolution and recursive EXPLAIN JSON analysis only after the user explicitly continues. No M4 application work has begun.
