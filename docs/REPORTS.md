# Saved reports and history

Milestone 11 adds durable report identities, a versioned format, JSON/Markdown exports and unified filtered history. Report creation reads saved metadata only: it does not reconnect to the monitored target, rerun optimization or start a physical benchmark.

## Start and use

From the repository root:

```powershell
uv sync --locked
uv run alembic upgrade head
uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000
```

Migration **0010** adds `saved_report`; readiness expects 0010. Stop an older backend with Ctrl+C in its terminal before starting the command above. Keep Docker/WSL running. Start the frontend separately using [FRONTEND.md](FRONTEND.md), then open http://127.0.0.1:5173/reports.

1. Choose a saved recommendation, enter a report title, and review the SQL inclusion checkboxes.
2. Optionally select up to five terminal benchmark jobs belonging to that recommendation. Active jobs are unavailable until finished/cancelled.
3. Choose **Save versioned report**. The returned report gets a new UUID and the format version `indexpilot-report-v1`.
4. Download JSON or Markdown, inspect candidate/query evidence, or compare with another saved report. A new report does not overwrite an earlier one.
5. In History, filter by record type, literal title/UUID text and local time. Apply/clear controls reset pagination. Links reopen the original resource IDs.

History supports workloads, plans, candidate batches, optimizer runs, recommendations, benchmarks and reports. Dates are converted from browser-local time to offset-bearing API timestamps. Counts and pages share a repeatable-read metadata snapshot. Sort ties use kind/UUID, so equal timestamps do not cause records to repeat between unchanged pages. Ordinary offset pagination is not a cursor snapshot across later inserts; changing source history between requests can shift page boundaries.

## Privacy policy and scope

`include_original_sql` defaults to **true**. It includes original query text and selected deployment SQL. Original SQL may already contain literal values; this option does not promise literal redaction.

`include_representative_sql` defaults to **false**. An explicit opt-in includes representative SQL with bound values. It requires original SQL inclusion. Typed parameter maps and raw EXPLAIN plans are never embedded in this report format. If representative values are omitted, parameterized original SQL is not necessarily executable by itself. The source recommendation remains available locally with its complete evidence.

Reports project known provenance/worker fields rather than copying arbitrary connection settings, credentials, DSNs, hosts, raw plans or future private fields. Query/index explanations, estimated costs, sizes, settings, captured statistics timestamps, candidate decisions/search trials and explicit missing-evidence sections remain available. The policy is part of the frozen document and shown by the UI. SQL and titles are displayed as React text. Markdown prose escapes HTML/Markdown metacharacters; SQL uses a fence longer than any backtick run in its content. There is no HTML report execution/rendering endpoint.

Filenames derive only from parsed report UUIDs: `indexpilot-report-<UUID>.json` or `.md`. User titles do not enter file paths or response headers. Downloads use `nosniff`, attachment disposition and no-store caching. The API has no report update/delete endpoint. Normal metadata administration is outside that API immutability boundary.

## What is frozen

One repeatable-read transaction loads the recommendation, optimization, generated candidates and explicitly selected terminal jobs, builds a bounded document and inserts the report. Indexed header columns support listing; JSONB stores the versioned historical artifact. Report reads/downloads use that document, not current source joins. Later source edits, target changes or job status/result changes cannot silently rewrite a saved report. Reports do not include a dump of individual benchmark transaction samples; stored measurement IDs link back to the existing sample API.

Each benchmark section retains its job identity, state, cleanup flag, dataset/settings, runtime conditions, phase/repetition metrics and regression comparisons. Completed comparisons require a completed job, verified cleanup, comparisons and measurements. Failed/cancelled jobs may contribute explicitly partial evidence; their comparisons are omitted. Active jobs return `report_benchmark_active` with a wait/cancel instruction. Selecting another recommendation's job returns `report_benchmark_mismatch`. No selected benchmark means missing measured evidence, not zero latency.

Index estimated bytes, actual benchmark main-fork bytes and milliseconds keep distinct units. Equal candidate-batch IDs do not establish identical planner statistics or runtime conditions. The comparison view shows saved values and source differences without manufacturing a cross-workload performance percentage. Costs are relative planner estimates; measured latency is a defined pgbench transaction. Cold-cache behavior, WAL and statistical significance remain unmeasured.

## API

| Endpoint | Behavior |
| --- | --- |
| `POST /api/v1/reports` | Create a new frozen report, 201. |
| `GET /api/v1/reports?recommendation_id=&q=&limit=20&offset=0` | Filter by recommendation/title; returns `items`, `total`, `limit`, `offset`. |
| `GET /api/v1/reports/{id}` | Retrieve the stored document by UUID. |
| `GET /api/v1/reports/{id}/download.json` | Download the stored versioned document as JSON. |
| `GET /api/v1/reports/{id}/download.md` | Render the same stored version as Markdown. |
| `GET /api/v1/history?kind=&q=&created_from=&created_to=&limit=20&offset=0` | Unified filtered history with exact matching count and resource types. |

`q` is literal substring matching, not SQL or a wildcard expression: `%` and `_` are escaped. Limits are 1-100; offsets 0-1,000,000; query/title inputs at most 120 characters. History date bounds are inclusive ISO timestamps with offsets; reversed ranges are rejected. Report bodies reject unknown fields, coerced booleans, duplicate benchmark IDs, control characters and inconsistent inclusion policies. Documents are bounded to 4 MiB. Missing reports return a safe 404 with an actionable message/request ID.

Example POST body (replace the UUID with a saved recommendation):

```json
{
  "recommendation_id": "00000000-0000-0000-0000-000000000001",
  "title": "Saved budget decision",
  "benchmark_ids": [],
  "include_original_sql": true,
  "include_representative_sql": false
}
```

The example ID is a placeholder, not a claim of stored evidence. [Actual sample JSON](../sample/reports/local-report.json) and [Markdown](../sample/reports/local-report.md) preserve an export from the published two-query M9 benchmark. See [sample notes](../sample/reports/README.md).

## Executed verification

The M11 full backend run passed **418 tests** (286 unit, 132 actual PostgreSQL/API). New cases verify report equality with stored source costs/options/trials, parameter omission/opt-in, safe Markdown/headers/UUIDs, missing/active/mismatched/cancelled benchmarks, actual pgbench measurement matching, later source changes and a fresh application instance, 105-record pagination with timestamp ties, literal searches and invalid dates. Six integration and 22 unit cases were added.

Frontend checks passed **29 component tests** and **five real browser scenarios**. Browser tests create both unmeasured and measured reports, download Markdown, reload by permanent identity, compare saved reports, filter history and reopen the result. All nine views pass desktop/mobile axe, keyboard and overflow checks. A final read-only audit verifies the report explanation panel. The migration upgrade/downgrade/re-upgrade/drift check ran on the separate disposable metadata database at port 55433; retained main history was only upgraded.

Run tests from the root with `uv run pytest --integration -q`. Frontend commands from `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run format:check`, then `npm run test:e2e`. Run the backend database suite and browser suite **sequentially** because both use the shared local benchmark queue. See [FRONTEND.md](FRONTEND.md) for required services/ports. Named browser evidence remains local; tests stop their owned servers and preserve user development servers.
