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

**GitHub record:** subject `Set up PostgreSQL development environment`, branch `main`; the containing commit is discoverable with `git log --format="%H %s" -- compose.yaml`. Exact SHA/link and push verification are reported after the commit is created, and recorded in the next update.

**Status / next:** M1 verified; API, workload ingestion, SQL safety engine, candidate generator, optimizer, benchmarking UI and reports are not implemented. M2 adds typed backend configuration, capability reporting, initial metadata migration, structured logging and safe API errors.
