# Technical roadmap

## Scope and development rules

This document defines dependency milestones, not a calendar. The essential path is M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10 → M11 → M12. Engine algorithms must work independently of HTTP routes before dashboard development starts.

Essential functionality includes modules A–J, the nine dashboard views, three-way isolated benchmarks, history, reports, CI and the complete demonstration. Advanced features are explicitly optional: additional index types, partial/expression/covering indexes, automatic parameter sampling, broader SQL grammar, online collection scheduling and exhaustive optimization experiments. They cannot substitute for essential acceptance criteria.

Verified status: **M0–M11 completed, verified and published (records in PROGRESS); M12 planned.** Development pauses after each milestone for user review.

Each milestone must have cohesive reviewed changes, executed relevant checks, updated README and progress, a natural commit message, a push and a remote-SHA verification. Record actual test counts and skipped/blocked checks. No milestone is complete merely because its files exist. Never use fixtures or mocks as proof of PostgreSQL behavior. Commit links for the containing commit are resolved through Git history rather than self-referential hashes inside that commit.

The directory/file names below are the intended implementation layout. They may be refined with a decision record; they do not indicate existing code.

## M0 — Repository inspection and technical roadmap

- **Objective:** establish the real starting state and a reviewable engineering plan before application code.
- **DBMS concepts:** separation of target and metadata databases; planner estimates versus measurements; index read/write trade-offs; trust boundaries.
- **Files:** `.gitignore`, `README.md`, `docs/{ROADMAP,PROGRESS,ARCHITECTURE,DECISIONS,DATABASE_DESIGN,OPTIMIZATION_ALGORITHM,BENCHMARKING,LEARNING_NOTES}.md`.
- **Functionality:** preserve existing work; identify branch, credentials, runtime tools, architecture, essential/advanced scope and evidence rules.
- **Prerequisites:** read access; authenticated developer identity and write access for publication.
- **Verification:** inspect refs/history/configuration and permissions; review document links, milestone coverage, secret exclusions and Git diff; perform actual push and compare remote head.
- **Acceptance:** complete roadmap presented to the user and published; useful design documents; no application feature claims; actual commit link and environment limitations reported.
- **GitHub deliverable:** `Document IndexPilot architecture and development roadmap` on main, or a feature PR if rules require it.

## M1 — PostgreSQL environment and reproducible sample database

- **Objective:** provide isolated metadata, demo and benchmark databases with deterministic e-commerce data.
- **DBMS concepts:** roles/privileges, primary and foreign keys, normalization, catalog statistics, ANALYZE and extension loading.
- **Files:** `compose.yaml`, `infra/postgres/{Dockerfile,init.sh}`, `scripts/{generate_demo,verify_environment}.py`, `sample/{schema,workload}.sql`, `.env.example`, `pyproject.toml`, `uv.lock`, `tests/integration/test_environment.py`, setup docs.
- **Functionality:** PostgreSQL 18 plus versioned HypoPG and preloaded pg_stat_statements; separate least-privilege analyzer and disposable benchmark owner; generated local secrets; bounded small/large datasets; fixed seed and timestamp anchor; persistent volumes; explicit safe cleanup.
- **Prerequisites:** M0 publication; working container engine or documented native PostgreSQL fallback; dependency installer.
- **Verification:** build and boot; extension/version checks; connect to three databases; reject analyzer writes; assert row counts, referential integrity and deterministic content after repeated isolated generation; verify parameter changes alter dataset size; run sample EXPLAIN; inspect grants; prove benchmark isolation.
- **Acceptance:** documented clean startup produces known data and usable extensions; metadata has no demo rows; target analysis account cannot mutate data/schema; generation rejects unrelated databases; actual environment checks pass. If container startup cannot be tested, explicitly leave that criterion pending.
- **GitHub deliverable:** `Set up PostgreSQL development environment`, lockfile, sample SQL and real integration evidence.

## M2 — Backend foundation and database connectivity (A)

- **Objective:** establish configuration, safe connections and capability reporting without optimization code in routes.
- **DBMS concepts:** sessions, transactions, read-only privileges, statement/lock/connect timeouts, extension availability versus installation.
- **Files:** `backend/indexpilot/{main,config,errors,logging}.py`, `db/{connections,capabilities}.py`, `api/{health,connections}.py`, `models/connections.py`, metadata session setup, initial Alembic migration, `tests/{unit,integration,api}/`.
- **Functionality:** typed FastAPI API; `/health/live` and `/health/ready`; allowlisted configured target references; version, extension, preload and privilege checks; safe diagnostics; metadata migration; structured logs with request IDs and redaction.
- **Prerequisites:** verified M1 databases and roles; install locked Python dependencies.
- **Verification:** valid/invalid credentials, unreachable host, wrong database, missing extension, insufficient grants, migration up/down on disposable metadata; assert responses/logs omit secrets; API validation and readiness failures.
- **Acceptance:** live target capability response and consistent error envelope; no password persistence; target and metadata connection pools separated; timeout behavior verified; route behavior tested against real PostgreSQL.
- **GitHub deliverable:** `Add backend configuration and database capability checks` plus OpenAPI usage and tests.

## M3 — SQL workload input and collection (B)

- **Objective:** ingest explicit query frequencies and correctly collect cumulative query statistics.
- **DBMS concepts:** query patterns, normalized SQL, cumulative counters, snapshot intervals, counter reset and parameter selectivity.
- **Files:** `workloads/{models,manual,collector,deltas,parameters}.py`, minimal `sql/validation.py`, `api/workloads.py`, query/snapshot Alembic migration, SQL/JSON input examples and tests.
- **Functionality:** paste/upload SQL; positive finite bounded frequencies; early AST safety validation; preserve representative SQL separately from normalized patterns; pg_stat_statements snapshots including database/user/queryid/top-level identity, calls, execution time, rows, buffers, reset/deallocation metadata and collection time. Missing values remain missing. Associate explicit representative parameters; skip planning unresolved placeholders.
- **Prerequisites:** M2 connectivity/persistence and pg_stat_statements; pglast dependency. Minimal AST validation is intentionally required here before more detailed M4 extraction.
- **Verification:** identical/changed counters, zero calls, new/missing entries, global and per-entry reset (where supported), server restart, eviction ambiguity, normalized `$1` binding and multiple parameter examples; real controlled queries between snapshots; reject DDL/DML and malformed files.
- **Acceptance:** intervals use counter differences, mean = delta total time / delta calls; no invented interval percentiles or zero baselines for unobserved history; ambiguous intervals marked unusable; manual inputs round-trip with frequencies.
- **GitHub deliverable:** `Add workload collection using pg_stat_statements` with reset-aware tests and examples.

## M4 — SQL, schema and execution-plan intelligence (C, D)

- **Objective:** connect parsed PostgreSQL syntax to real relations/statistics and recursively explain plans.
- **DBMS concepts:** schema/name resolution, selectivity, row estimates, scan/join/sort trees, relation OIDs and B-Tree access.
- **Files:** `sql/{analysis,resolution,safety}.py`, `schema/{catalogs,models}.py`, `plans/{models,parser,explanations}.py`, `api/{plans,schema}.py`, plan persistence migration and tests.
- **Functionality:** AST aliases and qualified columns; supported equality/range/join/order patterns; catalog tables, types, keys, indexes, sizes, usage, pg_stats; recursive JSON nodes including schema, conditions, costs, rows, width, sort keys and children; sequential-scan explanations. Reject unsupported/ambiguous SQL before planning.
- **Prerequisites:** M3 ingestion and validation, target SELECT/catalog privileges.
- **Verification:** joins, aliases, quoted identifiers, multiple schemas, ambiguous names, nested plan children, missing optional fields, bitmap/nested-loop/hash/merge/sort cases; real EXPLAIN JSON and catalogs; reject data-modifying CTEs, SELECT INTO, locks, functions/custom operators/types outside policy, views and unsupported relation kinds.
- **Acceptance:** plan estimates remain cost units; no ANALYZE or execution of input SELECT during ordinary analysis; safe supported subset enforced; every predicate resolves to a known physical column; unsupported constructs have explicit errors.
- **GitHub deliverable:** `Parse execution plans and inspect PostgreSQL schema` with real plan examples and security limitations.

## M5 — Automatic B-Tree candidate generation (E)

- **Objective:** produce a bounded set of justified, valid indexes from supported workload patterns.
- **DBMS concepts:** leftmost equality prefix, range bounds, ordered scans, composite column order and index duplication.
- **Files:** `candidates/{models,generator,deduplication,sql}.py`, `api/candidates.py`, candidate migration and unit/integration tests.
- **Functionality:** equality/range/join/order candidates; equality before range where justified; bounded alternatives for common conjunctions; correct direction/null-order handling; deterministic identifiers and safely quoted schema/table/column names; recorded source query/reason; default maximum three key columns and 32 candidates per analysis.
- **Prerequisites:** M4 resolved schema and query features; valid/ready existing-index catalog metadata.
- **Verification:** real CREATE INDEX syntax through HypoPG when available or disposable real DDL; equality/range ordering, joins, alias resolution, direction variants, schema duplicates, search bounds; compare exact signatures including predicate, expression, method, collation, opclass and ordering.
- **Acceptance:** no exact usable duplicates; no false equivalence between partial/expression and ordinary indexes; prefix redundancy reported cautiously rather than assumed universally; deterministic bounded output; unsupported types/features skipped with reason.
- **GitHub deliverable:** `Generate schema-aware B-Tree index candidates` and explanatory examples.

## M6 — HypoPG evaluation engine (F)

- **Objective:** obtain real planner estimates for singleton and combined candidate sets safely.
- **DBMS concepts:** session-local hypothetical indexes, estimated storage, optimizer interactions and plan cost units.
- **Files:** `evaluation/{session,hypopg,models,cache}.py`, `api/evaluations.py`, evaluation/plan migrations and real HypoPG tests.
- **Functionality:** collect unmodified baseline; reset/create complete index set in one exclusively held connection; EXPLAIN every representative query; estimate sizes via supported HypoPG functions; compare costs including zero-baseline handling; finally cleanup, and discard failed connections; missing HypoPG returns capability warning.
- **Prerequisites:** M5 candidates; installed/granted HypoPG functions and M4 safety checks.
- **Verification:** baseline versus candidate, several simultaneous indexes, isolated concurrent sessions, cleanup on success/error/timeout, unknown storage, unavailable extension and no hypothetical indexes after reuse; ensure no ANALYZE or physical target DDL.
- **Acceptance:** estimates originate from PostgreSQL; multi-index evaluation is measured as a set, not summed; no state leakage; unknown sizes cannot silently pass a hard budget; costs and bytes have explicit units.
- **GitHub deliverable:** `Evaluate candidate indexes with HypoPG` with actual integration evidence.

## M7 — Workload-aware optimization engine (G)

- **Objective:** implement a transparent greedy search over interacting index sets and a hard storage budget.
- **DBMS concepts:** weighted workload objective, marginal gain, storage constraints, heuristic write penalty and local optima.
- **Files:** `optimizer/{objective,greedy,models,exhaustive}.py`, `api/optimization.py`, optimizer unit tests and integration comparisons; update algorithm document.
- **Functionality:** evaluate weighted root costs; recompute every trial against current selected set; deterministic marginal net gain per byte; bound evaluations; enforce total bytes; report selected/rejected candidates, trial costs, regressions and stop reason; optional exhaustive baseline for ≤10 candidates.
- **Prerequisites:** M6 set evaluator, query frequencies and reliable size estimates.
- **Verification:** unequal frequencies reverse decisions; overlapping benefits, complementary candidates, zero/unknown size and cost, exact budget boundary, invalid/negative/non-finite input, no-benefit stop, stable ties and regression tolerance; real HypoPG budget examples. Hand-computed synthetic costs test algorithms only, not database effectiveness.
- **Acceptance:** every chosen index fits the budget; no additive-benefit assumption; final costs are re-evaluated for selected set; write penalty clearly heuristic; empty solution valid; algorithm has no FastAPI dependency.
- **GitHub deliverable:** `Add storage-aware workload index selection` with traceable trial records and limitations.

## M8 — Recommendation explanations and persistence (I)

- **Objective:** save a complete, reproducible analysis with understandable reasons and uncertainty.
- **DBMS concepts:** normalization, transactional consistency, configuration provenance and index maintenance trade-offs.
- **Files:** `recommendations/{models,explain,service}.py`, `metadata/{models,repositories}.py`, remaining Alembic migrations, `api/recommendations.py`, persistence tests.
- **Functionality:** transactional analysis saves; candidate/set membership; baseline/hypothetical plans and storage; query contribution; regression/unknown-statistics warnings; separate copyable deployment SQL; no automatic target DDL; retain database version, statistics time and algorithm settings.
- **Prerequisites:** M7 optimizer and earlier metadata entities.
- **Verification:** save/reload equivalent results; FK/unique/check constraints; rollback partial saves; no password/secret leakage; explanation references actual plan changes; quoted deployment SQL does not execute.
- **Acceptance:** analyses survive restart; explanations distinguish heuristics/estimates/measurements; selection membership and historical settings are immutable snapshots; per-query attribution does not falsely imply additive individual-index gains.
- **GitHub deliverable:** `Persist explainable recommendation sets` and migrated ER documentation.

## M9 — Isolated benchmarks and regression analysis (H)

- **Objective:** physically validate recommendations without exposing an arbitrary target to index creation or workload execution.
- **DBMS concepts:** warm caches, sampling, latency distributions, TPS, WAL/write amplification, index storage, regression and experimental controls.
- **Files:** `benchmarks/{guard,runner,pgbench,measurements,jobs}.py`, `api/benchmarks.py`, benchmark migrations, `sample/benchmarks/`, benchmark safety/integration tests; results methodology.
- **Functionality:** configured disposable target with server/database/role identity and explicit confirmation; baseline, simple per-query baseline and workload-aware set on identical seeded data; approved candidate IDs only; bounded warmup/repetitions; read and insert/update/delete experiments; real index bytes; job queued/running/completed/failed lifecycle; durable samples and comparisons.
- **Prerequisites:** M8 persisted analyses, pgbench binary and isolated benchmark database from M1.
- **Verification:** refuse demo/metadata/unknown targets, including DSN aliases; enforce isolation and timeouts; protect constraint indexes; restore starting state each arm; parse actual pgbench logs; derive percentiles only from individual transaction samples; test failure transitions and cancellation/cleanup behavior.
- **Acceptance:** reproducible three-arm experiment with actual recorded conditions/results and query regression flags; creation only after explicit benchmark confirmation; physical indexes never created on monitored target; no claim of universal improvement; measurements survive restart.
- **GitHub deliverable:** `Benchmark recommended indexes against baseline` with small checked-in summarized evidence, no database dumps or invented numbers.

## M10 — Frontend dashboard and API integration (J)

- **Objective:** expose the verified engine through nine responsive, accessible views.
- **DBMS concepts:** communicate estimates, workload trade-offs, plan trees and measured regressions accurately.
- **Files:** `frontend/` React/TypeScript/Vite project, lockfile, Tailwind styles, typed API client, components, page tests and Playwright E2E; deployment configuration.
- **Functionality:** Overview, Connections, SQL Analyzer, Query Explorer, Recommendations, Budget Simulator, Benchmark Comparison, History and Reports; file upload/frequency controls; plan tree; actual rerun on budget changes; accessible tables/charts and explicit benchmark confirmation; empty/loading/error states. Reports initially use available saved analysis; M11 adds complete export/history refinements.
- **Prerequisites:** M9 tested API; installed supported Node LTS; endpoint contracts stable. Use the Sites skill if its website workflow applies at this point; source remains in the official repository.
- **Verification:** ESLint, TypeScript, component tests (submit, recommendations, budgets, charts, loading/errors), keyboard/accessibility checks, responsive views and real backend/PG E2E; no synthetic metrics presented as actual.
- **Acceptance:** every view uses backend data, no unwired controls; budget submission changes the saved optimizer result; measured charts use measured results; one full real workload flows to recommendations on screen.
- **GitHub deliverable:** `Connect the IndexPilot dashboard to the analysis API` with screenshots only of functioning features.

## M11 — Reports, history and usability

- **Objective:** make saved analyses comparable and downloadable without confusing past and current state.
- **DBMS concepts:** immutable experiments, provenance, reproducibility and historical identity.
- **Files:** `reports/{models,render,service}.py`, `api/{history,reports}.py`, saved-report migration, frontend history/report improvements and tests.
- **Functionality:** paginated/filterable histories; JSON/Markdown reports with SQL, parameters policy, costs, sizes, settings, selected/rejected reasons and benchmark links; explicit missing-evidence sections; durable report identity and version; safe downloadable filenames.
- **Prerequisites:** M10 workflows plus M8/M9 durable data.
- **Verification:** exports match stored values/units; missing benchmarks are identified; large history paginates; SQL text is escaped in HTML contexts; no secrets, traversal or response header injection; report survives restart.
- **Acceptance:** download a real analysis summary through UI/API; previous budgets and benchmark runs remain reconstructible; errors tell the user what to fix; docs match actual commands and fields.
- **GitHub deliverable:** `Add analysis history and downloadable optimization reports` and real sanitized sample export.

## M12 — End-to-end validation, CI and final engineering evaluation

- **Objective:** verify clean-clone reproduction and honestly assess the complete implementation.
- **DBMS concepts:** evaluate cost-model accuracy, sensitivity to data/statistics and read/write trade-offs.
- **Files:** `.github/workflows/ci.yml` (extend earlier checks as introduced), full integration/E2E suites, `scripts/check.*`, final docs, actual screenshots and evidence summaries.
- **Functionality:** CI Ruff/unit/API, PostgreSQL/HypoPG integration, migration, frontend type/lint/component/build and real E2E jobs; documented production safety limits and clean setup; benchmark findings and greedy limitations.
- **Prerequisites:** M0–M11 acceptance; container engine, Node and GitHub Actions access. Add useful CI checks earlier rather than deferring all automation here.
- **Verification:** clean checkout with locked dependencies; start → connect → ingest → plans/stats → candidates → hypothetical sets → budget selection → dashboard → confirmed isolated physical benchmark → comparisons → history → report → restart/reload; test both missing-extension and insufficient-privilege paths; audit tracked files for secrets; verify remote head and CI results.
- **Acceptance:** all 18 completion requirements in the original brief have concrete evidence; all relevant automated suites pass; three benchmark arms include performance and storage; limitations are documented; no claims based on skipped tests; all completed changes pushed.
- **GitHub deliverable:** `Validate the end-to-end IndexPilot workflow` with final measured report, CI links and installation guide. Tagging/release is optional and never substitutes for checks.

## Advanced work after the essential path

Evaluate rather than promise: partial/expression/INCLUDE indexes; extended statistics; partitioned relations/views; automatic representative parameter collection with privacy controls; ongoing monitoring; more access methods; search strategies that capture pure complementarity; exhaustive comparisons on tiny sets. Each requires separate safety, correctness and performance evidence.
