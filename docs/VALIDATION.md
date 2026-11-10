# Reproduce the validation

M12 checks the engine and browser against actual PostgreSQL/HypoPG. Unit fixtures alone do not establish database behavior. Run database tests and browser tests sequentially; their worker queue is shared.

## Setup

Install Git, uv, Docker/Compose and the Node version in `frontend/.node-version`. On Windows, keep WSL running and use `wsl --exec docker compose` for Docker commands. Dot-source `scripts/use_node.ps1` for the optional checksum-verified Windows Node runtime. Python and npm installs use their lockfiles:

```powershell
uv sync --locked
uv run python scripts/init_local.py
docker compose up -d --build --wait
uv run python scripts/generate_demo.py
uv run python scripts/generate_demo.py --target bench
uv run alembic upgrade head
cd frontend
npm ci
npm run install:browser
cd ..
```

Existing generated data is never reset by these setup commands: use a fresh checkout/volume for clean validation. Keep original credentials with existing volumes. Details and explicit sample-reset limits are in [DEVELOPMENT.md](DEVELOPMENT.md).

For a second checkout on the same host, use a distinct port and project **in that checkout's ignored `.env`**, for example:

```dotenv
INDEXPILOT_DB_PORT=55434
INDEXPILOT_COMPOSE_PROJECT=indexpilot-validation
```

Start its cluster with `docker compose -p indexpilot-validation up -d --build --wait`. Subsequent Docker commands must use that same `-p` name. Python, the API and pgbench read the same trusted setting. The API cannot select a project, and the existing database/role/marker/transport-nonce checks still apply. Do not share secrets or `.venv` between checkouts/platforms. A matching namespace/port lets the second checkout use a new volume without stopping the development database or servers.

## Checks

From the repository root with uv, Node and npm available:

```powershell
# No database needed: lint/format, backend unit tests, frontend checks/build
uv run python scripts/check.py --output artifacts/checks-unit.json

# Explicit real PG/API suite, then real browser workflow (never parallel)
uv run python scripts/check.py --integration --browser --output artifacts/checks.json
```

The command stops at the first failure and writes executed checks/exit codes/durations, not fabricated pass counts. It does not provision/reset data or start a hidden benchmark worker. The browser suite explicitly confirms its own job and runs the real guarded worker, saving the resulting measurements and reports. Stop other workers and leave that validation queue idle first. The sequence covers every frontend view, both budget outcomes, SQL/files/typed parameters, report exports/history, measured regressions, and a saved report read through two separately started/terminated API processes.

Playwright owns ports 8010/5174 and separate ephemeral restart-check ports. It refuses to reuse unrelated servers and stops its own processes. Default screenshots go to ignored `artifacts/screenshots`; set `INDEXPILOT_SCREENSHOT_DIR` explicitly to capture elsewhere. Trace/report data stays under ignored frontend test output. Named `e2e-*` metadata remains reviewable on local validation volumes. Public source data and indexes remain protected; only test-owned benchmark schemas are physically modified and cleaned.

For migration reversal, use only a **disposable metadata database**, before retaining useful history:

```powershell
uv run alembic upgrade head
uv run alembic downgrade 0009
uv run alembic upgrade head
uv run alembic check
```

Downgrading removes saved-report tables/data. Never use this reversal sequence on the development metadata database containing reports you want to retain.

## CI

The pinned-actions workflow has an independent unit/frontend job and a fresh Linux PostgreSQL/HypoPG/browser job. The integration job creates credentials locally, builds the pinned database image, generates both datasets, reverses/reapplies migration 0010 before test history exists, and runs the same sequential checker. It installs Chromium/system dependencies, retains only explicit check/browser artifacts for seven days, and removes its runner-owned `indexpilot-ci` cluster/volume on completion. No secret directory, `.env`, database dump, raw pgbench scratch directory or whole checkout is uploaded.

An Actions badge or configured workflow is not proof that a run passed. Actual commit/run links and clean-checkout outcomes are recorded in [PROGRESS.md](PROGRESS.md) after execution. Engineering findings and remaining limitations are recorded in the final evaluation.

Linux file-backed secrets keep host UID/mode. The image's root entrypoint makes private postgres-owned tmpfs copies before initialization, without relaxing host permissions. Initialization checks file reads, and the health check waits for final TCP startup. This correction was prompted by actual fresh Linux CI, not inferred from a cached Windows build. Keep matching secret files with existing database volumes; the change does not rotate stored role passwords.
