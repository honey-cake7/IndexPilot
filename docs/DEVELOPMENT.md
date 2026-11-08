# Development environment

## Requirements

Install Git, uv, and a Linux container engine with Compose v2. `uv sync --locked` obtains Python 3.12 if necessary. The tested host is Windows PowerShell using Docker in WSL Ubuntu; Docker Desktop is not required for this configuration. Linux/macOS Docker setups use the standard `docker compose` commands below.

On the development machine, the following were actually installed/executed:

```powershell
uv python install 3.12
wsl --exec apt-get update -qq
wsl --exec apt-get install -y docker.io docker-compose-v2 postgresql-client-18
wsl --exec docker version
wsl --exec docker compose version
```

The apt commands assume the available WSL user is root. Other setups need their normal administrator installation procedure. These are system setup commands, not project dependencies. The PostgreSQL client package on this Ubuntu release does not include pgbench; the project container does.

WSL systemd services alone may not keep the distribution running. Keep a WSL terminal open during development. During automated verification a foreground `wsl --exec tail -f /dev/null` process kept WSL alive. If WSL exits, restart it and run the Compose startup command again. Do not mistake a stopped container for an application bug.

## Start from a clean checkout

From the repository root:

```powershell
uv sync --locked
uv run python scripts/init_local.py
docker compose up -d --build --wait
uv run python scripts/generate_demo.py
uv run python scripts/generate_demo.py --target bench
uv run python scripts/verify_environment.py
uv run alembic upgrade head
```

On this Windows setup use `wsl --exec docker compose up -d --build --wait` for the Docker command. WSL translates the current Windows working directory. All `uv` commands run in PowerShell. Do not share the Windows `.venv` with a Linux Python interpreter.

The image pins PostgreSQL 18.6 by multi-platform digest and builds HypoPG 1.4.3 from its pinned source commit with checksum verification. Build compilers stay in a separate image stage. PostgreSQL 18 uses the volume mount `/var/lib/postgresql`, following the [official image guidance](https://hub.docker.com/_/postgres). The first initialization creates three databases and separate roles, enables pg_stat_statements and installs HypoPG in demo/benchmark databases.

Expected generator counts for **each** demo/benchmark database: 1,000 users, 500 products, 10,000 orders, 20,000 items and 10,000 payments. The metadata database has no e-commerce tables. Environment inspection should report PostgreSQL 18.6, pg_stat_statements 1.12, HypoPG 1.4.3 and analyzer read-only default `on`. Baseline `orders.user_id` planning currently shows a sequential scan; that is an observation, not a recommendation by itself.

## Configuration and credentials

`scripts/init_local.py` generates `.env` and five unique password files in `.secrets/`, preserving existing files. POSIX files use restrictive creation modes; on Windows they inherit the current user's filesystem ACLs. Compose mounts local secret files; the Python helper reads them directly. No password is passed on command lines or returned in environment-inspection output.

| Variable | Default | Purpose |
| --- | --- | --- |
| INDEXPILOT_DB_HOST | 127.0.0.1 | Local PostgreSQL host |
| INDEXPILOT_DB_PORT | 55432 | Host port, also read by Compose |
| INDEXPILOT_SECRET_DIR | .secrets | Python credential-file directory; Compose uses the project `.secrets` directory |

Use matching port configuration in Compose and Python. If a port is occupied, edit ignored `.env` before startup. Never use `docker compose config` output containing interpolated secrets in public reports; this project verifies its syntax with `docker compose config --quiet`.

Roles: metadata owner for future migrations; demo owner only for sample generation; analyzer with SELECT but no INSERT/UPDATE/DELETE, schema CREATE or TEMP; benchmark owner only for the disposable benchmark database. Analyzer has `pg_read_all_stats` to read normalized statement text; this role exposes cluster-wide statistics, so this initial cluster is dedicated to IndexPilot. Production privilege design must not blindly copy this local grant.

## Data generation and reset

Generation verifies database name, current role and a provisioned database comment before touching approved sample tables. It uses fixed seed 42 and time anchor 2026-01-01 UTC. Each order has two items; its total is derived from item quantities/prices; its payment uses that total. A hash-based distribution concentrates orders among some users. All writes and ANALYZE are transactional, guarded by an advisory lock. Reset does not use CASCADE.

Rerunning without `--reset` refuses existing data. For an intentional replacement of **only local generated sample data**:

```powershell
uv run python scripts/generate_demo.py --target bench --orders 100000 --seed 42 --reset
uv run python scripts/generate_demo.py --target bench --orders 10000 --seed 42 --reset
```

Both sizes above were executed successfully. The configurable range is 100–1,000,000 orders, but the million-order case has not been tested. Generation is subject to a 30-second statement timeout and local resources. ANALYZE samples and physical layout are not guaranteed bit-identical, even when generated row values are identical.

## Tests and checks

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run pytest --integration -q
docker compose config --quiet
docker compose exec -T postgres pgbench --version
```

The default pytest command intentionally skips database tests. Use `--integration` for actual PostgreSQL verification; it must fail rather than silently skip when the server is unavailable. The integration suite replaces the marked benchmark sample data and restores the default 10,000-order dataset afterward. It never resets the demo/metadata database. At M1, 15 tests passed, including the real database tests, against both the main environment and a separate newly initialized container volume. No throughput/latency benchmark has run.

To stop without deleting data: `docker compose stop`. Use `docker compose start --wait` or `docker compose up -d --wait` to resume. Keep the secret files with the existing database volume: changing a file does not change the stored PostgreSQL role password. Initializer changes apply only to a new volume; preserve useful data and apply deliberate migrations/grants to existing environments.

## Backend (M2)

```powershell
uv run alembic upgrade head
uv run alembic check
uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. GET `/health/live` works without a database; GET `/health/ready` requires migrated metadata and the demo target. GET `/api/v1/connections/demo` and POST `/api/v1/connections/validate` with `{"target":"demo"}` report real capabilities and privileges. Arbitrary connection parameters are rejected. PostgreSQL setup happens outside the API. Requests get a generated X-Request-ID; errors use a consistent envelope without echoing input or raw driver exceptions.

The target timeout defaults to 5 seconds, lock timeout to 1 second, and connection timeout to 5 seconds. Set `INDEXPILOT_STATEMENT_TIMEOUT_MS`, `INDEXPILOT_LOCK_TIMEOUT_MS` and `INDEXPILOT_CONNECT_TIMEOUT` within validated bounds. Data-generation connections retain a separate 30-second statement limit. Metadata uses SQLAlchemy with hidden SQL parameters; the target uses fresh psycopg connections and read-only transactions. Neither migration nor database connection happens on ordinary module import.

Capability inspection probes pg_stat_statements directly rather than requiring settings-reader privileges. A null `configured` value means the current role cannot verify configuration; it is not a fabricated success. Startup connection failures are sanitized and may not reliably distinguish authentication from networking when libpq supplies no SQLSTATE.

M2 executed 25 tests successfully, including actual API/DB checks and timeout enforcement. Initial metadata upgrade → downgrade → upgrade and Alembic schema-drift verification were run on a second disposable metadata database. The API is loopback-only by documented startup convention and has no multi-user authentication; do not expose it publicly.

## Workloads (M3)

Run `uv sync --locked` and `uv run alembic upgrade head` to install the parser/multipart dependency and migrate metadata to 0002. Restart the backend after updating. The readiness endpoint now expects revision 0002.

Use `/docs` to submit `sample/workload.json` through `/api/v1/workloads/manual`, paste SQL through `/api/v1/workloads/sql`, or upload `sample/workload.sql` through `/api/v1/workloads/upload`. None of these operations execute the submitted SQL. The complete contract and limitations are in [WORKLOADS.md](WORKLOADS.md).

For two explicit periodic observations:

```powershell
uv run python scripts/collect_workload.py --samples 2 --interval-seconds 30
```

The CLI prints saved workload/snapshot IDs and the number of usable deltas; the first snapshot needs a baseline. No background collector is installed. To append, provide `--workload-id` with the printed workload UUID. Parameter values for normalized collected queries are supplied through the scenario endpoint.

`uv run pytest --integration -q` exercises real workload API persistence and controlled read-only probes. Its targeted reset test clears only its own probe statement's statistics. A permission-failure test briefly revokes the public statistics-view grant and restores it in a finally block; run this development suite serially on the dedicated local cluster. Tests clean up only their uniquely named metadata workloads. They do not reset all PostgreSQL statistics. Unit tests cover global reset, server restart and eviction detection without restarting or globally resetting the live cluster.

## Catalogs and estimated plans (M4)

Run `uv run alembic upgrade head` to apply migration 0003 and restart the backend. Readiness now expects 0003. GET `/api/v1/schema` and `/api/v1/schema/table?table_name=orders` inspect real catalogs. POST `/api/v1/plans` accepts the same SQL/frequency/parameters shape as one manual QueryInput. POST `/api/v1/query-scenarios/{id}/plan` analyzes a saved representative. GET `/api/v1/plans/{id}` reloads the saved evidence.

See [PLAN_ANALYSIS.md](PLAN_ANALYSIS.md) for an executable PowerShell request, schema configuration, safety limits and response semantics. There is no ANALYZE switch, arbitrary target or index-creation endpoint. The full M4 suite passed 166 tests; fixture indexes exist only on isolated test-owned tables and are removed with their unique schemas afterward. Planner switches used within tests exercise node parsing, not performance findings.

## Candidate generation (M5)

Run `uv sync --locked`, `uv run alembic upgrade head` and restart the backend. Metadata now expects revision 0005: migration 0004 adds candidate batches/decisions; 0005 normalizes evidence while preserving saved data. The full migrations were reversed/reapplied on the disposable metadata database, and a populated evidence round trip preserved the saved batch exactly.

POST `/api/v1/candidates` with `{ "plan_ids": ["<saved-plan-UUID>"], "max_columns": 3, "max_candidates": 32 }`. GET `/api/v1/candidates/{id}` reloads decisions; GET `/api/v1/candidates` lists batches. [CANDIDATES.md](CANDIDATES.md) contains a complete executable request and the duplicate/overlap rules. Generation does not require HypoPG or create real indexes. Benefits and size fields are null until evaluation exists.

M5 verification passed 204 tests (131 unit, 73 PostgreSQL/API integration). Additional tests validate generated SQL with session-local HypoPG and reset it; they do not measure benefit. Fixture index creation and schema changes affect only isolated test-owned tables. Pytest importlib mode keeps matching unit/integration test module names independent.
