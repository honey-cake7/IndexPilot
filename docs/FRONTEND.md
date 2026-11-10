# Local dashboard

Milestone 10 connects nine React views to the existing FastAPI/PostgreSQL engine. The source lives in `frontend/`. This is a local application with no hosted deployment or remote database credential form.

## Start it

First complete the PostgreSQL/secret/sample setup in [DEVELOPMENT.md](DEVELOPMENT.md). Keep WSL running while Docker is in use. From the repository root, start the backend in one terminal:

```powershell
uv sync --locked
uv run alembic upgrade head
uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell terminal, also starting at the repository root:

```powershell
. .\scripts\use_node.ps1
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Port 8000 provides the API and `/docs`; it does not serve the dashboard at `/`. Vite proxies `/api`, `/health`, `/docs` and `/openapi.json` to the backend on loopback. Keep both terminals running. Stop a server with Ctrl+C in its terminal.

`use_node.ps1` pins Node 26.13.0/npm 11.20.0 on Windows x64. When needed it downloads the official archive, verifies its SHA-256 against the official release checksum and extracts under ignored `.tools/`. It changes PATH only in the current PowerShell process. Dot-source it again in a new terminal. On other systems, install the version in `frontend/.node-version` with your usual Node manager; the PowerShell helper is optional and Windows x64 specific.

To change the API port, set server configuration before starting Vite:

```powershell
$env:INDEXPILOT_API_TARGET = 'http://127.0.0.1:8010'
npm run dev
```

Restart Vite after changing it. This variable configures its proxy; it is not a browser credential or an arbitrary user-supplied target. `npm run build` creates `frontend/dist`; `npm run preview` serves it on loopback port 4173 with the same API proxy for local verification. These servers are not an authenticated public hosting solution.

## Views and evidence

| View | Working behavior |
| --- | --- |
| Overview | Full metadata counts from one SQL statement; recent recommendations; actual measurements from the latest completed/clean job in the 20 most recent jobs. |
| Connections | Live target capabilities, privilege boundaries, extension availability, validation and explicit pg_stat_statements workload collection. |
| SQL Analyzer | Query rows with individual frequencies/typed parameter JSON; pasted scripts or UTF-8 `.sql` upload. Saves the workload, captures each resolved scenario, generates candidates, opens Budget Simulator. |
| Query Explorer | Paginated workload/plan lists, paginated workload patterns, stored parameters, original/canonical SQL, recursive plan trees, settings and raw EXPLAIN evidence. |
| Recommendations | Saved explanations, selected/rejected-empty outcomes, query before/after plans, warnings, links to source optimization and non-executing SQL downloads. |
| Budget Simulator | Saved candidate batches; budget slider/numeric input; bounded search, regression and heuristic write-penalty settings; real HypoPG rerun creates a new saved optimizer ID. |
| Benchmark Comparison | Explicit unchecked physical-benchmark confirmation, bounded settings, queue/cancel/status polling, measured read/write phase charts, storage and full conditions. |
| History | Unified paginated history including reports, filtered by type, literal title/UUID text and local date bounds, with links to original evidence. |
| Reports | Creates immutable versioned reports with explicit SQL inclusion choices and selected terminal benchmark evidence; downloads backend JSON/Markdown and compares saved decisions. See [REPORTS.md](REPORTS.md). |

The decorative bar illustration in the homepage introduction is not a result chart. Every numerical result comes from the API. A missing cost/size/measurement remains **Unknown** or empty. The recommendation's planner estimate is never relabeled as measured latency. Chart tables provide the same values without depending on hover or color.

Try the editable sample query with `user_id`, assign a frequency and choose **Analyze & generate candidates**. Choose a budget and **Run optimization**, then **Save recommendation**. Changing an input leaves the saved result labeled with its old budget until another run completes; saving a recommendation is disabled while settings differ. Zero budget is valid and can produce an empty selection. Old optimizer records remain unchanged.

If an input is rejected after the workload was saved, its link remains available. Unresolved parameters or additional pattern pages are identified instead of silently excluding part of the workload. Supported parameter types and SQL limitations are described in [WORKLOADS.md](WORKLOADS.md) and [PLAN_ANALYSIS.md](PLAN_ANALYSIS.md).

## Physical benchmarks

Queueing requires checking the confirmation for the fixed disposable `indexpilot_bench` database. A 202 response means queued, not measured or complete. Start the explicit worker in another terminal from the repository root:

```powershell
uv run python scripts/run_benchmarks.py --serve
```

No worker is started by Vite or FastAPI. The UI polls active jobs; failed/cancelled/partial results and cleanup status remain visible. See [BENCHMARKING.md](BENCHMARKING.md) for dataset/template bounds, owned schemas and transport checks. Measured charts show the arithmetic mean of repetition means for the selected phase, plus each repetition's range and count. They do not pool per-query means, infer p95 from an aggregate, or establish significance. A single repetition is a workflow check, not a stable performance conclusion.

## Contracts and verification

`src/api/schema.d.ts` is generated from the current backend OpenAPI document, without a database connection:

```powershell
# From frontend/, with uv and Node available
npm run generate:api
npm run lint
npm run typecheck
npm test
npm run build
npm run format:check
npm audit
```

The typed `openapi-fetch` client preserves endpoint/request/response contracts. API failures retain the safe message/code/request ID. React escapes SQL and evidence as text. SQL/parameters are not stored in browser localStorage. Downloads may contain representative SQL/values, so the UI explains what they contain. Request mutations have no automatic retries. Terminal benchmark jobs stop polling.

The minimatch override to 11.0.1 addresses GHSA-g3hv-75wg-m249 in development lint dependencies. It is pinned in the lockfile and exercised by the actual lint/build/test checks; no forced or legacy-peer installation is required. TypeScript stays at 5.9.3 because the OpenAPI generator and typescript-eslint peer ranges do not support TypeScript 7.

For real browser tests, provision the demo/bench databases and metadata migration first, stop other benchmark workers, and leave the queue idle. Then:

```powershell
npm run install:browser
npm run test:e2e
```

Playwright owns temporary backend port **8010** and frontend **5174**, uses the repository root for backend secret/config resolution and refuses to reuse an unrelated process on either port. It stops those owned servers after testing. A user's development server on port 8000 is not stopped. The suite submits real SQL/files/parameters, checks persisted budget results and exports, queues/cancels a confirmed job, explicitly runs one real three-arm benchmark, checks measured chart values against stored measurements, and audits all nine views at 1440px/390px with axe plus keyboard/overflow checks. Component-test fixtures are not database evidence.

Browser tests retain clearly named `e2e-*` workload/history records as reviewable local evidence, along with completed/cancelled benchmark metadata. Each successful physical job removes its private benchmark schema and preserves public sample tables. The helper refuses execution if another queued/running/unclean job exists; run this development suite only on an otherwise idle local queue. A failed run can leave its own queued job; cancel that specific job in the dashboard before retrying. Traces/logs/download artifacts stay ignored.

GitHub Actions runs an independent Ruff/unit/generated-contract/frontend job and a fresh pinned PostgreSQL/HypoPG/browser job. The integration job runs the same sequential checker and actual process-restart scenario. Unit results alone do not establish database integration. See [VALIDATION.md](VALIDATION.md) and [PROGRESS.md](PROGRESS.md) for commands and executed run links.

Published actual screenshots are [dashboard](screenshots/dashboard.png), [mobile analyzer](screenshots/analyzer-mobile.png) and [saved reports](screenshots/reports.png). Test captures default to ignored `artifacts/screenshots`; `INDEXPILOT_SCREENSHOT_DIR` explicitly selects another output directory. Counts and timings reflect the saved database at capture, not a product promise.
