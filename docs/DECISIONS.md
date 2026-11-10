# Technical decisions

Decisions at M0 are specifications, not implementation claims.

## D001 — Modular monolith, engine first

Keep one Python backend with domain packages and explicit data contracts. Pure parsing/candidate/optimizer logic stays independent of FastAPI. This makes correctness tests and CLI experiments possible before HTTP or charts. Separate services and distributed queues would add operational cost without helping the initial problem.

## D002 — Separate metadata, target and disposable benchmark databases

Use SQLAlchemy/Alembic only for metadata; use psycopg 3 for PostgreSQL catalogs, planning and controlled extension sessions. Separate roles prevent metadata migrations or benchmark DDL from accidentally running on the analyzed database. Store credential references and resolve secrets from local configuration; do not put plaintext passwords in metadata.

## D003 — PostgreSQL 18 reference environment

Target PostgreSQL 18 with pg_stat_statements and HypoPG. M1 verified PostgreSQL 18.6 and HypoPG 1.4.3 in a digest-pinned official container; HypoPG is built from a fixed revision with checksum verification. Python dependencies are locked in uv.lock. Supporting every PostgreSQL version initially would multiply extension/statistics compatibility paths; capability detection will report unsupported differences explicitly.

## D004 — AST and catalog resolution, bounded SQL support

Use pglast rather than regex SQL parsing. Reject unsupported constructs explicitly. Restrict early planning to trusted ordinary tables and supported built-in operators/types, and inspect privileges. A SELECT-only keyword check fails for modifying CTEs and side-effecting functions. EXPLAIN is not a sandbox for hostile database code.

## D005 — HypoPG sessions are exclusively held

Hypothetical indexes exist in one backend session. Baseline, resets, candidate-set creation, EXPLAIN and cleanup must use that same dedicated connection. Pool checkout/return between calls would produce incorrect results. Ordinary analyses never use EXPLAIN ANALYZE; real timing belongs to the disposable benchmark runner.

## D006 — Greedy marginal net benefit per byte

Use actual planner evaluation of each selected-set-plus-candidate combination with a weighted workload objective and hard storage budget. Optional write penalty is explicitly heuristic. Greedy search is explainable and bounded but can miss complementarities; tiny exhaustive comparisons are optional experiments.

## D007 — Snapshot deltas with provenance

Persist raw cumulative counters and reset/eviction metadata. Calculate interval changes only when comparable. New entries, resets and evictions can make interval inference ambiguous. Do not present a server-lifetime mean as the most recent interval mean or derive percentiles from totals.

## D008 — Local-only initial application and reproducible evidence

Bind locally with configured targets, bounded inputs and a restrictive origin policy. A public multi-user deployment needs a later authentication/authorization/security design. No fake demo metrics, benchmark claims or passing integration claims based on mocks. Pin dependencies when installed and update documentation with actual tested commands.

## D009 — Git identity and publishing

The repository is initially empty with default branch main. Windows Git Credential Manager authenticates as repository owner `honey-cake7` (Aniket Patil), with admin/push permission and no active rulesets. Local Git author is configured to that verified identity using the pre-existing configured developer email. The connected GitHub app is a different account with read-only access here, so repository publication uses authenticated local Git. Never change global identity or expose credentials.

## D010 — M3 admission is explicitly syntactic

M3 uses pglast's PostgreSQL 18 parser to admit a conservative SELECT subset, fingerprint patterns and safely transform parameter AST nodes. No submitted SQL is executed or explained. Representative strings are labeled syntax_only, because catalog resolution, overloaded operators, relation kinds and cast semantics require M4. Missing parameters remain unresolved. Input bytes, statement counts and AST complexity are bounded before persistence.

## D011 — Raw snapshots, conservative deltas and source-clock timestamps

Use pg_stat_statements 1.12, persisting raw counters and full server identity/reset metadata. Unknown/new/reset/evicted intervals return null metrics with reasons rather than optimistic estimates. Compare reset/deallocation metadata around the scan; do not claim an atomic statistics snapshot. A real repeated test exposed coarse Windows clock ticks; use PostgreSQL clock_timestamp for collection boundaries. Serialize query IDs as decimal JSON strings to preserve 64-bit precision in JavaScript.

## D012 — Explicit periodic collection and milestone review

An explicit bounded CLI or repeated snapshot requests provide periodic collection; no hidden daemon or distributed queue is introduced. Users supply representative parameter values, and scenario frequencies are explicit weights. As requested, finish, test, document, commit and push each milestone, then wait for the user's instruction before starting the next.

## D013 — Conservative catalog validation before planning

M4 resolves table/column identity and privileges and rejects unsupported relation/type/index dependencies before EXPLAIN. Qualified internal SQL and a pg_catalog search_path prevent ordinary schema-name shadowing. Existing user-defined constraint/index functions are refused, not assumed safe because SELECT is read-only. Only a trusted local database is supported; this is not a hostile-server sandbox. User SQL is never executed with ANALYZE.

## D014 — Schema-aware patterns and saved plan evidence

A real check showed pglast fingerprints ignore schemas. M4 combines structural identity with explicit relation scope, preserving public qualification equivalence while separating same-named relations across schemas. Existing M3 public-only records remain valid. Migration 0003 stores resolved schema/statistics context alongside raw plans and settings; it does not rely on future catalog state to explain historical results. Costs retain explicit planner units, and raw estimated plans with execution metrics are rejected.

## D015 — Statistics visibility and index semantics

Default inspection omits histogram/common-value text; opt-in values are formatted only for supported built-in column types with access. Index metadata retains expressions/predicates, key versus INCLUDE columns, opclasses, collations and sort/null flags for later accurate deduplication. Approximate uniform selectivity and cumulative usage remain labeled; neither is sufficient justification for an index recommendation or removal.

## D016 — Bounded candidates before hypothetical evaluation

M5 generates singleton/composite B-Tree alternatives from direct conjunctions, inner equality joins and compatible ordering. It caps width at three, proposed count at 32, the working pool at 512 and attempts at 4096; limits and structural priority are explicit. Equality-first order is a heuristic, not a theorem that other orders or PostgreSQL 18 skip scans cannot work. No benefit/size numbers are fabricated; M6 evaluates the candidates.

## D017 — Structural duplication and conservative overlap

Exact suppression compares live/ready/valid ordinary index signatures, including opclasses, collations and ordering. Matching unique indexes use a separate coverage reason. Partial/expression/covering, longer-prefix and backward-order relationships are not silently treated as identical general indexes. Current indexes are refreshed and stale source identities/types rejected. Identifier quoting and verified catalog opclasses produce deterministic DDL.

## D018 — Normalized candidate evidence with data-preserving migration

The working M5 prototype initially stored evidence alongside definitions. Migration 0005 preserves it while splitting candidate/plan/alias/reason relationships into a foreign-keyed table, supporting later query explanations without dangling plan IDs. A saved prototype batch survived downgrade/re-upgrade unchanged. Candidate definitions remain structured snapshots; evidence relationships are relational. Pytest now uses importlib mode so unit/integration modules can share meaningful basenames without import collisions.

## D019 — Fresh, complete-set planning in one context

M6 uses one exclusively held repeatable-read/read-only target connection per run. It refreshes source identities/catalogs, reruns SQL resolution, recompiles saved candidate definitions structurally and obtains a fresh empty-set baseline. Every trial replans all queries with the whole set present. Historical M4 costs and additive singleton percentages cannot substitute for this comparison. Parameter bindings preserved as AST literals are revalidated rather than interpolated. Frequency-weighted root costs remain planner units, not runtime.

## D020 — Explicit HypoPG cleanup and scoped caching

Live tests show rollback leaves hypothetical indexes in session memory. Always reset and verify both hypothetical and hidden-index state, recovering aborted transactions only to perform cleanup. Failed cleanup discards the physical connection. The private 65-set cache belongs to one fixed copied context and checks selected planner settings; any failure invalidates it. No cross-run cache is implemented, avoiding claims of reliable shared statistics/schema invalidation. Repeatable read does not freeze every planner input or physical change.

## D021 — Separate immutable evaluation evidence

M6 migration 0006 normalizes run/query/set/member/plan rows and records outcomes atomically after synchronous execution. Generation snapshots remain unchanged; evaluation evidence has its own identity. Failed/unavailable runs publish no partial comparisons, and missing costs/sizes are null rather than zero. Optional size access can be absent while cost planning remains usable. Unknown bytes cannot justify a future hard-budget selection. No measured speedup, write penalty, optimizer decision or physical deployment is inferred from these estimates.

## D022 — Complete greedy rounds with deterministic marginal scoring

M7 scores every selected-set-plus-candidate trial using freshly available whole-set estimates: frequency-weighted root cost plus optional heuristic write penalty. Rank positive feasible gain per additional estimated byte, then absolute gain, canonical signature and UUID. Query regression limits compare to the original baseline. Complete each round before choosing; reserve one final uncached evaluation, and stop before a round that cannot fit the allowance. This prevents evaluation-limit order bias. Greedy can miss complementary pairs; optional exhaustive search remains deferred.

## D023 — Estimated-byte budget and explicit heuristic write units

The budget applies to additional hypothetical bytes, not existing indexes or guaranteed physical disk consumption. Every selected set requires known positive member estimates and an actual complete-set total within budget. Unknown, zero/negative member sizes and nonpositive incremental bytes cannot earn a free selection. Default write penalty is zero; user weights default to one and share a declared scenario/frequency basis. The penalty is expressed in weighted planner-cost units per MiB, never measured write latency. Read improvement and penalized objective are separate fields.

## D024 — Fresh verification and atomic optimization history

M7 extends the evaluator with bounded per-run cache capacity and an explicit refresh call. The final set is replanned without a cache hit; budget/regressions/positive gain must pass and cost/size drift from the accepted trial fails the run rather than preserving stale claims. One metadata transaction saves normalized evaluation evidence, optimizer outcomes, selected order and foreign-keyed trial choices. A real induced membership constraint failure verified full rollback. Failed/unavailable searches save safe evaluation outcomes without partial selections. Rich recommendation artifacts/explanations remain M8 work.

## D025 — Metadata-only, versioned recommendation snapshots

M8 freezes completed optimization evidence without reconnecting to the target. One recommendation per optimization is created transactionally, with bounded row-lock serialization for duplicate requests. Selected definitions, settings, source context, raw plans, observation times and deterministic explanation metrics are copied into normalized scoped rows. No update/delete endpoint rewrites history. Source FKs retain provenance, while later source edits do not alter the snapshot. Current target validity is explicitly unverified; this is not protection against a privileged metadata administrator changing stored rows.

## D026 — Separate final query contributions from index marginals

Query contribution is frequency times baseline-minus-final root cost, expressed relative to the original workload baseline. It can be negative for regressions and is undefined as a percentage over zero. Index benefit instead records the actual selection-step marginal read/objective change with its trial link. Never independently attribute the final total to every index. Missing statistics, unavailable ANALYZE timestamps, unused final indexes, greedy limits and unmeasured runtime/write effects remain explicit. Evidence level is qualitative planner_estimate, not an invented confidence probability.

## D027 — Quoted SQL is a separate, non-executing artifact

At snapshot creation M8 rebuilds index SQL from saved structure/catalog context and checks signature/definition agreement. Only selected frozen commands are exported through JSON or a plain SQL download, with review warnings. Hypothetical names/OIDs are not deployment identities. No arbitrary DDL request or production execution route is added. Empty selections contain no commands; physical benchmarking remains M9 and requires an explicitly isolated target and confirmation.

## D028 — Owned benchmark namespaces with two transport checks

M9 accepts only explicitly confirmed recommendation IDs in the fixed disposable database/owner/marker. Live identities exclude demo/metadata/monitored aliases, and a nonce proves the fixed Compose pgbench client reaches the guarded database. All physical indexes/data belong to generated UUID-owned schemas; public indexes/data remain untouched. Source SQL is AST-rebound/re-resolved against a compatible template, and multiline/backslash literals are refused at the additional pgbench language boundary. Cleanup drops known objects without CASCADE; unknown dependencies block it safely.

## D029 — Three arms, durable individual measurements and honest write probes

The unconstrained per-query singleton union is selected on a benchmark pilot dataset; IndexPilot's saved set stays fixed. Each repetition rotates arm order and restores the same seeded rows per operation. Read mixtures and single-query transactions use checked warmups. Controlled committed insert/update/delete transactions require one affected row, with independently restored write state. Transaction logs support nearest-rank p95; TPS excludes initial connection time. Raw logs stay local, samples persist relationally, and the published summary retains every repetition/outlier/regression. Main-fork index bytes, cache limitations, weight quantization and budget mismatch are explicit. WAL, cold-cache behavior and significance are not measured.

## D030 — Explicit local worker and preserved failure history

An explicit foreground/one-shot CLI consumes a bounded durable queue under metadata/target advisory locks. Cancellation/deadlines are cooperative with bounded subprocess/server statements, and only job-owned clients are terminated. Startup marks interrupted jobs failed and retries safe cleanup before claiming more work. No partial successful whole-job result is published. A real CLI smoke test exposed script-only generator imports; the shared engine generator fixes that while preserving the original CLI. Failed prototype records remain failed, with cleanup rechecked rather than fabricated.

## D031 — Larger statistics capture without discarding history

Accumulated development history made the old workload integration tests correctly see truncated 1,000-entry captures. Keep the application's default and conservative truncation/reset/eviction semantics. Add an administrator-configured 1–5,000 bound and use the full pinned-server bound for controlled tests, without clearing global statistics or weakening interval assertions. A larger full capture does not make earlier truncated snapshots usable.

## D032 - Local dashboard with generated contracts

M10 follows the Sites skill's explicit local-preview path because the existing specification requires a repository-owned Vite dashboard bound to local FastAPI/PostgreSQL. No cloud hosting, registration or credential flow is introduced. React Router resource URLs and TanStack Query provide saved-state navigation without storing SQL/parameters in localStorage. OpenAPI-generated TypeScript and openapi-fetch catch contract mistakes before a request reaches the database. TypeScript 5.9.3 satisfies the generator/linter peer ranges; dependencies and a patched minimatch override are locked. The optional Windows x64 Node helper verifies the official release checksum and changes only process PATH.

## D033 - Saved budgets and measured phase charts

Budget changes explicitly call the existing optimizer and save a new immutable result; edited settings cannot relabel or save the previous selection as new evidence. Full overview counts come from a single metadata SQL statement, while bounded history remains labeled recent/paginated. Recharts cost charts use weighted root planner units; benchmark charts use only stored phase/repetition latency means, with equivalent tables. Unknown values stay unknown. Physical benchmark requests require an unchecked explicit confirmation and a separate worker; queued/partial/cancelled/failed states never imply completion. M10 downloads existing snapshots; durable report resources remain M11.

## D034 - Real browser verification and early CI

Vitest fixtures test UI behavior, while Playwright submits actual workloads, files and typed parameters through FastAPI/PostgreSQL/HypoPG, verifies separate persisted budgets and runs a confirmed three-arm pgbench job. A quiescent local queue is a prerequisite. Named e2e metadata remains reviewable; successful worker jobs clean their owned schema. Ports 8010/5174 belong to tests and are stopped afterward; user port 8000 is preserved. Axe, keyboard and overflow checks cover all nine views at desktop/mobile widths, with screenshots of real data. CI introduces pinned actions for unit/lint/contract/frontend checks now; complete container integration CI stays in M12.

## D035 - Versioned report documents in a single metadata snapshot

M11 stores each new report with a permanent UUID, format version and indexed recommendation/title/time header; a JSONB projection freezes the artifact. Repeatable read covers all source queries plus the insert, so downloads do not join later live evidence. Intentional snapshot duplication serves reproducibility rather than replacing the normalized engine tables. The API has no report update endpoint. Generic connection/worker dictionaries are projected through allowlists; representative SQL with bound values is opt-in, typed maps/raw plans are omitted, and original SQL literals are explicitly disclosed. UUID-only attachment names and escaped Markdown prose/collision-safe code fences keep exports independent of user filenames or markup.

## D036 - Filtered history and conditional comparison

A UNION ALL provides seven saved resource kinds with literal bound search, offset-aware time bounds and deterministic ordering. Count/page share one repeatable-read snapshot; separate page requests can still shift after later inserts. Reports embed only explicitly selected terminal jobs of their recommendation, preserve partial states and require completed/cleanup-verified measurements before claiming a completed comparison. The UI compares captured budgets/costs/sizes and source identity without deriving an improvement across different workloads. Active benchmarks must finish or be cancelled first. The development backend/browser suites run sequentially because they share the local benchmark queue.
