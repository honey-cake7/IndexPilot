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
